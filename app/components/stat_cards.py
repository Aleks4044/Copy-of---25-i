import reflex as rx

from app.states.overview_state import OverviewState


def stat_card(
    label: str,
    value: rx.Component | rx.Var | str,
    hint: rx.Component | rx.Var | str,
    icon: str,
    accent: str,
) -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.el.span(
                label,
                class_name="text-[11px] font-semibold uppercase tracking-wider text-zinc-500",
            ),
            rx.el.div(
                rx.icon(icon, class_name="h-4 w-4"),
                class_name=accent,
            ),
            class_name="flex items-start justify-between gap-3",
        ),
        rx.el.p(
            value,
            class_name="mt-3 text-2xl font-semibold tracking-tight text-white tabular-nums sm:text-3xl",
        ),
        rx.el.p(hint, class_name="mt-1 text-xs font-medium text-zinc-500"),
        class_name="w-full rounded-xl border border-zinc-800 bg-zinc-900/50 p-4 transition-colors hover:border-zinc-700",
    )


def stat_grid() -> rx.Component:
    return rx.el.div(
        stat_card(
            "Активни предвидувања",
            OverviewState.total_picks.to_string(),
            f"{OverviewState.live_count} во тек · {OverviewState.upcoming_count} денес и следни",
            "list-checks",
            "flex size-8 items-center justify-center rounded-lg border border-blue-500/30 bg-blue-500/10 text-blue-400",
        ),
        stat_card(
            "Успешност (7 дена)",
            f"{OverviewState.hit_rate:.1f}%",
            f"{OverviewState.won_bets} од {OverviewState.settled_bets} завршени",
            "trending-up",
            "flex size-8 items-center justify-center rounded-lg border border-emerald-500/30 bg-emerald-500/10 text-emerald-400",
        ),
        stat_card(
            "Средна сигурност",
            f"{OverviewState.avg_confidence:.1f}%",
            OverviewState.confidence_label,
            "gauge",
            "flex size-8 items-center justify-center rounded-lg border border-blue-500/30 bg-blue-500/10 text-blue-400",
        ),
        stat_card(
            "ROI",
            f"{OverviewState.roi:.2f}%",
            f"Профит: {OverviewState.profit:.2f} ед.",
            "coins",
            "flex size-8 items-center justify-center rounded-lg border border-amber-500/30 bg-amber-500/10 text-amber-400",
        ),
        class_name="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4",
    )
