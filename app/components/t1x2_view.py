import reflex as rx

from app.components.api_status import loading_skeleton, unavailable_note
from app.states.football_data_client import FDStat, FDStatus, FootballDataRow
from app.states.sportscore_client import SportScoreRow, SportScoreStat
from app.states.sportscore_state import SportScoreState
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
                "T1x2 · предвидувања",
                class_name="text-xl font-semibold tracking-tight text-white sm:text-2xl",
            ),
            rx.el.p(
                f"football-data.co.uk CSV + SportScore · {T1x2State.summary_label} · вчитано во {T1x2State.fetched_at}",
                class_name="mt-1 max-w-3xl text-sm font-medium text-zinc-500",
            ),
            rx.el.p(
                T1x2State.attribution,
                class_name="mt-1 text-xs font-medium text-zinc-400",
            ),
            rx.el.p(
                T1x2State.no_xg_note,
                class_name="mt-1 max-w-3xl text-xs font-medium text-zinc-600",
            ),
            class_name="flex min-w-0 flex-col",
        ),
        rx.el.div(
            _chip("Редови", T1x2State.total_count.to_string(), "list-checks"),
            _chip(
                "Со предвидување",
                T1x2State.prediction_count.to_string(),
                "brain",
            ),
            _chip("Со квоти", T1x2State.odds_count.to_string(), "coins"),
            _chip(
                "Успешност",
                f"{T1x2State.accuracy_rate:.1f}%",
                "gauge",
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
                on_click=T1x2State.refresh_all,
                class_name="flex shrink-0 items-center gap-2 rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-semibold text-white transition-colors hover:bg-blue-500",
            ),
            class_name="flex flex-wrap items-center gap-2",
        ),
        class_name="mb-4 flex w-full flex-col gap-3 lg:flex-row lg:items-end lg:justify-between",
    )


def _fd_status_card(status: FDStatus) -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.el.div(
                rx.el.span(
                    status["label"],
                    class_name="truncate text-sm font-semibold text-white",
                ),
                rx.el.span(
                    f"{status['season_label']} · {status['url']}",
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
                    "w-fit shrink-0 whitespace-nowrap rounded-full border border-red-500/35 bg-red-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-red-300 tabular-nums",
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
                f"{status['rows']} реални CSV редови",
                class_name="text-[10px] font-semibold text-zinc-400 tabular-nums",
            ),
            rx.el.span(
                f"{status['used_rows']} прикажани",
                class_name="text-[10px] font-medium text-zinc-600 tabular-nums",
            ),
            class_name="mt-2 flex items-center justify-between gap-2 border-t border-zinc-800 pt-2",
        ),
        class_name="w-full min-w-0 rounded-xl border border-zinc-800 bg-zinc-900/50 p-3.5",
    )


def _sportscore_status_card() -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.el.div(
                rx.el.span(
                    "SportScore · widget API",
                    class_name="truncate text-sm font-semibold text-white",
                ),
                rx.el.span(
                    "sportscore.com/api/widget/matches/ · без клуч",
                    class_name="mt-0.5 truncate text-[10px] font-medium text-zinc-600",
                ),
                class_name="flex min-w-0 flex-col",
            ),
            rx.el.span(
                rx.cond(
                    SportScoreState.has_data,
                    "200 · достапно",
                    "недостапно",
                ),
                class_name=rx.cond(
                    SportScoreState.has_data,
                    "w-fit shrink-0 whitespace-nowrap rounded-full border border-emerald-500/35 bg-emerald-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-emerald-300 tabular-nums",
                    "w-fit shrink-0 whitespace-nowrap rounded-full border border-amber-500/35 bg-amber-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-300 tabular-nums",
                ),
            ),
            class_name="flex items-start justify-between gap-2",
        ),
        rx.el.p(
            "Реални настани, статистики и минута од јавниот widget API. "
            "Препорака се пресметува САМО кога постојат реални статистики; xG "
            "не се измислува.",
            class_name="mt-2 text-[11px] font-medium text-zinc-500",
        ),
        rx.el.div(
            rx.el.span(
                f"{SportScoreState.total_count} реални настани · {SportScoreState.stats_count} со статистики",
                class_name="text-[10px] font-semibold text-zinc-400 tabular-nums",
            ),
            rx.el.span(
                f"{SportScoreState.prediction_count} со препорака",
                class_name="text-[10px] font-medium text-zinc-600 tabular-nums",
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
                    "football-data.co.uk CSV фајлови по лига · SportScore widget API",
                    class_name="text-xs font-medium text-zinc-500",
                ),
                class_name="flex min-w-0 flex-col",
            ),
            rx.el.span(
                rx.cond(
                    T1x2State.is_loading,
                    "Се чита...",
                    f"Ажурирано {T1x2State.fetched_at}",
                ),
                class_name="ml-auto shrink-0 whitespace-nowrap rounded-full border border-zinc-800 bg-zinc-950/60 px-2.5 py-1 text-[10px] font-semibold text-zinc-400 tabular-nums",
            ),
            class_name="flex items-center gap-3 border-b border-zinc-800 px-4 py-3",
        ),
        rx.cond(
            T1x2State.source_count > 0,
            rx.el.div(
                rx.foreach(T1x2State.statuses, _fd_status_card),
                _sportscore_status_card(),
                class_name="grid w-full grid-cols-1 gap-3 p-4 lg:grid-cols-2 2xl:grid-cols-3",
            ),
            rx.el.div(
                unavailable_note(
                    "CSV фајловите сè уште не се прочитани во оваа сесија"
                ),
                _sportscore_status_card(),
                class_name="flex flex-col gap-3 p-4",
            ),
        ),
        class_name="w-full overflow-hidden rounded-xl border border-zinc-800 bg-zinc-900/50",
    )


def _league_tab(tab: dict[str, str]) -> rx.Component:
    return rx.el.button(
        rx.el.span(tab["label"], class_name="whitespace-nowrap"),
        rx.el.span(
            tab["count"],
            class_name=rx.cond(
                T1x2State.league_filter == tab["key"],
                "rounded-full bg-blue-500/20 px-1.5 text-[10px] font-bold text-blue-200 tabular-nums",
                "rounded-full bg-zinc-800 px-1.5 text-[10px] font-bold text-zinc-400 tabular-nums",
            ),
        ),
        on_click=lambda: T1x2State.set_league_filter(tab["key"]),
        class_name=rx.cond(
            T1x2State.league_filter == tab["key"],
            "flex shrink-0 items-center justify-center gap-2 rounded-lg border border-blue-500/40 bg-blue-500/10 px-3 py-2 text-xs font-semibold text-blue-300 transition-all sm:text-sm",
            "flex shrink-0 items-center justify-center gap-2 rounded-lg border border-transparent px-3 py-2 text-xs font-semibold text-zinc-500 transition-all hover:bg-zinc-900 hover:text-zinc-200 sm:text-sm",
        ),
    )


def _prob_bar(
    label: rx.Var | str, value: rx.Var, bar_class: str
) -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.el.span(
                label, class_name="truncate text-xs font-medium text-zinc-300"
            ),
            rx.el.span(
                f"{value:.1f}%",
                class_name="shrink-0 text-xs font-semibold text-white tabular-nums",
            ),
            class_name="flex items-center justify-between gap-3",
        ),
        rx.el.div(
            rx.el.div(class_name=bar_class, style={"width": f"{value}%"}),
            class_name="mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-zinc-800",
        ),
        class_name="w-full min-w-0",
    )


def _fd_stat_row(stat: FDStat) -> rx.Component:
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


def _fd_verdict(row: FootballDataRow) -> rx.Component:
    return rx.cond(
        row["settled"],
        rx.el.div(
            rx.el.span(
                f"Реален исход · {row['actual_label']}",
                class_name="truncate text-[10px] font-medium text-zinc-500",
            ),
            rx.el.span(
                rx.cond(row["is_correct"], "Точно", "Погрешно"),
                class_name=rx.cond(
                    row["is_correct"],
                    "w-fit shrink-0 whitespace-nowrap rounded-full border border-emerald-500/35 bg-emerald-500/10 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-emerald-300",
                    "w-fit shrink-0 whitespace-nowrap rounded-full border border-red-500/35 bg-red-500/10 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-red-300",
                ),
            ),
            class_name="mt-2 flex items-center justify-between gap-2 rounded-lg border border-zinc-800 bg-zinc-950/60 px-2.5 py-1.5",
        ),
        rx.fragment(),
    )


def _fd_prediction_block(row: FootballDataRow) -> rx.Component:
    return rx.cond(
        row["has_prediction"],
        rx.el.div(
            rx.el.div(
                rx.el.span(
                    row["market"],
                    class_name="truncate text-[10px] font-semibold uppercase tracking-wider text-amber-300/80",
                ),
                rx.el.span(
                    f"{row['confidence']:.1f}%",
                    class_name="shrink-0 text-sm font-semibold text-amber-300 tabular-nums",
                ),
                class_name="flex flex-wrap items-center justify-between gap-2",
            ),
            rx.el.p(
                row["pick"],
                class_name="mt-1 truncate text-sm font-semibold text-white",
            ),
            rx.el.div(
                _prob_bar(
                    f"1 · {row['home']}",
                    row["prob_home"],
                    "h-full rounded-full bg-blue-500 transition-all duration-700",
                ),
                _prob_bar(
                    "X · Реми",
                    row["prob_draw"],
                    "h-full rounded-full bg-zinc-500 transition-all duration-700",
                ),
                _prob_bar(
                    f"2 · {row['away']}",
                    row["prob_away"],
                    "h-full rounded-full bg-blue-400/70 transition-all duration-700",
                ),
                class_name="mt-2.5 flex flex-col gap-2",
            ),
            rx.el.p(
                row["basis_label"],
                class_name="mt-2 text-[10px] font-medium text-zinc-600",
            ),
            rx.el.p(
                row["history_label"],
                class_name="text-[10px] font-medium text-zinc-700",
            ),
            _fd_verdict(row),
            class_name="w-full min-w-0 rounded-lg border border-amber-500/25 bg-amber-500/[0.04] px-3 py-2.5",
        ),
        rx.el.div(
            unavailable_note(row["prediction_note"]), class_name="w-full"
        ),
    )


def _fd_odds_block(row: FootballDataRow) -> rx.Component:
    return rx.cond(
        row["has_odds"],
        rx.el.div(
            rx.el.span(
                f"Квоти · {row['odds_label']}",
                class_name="truncate text-[10px] font-semibold uppercase tracking-wider text-zinc-500",
            ),
            rx.el.span(
                f"{row['odd_home']:.2f} · {row['odd_draw']:.2f} · {row['odd_away']:.2f}",
                class_name="whitespace-nowrap text-xs font-semibold text-emerald-300 tabular-nums",
            ),
            class_name="mt-2 flex items-center justify-between gap-2 rounded-lg border border-zinc-800 bg-zinc-950/60 px-2.5 py-1.5",
        ),
        rx.el.div(
            rx.el.span(
                "Квоти",
                class_name="text-[10px] font-semibold uppercase tracking-wider text-zinc-500",
            ),
            rx.el.span(
                "недостапно во CSV редот",
                class_name="text-[10px] font-medium text-zinc-600",
            ),
            class_name="mt-2 flex items-center justify-between gap-2 rounded-lg border border-dashed border-zinc-800 bg-zinc-950/40 px-2.5 py-1.5",
        ),
    )


def _fd_card(row: FootballDataRow) -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.el.div(
                rx.el.span(
                    row["league"],
                    class_name="truncate text-[11px] font-semibold uppercase tracking-wider text-zinc-500",
                ),
                rx.el.span(
                    row["season_label"],
                    class_name="w-fit whitespace-nowrap rounded-full border border-zinc-700 bg-zinc-800/60 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-zinc-400 tabular-nums",
                ),
                rx.el.span(
                    "football-data.co.uk",
                    class_name="w-fit whitespace-nowrap rounded-full border border-emerald-500/40 bg-emerald-500/10 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-emerald-300",
                ),
                rx.cond(
                    row["has_ft"],
                    rx.el.span(
                        "Одигран",
                        class_name="w-fit whitespace-nowrap rounded-full border border-zinc-700 bg-zinc-800/60 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-zinc-400",
                    ),
                    rx.el.span(
                        "Без FT резултат",
                        class_name="w-fit whitespace-nowrap rounded-full border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-300",
                    ),
                ),
                class_name="flex flex-wrap items-center gap-2",
            ),
            rx.el.div(
                rx.el.p(
                    row["home"],
                    class_name="min-w-0 flex-1 truncate text-sm font-semibold text-white",
                ),
                rx.el.span(
                    row["ft_score"],
                    class_name="shrink-0 rounded-lg border border-zinc-800 bg-zinc-950/70 px-2.5 py-1 text-sm font-semibold text-zinc-200 tabular-nums",
                ),
                rx.el.p(
                    row["away"],
                    class_name="min-w-0 flex-1 truncate text-right text-sm font-semibold text-white",
                ),
                class_name="mt-2 flex items-center gap-3",
            ),
            rx.el.div(
                rx.el.span(
                    f"{row['date_label']} · {row['kickoff']}",
                    class_name="truncate text-[11px] font-medium text-zinc-600 tabular-nums",
                ),
                rx.cond(
                    row["has_ht"],
                    rx.el.span(
                        row["ht_score"],
                        class_name="w-fit shrink-0 whitespace-nowrap rounded-full border border-zinc-700 bg-zinc-800/60 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-zinc-300 tabular-nums",
                    ),
                    rx.el.span(
                        "HT: недостапно",
                        class_name="shrink-0 whitespace-nowrap text-[10px] font-medium text-zinc-600",
                    ),
                ),
                class_name="mt-1.5 flex items-center justify-between gap-2",
            ),
            class_name="min-w-0 border-b border-zinc-800 px-4 py-3.5",
        ),
        rx.el.div(
            _fd_prediction_block(row),
            _fd_odds_block(row),
            rx.cond(
                row["has_stats"],
                rx.el.div(
                    rx.el.span(
                        "Реални статистики од CSV редот",
                        class_name="text-[10px] font-semibold uppercase tracking-wider text-zinc-500",
                    ),
                    rx.el.div(
                        rx.foreach(row["stats"], _fd_stat_row),
                        class_name="mt-2 flex flex-col gap-2",
                    ),
                    class_name="mt-2.5 w-full min-w-0 rounded-lg border border-zinc-800 bg-zinc-950/50 px-3 py-2.5",
                ),
                rx.el.div(
                    unavailable_note(
                        "CSV редот не содржи удари, корнери ниту картони за "
                        "овој натпревар"
                    ),
                    class_name="mt-2.5 w-full",
                ),
            ),
            class_name="p-3.5 sm:p-4",
        ),
        class_name="w-full min-w-0 rounded-xl border border-zinc-800 bg-zinc-900/50 transition-colors hover:border-zinc-700",
    )


def _fd_section() -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.icon("file-spreadsheet", class_name="h-4 w-4 text-emerald-400"),
            rx.el.div(
                rx.el.h3(
                    "football-data.co.uk · предвидувања од реални CSV редови",
                    class_name="text-sm font-semibold tracking-tight text-white",
                ),
                rx.el.p(
                    f"Прикажани {T1x2State.visible_count} од {T1x2State.total_count} редови · средна сигурност {T1x2State.avg_confidence:.1f}% · {T1x2State.correct_count} од {T1x2State.settled_count} проверени точни",
                    class_name="text-xs font-medium text-zinc-500",
                ),
                class_name="flex min-w-0 flex-col",
            ),
            class_name="flex items-center gap-3 rounded-xl border border-zinc-800 bg-zinc-900/40 px-4 py-3",
        ),
        rx.cond(
            T1x2State.is_loading & ~T1x2State.has_data,
            loading_skeleton(),
            rx.cond(
                T1x2State.has_data,
                rx.el.div(
                    rx.el.div(
                        rx.foreach(T1x2State.league_tabs, _league_tab),
                        class_name="flex w-full items-center gap-1 overflow-x-auto rounded-xl border border-zinc-800 bg-zinc-900/40 p-1",
                    ),
                    rx.cond(
                        T1x2State.visible_count > 0,
                        rx.el.div(
                            rx.foreach(T1x2State.visible_rows, _fd_card),
                            class_name="mt-4 grid w-full grid-cols-1 gap-3 lg:grid-cols-2 2xl:grid-cols-3",
                        ),
                        rx.el.div(
                            rx.icon(
                                "filter-x", class_name="h-6 w-6 text-zinc-600"
                            ),
                            rx.el.p(
                                "Нема CSV редови за избраната лига",
                                class_name="mt-2 text-sm font-medium text-zinc-500",
                            ),
                            class_name="mt-4 flex w-full flex-col items-center justify-center rounded-xl border border-zinc-800 bg-zinc-900/40 py-14",
                        ),
                    ),
                    class_name="mt-3 w-full",
                ),
                rx.el.div(
                    rx.el.div(
                        rx.icon(
                            "calendar-off", class_name="h-6 w-6 text-zinc-600"
                        ),
                        rx.el.p(
                            T1x2State.empty_label,
                            class_name="mt-2 max-w-2xl text-center text-sm font-medium text-zinc-500",
                        ),
                        class_name="flex w-full flex-col items-center justify-center rounded-xl border border-zinc-800 bg-zinc-900/40 px-4 py-14",
                    ),
                    class_name="mt-3 w-full",
                ),
            ),
        ),
        class_name="w-full",
    )


def _ss_stat_row(stat: SportScoreStat) -> rx.Component:
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


def _ss_status_pill(row: SportScoreRow) -> rx.Component:
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


def _ss_card(row: SportScoreRow) -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.el.div(
                rx.el.span(
                    row["competition"],
                    class_name="truncate text-[11px] font-semibold uppercase tracking-wider text-zinc-500",
                ),
                _ss_status_pill(row),
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
                    class_name="w-fit whitespace-nowrap rounded-full border border-amber-500/40 bg-amber-500/10 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-amber-300",
                ),
                class_name="flex flex-wrap items-center gap-2",
            ),
            rx.el.div(
                rx.el.p(
                    row["home"],
                    class_name="min-w-0 flex-1 truncate text-sm font-semibold text-white",
                ),
                rx.el.span(
                    row["score"],
                    class_name="shrink-0 rounded-lg border border-zinc-800 bg-zinc-950/70 px-2.5 py-1 text-sm font-semibold text-zinc-200 tabular-nums",
                ),
                rx.el.p(
                    row["away"],
                    class_name="min-w-0 flex-1 truncate text-right text-sm font-semibold text-white",
                ),
                class_name="mt-2 flex items-center gap-3",
            ),
            rx.el.div(
                rx.el.span(
                    f"{row['kickoff']} · {row['status_text']}",
                    class_name="truncate text-[11px] font-medium text-zinc-600",
                ),
                rx.cond(
                    row["detail_url"] != "",
                    rx.el.a(
                        rx.icon("external-link", class_name="h-3 w-3"),
                        rx.el.span("SportScore"),
                        href=row["detail_url"],
                        target="_blank",
                        rel="noopener noreferrer",
                        class_name="flex w-fit shrink-0 items-center gap-1.5 text-[10px] font-semibold text-zinc-500 transition-colors hover:text-amber-300",
                    ),
                    rx.fragment(),
                ),
                class_name="mt-1.5 flex items-center justify-between gap-2",
            ),
            class_name="min-w-0 border-b border-zinc-800 px-4 py-3.5",
        ),
        rx.el.div(
            rx.cond(
                row["has_prediction"],
                rx.el.div(
                    rx.el.div(
                        rx.el.span(
                            row["meta_market"],
                            class_name="truncate text-[10px] font-semibold uppercase tracking-wider text-amber-300/80",
                        ),
                        rx.el.span(
                            f"{row['meta_confidence']:.1f}%",
                            class_name="shrink-0 text-sm font-semibold text-amber-300 tabular-nums",
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
                        "Изведено САМО од реални SportScore статистики (удари "
                        "во гол, опасни напади, поседување, тековен резултат) "
                        "· без xG и без квоти.",
                        class_name="mt-2 text-[10px] font-medium text-zinc-600",
                    ),
                    class_name="w-full min-w-0 rounded-lg border border-amber-500/25 bg-amber-500/[0.04] px-3 py-2.5",
                ),
                rx.el.div(
                    unavailable_note(row["prediction_note"]),
                    class_name="w-full",
                ),
            ),
            rx.cond(
                row["has_stats"],
                rx.el.div(
                    rx.el.span(
                        "SportScore статистики",
                        class_name="text-[10px] font-semibold uppercase tracking-wider text-zinc-500",
                    ),
                    rx.el.div(
                        rx.foreach(row["stats"], _ss_stat_row),
                        class_name="mt-2 flex flex-col gap-2",
                    ),
                    class_name="mt-2.5 w-full min-w-0 rounded-lg border border-zinc-800 bg-zinc-950/50 px-3 py-2.5",
                ),
                rx.fragment(),
            ),
            class_name="p-3.5 sm:p-4",
        ),
        class_name="w-full min-w-0 rounded-xl border border-zinc-800 bg-zinc-900/50 transition-colors hover:border-zinc-700",
    )


def _ss_section() -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.icon("globe", class_name="h-4 w-4 text-amber-400"),
            rx.el.div(
                rx.el.h3(
                    "SportScore · предвидувања од реални статистики",
                    class_name="text-sm font-semibold tracking-tight text-white",
                ),
                rx.el.p(
                    f"{SportScoreState.prediction_count} непокриени настани со реални статистики · средна сигурност {SportScoreState.avg_confidence:.1f}% · вчитано во {SportScoreState.fetched_at}",
                    class_name="text-xs font-medium text-zinc-500",
                ),
                class_name="flex min-w-0 flex-col",
            ),
            rx.el.span(
                rx.cond(
                    SportScoreState.is_loading,
                    "Се чита...",
                    SportScoreState.selected_date_label,
                ),
                class_name="ml-auto shrink-0 whitespace-nowrap rounded-full border border-zinc-800 bg-zinc-950/60 px-2.5 py-1 text-[10px] font-semibold text-zinc-400 tabular-nums",
            ),
            class_name="flex items-center gap-3 rounded-xl border border-zinc-800 bg-zinc-900/40 px-4 py-3",
        ),
        rx.cond(
            SportScoreState.is_loading & ~SportScoreState.has_data,
            loading_skeleton(),
            rx.cond(
                SportScoreState.prediction_count > 0,
                rx.el.div(
                    rx.foreach(SportScoreState.prediction_rows, _ss_card),
                    class_name="mt-3 grid w-full grid-cols-1 gap-3 lg:grid-cols-2 2xl:grid-cols-3",
                ),
                rx.el.div(
                    unavailable_note(
                        rx.cond(
                            SportScoreState.error != "",
                            SportScoreState.error,
                            "SportScore во моментот не дава непокриен настан со "
                            "реални статистики, па предвидување не е достапно "
                            "и ништо не се измислува.",
                        )
                    ),
                    class_name="mt-3 w-full",
                ),
            ),
        ),
        class_name="w-full",
    )


def t1x2_view() -> rx.Component:
    return rx.el.div(
        _header(),
        _source_statuses(),
        rx.el.div(_fd_section(), class_name="mt-6 w-full"),
        rx.el.div(
            _ss_section(),
            class_name="mt-6 w-full border-t border-zinc-800/70 pt-5",
        ),
        rx.cond(
            T1x2State.has_data | (SportScoreState.prediction_count > 0),
            rx.fragment(),
            rx.el.div(
                unavailable_note(
                    "Ниту football-data.co.uk CSV фајловите ниту SportScore не "
                    "вратија употреблив реален ред. Наместо примерок, тука не "
                    "се прикажува ништо."
                ),
                class_name="mt-6 w-full",
            ),
        ),
        class_name="w-full",
    )
