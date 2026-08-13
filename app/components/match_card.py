import reflex as rx

from app.components.api_status import unavailable_note
from app.components.bzz_source_panel import bzz_source_section
from app.components.fudbal91_panel import fudbal91_match_context
from app.states.bsd_state import BSDMatch, BSDState, ComboMarket, ModelPick
from app.states.models_state import ModelsState, StackingPick
from app.states.predictions import ScoreProjection, StackingMarket


def _section_label(title: str, icon: str, accent: str) -> rx.Component:
    return rx.el.div(
        rx.icon(icon, class_name="h-3.5 w-3.5"),
        rx.el.span(
            title,
            class_name="text-[11px] font-semibold uppercase tracking-wider",
        ),
        class_name=accent,
    )


def _source_chip(label: str, icon: str, accent: str) -> rx.Component:
    return rx.el.div(
        rx.icon(icon, class_name="h-3 w-3"),
        rx.el.span(
            label,
            class_name="text-[10px] font-bold uppercase tracking-wider",
        ),
        class_name=accent,
    )


def _source_badge_header(match: BSDMatch) -> rx.Component:
    """Ознака за активниот извор на предвидување во заглавјето."""
    return rx.cond(
        match["has_prediction"],
        rx.match(
            match["source"],
            (
                "fotmob",
                _source_chip(
                    "Fotmob",
                    "database-zap",
                    "flex w-fit shrink-0 items-center gap-1.5 rounded-full border border-blue-500/40 bg-blue-500/10 px-2 py-0.5 text-blue-300",
                ),
            ),
            (
                "bzz_event",
                _source_chip(
                    "BZZ по настан",
                    "database",
                    "flex w-fit shrink-0 items-center gap-1.5 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-emerald-200",
                ),
            ),
            (
                "bzz_derived",
                _source_chip(
                    "BZZ изведено · квоти/H2H",
                    "sigma",
                    "flex w-fit shrink-0 items-center gap-1.5 rounded-full border border-amber-500/40 bg-amber-500/10 px-2 py-0.5 text-amber-300",
                ),
            ),
            _source_chip(
                "BZZ API",
                "database",
                "flex w-fit shrink-0 items-center gap-1.5 rounded-full border border-emerald-500/40 bg-emerald-500/10 px-2 py-0.5 text-emerald-300",
            ),
        ),
        _source_chip(
            "Без предвидување",
            "circle-slash",
            "flex w-fit shrink-0 items-center gap-1.5 rounded-full border border-zinc-700 bg-zinc-800/60 px-2 py-0.5 text-zinc-400",
        ),
    )


def _stat_fact_row(fact: rx.Var) -> rx.Component:
    return rx.el.div(
        rx.icon(
            "chart-no-axes-column",
            class_name="mt-0.5 h-3 w-3 shrink-0 text-zinc-400",
        ),
        rx.el.span(
            fact,
            class_name="min-w-0 text-[11px] font-medium text-zinc-400",
        ),
        class_name="flex items-start gap-2",
    )


def _stat_facts_section(match: BSDMatch) -> rx.Component:
    return rx.cond(
        match["stat_facts"].length() > 0,
        rx.el.div(
            _section_label(
                rx.cond(
                    match["source"] == "bzz_derived",
                    "BZZ изведени показатели",
                    "Fotmob статистички факти",
                ),
                rx.cond(
                    match["source"] == "bzz_derived",
                    "sigma",
                    "database-zap",
                ),
                rx.cond(
                    match["source"] == "bzz_derived",
                    "flex w-fit items-center gap-1.5 rounded-md border border-amber-500/30 bg-amber-500/10 px-2 py-1 text-amber-300",
                    "flex w-fit items-center gap-1.5 rounded-md border border-blue-500/30 bg-blue-500/10 px-2 py-1 text-blue-300",
                ),
            ),
            rx.el.div(
                rx.foreach(match["stat_facts"], _stat_fact_row),
                class_name="mt-3 flex flex-col gap-2",
            ),
            class_name="mt-3 w-full min-w-0 rounded-lg border border-zinc-800 bg-zinc-900/40 p-3.5",
        ),
        rx.fragment(),
    )


def _prob_bar(
    label: rx.Var | str,
    value: rx.Var,
    bar_class: str,
    text_class: str,
) -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.el.span(label, class_name="text-xs font-medium text-zinc-300"),
            rx.el.span(
                f"{value:.1f}%",
                class_name=text_class,
            ),
            class_name="flex items-center justify-between gap-3",
        ),
        rx.el.div(
            rx.el.div(
                class_name=bar_class,
                style={"width": f"{value}%"},
            ),
            class_name="mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-zinc-800",
        ),
        class_name="w-full min-w-0",
    )


def _stat_tile(
    label: str, value: rx.Var | str, hint: rx.Var | str
) -> rx.Component:
    return rx.el.div(
        rx.el.span(
            label,
            class_name="text-[10px] font-semibold uppercase tracking-wider text-zinc-500",
        ),
        rx.el.span(
            value,
            class_name="mt-1 text-sm font-semibold text-white tabular-nums",
        ),
        rx.el.span(hint, class_name="text-[10px] font-medium text-zinc-500"),
        class_name="flex w-full flex-col rounded-lg border border-zinc-800 bg-zinc-950/60 px-3 py-2",
    )


def _ht_chip(match: BSDMatch) -> rx.Component:
    """Резултат од полувреме кога API-то го обезбедува."""
    return rx.cond(
        match["has_ht"],
        rx.el.span(
            match["ht_label"],
            class_name="w-fit whitespace-nowrap rounded-full border border-zinc-700 bg-zinc-800/60 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-zinc-300 tabular-nums",
        ),
        rx.fragment(),
    )


def _status_pill(match: BSDMatch) -> rx.Component:
    return rx.el.span(
        rx.match(
            match["status"],
            (
                "live",
                rx.el.span(
                    rx.cond(
                        match["minute"] != "",
                        match["minute"],
                        match["status_text"],
                    )
                ),
            ),
            ("finished", rx.el.span("Завршен")),
            ("cancelled", rx.el.span("Откажан")),
            ("postponed", rx.el.span("Одложен")),
            rx.el.span(match["kickoff"]),
        ),
        class_name=rx.match(
            match["status"],
            (
                "live",
                "w-fit rounded-full border border-blue-500/40 bg-blue-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-blue-300 tabular-nums",
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
            "w-fit rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-emerald-300 tabular-nums",
        ),
    )


def _team_emblem(logo_url: rx.Var, name: rx.Var) -> rx.Component:
    """Компактен грб на тим; иницијал или икона кога нема ID/слика."""
    return rx.el.div(
        rx.cond(
            logo_url != "",
            rx.image(
                src=logo_url,
                alt="",
                loading="lazy",
                aria_hidden="true",
                class_name="size-5 object-contain",
            ),
            rx.cond(
                name != "",
                rx.el.span(
                    name.upper()[0],
                    aria_hidden="true",
                    class_name="text-[10px] font-bold text-zinc-400",
                ),
                rx.icon("shield", class_name="h-3 w-3 text-zinc-600"),
            ),
        ),
        aria_hidden="true",
        class_name="flex size-7 shrink-0 items-center justify-center overflow-hidden rounded-md border border-zinc-800 bg-zinc-950/70",
    )


def _team_form(form: rx.Var, align: str) -> rx.Component:
    """W/D/L форма од реални H2H/Fotmob резултати, или суптилна црта."""
    return rx.cond(
        form != "",
        rx.el.span(
            form,
            title="Форма од реални последни/H2H резултати (најново прво)",
            class_name=align
            + " mt-1 block text-[11px] font-semibold tracking-[0.18em] text-zinc-400",
        ),
        rx.el.span(
            "–",
            title="Формата не е достапна од API-то",
            class_name=align
            + " mt-1 block text-[11px] font-semibold text-zinc-700",
        ),
    )


def _match_header(match: BSDMatch) -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.el.div(
                rx.el.span(
                    match["league"],
                    class_name="text-[11px] font-semibold uppercase tracking-wider text-zinc-500",
                ),
                _status_pill(match),
                _ht_chip(match),
                _source_badge_header(match),
                class_name="flex flex-wrap items-center gap-2",
            ),
            rx.el.div(
                rx.el.div(
                    rx.el.div(
                        _team_emblem(match["home_logo_url"], match["home"]),
                        rx.el.p(
                            match["home"],
                            class_name="truncate text-sm font-semibold text-white sm:text-base",
                        ),
                        class_name="flex min-w-0 items-center gap-2",
                    ),
                    _team_form(match["form_home"], "text-left"),
                    class_name="min-w-0 flex-1",
                ),
                rx.el.span(
                    match["score"],
                    class_name="shrink-0 rounded-lg border border-zinc-800 bg-zinc-950/70 px-2.5 py-1 text-sm font-semibold text-zinc-200 tabular-nums",
                ),
                rx.el.div(
                    rx.el.div(
                        rx.el.p(
                            match["away"],
                            class_name="truncate text-right text-sm font-semibold text-white sm:text-base",
                        ),
                        _team_emblem(match["away_logo_url"], match["away"]),
                        class_name="flex min-w-0 items-center justify-end gap-2",
                    ),
                    _team_form(match["form_away"], "text-right"),
                    class_name="min-w-0 flex-1",
                ),
                class_name="mt-2 flex items-start gap-3",
            ),
            rx.el.div(
                rx.el.span(
                    f"{match['day_label']} {match['kickoff']} · {match['venue']}",
                    class_name="text-[11px] font-medium text-zinc-600",
                ),
                class_name="mt-1.5 flex items-center justify-center gap-3",
            ),
            class_name="min-w-0 flex-1",
        ),
        class_name="flex items-start gap-3 border-b border-zinc-800 px-4 py-3.5",
    )


def _bsd_ml_section(match: BSDMatch) -> rx.Component:
    return rx.el.div(
        _section_label(
            "BSD ML",
            "brain",
            "flex w-fit items-center gap-1.5 rounded-md border border-blue-500/30 bg-blue-500/10 px-2 py-1 text-blue-300",
        ),
        rx.el.div(
            _prob_bar(
                f"1 · {match['home']}",
                match["ml_home"],
                "h-full rounded-full bg-blue-500 transition-all duration-700",
                "text-xs font-semibold text-white tabular-nums",
            ),
            _prob_bar(
                "X · Реми",
                match["ml_draw"],
                "h-full rounded-full bg-zinc-500 transition-all duration-700",
                "text-xs font-semibold text-white tabular-nums",
            ),
            _prob_bar(
                f"2 · {match['away']}",
                match["ml_away"],
                "h-full rounded-full bg-blue-400/70 transition-all duration-700",
                "text-xs font-semibold text-white tabular-nums",
            ),
            class_name="mt-3 flex flex-col gap-2.5",
        ),
        rx.el.div(
            rx.el.span(
                "Избор на модел",
                class_name="text-[10px] font-semibold uppercase tracking-wider text-zinc-500",
            ),
            rx.el.span(
                match["ml_pick"],
                class_name="truncate text-xs font-semibold text-blue-300",
            ),
            class_name="mt-3 flex items-center justify-between gap-3 rounded-lg border border-zinc-800 bg-zinc-950/60 px-3 py-2",
        ),
        class_name="w-full min-w-0 rounded-lg border border-zinc-800 bg-zinc-900/40 p-3.5",
    )


def _poisson_section(match: BSDMatch) -> rx.Component:
    return rx.el.div(
        rx.el.div(
            _section_label(
                "Bivariate Poisson",
                "sigma",
                "flex w-fit items-center gap-1.5 rounded-md border border-emerald-500/30 bg-emerald-500/10 px-2 py-1 text-emerald-300",
            ),
            rx.el.span(
                f"xG {match['xg_home']:.2f} — {match['xg_away']:.2f}",
                class_name="text-[11px] font-semibold text-zinc-400 tabular-nums",
            ),
            class_name="flex flex-wrap items-center justify-between gap-2",
        ),
        rx.el.div(
            rx.el.div(
                rx.el.span(
                    "1",
                    class_name="text-[10px] font-semibold uppercase text-zinc-500",
                ),
                rx.el.span(
                    f"{match['poi_home']:.1f}%",
                    class_name="text-sm font-semibold text-white tabular-nums",
                ),
                class_name="flex flex-1 flex-col items-center rounded-lg border border-zinc-800 bg-zinc-950/60 py-2",
            ),
            rx.el.div(
                rx.el.span(
                    "X",
                    class_name="text-[10px] font-semibold uppercase text-zinc-500",
                ),
                rx.el.span(
                    f"{match['poi_draw']:.1f}%",
                    class_name="text-sm font-semibold text-white tabular-nums",
                ),
                class_name="flex flex-1 flex-col items-center rounded-lg border border-zinc-800 bg-zinc-950/60 py-2",
            ),
            rx.el.div(
                rx.el.span(
                    "2",
                    class_name="text-[10px] font-semibold uppercase text-zinc-500",
                ),
                rx.el.span(
                    f"{match['poi_away']:.1f}%",
                    class_name="text-sm font-semibold text-white tabular-nums",
                ),
                class_name="flex flex-1 flex-col items-center rounded-lg border border-zinc-800 bg-zinc-950/60 py-2",
            ),
            class_name="mt-3 flex items-stretch gap-2",
        ),
        rx.el.div(
            _stat_tile(
                "ГГ (BTTS)",
                f"{match['poi_btts']:.1f}%",
                rx.cond(
                    match["poi_btts"] >= 50.0, "Препорака: ГГ", "Препорака: НГ"
                ),
            ),
            _stat_tile(
                "Над 2.5",
                f"{match['poi_over25']:.1f}%",
                f"Под 2.5: {match['poi_under25']:.1f}%",
            ),
            _stat_tile(
                "Најверојатен резултат (FT)",
                rx.cond(
                    (match["top_score"] != "Недостапно")
                    & (match["top_score_prob"] > 0.0),
                    match["top_score"],
                    "Недостапно",
                ),
                rx.cond(
                    match["top_score_prob"] > 0.0,
                    f"{match['top_score_prob']:.1f}% од матрицата на резултати",
                    "нема употребливи вредности од моделот",
                ),
            ),
            _stat_tile(
                "Очекувани голови",
                f"{match['expected_goals']:.2f}",
                "λ дома + λ гости",
            ),
            class_name="mt-2 grid grid-cols-2 gap-2",
        ),
        class_name="w-full min-w-0 rounded-lg border border-zinc-800 bg-zinc-900/40 p-3.5",
    )


def _model_mini_card(model: ModelPick, index: int) -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.el.span(
                f"#{index + 1}",
                class_name="text-[10px] font-bold text-zinc-600 tabular-nums",
            ),
            rx.el.span(
                model["family"],
                class_name="truncate rounded-full border border-zinc-700 bg-zinc-800/60 px-2 py-0.5 text-[10px] font-semibold text-zinc-400",
            ),
            class_name="flex items-center justify-between gap-2",
        ),
        rx.el.p(
            model["name"],
            class_name="mt-2 truncate text-xs font-semibold text-white",
        ),
        rx.el.p(
            model["pick"],
            class_name="truncate text-[11px] font-medium text-blue-300",
        ),
        rx.el.div(
            rx.el.div(
                class_name="h-full rounded-full bg-blue-500/80",
                style={"width": f"{model['probability']}%"},
            ),
            class_name="mt-2 h-1 w-full overflow-hidden rounded-full bg-zinc-800",
        ),
        rx.el.div(
            rx.el.span(
                f"{model['probability']:.1f}%",
                class_name="text-xs font-semibold text-white tabular-nums",
            ),
            rx.el.span(
                f"точност {model['accuracy']:.1f}%",
                class_name="text-[10px] font-medium text-zinc-500 tabular-nums",
            ),
            class_name="mt-1.5 flex items-center justify-between gap-2",
        ),
        class_name="w-full min-w-0 rounded-lg border border-zinc-800 bg-zinc-950/60 p-3",
    )


def _top_models_section(match: BSDMatch) -> rx.Component:
    return rx.el.div(
        _section_label(
            "Топ 3 модели",
            "layers",
            "flex w-fit items-center gap-1.5 rounded-md border border-zinc-700 bg-zinc-800/60 px-2 py-1 text-zinc-300",
        ),
        rx.el.div(
            rx.foreach(
                match["top_models"],
                lambda model, index: _model_mini_card(model, index),
            ),
            class_name="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-3",
        ),
        class_name="w-full min-w-0 rounded-lg border border-zinc-800 bg-zinc-900/40 p-3.5",
    )


def _meta_section(match: BSDMatch) -> rx.Component:
    return rx.el.div(
        rx.el.div(
            _section_label(
                "Meta-Ensemble · финален избор",
                "crown",
                "flex w-fit items-center gap-1.5 rounded-md border border-amber-500/40 bg-amber-500/10 px-2 py-1 text-amber-300",
            ),
            rx.el.span(
                match["meta_value"],
                class_name=rx.cond(
                    match["meta_edge"] >= 6.0,
                    "w-fit rounded-full border border-amber-500/40 bg-amber-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-300",
                    "w-fit rounded-full border border-zinc-700 bg-zinc-800/60 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-zinc-400",
                ),
            ),
            class_name="flex flex-wrap items-center justify-between gap-2",
        ),
        rx.el.div(
            rx.el.div(
                rx.el.span(
                    match["meta_market"],
                    class_name="text-[10px] font-semibold uppercase tracking-wider text-amber-300/70",
                ),
                rx.el.p(
                    match["meta_pick"],
                    class_name="text-base font-semibold text-white sm:text-lg",
                ),
                class_name="flex min-w-0 flex-col",
            ),
            rx.el.div(
                rx.el.span(
                    f"{match['meta_confidence']:.1f}%",
                    class_name="text-xl font-semibold text-amber-300 tabular-nums sm:text-2xl",
                ),
                rx.el.span(
                    "сигурност",
                    class_name="text-[10px] font-semibold uppercase tracking-wider text-zinc-500",
                ),
                class_name="flex shrink-0 flex-col items-end",
            ),
            class_name="mt-3 flex items-end justify-between gap-3",
        ),
        rx.el.div(
            rx.el.div(
                class_name="h-full rounded-full bg-amber-400 transition-all duration-700",
                style={"width": f"{match['meta_confidence']}%"},
            ),
            class_name="mt-2.5 h-1.5 w-full overflow-hidden rounded-full bg-zinc-800",
        ),
        rx.el.div(
            _stat_tile("Квота", f"{match['meta_odds']:.2f}", "препорачана"),
            _stat_tile(
                "Предност",
                f"{match['meta_edge']:.2f} п.п.",
                rx.cond(match["meta_edge"] >= 0.0, "позитивна", "негативна"),
            ),
            _stat_tile(
                "Согласност",
                f"{match['meta_agreement']:.0f}%",
                "од топ 3 модели",
            ),
            _stat_tile(
                "Над / Под 1.5",
                rx.cond(
                    match["poi_over15"] > 0.0,
                    f"{match['poi_over15']:.1f}%",
                    "Недостапно",
                ),
                rx.cond(
                    match["poi_over15"] > 0.0,
                    f"Под 1.5: {match['poi_under15']:.1f}%",
                    "нема веројатност за 1.5 гола",
                ),
            ),
            class_name="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4",
        ),
        _extra_recommendation_tile(match),
        class_name="w-full min-w-0 rounded-lg border border-amber-500/25 bg-amber-500/[0.04] p-3.5",
    )


def _extra_recommendation_tile(match: BSDMatch) -> rx.Component:
    """Една дополнителна препорака од најсилната реална веројатност."""
    return rx.el.div(
        rx.el.div(
            rx.el.span(
                "Дополнителна препорака",
                class_name="text-[10px] font-semibold uppercase tracking-wider text-zinc-500",
            ),
            rx.cond(
                match["extra_probability"] > 0.0,
                rx.el.span(
                    match["extra_label"],
                    class_name="w-fit whitespace-nowrap rounded-full border border-zinc-700 bg-zinc-800/60 px-2 py-0.5 text-[10px] font-semibold text-zinc-400",
                ),
                rx.fragment(),
            ),
            class_name="flex flex-wrap items-center justify-between gap-2",
        ),
        rx.cond(
            match["extra_probability"] > 0.0,
            rx.el.div(
                rx.el.div(
                    rx.el.span(
                        match["extra_pick"],
                        class_name="truncate text-sm font-semibold text-white",
                    ),
                    rx.el.span(
                        f"{match['extra_probability']:.1f}%",
                        class_name="shrink-0 text-sm font-semibold text-amber-300 tabular-nums",
                    ),
                    class_name="mt-1 flex items-center justify-between gap-2",
                ),
                rx.el.div(
                    rx.el.div(
                        class_name="h-full rounded-full bg-amber-400/70 transition-all duration-700",
                        style={"width": f"{match['extra_probability']}%"},
                    ),
                    class_name="mt-2 h-1 w-full overflow-hidden rounded-full bg-zinc-800",
                ),
                class_name="w-full",
            ),
            rx.el.span(
                "Недостапно",
                class_name="mt-1 block text-sm font-semibold text-zinc-500",
            ),
        ),
        class_name="mt-2 flex w-full min-w-0 flex-col rounded-lg border border-zinc-800 bg-zinc-950/60 px-3 py-2",
    )


def _stacking_pick_card(pick: StackingPick) -> rx.Component:
    """Реален XGBoost + Stacking избор за конкретен натпревар."""
    return rx.el.div(
        rx.el.div(
            rx.el.div(
                rx.el.span(
                    pick["market"],
                    class_name="text-[10px] font-semibold uppercase tracking-wider text-blue-300/70",
                ),
                rx.el.p(
                    pick["pick"],
                    class_name="truncate text-base font-semibold text-white sm:text-lg",
                ),
                class_name="flex min-w-0 flex-col",
            ),
            rx.el.div(
                rx.el.span(
                    f"{pick['confidence']:.1f}%",
                    class_name="text-xl font-semibold text-blue-300 tabular-nums sm:text-2xl",
                ),
                rx.el.span(
                    "сигурност",
                    class_name="text-[10px] font-semibold uppercase tracking-wider text-zinc-500",
                ),
                class_name="flex shrink-0 flex-col items-end",
            ),
            class_name="flex items-end justify-between gap-3",
        ),
        rx.el.div(
            rx.el.div(
                class_name="h-full rounded-full bg-blue-500 transition-all duration-700",
                style={"width": f"{pick['confidence']}%"},
            ),
            class_name="mt-2.5 h-1.5 w-full overflow-hidden rounded-full bg-zinc-800",
        ),
        rx.el.div(
            _prob_bar(
                "1 · Домашен",
                pick["prob_home"],
                "h-full rounded-full bg-blue-500 transition-all duration-700",
                "text-xs font-semibold text-white tabular-nums",
            ),
            _prob_bar(
                "X · Реми",
                pick["prob_draw"],
                "h-full rounded-full bg-zinc-500 transition-all duration-700",
                "text-xs font-semibold text-white tabular-nums",
            ),
            _prob_bar(
                "2 · Гостин",
                pick["prob_away"],
                "h-full rounded-full bg-blue-400/70 transition-all duration-700",
                "text-xs font-semibold text-white tabular-nums",
            ),
            class_name="mt-3 flex flex-col gap-2.5",
        ),
        rx.el.div(
            _stat_tile(
                "Квота",
                rx.cond(pick["has_odds"], f"{pick['odds']:.2f}", "недостапна"),
                "од Meta препораката",
            ),
            _stat_tile(
                "Предност",
                rx.cond(
                    pick["has_odds"], f"{pick['edge']:.2f} п.п.", "недостапна"
                ),
                rx.cond(pick["edge"] >= 0.0, "позитивна", "негативна"),
            ),
            _stat_tile(
                "Глобална точност",
                f"{ModelsState.stacking_accuracy:.1f}%",
                f"1X2 {ModelsState.stacking_acc_1x2:.1f}% · обем {ModelsState.stacking_sample}",
            ),
            _stat_tile(
                "Наспроти Meta",
                f"{ModelsState.stacking_delta_vs_meta:.2f} п.п.",
                "втор предвидувачки слој",
            ),
            class_name="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4",
        ),
        rx.cond(
            pick["settled"],
            rx.el.div(
                rx.el.span(
                    "Проверено со реален резултат",
                    class_name="text-[10px] font-semibold uppercase tracking-wider text-zinc-500",
                ),
                rx.el.span(
                    rx.cond(pick["is_correct"], "Точно", "Погрешно"),
                    class_name=rx.cond(
                        pick["is_correct"],
                        "w-fit whitespace-nowrap rounded-full border border-emerald-500/35 bg-emerald-500/10 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-emerald-300",
                        "w-fit whitespace-nowrap rounded-full border border-red-500/35 bg-red-500/10 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-red-300",
                    ),
                ),
                class_name="mt-3 flex flex-wrap items-center justify-between gap-2 rounded-lg border border-zinc-800 bg-zinc-950/60 px-3 py-2",
            ),
            rx.fragment(),
        ),
        class_name="w-full min-w-0",
    )


def _stacking_market_tile(row: StackingMarket) -> rx.Component:
    """Компактна плочка за дополнителен маркет од вториот слој."""
    return rx.el.div(
        rx.el.div(
            rx.el.span(
                row["market"],
                class_name="truncate text-[9px] font-semibold uppercase tracking-wider text-zinc-500",
            ),
            rx.cond(
                row["available"],
                rx.el.span(
                    f"{row['confidence']:.1f}%",
                    class_name="shrink-0 text-[11px] font-semibold text-blue-300 tabular-nums",
                ),
                rx.el.span(
                    "недостапно",
                    class_name="shrink-0 text-[9px] font-semibold uppercase tracking-wide text-zinc-600",
                ),
            ),
            class_name="flex items-center justify-between gap-2",
        ),
        rx.el.p(
            row["pick"],
            class_name=rx.cond(
                row["available"],
                "mt-0.5 truncate text-[11px] font-semibold text-white",
                "mt-0.5 truncate text-[11px] font-semibold text-zinc-500",
            ),
        ),
        rx.cond(
            row["available"],
            rx.el.div(
                rx.el.div(
                    class_name="h-full rounded-full bg-blue-500/80 transition-all duration-700",
                    style={"width": f"{row['confidence']}%"},
                ),
                class_name="mt-1.5 h-1 w-full overflow-hidden rounded-full bg-zinc-800",
            ),
            rx.fragment(),
        ),
        rx.el.span(
            rx.cond(
                row["has_odds"],
                f"квота {row['odds']:.2f} · предност {row['edge']:.2f} п.п.",
                "без квота и предност",
            ),
            class_name="mt-1 block truncate text-[9px] font-medium text-zinc-600",
        ),
        rx.el.span(
            row["basis"],
            class_name="block truncate text-[9px] font-medium text-zinc-700",
        ),
        class_name=rx.cond(
            row["available"],
            "w-full min-w-0 rounded-lg border border-zinc-800 bg-zinc-950/60 px-2.5 py-2",
            "w-full min-w-0 rounded-lg border border-dashed border-zinc-800 bg-zinc-950/40 px-2.5 py-2",
        ),
    )


def _score_projection_row(row: ScoreProjection) -> rx.Component:
    """Еден ред од проекцијата на точен резултат (само реални λ)."""
    return rx.el.div(
        rx.el.div(
            rx.el.span(
                f"#{row['rank']}",
                class_name="w-5 shrink-0 text-[10px] font-bold text-zinc-600 tabular-nums",
            ),
            rx.el.span(
                row["score"],
                class_name="min-w-0 flex-1 text-sm font-semibold text-white tabular-nums",
            ),
            rx.el.span(
                f"{row['probability']:.1f}%",
                class_name="shrink-0 text-xs font-semibold text-blue-300 tabular-nums",
            ),
            class_name="flex items-center gap-2",
        ),
        rx.el.div(
            rx.el.div(
                class_name="h-full rounded-full bg-blue-500/80 transition-all duration-700",
                style={"width": f"{row['probability']}%"},
            ),
            class_name="mt-1 h-1 w-full overflow-hidden rounded-full bg-zinc-800",
        ),
        class_name="w-full min-w-0 rounded-lg border border-zinc-800 bg-zinc-950/60 px-2.5 py-1.5",
    )


def _score_projection_column(
    title: str,
    icon: str,
    rows: rx.Var,
    match: BSDMatch,
) -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.icon(icon, class_name="h-3 w-3 shrink-0 text-blue-400"),
            rx.el.span(
                title,
                class_name="truncate text-[10px] font-semibold uppercase tracking-wider text-zinc-500",
            ),
            class_name="flex items-center gap-1.5",
        ),
        rx.el.div(
            rx.foreach(
                rows,
                lambda row: rx.cond(
                    row["match_id"] == match["id"],
                    _score_projection_row(row),
                    rx.fragment(),
                ),
            ),
            class_name="mt-2 flex flex-col gap-1.5",
        ),
        class_name="w-full min-w-0 rounded-lg border border-zinc-800 bg-zinc-950/40 px-2.5 py-2",
    )


def _score_projections_block(match: BSDMatch) -> rx.Component:
    """Најверојатни FT и HT резултати од вториот слој."""
    return rx.cond(
        ModelsState.stacking_score_ids.contains(match["id"]),
        rx.el.div(
            rx.el.div(
                rx.el.span(
                    "Проекции на точен резултат · од реални очекувани голови",
                    class_name="truncate text-[10px] font-semibold uppercase tracking-wider text-zinc-500",
                ),
                rx.el.span(
                    "Poisson од λ",
                    class_name="shrink-0 whitespace-nowrap text-[9px] font-medium text-zinc-600",
                ),
                class_name="flex flex-wrap items-center justify-between gap-2",
            ),
            rx.el.div(
                _score_projection_column(
                    "Топ 3 FT резултати",
                    "flag",
                    ModelsState.stacking_ft_scores,
                    match,
                ),
                _score_projection_column(
                    "Топ 3 HT резултати",
                    "timer",
                    ModelsState.stacking_ht_scores,
                    match,
                ),
                class_name="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-2",
            ),
            rx.el.p(
                "HT проекцијата користи ~45% од истите реални λ; ниту една "
                "вредност не е измислена.",
                class_name="mt-2 text-[9px] font-medium text-zinc-700",
            ),
            class_name="mt-3 w-full min-w-0 rounded-lg border border-zinc-800 bg-zinc-950/40 px-2.5 py-2",
        ),
        rx.cond(
            ModelsState.stacking_match_ids.contains(match["id"]),
            rx.el.div(
                unavailable_note(ModelsState.stacking_scores_note),
                class_name="mt-3 w-full",
            ),
            rx.fragment(),
        ),
    )


def _stacking_markets_grid(match: BSDMatch) -> rx.Component:
    """Компактна решетка со дополнителните маркети од вториот слој."""
    return rx.cond(
        ModelsState.stacking_market_ids.contains(match["id"]),
        rx.el.div(
            rx.el.div(
                rx.el.span(
                    "Дополнителни маркети · XGBoost + Stacking втор слој",
                    class_name="text-[10px] font-semibold uppercase tracking-wider text-zinc-500",
                ),
                rx.el.span(
                    "Топ 6 достапни по сигурност",
                    class_name="whitespace-nowrap text-[9px] font-medium text-zinc-600",
                ),
                class_name="flex flex-wrap items-center justify-between gap-2",
            ),
            rx.cond(
                ModelsState.stacking_available_ids.contains(match["id"]),
                rx.el.div(
                    rx.foreach(
                        ModelsState.stacking_visible_markets,
                        lambda row: rx.cond(
                            row["match_id"] == match["id"],
                            _stacking_market_tile(row),
                            rx.fragment(),
                        ),
                    ),
                    class_name="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-3",
                ),
                rx.el.div(
                    unavailable_note(
                        "Вториот слој не врати достапен дополнителен маркет за "
                        "овој натпревар"
                    ),
                    class_name="mt-2 w-full",
                ),
            ),
            class_name="mt-3 w-full min-w-0 rounded-lg border border-zinc-800 bg-zinc-950/40 px-2.5 py-2",
        ),
        rx.fragment(),
    )


def _stacking_section(match: BSDMatch) -> rx.Component:
    """Втор предвидувачки слој под Meta-Ensemble (не го заменува)."""
    return rx.el.div(
        rx.el.div(
            _section_label(
                "XGBoost + Stacking · втор слој",
                "boxes",
                "flex w-fit items-center gap-1.5 rounded-md border border-blue-500/30 bg-blue-500/10 px-2 py-1 text-blue-300",
            ),
            rx.el.span(
                ModelsState.stacking_badge_label,
                class_name=rx.cond(
                    ModelsState.stacking_match_ids.contains(match["id"]),
                    "w-fit whitespace-nowrap rounded-full border border-blue-500/35 bg-blue-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-blue-300 tabular-nums",
                    "w-fit whitespace-nowrap rounded-full border border-amber-500/35 bg-amber-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-300",
                ),
            ),
            class_name="flex flex-wrap items-center justify-between gap-2",
        ),
        rx.cond(
            ModelsState.stacking_match_ids.contains(match["id"]),
            rx.el.div(
                rx.foreach(
                    ModelsState.stacking_picks,
                    lambda pick: rx.cond(
                        pick["match_id"] == match["id"],
                        _stacking_pick_card(pick),
                        rx.fragment(),
                    ),
                ),
                class_name="mt-3 w-full",
            ),
            rx.el.div(
                unavailable_note(ModelsState.stacking_status_note),
                rx.el.button(
                    rx.icon(
                        "refresh-cw",
                        class_name=rx.cond(
                            ModelsState.stacking_is_loading,
                            "h-3.5 w-3.5 animate-spin",
                            "h-3.5 w-3.5",
                        ),
                    ),
                    rx.el.span(
                        "Пресметај stacking слој",
                        class_name="whitespace-nowrap",
                    ),
                    on_click=ModelsState.refresh_stacking,
                    class_name="mt-2 flex w-full items-center justify-center gap-2 rounded-lg border border-zinc-800 bg-zinc-950/50 px-3 py-2 text-xs font-semibold text-zinc-400 transition-colors hover:border-zinc-700 hover:text-white",
                ),
                class_name="mt-3 w-full",
            ),
        ),
        _score_projections_block(match),
        _stacking_markets_grid(match),
        class_name="mt-3 w-full min-w-0 rounded-lg border border-blue-500/20 bg-blue-500/[0.03] p-3.5",
    )


def _combo_row(combo: ComboMarket) -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.el.span(
                combo["label"],
                class_name="min-w-0 flex-1 truncate text-xs font-semibold text-white",
            ),
            rx.el.span(
                f"{combo['probability']:.1f}%",
                class_name=rx.cond(
                    combo["recommended"],
                    "shrink-0 text-xs font-semibold text-blue-300 tabular-nums",
                    "shrink-0 text-xs font-semibold text-zinc-400 tabular-nums",
                ),
            ),
            class_name="flex items-center gap-2",
        ),
        rx.el.div(
            rx.el.div(
                class_name=rx.cond(
                    combo["recommended"],
                    "h-full rounded-full bg-blue-500 transition-all duration-700",
                    "h-full rounded-full bg-zinc-600 transition-all duration-700",
                ),
                style={"width": f"{combo['probability']}%"},
            ),
            class_name="mt-1.5 h-1 w-full overflow-hidden rounded-full bg-zinc-800",
        ),
        rx.el.div(
            rx.el.span(
                combo["group_label"],
                class_name="truncate text-[10px] font-medium text-zinc-600",
            ),
            rx.cond(
                combo["recommended"],
                rx.el.span(
                    combo["recommendation"],
                    class_name=rx.cond(
                        combo["probability"] >= 70.0,
                        "w-fit whitespace-nowrap rounded-full border border-emerald-500/35 bg-emerald-500/10 px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide text-emerald-300",
                        rx.cond(
                            combo["probability"] >= 55.0,
                            "w-fit whitespace-nowrap rounded-full border border-blue-500/35 bg-blue-500/10 px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide text-blue-300",
                            "w-fit whitespace-nowrap rounded-full border border-amber-500/35 bg-amber-500/10 px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide text-amber-300",
                        ),
                    ),
                ),
                rx.el.span(
                    f"квота {combo['odds']:.2f}",
                    class_name="whitespace-nowrap text-[10px] font-medium text-zinc-600 tabular-nums",
                ),
            ),
            class_name="mt-1.5 flex items-center justify-between gap-2",
        ),
        class_name="w-full min-w-0 rounded-lg border border-zinc-800 bg-zinc-950/60 px-3 py-2",
    )


def _combos_section(match: BSDMatch) -> rx.Component:
    return rx.el.div(
        rx.el.div(
            _section_label(
                "Комбинирани маркети",
                "layers",
                "flex w-fit items-center gap-1.5 rounded-md border border-blue-500/30 bg-blue-500/10 px-2 py-1 text-blue-300",
            ),
            rx.el.span(
                f"{match['combo_count']} комбинации · {match['combo_recommended']} над 40%",
                class_name="text-[11px] font-semibold text-zinc-400 tabular-nums",
            ),
            class_name="flex flex-wrap items-center justify-between gap-2",
        ),
        rx.cond(
            BSDState.expanded_id == match["id"],
            rx.el.div(
                rx.foreach(match["combos"], _combo_row),
                class_name="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2 xl:grid-cols-3",
            ),
            rx.el.div(
                rx.foreach(match["top_combos"], _combo_row),
                class_name="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2 xl:grid-cols-3",
            ),
        ),
        rx.el.div(
            rx.el.span(
                "Најсилна комбинација",
                class_name="text-[10px] font-semibold uppercase tracking-wider text-zinc-500",
            ),
            rx.el.span(
                f"{match['best_combo_label']} · {match['best_combo_probability']:.1f}%",
                class_name="truncate text-xs font-semibold text-blue-300 tabular-nums",
            ),
            class_name="mt-3 flex items-center justify-between gap-3 rounded-lg border border-zinc-800 bg-zinc-950/60 px-3 py-2",
        ),
        class_name="w-full min-w-0 rounded-lg border border-zinc-800 bg-zinc-900/40 p-3.5",
    )


def _prediction_body(match: BSDMatch) -> rx.Component:
    return rx.el.div(
        rx.el.div(
            _bsd_ml_section(match),
            _poisson_section(match),
            class_name="grid grid-cols-1 gap-3 lg:grid-cols-2",
        ),
        rx.cond(
            BSDState.expanded_id == match["id"],
            rx.el.div(
                _top_models_section(match),
                _meta_section(match),
                _stacking_section(match),
                class_name="mt-3 flex flex-col gap-3",
            ),
            rx.el.div(
                _meta_section(match),
                _stacking_section(match),
                class_name="mt-3",
            ),
        ),
        _stat_facts_section(match),
        rx.cond(
            match["combo_count"] > 0,
            rx.el.div(_combos_section(match), class_name="mt-3"),
            rx.el.div(
                unavailable_note(
                    "Комбинираните маркети не се достапни без веројатности за ГГ и Над 2.5"
                ),
                class_name="mt-3",
            ),
        ),
        class_name="w-full",
    )


def _unavailable_body(match: BSDMatch) -> rx.Component:
    return rx.el.div(
        unavailable_note(match["prediction_note"]),
        rx.el.div(
            _stat_tile("BSD ML", "Недостапно", "нема предвидување"),
            _stat_tile(
                "Очекувани голови",
                rx.cond(
                    match["expected_goals"] > 0,
                    f"{match['expected_goals']:.2f}",
                    "Недостапно",
                ),
                "од статистика на настанот",
            ),
            _stat_tile("Најверојатен резултат", "Недостапно", "нема модел"),
            _stat_tile("Meta-Ensemble", "Недостапно", "нема препорака"),
            class_name="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4",
        ),
        class_name="w-full",
    )


def match_card(match: BSDMatch) -> rx.Component:
    return rx.el.div(
        _match_header(match),
        rx.el.div(
            rx.cond(
                match["has_prediction"],
                _prediction_body(match),
                _unavailable_body(match),
            ),
            bzz_source_section(match),
            fudbal91_match_context(match),
            rx.cond(
                match["has_prediction"],
                rx.el.button(
                    rx.cond(
                        BSDState.expanded_id == match["id"],
                        rx.el.span("Сокрий детали и сите маркети"),
                        rx.el.span("Прикажи топ 3 модели и сите маркети"),
                    ),
                    rx.icon(
                        "chevron-down",
                        class_name=rx.cond(
                            BSDState.expanded_id == match["id"],
                            "h-3.5 w-3.5 rotate-180 transition-transform",
                            "h-3.5 w-3.5 transition-transform",
                        ),
                    ),
                    on_click=lambda: BSDState.toggle_expanded(match["id"]),
                    class_name="mt-3 flex w-full items-center justify-center gap-2 rounded-lg border border-zinc-800 bg-zinc-950/50 px-3 py-2 text-xs font-semibold text-zinc-400 transition-colors hover:border-zinc-700 hover:text-white",
                ),
                rx.fragment(),
            ),
            class_name="p-3.5 sm:p-4",
        ),
        class_name="w-full rounded-xl border border-zinc-800 bg-zinc-900/50 transition-colors hover:border-zinc-700",
    )
