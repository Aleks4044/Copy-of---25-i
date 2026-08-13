import reflex as rx

from app.components.api_status import unavailable_note
from app.states.bsd_state import BSDMatch
from app.states.fudbal91_client import (
    Fudbal91Row,
    MutualRow,
    OptionRow,
    StatRow,
)
from app.states.fudbal91_state import Fudbal91State


def _tile(label: str, value: rx.Var | str, hint: rx.Var | str) -> rx.Component:
    return rx.el.div(
        rx.el.span(
            label,
            class_name="text-[10px] font-semibold uppercase tracking-wider text-zinc-500",
        ),
        rx.el.span(
            value,
            class_name="mt-0.5 truncate text-sm font-semibold text-white tabular-nums",
        ),
        rx.el.span(
            hint, class_name="truncate text-[10px] font-medium text-zinc-500"
        ),
        class_name="flex w-full min-w-0 flex-col rounded-lg border border-zinc-800 bg-zinc-950/60 px-2.5 py-2",
    )


def _option_row(option: OptionRow) -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.el.span(
                option["label"],
                class_name="min-w-0 flex-1 truncate text-xs font-semibold text-white",
            ),
            rx.el.span(
                f"{option['probability']:.1f}%",
                class_name="shrink-0 text-xs font-semibold text-blue-300 tabular-nums",
            ),
            class_name="flex items-center gap-2",
        ),
        rx.el.div(
            rx.el.div(
                class_name="h-full rounded-full bg-blue-500 transition-all duration-700",
                style={"width": f"{option['probability']}%"},
            ),
            class_name="mt-1.5 h-1 w-full overflow-hidden rounded-full bg-zinc-800",
        ),
        rx.el.span(
            option["support_label"],
            class_name="mt-1.5 block truncate text-[10px] font-medium text-zinc-500",
        ),
        class_name="w-full min-w-0 rounded-lg border border-zinc-800 bg-zinc-950/60 px-2.5 py-2",
    )


def _mutual_row(row: MutualRow) -> rx.Component:
    return rx.el.tr(
        rx.el.td(
            row["date"],
            class_name="px-2 py-1.5 text-left text-[11px] font-medium text-zinc-300 tabular-nums",
        ),
        rx.el.td(
            row["score"],
            class_name="px-2 py-1.5 text-center text-[11px] font-semibold text-white tabular-nums",
        ),
        rx.el.td(
            row["goals"],
            class_name="px-2 py-1.5 text-center text-[11px] font-medium text-zinc-400",
        ),
        rx.el.td(
            row["competition"],
            class_name="hidden px-2 py-1.5 text-left text-[11px] font-medium text-zinc-500 sm:table-cell",
        ),
        rx.el.td(
            row["season"],
            class_name="hidden px-2 py-1.5 text-right text-[11px] font-medium text-zinc-500 tabular-nums md:table-cell",
        ),
        class_name="border-b border-zinc-800/70 last:border-0",
    )


def _mutual_table(row: Fudbal91Row) -> rx.Component:
    return rx.el.div(
        rx.el.span(
            "Меѓусебни средби (Fudbal91)",
            class_name="text-[10px] font-semibold uppercase tracking-wider text-zinc-500",
        ),
        rx.el.div(
            rx.el.table(
                rx.el.thead(
                    rx.el.tr(
                        rx.el.th(
                            "Датум",
                            class_name="px-2 py-1 text-left text-[10px] font-semibold uppercase tracking-wider text-zinc-500",
                        ),
                        rx.el.th(
                            "Резултат",
                            class_name="px-2 py-1 text-center text-[10px] font-semibold uppercase tracking-wider text-zinc-500",
                        ),
                        rx.el.th(
                            "Голови",
                            class_name="px-2 py-1 text-center text-[10px] font-semibold uppercase tracking-wider text-zinc-500",
                        ),
                        rx.el.th(
                            "Натпреварување",
                            class_name="hidden px-2 py-1 text-left text-[10px] font-semibold uppercase tracking-wider text-zinc-500 sm:table-cell",
                        ),
                        rx.el.th(
                            "Сезона",
                            class_name="hidden px-2 py-1 text-right text-[10px] font-semibold uppercase tracking-wider text-zinc-500 md:table-cell",
                        ),
                    ),
                    class_name="border-b border-zinc-800 bg-zinc-950/50",
                ),
                rx.el.tbody(rx.foreach(row["mutual_rows"], _mutual_row)),
                class_name="w-full table-auto",
            ),
            class_name="mt-2 w-full overflow-x-auto",
        ),
        class_name="mt-2.5 w-full min-w-0 overflow-hidden rounded-lg border border-zinc-800 bg-zinc-950/40 px-2.5 py-2",
    )


def _stat_row(stat: StatRow) -> rx.Component:
    return rx.el.div(
        rx.el.span(
            stat["label"],
            class_name="min-w-0 flex-1 truncate text-[11px] font-medium text-zinc-400",
        ),
        rx.el.span(
            stat["value"],
            class_name="shrink-0 text-[11px] font-semibold text-zinc-200 tabular-nums",
        ),
        class_name="flex items-center justify-between gap-3 border-b border-zinc-800/70 py-1.5 last:border-0",
    )


def _stats_block(row: Fudbal91Row) -> rx.Component:
    return rx.cond(
        row["has_stats"],
        rx.el.div(
            rx.el.span(
                "Дополнителни статистики",
                class_name="text-[10px] font-semibold uppercase tracking-wider text-zinc-500",
            ),
            rx.el.div(
                rx.foreach(row["stat_rows"], _stat_row),
                class_name="mt-1 flex flex-col",
            ),
            class_name="mt-2.5 w-full min-w-0 rounded-lg border border-zinc-800 bg-zinc-950/40 px-2.5 py-2",
        ),
        rx.el.div(
            unavailable_note(
                "Fudbal91 не објавува дополнителни статистики за овој натпревар"
            ),
            class_name="mt-2.5 w-full",
        ),
    )


def _source_pick_block(row: Fudbal91Row) -> rx.Component:
    return rx.cond(
        row["has_source_pick"],
        rx.el.div(
            rx.el.div(
                rx.el.span(
                    "Избор од изворот · најниска просечна квота",
                    class_name="text-[10px] font-semibold uppercase tracking-wider text-zinc-500",
                ),
                rx.el.span(
                    f"квота {row['source_pick_odds']:.2f}",
                    class_name="whitespace-nowrap text-[10px] font-semibold text-zinc-400 tabular-nums",
                ),
                class_name="flex flex-wrap items-center justify-between gap-2",
            ),
            rx.el.p(
                row["source_pick"],
                class_name="mt-0.5 truncate text-sm font-semibold text-white",
            ),
            class_name="mt-2.5 w-full min-w-0 rounded-lg border border-blue-500/25 bg-blue-500/[0.05] px-2.5 py-2",
        ),
        rx.el.div(
            unavailable_note(
                "Fudbal91 не објавува просечни квоти 1/X/2 за овој натпревар, "
                "па избор од изворот не може да се изведе"
            ),
            class_name="mt-2.5 w-full",
        ),
    )


def _closed_summary(row: Fudbal91Row) -> rx.Component:
    return rx.el.div(
        _tile(
            "Поддршка",
            row["support_label"],
            row["top_label"],
        ),
        _tile(
            "Топ опција",
            rx.cond(
                row["top_probability"] > 0.0,
                f"{row['top_probability']:.1f}%",
                "недостапно",
            ),
            "изведено од просечни квоти",
        ),
        _tile(
            "FT проекција",
            row["ft_projection"],
            rx.cond(
                row["ft_probability"] > 0.0,
                f"{row['ft_probability']:.1f}% од матрицата",
                "нема линија за 2.5 гола",
            ),
        ),
        _tile(
            "HT проекција",
            row["ht_projection"],
            rx.cond(
                row["ht_probability"] > 0.0,
                f"{row['ht_probability']:.1f}% · ~45% од голови",
                "недостапно",
            ),
        ),
        class_name="mt-2.5 grid grid-cols-2 gap-2 sm:grid-cols-4",
    )


def _open_details(row: Fudbal91Row) -> rx.Component:
    return rx.el.div(
        _source_pick_block(row),
        rx.el.div(
            rx.el.span(
                "Топ 3 поддржани опции",
                class_name="text-[10px] font-semibold uppercase tracking-wider text-zinc-500",
            ),
            rx.cond(
                row["options"].length() > 0,
                rx.el.div(
                    rx.foreach(row["options"], _option_row),
                    class_name="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-3",
                ),
                rx.el.div(
                    unavailable_note(
                        "Без објавени просечни квоти не може да се изведе "
                        "поддршка по опција"
                    ),
                    class_name="mt-2 w-full",
                ),
            ),
            class_name="mt-2.5 w-full min-w-0 rounded-lg border border-zinc-800 bg-zinc-950/40 px-2.5 py-2",
        ),
        rx.el.div(
            _tile(
                "Очекувани голови",
                rx.cond(
                    row["expected_goals"] > 0.0,
                    f"{row['expected_goals']:.2f}",
                    "недостапно",
                ),
                "од линијата 0-2 / 3+",
            ),
            _tile(
                "Над / Под 2.5",
                rx.cond(
                    row["prob_over25"] > 0.0,
                    f"{row['prob_over25']:.1f}% / {row['prob_under25']:.1f}%",
                    "недостапно",
                ),
                "имплицирано од просечни квоти",
            ),
            _tile("FT проекција", row["ft_projection"], "Poisson од квотите"),
            _tile("HT проекција", row["ht_projection"], "~45% од очекувани"),
            class_name="mt-2.5 grid grid-cols-2 gap-2 sm:grid-cols-4",
        ),
        rx.cond(
            row["has_mutual"],
            _mutual_table(row),
            rx.el.div(
                unavailable_note(
                    rx.cond(
                        row["compare_note"] != "",
                        row["compare_note"],
                        "Fudbal91 не објавува меѓусебни средби ниту табела за "
                        "овој натпревар",
                    )
                ),
                class_name="mt-2.5 w-full",
            ),
        ),
        _stats_block(row),
        rx.el.div(
            rx.el.div(
                rx.el.span(
                    "Отсутни играчи",
                    class_name="text-[10px] font-semibold uppercase tracking-wider text-zinc-500",
                ),
                rx.el.span(
                    row["absences_label"],
                    class_name="w-fit whitespace-nowrap rounded-full border border-zinc-700 bg-zinc-800/60 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-zinc-400",
                ),
                class_name="flex flex-wrap items-center justify-between gap-2",
            ),
            rx.el.p(
                row["absences_note"],
                class_name="mt-1 text-[10px] font-medium text-zinc-600",
            ),
            class_name="mt-2.5 w-full min-w-0 rounded-lg border border-dashed border-zinc-800 bg-zinc-950/40 px-2.5 py-2",
        ),
        rx.el.p(
            row["derived_note"],
            class_name="mt-2.5 text-[10px] font-medium text-zinc-600",
        ),
        rx.el.p(
            Fudbal91State.sportscore_note,
            class_name="mt-1 text-[10px] font-medium text-zinc-600",
        ),
        rx.cond(
            row["compare_url"] != "",
            rx.el.a(
                rx.icon("external-link", class_name="h-3 w-3"),
                rx.el.span("Споредба на Fudbal91"),
                href=row["compare_url"],
                target="_blank",
                rel="noopener noreferrer",
                class_name="mt-2 flex w-fit items-center gap-1.5 text-[10px] font-semibold text-zinc-500 transition-colors hover:text-blue-300",
            ),
            rx.fragment(),
        ),
        class_name="w-full",
    )


def fudbal91_context_panel(row: Fudbal91Row) -> rx.Component:
    """Компактен, расклопувачки „Fudbal91 статистички контекст“."""
    return rx.el.div(
        rx.el.div(
            rx.el.div(
                rx.icon("chart-line", class_name="h-3.5 w-3.5"),
                rx.el.span(
                    "Fudbal91 статистички контекст",
                    class_name="text-[11px] font-semibold uppercase tracking-wider",
                ),
                class_name="flex w-fit items-center gap-1.5 rounded-md border border-blue-500/30 bg-blue-500/10 px-2 py-1 text-blue-300",
            ),
            rx.el.span(
                row["competition"],
                class_name="truncate text-[10px] font-medium text-zinc-600",
            ),
            class_name="flex flex-wrap items-center justify-between gap-2",
        ),
        _closed_summary(row),
        rx.cond(
            Fudbal91State.expanded_ids.contains(row["id"]),
            _open_details(row),
            rx.fragment(),
        ),
        rx.el.button(
            rx.cond(
                Fudbal91State.expanded_ids.contains(row["id"]),
                rx.el.span("Сокрий Fudbal91 контекст"),
                rx.el.span("Прикажи Fudbal91 контекст"),
            ),
            rx.icon(
                "chevron-down",
                class_name=rx.cond(
                    Fudbal91State.expanded_ids.contains(row["id"]),
                    "h-3.5 w-3.5 rotate-180 transition-transform",
                    "h-3.5 w-3.5 transition-transform",
                ),
            ),
            on_click=lambda: Fudbal91State.toggle_expanded(row["id"]),
            class_name="mt-2.5 flex w-full items-center justify-center gap-2 rounded-lg border border-zinc-800 bg-zinc-950/50 px-3 py-2 text-xs font-semibold text-zinc-400 transition-colors hover:border-zinc-700 hover:text-white",
        ),
        class_name="mt-3 w-full min-w-0 rounded-lg border border-zinc-800 bg-zinc-900/40 p-3.5",
    )


def fudbal91_card(row: Fudbal91Row) -> rx.Component:
    """Дополнителна картичка за натпревар што недостасува во другите извори."""
    return rx.el.div(
        rx.el.div(
            rx.el.div(
                rx.el.span(
                    row["competition"],
                    class_name="truncate text-[11px] font-semibold uppercase tracking-wider text-zinc-500",
                ),
                rx.el.span(
                    row["kickoff"],
                    class_name="w-fit whitespace-nowrap rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-emerald-300 tabular-nums",
                ),
                rx.el.div(
                    rx.icon("database", class_name="h-3 w-3"),
                    rx.el.span(
                        Fudbal91State.missing_badge,
                        class_name="text-[10px] font-bold uppercase tracking-wider",
                    ),
                    class_name="flex w-fit shrink-0 items-center gap-1.5 rounded-full border border-amber-500/40 bg-amber-500/10 px-2 py-0.5 text-amber-300",
                ),
                class_name="flex flex-wrap items-center gap-2",
            ),
            rx.el.div(
                rx.el.p(
                    row["home"],
                    class_name="min-w-0 flex-1 truncate text-sm font-semibold text-white sm:text-base",
                ),
                rx.el.span(
                    "vs",
                    class_name="shrink-0 rounded-lg border border-zinc-800 bg-zinc-950/70 px-2.5 py-1 text-sm font-semibold text-zinc-200",
                ),
                rx.el.p(
                    row["away"],
                    class_name="min-w-0 flex-1 truncate text-right text-sm font-semibold text-white sm:text-base",
                ),
                class_name="mt-2 flex items-center gap-3",
            ),
            rx.el.p(
                f"{row['day_label']} {row['kickoff']} · Fudbal91 јавна понуда",
                class_name="mt-1.5 text-center text-[11px] font-medium text-zinc-600",
            ),
            class_name="min-w-0 border-b border-zinc-800 px-4 py-3.5",
        ),
        rx.el.div(
            rx.cond(
                row["has_context"],
                fudbal91_context_panel(row),
                unavailable_note(
                    "Fudbal91 не објавува просечни квоти ниту статистики за "
                    "овој натпревар, па контекст не е достапен"
                ),
            ),
            class_name="p-3.5 sm:p-4",
        ),
        class_name="w-full min-w-0 rounded-xl border border-zinc-800 bg-zinc-900/50 transition-colors hover:border-zinc-700",
    )


def fudbal91_match_context(match: BSDMatch) -> rx.Component:
    """Контекст панел за спарена BZZ/Fotmob картичка (ако постои)."""
    return rx.foreach(
        Fudbal91State.matched_contexts,
        lambda row: rx.cond(
            row["match_id"] == match["id"],
            fudbal91_context_panel(row),
            rx.fragment(),
        ),
    )


def fudbal91_section() -> rx.Component:
    """Секција со дополнителните Fudbal91 картички во BSD Предвидувања."""
    return rx.el.div(
        rx.el.div(
            rx.el.div(
                rx.icon("database", class_name="h-4 w-4 text-amber-400"),
                rx.el.div(
                    rx.el.h3(
                        "Fudbal91 · натпревари што недостасуваат во BZZ",
                        class_name="text-sm font-semibold tracking-tight text-white",
                    ),
                    rx.el.p(
                        Fudbal91State.summary_label,
                        class_name="text-xs font-medium text-zinc-500",
                    ),
                    class_name="flex min-w-0 flex-col",
                ),
                class_name="flex min-w-0 items-center gap-3",
            ),
            rx.el.span(
                rx.cond(
                    Fudbal91State.is_loading,
                    "Се вчитува...",
                    f"Ажурирано {Fudbal91State.fetched_at}",
                ),
                class_name="shrink-0 whitespace-nowrap rounded-full border border-zinc-800 bg-zinc-950/60 px-2.5 py-1 text-[10px] font-semibold text-zinc-400 tabular-nums",
            ),
            class_name="flex flex-wrap items-center justify-between gap-3 border-b border-zinc-800 px-4 py-3",
        ),
        rx.el.div(
            rx.cond(
                Fudbal91State.missing_rows.length() > 0,
                rx.el.div(
                    rx.el.div(
                        rx.foreach(Fudbal91State.missing_rows, fudbal91_card),
                        class_name="grid w-full grid-cols-1 gap-3 lg:grid-cols-2",
                    ),
                    rx.el.div(
                        rx.icon(
                            "info",
                            class_name="mt-0.5 h-4 w-4 shrink-0 text-blue-400",
                        ),
                        rx.el.div(
                            rx.el.p(
                                Fudbal91State.coverage_note,
                                class_name="text-xs font-medium text-zinc-400",
                            ),
                            rx.el.p(
                                Fudbal91State.robots_note,
                                class_name="mt-1 text-xs font-medium text-zinc-500",
                            ),
                            rx.el.p(
                                Fudbal91State.sportscore_note,
                                class_name="mt-1 text-xs font-medium text-zinc-500",
                            ),
                            class_name="flex min-w-0 flex-col",
                        ),
                        class_name="mt-3 flex w-full items-start gap-3 rounded-lg border border-zinc-800 bg-zinc-950/50 px-3 py-2.5",
                    ),
                    class_name="w-full",
                ),
                unavailable_note(Fudbal91State.empty_missing_note),
            ),
            class_name="p-4",
        ),
        class_name="mt-4 w-full overflow-hidden rounded-xl border border-zinc-800 bg-zinc-900/50",
    )
