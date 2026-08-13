import reflex as rx

from app.components.api_status import unavailable_note
from app.states.mutating_state import MutatingRow, MutatingState
from app.states.sportscore_client import SportScoreRow
from app.states.sportscore_state import SportScoreState


def _source_chip(label: str, icon: str, accent: str) -> rx.Component:
    return rx.el.div(
        rx.icon(icon, class_name="h-3 w-3"),
        rx.el.span(
            label,
            class_name="text-[10px] font-bold uppercase tracking-wider",
        ),
        class_name=accent,
    )


def _value_tile(
    label: str, value: rx.Var | str, hint: rx.Var | str
) -> rx.Component:
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
            hint,
            class_name="truncate text-[10px] font-medium text-zinc-500",
        ),
        class_name="flex w-full min-w-0 flex-col rounded-lg border border-zinc-800 bg-zinc-950/60 px-2.5 py-2",
    )


def _mutating_status_pill(row: MutatingRow) -> rx.Component:
    return rx.el.span(
        row["status"],
        class_name=rx.match(
            row["status_kind"],
            (
                "live",
                "w-fit whitespace-nowrap rounded-full border border-blue-500/30 bg-blue-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-blue-300",
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


def _mutating_card(row: MutatingRow) -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.el.div(
                rx.el.span(
                    row["match_label"],
                    class_name="truncate text-sm font-semibold text-white",
                ),
                rx.el.p(
                    f"{row['league_label']} · #{row['fixture_id']}",
                    class_name="mt-0.5 truncate text-[10px] font-medium text-zinc-600",
                ),
                class_name="min-w-0 flex-1",
            ),
            _source_chip(
                "Mutating",
                "database",
                "flex w-fit shrink-0 items-center gap-1.5 rounded-full border border-zinc-700 bg-zinc-800/60 px-2 py-0.5 text-zinc-300",
            ),
            class_name="flex items-start gap-2 border-b border-zinc-800 px-3.5 py-3",
        ),
        rx.el.div(
            rx.el.div(
                _mutating_status_pill(row),
                rx.el.span(
                    row["score"],
                    class_name="whitespace-nowrap text-[10px] font-semibold text-zinc-400 tabular-nums",
                ),
                rx.el.span(
                    row["pick"],
                    class_name="w-fit shrink-0 whitespace-nowrap rounded-lg border border-blue-500/35 bg-blue-500/10 px-2 py-0.5 text-xs font-bold text-blue-300",
                ),
                class_name="flex flex-wrap items-center gap-2",
            ),
            rx.cond(
                row["pick_description"] != "",
                rx.el.p(
                    row["pick_description"],
                    class_name="mt-1.5 truncate text-xs font-medium text-zinc-300",
                ),
                rx.fragment(),
            ),
            rx.el.div(
                _value_tile("ГГ", row["btts_label"], "од страницата за детали"),
                _value_tile("Над 1.5", row["over15_label"], "реален процент"),
                _value_tile("Над 2.5", row["over25_label"], "реален процент"),
                _value_tile("НГ", row["ng_label"], "без ГГ"),
                class_name="mt-2.5 grid grid-cols-2 gap-2",
            ),
            rx.el.p(
                "Квота и сигурност не се објавени од Mutating.com и не се "
                "измислуваат.",
                class_name="mt-2 text-[10px] font-medium text-zinc-600",
            ),
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
            class_name="p-3.5",
        ),
        class_name="w-full min-w-0 rounded-xl border border-zinc-800 bg-zinc-900/50 transition-colors hover:border-zinc-700",
    )


def _sportscore_status_pill(row: SportScoreRow) -> rx.Component:
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


def _sportscore_card(row: SportScoreRow) -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.el.div(
                rx.el.span(
                    f"{row['home']} — {row['away']}",
                    class_name="truncate text-sm font-semibold text-white",
                ),
                rx.el.p(
                    row["competition"],
                    class_name="mt-0.5 truncate text-[10px] font-medium text-zinc-600",
                ),
                class_name="min-w-0 flex-1",
            ),
            _source_chip(
                "SportScore",
                "globe",
                "flex w-fit shrink-0 items-center gap-1.5 rounded-full border border-amber-500/40 bg-amber-500/10 px-2 py-0.5 text-amber-300",
            ),
            class_name="flex items-start gap-2 border-b border-zinc-800 px-3.5 py-3",
        ),
        rx.el.div(
            rx.el.div(
                _sportscore_status_pill(row),
                rx.el.span(
                    row["score"],
                    class_name="whitespace-nowrap text-[10px] font-semibold text-zinc-400 tabular-nums",
                ),
                rx.cond(
                    row["has_ht"],
                    rx.el.span(
                        row["ht_label"],
                        class_name="w-fit whitespace-nowrap rounded-full border border-zinc-700 bg-zinc-800/60 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-zinc-300 tabular-nums",
                    ),
                    rx.fragment(),
                ),
                class_name="flex flex-wrap items-center gap-2",
            ),
            rx.el.div(
                rx.el.div(
                    rx.el.span(
                        row["meta_market"],
                        class_name="truncate text-[10px] font-semibold uppercase tracking-wider text-amber-300/80",
                    ),
                    rx.el.p(
                        row["meta_pick"],
                        class_name="mt-0.5 truncate text-sm font-semibold text-white",
                    ),
                    class_name="min-w-0 flex-1",
                ),
                rx.el.span(
                    f"{row['meta_confidence']:.1f}%",
                    class_name="shrink-0 text-sm font-semibold text-amber-300 tabular-nums",
                ),
                class_name="mt-2.5 flex items-end gap-2",
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
                "Без квоти · изведено само од реални статистики (удари во гол, "
                "опасни напади, поседување, тековен резултат).",
                class_name="mt-2 text-[10px] font-medium text-zinc-600",
            ),
            class_name="p-3.5",
        ),
        class_name="w-full min-w-0 rounded-xl border border-zinc-800 bg-zinc-900/50 transition-colors hover:border-zinc-700",
    )


def supplemental_predictions() -> rx.Component:
    """Дополнителни реални предвидувања од Mutating и SportScore.

    Прикажани се САМО непокриени настани со вистински маркети (Mutating) или
    вистински статистики (SportScore). Тие никогаш не се претставуваат како
    BZZ предвидувања — секоја картичка е јасно означена со својот извор.
    """
    return rx.el.div(
        rx.el.div(
            rx.el.div(
                rx.icon("layers", class_name="h-4 w-4 text-blue-400"),
                rx.el.div(
                    rx.el.h3(
                        "Дополнителни извори · Mutating и SportScore",
                        class_name="text-sm font-semibold tracking-tight text-white",
                    ),
                    rx.el.p(
                        f"{MutatingState.unmatched_count} Mutating со реални маркети · {SportScoreState.prediction_count} SportScore со реални статистики · само непокриени од BZZ/Fotmob",
                        class_name="text-xs font-medium text-zinc-500",
                    ),
                    class_name="flex min-w-0 flex-col",
                ),
                class_name="flex min-w-0 items-center gap-3",
            ),
            rx.el.span(
                "Не се BZZ предвидувања",
                class_name="w-fit shrink-0 whitespace-nowrap rounded-full border border-zinc-700 bg-zinc-800/60 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-zinc-400",
            ),
            class_name="flex flex-wrap items-center justify-between gap-3 border-b border-zinc-800 px-4 py-3",
        ),
        rx.el.div(
            rx.cond(
                (
                    MutatingState.unmatched_count
                    + SportScoreState.prediction_count
                )
                > 0,
                rx.el.div(
                    rx.foreach(MutatingState.today_rows, _mutating_card),
                    rx.foreach(
                        SportScoreState.prediction_rows, _sportscore_card
                    ),
                    class_name="grid w-full grid-cols-1 gap-3 lg:grid-cols-2 2xl:grid-cols-3",
                ),
                unavailable_note(
                    "Mutating и SportScore во моментот не даваат непокриени "
                    "настани со реални маркети или статистики"
                ),
            ),
            class_name="p-4",
        ),
        class_name="mt-4 w-full overflow-hidden rounded-xl border border-zinc-800 bg-zinc-900/50",
    )
