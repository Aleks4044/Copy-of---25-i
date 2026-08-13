import reflex as rx

from app.components.api_status import error_banner, unavailable_note
from app.states.markets_state import MarketRow, MarketsState


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
                "Комбинирани маркети",
                class_name="text-xl font-semibold tracking-tight text-white sm:text-2xl",
            ),
            rx.el.p(
                f"Вчитано во {MarketsState.generated_at} · {MarketsState.combos_per_match} комбинации по BZZ/Fotmob натпревар, пресметани само од реални веројатности · {MarketsState.missing_predictions} настани без предвидување",
                class_name="mt-1 max-w-3xl text-sm font-medium text-zinc-500",
            ),
            rx.el.p(
                f"Извори: {MarketsState.sources_label} · Mutating, SportScore и Fudbal91 не даваат маркет квоти за изведените редови, па квотата и предноста стојат како „недостапно“ и не се измислуваат",
            ),
            rx.el.p(
                "Fudbal91 редовите се изведени од јавните просечни квоти "
                "(имплицирана поддршка), не од официјална сигурност, и се "
                "прикажани само за настани непокриени од другите извори.",
                class_name="mt-1 max-w-3xl text-xs font-medium text-zinc-600",
            ),
            class_name="flex min-w-0 flex-col",
        ),
        rx.el.div(
            _chip("Маркети", MarketsState.total_count.to_string(), "layers"),
            _chip(
                "По филтер",
                MarketsState.filtered_count.to_string(),
                "list-filter",
            ),
            _chip(
                "Со препорака",
                MarketsState.recommended_count.to_string(),
                "badge-check",
            ),
            _chip(
                "Избор",
                MarketsState.market_filter_label,
                "target",
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
            "Препораки над 40%",
            MarketsState.recommended_count.to_string(),
            f"{MarketsState.strong_count} со силна препорака (≥70%)",
            "badge-check",
            "flex size-8 items-center justify-center rounded-lg border border-blue-500/30 bg-blue-500/10 text-blue-400",
        ),
        _kpi_card(
            "Средна веројатност",
            f"{MarketsState.avg_probability:.1f}%",
            f"Од {MarketsState.filtered_count} филтрирани маркети",
            "gauge",
            "flex size-8 items-center justify-center rounded-lg border border-emerald-500/30 bg-emerald-500/10 text-emerald-400",
        ),
        _kpi_card(
            "Најсилна комбинација",
            f"{MarketsState.best_row_probability:.1f}%",
            MarketsState.best_row_label,
            "crown",
            "flex size-8 items-center justify-center rounded-lg border border-amber-500/30 bg-amber-500/10 text-amber-400",
        ),
        _kpi_card(
            "Со вредност",
            MarketsState.value_count.to_string(),
            "Предност ≥ 3.00 п.п. над квотата",
            "badge-dollar-sign",
            "flex size-8 items-center justify-center rounded-lg border border-blue-500/30 bg-blue-500/10 text-blue-400",
        ),
        class_name="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4",
    )


def _inline_chip(tab: dict[str, str]) -> rx.Component:
    """Еден чип од заедничкиот ред: група или конкретен избор."""
    is_active = rx.cond(
        tab["kind"] == "group",
        MarketsState.group_filter == tab["key"],
        MarketsState.market_filter == tab["key"],
    )
    return rx.el.button(
        rx.el.span(tab["label"], class_name="whitespace-nowrap"),
        rx.el.span(
            tab["count"],
            class_name=rx.cond(
                is_active,
                "rounded-full bg-blue-500/20 px-1.5 text-[10px] font-bold text-blue-200 tabular-nums",
                "rounded-full bg-zinc-800 px-1.5 text-[10px] font-bold text-zinc-400 tabular-nums",
            ),
        ),
        on_click=lambda: MarketsState.apply_inline_filter(tab["key"]),
        class_name=rx.cond(
            is_active,
            "flex shrink-0 items-center justify-center gap-2 rounded-lg border border-blue-500/40 bg-blue-500/10 px-3 py-2 text-xs font-semibold text-blue-300 transition-all sm:text-sm",
            rx.cond(
                tab["kind"] == "market",
                "flex shrink-0 items-center justify-center gap-2 rounded-lg border border-zinc-800 px-3 py-2 text-xs font-semibold text-zinc-500 transition-all hover:bg-zinc-900 hover:text-zinc-200 sm:text-sm",
                "flex shrink-0 items-center justify-center gap-2 rounded-lg border border-transparent px-3 py-2 text-xs font-semibold text-zinc-500 transition-all hover:bg-zinc-900 hover:text-zinc-200 sm:text-sm",
            ),
        ),
    )


def _select(
    options: rx.Component, value: rx.Var, handler: rx.event.EventType
) -> rx.Component:
    return rx.el.div(
        rx.el.select(
            options,
            default_value=value,
            key=value,
            on_change=handler,
            class_name="w-full appearance-none rounded-lg border border-zinc-800 bg-zinc-900/60 px-3 py-2 pr-9 text-xs font-semibold text-zinc-300 outline-hidden transition-colors hover:border-zinc-700 focus:border-blue-500/50 sm:text-sm",
        ),
        rx.icon(
            "chevron-down",
            class_name="pointer-events-none absolute right-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-zinc-500",
        ),
        class_name="relative w-full",
    )


def _controls() -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.foreach(MarketsState.inline_filter_tabs, _inline_chip),
            class_name="flex w-full items-center gap-1 overflow-x-auto rounded-xl border border-zinc-800 bg-zinc-900/40 p-1",
        ),
        rx.el.div(
            _select(
                rx.foreach(
                    MarketsState.match_options,
                    lambda option: rx.el.option(
                        option["label"], value=option["key"]
                    ),
                ),
                MarketsState.match_filter,
                MarketsState.set_match_filter,
            ),
            _select(
                rx.fragment(
                    rx.el.option("Сите статуси", value="all"),
                    rx.el.option("Претстојни (денес и утре)", value="upcoming"),
                    rx.el.option("Во тек", value="live"),
                    rx.el.option("Завршени", value="finished"),
                ),
                MarketsState.status_filter,
                MarketsState.set_status_filter,
            ),
            _select(
                rx.fragment(
                    rx.el.option("Веројатност", value="probability"),
                    rx.el.option("Предност", value="edge"),
                    rx.el.option("Квота", value="odds"),
                    rx.el.option("Натпревар", value="match"),
                    rx.el.option("Маркет", value="market"),
                ),
                MarketsState.sort_key,
                MarketsState.set_sort_key,
            ),
            class_name="grid w-full grid-cols-1 gap-2 sm:grid-cols-3",
        ),
        rx.el.div(
            rx.el.div(
                rx.el.div(
                    rx.el.span(
                        "Мин. веројатност",
                        class_name="text-[11px] font-semibold uppercase tracking-wider text-zinc-500",
                    ),
                    rx.el.span(
                        MarketsState.min_probability_label,
                        class_name="text-xs font-semibold text-blue-300 tabular-nums",
                    ),
                    class_name="flex items-center justify-between gap-3",
                ),
                rx.el.input(
                    type="range",
                    min="0",
                    max="90",
                    step="5",
                    default_value=MarketsState.min_probability.to_string(),
                    on_change=MarketsState.set_min_probability.throttle(300),
                    class_name="mt-2 h-1.5 w-full cursor-pointer appearance-none rounded-full bg-zinc-800 accent-blue-500",
                ),
                class_name="min-w-0 flex-1 rounded-lg border border-zinc-800 bg-zinc-900/50 px-3 py-2",
            ),
            rx.el.button(
                rx.icon(
                    rx.cond(
                        MarketsState.only_recommended, "check-check", "check"
                    ),
                    class_name="h-3.5 w-3.5",
                ),
                rx.el.span("Само препораки", class_name="whitespace-nowrap"),
                on_click=MarketsState.toggle_only_recommended,
                class_name=rx.cond(
                    MarketsState.only_recommended,
                    "flex shrink-0 items-center gap-2 rounded-lg border border-blue-500/40 bg-blue-500/10 px-3 py-2 text-xs font-semibold text-blue-300 transition-colors",
                    "flex shrink-0 items-center gap-2 rounded-lg border border-zinc-800 bg-zinc-900/60 px-3 py-2 text-xs font-semibold text-zinc-400 transition-colors hover:border-zinc-700 hover:text-zinc-200",
                ),
            ),
            rx.el.button(
                rx.icon("rotate-ccw", class_name="h-3.5 w-3.5"),
                rx.el.span("Ресетирај", class_name="whitespace-nowrap"),
                on_click=MarketsState.reset_filters,
                class_name="flex shrink-0 items-center gap-2 rounded-lg border border-zinc-800 bg-zinc-900/60 px-3 py-2 text-xs font-semibold text-zinc-400 transition-colors hover:border-zinc-700 hover:text-zinc-200",
            ),
            class_name="flex w-full flex-col gap-2 sm:flex-row sm:items-center",
        ),
        class_name="mt-4 flex w-full flex-col gap-2",
    )


def _recommendation_badge(row: MarketRow) -> rx.Component:
    return rx.cond(
        row["recommended"],
        rx.el.span(
            row["recommendation"],
            class_name=rx.cond(
                row["probability"] >= 70.0,
                "w-fit whitespace-nowrap rounded-full border border-emerald-500/35 bg-emerald-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-emerald-300",
                rx.cond(
                    row["probability"] >= 55.0,
                    "w-fit whitespace-nowrap rounded-full border border-blue-500/35 bg-blue-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-blue-300",
                    "w-fit whitespace-nowrap rounded-full border border-amber-500/35 bg-amber-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-300",
                ),
            ),
        ),
        rx.el.span(
            "Без препорака",
            class_name="w-fit whitespace-nowrap rounded-full border border-zinc-700 bg-zinc-800/60 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-zinc-500",
        ),
    )


def _probability_cell(row: MarketRow) -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.el.span(
                f"{row['probability']:.1f}%",
                class_name="text-sm font-semibold text-white tabular-nums",
            ),
            class_name="flex justify-end",
        ),
        rx.el.div(
            rx.el.div(
                class_name=rx.cond(
                    row["recommended"],
                    "h-full rounded-full bg-blue-500 transition-all duration-700",
                    "h-full rounded-full bg-zinc-600 transition-all duration-700",
                ),
                style={"width": f"{row['probability']}%"},
            ),
            class_name="ml-auto mt-1.5 h-1.5 w-24 overflow-hidden rounded-full bg-zinc-800 sm:w-32",
        ),
        class_name="flex w-full flex-col items-end",
    )


def _status_dot(row: MarketRow) -> rx.Component:
    return rx.el.span(
        rx.match(
            row["status"],
            ("live", "Во тек"),
            ("finished", "Завршен"),
            row["kickoff"],
        ),
        class_name=rx.match(
            row["status"],
            (
                "live",
                "w-fit whitespace-nowrap rounded-full border border-blue-500/30 bg-blue-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-blue-300",
            ),
            (
                "finished",
                "w-fit whitespace-nowrap rounded-full border border-zinc-700 bg-zinc-800/60 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-zinc-400",
            ),
            "w-fit whitespace-nowrap rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-emerald-300 tabular-nums",
        ),
    )


def _market_row(row: MarketRow) -> rx.Component:
    return rx.el.tr(
        rx.el.td(
            rx.el.div(
                rx.el.span(
                    row["match_label"],
                    class_name="truncate text-sm font-medium text-zinc-100",
                ),
                rx.el.div(
                    rx.el.span(
                        row["league"],
                        class_name="truncate text-[10px] font-medium text-zinc-600",
                    ),
                    _status_dot(row),
                    rx.el.span(
                        row["source_label"],
                        class_name="w-fit whitespace-nowrap rounded-full border border-zinc-700 bg-zinc-800/60 px-2 py-0.5 text-[10px] font-semibold text-zinc-400",
                    ),
                    class_name="mt-0.5 flex flex-wrap items-center gap-2",
                ),
                class_name="flex min-w-0 flex-col",
            ),
            class_name="px-3 py-2.5",
        ),
        rx.el.td(
            rx.el.div(
                rx.el.span(
                    row["label"],
                    class_name="truncate text-sm font-semibold text-white",
                ),
                rx.el.span(
                    row["group_label"],
                    class_name="mt-0.5 truncate text-[10px] font-medium text-zinc-600 sm:hidden",
                ),
                class_name="flex min-w-0 flex-col",
            ),
            class_name="px-3 py-2.5",
        ),
        rx.el.td(
            rx.el.span(
                row["group_label"],
                class_name="w-fit whitespace-nowrap rounded-full border border-zinc-700 bg-zinc-800/60 px-2 py-0.5 text-[10px] font-semibold text-zinc-400",
            ),
            class_name="hidden px-3 py-2.5 sm:table-cell",
        ),
        rx.el.td(
            _probability_cell(row),
            class_name="px-3 py-2.5",
        ),
        rx.el.td(
            rx.cond(
                row["has_odds"],
                rx.el.span(
                    f"{row['odds']:.2f}",
                    class_name="text-sm text-zinc-300 tabular-nums",
                ),
                rx.el.span(
                    "недостапно",
                    class_name="text-[10px] font-medium text-zinc-600",
                ),
            ),
            class_name="hidden px-3 py-2.5 text-right md:table-cell",
        ),
        rx.el.td(
            rx.cond(
                row["has_odds"],
                rx.el.span(
                    f"{row['edge']:.2f} п.п.",
                    class_name=rx.cond(
                        row["edge"] >= 0.0,
                        "w-fit whitespace-nowrap rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-xs font-semibold text-emerald-300 tabular-nums",
                        "w-fit whitespace-nowrap rounded-full border border-zinc-700 bg-zinc-800/60 px-2 py-0.5 text-xs font-semibold text-zinc-400 tabular-nums",
                    ),
                ),
                rx.el.span(
                    "недостапно",
                    class_name="text-[10px] font-medium text-zinc-600",
                ),
            ),
            class_name="hidden px-3 py-2.5 text-right lg:table-cell",
        ),
        rx.el.td(
            _recommendation_badge(row),
            class_name="px-3 py-2.5 text-right",
        ),
        class_name="border-b border-zinc-800/70 transition-colors last:border-0 hover:bg-zinc-800/30",
    )


def _th(label: str, extra: str) -> rx.Component:
    return rx.el.th(label, class_name=extra)


def _markets_table() -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.icon("layers", class_name="h-4 w-4 text-blue-400"),
            rx.el.div(
                rx.el.h3(
                    "Сите комбинирани маркети",
                    class_name="text-sm font-semibold tracking-tight text-white",
                ),
                rx.el.p(
                    f"Прикажани {MarketsState.visible_count} од {MarketsState.filtered_count} филтрирани маркети · {MarketsState.without_odds_count} без објавена квота",
                    class_name="text-xs font-medium text-zinc-500",
                ),
                class_name="flex min-w-0 flex-col",
            ),
            class_name="flex items-center gap-3 border-b border-zinc-800 px-4 py-3",
        ),
        rx.cond(
            MarketsState.visible_count > 0,
            rx.el.div(
                rx.el.div(
                    rx.el.table(
                        rx.el.thead(
                            rx.el.tr(
                                _th(
                                    "Натпревар",
                                    "px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-wider text-zinc-500",
                                ),
                                _th(
                                    "Маркет",
                                    "px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-wider text-zinc-500",
                                ),
                                _th(
                                    "Група",
                                    "hidden px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-wider text-zinc-500 sm:table-cell",
                                ),
                                _th(
                                    "Веројатност",
                                    "px-3 py-2 text-right text-[11px] font-semibold uppercase tracking-wider text-zinc-500",
                                ),
                                _th(
                                    "Квота",
                                    "hidden px-3 py-2 text-right text-[11px] font-semibold uppercase tracking-wider text-zinc-500 md:table-cell",
                                ),
                                _th(
                                    "Предност",
                                    "hidden px-3 py-2 text-right text-[11px] font-semibold uppercase tracking-wider text-zinc-500 lg:table-cell",
                                ),
                                _th(
                                    "Препорака",
                                    "px-3 py-2 text-right text-[11px] font-semibold uppercase tracking-wider text-zinc-500",
                                ),
                            ),
                            class_name="border-b border-zinc-800 bg-zinc-950/40",
                        ),
                        rx.el.tbody(
                            rx.foreach(MarketsState.visible_rows, _market_row)
                        ),
                        class_name="w-full table-auto",
                    ),
                    class_name="w-full overflow-x-auto",
                ),
                rx.cond(
                    MarketsState.is_truncated,
                    rx.el.p(
                        "Стеснете ги филтрите за да ги видите останатите маркети",
                        class_name="mt-3 text-center text-[11px] font-medium text-zinc-600",
                    ),
                    rx.fragment(),
                ),
                class_name="p-4",
            ),
            rx.el.div(
                rx.icon("filter-x", class_name="h-6 w-6 text-zinc-600"),
                rx.el.p(
                    "Нема маркети што ги задоволуваат филтрите",
                    class_name="mt-2 text-sm font-medium text-zinc-500",
                ),
                class_name="flex flex-col items-center justify-center py-14",
            ),
        ),
        class_name="w-full overflow-hidden rounded-xl border border-zinc-800 bg-zinc-900/50",
    )


def _group_summary_row(row: dict[str, str]) -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.el.span(
                row["label"],
                class_name="truncate text-xs font-semibold text-white",
            ),
            rx.el.span(
                row["avg"],
                class_name="text-xs font-semibold text-blue-300 tabular-nums",
            ),
            class_name="flex items-center justify-between gap-3",
        ),
        rx.el.div(
            rx.el.div(
                class_name="h-full rounded-full bg-blue-500 transition-all duration-700",
                style={"width": row["avg_width"]},
            ),
            class_name="mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-zinc-800",
        ),
        rx.el.div(
            rx.el.span(
                f"{row['count']} маркети · {row['recommended']} препораки",
                class_name="truncate text-[10px] font-medium text-zinc-500",
            ),
            rx.el.span(
                f"{row['best_label']} {row['best_probability']}",
                class_name="truncate text-[10px] font-medium text-zinc-500 tabular-nums",
            ),
            class_name="mt-1.5 flex items-center justify-between gap-3",
        ),
        class_name="w-full min-w-0 border-b border-zinc-800/70 py-2.5 last:border-0",
    )


def _group_summaries() -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.icon("chart-bar", class_name="h-4 w-4 text-blue-400"),
            rx.el.div(
                rx.el.h3(
                    "Статистика по група",
                    class_name="text-sm font-semibold tracking-tight text-white",
                ),
                rx.el.p(
                    "Средна веројатност и препораки",
                    class_name="text-xs font-medium text-zinc-500",
                ),
                class_name="flex flex-col",
            ),
            class_name="flex items-center gap-3 border-b border-zinc-800 px-4 py-3",
        ),
        rx.cond(
            MarketsState.group_summaries.length() > 0,
            rx.el.div(
                rx.foreach(MarketsState.group_summaries, _group_summary_row),
                class_name="flex flex-col px-4 py-2",
            ),
            rx.el.p(
                "Нема податоци за избраните филтри",
                class_name="px-4 py-8 text-center text-sm font-medium text-zinc-500",
            ),
        ),
        class_name="w-full rounded-xl border border-zinc-800 bg-zinc-900/50",
    )


def markets_view() -> rx.Component:
    return rx.el.div(
        _header(),
        error_banner(MarketsState.error),
        rx.cond(
            MarketsState.has_data,
            rx.el.div(
                _kpi_grid(),
                _controls(),
                rx.el.div(
                    rx.el.div(_markets_table(), class_name="min-w-0 flex-1"),
                    rx.el.div(
                        _group_summaries(),
                        class_name="w-full lg:w-80 lg:shrink-0",
                    ),
                    class_name="mt-4 flex w-full flex-col gap-4 lg:flex-row",
                ),
                class_name="w-full",
            ),
            unavailable_note(
                "Ниту еден извор (BZZ, Fotmob, Mutating, SportScore, Fudbal91) не врати "
                "реални веројатности, па комбинираните маркети не можат да се "
                "пресметаат"
            ),
        ),
        class_name="w-full",
    )
