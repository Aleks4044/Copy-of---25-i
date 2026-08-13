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
    # Бавните јавни HTML извори (Mutating, SportScore, Fudbal91) се освежуваат
    # само на секој N-ти автоматски круг, и то́а САМО ако веќе биле вчитани.
    slow_cycle_every: int = 4
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

    def _lazy_events(self, tab: str) -> list:
        """Отложено вчитување на тежките извори — само за отворениот таб."""
        from app.states.fudbal91_state import Fudbal91State
        from app.states.markets_state import MarketsState
        from app.states.models_state import ModelsState
        from app.states.mutating_state import MutatingState
        from app.states.overview_state import OverviewState
        from app.states.sportscore_state import SportScoreState

        events: list = []
        if tab in ("bsd", "sources", "markets"):
            events.append(MutatingState.load)
        if tab in ("bsd", "sportscore", "markets"):
            events.append(SportScoreState.load)
        if tab in ("bsd", "markets"):
            events.append(Fudbal91State.load)
        if tab == "models":
            events.append(ModelsState.load)
        if events or tab in ("home", "markets"):
            events.extend([OverviewState.sync, MarketsState.sync])
        return events

    async def _fast_events(self) -> list:
        """Брз примарен пат: BZZ/Fotmob + агрегатите, без бавни HTML извори.

        Рачното освежување НИКОГАШ не чека Mutating, SportScore или Fudbal91
        мрежни барања — тие се вчитуваат кога корисникот ќе го отвори табот
        или на бавен круг од автоматското освежување (и то́а само ако веќе
        биле вчитани).
        """
        from app.states.bsd_state import BSDState
        from app.states.fudbal91_state import Fudbal91State
        from app.states.markets_state import MarketsState
        from app.states.mutating_state import MutatingState
        from app.states.overview_state import OverviewState

        events: list = [BSDState.refresh_data]
        fudbal91 = await self.get_state(Fudbal91State)
        if fudbal91.has_loaded:
            # Само повторно спарување со новите BZZ редови (без мрежа).
            events.append(Fudbal91State.sync)
        events.append(MutatingState.sync_coverage)
        events.append(OverviewState.sync)
        events.append(MarketsState.sync)
        return events

    async def _cycle_events(self, slow: bool) -> list:
        """Настани за едно освежување; бавните извори само кога е потребно."""
        from app.states.bsd_state import BSDState
        from app.states.fudbal91_state import Fudbal91State
        from app.states.markets_state import MarketsState
        from app.states.models_state import ModelsState
        from app.states.mutating_state import MutatingState
        from app.states.overview_state import OverviewState
        from app.states.sportscore_state import SportScoreState

        events: list = [BSDState.refresh_data]
        if slow:
            mutating = await self.get_state(MutatingState)
            if mutating.has_loaded and not mutating.is_loading:
                events.append(MutatingState.refresh)
            sportscore = await self.get_state(SportScoreState)
            if sportscore.has_loaded and not sportscore.is_loading:
                events.append(SportScoreState.refresh)
            fudbal91 = await self.get_state(Fudbal91State)
            if fudbal91.has_loaded and not fudbal91.is_loading:
                events.append(Fudbal91State.refresh)
        else:
            fudbal91 = await self.get_state(Fudbal91State)
            if fudbal91.has_loaded:
                # Само повторно спарување, без нови мрежни барања.
                events.append(Fudbal91State.sync)
        events.append(MutatingState.sync_coverage)
        events.append(OverviewState.sync)
        events.append(MarketsState.sync)
        if slow:
            events.append(ModelsState.sync)
        return events

    @rx.event
    async def set_tab(self, tab: str):
        if tab == self.active_tab:
            return
        self.active_tab = tab
        yield
        for event in self._lazy_events(tab):
            yield event

    @rx.event
    def bootstrap(self):
        """Единствен `on_load` влез: не чека ниту едно мрежно барање.

        Само подига две background задачи — иницијалното BZZ вчитување и
        часовникот за автоматско освежување — така што страницата се
        рендерира и хидрира веднаш.
        """
        from app.states.bsd_state import BSDState

        yield BSDState.startup_load
        yield AppState.start_clock

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
        if self.is_refreshing:
            return
        self.is_refreshing = True
        self.seconds_until_refresh = self.refresh_interval
        yield
        try:
            # Само брзиот примарен пат: BZZ/Fotmob за избраниот датум и
            # агрегатите (Преглед и Маркети). Бавните јавни HTML извори не се
            # чекаат синхроно, за да не се надмине практичното време на едно
            # рачно освежување.
            for event in await self._fast_events():
                yield event
        finally:
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
            events: list = []
            async with self:
                if not self.auto_refresh or self.is_refreshing:
                    continue
                self.seconds_until_refresh -= 1
                if self.seconds_until_refresh > 0:
                    continue
                self.seconds_until_refresh = self.refresh_interval
                self.is_refreshing = True
                self.tick_count += 1
                slow = (self.tick_count % max(1, self.slow_cycle_every)) == 0
                events = await self._cycle_events(slow)

            try:
                for event in events:
                    yield event
            finally:
                async with self:
                    await self._apply_backoff()
                    self.last_updated = local_clock()
                    self.is_refreshing = False
