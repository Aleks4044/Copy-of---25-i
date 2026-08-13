"""Состојба за панелот „BZZ извори по настан“ (читање по барање)."""

import asyncio

import reflex as rx

from app.states import bzz_sources
from app.states.bzz_sources import SourcePanel

MAX_PANELS = 24


class BzzSourceState(rx.State):
    """Ги чува прочитаните подресурси по настан, без измислени вредности."""

    panels: list[SourcePanel] = []
    open_ids: list[str] = []
    loading_ids: list[str] = []

    @rx.var
    def loaded_ids(self) -> list[str]:
        return [panel["match_id"] for panel in self.panels]

    @rx.var
    def loaded_count(self) -> int:
        return len(self.panels)

    async def _fetch(self, match_id: str):
        """Ги чита подресурсите за еден настан (помошен генератор)."""
        if match_id in self.loaded_ids or match_id in self.loading_ids:
            return

        from app.states.bsd_state import BSDState

        bsd = await self.get_state(BSDState)
        event_id = 0
        label = ""
        for match in bsd.matches:
            if match["id"] == match_id:
                event_id = int(match["event_id"])
                label = f"{match['home']} — {match['away']}"
                break
        if event_id <= 0:
            return

        self.loading_ids = [*self.loading_ids, match_id]
        yield
        panel = await asyncio.to_thread(
            bzz_sources.fetch_panel, event_id, match_id, label
        )
        rows = [item for item in self.panels if item["match_id"] != match_id]
        rows.append(panel)
        self.panels = rows[-MAX_PANELS:]
        self.loading_ids = [
            item for item in self.loading_ids if item != match_id
        ]
        yield

    @rx.event
    async def toggle(self, match_id: str):
        """Отвора/затвора панел и го чита изворот при прво отворање."""
        if match_id in self.open_ids:
            self.open_ids = [item for item in self.open_ids if item != match_id]
            return
        self.open_ids = [*self.open_ids, match_id]
        async for event in self._fetch(match_id):
            yield event

    @rx.event
    async def reload(self, match_id: str):
        """Повторно читање на подресурсите за истиот настан."""
        self.panels = [
            item for item in self.panels if item["match_id"] != match_id
        ]
        if match_id not in self.open_ids:
            self.open_ids = [*self.open_ids, match_id]
        async for event in self._fetch(match_id):
            yield event

    @rx.event
    def clear(self):
        """Ги чисти панелите (пр. при промена на датумот)."""
        self.panels = []
        self.open_ids = []
        self.loading_ids = []
