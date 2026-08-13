import reflex as rx

from app.components.api_status import (
    loading_skeleton,
    unavailable_note,
    warning_banner,
)
from app.states.sportscore_client import SportScoreRow, SportScoreStat
from app.states.sportscore_state import SportScoreState


def _chip(label: str, value: rx.Var | str, icon: str) -> rx.Component:
    return rx.el.div(
        rx.icon(icon, class_name="h-3.5 w-3.5 text-zinc-500"),
        rx.el.span(label, class_name="text-[11px] font-medium text-zinc-500"),
        rx.el.span(
            value,
            class_name="text-xs font-semibold text-zinc-200 tabular-nums",
        ),
        class_name="flex items-center gap-2 rounded-lg border border-zinc-800 bg-zinc-900/50 px-3 py-1.5",
    )


def _header() -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.el.h2(
                "Дополнителни · SportScore",
                class_name="text-xl font-semibold tracking-tight text-white sm:text-2xl",
            ),
            rx.el.p(
                f"Јавен widget API без клуч · избран датум {SportScoreState.selected_date_label} · вчитано во {SportScoreState.fetched_at} · {SportScoreState.total_count} настани, {SportScoreState.covered_count} веќе покриени од BZZ/Fotmob/Mutating",
                class_name="mt-1 max-w-3xl text-sm font-medium text-zinc-500",
            ),
            rx.el.p(
                f"Детали (статистики, минута и полувреме) се читаат за до {SportScoreState.enriched_count} непокриени настани од /api/widget/match/. Препораката се пресметува САМО од реални статистики; ако ги нема, стои „недостапно“.",
                class_name="mt-1 max-w-3xl text-xs font-medium text-zinc-600",
            ),
            class_name="flex min-w-0 flex-col",
        ),
        rx.el.div(
            _chip(
                "Непокриени",
                SportScoreState.uncovered_count.to_string(),
                "unlink",
            ),
            _chip(
                "Со статистики",
                SportScoreState.stats_count.to_string(),
                "chart-no-axes-column",
            ),
            _chip(
                "Со препорака",
                SportScoreState.prediction_count.to_string(),
                "crown",
            ),
            _chip(
                "Средна сигурност",
                f"{SportScoreState.avg_confidence:.1f}%",
                "gauge",
            ),
            class_name="flex flex-wrap items-center gap-2",
        ),
        class_name="mb-4 flex w-full flex-col gap-3 lg:flex-row lg:items-end lg:justify-between",
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
                    default_value=SportScoreState.selected_date_value,
                    on_change=SportScoreState.set_selected_date,
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
                lambda: SportScoreState.shift_day(-1),
            ),
            _nav_button(
                "Следен",
                "chevron-right",
                lambda: SportScoreState.shift_day(1),
            ),
            rx.el.button(
                rx.icon(
                    rx.cond(
                        SportScoreState.only_uncovered, "check-check", "check"
                    ),
                    class_name="h-3.5 w-3.5",
                ),
                rx.el.span("Само непокриени", class_name="whitespace-nowrap"),
                on_click=SportScoreState.toggle_only_uncovered,
                class_name=rx.cond(
                    SportScoreState.only_uncovered,
                    "flex shrink-0 items-center gap-2 rounded-lg border border-blue-500/40 bg-blue-500/10 px-3 py-2 text-xs font-semibold text-blue-300 transition-colors",
                    "flex shrink-0 items-center gap-2 rounded-lg border border-zinc-800 bg-zinc-900/60 px-3 py-2 text-xs font-semibold text-zinc-400 transition-colors hover:border-zinc-700 hover:text-zinc-200",
                ),
            ),
            rx.el.button(
                rx.icon(
                    "refresh-cw",
                    class_name=rx.cond(
                        SportScoreState.is_loading,
                        "h-3.5 w-3.5 animate-spin",
                        "h-3.5 w-3.5",
                    ),
                ),
                rx.el.span("Вчитај датум", class_name="whitespace-nowrap"),
                on_click=SportScoreState.refresh,
                class_name="flex shrink-0 items-center gap-2 rounded-lg bg-blue-600 px-3 py-2 text-xs font-semibold text-white transition-colors hover:bg-blue-500",
            ),
            class_name="flex flex-wrap items-center gap-2",
        ),
        class_name="mb-4 flex w-full flex-col gap-2 sm:flex-row sm:items-center",
    )


def _filter_tab(tab: dict[str, str]) -> rx.Component:
    return rx.el.button(
        rx.el.span(tab["label"], class_name="whitespace-nowrap"),
        rx.el.span(
            tab["count"],
            class_name=rx.cond(
                SportScoreState.status_filter == tab["key"],
                "rounded-full bg-blue-500/20 px-1.5 text-[10px] font-bold text-blue-200 tabular-nums",
                "rounded-full bg-zinc-800 px-1.5 text-[10px] font-bold text-zinc-400 tabular-nums",
            ),
        ),
        on_click=lambda: SportScoreState.set_status_filter(tab["key"]),
        class_name=rx.cond(
            SportScoreState.status_filter == tab["key"],
            "flex flex-1 items-center justify-center gap-2 rounded-lg border border-blue-500/40 bg-blue-500/10 px-3 py-2 text-xs font-semibold text-blue-300 transition-all sm:text-sm",
            "flex flex-1 items-center justify-center gap-2 rounded-lg border border-transparent px-3 py-2 text-xs font-semibold text-zinc-500 transition-all hover:bg-zinc-900 hover:text-zinc-200 sm:text-sm",
        ),
    )


def _emblem(logo: rx.Var, name: rx.Var) -> rx.Component:
    return rx.el.div(
        rx.cond(
            logo != "",
            rx.image(
                src=logo,
                alt="",
                loading="lazy",
                aria_hidden="true",
                class_name="size-5 object-contain",
            ),
            rx.icon("shield", class_name="h-3 w-3 text-zinc-600"),
        ),
        aria_hidden="true",
        class_name="flex size-7 shrink-0 items-center justify-center overflow-hidden rounded-md border border-zinc-800 bg-zinc-950/70",
    )


def _status_pill(row: SportScoreRow) -> rx.Component:
    return rx.el.span(
        rx.match(
            row["status"],
            (
                "live",
                rx.cond(
                    row["minute_label"] != "",
                    row["minute_label"],
                    row["status_text"],
                ),
            ),
            ("finished", "Завршен"),
            row["kickoff"],
        ),
        class_name=rx.match(
            row["status"],
            (
                "live",
                "w-fit whitespace-nowrap rounded-full border border-blue-500/40 bg-blue-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-blue-300 tabular-nums",
            ),
            (
                "finished",
                "w-fit whitespace-nowrap rounded-full border border-zinc-700 bg-zinc-800/60 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-zinc-400",
            ),
            "w-fit whitespace-nowrap rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-emerald-300 tabular-nums",
        ),
    )


def _stat_row(stat: SportScoreStat) -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.el.span(
                stat["home"],
                class_name="w-12 text-xs font-semibold text-zinc-200 tabular-nums",
            ),
            rx.el.span(
                stat["label"],
                class_name="min-w-0 flex-1 truncate text-center text-[11px] font-medium text-zinc-500",
            ),
            rx.el.span(
                stat["away"],
                class_name="w-12 text-right text-xs font-semibold text-zinc-200 tabular-nums",
            ),
            class_name="flex items-center gap-2",
        ),
        rx.el.div(
            rx.el.div(
                class_name="h-full rounded-full bg-blue-500 transition-all duration-700",
                style={"width": f"{stat['home_pct']}%"},
            ),
            class_name="mt-1 h-1 w-full overflow-hidden rounded-full bg-zinc-800",
        ),
        class_name="w-full min-w-0",
    )


def _stats_block(row: SportScoreRow) -> rx.Component:
    return rx.cond(
        row["has_stats"],
        rx.el.div(
            rx.el.span(
                "SportScore статистики",
                class_name="text-[10px] font-semibold uppercase tracking-wider text-zinc-500",
            ),
            rx.el.div(
                rx.foreach(row["stats"], _stat_row),
                class_name="mt-2 flex flex-col gap-2",
            ),
            class_name="mt-2.5 w-full min-w-0 rounded-lg border border-zinc-800 bg-zinc-950/50 px-3 py-2.5",
        ),
        rx.el.div(
            unavailable_note(row["prediction_note"]),
            class_name="mt-2.5 w-full",
        ),
    )


def _prediction_block(row: SportScoreRow) -> rx.Component:
    return rx.cond(
        row["has_prediction"],
        rx.el.div(
            rx.el.div(
                rx.el.span(
                    "Meta-Ensemble · од SportScore статистики",
                    class_name="text-[10px] font-semibold uppercase tracking-wider text-amber-300/80",
                ),
                rx.el.span(
                    f"{row['meta_confidence']:.1f}%",
                    class_name="text-sm font-semibold text-amber-300 tabular-nums",
                ),
                class_name="flex flex-wrap items-center justify-between gap-2",
            ),
            rx.el.p(
                row["meta_pick"],
                class_name="mt-1 truncate text-sm font-semibold text-white",
            ),
            rx.el.div(
                rx.el.div(
                    class_name="h-full rounded-full bg-amber-400 transition-all duration-700",
                    style={"width": f"{row['meta_confidence']}%"},
                ),
                class_name="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-zinc-800",
            ),
            rx.cond(
                row["goals_pick"] != "",
                rx.el.div(
                    rx.el.span(
                        row["goals_market"],
                        class_name="truncate text-[10px] font-medium text-zinc-500",
                    ),
                    rx.el.span(
                        f"{row['goals_pick']} · {row['goals_confidence']:.1f}%",
                        class_name="whitespace-nowrap text-xs font-semibold text-blue-300 tabular-nums",
                    ),
                    class_name="mt-2 flex items-center justify-between gap-2 rounded-lg border border-zinc-800 bg-zinc-950/60 px-2.5 py-1.5",
                ),
                rx.fragment(),
            ),
            rx.el.p(
                "Без квоти · вредностите се изведени само од реални статистики "
                "(удари во гол, опасни напади, поседување, тековен резултат).",
                class_name="mt-2 text-[10px] font-medium text-zinc-600",
            ),
            class_name="mt-2.5 w-full min-w-0 rounded-lg border border-amber-500/25 bg-amber-500/[0.04] px-3 py-2.5",
        ),
        rx.fragment(),
    )


def _match_card(row: SportScoreRow) -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.el.div(
                rx.el.span(
                    row["competition"],
                    class_name="truncate text-[11px] font-semibold uppercase tracking-wider text-zinc-500",
                ),
                _status_pill(row),
                rx.cond(
                    row["has_ht"],
                    rx.el.span(
                        row["ht_label"],
                        class_name="w-fit whitespace-nowrap rounded-full border border-zinc-700 bg-zinc-800/60 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-zinc-300 tabular-nums",
                    ),
                    rx.fragment(),
                ),
                rx.el.span(
                    "SportScore",
                    class_name="w-fit whitespace-nowrap rounded-full border border-blue-500/40 bg-blue-500/10 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-blue-300",
                ),
                class_name="flex flex-wrap items-center gap-2",
            ),
            rx.el.div(
                rx.el.div(
                    _emblem(row["home_logo"], row["home"]),
                    rx.el.p(
                        row["home"],
                        class_name="truncate text-sm font-semibold text-white",
                    ),
                    class_name="flex min-w-0 flex-1 items-center gap-2",
                ),
                rx.el.span(
                    row["score"],
                    class_name="shrink-0 rounded-lg border border-zinc-800 bg-zinc-950/70 px-2.5 py-1 text-sm font-semibold text-zinc-200 tabular-nums",
                ),
                rx.el.div(
                    rx.el.p(
                        row["away"],
                        class_name="truncate text-right text-sm font-semibold text-white",
                    ),
                    _emblem(row["away_logo"], row["away"]),
                    class_name="flex min-w-0 flex-1 items-center justify-end gap-2",
                ),
                class_name="mt-2 flex items-center gap-3",
            ),
            rx.el.div(
                rx.el.span(
                    f"{row['kickoff']} · {row['status_text']}",
                    class_name="text-[11px] font-medium text-zinc-600",
                ),
                rx.cond(
                    row["detail_url"] != "",
                    rx.el.a(
                        rx.icon("external-link", class_name="h-3 w-3"),
                        rx.el.span("SportScore"),
                        href=row["detail_url"],
                        target="_blank",
                        rel="noopener noreferrer",
                        class_name="flex w-fit items-center gap-1.5 text-[10px] font-semibold text-zinc-500 transition-colors hover:text-blue-300",
                    ),
                    rx.fragment(),
                ),
                class_name="mt-1.5 flex items-center justify-between gap-2",
            ),
            class_name="min-w-0 border-b border-zinc-800 px-4 py-3.5",
        ),
        rx.el.div(
            _prediction_block(row),
            _stats_block(row),
            class_name="p-3.5 sm:p-4",
        ),
        class_name="w-full min-w-0 rounded-xl border border-zinc-800 bg-zinc-900/50 transition-colors hover:border-zinc-700",
    )


def _fbref_note() -> rx.Component:
    return rx.el.div(
        rx.icon(
            "circle-slash", class_name="mt-0.5 h-4 w-4 shrink-0 text-zinc-500"
        ),
        rx.el.div(
            rx.el.div(
                rx.el.p(
                    "FBref",
                    class_name="text-sm font-semibold tracking-tight text-white",
                ),
                rx.el.span(
                    "Не се користи",
                    class_name="w-fit whitespace-nowrap rounded-full border border-zinc-700 bg-zinc-800/60 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-zinc-400",
                ),
                class_name="flex flex-wrap items-center gap-2",
            ),
            rx.el.p(
                SportScoreState.fbref_note,
                class_name="mt-1 text-xs font-medium text-zinc-500",
            ),
            class_name="flex min-w-0 flex-col",
        ),
        class_name="mt-4 flex w-full items-start gap-3 rounded-xl border border-dashed border-zinc-800 bg-zinc-900/40 px-4 py-3",
    )


def sportscore_view() -> rx.Component:
    return rx.el.div(
        _header(),
        _date_controls(),
        warning_banner(SportScoreState.notice),
        rx.cond(
            SportScoreState.is_loading & ~SportScoreState.has_data,
            loading_skeleton(),
            rx.cond(
                SportScoreState.has_data,
                rx.el.div(
                    rx.el.div(
                        rx.foreach(SportScoreState.filter_tabs, _filter_tab),
                        class_name="flex w-full items-center gap-1 overflow-x-auto rounded-xl border border-zinc-800 bg-zinc-900/40 p-1",
                    ),
                    rx.cond(
                        SportScoreState.visible_count > 0,
                        rx.el.div(
                            rx.foreach(
                                SportScoreState.visible_rows, _match_card
                            ),
                            class_name="mt-4 grid w-full grid-cols-1 gap-4 lg:grid-cols-2 2xl:grid-cols-3",
                        ),
                        rx.el.div(
                            rx.icon(
                                "filter-x", class_name="h-6 w-6 text-zinc-600"
                            ),
                            rx.el.p(
                                "Нема SportScore настани за избраниот филтер",
                                class_name="mt-2 text-sm font-medium text-zinc-500",
                            ),
                            class_name="mt-4 flex w-full flex-col items-center justify-center rounded-xl border border-zinc-800 bg-zinc-900/40 py-14",
                        ),
                    ),
                    _fbref_note(),
                    class_name="w-full",
                ),
                rx.el.div(
                    unavailable_note(
                        rx.cond(
                            SportScoreState.error != "",
                            SportScoreState.error,
                            "SportScore не врати настани за избраниот датум",
                        )
                    ),
                    _fbref_note(),
                    class_name="w-full",
                ),
            ),
        ),
        class_name="w-full",
    )
