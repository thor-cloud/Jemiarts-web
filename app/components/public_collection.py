import reflex as rx

from app.states.public_state import PublicState
from app.states.store_models import Bouquet
from app.components.public_layout import action_link
from app.states.customer_state import CustomerState


def public_image(filename: str, alt: str, classes: str) -> rx.Component:
    return rx.cond(
        filename != "",
        rx.el.img(
            src=rx.get_upload_url(filename),
            alt=alt,
            loading="lazy",
            class_name=classes,
        ),
        rx.el.div(
            rx.icon(
                "image", class_name="h-8 w-8 text-[var(--studio-accent)]/60"
            ),
            rx.el.span(
                "Image coming soon",
                class_name="text-xs text-[var(--studio-text)]/55",
            ),
            class_name="aspect-[4/5] w-full flex flex-col items-center justify-center gap-4 bg-[var(--studio-text)]/5 border border-[var(--studio-text)]/10",
        ),
    )


def bouquet_card(bouquet: Bouquet) -> rx.Component:
    return rx.el.article(
        public_image(
            bouquet["image_path"],
            bouquet["name"],
            "aspect-[4/5] w-full object-cover bg-[var(--studio-text)]/5",
        ),
        rx.el.div(
            rx.el.h2(
                bouquet["name"],
                class_name="font-['Cormorant_Garamond'] text-3xl font-medium break-words",
            ),
            rx.el.p(
                f"₹{bouquet['price_paise'] / 100:,.2f}",
                class_name="text-sm text-[var(--studio-text)]/70 mt-2",
            ),
            rx.el.button(
                "Order Now",
                rx.icon("arrow-up-right", class_name="h-4 w-4"),
                on_click=lambda: CustomerState.select_bouquet(bouquet["id"]),
                class_name="flex items-center gap-3 mt-5 text-sm text-[var(--studio-accent)] border-b border-[var(--studio-accent)]/40 pb-1 hover:opacity-70 focus-visible:outline-2",
            ),
            class_name="pt-5 pb-2",
        ),
        key=bouquet["id"],
        class_name="w-full min-w-0",
    )


def collection() -> rx.Component:
    return rx.cond(
        PublicState.loading,
        rx.el.div(
            rx.foreach(
                [1, 2, 3],
                lambda _: rx.el.div(
                    class_name="aspect-[4/5] animate-pulse bg-[var(--studio-text)]/5"
                ),
            ),
            aria_label="Loading bouquet collection",
            class_name="grid sm:grid-cols-2 lg:grid-cols-3 gap-8",
        ),
        rx.cond(
            PublicState.bouquets.length() > 0,
            rx.el.div(
                rx.foreach(PublicState.bouquets, bouquet_card),
                class_name="grid sm:grid-cols-2 lg:grid-cols-3 gap-x-8 gap-y-12",
            ),
            rx.el.div(
                rx.icon(
                    "flower-2",
                    class_name="h-12 w-12 text-[var(--studio-accent)]",
                ),
                rx.el.p(
                    rx.cond(
                        PublicState.load_error != "",
                        "The collection is temporarily unavailable",
                        "A collection worth waiting for",
                    ),
                    class_name="font-['Cormorant_Garamond'] text-3xl md:text-4xl",
                ),
                rx.el.p(
                    rx.cond(
                        PublicState.load_error != "",
                        "Please try loading the studio again.",
                        "There are no bouquets listed just yet. New designs will appear here as the artist adds them.",
                    ),
                    class_name="text-sm leading-relaxed text-[var(--studio-text)]/65 max-w-md",
                ),
                action_link("Explore personal portraits", "/portraits"),
                class_name="flex flex-col items-center text-center gap-6 border border-[var(--studio-text)]/15 py-20 px-6",
            ),
        ),
    )
