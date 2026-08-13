import reflex as rx

from app.states.app_state import AppState

TABS: list[dict[str, str]] = [
    {"key": "home", "label": "Почетна", "icon": "house"},
    {"key": "bsd", "label": "BSD Предвидувања", "icon": "activity"},
    {"key": "models", "label": "25 Модели", "icon": "brain"},
    {"key": "markets", "label": "Комбинирани", "icon": "layers"},
    {"key": "sources", "label": "Mutating", "icon": "database"},
    {"key": "sportscore", "label": "Дополнителни", "icon": "globe"},
]


def tab_button(tab: dict[str, str]) -> rx.Component:
    return rx.el.button(
        rx.icon(tab["icon"], class_name="h-4 w-4 shrink-0"),
        rx.el.span(tab["label"], class_name="whitespace-nowrap"),
        on_click=lambda: AppState.set_tab(tab["key"]),
        class_name=rx.cond(
            AppState.active_tab == tab["key"],
            "flex flex-1 items-center justify-center gap-2 rounded-lg border border-blue-500/40 bg-blue-500/10 px-3 py-2.5 text-xs font-semibold text-blue-300 transition-all sm:text-sm",
            "flex flex-1 items-center justify-center gap-2 rounded-lg border border-transparent px-3 py-2.5 text-xs font-semibold text-zinc-500 transition-all hover:bg-zinc-900 hover:text-zinc-200 sm:text-sm",
        ),
    )


def tab_nav() -> rx.Component:
    return rx.el.nav(
        rx.el.div(
            rx.foreach(TABS, tab_button),
            class_name="mx-auto flex w-full max-w-7xl items-center gap-1 overflow-x-auto rounded-xl border border-zinc-800 bg-zinc-900/40 p-1",
        ),
        class_name="mx-auto w-full max-w-7xl px-4 pt-5 sm:px-6",
    )
