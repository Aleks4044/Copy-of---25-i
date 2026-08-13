import asyncio

import reflex as rx

from app.states.bsd_state import local_clock


class AppState(rx.State):
    """Навигација помеѓу главните табови и автоматско освежување."""

    active_tab: str = "home"
    auto_refresh: bool = True
    # Стандарден интервал; кога има натпревари во тек се користи пократок
    # интервал за да бидат резултатот, минутата и статусот што поблиску до
    # реално време, но сè уште во разумни граници за јавните API-ја.
    base_interval: int = 45
    live_interval: int = 20
    backoff_interval: int = 180
    refresh_interval: int = 45
    seconds_until_refresh: int = 45
    backoff_active: bool = False
    live_active: bool = False
    is_refreshing: bool = False
    loop_active: bool = False
    # Секој трет live круг вклучува и целосно освежување на Mutating
    # изворот, за да не се праќаат премногу барања кон јавната страница.
    tick_count: int = 0
    last_updated: str = "--:--:--"

    @rx.var
    def refresh_progress(self) -> float:
        if self.refresh_interval <= 0:
            return 0.0
        elapsed = self.refresh_interval - self.seconds_until_refresh
        return round(elapsed / self.refresh_interval * 100, 1)

    @rx.var
    def refresh_label(self) -> str:
        if not self.auto_refresh:
            return "Автоматско освежување: исклучено"
        if self.backoff_active:
            return (
                "Ограничено од API-то · следно освежување за "
                f"{self.seconds_until_refresh}с"
            )
        if self.live_active:
            return f"Live режим · освежување за {self.seconds_until_refresh}с"
        return f"Следно освежување за {self.seconds_until_refresh}с"

    async def _apply_backoff(self) -> None:
        """Го приспособува интервалот според 429 и според live натпревари."""
        from app.states.bsd_state import BSDState

        bsd = await self.get_state(BSDState)
        self.backoff_active = bsd.rate_limited
        self.live_active = (not bsd.rate_limited) and bsd.live_count > 0
        if bsd.rate_limited:
            self.refresh_interval = self.backoff_interval
        elif self.live_active:
            self.refresh_interval = self.live_interval
        else:
            self.refresh_interval = self.base_interval
        if self.seconds_until_refresh > self.refresh_interval:
            self.seconds_until_refresh = self.refresh_interval

    @rx.event
    def set_tab(self, tab: str):
        self.active_tab = tab

    @rx.event
    def toggle_auto_refresh(self):
        self.auto_refresh = not self.auto_refresh
        self.seconds_until_refresh = self.refresh_interval
        message = (
            "Автоматското освежување е вклучено"
            if self.auto_refresh
            else "Автоматското освежување е паузирано"
        )
        return rx.toast(message, duration=2000)

    @rx.event
    async def refresh_now(self):
        from app.states.bsd_state import BSDState
        from app.states.fudbal91_state import Fudbal91State
        from app.states.markets_state import MarketsState
        from app.states.models_state import ModelsState
        from app.states.mutating_state import MutatingState
        from app.states.overview_state import OverviewState
        from app.states.sportscore_state import SportScoreState
        from app.states.t1x2_state import T1x2State

        self.is_refreshing = True
        self.seconds_until_refresh = self.refresh_interval
        yield
        # Прво BZZ/Fotmob (за тековно избраниот датум), потоа Mutating
        # покриеноста и SportScore, и на крај агрегатите.
        yield BSDState.refresh_data
        yield MutatingState.refresh
        yield MutatingState.sync_coverage
        yield SportScoreState.refresh
        yield Fudbal91State.refresh
        yield T1x2State.refresh
        yield OverviewState.sync
        yield MarketsState.sync
        yield ModelsState.sync
        await self._apply_backoff()
        self.last_updated = local_clock()
        self.is_refreshing = False

    @rx.event(background=True)
    async def start_clock(self):
        async with self:
            if self.loop_active:
                return
            self.loop_active = True
            self.last_updated = local_clock()

        while True:
            await asyncio.sleep(1)
            do_refresh = False
            light_cycle = False
            async with self:
                if not self.auto_refresh:
                    continue
                self.seconds_until_refresh -= 1
                if self.seconds_until_refresh <= 0:
                    self.seconds_until_refresh = self.refresh_interval
                    self.is_refreshing = True
                    self.tick_count += 1
                    # Во live режим само секој трет круг го освежува и
                    # Mutating изворот (јавна HTML страница).
                    light_cycle = self.live_active and (
                        self.tick_count % 3 != 0
                    )
                    do_refresh = True

            if not do_refresh:
                continue

            from app.states.bsd_state import BSDState
            from app.states.fudbal91_state import Fudbal91State
            from app.states.markets_state import MarketsState
            from app.states.models_state import ModelsState
            from app.states.mutating_state import MutatingState
            from app.states.overview_state import OverviewState
            from app.states.sportscore_state import SportScoreState
            from app.states.t1x2_state import T1x2State

            yield BSDState.refresh_data
            if not light_cycle:
                yield MutatingState.refresh
            yield MutatingState.sync_coverage
            yield SportScoreState.refresh
            if light_cycle:
                yield Fudbal91State.sync
            else:
                yield Fudbal91State.refresh
                yield T1x2State.refresh
            yield OverviewState.sync
            yield MarketsState.sync
            if not light_cycle:
                yield ModelsState.sync

            async with self:
                await self._apply_backoff()
                self.last_updated = local_clock()
                self.is_refreshing = False
