import reflex as rx

from app.states.app_state import AppState


def _live_dot() -> rx.Component:
    return rx.el.span(
        rx.el.span(
            class_name="absolute inset-0 rounded-full bg-blue-500 animate-ping opacity-60"
        ),
        rx.el.span(class_name="relative block size-2 rounded-full bg-blue-400"),
        class_name="relative flex size-2 items-center justify-center",
    )


def refresh_controls() -> rx.Component:
    return rx.el.div(
        rx.el.div(
            _live_dot(),
            rx.el.span(
                AppState.refresh_label,
                class_name="text-xs font-medium text-zinc-400 tabular-nums",
            ),
            class_name="flex items-center gap-2 rounded-full border border-zinc-800 bg-zinc-900/70 px-3 py-1.5",
        ),
        rx.el.button(
            rx.cond(
                AppState.auto_refresh,
                rx.icon("pause", class_name="h-4 w-4"),
                rx.icon("play", class_name="h-4 w-4"),
            ),
            rx.el.span(
                rx.cond(AppState.auto_refresh, "Пауза", "Продолжи"),
                class_name="hidden sm:inline",
            ),
            on_click=AppState.toggle_auto_refresh,
            class_name="flex items-center gap-2 rounded-lg border border-zinc-800 bg-zinc-900/70 px-3 py-2 text-xs font-semibold text-zinc-300 transition-colors hover:border-zinc-700 hover:text-white",
        ),
        rx.el.button(
            rx.icon(
                "refresh-cw",
                class_name=rx.cond(
                    AppState.is_refreshing,
                    "h-4 w-4 animate-spin",
                    "h-4 w-4",
                ),
            ),
            rx.el.span("Освежи", class_name="hidden sm:inline"),
            on_click=AppState.refresh_now,
            class_name="flex items-center gap-2 rounded-lg bg-blue-600 px-3 py-2 text-xs font-semibold text-white transition-colors hover:bg-blue-500",
        ),
        class_name="flex flex-wrap items-center gap-2",
    )


def header() -> rx.Component:
    return rx.el.header(
        rx.el.div(
            rx.el.div(
                rx.el.div(
                    rx.icon("target", class_name="h-5 w-5 text-blue-400"),
                    class_name="flex size-10 items-center justify-center rounded-xl border border-blue-500/30 bg-blue-500/10",
                ),
                rx.el.div(
                    rx.el.h1(
                        "BSD Фудбал",
                        class_name="text-lg font-semibold tracking-tight text-white sm:text-xl",
                    ),
                    rx.el.p(
                        "Аналитика и предвидувања во реално време",
                        class_name="text-xs font-medium text-zinc-500",
                    ),
                    class_name="flex flex-col",
                ),
                class_name="flex items-center gap-3",
            ),
            rx.el.div(
                rx.el.div(
                    rx.el.span(
                        "Последно ажурирање",
                        class_name="text-[11px] font-medium uppercase tracking-wider text-zinc-500",
                    ),
                    rx.el.span(
                        AppState.last_updated,
                        class_name="text-sm font-semibold text-zinc-200 tabular-nums",
                    ),
                    class_name="hidden flex-col items-end md:flex",
                ),
                refresh_controls(),
                class_name="flex items-center gap-4",
            ),
            class_name="mx-auto flex w-full max-w-7xl flex-col gap-4 px-4 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-6",
        ),
        rx.el.div(
            rx.el.div(
                class_name="h-full bg-blue-500/70 transition-all duration-1000 ease-linear",
                style={"width": f"{AppState.refresh_progress}%"},
            ),
            class_name="h-[2px] w-full bg-zinc-900",
        ),
        class_name="sticky top-0 z-30 border-b border-zinc-800/80 bg-zinc-950/85 backdrop-blur",
    )
