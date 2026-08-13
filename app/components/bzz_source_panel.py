import reflex as rx

from app.components.api_status import unavailable_note
from app.states.bsd_state import BSDMatch
from app.states.bzz_source_state import BzzSourceState
from app.states.bzz_sources import EndpointRow, SourcePanel


def _status_chip(row: EndpointRow) -> rx.Component:
    return rx.el.span(
        row["status_label"],
        class_name=rx.match(
            row["status_kind"],
            (
                "ok",
                "w-fit whitespace-nowrap rounded-full border border-emerald-500/35 bg-emerald-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-emerald-300 tabular-nums",
            ),
            (
                "limited",
                "w-fit whitespace-nowrap rounded-full border border-amber-500/35 bg-amber-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-300 tabular-nums",
            ),
            (
                "error",
                "w-fit whitespace-nowrap rounded-full border border-red-500/35 bg-red-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-red-300 tabular-nums",
            ),
            "w-fit whitespace-nowrap rounded-full border border-zinc-700 bg-zinc-800/60 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-zinc-400 tabular-nums",
        ),
    )


def _fact_row(fact: rx.Var) -> rx.Component:
    return rx.el.div(
        rx.icon(
            "chart-no-axes-column",
            class_name="mt-0.5 h-3 w-3 shrink-0 text-zinc-500",
        ),
        rx.el.span(
            fact,
            class_name="min-w-0 break-words text-[11px] font-medium text-zinc-400",
        ),
        class_name="flex items-start gap-2",
    )


def _endpoint_row(row: EndpointRow) -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.el.div(
                rx.el.span(
                    row["label"],
                    class_name="text-xs font-semibold text-white",
                ),
                rx.el.span(
                    row["path"],
                    class_name="truncate text-[10px] font-medium text-zinc-600",
                ),
                class_name="flex min-w-0 flex-col",
            ),
            _status_chip(row),
            class_name="flex flex-wrap items-center justify-between gap-2",
        ),
        rx.el.p(
            row["capability"],
            class_name="mt-1 text-[10px] font-medium text-zinc-600",
        ),
        rx.cond(
            row["available"],
            rx.el.div(
                rx.foreach(row["facts"], _fact_row),
                class_name="mt-2 flex flex-col gap-1.5",
            ),
            rx.el.p(
                "Недостапно · нема реални полиња од овој ресурс, па ништо не "
                "се пресметува и ништо не се измислува.",
                class_name="mt-2 text-[10px] font-medium text-zinc-500",
            ),
        ),
        class_name=rx.cond(
            row["available"],
            "w-full min-w-0 rounded-lg border border-zinc-800 bg-zinc-950/60 px-2.5 py-2",
            "w-full min-w-0 rounded-lg border border-dashed border-zinc-800 bg-zinc-950/40 px-2.5 py-2",
        ),
    )


def _panel_body(panel: SourcePanel) -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.el.span(
                f"{panel['available_count']} од {panel['total_count']} ресурси вратија податоци",
                class_name="text-[10px] font-semibold uppercase tracking-wider text-zinc-500",
            ),
            rx.el.span(
                f"прочитано {panel['fetched_at']}",
                class_name="whitespace-nowrap text-[10px] font-medium text-zinc-500 tabular-nums",
            ),
            class_name="flex flex-wrap items-center justify-between gap-2",
        ),
        rx.el.div(
            rx.foreach(panel["endpoints"], _endpoint_row),
            class_name="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-2",
        ),
        rx.el.p(
            panel["note"],
            class_name="mt-2 text-[10px] font-medium text-zinc-600",
        ),
        rx.el.button(
            rx.icon("refresh-cw", class_name="h-3 w-3"),
            rx.el.span("Повторно прочитај изворите"),
            on_click=lambda: BzzSourceState.reload(panel["match_id"]),
            class_name="mt-2 flex w-fit items-center gap-1.5 rounded-lg border border-zinc-800 bg-zinc-950/50 px-2.5 py-1.5 text-[10px] font-semibold text-zinc-400 transition-colors hover:border-zinc-700 hover:text-white",
        ),
        class_name="mt-2.5 w-full min-w-0",
    )


def _loading() -> rx.Component:
    return rx.el.div(
        rx.el.div(
            class_name="h-16 w-full animate-pulse rounded-lg border border-zinc-800 bg-zinc-950/60"
        ),
        rx.el.div(
            class_name="h-16 w-full animate-pulse rounded-lg border border-zinc-800 bg-zinc-950/60"
        ),
        class_name="mt-2.5 grid w-full grid-cols-1 gap-2 sm:grid-cols-2",
    )


def _panel(match: BSDMatch) -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.el.div(
                rx.icon("database", class_name="h-3.5 w-3.5"),
                rx.el.span(
                    "BZZ извори по настан",
                    class_name="text-[11px] font-semibold uppercase tracking-wider",
                ),
                class_name="flex w-fit items-center gap-1.5 rounded-md border border-emerald-500/30 bg-emerald-500/10 px-2 py-1 text-emerald-300",
            ),
            rx.el.span(
                f"#{match['event_id']}",
                class_name="whitespace-nowrap text-[10px] font-medium text-zinc-600 tabular-nums",
            ),
            class_name="flex flex-wrap items-center justify-between gap-2",
        ),
        rx.el.p(
            "Summary · Lineups · Prediction · Odds · Money · Stats · H2H — "
            "точно она што автентицираните ресурси на овој настан го вратија.",
            class_name="mt-1.5 text-[10px] font-medium text-zinc-600",
        ),
        rx.cond(
            BzzSourceState.open_ids.contains(match["id"]),
            rx.cond(
                BzzSourceState.loading_ids.contains(match["id"]),
                _loading(),
                rx.cond(
                    BzzSourceState.loaded_ids.contains(match["id"]),
                    rx.foreach(
                        BzzSourceState.panels,
                        lambda panel: rx.cond(
                            panel["match_id"] == match["id"],
                            _panel_body(panel),
                            rx.fragment(),
                        ),
                    ),
                    rx.el.div(
                        unavailable_note(
                            "Подресурсите за овој настан не можеа да се "
                            "прочитаат (нема ID, нема клуч или API-то "
                            "ограничи барањата)."
                        ),
                        class_name="mt-2.5 w-full",
                    ),
                ),
            ),
            rx.fragment(),
        ),
        rx.el.button(
            rx.cond(
                BzzSourceState.open_ids.contains(match["id"]),
                rx.el.span("Сокрий детали за изворот"),
                rx.el.span("Прикажи што вратија BZZ ресурсите"),
            ),
            rx.icon(
                "chevron-down",
                class_name=rx.cond(
                    BzzSourceState.open_ids.contains(match["id"]),
                    "h-3.5 w-3.5 rotate-180 transition-transform",
                    "h-3.5 w-3.5 transition-transform",
                ),
            ),
            on_click=lambda: BzzSourceState.toggle(match["id"]),
            class_name="mt-2.5 flex w-full items-center justify-center gap-2 rounded-lg border border-zinc-800 bg-zinc-950/50 px-3 py-2 text-xs font-semibold text-zinc-400 transition-colors hover:border-zinc-700 hover:text-white",
        ),
        class_name="mt-3 w-full min-w-0 rounded-lg border border-zinc-800 bg-zinc-900/40 p-3.5",
    )


def bzz_source_section(match: BSDMatch) -> rx.Component:
    """Панел со детали за изворот — само за настани без официјално
    предвидување/статистика или каде што е употребен резервен извор.
    """
    return rx.cond(
        (~match["has_prediction"])
        | (match["source"] == "bzz_derived")
        | (match["source"] == "fotmob"),
        _panel(match),
        rx.fragment(),
    )
