import reflex as rx

from app.components.customer_forms import feedback
from app.components.customer_pages import (
    account_guard,
    checkout_order,
    page_heading,
)
from app.components.public_layout import (
    action_link,
    contact_links,
    public_layout,
)
from app.states.customer_state import CustomerState


__all__ = ["new_customer_checkout_page"]


def checkout_steps() -> rx.Component:
    return rx.el.ol(
        rx.el.li(
            rx.icon(
                "clipboard-list",
                class_name="h-5 w-5 text-[var(--studio-accent)]",
            ),
            rx.el.div(
                rx.el.h2(
                    "01 · Review your piece",
                    class_name="text-sm font-medium text-[var(--studio-text)]",
                ),
                rx.el.p(
                    "Check the quantity and saved total. Confirm provisional portrait pricing with the artist.",
                    class_name="mt-2 text-xs leading-6 text-[var(--studio-text)]/65",
                ),
            ),
            class_name="flex items-start gap-4 border border-[var(--studio-text)]/15 p-6",
        ),
        rx.el.li(
            rx.icon(
                "qr-code", class_name="h-5 w-5 text-[var(--studio-accent)]"
            ),
            rx.el.div(
                rx.el.h2(
                    "02 · Verify before paying",
                    class_name="text-sm font-medium text-[var(--studio-text)]",
                ),
                rx.el.p(
                    "Use only the studio-uploaded QR below. Verify the recipient in your UPI app before paying the agreed quote.",
                    class_name="mt-2 text-xs leading-6 text-[var(--studio-text)]/65",
                ),
            ),
            class_name="flex items-start gap-4 border border-[var(--studio-text)]/15 p-6",
        ),
        rx.el.li(
            rx.icon(
                "image-up", class_name="h-5 w-5 text-[var(--studio-accent)]"
            ),
            rx.el.div(
                rx.el.h2(
                    "03 · Submit for review",
                    class_name="text-sm font-medium text-[var(--studio-text)]",
                ),
                rx.el.p(
                    "Upload one real payment screenshot. The artist reviews proof; submission does not automatically confirm payment.",
                    class_name="mt-2 text-xs leading-6 text-[var(--studio-text)]/65",
                ),
            ),
            class_name="flex items-start gap-4 border border-[var(--studio-text)]/15 p-6",
        ),
        aria_label="Checkout guidance",
        class_name="grid grid-cols-1 md:grid-cols-3 gap-4 my-8",
    )


def checkout_empty() -> rx.Component:
    return rx.el.section(
        rx.icon(
            "package-open", class_name="h-10 w-10 text-[var(--studio-accent)]"
        ),
        rx.el.h2(
            "Choose your personal piece.",
            class_name="font-['Cormorant_Garamond'] text-4xl md:text-5xl text-[var(--studio-text)]",
        ),
        rx.el.p(
            "No saved order is selected for checkout. Open an order from your dashboard to review its details and payment steps. If the order could not be found, choose one belonging to your account.",
            class_name="max-w-2xl text-sm leading-7 text-[var(--studio-text)]/65",
        ),
        rx.el.div(
            action_link("Choose from my orders", "/dashboard"),
            action_link("Explore bouquets", "/bouquets"),
            action_link("Book a portrait", "/portraits"),
            class_name="flex flex-wrap justify-center gap-3",
        ),
        class_name="flex flex-col items-center gap-6 text-center border border-[var(--studio-text)]/15 px-6 py-14 md:py-20 mt-8",
    )


def checkout_help() -> rx.Component:
    return rx.el.section(
        rx.el.div(
            rx.icon(
                "message-circle",
                class_name="h-6 w-6 text-[var(--studio-accent)]",
            ),
            rx.el.h2(
                "A little help, if you need it.",
                class_name="font-['Cormorant_Garamond'] text-3xl md:text-4xl text-[var(--studio-text)]",
            ),
            rx.el.p(
                "Unsure about a portrait quote, the payment recipient or an order update? Check with the studio before paying. Keep your order number handy when you get in touch.",
                class_name="max-w-2xl text-sm leading-7 text-[var(--studio-text)]/65",
            ),
            class_name="flex flex-col gap-4 min-w-0",
        ),
        contact_links(),
        class_name="grid grid-cols-1 md:grid-cols-2 gap-8 items-start border-t border-[var(--studio-text)]/15 mt-14 pt-10",
    )


def checkout_content() -> rx.Component:
    return rx.el.div(
        rx.el.div(feedback(), aria_live="polite", class_name="mb-6"),
        rx.cond(
            CustomerState.busy,
            rx.el.div(
                rx.icon("loader-circle", class_name="h-4 w-4 animate-spin"),
                "Saving your payment proof… Please keep this page open.",
                role="status",
                class_name="flex items-center gap-3 text-sm text-[var(--studio-accent)] mb-6",
            ),
        ),
        rx.cond(
            CustomerState.checkout_orders.length() > 0,
            rx.el.div(
                checkout_steps(),
                rx.el.div(
                    rx.icon(
                        "shield-check",
                        class_name="h-5 w-5 shrink-0 text-[var(--studio-accent)]",
                    ),
                    rx.el.p(
                        "Your saved order is shown below. Payment happens in your UPI app, not on this site. Proof uploads are available only for orders awaiting payment and only when the studio has a valid saved QR.",
                        class_name="text-sm leading-7 text-[var(--studio-text)]/65",
                    ),
                    class_name="flex items-start gap-3 border-l-2 border-[var(--studio-accent)] pl-5 mb-8",
                ),
                rx.foreach(CustomerState.checkout_orders, checkout_order),
                class_name="w-full min-w-0",
            ),
            checkout_empty(),
        ),
        checkout_help(),
        class_name="w-full min-w-0",
    )


def new_customer_checkout_page() -> rx.Component:
    """Standalone checkout; future wiring must retain /checkout?order= and load_account_page."""
    return public_layout(
        rx.el.div(
            page_heading(
                "YOUR PERSONAL PIECE · CHECKOUT",
                "The next step, thoughtfully.",
                "Review your saved order, confirm the artist's quote and submit payment proof for a personal review by the studio.",
            ),
            rx.el.nav(
                action_link("Back to my orders", "/dashboard"),
                rx.el.button(
                    rx.icon("refresh-cw", class_name="h-4 w-4"),
                    "Refresh checkout",
                    type="button",
                    on_click=CustomerState.load_account_page,
                    disabled=CustomerState.busy,
                    class_name="inline-flex items-center gap-3 border border-[var(--studio-accent)]/35 px-5 py-3 text-sm text-[var(--studio-accent)] hover:bg-[var(--studio-accent)]/5 disabled:opacity-50 disabled:cursor-not-allowed focus-visible:outline-2 focus-visible:outline-offset-4",
                ),
                aria_label="Checkout navigation",
                class_name="flex flex-wrap items-center gap-4 mb-8",
            ),
            account_guard(checkout_content()),
            class_name="w-full min-w-0 max-w-7xl mx-auto px-6 md:px-10 pb-20",
        ),
    )
