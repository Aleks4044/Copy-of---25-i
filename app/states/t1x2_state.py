"""Состојба за табот „T1x2“ · предвидувања од football-data.co.uk и SportScore.

football-data.co.uk се чита САМО преку директно преземање на јавни CSV
фајлови (без стругање на HTML), а SportScore преку веќе постоечкиот безбеден
клиент. Ниту еден ред не се измислува: ако изворот не даде реални бројки,
редот воопшто не постои или стои како „недостапно“.
"""

import asyncio

import reflex as rx

from app.states import football_data_client as fd
from app.states.bsd_state import local_clock
from app.states.football_data_client import FDStatus, FootballDataRow

MAX_VISIBLE = 36


class T1x2State(rx.State):
    """Реални football-data.co.uk редови со јасно означена хеуристика."""

    rows: list[FootballDataRow] = []
    statuses: list[FDStatus] = []
    league_filter: str = "all"
    fetched_at: str = "--:--:--"
    note: str = ""
    error: str = ""
    is_loading: bool = False
    has_loaded: bool = False

    @rx.var
    def attribution(self) -> str:
        return fd.ATTRIBUTION

    @rx.var
    def no_xg_note(self) -> str:
        return fd.NO_XG_NOTE

    @rx.var
    def total_count(self) -> int:
        return len(self.rows)

    @rx.var
    def league_rows(self) -> list[FootballDataRow]:
        if self.league_filter == "all":
            return list(self.rows)
        return [
            row for row in self.rows if row["league_key"] == self.league_filter
        ]

    @rx.var
    def prediction_count(self) -> int:
        return len([row for row in self.rows if row["has_prediction"]])

    @rx.var
    def odds_count(self) -> int:
        return len([row for row in self.rows if row["has_odds"]])

    @rx.var
    def stats_count(self) -> int:
        return len([row for row in self.rows if row["has_stats"]])

    @rx.var
    def settled_count(self) -> int:
        return len([row for row in self.rows if row["settled"]])

    @rx.var
    def correct_count(self) -> int:
        return len(
            [row for row in self.rows if row["settled"] and row["is_correct"]]
        )

    @rx.var
    def accuracy_rate(self) -> float:
        settled = self.settled_count
        if settled == 0:
            return 0.0
        return round(self.correct_count / settled * 100.0, 1)

    @rx.var
    def avg_confidence(self) -> float:
        rows = [row for row in self.rows if row["has_prediction"]]
        if not rows:
            return 0.0
        return round(sum(row["confidence"] for row in rows) / len(rows), 1)

    @rx.var
    def available_source_count(self) -> int:
        return len([row for row in self.statuses if row["available"]])

    @rx.var
    def source_count(self) -> int:
        return len(self.statuses)

    @rx.var
    def league_tabs(self) -> list[dict[str, str]]:
        tabs: list[dict[str, str]] = [
            {"key": "all", "label": "Сите лиги", "count": str(len(self.rows))}
        ]
        for key, label in fd.LEAGUES:
            count = len([row for row in self.rows if row["league_key"] == key])
            if count == 0:
                continue
            tabs.append({"key": key, "label": label, "count": str(count)})
        return tabs

    @rx.var
    def visible_rows(self) -> list[FootballDataRow]:
        return self.league_rows[:MAX_VISIBLE]

    @rx.var
    def visible_count(self) -> int:
        return len(self.visible_rows)

    @rx.var
    def has_data(self) -> bool:
        return len(self.rows) > 0

    @rx.var
    def summary_label(self) -> str:
        return (
            f"{self.total_count} реални CSV редови · "
            f"{self.prediction_count} со хеуристичко предвидување · "
            f"{self.odds_count} со објавени квоти · "
            f"{self.available_source_count} од {self.source_count} лиги достапни"
        )

    @rx.var
    def empty_label(self) -> str:
        if self.error:
            return self.error
        return fd.EMPTY_NOTE

    async def _load(self) -> None:
        self.is_loading = True
        try:
            snapshot = await asyncio.to_thread(fd.fetch_snapshot)
        except Exception as error:
            import logging

            logging.exception(
                f"Error: football-data читањето не успеа: {error}"
            )
            self.note = fd.ATTRIBUTION
            self.error = fd.UNAVAILABLE_NOTE
            self.fetched_at = local_clock()
            self.has_loaded = True
            self.is_loading = False
            return
        self.statuses = list(snapshot["statuses"])
        self.note = snapshot["note"]
        self.fetched_at = local_clock()
        self.has_loaded = True
        if snapshot["rows"]:
            self.rows = list(snapshot["rows"])
            self.error = ""
        else:
            self.rows = []
            self.error = snapshot["error"]
        if self.league_filter != "all" and all(
            row["league_key"] != self.league_filter for row in self.rows
        ):
            self.league_filter = "all"
        self.is_loading = False

    @rx.event
    async def load(self):
        """Безбедно вчитување за on_load: без грешки и без измислени редови."""
        from app.states.sportscore_state import SportScoreState

        if self.has_loaded or self.is_loading:
            yield SportScoreState.load
            return
        yield
        await self._load()
        yield
        yield SportScoreState.load

    @rx.event
    async def refresh(self):
        if self.is_loading:
            return
        yield
        await self._load()
        yield

    @rx.event
    async def refresh_all(self):
        """Рачно освежување на двата извора од копчето во табот."""
        from app.states.sportscore_state import SportScoreState

        yield T1x2State.refresh
        yield SportScoreState.refresh

    @rx.event
    def set_league_filter(self, key: str):
        self.league_filter = key
