import reflex as rx

from app.components.admin_pages import (
    admin_feedback,
    admin_order,
    bouquet_panel,
    section_title,
    settings_panel,
)
from app.components.customer_pages import page_heading
from app.components.public_layout import action_link, public_layout
from app.states.admin_state import AdminState


__all__ = ["new_admin_dashboard_page"]


def workspace_overview() -> rx.Component:
    return rx.el.div(
        rx.el.article(
            rx.icon(
                "clipboard-list",
                class_name="h-5 w-5 text-[var(--studio-accent)]",
            ),
            rx.el.p(
                "Saved orders",
                class_name="mt-4 text-sm text-[var(--studio-text)]/65",
            ),
            rx.el.p(
                AdminState.orders.length(),
                class_name="mt-2 font-['Cormorant_Garamond'] text-4xl text-[var(--studio-text)]",
            ),
            class_name="w-full border border-[var(--studio-text)]/15 p-6",
        ),
        rx.el.article(
            rx.icon(
                "flower-2", class_name="h-5 w-5 text-[var(--studio-accent)]"
            ),
            rx.el.p(
                "Published bouquets",
                class_name="mt-4 text-sm text-[var(--studio-text)]/65",
            ),
            rx.el.p(
                AdminState.bouquets.length(),
                class_name="mt-2 font-['Cormorant_Garamond'] text-4xl text-[var(--studio-text)]",
            ),
            class_name="w-full border border-[var(--studio-text)]/15 p-6",
        ),
        rx.el.article(
            rx.icon(
                "qr-code", class_name="h-5 w-5 text-[var(--studio-accent)]"
            ),
            rx.el.p(
                "Saved payment QR",
                class_name="mt-4 text-sm text-[var(--studio-text)]/65",
            ),
            rx.el.p(
                rx.cond(
                    AdminState.settings["payment_qr_path"] != "",
                    "Configured",
                    "Not configured",
                ),
                class_name="mt-2 font-['Cormorant_Garamond'] text-3xl text-[var(--studio-text)]",
            ),
            rx.el.p(
                "Review the current image in site settings. Uploads must be saved to publish.",
                class_name="mt-3 text-xs leading-6 text-[var(--studio-text)]/60",
            ),
            class_name="w-full border border-[var(--studio-text)]/15 p-6",
        ),
        class_name="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-10",
    )


def workspace_orders() -> rx.Component:
    return rx.el.section(
        section_title(
            "Every personal piece",
            "Open the saved portrait reference and payment proof, review the order, then choose an available status. A screenshot alone is not payment verification.",
        ),
        rx.el.div(
            rx.icon(
                "message-circle",
                class_name="h-5 w-5 shrink-0 text-[var(--studio-accent)]",
            ),
            rx.el.p(
                "Save a status before opening its WhatsApp draft. The message is prefilled with the saved status; nothing is sent until you choose to send it in WhatsApp.",
                class_name="text-sm leading-7 text-[var(--studio-text)]/65",
            ),
            class_name="flex items-start gap-3 border-l-2 border-[var(--studio-accent)] pl-5 mb-8",
        ),
        rx.cond(
            AdminState.orders.length() > 0,
            rx.el.div(
                rx.foreach(AdminState.orders, admin_order),
                class_name="grid grid-cols-1 xl:grid-cols-2 gap-6 items-start",
            ),
            rx.el.div(
                rx.icon(
                    "package-open",
                    class_name="h-10 w-10 text-[var(--studio-accent)]",
                ),
                rx.el.h3(
                    "Room for the next personal piece.",
                    class_name="font-['Cormorant_Garamond'] text-3xl md:text-4xl text-[var(--studio-text)]",
                ),
                rx.el.p(
                    "No customer orders are saved yet. New orders and their submitted payment proofs will appear here. Refresh to check for updates.",
                    class_name="max-w-xl text-sm leading-7 text-[var(--studio-text)]/65",
                ),
                action_link("Visit the storefront", "/"),
                class_name="flex flex-col items-center gap-5 border border-[var(--studio-text)]/15 px-6 py-14 text-center",
            ),
        ),
        id="admin-orders",
        class_name="w-full min-w-0 pb-12 scroll-mt-8",
    )


def authorized_workspace() -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.icon(
                "shield-check", class_name="h-4 w-4 text-[var(--studio-accent)]"
            ),
            "Studio owner workspace",
            class_name="w-fit flex items-center gap-2 mb-6 text-xs text-[var(--studio-text)]/65",
        ),
        workspace_overview(),
        rx.el.nav(
            action_link("Review orders", "#admin-orders"),
            action_link("Curate bouquets", "#admin-bouquets"),
            action_link("Site settings & QR", "#admin-settings"),
            aria_label="Workspace sections",
            class_name="flex flex-wrap gap-3 mb-12",
        ),
        workspace_orders(),
        bouquet_panel(),
        settings_panel(),
        class_name="w-full min-w-0",
    )


def workspace_access_notice() -> rx.Component:
    return rx.el.section(
        rx.icon(
            "lock-keyhole", class_name="h-10 w-10 text-[var(--studio-accent)]"
        ),
        rx.el.h2(
            "For the studio owner.",
            class_name="font-['Cormorant_Garamond'] text-4xl text-[var(--studio-text)]",
        ),
        rx.el.p(
            "This workspace requires an administrator account. Guests and customer accounts cannot review orders, edit the collection or change site settings. If loading failed, use Refresh workspace to retry.",
            class_name="max-w-2xl text-sm leading-7 text-[var(--studio-text)]/65",
        ),
        rx.el.div(
            action_link("Go to your account", "/login"),
            action_link("Back to the studio", "/"),
            class_name="flex flex-wrap gap-3",
        ),
        class_name="flex flex-col gap-6 border border-[var(--studio-text)]/15 p-6 md:p-10",
    )


def workspace_loading() -> rx.Component:
    return rx.el.div(
        rx.el.p(
            "Checking access and loading the studio workspace…",
            role="status",
            class_name="text-sm leading-7 text-[var(--studio-text)]/65",
        ),
        rx.el.div(class_name="h-24 animate-pulse bg-[var(--studio-text)]/5"),
        rx.el.div(class_name="h-64 animate-pulse bg-[var(--studio-text)]/5"),
        aria_busy=True,
        class_name="w-full space-y-5",
    )


def new_admin_dashboard_page() -> rx.Component:
    """Standalone workspace; future route loading should restore the account and load_admin."""
    return public_layout(
        rx.el.div(
            page_heading(
                "BEHIND THE STUDIO",
                "A thoughtful place to create.",
                "Review personal orders, curate the bouquet gallery and make every detail of your storefront yours.",
            ),
            rx.el.div(
                rx.el.button(
                    rx.icon("refresh-cw", class_name="h-4 w-4"),
                    "Refresh workspace",
                    type="button",
                    on_click=AdminState.load_admin,
                    disabled=AdminState.busy,
                    class_name="inline-flex items-center gap-3 border border-[var(--studio-accent)]/35 px-5 py-3 text-sm text-[var(--studio-accent)] hover:bg-[var(--studio-accent)]/5 disabled:opacity-50 disabled:cursor-not-allowed focus-visible:outline-2 focus-visible:outline-offset-4",
                ),
                action_link("View storefront", "/"),
                class_name="flex flex-wrap items-center gap-4 mb-8",
            ),
            admin_feedback(),
            rx.cond(
                AdminState.busy,
                rx.el.div(
                    rx.icon("loader-circle", class_name="h-4 w-4 animate-spin"),
                    "Saving or uploading… Please wait before refreshing.",
                    role="status",
                    class_name="flex items-center gap-3 mb-6 text-sm text-[var(--studio-accent)]",
                ),
            ),
            rx.cond(
                AdminState.ready,
                rx.cond(
                    AdminState.allowed,
                    authorized_workspace(),
                    workspace_access_notice(),
                ),
                workspace_loading(),
            ),
            class_name="w-full min-w-0 max-w-7xl mx-auto px-6 md:px-10 pb-20",
        ),
    )
