import reflex as rx

from app.components.api_status import (
    loading_skeleton,
    unavailable_note,
    warning_banner,
)
from app.states.mutating_state import MutatingRow, MutatingState


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
                "Mutating · предвидувања од Mutating.com",
                class_name="text-xl font-semibold tracking-tight text-white sm:text-2xl",
            ),
            rx.el.p(
                f"Вчитано во {MutatingState.fetched_at} · јавен извор без клуч · имена, лига, почеток и предвидувања од /soccer-predictions/, маркети од страницата за детали, статус и резултат од /updatepredictions/",
                class_name="mt-1 max-w-3xl text-sm font-medium text-zinc-500",
            ),
            rx.el.p(
                f"Синхронизирано во {MutatingState.coverage_synced_at} со {MutatingState.coverage_source_count} BZZ/Fotmob натпревари · {MutatingState.enriched_count} предвидувања со имена од страницата · прикажани само непокриени настани со реални маркети од страницата за детали · {MutatingState.without_markets_count} скриени без маркети",
                class_name="mt-1 max-w-3xl text-xs font-medium text-zinc-600",
            ),
            class_name="flex min-w-0 flex-col",
        ),
        rx.el.div(
            _chip(
                "Приказливи",
                MutatingState.named_count.to_string(),
                "database",
            ),
            _chip(
                "Непокриени",
                MutatingState.unmatched_count.to_string(),
                "unlink",
            ),
            _chip(
                "Скриени без маркети",
                MutatingState.without_markets_count.to_string(),
                "percent",
            ),
            _chip(
                "Решени",
                MutatingState.settled_count.to_string(),
                "circle-check",
            ),
            rx.el.button(
                rx.icon(
                    "refresh-cw",
                    class_name=rx.cond(
                        MutatingState.is_loading,
                        "h-3.5 w-3.5 animate-spin",
                        "h-3.5 w-3.5",
                    ),
                ),
                rx.el.span("Освежи извор", class_name="whitespace-nowrap"),
                on_click=MutatingState.refresh,
                class_name="flex shrink-0 items-center gap-2 rounded-lg border border-zinc-800 bg-zinc-900/60 px-3 py-1.5 text-xs font-semibold text-zinc-300 transition-colors hover:border-zinc-700 hover:text-white",
            ),
            class_name="flex flex-wrap items-center gap-2",
        ),
        class_name="mb-4 flex w-full flex-col gap-3 lg:flex-row lg:items-end lg:justify-between",
    )


def _kpi_card(
    label: str, value: rx.Var | str, hint: rx.Var | str, icon: str, accent: str
) -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.el.span(
                label,
                class_name="text-[11px] font-semibold uppercase tracking-wider text-zinc-500",
            ),
            rx.el.div(rx.icon(icon, class_name="h-4 w-4"), class_name=accent),
            class_name="flex items-start justify-between gap-3",
        ),
        rx.el.p(
            value,
            class_name="mt-3 text-2xl font-semibold tracking-tight text-white tabular-nums sm:text-3xl",
        ),
        rx.el.p(
            hint, class_name="mt-1 truncate text-xs font-medium text-zinc-500"
        ),
        class_name="w-full min-w-0 rounded-xl border border-zinc-800 bg-zinc-900/50 p-4 transition-colors hover:border-zinc-700",
    )


def _kpi_grid() -> rx.Component:
    return rx.el.div(
        _kpi_card(
            "Настани со маркети",
            MutatingState.named_count.to_string(),
            f"{MutatingState.without_markets_count} без маркети · {MutatingState.unnamed_count} без имена · скриени",
            "database",
            "flex size-8 items-center justify-center rounded-lg border border-blue-500/30 bg-blue-500/10 text-blue-400",
        ),
        _kpi_card(
            "Точни предвидувања",
            MutatingState.correct_count.to_string(),
            f"{MutatingState.wrong_count} погрешни · непокриени",
            "circle-check",
            "flex size-8 items-center justify-center rounded-lg border border-emerald-500/30 bg-emerald-500/10 text-emerald-400",
        ),
        _kpi_card(
            "Успешност на извор",
            f"{MutatingState.accuracy_rate:.1f}%",
            f"Од {MutatingState.settled_count} непокриени решени настани",
            "gauge",
            "flex size-8 items-center justify-center rounded-lg border border-amber-500/30 bg-amber-500/10 text-amber-400",
        ),
        _kpi_card(
            "Непокриени од BZZ/Fotmob",
            MutatingState.unmatched_count.to_string(),
            f"{MutatingState.matched_count} совпаднати · без квота и сигурност",
            "unlink",
            "flex size-8 items-center justify-center rounded-lg border border-zinc-700 bg-zinc-800/60 text-zinc-400",
        ),
        class_name="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4",
    )


def _filter_tab(tab: dict[str, str]) -> rx.Component:
    return rx.el.button(
        rx.el.span(tab["label"], class_name="whitespace-nowrap"),
        rx.el.span(
            tab["count"],
            class_name=rx.cond(
                MutatingState.filter_mode == tab["key"],
                "rounded-full bg-blue-500/20 px-1.5 text-[10px] font-bold text-blue-200 tabular-nums",
                "rounded-full bg-zinc-800 px-1.5 text-[10px] font-bold text-zinc-400 tabular-nums",
            ),
        ),
        on_click=lambda: MutatingState.set_filter_mode(tab["key"]),
        class_name=rx.cond(
            MutatingState.filter_mode == tab["key"],
            "flex flex-1 items-center justify-center gap-2 rounded-lg border border-blue-500/40 bg-blue-500/10 px-3 py-2 text-xs font-semibold text-blue-300 transition-all sm:text-sm",
            "flex flex-1 items-center justify-center gap-2 rounded-lg border border-transparent px-3 py-2 text-xs font-semibold text-zinc-500 transition-all hover:bg-zinc-900 hover:text-zinc-200 sm:text-sm",
        ),
    )


def _status_pill(row: MutatingRow) -> rx.Component:
    return rx.el.span(
        row["status"],
        class_name=rx.match(
            row["status_kind"],
            (
                "finished",
                "w-fit whitespace-nowrap rounded-full border border-zinc-700 bg-zinc-800/60 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-zinc-400",
            ),
            (
                "live",
                "w-fit whitespace-nowrap rounded-full border border-blue-500/30 bg-blue-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-blue-300",
            ),
            (
                "postponed",
                "w-fit whitespace-nowrap rounded-full border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-300",
            ),
            "w-fit whitespace-nowrap rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-emerald-300 tabular-nums",
        ),
    )


def _result_pill(row: MutatingRow) -> rx.Component:
    return rx.el.span(
        row["result_label"],
        class_name=rx.match(
            row["result"],
            (
                "correct",
                "w-fit whitespace-nowrap rounded-full border border-emerald-500/35 bg-emerald-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-emerald-300",
            ),
            (
                "wrong",
                "w-fit whitespace-nowrap rounded-full border border-red-500/30 bg-red-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-red-300",
            ),
            "w-fit whitespace-nowrap rounded-full border border-zinc-700 bg-zinc-800/60 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-zinc-500",
        ),
    )


def _pick_pill(row: MutatingRow) -> rx.Component:
    return rx.el.span(
        row["pick"],
        class_name="w-fit shrink-0 whitespace-nowrap rounded-lg border border-blue-500/35 bg-blue-500/10 px-2.5 py-0.5 text-xs font-bold text-blue-300",
    )


def _market_chip(label: str, value: rx.Var) -> rx.Component:
    """Компактен чип со реален процент од Mutating деталите."""
    return rx.el.div(
        rx.el.span(
            label,
            class_name="text-[9px] font-semibold uppercase tracking-wider text-zinc-500",
        ),
        rx.el.span(
            value,
            class_name=rx.cond(
                value == "недостапно",
                "mt-0.5 truncate text-[10px] font-medium text-zinc-600",
                "mt-0.5 text-[11px] font-semibold text-blue-300 tabular-nums",
            ),
        ),
        class_name="flex min-w-0 flex-col rounded-lg border border-zinc-800 bg-zinc-950/60 px-2 py-1.5",
    )


def _market_chips(row: MutatingRow) -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.el.span(
                "Маркети од страницата за детали",
                class_name="text-[10px] font-semibold uppercase tracking-wider text-zinc-500",
            ),
            rx.cond(
                row["has_markets"],
                rx.el.span(
                    "Реални проценти",
                    class_name="w-fit whitespace-nowrap rounded-full border border-blue-500/35 bg-blue-500/10 px-2 py-0.5 text-[9px] font-semibold uppercase tracking-wide text-blue-300",
                ),
                rx.el.span(
                    "недостапно",
                    class_name="w-fit whitespace-nowrap rounded-full border border-zinc-700 bg-zinc-800/60 px-2 py-0.5 text-[9px] font-semibold uppercase tracking-wide text-zinc-500",
                ),
            ),
            class_name="flex items-center justify-between gap-2",
        ),
        rx.el.div(
            _market_chip("ГГ", row["btts_label"]),
            _market_chip("НГ", row["ng_label"]),
            _market_chip("Над 1.5", row["over15_label"]),
            _market_chip("Под 1.5", row["under15_label"]),
            _market_chip("Над 2.5", row["over25_label"]),
            _market_chip("Под 2.5", row["under25_label"]),
            class_name="mt-2 grid grid-cols-3 gap-1.5",
        ),
        class_name="mt-2.5 w-full min-w-0 rounded-lg border border-zinc-800 bg-zinc-950/40 px-2.5 py-2",
    )


def _table_market_cell(row: MutatingRow) -> rx.Component:
    return rx.el.div(
        rx.el.span(
            f"ГГ {row['btts_label']}",
            class_name="w-fit whitespace-nowrap rounded-full border border-zinc-800 bg-zinc-950/60 px-2 py-0.5 text-[10px] font-medium text-zinc-400 tabular-nums",
        ),
        rx.el.span(
            f"1.5 {row['over15_label']}",
            class_name="w-fit whitespace-nowrap rounded-full border border-zinc-800 bg-zinc-950/60 px-2 py-0.5 text-[10px] font-medium text-zinc-400 tabular-nums",
        ),
        rx.el.span(
            f"2.5 {row['over25_label']}",
            class_name="w-fit whitespace-nowrap rounded-full border border-zinc-800 bg-zinc-950/60 px-2 py-0.5 text-[10px] font-medium text-zinc-400 tabular-nums",
        ),
        class_name="flex flex-wrap items-center justify-end gap-1",
    )


def _today_card(row: MutatingRow) -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.el.span(
                row["match_label"],
                class_name="min-w-0 flex-1 truncate text-sm font-semibold text-white",
            ),
            _status_pill(row),
            class_name="flex items-center justify-between gap-2",
        ),
        rx.el.p(
            f"{row['league_label']} · #{row['fixture_id']} · непокриен од BZZ/Fotmob",
            class_name="mt-1 truncate text-[10px] font-medium text-zinc-600",
        ),
        rx.el.div(
            rx.el.div(
                rx.el.span(
                    "Предвидување на Mutating",
                    class_name="text-[10px] font-semibold uppercase tracking-wider text-zinc-500",
                ),
                rx.cond(
                    row["pick_description"] != "",
                    rx.el.span(
                        row["pick_description"],
                        class_name="mt-0.5 truncate text-xs font-medium text-zinc-300",
                    ),
                    rx.fragment(),
                ),
                rx.el.span(
                    "квота и сигурност: недостапни",
                    class_name="mt-0.5 text-[10px] font-medium text-zinc-600",
                ),
                class_name="flex min-w-0 flex-col",
            ),
            _pick_pill(row),
            class_name="mt-2.5 flex items-center justify-between gap-2 rounded-lg border border-zinc-800 bg-zinc-950/60 px-2.5 py-2",
        ),
        _market_chips(row),
        rx.cond(
            row["detail_url"] != "",
            rx.el.a(
                rx.icon("external-link", class_name="h-3 w-3"),
                rx.el.span("Детали на Mutating.com"),
                href=row["detail_url"],
                target="_blank",
                rel="noopener noreferrer",
                class_name="mt-2 flex w-fit items-center gap-1.5 text-[10px] font-semibold text-zinc-500 transition-colors hover:text-blue-300",
            ),
            rx.fragment(),
        ),
        rx.el.div(
            rx.el.div(
                rx.el.span(
                    "Резултат",
                    class_name="text-[10px] font-semibold uppercase tracking-wider text-zinc-500",
                ),
                rx.el.span(
                    row["score"],
                    class_name="mt-0.5 text-sm font-semibold text-white tabular-nums",
                ),
                class_name="flex w-full flex-col rounded-lg border border-zinc-800 bg-zinc-950/60 px-2.5 py-2",
            ),
            rx.el.div(
                rx.el.span(
                    "Почеток / статус",
                    class_name="text-[10px] font-semibold uppercase tracking-wider text-zinc-500",
                ),
                rx.el.span(
                    row["status"],
                    class_name="mt-0.5 text-sm font-semibold text-zinc-200 tabular-nums",
                ),
                class_name="flex w-full flex-col rounded-lg border border-zinc-800 bg-zinc-950/60 px-2.5 py-2",
            ),
            class_name="mt-2.5 grid grid-cols-2 gap-2",
        ),
        rx.el.div(
            rx.el.span(
                row["winner_label"],
                class_name=rx.match(
                    row["winner"],
                    (
                        "home",
                        "w-fit whitespace-nowrap rounded-full border border-blue-500/35 bg-blue-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-blue-300",
                    ),
                    (
                        "away",
                        "w-fit whitespace-nowrap rounded-full border border-emerald-500/35 bg-emerald-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-emerald-300",
                    ),
                    "w-fit whitespace-nowrap rounded-full border border-zinc-700 bg-zinc-800/60 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-zinc-500",
                ),
            ),
            _result_pill(row),
            class_name="mt-2.5 flex items-center justify-between gap-2",
        ),
        class_name="w-full min-w-0 rounded-xl border border-zinc-800 bg-zinc-900/50 p-3.5 transition-colors hover:border-zinc-700",
    )


def _today_games() -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.icon("unlink", class_name="h-4 w-4 text-blue-400"),
            rx.el.div(
                rx.el.h3(
                    "Непокриени Mutating предвидувања со маркети (денес)",
                    class_name="text-sm font-semibold tracking-tight text-white",
                ),
                rx.el.p(
                    f"{MutatingState.today_label} · {MutatingState.unmatched_count} непокриени од {MutatingState.named_count} настани со имена, предвидување и реални маркети · {MutatingState.matched_count} совпаднати со BZZ/Fotmob",
                    class_name="text-xs font-medium text-zinc-500",
                ),
                class_name="flex min-w-0 flex-col",
            ),
            rx.el.span(
                rx.cond(
                    MutatingState.is_loading,
                    "Се освежува...",
                    f"Ажурирано {MutatingState.fetched_at}",
                ),
                class_name="ml-auto shrink-0 whitespace-nowrap rounded-full border border-zinc-800 bg-zinc-950/60 px-2.5 py-1 text-[10px] font-semibold text-zinc-400 tabular-nums",
            ),
            class_name="flex items-center gap-3 border-b border-zinc-800 px-4 py-3",
        ),
        rx.cond(
            MutatingState.today_rows.length() > 0,
            rx.el.div(
                rx.el.div(
                    rx.foreach(MutatingState.today_rows, _today_card),
                    class_name="grid w-full grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3",
                ),
                rx.el.div(
                    rx.icon(
                        "info",
                        class_name="mt-0.5 h-4 w-4 shrink-0 text-blue-400",
                    ),
                    rx.el.div(
                        rx.el.p(
                            MutatingState.coverage_note,
                            class_name="text-xs font-medium text-zinc-400",
                        ),
                        rx.el.p(
                            MutatingState.today_note,
                            class_name="mt-1 text-xs font-medium text-zinc-500",
                        ),
                        rx.el.p(
                            MutatingState.odds_note,
                            class_name="mt-1 text-xs font-medium text-zinc-500",
                        ),
                        rx.el.p(
                            MutatingState.markets_note,
                            class_name="mt-1 text-xs font-medium text-zinc-500",
                        ),
                        rx.cond(
                            MutatingState.pending_note != "",
                            rx.el.p(
                                MutatingState.pending_note,
                                class_name="mt-1 text-xs font-medium text-zinc-600",
                            ),
                            rx.fragment(),
                        ),
                        class_name="flex min-w-0 flex-col",
                    ),
                    class_name="mt-3 flex w-full items-start gap-3 rounded-lg border border-zinc-800 bg-zinc-950/50 px-3 py-2.5",
                ),
                class_name="p-4",
            ),
            rx.el.div(
                rx.icon("calendar-off", class_name="h-6 w-6 text-zinc-600"),
                rx.el.p(
                    MutatingState.coverage_note,
                    class_name="mt-2 max-w-md text-center text-sm font-medium text-zinc-500",
                ),
                class_name="flex flex-col items-center justify-center px-4 py-14",
            ),
        ),
        class_name="w-full overflow-hidden rounded-xl border border-zinc-800 bg-zinc-900/50",
    )


def _row(row: MutatingRow) -> rx.Component:
    return rx.el.tr(
        rx.el.td(
            rx.el.div(
                rx.el.span(
                    row["match_label"],
                    class_name="truncate text-sm font-medium text-zinc-100",
                ),
                rx.el.span(
                    f"{row['league_label']} · #{row['fixture_id']} · без квота/сигурност",
                    class_name="truncate text-[10px] font-medium text-zinc-600",
                ),
                class_name="flex min-w-0 flex-col",
            ),
            class_name="px-3 py-2.5",
        ),
        rx.el.td(_pick_pill(row), class_name="px-3 py-2.5"),
        rx.el.td(
            _table_market_cell(row),
            class_name="hidden px-3 py-2.5 lg:table-cell",
        ),
        rx.el.td(_status_pill(row), class_name="px-3 py-2.5"),
        rx.el.td(
            row["score"],
            class_name="px-3 py-2.5 text-right text-sm font-semibold text-white tabular-nums",
        ),
        rx.el.td(
            rx.el.span(
                rx.match(
                    row["winner"],
                    ("home", "Домашен"),
                    ("away", "Гостин"),
                    "—",
                ),
                class_name="text-xs font-medium text-zinc-400",
            ),
            class_name="hidden px-3 py-2.5 text-right sm:table-cell",
        ),
        rx.el.td(_result_pill(row), class_name="px-3 py-2.5 text-right"),
        class_name="border-b border-zinc-800/70 transition-colors last:border-0 hover:bg-zinc-800/30",
    )


def _table() -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.icon("table-2", class_name="h-4 w-4 text-blue-400"),
            rx.el.div(
                rx.el.h3(
                    "Непокриени предвидувања со маркети од Mutating.com",
                    class_name="text-sm font-semibold tracking-tight text-white",
                ),
                rx.el.p(
                    f"Прикажани {MutatingState.visible_count} од {MutatingState.unmatched_count} непокриени настани со реални маркети · {MutatingState.named_count} од {MutatingState.total_count} редови се приказливи · {MutatingState.without_markets_count} скриени без маркети",
                    class_name="text-xs font-medium text-zinc-500",
                ),
                class_name="flex min-w-0 flex-col",
            ),
            class_name="flex items-center gap-3 border-b border-zinc-800 px-4 py-3",
        ),
        rx.cond(
            MutatingState.visible_count > 0,
            rx.el.div(
                rx.el.div(
                    rx.el.table(
                        rx.el.thead(
                            rx.el.tr(
                                rx.el.th(
                                    "Натпревар",
                                    class_name="px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-wider text-zinc-500",
                                ),
                                rx.el.th(
                                    "Предвидување",
                                    class_name="px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-wider text-zinc-500",
                                ),
                                rx.el.th(
                                    "Маркети (ГГ / 1.5 / 2.5)",
                                    class_name="hidden px-3 py-2 text-right text-[11px] font-semibold uppercase tracking-wider text-zinc-500 lg:table-cell",
                                ),
                                rx.el.th(
                                    "Статус",
                                    class_name="px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-wider text-zinc-500",
                                ),
                                rx.el.th(
                                    "Резултат",
                                    class_name="px-3 py-2 text-right text-[11px] font-semibold uppercase tracking-wider text-zinc-500",
                                ),
                                rx.el.th(
                                    "Победник",
                                    class_name="hidden px-3 py-2 text-right text-[11px] font-semibold uppercase tracking-wider text-zinc-500 sm:table-cell",
                                ),
                                rx.el.th(
                                    "Ознака",
                                    class_name="px-3 py-2 text-right text-[11px] font-semibold uppercase tracking-wider text-zinc-500",
                                ),
                            ),
                            class_name="border-b border-zinc-800 bg-zinc-950/40",
                        ),
                        rx.el.tbody(
                            rx.foreach(MutatingState.visible_rows, _row)
                        ),
                        class_name="w-full table-auto",
                    ),
                    class_name="w-full overflow-x-auto",
                ),
                class_name="p-4",
            ),
            rx.el.div(
                rx.icon("filter-x", class_name="h-6 w-6 text-zinc-600"),
                rx.el.p(
                    rx.cond(
                        MutatingState.has_result_rows,
                        "Нема непокриени настани со предвидување за избраниот филтер",
                        MutatingState.coverage_note,
                    ),
                    class_name="mt-2 max-w-md text-center text-sm font-medium text-zinc-500",
                ),
                class_name="flex flex-col items-center justify-center py-14",
            ),
        ),
        class_name="w-full overflow-hidden rounded-xl border border-zinc-800 bg-zinc-900/50",
    )


def _makeyourstats_note() -> rx.Component:
    """Ознака за недостапен извор што чека официјален/јавен пристап."""
    return rx.el.div(
        rx.icon(
            "circle-slash", class_name="mt-0.5 h-4 w-4 shrink-0 text-zinc-500"
        ),
        rx.el.div(
            rx.el.div(
                rx.el.p(
                    "MakeYourStats",
                    class_name="text-sm font-semibold tracking-tight text-white",
                ),
                rx.el.span(
                    "Чека официјален пристап",
                    class_name="w-fit whitespace-nowrap rounded-full border border-zinc-700 bg-zinc-800/60 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-zinc-400",
                ),
                class_name="flex flex-wrap items-center gap-2",
            ),
            rx.el.p(
                MutatingState.makeyourstats_note,
                class_name="mt-1 text-xs font-medium text-zinc-500",
            ),
            class_name="flex min-w-0 flex-col",
        ),
        class_name="mt-4 flex w-full items-start gap-3 rounded-xl border border-dashed border-zinc-800 bg-zinc-900/40 px-4 py-3",
    )


def mutating_panel() -> rx.Component:
    return rx.el.div(
        _header(),
        warning_banner(MutatingState.error),
        warning_banner(MutatingState.page_notice),
        rx.cond(
            MutatingState.is_loading & ~MutatingState.has_data,
            loading_skeleton(),
            rx.cond(
                MutatingState.has_data,
                rx.el.div(
                    _kpi_grid(),
                    rx.el.div(
                        rx.foreach(MutatingState.filter_tabs, _filter_tab),
                        class_name="mt-4 flex w-full items-center gap-1 overflow-x-auto rounded-xl border border-zinc-800 bg-zinc-900/40 p-1",
                    ),
                    rx.el.div(_today_games(), class_name="mt-4 w-full"),
                    rx.el.div(_table(), class_name="mt-4 w-full"),
                    rx.el.div(
                        rx.icon(
                            "info",
                            class_name="mt-0.5 h-4 w-4 shrink-0 text-blue-400",
                        ),
                        rx.el.p(
                            MutatingState.limitation_note,
                            class_name="text-xs font-medium text-zinc-400",
                        ),
                        class_name="mt-4 flex w-full items-start gap-3 rounded-xl border border-zinc-800 bg-zinc-900/40 px-4 py-3",
                    ),
                    _makeyourstats_note(),
                    class_name="w-full",
                ),
                rx.el.div(
                    unavailable_note(MutatingState.coverage_note),
                    _makeyourstats_note(),
                    class_name="w-full",
                ),
            ),
        ),
        class_name="w-full",
    )
