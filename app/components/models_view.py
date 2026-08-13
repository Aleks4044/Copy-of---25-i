import reflex as rx

from app.states.predictions import BacktestWeek
from app.states.models_state import (
    BacktestPoint,
    FamilySummary,
    ModelRow,
    ModelsState,
)


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
                "25 Модели",
                class_name="text-xl font-semibold tracking-tight text-white sm:text-2xl",
            ),
            rx.el.p(
                f"Генерирано во {ModelsState.generated_at} · 16 BiPoisson ρ варијанти, 4 ELO корекции, 2 Dixon-Coles адаптации и 3 Moving Average xG модели",
                class_name="mt-1 max-w-3xl text-sm font-medium text-zinc-500",
            ),
            class_name="flex min-w-0 flex-col",
        ),
        rx.el.div(
            _chip("Модели", ModelsState.total_count.to_string(), "brain"),
            _chip(
                "Средна точност", f"{ModelsState.avg_accuracy:.1f}%", "gauge"
            ),
            _chip(
                "Над Meta",
                ModelsState.above_meta_count.to_string(),
                "trending-up",
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
        rx.el.p(hint, class_name="mt-1 text-xs font-medium text-zinc-500"),
        class_name="w-full rounded-xl border border-zinc-800 bg-zinc-900/50 p-4 transition-colors hover:border-zinc-700",
    )


def _kpi_grid() -> rx.Component:
    return rx.el.div(
        _kpi_card(
            "Meta-Ensemble точност",
            f"{ModelsState.meta['global_accuracy']:.1f}%",
            f"Предност: {ModelsState.meta['edge']:.2f} п.п. над просекот",
            "crown",
            "flex size-8 items-center justify-center rounded-lg border border-amber-500/30 bg-amber-500/10 text-amber-400",
        ),
        _kpi_card(
            "Најдобар поединечен",
            f"{ModelsState.best_model_accuracy:.1f}%",
            ModelsState.best_model_name,
            "award",
            "flex size-8 items-center justify-center rounded-lg border border-blue-500/30 bg-blue-500/10 text-blue-400",
        ),
        _kpi_card(
            "Денешна успешност",
            f"{ModelsState.avg_today_accuracy:.1f}%",
            f"Просек од {ModelsState.total_count} модели · {ModelsState.today_total} решени натпревари",
            "calendar-check",
            "flex size-8 items-center justify-center rounded-lg border border-emerald-500/30 bg-emerald-500/10 text-emerald-400",
        ),
        _kpi_card(
            "Meta денес",
            f"{ModelsState.meta['today_accuracy']:.1f}%",
            f"{ModelsState.meta['today_correct']:.0f} од {ModelsState.meta['today_total']:.0f} точни",
            "target",
            "flex size-8 items-center justify-center rounded-lg border border-blue-500/30 bg-blue-500/10 text-blue-400",
        ),
        class_name="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4",
    )


def _family_tab(tab: dict[str, str]) -> rx.Component:
    return rx.el.button(
        rx.el.span(tab["label"], class_name="whitespace-nowrap"),
        rx.el.span(
            tab["count"],
            class_name=rx.cond(
                ModelsState.family_filter == tab["key"],
                "rounded-full bg-blue-500/20 px-1.5 text-[10px] font-bold text-blue-200 tabular-nums",
                "rounded-full bg-zinc-800 px-1.5 text-[10px] font-bold text-zinc-400 tabular-nums",
            ),
        ),
        on_click=lambda: ModelsState.set_family_filter(tab["key"]),
        class_name=rx.cond(
            ModelsState.family_filter == tab["key"],
            "flex flex-1 items-center justify-center gap-2 rounded-lg border border-blue-500/40 bg-blue-500/10 px-3 py-2 text-xs font-semibold text-blue-300 transition-all sm:text-sm",
            "flex flex-1 items-center justify-center gap-2 rounded-lg border border-transparent px-3 py-2 text-xs font-semibold text-zinc-500 transition-all hover:bg-zinc-900 hover:text-zinc-200 sm:text-sm",
        ),
    )


def _controls() -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.foreach(ModelsState.family_tabs, _family_tab),
            class_name="flex min-w-0 flex-1 items-center gap-1 overflow-x-auto rounded-xl border border-zinc-800 bg-zinc-900/40 p-1",
        ),
        rx.el.div(
            rx.el.select(
                rx.el.option("Точност (глобална)", value="accuracy"),
                rx.el.option("Денешна успешност", value="today"),
                rx.el.option("ROI", value="roi"),
                rx.el.option("Име", value="name"),
                default_value=ModelsState.sort_key,
                on_change=ModelsState.set_sort_key,
                class_name="w-full appearance-none rounded-lg border border-zinc-800 bg-zinc-900/60 px-3 py-2 pr-9 text-xs font-semibold text-zinc-300 outline-hidden transition-colors hover:border-zinc-700 focus:border-blue-500/50 sm:text-sm",
            ),
            rx.icon(
                "chevron-down",
                class_name="pointer-events-none absolute right-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-zinc-500",
            ),
            class_name="relative w-full sm:w-56",
        ),
        class_name="flex w-full flex-col gap-2 sm:flex-row sm:items-center",
    )


def _metric(label: str, value: rx.Var | str) -> rx.Component:
    return rx.el.div(
        rx.el.span(
            label,
            class_name="text-[10px] font-semibold uppercase tracking-wider text-zinc-500",
        ),
        rx.el.span(
            value,
            class_name="mt-0.5 text-sm font-semibold text-white tabular-nums",
        ),
        class_name="flex w-full flex-col rounded-lg border border-zinc-800 bg-zinc-950/60 px-2.5 py-2",
    )


def _trend_icon(trend: rx.Var) -> rx.Component:
    return rx.match(
        trend,
        (
            "up",
            rx.icon("trending-up", class_name="h-3.5 w-3.5 text-emerald-400"),
        ),
        (
            "down",
            rx.icon("trending-down", class_name="h-3.5 w-3.5 text-red-400"),
        ),
        rx.icon("minus", class_name="h-3.5 w-3.5 text-zinc-500"),
    )


def _model_card(model: ModelRow) -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.el.div(
                rx.el.p(
                    model["name"],
                    class_name="truncate text-sm font-semibold text-white",
                ),
                rx.el.p(
                    model["params"],
                    class_name="mt-0.5 truncate text-[11px] font-medium text-zinc-500",
                ),
                class_name="min-w-0 flex-1",
            ),
            rx.el.div(
                _trend_icon(model["trend"]),
                rx.el.span(
                    model["family"],
                    class_name="whitespace-nowrap rounded-full border border-zinc-700 bg-zinc-800/60 px-2 py-0.5 text-[10px] font-semibold text-zinc-400",
                ),
                class_name="flex shrink-0 items-center gap-2",
            ),
            class_name="flex items-start gap-3",
        ),
        rx.el.div(
            rx.el.div(
                rx.el.span(
                    "Глобална точност",
                    class_name="text-[11px] font-medium text-zinc-400",
                ),
                rx.el.span(
                    f"{model['global_accuracy']:.1f}%",
                    class_name="text-xs font-semibold text-white tabular-nums",
                ),
                class_name="flex items-center justify-between gap-3",
            ),
            rx.el.div(
                rx.el.div(
                    class_name="h-full rounded-full bg-blue-500 transition-all duration-700",
                    style={"width": f"{model['global_accuracy']}%"},
                ),
                class_name="mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-zinc-800",
            ),
            class_name="mt-3 w-full",
        ),
        rx.el.div(
            rx.el.div(
                rx.el.span(
                    "Денес",
                    class_name="text-[11px] font-medium text-zinc-400",
                ),
                rx.el.span(
                    f"{model['today_correct']}/{model['today_total']} · {model['today_accuracy']:.1f}%",
                    class_name=rx.cond(
                        model["today_accuracy"] >= 60.0,
                        "text-xs font-semibold text-emerald-400 tabular-nums",
                        "text-xs font-semibold text-amber-400 tabular-nums",
                    ),
                ),
                class_name="flex items-center justify-between gap-3",
            ),
            rx.el.div(
                rx.el.div(
                    class_name="h-full rounded-full bg-emerald-500/80 transition-all duration-700",
                    style={"width": f"{model['today_accuracy']}%"},
                ),
                class_name="mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-zinc-800",
            ),
            class_name="mt-2.5 w-full",
        ),
        rx.el.div(
            _metric("1X2", f"{model['acc_1x2']:.1f}%"),
            _metric("ГГ", f"{model['acc_btts']:.1f}%"),
            _metric("Над 2.5", f"{model['acc_over25']:.1f}%"),
            class_name="mt-3 grid grid-cols-3 gap-2",
        ),
        rx.el.div(
            rx.el.span(
                f"Log-loss {model['log_loss']:.3f}",
                class_name="text-[10px] font-medium text-zinc-500 tabular-nums",
            ),
            rx.el.span(
                f"Brier {model['brier']:.3f}",
                class_name="text-[10px] font-medium text-zinc-500 tabular-nums",
            ),
            rx.el.span(
                f"ROI {model['roi']:.2f}%",
                class_name=rx.cond(
                    model["roi"] >= 0.0,
                    "text-[10px] font-semibold text-emerald-400 tabular-nums",
                    "text-[10px] font-semibold text-red-400 tabular-nums",
                ),
            ),
            class_name="mt-3 flex flex-wrap items-center justify-between gap-2 border-t border-zinc-800 pt-2.5",
        ),
        class_name="w-full min-w-0 rounded-xl border border-zinc-800 bg-zinc-900/50 p-3.5 transition-colors hover:border-zinc-700",
    )


def _family_row(row: FamilySummary) -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.el.p(
                row["label"],
                class_name="truncate text-xs font-semibold text-white",
            ),
            rx.el.p(
                f"{row['count']} модели · најдобар: {row['best_name']}",
                class_name="truncate text-[11px] font-medium text-zinc-500",
            ),
            class_name="min-w-0 flex-1",
        ),
        rx.el.div(
            rx.el.span(
                f"{row['avg_accuracy']:.1f}%",
                class_name="text-sm font-semibold text-white tabular-nums",
            ),
            rx.el.span(
                f"денес {row['avg_today']:.1f}%",
                class_name="text-[10px] font-medium text-zinc-500 tabular-nums",
            ),
            class_name="flex shrink-0 flex-col items-end",
        ),
        class_name="flex items-center justify-between gap-3 border-b border-zinc-800/70 py-2.5 last:border-0",
    )


def _families_card() -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.icon("layers", class_name="h-4 w-4 text-blue-400"),
            rx.el.div(
                rx.el.h3(
                    "Семејства на модели",
                    class_name="text-sm font-semibold tracking-tight text-white",
                ),
                rx.el.p(
                    "Средна точност по семејство",
                    class_name="text-xs font-medium text-zinc-500",
                ),
                class_name="flex flex-col",
            ),
            class_name="flex items-center gap-3 border-b border-zinc-800 px-4 py-3",
        ),
        rx.el.div(
            rx.foreach(ModelsState.family_summaries, _family_row),
            class_name="flex flex-col px-4 py-2",
        ),
        class_name="w-full rounded-xl border border-zinc-800 bg-zinc-900/50",
    )


def _backtest_chart() -> rx.Component:
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
                data_key="meta",
                stroke="#f59e0b",
                fill="#f59e0b",
                fill_opacity=0.16,
                type_="monotone",
                stroke_width=2,
            ),
            rx.recharts.area(
                data_key="best",
                stroke="#3b82f6",
                fill="#3b82f6",
                fill_opacity=0.12,
                type_="monotone",
                stroke_width=2,
            ),
            rx.recharts.area(
                data_key="average",
                stroke="#52525b",
                fill="#52525b",
                fill_opacity=0.06,
                type_="monotone",
                stroke_width=1,
            ),
            rx.recharts.x_axis(
                data_key="week",
                axis_line=False,
                tick_line=False,
                custom_attrs={"fontSize": "11px", "fill": "#71717a"},
            ),
            rx.recharts.y_axis(
                domain=[50, 90],
                axis_line=False,
                tick_line=False,
                width=32,
                custom_attrs={"fontSize": "11px", "fill": "#71717a"},
            ),
            data=ModelsState.backtest,
            width="100%",
            height=250,
            min_width=300,
            margin={"left": 0, "right": 12, "top": 12, "bottom": 0},
        ),
        rx.el.div(
            rx.el.div(
                rx.el.span(class_name="size-2 rounded-full bg-amber-500"),
                rx.el.span(
                    "Meta-Ensemble",
                    class_name="text-xs font-medium text-zinc-400",
                ),
                class_name="flex items-center gap-2",
            ),
            rx.el.div(
                rx.el.span(class_name="size-2 rounded-full bg-blue-500"),
                rx.el.span(
                    "Најдобар поединечен",
                    class_name="text-xs font-medium text-zinc-400",
                ),
                class_name="flex items-center gap-2",
            ),
            rx.el.div(
                rx.el.span(class_name="size-2 rounded-full bg-zinc-600"),
                rx.el.span(
                    "Просек од 25 модели",
                    class_name="text-xs font-medium text-zinc-400",
                ),
                class_name="flex items-center gap-2",
            ),
            class_name="mt-3 flex flex-wrap items-center gap-4",
        ),
        class_name="w-full",
    )


def _meta_stat(label: str, value: rx.Var | str) -> rx.Component:
    return rx.el.div(
        rx.el.span(
            label,
            class_name="text-[10px] font-semibold uppercase tracking-wider text-zinc-500",
        ),
        rx.el.span(
            value,
            class_name="mt-0.5 text-sm font-semibold text-white tabular-nums",
        ),
        class_name="flex w-full flex-col rounded-lg border border-zinc-800 bg-zinc-950/60 px-3 py-2",
    )


def _meta_panel() -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.icon("crown", class_name="h-4 w-4 text-amber-400"),
            rx.el.div(
                rx.el.h3(
                    "Meta-Ensemble · бектестирање",
                    class_name="text-sm font-semibold tracking-tight text-white",
                ),
                rx.el.p(
                    "Последни 12 недели наспроти поединечни модели",
                    class_name="text-xs font-medium text-zinc-500",
                ),
                class_name="flex flex-col",
            ),
            class_name="flex items-center gap-3 border-b border-zinc-800 px-4 py-3",
        ),
        rx.el.div(
            _backtest_chart(),
            rx.el.div(
                _meta_stat("1X2", f"{ModelsState.meta['acc_1x2']:.1f}%"),
                _meta_stat("ГГ", f"{ModelsState.meta['acc_btts']:.1f}%"),
                _meta_stat("Над 2.5", f"{ModelsState.meta['acc_over25']:.1f}%"),
                _meta_stat("Log-loss", f"{ModelsState.meta['log_loss']:.3f}"),
                _meta_stat("Brier", f"{ModelsState.meta['brier']:.3f}"),
                _meta_stat("ROI", f"{ModelsState.meta['roi']:.2f}%"),
                class_name="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-3",
            ),
            rx.el.div(
                rx.el.div(
                    rx.el.span(
                        "Победи над поединечни модели",
                        class_name="text-[11px] font-semibold uppercase tracking-wider text-zinc-500",
                    ),
                    rx.el.span(
                        f"{ModelsState.meta_wins} од {ModelsState.total_count}",
                        class_name="text-sm font-semibold text-amber-300 tabular-nums",
                    ),
                    class_name="flex items-center justify-between gap-3",
                ),
                rx.el.div(
                    rx.el.span(
                        "Обем на бектест",
                        class_name="text-[11px] font-semibold uppercase tracking-wider text-zinc-500",
                    ),
                    rx.el.span(
                        f"{ModelsState.meta['sample']:.0f} натпревари",
                        class_name="text-sm font-semibold text-white tabular-nums",
                    ),
                    class_name="mt-2 flex items-center justify-between gap-3",
                ),
                class_name="mt-3 rounded-lg border border-amber-500/25 bg-amber-500/[0.04] p-3",
            ),
            class_name="p-4",
        ),
        class_name="w-full rounded-xl border border-zinc-800 bg-zinc-900/50",
    )


def _stacking_metric(label: str, value: rx.Var | str) -> rx.Component:
    return rx.el.div(
        rx.el.span(
            label,
            class_name="text-[10px] font-semibold uppercase tracking-wider text-zinc-500",
        ),
        rx.el.span(
            value,
            class_name="mt-0.5 text-sm font-semibold text-white tabular-nums",
        ),
        class_name="flex w-full min-w-0 flex-col rounded-lg border border-zinc-800 bg-zinc-950/60 px-3 py-2",
    )


def _stacking_week(row: BacktestWeek) -> rx.Component:
    return rx.el.div(
        rx.el.span(
            row["week"],
            class_name="w-10 shrink-0 text-[10px] font-semibold text-zinc-500 tabular-nums",
        ),
        rx.el.div(
            rx.el.div(
                class_name="h-full rounded-full bg-blue-500 transition-all duration-700",
                style={"width": f"{row['accuracy']}%"},
            ),
            class_name="h-1.5 min-w-0 flex-1 overflow-hidden rounded-full bg-zinc-800",
        ),
        rx.el.span(
            f"{row['accuracy']:.1f}%",
            class_name="w-14 shrink-0 text-right text-[10px] font-semibold text-zinc-300 tabular-nums",
        ),
        rx.el.span(
            f"ROI {row['roi']:.2f}%",
            class_name="hidden w-20 shrink-0 text-right text-[10px] font-medium text-zinc-500 tabular-nums sm:block",
        ),
        class_name="flex items-center gap-2",
    )


def stacking_meta_card() -> rx.Component:
    """XGBoost + Stacking картичка веднаш до постоечкиот Meta-Ensemble панел."""
    return rx.el.div(
        rx.el.div(
            rx.el.div(
                rx.icon("boxes", class_name="h-4 w-4 text-blue-400"),
                rx.el.div(
                    rx.el.h3(
                        "XGBoost + Stacking",
                        class_name="text-sm font-semibold tracking-tight text-white",
                    ),
                    rx.el.p(
                        f"Stacking врз излезите од {ModelsState.total_count} модели · {ModelsState.stacking_rows} редови · {ModelsState.stacking_predictions} 1X2 · {ModelsState.stacking_market_count} дополнителни маркети · ажурирано {ModelsState.stacking_updated_at}",
                        class_name="text-xs font-medium text-zinc-500",
                    ),
                    class_name="flex min-w-0 flex-col",
                ),
                class_name="flex min-w-0 items-center gap-3",
            ),
            rx.el.button(
                rx.icon(
                    "refresh-cw",
                    class_name=rx.cond(
                        ModelsState.stacking_is_loading,
                        "h-3.5 w-3.5 animate-spin",
                        "h-3.5 w-3.5",
                    ),
                ),
                rx.el.span("Освежи модел", class_name="whitespace-nowrap"),
                on_click=ModelsState.refresh_stacking,
                class_name="flex shrink-0 items-center gap-2 rounded-lg bg-blue-600 px-3 py-2 text-xs font-semibold text-white transition-colors hover:bg-blue-500",
            ),
            class_name="flex flex-wrap items-center justify-between gap-3 border-b border-zinc-800 px-4 py-3",
        ),
        rx.el.div(
            rx.el.div(
                rx.el.div(
                    rx.el.span(
                        "Глобална точност",
                        class_name="text-[11px] font-semibold uppercase tracking-wider text-zinc-500",
                    ),
                    rx.el.p(
                        f"{ModelsState.stacking_accuracy:.1f}%",
                        class_name="mt-1 text-2xl font-semibold tracking-tight text-white tabular-nums sm:text-3xl",
                    ),
                    rx.el.p(
                        ModelsState.stacking_today_label,
                        class_name="mt-1 text-xs font-medium text-zinc-500",
                    ),
                    class_name="min-w-0 flex-1",
                ),
                rx.el.div(
                    rx.el.span(
                        "наспроти Meta-Ensemble",
                        class_name="text-[10px] font-semibold uppercase tracking-wider text-zinc-500",
                    ),
                    rx.el.span(
                        f"{ModelsState.stacking_delta_vs_meta:.2f} п.п.",
                        class_name=rx.cond(
                            ModelsState.stacking_delta_vs_meta >= 0.0,
                            "mt-1 w-fit rounded-full border border-emerald-500/35 bg-emerald-500/10 px-2 py-0.5 text-xs font-semibold text-emerald-300 tabular-nums",
                            "mt-1 w-fit rounded-full border border-amber-500/35 bg-amber-500/10 px-2 py-0.5 text-xs font-semibold text-amber-300 tabular-nums",
                        ),
                    ),
                    class_name="flex shrink-0 flex-col items-end",
                ),
                class_name="flex items-start justify-between gap-3",
            ),
            rx.el.div(
                rx.el.div(
                    class_name="h-full rounded-full bg-blue-500 transition-all duration-700",
                    style={"width": f"{ModelsState.stacking_accuracy}%"},
                ),
                class_name="mt-3 h-1.5 w-full overflow-hidden rounded-full bg-zinc-800",
            ),
            rx.el.div(
                _stacking_metric("1X2", f"{ModelsState.stacking_acc_1x2:.1f}%"),
                _stacking_metric("ГГ", f"{ModelsState.stacking_acc_btts:.1f}%"),
                _stacking_metric(
                    "Над 2.5", f"{ModelsState.stacking_acc_over25:.1f}%"
                ),
                _stacking_metric(
                    "Log-loss", f"{ModelsState.stacking_log_loss:.3f}"
                ),
                _stacking_metric("Brier", f"{ModelsState.stacking_brier:.3f}"),
                _stacking_metric("ROI", f"{ModelsState.stacking_roi:.2f}%"),
                class_name="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-3",
            ),
            rx.cond(
                ModelsState.stacking_backtest.length() > 0,
                rx.el.div(
                    rx.el.span(
                        "Ротирачки бектест (до 12 недели)",
                        class_name="text-[10px] font-semibold uppercase tracking-wider text-zinc-500",
                    ),
                    rx.el.div(
                        rx.foreach(
                            ModelsState.stacking_backtest, _stacking_week
                        ),
                        class_name="mt-2 flex flex-col gap-1.5",
                    ),
                    class_name="mt-4 w-full rounded-lg border border-zinc-800 bg-zinc-950/50 px-3 py-2.5",
                ),
                rx.fragment(),
            ),
            rx.el.div(
                rx.el.span(
                    f"Зачувани {ModelsState.stacking_saved} реда како XGBoost_Stacking (is_meta)",
                    class_name="text-[10px] font-semibold text-zinc-400 tabular-nums",
                ),
                rx.el.span(
                    f"Обем: {ModelsState.stacking_sample} решени натпревари",
                    class_name="text-[10px] font-medium text-zinc-500 tabular-nums",
                ),
                class_name="mt-3 flex flex-wrap items-center justify-between gap-2 rounded-lg border border-blue-500/25 bg-blue-500/[0.04] px-3 py-2",
            ),
            rx.cond(
                ModelsState.stacking_note != "",
                rx.el.p(
                    ModelsState.stacking_note,
                    class_name="mt-2 text-[10px] font-medium text-zinc-600",
                ),
                rx.fragment(),
            ),
            class_name="p-4",
        ),
        class_name="w-full rounded-xl border border-zinc-800 bg-zinc-900/50",
    )


def _comparison_row(row: ModelRow) -> rx.Component:
    return rx.el.tr(
        rx.el.td(
            rx.el.div(
                rx.el.span(
                    row["name"],
                    class_name="truncate text-sm font-medium text-zinc-100",
                ),
                rx.el.span(
                    row["params"],
                    class_name="truncate text-[10px] font-medium text-zinc-600",
                ),
                class_name="flex min-w-0 flex-col",
            ),
            class_name="px-3 py-2.5",
        ),
        rx.el.td(
            rx.el.span(
                row["family"],
                class_name="w-fit whitespace-nowrap rounded-full border border-zinc-700 bg-zinc-800/60 px-2 py-0.5 text-[10px] font-semibold text-zinc-400",
            ),
            class_name="hidden px-3 py-2.5 sm:table-cell",
        ),
        rx.el.td(
            f"{row['global_accuracy']:.1f}%",
            class_name="px-3 py-2.5 text-right text-sm font-semibold text-white tabular-nums",
        ),
        rx.el.td(
            f"{row['today_accuracy']:.1f}%",
            class_name="px-3 py-2.5 text-right text-sm text-zinc-300 tabular-nums",
        ),
        rx.el.td(
            f"{row['acc_1x2']:.1f}%",
            class_name="hidden px-3 py-2.5 text-right text-sm text-zinc-400 tabular-nums md:table-cell",
        ),
        rx.el.td(
            f"{row['acc_btts']:.1f}%",
            class_name="hidden px-3 py-2.5 text-right text-sm text-zinc-400 tabular-nums md:table-cell",
        ),
        rx.el.td(
            f"{row['acc_over25']:.1f}%",
            class_name="hidden px-3 py-2.5 text-right text-sm text-zinc-400 tabular-nums lg:table-cell",
        ),
        rx.el.td(
            rx.el.span(
                f"{row['delta_vs_meta']:.2f} п.п.",
                class_name=rx.cond(
                    row["delta_vs_meta"] >= 0.0,
                    "w-fit rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-xs font-semibold text-emerald-300 tabular-nums",
                    "w-fit rounded-full border border-zinc-700 bg-zinc-800/60 px-2 py-0.5 text-xs font-semibold text-zinc-400 tabular-nums",
                ),
            ),
            class_name="px-3 py-2.5 text-right",
        ),
        class_name="border-b border-zinc-800/70 transition-colors last:border-0 hover:bg-zinc-800/30",
    )


def _meta_reference_row() -> rx.Component:
    return rx.el.tr(
        rx.el.td(
            rx.el.div(
                rx.el.span(
                    "Meta-Ensemble",
                    class_name="text-sm font-semibold text-amber-300",
                ),
                rx.el.span(
                    "Тежинска комбинација од 25 модели",
                    class_name="truncate text-[10px] font-medium text-amber-300/60",
                ),
                class_name="flex min-w-0 flex-col",
            ),
            class_name="px-3 py-2.5",
        ),
        rx.el.td(
            rx.el.span(
                "Ансамбл",
                class_name="w-fit whitespace-nowrap rounded-full border border-amber-500/40 bg-amber-500/10 px-2 py-0.5 text-[10px] font-semibold text-amber-300",
            ),
            class_name="hidden px-3 py-2.5 sm:table-cell",
        ),
        rx.el.td(
            f"{ModelsState.meta['global_accuracy']:.1f}%",
            class_name="px-3 py-2.5 text-right text-sm font-semibold text-amber-300 tabular-nums",
        ),
        rx.el.td(
            f"{ModelsState.meta['today_accuracy']:.1f}%",
            class_name="px-3 py-2.5 text-right text-sm font-semibold text-amber-300 tabular-nums",
        ),
        rx.el.td(
            f"{ModelsState.meta['acc_1x2']:.1f}%",
            class_name="hidden px-3 py-2.5 text-right text-sm text-amber-300/80 tabular-nums md:table-cell",
        ),
        rx.el.td(
            f"{ModelsState.meta['acc_btts']:.1f}%",
            class_name="hidden px-3 py-2.5 text-right text-sm text-amber-300/80 tabular-nums md:table-cell",
        ),
        rx.el.td(
            f"{ModelsState.meta['acc_over25']:.1f}%",
            class_name="hidden px-3 py-2.5 text-right text-sm text-amber-300/80 tabular-nums lg:table-cell",
        ),
        rx.el.td(
            rx.el.span(
                "референца",
                class_name="w-fit rounded-full border border-amber-500/40 bg-amber-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-300",
            ),
            class_name="px-3 py-2.5 text-right",
        ),
        class_name="border-b border-amber-500/20 bg-amber-500/[0.05]",
    )


def _comparison_table() -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.icon("table-2", class_name="h-4 w-4 text-blue-400"),
            rx.el.div(
                rx.el.h3(
                    "Meta-Ensemble наспроти поединечни модели",
                    class_name="text-sm font-semibold tracking-tight text-white",
                ),
                rx.el.p(
                    "Топ 10 модели според глобална точност",
                    class_name="text-xs font-medium text-zinc-500",
                ),
                class_name="flex flex-col",
            ),
            class_name="flex items-center gap-3 border-b border-zinc-800 px-4 py-3",
        ),
        rx.el.div(
            rx.el.div(
                rx.el.table(
                    rx.el.thead(
                        rx.el.tr(
                            rx.el.th(
                                "Модел",
                                class_name="px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-wider text-zinc-500",
                            ),
                            rx.el.th(
                                "Семејство",
                                class_name="hidden px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-wider text-zinc-500 sm:table-cell",
                            ),
                            rx.el.th(
                                "Точност",
                                class_name="px-3 py-2 text-right text-[11px] font-semibold uppercase tracking-wider text-zinc-500",
                            ),
                            rx.el.th(
                                "Денес",
                                class_name="px-3 py-2 text-right text-[11px] font-semibold uppercase tracking-wider text-zinc-500",
                            ),
                            rx.el.th(
                                "1X2",
                                class_name="hidden px-3 py-2 text-right text-[11px] font-semibold uppercase tracking-wider text-zinc-500 md:table-cell",
                            ),
                            rx.el.th(
                                "ГГ",
                                class_name="hidden px-3 py-2 text-right text-[11px] font-semibold uppercase tracking-wider text-zinc-500 md:table-cell",
                            ),
                            rx.el.th(
                                "Над 2.5",
                                class_name="hidden px-3 py-2 text-right text-[11px] font-semibold uppercase tracking-wider text-zinc-500 lg:table-cell",
                            ),
                            rx.el.th(
                                "Δ vs Meta",
                                class_name="px-3 py-2 text-right text-[11px] font-semibold uppercase tracking-wider text-zinc-500",
                            ),
                        ),
                        class_name="border-b border-zinc-800 bg-zinc-950/40",
                    ),
                    rx.el.tbody(
                        _meta_reference_row(),
                        rx.foreach(
                            ModelsState.comparison_rows, _comparison_row
                        ),
                    ),
                    class_name="w-full table-auto",
                ),
                class_name="w-full overflow-x-auto",
            ),
            class_name="p-4",
        ),
        class_name="w-full overflow-hidden rounded-xl border border-zinc-800 bg-zinc-900/50",
    )


def models_view() -> rx.Component:
    return rx.el.div(
        _header(),
        _kpi_grid(),
        rx.el.div(_controls(), class_name="mt-4 w-full"),
        rx.cond(
            ModelsState.visible_count > 0,
            rx.el.div(
                rx.foreach(ModelsState.visible_models, _model_card),
                class_name="mt-4 grid w-full grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3",
            ),
            rx.el.div(
                rx.icon("inbox", class_name="h-6 w-6 text-zinc-600"),
                rx.el.p(
                    "Нема модели во оваа категорија",
                    class_name="mt-2 text-sm font-medium text-zinc-500",
                ),
                class_name="mt-4 flex w-full flex-col items-center justify-center rounded-xl border border-zinc-800 bg-zinc-900/40 py-14",
            ),
        ),
        rx.el.div(
            rx.el.div(_meta_panel(), class_name="flex-1 min-w-0"),
            rx.el.div(
                _families_card(),
                class_name="w-full lg:w-80 lg:shrink-0",
            ),
            class_name="mt-4 flex w-full flex-col gap-4 lg:flex-row",
        ),
        rx.el.div(stacking_meta_card(), class_name="mt-4 w-full"),
        rx.el.div(_comparison_table(), class_name="mt-4 w-full"),
        class_name="w-full",
    )
