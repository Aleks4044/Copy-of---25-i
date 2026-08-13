"""Состојба за табот „ESPN Football“ (јавни, само-читачки endpoints)."""

import asyncio
from datetime import date, timedelta

import reflex as rx

from app.states import espn_client
from app.states.bsd_state import local_clock, local_today
from app.states.espn_client import ESPNRow

MAX_VISIBLE = 30


def _as_date(value: str) -> date:
    if isinstance(value, str) and len(value) >= 10:
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return local_today()
    return local_today()


class ESPNState(rx.State):
    """Реални ESPN настани; предвидување само од реални статистики/квоти."""

    selected_date: str = ""
    rows: list[ESPNRow] = []
    fetched_at: str = "--:--:--"
    notice: str = ""
    error: str = ""
    status_filter: str = "all"
    league_filter: str = "all"
    is_loading: bool = False
    has_loaded: bool = False
    enriched_count: int = 0

    @rx.var
    def selected_date_value(self) -> str:
        return self.selected_date or local_today().isoformat()

    @rx.var
    def selected_date_label(self) -> str:
        return _as_date(self.selected_date_value).strftime("%d.%m.%Y")

    @rx.var
    def league_options(self) -> list[dict[str, str]]:
        options: list[dict[str, str]] = [{"key": "all", "label": "Сите лиги"}]
        for key, label in espn_client.LEAGUES:
            options.append({"key": key, "label": label})
        return options

    @rx.var
    def league_count(self) -> int:
        return len(espn_client.LEAGUES)

    @rx.var
    def total_count(self) -> int:
        return len(self.rows)

    @rx.var
    def league_rows(self) -> list[ESPNRow]:
        if self.league_filter == "all":
            return list(self.rows)
        return [r for r in self.rows if r["league_key"] == self.league_filter]

    @rx.var
    def live_count(self) -> int:
        return len([r for r in self.league_rows if r["status"] == "live"])

    @rx.var
    def upcoming_count(self) -> int:
        return len([r for r in self.league_rows if r["status"] == "upcoming"])

    @rx.var
    def finished_count(self) -> int:
        return len([r for r in self.league_rows if r["status"] == "finished"])

    @rx.var
    def prediction_rows(self) -> list[ESPNRow]:
        return [r for r in self.rows if r["has_prediction"]]

    @rx.var
    def prediction_count(self) -> int:
        return len(self.prediction_rows)

    @rx.var
    def stats_count(self) -> int:
        return len([r for r in self.rows if r["has_stats"]])

    @rx.var
    def odds_count(self) -> int:
        return len([r for r in self.rows if r["has_odds"]])

    @rx.var
    def uncovered_count(self) -> int:
        return len([r for r in self.rows if not r["covered"]])

    @rx.var
    def avg_confidence(self) -> float:
        rows = self.prediction_rows
        if not rows:
            return 0.0
        return round(sum(r["confidence"] for r in rows) / len(rows), 1)

    @rx.var
    def filter_tabs(self) -> list[dict[str, str]]:
        return [
            {
                "key": "all",
                "label": "Сите",
                "count": str(len(self.league_rows)),
            },
            {"key": "live", "label": "Во тек", "count": str(self.live_count)},
            {
                "key": "upcoming",
                "label": "Претстојни",
                "count": str(self.upcoming_count),
            },
            {
                "key": "finished",
                "label": "Завршени",
                "count": str(self.finished_count),
            },
        ]

    @rx.var
    def visible_rows(self) -> list[ESPNRow]:
        rows = self.league_rows
        if self.status_filter != "all":
            rows = [r for r in rows if r["status"] == self.status_filter]
        order = {"live": 0, "upcoming": 1, "finished": 2}
        rows = sorted(
            rows,
            key=lambda r: (order.get(r["status"], 3), r["kickoff"], r["home"]),
        )
        return rows[:MAX_VISIBLE]

    @rx.var
    def visible_count(self) -> int:
        return len(self.visible_rows)

    @rx.var
    def has_data(self) -> bool:
        return len(self.rows) > 0

    @rx.var
    def empty_label(self) -> str:
        if self.error:
            return self.error
        if self.notice:
            return self.notice
        return espn_client.EMPTY_NOTE

    async def _covered_keys(self) -> set[str]:
        from app.states.bsd_state import BSDState

        keys: set[str] = set()
        bsd = await self.get_state(BSDState)
        for match in bsd.matches:
            keys.add(espn_client.pair_key(match["home"], match["away"]))
        return keys

    async def _load(self) -> None:
        self.is_loading = True
        rows, notice = await asyncio.to_thread(
            espn_client.fetch_rows, self.selected_date_value, None
        )
        self.fetched_at = local_clock()
        self.has_loaded = True
        if not rows:
            self.rows = []
            self.notice = notice
            self.error = notice
            self.is_loading = False
            return
        covered = await self._covered_keys()
        plain: list[ESPNRow] = []
        for row in rows:
            item = dict(row)
            item["covered"] = item["pair_key"] in covered
            plain.append(item)
        enriched = await asyncio.to_thread(
            espn_client.enrich_rows, plain, espn_client.DETAIL_LIMIT
        )
        self.rows = plain
        self.enriched_count = enriched
        self.notice = notice
        self.error = ""
        self.is_loading = False

    @rx.event
    async def load(self):
        if self.has_loaded or self.is_loading:
            return
        yield
        await self._load()
        yield

    @rx.event
    async def refresh(self):
        if self.is_loading:
            return
        yield
        await self._load()
        yield

    @rx.event
    async def sync(self):
        """Повторно спарување со BZZ, без нови мрежни барања."""
        if not self.rows:
            return
        covered = await self._covered_keys()
        rows: list[ESPNRow] = []
        for row in self.rows:
            item = dict(row)
            item["covered"] = item["pair_key"] in covered
            rows.append(ESPNRow(**item))
        self.rows = rows

    @rx.event
    async def set_selected_date(self, value: str):
        cleaned = (value or "").strip()[:10]
        try:
            date.fromisoformat(cleaned)
        except ValueError:
            return
        self.selected_date = cleaned
        yield
        await self._load()
        yield

    @rx.event
    async def shift_day(self, offset: int):
        target = _as_date(self.selected_date_value) + timedelta(days=offset)
        self.selected_date = target.isoformat()
        yield
        await self._load()
        yield

    @rx.event
    def set_status_filter(self, key: str):
        self.status_filter = key

    @rx.event
    def set_league_filter(self, key: str):
        self.league_filter = key
