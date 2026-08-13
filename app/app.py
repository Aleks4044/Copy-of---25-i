import reflex as rx

from app.components.bsd_predictions import bsd_predictions
from app.components.header import header
from app.components.markets_view import markets_view
from app.components.models_view import models_view
from app.components.mutating_panel import mutating_panel
from app.components.overview import overview
from app.components.sportscore_view import sportscore_view
from app.components.tab_nav import tab_nav
from app.states.app_state import AppState
from app.states.bsd_state import BSDState
from app.states.markets_state import MarketsState
from app.states.overview_state import OverviewState


def tab_content() -> rx.Component:
    return rx.match(
        AppState.active_tab,
        ("home", overview()),
        ("bsd", bsd_predictions()),
        ("models", models_view()),
        ("markets", markets_view()),
        ("sources", mutating_panel()),
        ("sportscore", sportscore_view()),
        overview(),
    )


def index() -> rx.Component:
    return rx.el.main(
        header(),
        tab_nav(),
        rx.el.div(
            tab_content(),
            class_name="mx-auto w-full max-w-7xl px-4 py-5 sm:px-6 sm:py-6",
        ),
        rx.el.footer(
            rx.el.p(
                "BSD Фудбал · Статистичките предвидувања не гарантираат исход",
                class_name="text-xs font-medium text-zinc-600",
            ),
            class_name="mx-auto w-full max-w-7xl border-t border-zinc-800/70 px-4 py-6 sm:px-6",
        ),
        class_name="min-h-screen w-full bg-zinc-950 font-['Inter'] antialiased",
    )


app = rx.App(
    theme=rx.theme(appearance="light"),
    head_components=[
        rx.el.link(rel="preconnect", href="https://fonts.googleapis.com"),
        rx.el.link(
            rel="preconnect",
            href="https://fonts.gstatic.com",
            cross_origin="",
        ),
        rx.el.link(
            href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap",
            rel="stylesheet",
        ),
    ],
)
app.add_page(
    index,
    route="/",
    title="BSD Фудбал · Предвидувања",
    # Само примарните податоци за почетниот приказ се вчитуваат веднаш;
    # бавните јавни извори се вчитуваат кога корисникот ќе го отвори
    # соодветниот таб или при бавен круг на автоматското освежување.
    on_load=[
        BSDState.load,
        OverviewState.load,
        MarketsState.load,
        AppState.start_clock,
    ],
)
