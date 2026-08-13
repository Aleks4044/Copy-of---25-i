"""Состојба за дополнителната Fudbal91 покриеност (само за читање).

Fudbal91 редовите се спарувааат со веќе вчитаните BZZ, Fotmob, Mutating и
SportScore натпревари по нормализиран пар тимови (и по време кога е познато).
Само натпреварите што недостасуваат во тие извори се прикажуваат како
дополнителни картички, а спарените само даваат статистички контекст.
"""

import asyncio
from typing import TypedDict

import reflex as rx

from app.states import fudbal91_client
from app.states.bsd_state import local_clock, local_now
from app.states.fudbal91_client import Fudbal91Row

MAX_MISSING_CARDS = 12
MAX_TIME_DELTA = 90

MISSING_BADGE = "Fudbal91 · недостасува во BZZ"
EMPTY_MISSING_NOTE = (
    "Сите претстојни Fudbal91 натпревари од денешната понуда се веќе покриени "
    "од BZZ, Fotmob, Mutating или SportScore, па нема дополнителни картички."
)
COVERAGE_NOTE = (
    "Спарувањето е по нормализиран пар тимови (прикажани имена и имена од "
    "линкот за споредба) и по време на почеток кога изворите го објавуваат."
)
ROBOTS_NOTE = (
    "Читањето е само за читање, преку јавниот HTML и часовниот појас на "
    "изворот. Патеките quick_odds, odds_changes и modules НЕ се повикуваат."
)
SPORTSCORE_NOTE = (
    "Fudbal91 контекстот НЕ користи SportScore статистики — изведен е само од "
    "јавните просечни квоти и од реално најдените Fudbal91 статистики."
)


class CoverageEntry(TypedDict):
    key: str
    match_id: str
    minutes: int


def _minutes(label: str) -> int:
    parts = (label or "").split(":")
    if len(parts) < 2:
        return -1
    try:
        return int(parts[0]) * 60 + int(parts[1])
    except ValueError:
        return -1


def _local_minutes() -> int:
    now = local_now()
    return now.hour * 60 + now.minute


class Fudbal91State(rx.State):
    """Само реални Fudbal91 редови што недостасуваат во другите извори."""

    rows: list[Fudbal91Row] = []
    fetched_at: str = "--:--:--"
    notice: str = ""
    error: str = ""
    compare_count: int = 0
    is_loading: bool = False
    has_loaded: bool = False
    expanded_ids: list[str] = []

    @rx.var
    def coverage_note(self) -> str:
        return COVERAGE_NOTE

    @rx.var
    def robots_note(self) -> str:
        return ROBOTS_NOTE

    @rx.var
    def sportscore_note(self) -> str:
        return SPORTSCORE_NOTE

    @rx.var
    def missing_badge(self) -> str:
        return MISSING_BADGE

    @rx.var
    def total_count(self) -> int:
        return len(self.rows)

    @rx.var
    def upcoming_rows(self) -> list[Fudbal91Row]:
        return [r for r in self.rows if r["is_upcoming"]]

    @rx.var
    def upcoming_count(self) -> int:
        return len(self.upcoming_rows)

    @rx.var
    def missing_rows(self) -> list[Fudbal91Row]:
        rows = [r for r in self.upcoming_rows if not r["covered"]]
        return sorted(rows, key=lambda r: (r["kickoff_minutes"], r["home"]))[
            :MAX_MISSING_CARDS
        ]

    @rx.var
    def missing_count(self) -> int:
        return len([r for r in self.upcoming_rows if not r["covered"]])

    @rx.var
    def covered_count(self) -> int:
        return len([r for r in self.upcoming_rows if r["covered"]])

    @rx.var
    def matched_contexts(self) -> list[Fudbal91Row]:
        """Контекст за спарените BZZ/Fotmob картички (само со реален контекст)."""
        return [
            r
            for r in self.rows
            if r["covered"] and r["match_id"] != "" and r["has_context"]
        ]

    @rx.var
    def matched_context_count(self) -> int:
        return len(self.matched_contexts)

    @rx.var
    def empty_missing_note(self) -> str:
        if self.notice:
            return self.notice
        return EMPTY_MISSING_NOTE

    @rx.var
    def has_data(self) -> bool:
        return len(self.rows) > 0

    @rx.var
    def summary_label(self) -> str:
        return (
            f"{self.upcoming_count} претстојни од понудата · "
            f"{self.missing_count} недостасуваат во другите извори · "
            f"{self.covered_count} спарени · "
            f"{self.compare_count} прочитани страници за споредба"
        )

    async def _coverage(self) -> list[CoverageEntry]:
        """Идентификатори на веќе покриените натпревари од другите извори."""
        from app.states.bsd_state import BSDState
        from app.states.mutating_state import MutatingState
        from app.states.sportscore_state import SportScoreState

        entries: list[CoverageEntry] = []
        bsd = await self.get_state(BSDState)
        for match in bsd.matches:
            entries.append(
                CoverageEntry(
                    key=fudbal91_client.pair_key(match["home"], match["away"]),
                    match_id=str(match["id"]),
                    minutes=_minutes(match["kickoff"]),
                )
            )
        mutating = await self.get_state(MutatingState)
        for row in mutating.rows:
            if row["has_names"]:
                entries.append(
                    CoverageEntry(
                        key=fudbal91_client.pair_key(row["home"], row["away"]),
                        match_id="",
                        minutes=_minutes(row["kickoff"]),
                    )
                )
        sportscore = await self.get_state(SportScoreState)
        for row in sportscore.rows:
            entries.append(
                CoverageEntry(
                    key=str(row["pair_key"]),
                    match_id="",
                    minutes=_minutes(row["kickoff"]),
                )
            )
        return [entry for entry in entries if entry["key"]]

    def _resolve(
        self, fixture: dict, entries: list[CoverageEntry]
    ) -> tuple[bool, str]:
        keys = {fixture["display_pair"], fixture["slug_pair"]}
        keys.discard("")
        minutes = int(fixture["kickoff_minutes"])
        covered = False
        match_id = ""
        for entry in entries:
            if entry["key"] not in keys:
                continue
            other = entry["minutes"]
            if (
                minutes >= 0
                and other >= 0
                and abs(other - minutes) > (MAX_TIME_DELTA)
            ):
                continue
            covered = True
            if entry["match_id"] and not match_id:
                match_id = entry["match_id"]
        return covered, match_id

    def _rebuild(
        self,
        fixtures: list[dict],
        compares: dict[str, fudbal91_client.Fudbal91Compare],
        entries: list[CoverageEntry],
    ) -> None:
        now_minutes = _local_minutes()
        rows: list[Fudbal91Row] = []
        for fixture in fixtures:
            covered, match_id = self._resolve(fixture, entries)
            minutes = int(fixture["kickoff_minutes"])
            is_upcoming = minutes < 0 or minutes >= now_minutes
            rows.append(
                fudbal91_client.build_row(
                    fudbal91_client.Fudbal91Fixture(**fixture),
                    compares.get(fixture["compare_url"]),
                    covered,
                    match_id,
                    is_upcoming,
                )
            )
        self.rows = sorted(
            rows, key=lambda r: (r["kickoff_minutes"], r["home"])
        )
        self.compare_count = len(
            [url for url, value in compares.items() if value["has_mutual"]]
        )

    def _compare_targets(
        self, fixtures: list[dict], entries: list[CoverageEntry]
    ) -> list[str]:
        """Прво непокриените претстојни, потоа спарените — со тврд лимит."""
        now_minutes = _local_minutes()
        missing: list[dict] = []
        matched: list[dict] = []
        for fixture in fixtures:
            minutes = int(fixture["kickoff_minutes"])
            if minutes >= 0 and minutes < now_minutes:
                continue
            covered, match_id = self._resolve(fixture, entries)
            if covered and match_id:
                matched.append(fixture)
            elif not covered:
                missing.append(fixture)
        missing.sort(key=lambda f: f["kickoff_minutes"])
        matched.sort(key=lambda f: f["kickoff_minutes"])
        urls: list[str] = []
        for fixture in missing + matched:
            url = str(fixture["compare_url"])
            if url and url not in urls:
                urls.append(url)
            if len(urls) >= fudbal91_client.MAX_COMPARE_PAGES:
                break
        return urls

    async def _load(self) -> None:
        if self.is_loading:
            return
        self.is_loading = True
        try:
            fixtures, notice = await asyncio.to_thread(
                fudbal91_client.fetch_offer
            )
            if not fixtures:
                self.rows = []
                self.notice = notice
                self.error = notice
                return
            plain = [dict(fixture) for fixture in fixtures]
            entries = await self._coverage()
            urls = self._compare_targets(plain, entries)
            compares: dict[str, fudbal91_client.Fudbal91Compare] = {}
            if urls:
                compares = await asyncio.to_thread(
                    fudbal91_client.fetch_compare, urls
                )
            self._rebuild(plain, compares, entries)
            self.notice = notice
            self.error = ""
            self.fetched_at = local_clock()
            self.has_loaded = True
        finally:
            self.is_loading = False

    def _dependent_events(self):
        """Агрегатите што користат Fudbal91 изведени редови."""
        from app.states.markets_state import MarketsState
        from app.states.overview_state import OverviewState

        return [OverviewState.sync, MarketsState.sync]

    @rx.event
    async def load(self):
        if self.has_loaded or self.is_loading:
            return
        yield
        await self._load()
        yield
        for event in self._dependent_events():
            yield event

    @rx.event
    async def refresh(self):
        """Освежување од циклусот на апликацијата.

        Агрегатите (Преглед и Маркети) се синхронизираат од `AppState` по
        завршување на целиот круг, за да не се повторува истата работа.
        """
        if self.is_loading:
            return
        yield
        await self._load()
        yield

    @rx.event
    async def sync(self):
        """Повторно спарување без нови барања кон изворот."""
        if not self.rows:
            return
        entries = await self._coverage()
        now_minutes = _local_minutes()
        rows: list[Fudbal91Row] = []
        for row in self.rows:
            item = dict(row)
            covered, match_id = self._resolve(item, entries)
            minutes = int(item["kickoff_minutes"])
            item["covered"] = covered
            item["match_id"] = match_id
            item["is_upcoming"] = minutes < 0 or minutes >= now_minutes
            rows.append(Fudbal91Row(**item))
        self.rows = rows

    @rx.event
    def toggle_expanded(self, row_id: str):
        if row_id in self.expanded_ids:
            self.expanded_ids = [
                item for item in self.expanded_ids if item != row_id
            ]
            return
        self.expanded_ids = [*self.expanded_ids, row_id]
