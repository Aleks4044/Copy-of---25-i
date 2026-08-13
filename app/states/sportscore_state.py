"""Состојба за дополнителниот SportScore таб (јавен widget API)."""

import asyncio
import logging
from datetime import date, timedelta

import reflex as rx

from app.states import sportscore_client
from app.states.bsd_state import local_clock, local_today
from app.states.sportscore_client import SportScoreRow

MAX_VISIBLE = 24


def _as_date(value: str) -> date:
    if isinstance(value, str) and len(value) >= 10:
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return local_today()
    return local_today()


class SportScoreState(rx.State):
    """Само реални SportScore настани што не се покриени од другите извори."""

    selected_date: str = ""
    rows: list[SportScoreRow] = []
    fetched_at: str = "--:--:--"
    notice: str = ""
    error: str = ""
    status_filter: str = "all"
    only_uncovered: bool = True
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
    def fbref_note(self) -> str:
        return sportscore_client.FBREF_NOTE

    @rx.var
    def total_count(self) -> int:
        return len(self.rows)

    @rx.var
    def uncovered_rows(self) -> list[SportScoreRow]:
        return [r for r in self.rows if not r["covered"]]

    @rx.var
    def uncovered_count(self) -> int:
        return len(self.uncovered_rows)

    @rx.var
    def covered_count(self) -> int:
        return len(self.rows) - len(self.uncovered_rows)

    @rx.var
    def prediction_rows(self) -> list[SportScoreRow]:
        return [r for r in self.uncovered_rows if r["has_prediction"]]

    @rx.var
    def prediction_count(self) -> int:
        return len(self.prediction_rows)

    @rx.var
    def stats_count(self) -> int:
        return len([r for r in self.uncovered_rows if r["has_stats"]])

    @rx.var
    def live_count(self) -> int:
        return len([r for r in self.uncovered_rows if r["status"] == "live"])

    @rx.var
    def upcoming_count(self) -> int:
        return len(
            [r for r in self.uncovered_rows if r["status"] == "upcoming"]
        )

    @rx.var
    def finished_count(self) -> int:
        return len(
            [r for r in self.uncovered_rows if r["status"] == "finished"]
        )

    @rx.var
    def filter_tabs(self) -> list[dict[str, str]]:
        return [
            {
                "key": "all",
                "label": "Сите",
                "count": str(self.uncovered_count),
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
            {
                "key": "prediction",
                "label": "Со препорака",
                "count": str(self.prediction_count),
            },
        ]

    @rx.var
    def visible_rows(self) -> list[SportScoreRow]:
        rows = self.uncovered_rows if self.only_uncovered else list(self.rows)
        if self.status_filter == "prediction":
            rows = [r for r in rows if r["has_prediction"]]
        elif self.status_filter != "all":
            rows = [r for r in rows if r["status"] == self.status_filter]
        order = {"live": 0, "upcoming": 1, "finished": 2}
        rows = sorted(
            rows,
            key=lambda r: (order.get(r["status"], 3), r["kickoff"]),
        )
        return rows[:MAX_VISIBLE]

    @rx.var
    def visible_count(self) -> int:
        return len(self.visible_rows)

    @rx.var
    def has_data(self) -> bool:
        return len(self.rows) > 0

    @rx.var
    def avg_confidence(self) -> float:
        rows = self.prediction_rows
        if not rows:
            return 0.0
        return round(
            sum(r["meta_confidence"] for r in rows) / len(rows),
            1,
        )

    async def _covered_pairs(self) -> set[str]:
        from app.states.bsd_state import BSDState
        from app.states.mutating_state import MutatingState

        keys: set[str] = set()
        bsd = await self.get_state(BSDState)
        for match in bsd.matches:
            keys.add(sportscore_client.pair_key(match["home"], match["away"]))
        mutating = await self.get_state(MutatingState)
        for row in mutating.rows:
            if row["has_names"]:
                keys.add(sportscore_client.pair_key(row["home"], row["away"]))
        return keys

    def _mark_unavailable(self, notice: str) -> None:
        """Празна, но исправна состојба кога SportScore не е достапен."""
        self.rows = []
        self.enriched_count = 0
        self.notice = notice
        self.error = notice
        self.has_loaded = True
        self.is_loading = False
        self.fetched_at = local_clock()

    async def _load(self):
        """Безбедно вчитување: мрежните грешки никогаш не се пренесуваат нагоре."""
        self.is_loading = True
        day = self.selected_date_value
        try:
            rows, notice = await asyncio.to_thread(
                sportscore_client.fetch_rows, day, sportscore_client.MATCH_LIMIT
            )
        except Exception as error:
            logging.exception("Unexpected error")
            logging.info(
                f"SportScore не е достапен: {type(error).__name__}. "
                "Прикажана е ознака за недостапност."
            )
            self._mark_unavailable(sportscore_client.UNAVAILABLE_NOTE)
            return
        if not rows:
            self._mark_unavailable(notice or sportscore_client.UNAVAILABLE_NOTE)
            return
        try:
            covered = await self._covered_pairs()
        except Exception as error:
            logging.exception("Unexpected error")
            logging.info(
                f"SportScore покриеноста не е пресметана: {type(error).__name__}"
            )
            covered = set()
        plain: list[SportScoreRow] = []
        for row in rows:
            item = dict(row)
            item["covered"] = item["pair_key"] in covered
            plain.append(item)
        targets = [r for r in plain if not r["covered"]]
        enriched = 0
        if targets:
            try:
                enriched = await asyncio.to_thread(
                    sportscore_client.enrich_rows,
                    targets,
                    sportscore_client.DETAIL_LIMIT,
                )
            except Exception as error:
                logging.exception("Unexpected error")
                logging.info(
                    f"SportScore деталите не се вчитани: {type(error).__name__}"
                )
                enriched = 0
        self.rows = plain
        self.enriched_count = enriched
        self.notice = notice
        self.error = ""
        self.has_loaded = True
        self.is_loading = False
        self.fetched_at = local_clock()

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
        from app.states.overview_state import OverviewState

        yield OverviewState.sync

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
        from app.states.overview_state import OverviewState

        yield OverviewState.sync

    @rx.event
    async def shift_day(self, offset: int):
        target = _as_date(self.selected_date_value) + timedelta(days=offset)
        self.selected_date = target.isoformat()
        yield
        await self._load()
        yield
        from app.states.overview_state import OverviewState

        yield OverviewState.sync

    @rx.event
    def set_status_filter(self, key: str):
        self.status_filter = key

    @rx.event
    def toggle_only_uncovered(self):
        self.only_uncovered = not self.only_uncovered
