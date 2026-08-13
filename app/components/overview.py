import reflex as rx

from app.components.api_status import (
    error_banner,
    loading_skeleton,
    unavailable_note,
)
from app.components.stat_cards import stat_grid
from app.states.bsd_state import BSDState
from app.states.overview_state import LeagueRow, MatchPick, OverviewState


def section_card(
    title: str, subtitle: str, icon: str, *children
) -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.el.div(
                rx.icon(icon, class_name="h-4 w-4 text-blue-400"),
                rx.el.div(
                    rx.el.h2(
                        title,
                        class_name="text-sm font-semibold tracking-tight text-white",
                    ),
                    rx.el.p(
                        subtitle, class_name="text-xs font-medium text-zinc-500"
                    ),
                    class_name="flex flex-col",
                ),
                class_name="flex items-center gap-3",
            ),
            class_name="flex items-center justify-between border-b border-zinc-800 px-4 py-3",
        ),
        rx.el.div(*children, class_name="p-4"),
        class_name="w-full rounded-xl border border-zinc-800 bg-zinc-900/50",
    )


def accuracy_chart() -> rx.Component:
    return rx.cond(
        OverviewState.trend.length() > 0,
        _accuracy_chart_body(),
        unavailable_note(
            "Нема доволно решени натпревари од API-то за пресметка на точност"
        ),
    )


def _accuracy_chart_body() -> rx.Component:
    return rx.el.div(
        rx.recharts.area_chart(
            rx.recharts.cartesian_grid(
                horizontal=True, vertical=False, class_name="opacity-15"
            ),
            rx.recharts.graphing_tooltip(
                content_style={
                    "background": "#09090b",
                    "borderColor": "#27272a",
                    "borderRadius": "8px",
                    "color": "#fafafa",
                    "fontSize": "12px",
                }
            ),
            rx.recharts.area(
                data_key="accuracy",
                stroke="#3b82f6",
                fill="#3b82f6",
                fill_opacity=0.18,
                type_="monotone",
                stroke_width=2,
            ),
            rx.recharts.area(
                data_key="baseline",
                stroke="#52525b",
                fill="#52525b",
                fill_opacity=0.05,
                type_="monotone",
                stroke_width=1,
            ),
            rx.recharts.x_axis(
                data_key="day",
                axis_line=False,
                tick_line=False,
                custom_attrs={"fontSize": "11px", "fill": "#71717a"},
            ),
            rx.recharts.y_axis(
                domain=[40, 90],
                axis_line=False,
                tick_line=False,
                width=32,
                custom_attrs={"fontSize": "11px", "fill": "#71717a"},
            ),
            data=OverviewState.trend,  # само реални, решени натпревари
            width="100%",
            height=260,
            min_width=300,
            margin={"left": 0, "right": 12, "top": 12, "bottom": 0},
        ),
        rx.el.div(
            rx.el.div(
                rx.el.span(class_name="size-2 rounded-full bg-blue-500"),
                rx.el.span(
                    "Точност на моделите",
                    class_name="text-xs font-medium text-zinc-400",
                ),
                class_name="flex items-center gap-2",
            ),
            rx.el.div(
                rx.el.span(class_name="size-2 rounded-full bg-zinc-600"),
                rx.el.span(
                    "Референтна линија",
                    class_name="text-xs font-medium text-zinc-400",
                ),
                class_name="flex items-center gap-2",
            ),
            class_name="mt-3 flex items-center gap-5",
        ),
        class_name="w-full",
    )


def status_badge(status: rx.Var) -> rx.Component:
    return rx.el.span(
        rx.match(
            status,
            ("live", "Во тек"),
            ("finished", "Завршен"),
            ("cancelled", "Откажан"),
            ("postponed", "Одложен"),
            "Денес",
        ),
        class_name=rx.match(
            status,
            (
                "live",
                "w-fit rounded-full border border-blue-500/30 bg-blue-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-blue-300",
            ),
            (
                "finished",
                "w-fit rounded-full border border-zinc-700 bg-zinc-800/60 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-zinc-400",
            ),
            (
                "cancelled",
                "w-fit rounded-full border border-red-500/30 bg-red-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-red-300",
            ),
            (
                "postponed",
                "w-fit rounded-full border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-300",
            ),
            "w-fit rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-emerald-300",
        ),
    )


def source_badge(pick: MatchPick) -> rx.Component:
    return rx.el.span(
        pick["source_label"],
        class_name=rx.match(
            pick["source"],
            (
                "fotmob",
                "w-fit whitespace-nowrap rounded-full border border-blue-500/35 bg-blue-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-blue-300",
            ),
            (
                "mutating",
                "w-fit whitespace-nowrap rounded-full border border-zinc-700 bg-zinc-800/60 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-zinc-400",
            ),
            (
                "sportscore",
                "w-fit whitespace-nowrap rounded-full border border-amber-500/35 bg-amber-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-300",
            ),
            (
                "fudbal91",
                "w-fit whitespace-nowrap rounded-full border border-blue-500/25 bg-blue-500/[0.07] px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-blue-200",
            ),
            "w-fit whitespace-nowrap rounded-full border border-emerald-500/35 bg-emerald-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-emerald-300",
        ),
    )


def pick_row(pick: MatchPick) -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.el.div(
                rx.el.span(
                    pick["kickoff"],
                    class_name="text-xs font-semibold text-zinc-400 tabular-nums",
                ),
                status_badge(pick["status"]),
                source_badge(pick),
                class_name="flex flex-wrap items-center gap-2",
            ),
            rx.el.p(
                f"{pick['home']} — {pick['away']}",
                class_name="mt-1.5 text-sm font-semibold text-white",
            ),
            rx.el.p(
                f"{pick['league']} · {pick['market']}",
                class_name="truncate text-xs font-medium text-zinc-500",
            ),
            class_name="min-w-0 flex-1",
        ),
        rx.el.div(
            rx.el.span(
                pick["pick"],
                class_name="w-fit rounded-lg border border-blue-500/30 bg-blue-500/10 px-2.5 py-1 text-xs font-semibold text-blue-300",
            ),
            rx.el.div(
                rx.el.span(
                    f"{pick['confidence']:.1f}%",
                    class_name="text-sm font-semibold text-white tabular-nums",
                ),
                rx.cond(
                    pick["has_odds"],
                    rx.el.span(
                        f"квота {pick['odds']:.2f}",
                        class_name="text-[11px] font-medium text-zinc-500 tabular-nums",
                    ),
                    rx.el.span(
                        "квота: недостапна",
                        class_name="text-[11px] font-medium text-zinc-600",
                    ),
                ),
                class_name="flex flex-col items-end",
            ),
            class_name="flex items-center gap-3",
        ),
        class_name="flex items-center justify-between gap-3 border-b border-zinc-800/70 py-3 last:border-0",
    )


def _picks_toggle(key: str, label: str) -> rx.Component:
    return rx.el.button(
        label,
        on_click=lambda: OverviewState.set_picks_view(key),
        class_name=rx.cond(
            OverviewState.picks_view == key,
            "flex-1 whitespace-nowrap rounded-md border border-blue-500/40 bg-blue-500/10 px-3 py-1.5 text-[11px] font-semibold text-blue-300 transition-all",
            "flex-1 whitespace-nowrap rounded-md border border-transparent px-3 py-1.5 text-[11px] font-semibold text-zinc-500 transition-all hover:bg-zinc-900 hover:text-zinc-200",
        ),
    )


def top_picks() -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.el.div(
                _picks_toggle("top5", "Топ 5"),
                _picks_toggle("top10", "Топ 10"),
                _picks_toggle("top15", "Топ 15"),
                class_name="flex items-center gap-1 rounded-lg border border-zinc-800 bg-zinc-900/40 p-1",
            ),
            rx.el.span(
                f"Прикажани {OverviewState.top_picks.length()} од {OverviewState.total_picks}",
                class_name="text-[11px] font-medium text-zinc-500 tabular-nums",
            ),
            class_name="mb-2 flex items-center justify-between gap-3",
        ),
        rx.el.div(
            rx.icon("shuffle", class_name="h-3.5 w-3.5 shrink-0 text-blue-400"),
            rx.el.div(
                rx.el.span(
                    OverviewState.top_picks_mix_label,
                    class_name="text-[11px] font-semibold text-zinc-300",
                ),
                rx.el.span(
                    "Изворите се мешаат наизменично (BZZ → Fotmob → Mutating → "
                    "SportScore → Fudbal91), а внатре во секој извор редот е по "
                    "реална сигурност. За Fudbal91 се користи изведена поддршка "
                    "од јавните просечни квоти, не официјална сигурност.",
                    class_name="mt-0.5 text-[11px] font-medium text-zinc-500",
                ),
                class_name="flex min-w-0 flex-col",
            ),
            class_name="mb-2 flex items-start gap-2 rounded-lg border border-zinc-800 bg-zinc-950/60 px-3 py-2",
        ),
        rx.cond(
            OverviewState.top_picks.length() > 0,
            rx.el.div(
                rx.foreach(
                    OverviewState.top_picks,
                    pick_row,
                ),
                class_name="flex flex-col",
            ),
            rx.el.div(
                rx.icon("inbox", class_name="h-6 w-6 text-zinc-600"),
                rx.el.p(
                    "Нема достапни предвидувања",
                    class_name="mt-2 text-sm font-medium text-zinc-500",
                ),
                class_name="flex flex-col items-center justify-center py-10",
            ),
        ),
        class_name="w-full",
    )


def model_bar(label: str, value: rx.Var) -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.el.span(label, class_name="text-xs font-medium text-zinc-300"),
            rx.el.span(
                f"{value:.1f}%",
                class_name="text-xs font-semibold text-white tabular-nums",
            ),
            class_name="flex items-center justify-between",
        ),
        rx.el.div(
            rx.el.div(
                class_name="h-full rounded-full bg-blue-500 transition-all duration-700",
                style={"width": f"{value}%"},
            ),
            class_name="mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-zinc-800",
        ),
        class_name="w-full",
    )


def model_health() -> rx.Component:
    return rx.el.div(
        model_bar("Meta-Ensemble", OverviewState.model_health["meta"]),
        model_bar("BSD ML", OverviewState.model_health["bsd_ml"]),
        model_bar("Bivariate Poisson", OverviewState.model_health["poisson"]),
        model_bar(
            "Консензус (25 модели)", OverviewState.model_health["consensus"]
        ),
        rx.el.div(
            rx.el.div(
                rx.el.span(
                    "Средна предност",
                    class_name="text-[11px] font-semibold uppercase tracking-wider text-zinc-500",
                ),
                rx.el.span(
                    f"{OverviewState.avg_edge:.2f} п.п.",
                    class_name="text-sm font-semibold text-emerald-400 tabular-nums",
                ),
                class_name="flex items-center justify-between",
            ),
            rx.el.div(
                rx.el.span(
                    "Тикети со висока сигурност",
                    class_name="text-[11px] font-semibold uppercase tracking-wider text-zinc-500",
                ),
                rx.el.span(
                    OverviewState.high_confidence_count.to_string(),
                    class_name="text-sm font-semibold text-white tabular-nums",
                ),
                class_name="mt-2 flex items-center justify-between",
            ),
            class_name="mt-4 rounded-lg border border-zinc-800 bg-zinc-950/60 p-3",
        ),
        class_name="flex w-full flex-col gap-4",
    )


def league_row(row: LeagueRow) -> rx.Component:
    return rx.el.tr(
        rx.el.td(
            row["league"],
            class_name="px-3 py-2.5 text-sm font-medium text-zinc-200",
        ),
        rx.el.td(
            row["matches"],
            class_name="px-3 py-2.5 text-right text-sm text-zinc-400 tabular-nums",
        ),
        rx.el.td(
            rx.el.span(
                f"{row['value_picks']}",
                class_name="w-fit rounded-full border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 text-xs font-semibold text-amber-300 tabular-nums",
            ),
            class_name="px-3 py-2.5 text-right",
        ),
        rx.el.td(
            rx.el.div(
                rx.el.span(
                    f"{row['accuracy']:.1f}%",
                    class_name="text-sm font-semibold text-white tabular-nums",
                ),
                rx.el.div(
                    rx.el.div(
                        class_name="h-full rounded-full bg-blue-500",
                        style={"width": f"{row['accuracy']}%"},
                    ),
                    class_name="h-1 w-16 overflow-hidden rounded-full bg-zinc-800",
                ),
                class_name="flex items-center justify-end gap-2",
            ),
            class_name="px-3 py-2.5 text-right",
        ),
        class_name="border-b border-zinc-800/70 transition-colors last:border-0 hover:bg-zinc-800/30",
    )


def league_table() -> rx.Component:
    return rx.el.div(
        rx.el.table(
            rx.el.thead(
                rx.el.tr(
                    rx.el.th(
                        "Лига",
                        class_name="px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-wider text-zinc-500",
                    ),
                    rx.el.th(
                        "Натпревари",
                        class_name="px-3 py-2 text-right text-[11px] font-semibold uppercase tracking-wider text-zinc-500",
                    ),
                    rx.el.th(
                        "Вредност",
                        class_name="px-3 py-2 text-right text-[11px] font-semibold uppercase tracking-wider text-zinc-500",
                    ),
                    rx.el.th(
                        "Точност",
                        class_name="px-3 py-2 text-right text-[11px] font-semibold uppercase tracking-wider text-zinc-500",
                    ),
                ),
                class_name="border-b border-zinc-800 bg-zinc-950/40",
            ),
            rx.el.tbody(rx.foreach(OverviewState.league_rows, league_row)),
            class_name="w-full table-auto",
        ),
        class_name="w-full overflow-hidden rounded-lg border border-zinc-800",
    )


def overview() -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.el.div(
                rx.el.h2(
                    "Преглед на денес",
                    class_name="text-xl font-semibold tracking-tight text-white sm:text-2xl",
                ),
                rx.el.p(
                    f"Вчитано во {OverviewState.generated_at} · BZZ покриеност: избран датум и следниот ден · {OverviewState.total_picks} избори · {OverviewState.bzz_pick_count} BZZ · {OverviewState.fotmob_pick_count} Fotmob · {OverviewState.mutating_pick_count} Mutating · {OverviewState.sportscore_pick_count} SportScore · {OverviewState.fudbal91_pick_count} Fudbal91 · {OverviewState.missing_predictions} настани без предвидување",
                    class_name="mt-1 max-w-3xl text-sm font-medium text-zinc-500",
                ),
                class_name="flex flex-col",
            ),
            class_name="mb-5",
        ),
        error_banner(OverviewState.error),
        rx.cond(
            BSDState.is_loading & ~OverviewState.has_data,
            rx.el.div(
                rx.el.div(
                    rx.icon(
                        "loader-circle",
                        class_name="h-4 w-4 shrink-0 animate-spin text-blue-400",
                    ),
                    rx.el.p(
                        "Примарните BZZ податоци се вчитуваат во заднина · "
                        "интерфејсот е веќе достапен",
                        class_name="text-xs font-medium text-zinc-400",
                    ),
                    class_name="flex w-full items-center gap-3 rounded-xl border border-zinc-800 bg-zinc-900/50 px-4 py-3",
                ),
                loading_skeleton(),
                class_name="mb-4 w-full",
            ),
            rx.fragment(),
        ),
        stat_grid(),
        rx.el.div(
            rx.el.div(
                section_card(
                    "Точност низ неделата",
                    "Meta-Ensemble наспроти референтна линија",
                    "chart-line",
                    accuracy_chart(),
                ),
                class_name="flex-1 min-w-0",
            ),
            rx.el.div(
                section_card(
                    "Здравје на моделите",
                    "Актуелна точност по семејство",
                    "activity",
                    model_health(),
                ),
                class_name="w-full lg:w-80 lg:shrink-0",
            ),
            class_name="mt-4 flex w-full flex-col gap-4 lg:flex-row",
        ),
        rx.el.div(
            rx.el.div(
                section_card(
                    "Најсигурни избори",
                    "Наизменично мешани извори: BZZ, Fotmob, Mutating, SportScore и Fudbal91",
                    "star",
                    top_picks(),
                ),
                class_name="flex-1 min-w-0",
            ),
            rx.el.div(
                section_card(
                    "Успешност по лига",
                    "Последни 30 дена",
                    "trophy",
                    league_table(),
                ),
                class_name="flex-1 min-w-0",
            ),
            class_name="mt-4 flex w-full flex-col gap-4 xl:flex-row",
        ),
        class_name="w-full",
    )
