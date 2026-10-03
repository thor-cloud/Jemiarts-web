import reflex as rx

from app.states.public_state import PublicState
from app.states.customer_state import CustomerState


def nav_link(label: str, href: str) -> rx.Component:
    return rx.el.a(
        label,
        href=href,
        aria_current=rx.cond(PublicState.active_page == href, "page", "false"),
        class_name=rx.cond(
            PublicState.active_page == href,
            "py-2 text-[var(--studio-accent)] border-b border-[var(--studio-accent)] text-sm font-medium",
            "py-2 text-[var(--studio-text)] border-b border-transparent hover:text-[var(--studio-accent)] text-sm font-medium transition-colors",
        ),
    )


def navigation() -> rx.Component:
    return rx.el.header(
        rx.el.div(
            rx.el.a(
                rx.icon(
                    "flower-2",
                    class_name="h-6 w-6 shrink-0 text-[var(--studio-accent)]",
                ),
                rx.el.span(
                    PublicState.settings["brand_name"],
                    class_name="font-['Cormorant_Garamond'] text-2xl font-semibold break-words",
                ),
                href="/",
                class_name="flex min-w-0 items-center gap-3 text-[var(--studio-text)]",
            ),
            rx.el.nav(
                nav_link("Home", "/"),
                nav_link("Bouquets", "/bouquets"),
                nav_link("Portraits", "/portraits"),
                nav_link("Contact", "#contact"),
                rx.cond(
                    CustomerState.authenticated,
                    nav_link("My orders", "/dashboard"),
                    nav_link("Log in", "/login"),
                ),
                aria_label="Main navigation",
                class_name="hidden md:flex items-center gap-8",
            ),
            rx.el.button(
                rx.cond(
                    PublicState.menu_open,
                    rx.icon("x", class_name="h-5 w-5"),
                    rx.icon("menu", class_name="h-5 w-5"),
                ),
                on_click=PublicState.toggle_menu,
                aria_label="Toggle navigation",
                aria_expanded=PublicState.menu_open,
                aria_controls="mobile-navigation",
                class_name="md:hidden shrink-0 p-3 border border-[var(--studio-text)]/20 rounded-full text-[var(--studio-text)] bg-transparent focus-visible:outline-2",
            ),
            class_name="max-w-7xl mx-auto flex items-center justify-between gap-6 px-6 md:px-10 py-6",
        ),
        rx.cond(
            PublicState.menu_open,
            rx.el.nav(
                nav_link("Home", "/"),
                nav_link("Bouquets", "/bouquets"),
                nav_link("Portraits", "/portraits"),
                nav_link("Contact", "#contact"),
                id="mobile-navigation",
                aria_label="Mobile navigation",
                class_name="md:hidden flex flex-col gap-3 px-6 pb-6 border-t border-[var(--studio-text)]/10",
            ),
        ),
        class_name="w-full bg-[var(--studio-bg)] border-b border-[var(--studio-text)]/10",
    )


def action_link(label: str, href: str) -> rx.Component:
    return rx.el.a(
        label,
        rx.icon("arrow-up-right", class_name="h-4 w-4"),
        href=href,
        class_name="inline-flex w-fit items-center justify-center gap-4 bg-[var(--studio-accent)] text-[var(--studio-bg)] px-6 py-3.5 text-sm font-medium hover:opacity-85 transition-opacity focus-visible:outline-2 focus-visible:outline-offset-4",
    )


def contact_links() -> rx.Component:
    return rx.cond(
        PublicState.settings["contact_number"] != "",
        rx.el.div(
            rx.el.a(
                rx.icon("phone", class_name="h-4 w-4"),
                PublicState.settings["contact_number"],
                href=f"tel:{PublicState.settings['contact_number']}",
                class_name="flex items-center gap-3 text-[var(--studio-text)] hover:text-[var(--studio-accent)]",
            ),
            rx.el.a(
                rx.icon("message-circle", class_name="h-4 w-4"),
                "Enquire on WhatsApp",
                href=PublicState.whatsapp_url,
                target="_blank",
                rel="noopener noreferrer",
                class_name="flex items-center gap-3 text-[var(--studio-accent)] hover:underline",
            ),
            class_name="flex flex-col gap-4 text-sm",
        ),
        rx.el.p(
            "Contact details will be shared here when the studio adds them.",
            class_name="text-sm text-[var(--studio-text)]/65 max-w-xs leading-relaxed",
        ),
    )


def footer() -> rx.Component:
    return rx.el.footer(
        rx.el.div(
            rx.el.div(
                rx.el.p(
                    PublicState.settings["brand_name"],
                    class_name="font-['Cormorant_Garamond'] text-3xl font-semibold",
                ),
                rx.el.p(
                    "A little art. A little heart.",
                    class_name="mt-3 text-sm text-[var(--studio-text)]/65",
                ),
            ),
            rx.el.div(
                rx.el.p(
                    "EXPLORE",
                    class_name="text-xs tracking-[0.2em] text-[var(--studio-text)]/55 mb-5",
                ),
                rx.el.div(
                    nav_link("Home", "/"),
                    nav_link("Bouquets", "/bouquets"),
                    nav_link("Portraits", "/portraits"),
                    class_name="flex flex-col items-start gap-1",
                ),
            ),
            rx.el.div(
                rx.el.p(
                    "LET’S MAKE SOMETHING PERSONAL",
                    class_name="text-xs tracking-[0.15em] text-[var(--studio-text)]/55 mb-5",
                ),
                contact_links(),
            ),
            class_name="grid md:grid-cols-3 gap-10 max-w-7xl mx-auto px-6 md:px-10 py-14",
        ),
        rx.el.div(
            "Portraits & bouquets · Made personal",
            class_name="max-w-7xl mx-auto px-6 md:px-10 pb-6 text-xs text-[var(--studio-text)]/50",
        ),
        id="contact",
        class_name="border-t border-[var(--studio-text)]/15 bg-[var(--studio-bg)] text-[var(--studio-text)] scroll-mt-6",
    )


def public_layout(content: rx.Component) -> rx.Component:
    return rx.el.div(
        rx.el.a(
            "Skip to content",
            href="#main-content",
            class_name="sr-only focus:not-sr-only focus:p-4 text-[var(--studio-text)] bg-[var(--studio-bg)]",
        ),
        navigation(),
        rx.el.main(
            rx.cond(
                PublicState.load_error != "",
                rx.el.div(
                    rx.icon("circle-alert", class_name="h-5 w-5 shrink-0"),
                    rx.el.p(PublicState.load_error),
                    rx.el.button(
                        "Try again",
                        on_click=PublicState.load_public,
                        class_name="underline font-medium",
                    ),
                    role="alert",
                    class_name="flex flex-wrap items-center gap-3 bg-red-100 text-red-700 mx-6 mt-6 p-4 text-sm",
                ),
            ),
            content,
            id="main-content",
            class_name="w-full flex-1 min-w-0",
        ),
        footer(),
        style={
            "--studio-bg": PublicState.settings["background_color"],
            "--studio-text": PublicState.settings["text_color"],
            "--studio-accent": PublicState.settings["accent_color"],
        },
        class_name="min-h-dvh flex flex-col w-full bg-[var(--studio-bg)] text-[var(--studio-text)] font-['DM_Sans'] selection:bg-[var(--studio-accent)]/20",
    )
