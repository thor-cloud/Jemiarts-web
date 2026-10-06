import reflex as rx
from reflex.config import get_config


def protected_file_link(
    order_id: int, kind: str, present: bool, label: str
) -> rx.Component:
    return rx.cond(
        present,
        rx.el.a(
            rx.icon("lock-keyhole", class_name="h-4 w-4"),
            label,
            href=f"{get_config().api_url.rstrip('/')}/order-files/{order_id}/{kind}",
            target="_blank",
            rel="noopener noreferrer",
            aria_label=f"View {label} for order {order_id} (opens in a new tab; sign-in required)",
            class_name="inline-flex items-center gap-2 text-sm text-[var(--studio-accent)] underline underline-offset-4 hover:opacity-75 focus-visible:outline-2 focus-visible:outline-offset-4",
        ),
        rx.el.span(
            f"{label}: not submitted",
            class_name="text-xs text-[var(--studio-text)]/55",
        ),
    )
