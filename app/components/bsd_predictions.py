import reflex as rx

from app.components.api_status import (
    error_banner,
    loading_skeleton,
    warning_banner,
)
from app.components.fudbal91_panel import fudbal91_section
from app.components.match_card import match_card
from app.components.supplemental_predictions import supplemental_predictions
from app.states.bsd_state import BSDState


def _sub_tab(key: str, label: str, icon: str, count: rx.Var) -> rx.Component:
    return rx.el.button(
        rx.icon(icon, class_name="h-3.5 w-3.5 shrink-0"),
        rx.el.span(label, class_name="whitespace-nowrap"),
        rx.el.span(
            count.to_string(),
            class_name=rx.cond(
                BSDState.sub_tab == key,
                "rounded-full bg-blue-500/20 px-1.5 text-[10px] font-bold text-blue-200 tabular-nums",
                "rounded-full bg-zinc-800 px-1.5 text-[10px] font-bold text-zinc-400 tabular-nums",
            ),
        ),
        on_click=lambda: BSDState.set_sub_tab(key),
        class_name=rx.cond(
            BSDState.sub_tab == key,
            "flex flex-1 items-center justify-center gap-2 rounded-lg border border-blue-500/40 bg-blue-500/10 px-3 py-2 text-xs font-semibold text-blue-300 transition-all sm:text-sm",
            "flex flex-1 items-center justify-center gap-2 rounded-lg border border-transparent px-3 py-2 text-xs font-semibold text-zinc-500 transition-all hover:bg-zinc-900 hover:text-zinc-200 sm:text-sm",
        ),
    )


def _sub_nav() -> rx.Component:
    return rx.el.div(
        _sub_tab("all", "Сите", "layers", BSDState.all_count),
        _sub_tab(
            "today", "Претстојни денес", "calendar-days", BSDState.today_count
        ),
        _sub_tab("tomorrow", "Утре", "calendar-plus", BSDState.tomorrow_count),
        _sub_tab("live", "Live", "radio", BSDState.live_count),
        _sub_tab(
            "finished", "Завршени", "circle-check", BSDState.finished_count
        ),
        class_name="flex w-full items-center gap-1 overflow-x-auto rounded-xl border border-zinc-800 bg-zinc-900/40 p-1",
    )


def _nav_button(
    label: str, icon: str, handler: rx.event.EventType
) -> rx.Component:
    return rx.el.button(
        rx.icon(icon, class_name="h-3.5 w-3.5 shrink-0"),
        rx.el.span(label, class_name="whitespace-nowrap"),
        on_click=handler,
        class_name="flex shrink-0 items-center gap-2 rounded-lg border border-zinc-800 bg-zinc-900/60 px-3 py-2 text-xs font-semibold text-zinc-300 transition-colors hover:border-zinc-700 hover:text-white",
    )


def _date_controls() -> rx.Component:
    """Календар за BZZ датумот (стандардно локалниот ден во Македонија)."""
    return rx.el.div(
        rx.el.div(
            rx.icon(
                "calendar-days", class_name="h-4 w-4 shrink-0 text-blue-400"
            ),
            rx.el.div(
                rx.el.span(
                    "Избран датум",
                    class_name="text-[10px] font-semibold uppercase tracking-wider text-zinc-500",
                ),
                rx.el.input(
                    type="date",
                    default_value=BSDState.selected_date_value,
                    on_change=BSDState.set_selected_date,
                    class_name="mt-0.5 w-full rounded-lg border border-zinc-800 bg-zinc-950/60 px-2 py-1 text-xs font-semibold text-zinc-200 outline-hidden transition-colors [color-scheme:dark] hover:border-zinc-700 focus:border-blue-500/50",
                ),
                class_name="flex min-w-0 flex-col",
            ),
            class_name="flex min-w-0 flex-1 items-center gap-2.5 rounded-xl border border-zinc-800 bg-zinc-900/50 px-3 py-2",
        ),
        rx.el.div(
            _nav_button(
                "Претходен",
                "chevron-left",
                lambda: BSDState.shift_day(-1),
            ),
            _nav_button(
                "Следен", "chevron-right", lambda: BSDState.shift_day(1)
            ),
            rx.cond(
                BSDState.is_today_selected,
                rx.fragment(),
                _nav_button("Денес", "calendar-check", BSDState.select_today),
            ),
            rx.el.button(
                rx.icon(
                    "refresh-cw",
                    class_name=rx.cond(
                        BSDState.is_loading,
                        "h-3.5 w-3.5 animate-spin",
                        "h-3.5 w-3.5",
                    ),
                ),
                rx.el.span("Вчитај датум", class_name="whitespace-nowrap"),
                on_click=BSDState.reload_selected,
                class_name="flex shrink-0 items-center gap-2 rounded-lg bg-blue-600 px-3 py-2 text-xs font-semibold text-white transition-colors hover:bg-blue-500",
            ),
            class_name="flex flex-wrap items-center gap-2",
        ),
        class_name="mb-4 flex w-full flex-col gap-2 sm:flex-row sm:items-center",
    )


def _summary_chip(label: str, value: rx.Var | str, icon: str) -> rx.Component:
    return rx.el.div(
        rx.icon(icon, class_name="h-3.5 w-3.5 text-zinc-500"),
        rx.el.span(label, class_name="text-[11px] font-medium text-zinc-500"),
        rx.el.span(
            value,
            class_name="text-xs font-semibold text-zinc-200 tabular-nums",
        ),
        class_name="flex items-center gap-2 rounded-lg border border-zinc-800 bg-zinc-900/50 px-3 py-1.5",
    )


def _empty_state() -> rx.Component:
    return rx.el.div(
        rx.icon("calendar-off", class_name="h-6 w-6 text-zinc-600"),
        rx.el.p(
            BSDState.empty_label,
            class_name="mt-2 text-sm font-medium text-zinc-500",
        ),
        class_name="flex w-full flex-col items-center justify-center rounded-xl border border-zinc-800 bg-zinc-900/40 py-14",
    )


def bsd_predictions() -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.el.div(
                rx.el.h2(
                    "BSD Предвидувања",
                    class_name="text-xl font-semibold tracking-tight text-white sm:text-2xl",
                ),
                rx.el.p(
                    f"{BSDState.window_label} · {BSDState.window_count} вчитани настани · {BSDState.generated_at}",
                    class_name="mt-1 text-sm font-medium text-zinc-500",
                ),
                rx.el.p(
                    BSDState.source_breakdown_label,
                    class_name="mt-1 text-xs font-medium text-zinc-400",
                ),
                rx.el.p(
                    "Настаните без предвидување, одложените и откажаните "
                    "остануваат видливи во табот „Сите“.",
                    class_name="mt-1 text-xs font-medium text-zinc-600",
                ),
                class_name="flex min-w-0 flex-col",
            ),
            rx.el.div(
                _summary_chip(
                    "Натпревари",
                    BSDState.visible_count.to_string(),
                    "list-checks",
                ),
                _summary_chip(
                    "Средна сигурност",
                    f"{BSDState.avg_visible_confidence:.1f}%",
                    "gauge",
                ),
                _summary_chip(
                    "Со вредност",
                    BSDState.value_visible_count.to_string(),
                    "badge-dollar-sign",
                ),
                class_name="flex flex-wrap items-center gap-2",
            ),
            class_name="mb-4 flex w-full flex-col gap-3 lg:flex-row lg:items-end lg:justify-between",
        ),
        _date_controls(),
        error_banner(BSDState.error),
        warning_banner(BSDState.stats_notice),
        _sub_nav(),
        rx.cond(
            BSDState.is_loading,
            loading_skeleton(),
            rx.cond(
                BSDState.visible_count > 0,
                rx.el.div(
                    rx.foreach(
                        BSDState.visible_matches,
                        lambda m: match_card(m),
                    ),
                    class_name="mt-4 grid w-full grid-cols-1 gap-4 2xl:grid-cols-2",
                ),
                rx.el.div(_empty_state(), class_name="mt-4 w-full"),
            ),
        ),
        fudbal91_section(),
        supplemental_predictions(),
        class_name="w-full",
    )
