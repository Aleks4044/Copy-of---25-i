import reflex as rx


def error_banner(message: rx.Var) -> rx.Component:
    """Црвен, дискретен банер со порака за грешка од API-то."""
    return rx.cond(
        message != "",
        rx.el.div(
            rx.icon(
                "triangle-alert", class_name="h-4 w-4 shrink-0 text-red-400"
            ),
            rx.el.div(
                rx.el.p(
                    "Грешка при поврзување со API-то",
                    class_name="text-xs font-semibold text-red-300",
                ),
                rx.el.p(
                    message,
                    class_name="mt-0.5 text-xs font-medium text-red-300/80",
                ),
                class_name="flex min-w-0 flex-col",
            ),
            class_name="mb-4 flex w-full items-start gap-3 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3",
        ),
        rx.fragment(),
    )


def unavailable_note(message: rx.Var | str) -> rx.Component:
    """Неутрална ознака кога API-то не обезбедува предвидување."""
    return rx.el.div(
        rx.icon("circle-slash", class_name="h-4 w-4 shrink-0 text-zinc-500"),
        rx.el.p(
            message,
            class_name="text-xs font-medium text-zinc-500",
        ),
        class_name="flex w-full items-center gap-2.5 rounded-lg border border-dashed border-zinc-800 bg-zinc-950/40 px-3 py-3",
    )


def warning_banner(message: rx.Var) -> rx.Component:
    """Жолт банер за делумно недостапни детални податоци од API-то."""
    return rx.cond(
        message != "",
        rx.el.div(
            rx.icon("info", class_name="h-4 w-4 shrink-0 text-amber-400"),
            rx.el.div(
                rx.el.p(
                    "Ограничени детални податоци",
                    class_name="text-xs font-semibold text-amber-300",
                ),
                rx.el.p(
                    message,
                    class_name="mt-0.5 text-xs font-medium text-amber-300/80",
                ),
                class_name="flex min-w-0 flex-col",
            ),
            class_name="mb-4 flex w-full items-start gap-3 rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3",
        ),
        rx.fragment(),
    )


def loading_skeleton() -> rx.Component:
    return rx.el.div(
        rx.el.div(
            class_name="h-28 w-full animate-pulse rounded-xl border border-zinc-800 bg-zinc-900/50"
        ),
        rx.el.div(
            class_name="h-28 w-full animate-pulse rounded-xl border border-zinc-800 bg-zinc-900/50"
        ),
        rx.el.div(
            class_name="h-28 w-full animate-pulse rounded-xl border border-zinc-800 bg-zinc-900/50"
        ),
        class_name="mt-4 grid w-full grid-cols-1 gap-4",
    )
