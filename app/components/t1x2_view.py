import reflex as rx

from app.components.api_status import loading_skeleton, unavailable_note
from app.states.multi_source_state import (
    MultiMatch,
    MultiSourceState,
    MultiStatRow,
    SourceStatus,
)
from app.states.t1x2_client import T1x2Page, T1x2Snippet, T1x2Tipster
from app.states.t1x2_state import T1x2State


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
                "T1x2 · јавни извадоци",
                class_name="text-xl font-semibold tracking-tight text-white sm:text-2xl",
            ),
            rx.el.p(
                f"Само-читачки јавни страници без клуч · {T1x2State.reachable_count} од {T1x2State.page_count} достапни · вчитано во {T1x2State.fetched_at}",
                class_name="mt-1 max-w-3xl text-sm font-medium text-zinc-500",
            ),
            rx.el.p(
                T1x2State.attribution,
                class_name="mt-1 text-xs font-medium text-zinc-400",
            ),
            rx.el.p(
                T1x2State.extraction_note,
                class_name="mt-1 max-w-3xl text-xs font-medium text-zinc-600",
            ),
            class_name="flex min-w-0 flex-col",
        ),
        rx.el.div(
            _chip("Извадоци", T1x2State.total_count.to_string(), "file-text"),
            _chip("Со квоти", T1x2State.odds_count.to_string(), "coins"),
            _chip(
                "Со ознаки", T1x2State.marker_count.to_string(), "circle-check"
            ),
            _chip(
                "Tipster редови",
                T1x2State.tipster_count.to_string(),
                "users",
            ),
            rx.el.button(
                rx.icon(
                    "refresh-cw",
                    class_name=rx.cond(
                        T1x2State.is_loading,
                        "h-3.5 w-3.5 animate-spin",
                        "h-3.5 w-3.5",
                    ),
                ),
                rx.el.span("Освежи извори", class_name="whitespace-nowrap"),
                on_click=[
                    MultiSourceState.fetch_all_matches,
                    T1x2State.refresh,
                ],
                class_name="flex shrink-0 items-center gap-2 rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-semibold text-white transition-colors hover:bg-blue-500",
            ),
            class_name="flex flex-wrap items-center gap-2",
        ),
        class_name="mb-4 flex w-full flex-col gap-3 lg:flex-row lg:items-end lg:justify-between",
    )


def _multi_header() -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.el.h3(
                "Мулти-извор · реални редови",
                class_name="text-sm font-semibold tracking-tight text-white",
            ),
            rx.el.p(
                f"{MultiSourceState.selected_day_label} · {MultiSourceState.summary_label}",
                class_name="mt-0.5 max-w-3xl text-xs font-medium text-zinc-500",
            ),
            rx.el.p(
                "Само обични, само-читачки барања. Заштитата не се "
                "заобиколува, не се користи прелистувачка автоматизација и "
                "НИКОГАШ не се прикажува примерок или измислен натпревар.",
                class_name="mt-0.5 max-w-3xl text-[10px] font-medium text-zinc-600",
            ),
            class_name="flex min-w-0 flex-col",
        ),
        rx.el.div(
            _chip(
                "Редови",
                MultiSourceState.total_count.to_string(),
                "list-checks",
            ),
            _chip(
                "Со xG предвидување",
                MultiSourceState.prediction_count.to_string(),
                "brain",
            ),
            _chip(
                "Достапни извори",
                MultiSourceState.available_source_count.to_string(),
                "plug",
            ),
            rx.el.button(
                rx.icon(
                    "refresh-cw",
                    class_name=rx.cond(
                        MultiSourceState.is_loading,
                        "h-3.5 w-3.5 animate-spin",
                        "h-3.5 w-3.5",
                    ),
                ),
                rx.el.span("Вчитај извори", class_name="whitespace-nowrap"),
                on_click=MultiSourceState.fetch_all_matches,
                class_name="flex shrink-0 items-center gap-2 rounded-lg border border-zinc-800 bg-zinc-900/60 px-3 py-1.5 text-xs font-semibold text-zinc-300 transition-colors hover:border-zinc-700 hover:text-white",
            ),
            class_name="flex flex-wrap items-center gap-2",
        ),
        class_name="mb-3 flex w-full flex-col gap-3 lg:flex-row lg:items-end lg:justify-between",
    )


def _source_status_card(status: SourceStatus) -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.el.div(
                rx.el.span(
                    status["label"],
                    class_name="truncate text-sm font-semibold text-white",
                ),
                rx.el.span(
                    status["endpoint"],
                    class_name="mt-0.5 truncate text-[10px] font-medium text-zinc-600",
                ),
                class_name="flex min-w-0 flex-col",
            ),
            rx.el.span(
                status["status_label"],
                class_name=rx.match(
                    status["kind"],
                    (
                        "ok",
                        "w-fit shrink-0 whitespace-nowrap rounded-full border border-emerald-500/35 bg-emerald-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-emerald-300 tabular-nums",
                    ),
                    (
                        "limited",
                        "w-fit shrink-0 whitespace-nowrap rounded-full border border-amber-500/35 bg-amber-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-300 tabular-nums",
                    ),
                    (
                        "blocked",
                        "w-fit shrink-0 whitespace-nowrap rounded-full border border-red-500/35 bg-red-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-red-300 tabular-nums",
                    ),
                    "w-fit shrink-0 whitespace-nowrap rounded-full border border-zinc-700 bg-zinc-800/60 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-zinc-400 tabular-nums",
                ),
            ),
            class_name="flex items-start justify-between gap-2",
        ),
        rx.el.p(
            status["note"],
            class_name="mt-2 text-[11px] font-medium text-zinc-500",
        ),
        rx.el.div(
            rx.el.span(
                f"{status['rows']} реални редови",
                class_name="text-[10px] font-semibold text-zinc-400 tabular-nums",
            ),
            rx.el.span(
                rx.cond(status["available"], "употребливо", "без редови"),
                class_name="text-[10px] font-medium text-zinc-600",
            ),
            class_name="mt-2 flex items-center justify-between gap-2 border-t border-zinc-800 pt-2",
        ),
        class_name="w-full min-w-0 rounded-xl border border-zinc-800 bg-zinc-900/50 p-3.5",
    )


def _source_statuses() -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.icon("plug", class_name="h-4 w-4 text-blue-400"),
            rx.el.div(
                rx.el.h3(
                    "Состојба на изворите",
                    class_name="text-sm font-semibold tracking-tight text-white",
                ),
                rx.el.p(
                    "SofaScore · Flashscore/Rezultati · FBref",
                    class_name="text-xs font-medium text-zinc-500",
                ),
                class_name="flex min-w-0 flex-col",
            ),
            rx.el.span(
                rx.cond(
                    MultiSourceState.is_loading,
                    "Се чита...",
                    f"Ажурирано {MultiSourceState.fetched_at}",
                ),
                class_name="ml-auto shrink-0 whitespace-nowrap rounded-full border border-zinc-800 bg-zinc-950/60 px-2.5 py-1 text-[10px] font-semibold text-zinc-400 tabular-nums",
            ),
            class_name="flex items-center gap-3 border-b border-zinc-800 px-4 py-3",
        ),
        rx.cond(
            MultiSourceState.source_count > 0,
            rx.el.div(
                rx.foreach(
                    MultiSourceState.source_statuses, _source_status_card
                ),
                class_name="grid w-full grid-cols-1 gap-3 p-4 lg:grid-cols-3",
            ),
            rx.el.div(
                unavailable_note(
                    "Изворите сè уште не се прочитани во оваа сесија"
                ),
                class_name="p-4",
            ),
        ),
        class_name="w-full overflow-hidden rounded-xl border border-zinc-800 bg-zinc-900/50",
    )


def _multi_source_count(tab: dict[str, str]) -> rx.Component:
    """Неутрален чип со број реални редови по извор."""
    return rx.el.div(
        rx.el.span(tab["label"], class_name="whitespace-nowrap"),
        rx.el.span(
            tab["count"],
            class_name="rounded-full bg-zinc-800 px-1.5 text-[10px] font-bold text-zinc-400 tabular-nums",
        ),
        class_name="flex shrink-0 items-center gap-2 rounded-lg border border-zinc-800 bg-zinc-950/50 px-3 py-2 text-xs font-semibold text-zinc-400",
    )


def _multi_status_pill(row: MultiMatch) -> rx.Component:
    return rx.el.span(
        row["status_label"],
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
            (
                "postponed",
                "w-fit whitespace-nowrap rounded-full border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-300",
            ),
            "w-fit whitespace-nowrap rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-emerald-300 tabular-nums",
        ),
    )


def _multi_source_badge(row: MultiMatch) -> rx.Component:
    return rx.el.div(
        rx.icon("database", class_name="h-3 w-3"),
        rx.el.span(
            row["source_label"],
            class_name="text-[10px] font-bold uppercase tracking-wider",
        ),
        class_name=rx.match(
            row["source"],
            (
                "sofascore",
                "flex w-fit shrink-0 items-center gap-1.5 rounded-full border border-emerald-500/40 bg-emerald-500/10 px-2 py-0.5 text-emerald-300",
            ),
            (
                "rezultati",
                "flex w-fit shrink-0 items-center gap-1.5 rounded-full border border-amber-500/40 bg-amber-500/10 px-2 py-0.5 text-amber-300",
            ),
            "flex w-fit shrink-0 items-center gap-1.5 rounded-full border border-zinc-700 bg-zinc-800/60 px-2 py-0.5 text-zinc-300",
        ),
    )


def _multi_stat_row(stat: MultiStatRow) -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.el.span(
                stat["home"],
                class_name="w-14 text-xs font-semibold text-zinc-200 tabular-nums",
            ),
            rx.el.span(
                stat["label"],
                class_name="min-w-0 flex-1 truncate text-center text-[11px] font-medium text-zinc-500",
            ),
            rx.el.span(
                stat["away"],
                class_name="w-14 text-right text-xs font-semibold text-zinc-200 tabular-nums",
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


def _multi_prediction_block(row: MultiMatch) -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.el.span(
                "Предвидување (само од реален xG)",
                class_name="text-[10px] font-semibold uppercase tracking-wider text-zinc-500",
            ),
            rx.el.span(
                row["prediction_label"],
                class_name=rx.match(
                    row["prediction"],
                    (
                        "1",
                        "w-fit shrink-0 whitespace-nowrap rounded-lg border border-emerald-500/40 bg-emerald-500/10 px-2.5 py-0.5 text-xs font-bold text-emerald-300",
                    ),
                    (
                        "X",
                        "w-fit shrink-0 whitespace-nowrap rounded-lg border border-amber-500/40 bg-amber-500/10 px-2.5 py-0.5 text-xs font-bold text-amber-300",
                    ),
                    (
                        "2",
                        "w-fit shrink-0 whitespace-nowrap rounded-lg border border-red-500/40 bg-red-500/10 px-2.5 py-0.5 text-xs font-bold text-red-300",
                    ),
                    "w-fit shrink-0 whitespace-nowrap rounded-lg border border-zinc-700 bg-zinc-800/60 px-2.5 py-0.5 text-xs font-bold text-zinc-400",
                ),
            ),
            class_name="flex flex-wrap items-center justify-between gap-2",
        ),
        rx.cond(
            row["has_prediction"],
            rx.el.div(
                rx.el.div(
                    class_name="h-full rounded-full bg-blue-500 transition-all duration-700",
                    style={"width": f"{row['confidence']}%"},
                ),
                class_name="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-zinc-800",
            ),
            rx.fragment(),
        ),
        rx.el.div(
            rx.el.span(
                row["prediction_reason"],
                class_name="min-w-0 flex-1 truncate text-[10px] font-medium text-zinc-600",
            ),
            rx.cond(
                row["has_prediction"],
                rx.el.span(
                    f"{row['confidence']:.1f}%",
                    class_name="shrink-0 text-[11px] font-semibold text-blue-300 tabular-nums",
                ),
                rx.fragment(),
            ),
            class_name="mt-1.5 flex items-center justify-between gap-2",
        ),
        class_name=rx.cond(
            row["has_prediction"],
            "mt-2.5 w-full min-w-0 rounded-lg border border-blue-500/25 bg-blue-500/[0.05] px-3 py-2.5",
            "mt-2.5 w-full min-w-0 rounded-lg border border-dashed border-zinc-800 bg-zinc-950/40 px-3 py-2.5",
        ),
    )


def _multi_xg_block(row: MultiMatch) -> rx.Component:
    """Реален xG од изворот; сосема се скрива кога не е објавен."""
    return rx.cond(
        (row["home_xg"] > 0.0) | (row["away_xg"] > 0.0),
        rx.el.div(
            rx.el.span(
                f"{row['home_xg']:.2f}",
                class_name="text-[11px] font-semibold text-zinc-200 tabular-nums",
            ),
            rx.el.span(
                "xG",
                class_name="text-[10px] font-medium uppercase tracking-wider text-zinc-600",
            ),
            rx.el.span(
                f"{row['away_xg']:.2f}",
                class_name="text-[11px] font-semibold text-zinc-200 tabular-nums",
            ),
            class_name="mt-2 flex items-center justify-between gap-2 rounded-lg border border-zinc-800 bg-zinc-950/60 px-2.5 py-1.5",
        ),
        rx.fragment(),
    )


def _multi_form_block(row: MultiMatch) -> rx.Component:
    return rx.cond(
        row["has_form"],
        rx.el.div(
            rx.el.span(
                rx.cond(row["form_home"] != "", row["form_home"], "–"),
                class_name="text-[11px] font-semibold tracking-[0.18em] text-zinc-400",
            ),
            rx.el.span(
                "форма",
                class_name="text-[10px] font-medium uppercase tracking-wider text-zinc-600",
            ),
            rx.el.span(
                rx.cond(row["form_away"] != "", row["form_away"], "–"),
                class_name="text-[11px] font-semibold tracking-[0.18em] text-zinc-400",
            ),
            class_name="mt-2 flex items-center justify-between gap-2 rounded-lg border border-zinc-800 bg-zinc-950/60 px-2.5 py-1.5",
        ),
        rx.fragment(),
    )


def _multi_match_card(row: MultiMatch) -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.el.div(
                rx.el.span(
                    row["league"],
                    class_name="truncate text-[11px] font-semibold uppercase tracking-wider text-zinc-500",
                ),
                _multi_status_pill(row),
                _multi_source_badge(row),
                class_name="flex flex-wrap items-center gap-2",
            ),
            rx.el.div(
                rx.el.p(
                    row["home_team"],
                    class_name="min-w-0 flex-1 truncate text-sm font-semibold text-white",
                ),
                rx.el.span(
                    row["score"],
                    class_name="shrink-0 rounded-lg border border-zinc-800 bg-zinc-950/70 px-2.5 py-1 text-sm font-semibold text-zinc-200 tabular-nums",
                ),
                rx.el.p(
                    row["away_team"],
                    class_name="min-w-0 flex-1 truncate text-right text-sm font-semibold text-white",
                ),
                class_name="mt-2 flex items-center gap-3",
            ),
            rx.el.div(
                rx.el.span(
                    f"{row['day_key']} · {row['time']}",
                    class_name="truncate text-[11px] font-medium text-zinc-600 tabular-nums",
                ),
                rx.cond(
                    row["detail_url"] != "",
                    rx.el.a(
                        rx.icon("external-link", class_name="h-3 w-3"),
                        rx.el.span("извор"),
                        href=row["detail_url"],
                        target="_blank",
                        rel="noopener noreferrer",
                        class_name="flex w-fit shrink-0 items-center gap-1.5 text-[10px] font-semibold text-zinc-500 transition-colors hover:text-blue-300",
                    ),
                    rx.fragment(),
                ),
                class_name="mt-1.5 flex items-center justify-between gap-2",
            ),
            class_name="min-w-0 border-b border-zinc-800 px-4 py-3.5",
        ),
        rx.el.div(
            _multi_prediction_block(row),
            _multi_xg_block(row),
            _multi_form_block(row),
            rx.cond(
                row["has_stats"],
                rx.el.div(
                    rx.el.span(
                        "Реални статистики од изворот",
                        class_name="text-[10px] font-semibold uppercase tracking-wider text-zinc-500",
                    ),
                    rx.el.div(
                        rx.foreach(row["stat_rows"], _multi_stat_row),
                        class_name="mt-2 flex flex-col gap-2",
                    ),
                    class_name="mt-2.5 w-full min-w-0 rounded-lg border border-zinc-800 bg-zinc-950/50 px-3 py-2.5",
                ),
                rx.el.div(
                    unavailable_note(
                        "Изворот не објавува поседување, удари, xG, корнери "
                        "ниту картони за овој натпревар"
                    ),
                    class_name="mt-2.5 w-full",
                ),
            ),
            class_name="p-3.5",
        ),
        class_name="w-full min-w-0 rounded-xl border border-zinc-800 bg-zinc-900/50 transition-colors hover:border-zinc-700",
    )


def _multi_source_section() -> rx.Component:
    return rx.el.div(
        _multi_header(),
        _source_statuses(),
        rx.cond(
            MultiSourceState.is_loading
            & (MultiSourceState.matches.length() == 0),
            loading_skeleton(),
            rx.cond(
                MultiSourceState.matches.length() > 0,
                rx.el.div(
                    rx.el.div(
                        rx.foreach(
                            MultiSourceState.source_row_counts,
                            _multi_source_count,
                        ),
                        class_name="flex w-full items-center gap-1 overflow-x-auto rounded-xl border border-zinc-800 bg-zinc-900/40 p-1",
                    ),
                    rx.el.div(
                        rx.foreach(
                            MultiSourceState.matches,
                            _multi_match_card,
                        ),
                        class_name="mt-3 grid w-full grid-cols-1 gap-3 lg:grid-cols-2 2xl:grid-cols-3",
                    ),
                    rx.el.p(
                        MultiSourceState.source_note,
                        class_name="mt-3 text-[10px] font-medium text-zinc-600",
                    ),
                    class_name="mt-4 w-full",
                ),
                rx.el.div(
                    rx.el.div(
                        rx.icon(
                            "calendar-off", class_name="h-6 w-6 text-zinc-600"
                        ),
                        rx.el.p(
                            MultiSourceState.empty_label,
                            class_name="mt-2 max-w-2xl text-center text-sm font-medium text-zinc-500",
                        ),
                        class_name="flex w-full flex-col items-center justify-center rounded-xl border border-zinc-800 bg-zinc-900/40 px-4 py-14",
                    ),
                    rx.el.div(
                        unavailable_note(MultiSourceState.source_note),
                        class_name="mt-3 w-full",
                    ),
                    class_name="mt-4 w-full",
                ),
            ),
        ),
        class_name="w-full",
    )


def _category_tab(tab: dict[str, str]) -> rx.Component:
    return rx.el.button(
        rx.el.span(tab["label"], class_name="whitespace-nowrap"),
        rx.el.span(
            tab["count"],
            class_name=rx.cond(
                T1x2State.category_filter == tab["key"],
                "rounded-full bg-blue-500/20 px-1.5 text-[10px] font-bold text-blue-200 tabular-nums",
                "rounded-full bg-zinc-800 px-1.5 text-[10px] font-bold text-zinc-400 tabular-nums",
            ),
        ),
        on_click=lambda: T1x2State.set_category_filter(tab["key"]),
        class_name=rx.cond(
            T1x2State.category_filter == tab["key"],
            "flex flex-1 items-center justify-center gap-2 rounded-lg border border-blue-500/40 bg-blue-500/10 px-3 py-2 text-xs font-semibold text-blue-300 transition-all sm:text-sm",
            "flex flex-1 items-center justify-center gap-2 rounded-lg border border-transparent px-3 py-2 text-xs font-semibold text-zinc-500 transition-all hover:bg-zinc-900 hover:text-zinc-200 sm:text-sm",
        ),
    )


def _category_badge(row: T1x2Snippet) -> rx.Component:
    return rx.el.span(
        row["category"],
        class_name=rx.match(
            row["category_key"],
            (
                "tip",
                "w-fit whitespace-nowrap rounded-full border border-blue-500/40 bg-blue-500/10 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-blue-300",
            ),
            (
                "tiket",
                "w-fit whitespace-nowrap rounded-full border border-amber-500/40 bg-amber-500/10 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-amber-300",
            ),
            (
                "stat",
                "w-fit whitespace-nowrap rounded-full border border-emerald-500/35 bg-emerald-500/10 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-emerald-300",
            ),
            "w-fit whitespace-nowrap rounded-full border border-zinc-700 bg-zinc-800/60 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-zinc-400",
        ),
    )


def _odd_chip(value: rx.Var) -> rx.Component:
    return rx.el.span(
        value,
        class_name="w-fit whitespace-nowrap rounded-lg border border-zinc-800 bg-zinc-950/60 px-2 py-0.5 text-[11px] font-semibold text-emerald-300 tabular-nums",
    )


def _triple_block(row: T1x2Snippet) -> rx.Component:
    """Прикажува натпревар + избор + квота САМО кога тројката е парсирана."""
    return rx.cond(
        row["has_triple"],
        rx.el.div(
            rx.el.div(
                rx.el.span(
                    "Парсирана тројка · натпревар / избор / квота",
                    class_name="text-[10px] font-semibold uppercase tracking-wider text-zinc-500",
                ),
                rx.el.span(
                    f"{row['top_odd']:.2f}",
                    class_name="shrink-0 text-xs font-semibold text-emerald-300 tabular-nums",
                ),
                class_name="flex items-center justify-between gap-2",
            ),
            rx.el.p(
                row["match_label"],
                class_name="mt-0.5 truncate text-sm font-semibold text-white",
            ),
            rx.el.p(
                row["pick"],
                class_name="truncate text-[11px] font-medium text-blue-300",
            ),
            class_name="mt-2 w-full min-w-0 rounded-lg border border-blue-500/25 bg-blue-500/[0.05] px-2.5 py-2",
        ),
        rx.fragment(),
    )


def _snippet_card(row: T1x2Snippet) -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.el.div(
                _category_badge(row),
                rx.cond(
                    row["has_markers"],
                    rx.el.span(
                        row["marker_label"],
                        class_name="w-fit whitespace-nowrap rounded-full border border-zinc-700 bg-zinc-800/60 px-2 py-0.5 text-[10px] font-semibold text-zinc-300 tabular-nums",
                    ),
                    rx.fragment(),
                ),
                rx.cond(
                    row["has_odds"],
                    rx.el.span(
                        f"{row['odds_count']} квоти",
                        class_name="w-fit whitespace-nowrap rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-[10px] font-semibold text-emerald-300 tabular-nums",
                    ),
                    rx.el.span(
                        "без квоти",
                        class_name="w-fit whitespace-nowrap rounded-full border border-zinc-700 bg-zinc-800/60 px-2 py-0.5 text-[10px] font-semibold text-zinc-500",
                    ),
                ),
                class_name="flex flex-wrap items-center gap-2",
            ),
            rx.el.p(
                row["title"],
                class_name="mt-2 line-clamp-2 text-sm font-semibold text-white",
            ),
            class_name="min-w-0 border-b border-zinc-800 px-3.5 py-3",
        ),
        rx.el.div(
            rx.el.p(
                row["excerpt"],
                class_name="line-clamp-4 text-[11px] font-medium text-zinc-400",
            ),
            rx.cond(
                row["has_odds"],
                rx.el.div(
                    rx.foreach(row["odds"], _odd_chip),
                    class_name="mt-2 flex flex-wrap items-center gap-1.5",
                ),
                rx.fragment(),
            ),
            _triple_block(row),
            rx.el.a(
                rx.icon("external-link", class_name="h-3 w-3"),
                rx.el.span(row["url"], class_name="truncate"),
                href=row["url"],
                target="_blank",
                rel="noopener noreferrer",
                class_name="mt-2 flex w-full min-w-0 items-center gap-1.5 text-[10px] font-semibold text-zinc-500 transition-colors hover:text-blue-300",
            ),
            rx.el.p(
                row["note"],
                class_name="mt-1 text-[10px] font-medium text-zinc-600",
            ),
            class_name="p-3.5",
        ),
        class_name="w-full min-w-0 rounded-xl border border-zinc-800 bg-zinc-900/50 transition-colors hover:border-zinc-700",
    )


def _capability_row(label: rx.Var) -> rx.Component:
    return rx.el.div(
        rx.icon("check", class_name="mt-0.5 h-3 w-3 shrink-0 text-emerald-400"),
        rx.el.span(
            label,
            class_name="min-w-0 text-[11px] font-medium text-zinc-400",
        ),
        class_name="flex items-start gap-2",
    )


def _capabilities_card() -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.icon("list-checks", class_name="h-4 w-4 text-blue-400"),
            rx.el.div(
                rx.el.h3(
                    "Што може да се извлече",
                    class_name="text-sm font-semibold tracking-tight text-white",
                ),
                rx.el.p(
                    "Само јавни страници, без најава",
                    class_name="text-xs font-medium text-zinc-500",
                ),
                class_name="flex min-w-0 flex-col",
            ),
            class_name="flex items-center gap-3 border-b border-zinc-800 px-4 py-3",
        ),
        rx.cond(
            T1x2State.capabilities.length() > 0,
            rx.el.div(
                rx.foreach(T1x2State.capabilities, _capability_row),
                class_name="flex flex-col gap-2 px-4 py-3",
            ),
            rx.el.div(
                unavailable_note(
                    "Ниту една јавна страница не врати читлив извадок"
                ),
                class_name="p-4",
            ),
        ),
        class_name="w-full rounded-xl border border-zinc-800 bg-zinc-900/50",
    )


def _page_row(page: T1x2Page) -> rx.Component:
    return rx.el.tr(
        rx.el.td(
            rx.el.div(
                rx.el.span(
                    page["category"],
                    class_name="truncate text-xs font-semibold text-zinc-100",
                ),
                rx.el.span(
                    page["url"],
                    class_name="truncate text-[10px] font-medium text-zinc-600",
                ),
                class_name="flex min-w-0 flex-col",
            ),
            class_name="px-3 py-2",
        ),
        rx.el.td(
            rx.el.span(
                page["status_label"],
                class_name=rx.cond(
                    page["ok"],
                    "w-fit whitespace-nowrap rounded-full border border-emerald-500/35 bg-emerald-500/10 px-2 py-0.5 text-[10px] font-semibold text-emerald-300 tabular-nums",
                    "w-fit whitespace-nowrap rounded-full border border-red-500/30 bg-red-500/10 px-2 py-0.5 text-[10px] font-semibold text-red-300 tabular-nums",
                ),
            ),
            class_name="px-3 py-2",
        ),
        rx.el.td(
            page["snippet_count"],
            class_name="px-3 py-2 text-right text-xs text-zinc-300 tabular-nums",
        ),
        rx.el.td(
            page["odds_count"],
            class_name="hidden px-3 py-2 text-right text-xs text-zinc-400 tabular-nums sm:table-cell",
        ),
        rx.el.td(
            page["marker_count"],
            class_name="hidden px-3 py-2 text-right text-xs text-zinc-400 tabular-nums md:table-cell",
        ),
        class_name="border-b border-zinc-800/70 transition-colors last:border-0 hover:bg-zinc-800/30",
    )


def _pages_card() -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.icon("globe", class_name="h-4 w-4 text-blue-400"),
            rx.el.div(
                rx.el.h3(
                    "Прочитани јавни страници",
                    class_name="text-sm font-semibold tracking-tight text-white",
                ),
                rx.el.p(
                    "URL · статус · извадоци · квоти · ознаки",
                    class_name="text-xs font-medium text-zinc-500",
                ),
                class_name="flex min-w-0 flex-col",
            ),
            class_name="flex items-center gap-3 border-b border-zinc-800 px-4 py-3",
        ),
        rx.cond(
            T1x2State.pages.length() > 0,
            rx.el.div(
                rx.el.div(
                    rx.el.table(
                        rx.el.thead(
                            rx.el.tr(
                                rx.el.th(
                                    "Страница",
                                    class_name="px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-wider text-zinc-500",
                                ),
                                rx.el.th(
                                    "Статус",
                                    class_name="px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-wider text-zinc-500",
                                ),
                                rx.el.th(
                                    "Извадоци",
                                    class_name="px-3 py-2 text-right text-[11px] font-semibold uppercase tracking-wider text-zinc-500",
                                ),
                                rx.el.th(
                                    "Квоти",
                                    class_name="hidden px-3 py-2 text-right text-[11px] font-semibold uppercase tracking-wider text-zinc-500 sm:table-cell",
                                ),
                                rx.el.th(
                                    "Ознаки",
                                    class_name="hidden px-3 py-2 text-right text-[11px] font-semibold uppercase tracking-wider text-zinc-500 md:table-cell",
                                ),
                            ),
                            class_name="border-b border-zinc-800 bg-zinc-950/40",
                        ),
                        rx.el.tbody(rx.foreach(T1x2State.pages, _page_row)),
                        class_name="w-full table-auto",
                    ),
                    class_name="w-full overflow-x-auto",
                ),
                class_name="p-4",
            ),
            rx.el.div(
                unavailable_note("Сè уште не е прочитана ниту една страница"),
                class_name="p-4",
            ),
        ),
        class_name="w-full overflow-hidden rounded-xl border border-zinc-800 bg-zinc-900/50",
    )


def _tipster_row(row: T1x2Tipster) -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.el.span(
                row["name"],
                class_name="truncate text-xs font-semibold text-white",
            ),
            rx.el.span(
                row["accuracy"],
                class_name="shrink-0 text-xs font-semibold text-blue-300 tabular-nums",
            ),
            class_name="flex items-center justify-between gap-3",
        ),
        rx.el.div(
            rx.el.span(
                f"биланс {row['record']}",
                class_name="truncate text-[10px] font-medium text-zinc-500 tabular-nums",
            ),
            rx.el.span(
                f"ROI {row['roi']} · {row['profit']}",
                class_name="truncate text-[10px] font-medium text-zinc-500 tabular-nums",
            ),
            class_name="mt-1 flex items-center justify-between gap-3",
        ),
        class_name="w-full min-w-0 border-b border-zinc-800/70 py-2.5 last:border-0",
    )


def _tipsters_card() -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.icon("users", class_name="h-4 w-4 text-amber-400"),
            rx.el.div(
                rx.el.h3(
                    "Јавни tipster метрики",
                    class_name="text-sm font-semibold tracking-tight text-white",
                ),
                rx.el.p(
                    "Точно како што ги објавува јавната табела",
                    class_name="text-xs font-medium text-zinc-500",
                ),
                class_name="flex min-w-0 flex-col",
            ),
            class_name="flex items-center gap-3 border-b border-zinc-800 px-4 py-3",
        ),
        rx.cond(
            T1x2State.tipsters.length() > 0,
            rx.el.div(
                rx.foreach(T1x2State.tipsters, _tipster_row),
                class_name="flex flex-col px-4 py-2",
            ),
            rx.el.div(
                unavailable_note(
                    "Јавната табела не објавува tipster метрики во моментот"
                ),
                class_name="p-4",
            ),
        ),
        class_name="w-full rounded-xl border border-zinc-800 bg-zinc-900/50",
    )


def _snippets_section_header() -> rx.Component:
    return rx.el.div(
        rx.icon("file-text", class_name="h-4 w-4 text-blue-400"),
        rx.el.div(
            rx.el.h3(
                "Јавни извадоци · t1x2.net",
                class_name="text-sm font-semibold tracking-tight text-white",
            ),
            rx.el.p(
                "Само-читачки јавни страници · не се предвидувања на моделите",
                class_name="text-xs font-medium text-zinc-500",
            ),
            class_name="flex min-w-0 flex-col",
        ),
        class_name="mb-3 flex items-center gap-3 rounded-xl border border-zinc-800 bg-zinc-900/40 px-4 py-3",
    )


def _public_snippets_section() -> rx.Component:
    return rx.el.div(
        _snippets_section_header(),
        rx.cond(
            T1x2State.is_loading & ~T1x2State.has_data,
            loading_skeleton(),
            rx.cond(
                T1x2State.has_data,
                rx.el.div(
                    rx.el.div(
                        rx.foreach(T1x2State.category_tabs, _category_tab),
                        class_name="flex w-full items-center gap-1 overflow-x-auto rounded-xl border border-zinc-800 bg-zinc-900/40 p-1",
                    ),
                    rx.cond(
                        T1x2State.visible_count > 0,
                        rx.el.div(
                            rx.foreach(
                                T1x2State.visible_snippets, _snippet_card
                            ),
                            class_name="mt-4 grid w-full grid-cols-1 gap-3 lg:grid-cols-2 2xl:grid-cols-3",
                        ),
                        rx.el.div(
                            rx.icon(
                                "filter-x", class_name="h-6 w-6 text-zinc-600"
                            ),
                            rx.el.p(
                                "Нема јавни извадоци за избраната категорија",
                                class_name="mt-2 text-sm font-medium text-zinc-500",
                            ),
                            class_name="mt-4 flex w-full flex-col items-center justify-center rounded-xl border border-zinc-800 bg-zinc-900/40 py-14",
                        ),
                    ),
                    rx.el.div(
                        rx.el.div(_pages_card(), class_name="min-w-0 flex-1"),
                        rx.el.div(
                            _capabilities_card(),
                            class_name="w-full lg:w-80 lg:shrink-0",
                        ),
                        class_name="mt-4 flex w-full flex-col gap-4 lg:flex-row",
                    ),
                    rx.el.div(_tipsters_card(), class_name="mt-4 w-full"),
                    class_name="w-full",
                ),
                rx.el.div(
                    unavailable_note(T1x2State.empty_label),
                    rx.el.div(_pages_card(), class_name="mt-4 w-full"),
                    class_name="w-full",
                ),
            ),
        ),
        class_name="w-full",
    )


def t1x2_view() -> rx.Component:
    return rx.el.div(
        _header(),
        _multi_source_section(),
        rx.el.div(
            _public_snippets_section(),
            class_name="mt-6 w-full border-t border-zinc-800/70 pt-5",
        ),
        class_name="w-full",
    )
