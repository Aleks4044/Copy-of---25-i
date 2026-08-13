"""Состојба за табот „T1x2“ (само јавни, само-читачки страници)."""

import asyncio

import reflex as rx

from app.states import t1x2_client
from app.states.bsd_state import local_clock
from app.states.t1x2_client import T1x2Page, T1x2Snippet, T1x2Tipster

MAX_VISIBLE = 24


class T1x2State(rx.State):
    """Само реални јавни извадоци од t1x2.net; ништо не се измислува."""

    snippets: list[T1x2Snippet] = []
    tipsters: list[T1x2Tipster] = []
    pages: list[T1x2Page] = []
    capabilities: list[str] = []
    category_filter: str = "all"
    fetched_at: str = "--:--:--"
    note: str = ""
    error: str = ""
    is_loading: bool = False
    has_loaded: bool = False

    @rx.var
    def attribution(self) -> str:
        return t1x2_client.ATTRIBUTION

    @rx.var
    def total_count(self) -> int:
        return len(self.snippets)

    @rx.var
    def odds_count(self) -> int:
        return len([row for row in self.snippets if row["has_odds"]])

    @rx.var
    def marker_count(self) -> int:
        return len([row for row in self.snippets if row["has_markers"]])

    @rx.var
    def triple_count(self) -> int:
        return len([row for row in self.snippets if row["has_triple"]])

    @rx.var
    def tipster_count(self) -> int:
        return len(self.tipsters)

    @rx.var
    def reachable_count(self) -> int:
        return len([page for page in self.pages if page["ok"]])

    @rx.var
    def page_count(self) -> int:
        return len(self.pages)

    @rx.var
    def category_tabs(self) -> list[dict[str, str]]:
        tabs: list[dict[str, str]] = [
            {"key": "all", "label": "Сите", "count": str(len(self.snippets))}
        ]
        for key, category, _path in t1x2_client.PUBLIC_PAGES:
            count = len(
                [row for row in self.snippets if row["category_key"] == key]
            )
            tabs.append({"key": key, "label": category, "count": str(count)})
        return tabs

    @rx.var
    def visible_snippets(self) -> list[T1x2Snippet]:
        rows = list(self.snippets)
        if self.category_filter != "all":
            rows = [
                row
                for row in rows
                if row["category_key"] == self.category_filter
            ]
        rows.sort(
            key=lambda row: (
                0 if row["has_triple"] else 1,
                0 if row["has_odds"] else 1,
                -row["odds_count"],
            )
        )
        return rows[:MAX_VISIBLE]

    @rx.var
    def visible_count(self) -> int:
        return len(self.visible_snippets)

    @rx.var
    def has_data(self) -> bool:
        return len(self.snippets) > 0

    @rx.var
    def empty_label(self) -> str:
        if self.error:
            return self.error
        return t1x2_client.EMPTY_NOTE

    @rx.var
    def extraction_note(self) -> str:
        return t1x2_client.NOT_EXTRACTABLE

    async def _load(self) -> None:
        self.is_loading = True
        snapshot = await asyncio.to_thread(t1x2_client.fetch_snapshot, True)
        self.pages = list(snapshot["pages"])
        self.capabilities = list(snapshot["capabilities"])
        self.tipsters = list(snapshot["tipsters"])
        self.note = snapshot["note"]
        self.fetched_at = local_clock()
        self.has_loaded = True
        if snapshot["snippets"]:
            self.snippets = list(snapshot["snippets"])
            self.error = ""
        else:
            self.snippets = []
            self.error = snapshot["error"]
        self.is_loading = False

    @rx.event
    async def load(self):
        from app.states.multi_source_state import MultiSourceState

        if self.has_loaded or self.is_loading:
            yield MultiSourceState.fetch_all_matches
            return
        yield
        await self._load()
        yield
        yield MultiSourceState.fetch_all_matches

    @rx.event
    async def refresh(self):
        from app.states.multi_source_state import MultiSourceState

        if self.is_loading:
            yield MultiSourceState.fetch_all_matches
            return
        yield
        await self._load()
        yield
        yield MultiSourceState.fetch_all_matches

    @rx.event
    def set_category_filter(self, key: str):
        self.category_filter = key
