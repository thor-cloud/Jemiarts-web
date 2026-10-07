import reflex as rx

from app.components.public_layout import (
    public_layout,
    action_link,
    contact_links,
)
from app.components.customer_forms import (
    BUTTON,
    feedback,
    field,
    image_picker,
    password_change_form,
)
from app.states.customer_state import CustomerState, OrderView
from app.components.protected_files import protected_file_link


def page_heading(kicker: str, title: str, description: str) -> rx.Component:
    return rx.el.div(
        rx.el.p(
            kicker,
            class_name="text-xs tracking-[0.25em] text-[var(--studio-accent)] mb-5",
        ),
        rx.el.h1(
            title,
            class_name="font-['Cormorant_Garamond'] text-5xl md:text-6xl font-medium leading-tight",
        ),
        rx.el.p(
            description,
            class_name="mt-5 text-base leading-7 text-[var(--studio-text)]/65 max-w-2xl",
        ),
        class_name="pt-14 md:pt-20 pb-10",
    )


def login_page() -> rx.Component:
    return public_layout(
        rx.el.div(
            page_heading(
                "YOUR STUDIO ACCOUNT",
                "A little closer to something personal.",
                "Sign in to order a portrait or bouquet, submit payment proof and follow your orders.",
            ),
            rx.el.div(
                rx.el.div(
                    rx.icon(
                        "flower-2",
                        class_name="h-10 w-10 text-[var(--studio-accent)]",
                    ),
                    rx.el.h2(
                        "Made for you.\nKept in one place.",
                        class_name="font-['Cormorant_Garamond'] text-4xl md:text-5xl whitespace-pre-line mt-7",
                    ),
                    rx.el.p(
                        "Your own order history, reference submissions and next steps. No customer photos or payment screenshots appear in the public gallery.",
                        class_name="mt-6 text-sm leading-7 text-[var(--studio-text)]/65",
                    ),
                    class_name="border border-[var(--studio-accent)]/20 bg-[var(--studio-accent)]/5 p-8 md:p-12",
                ),
                rx.el.div(
                    rx.cond(
                        CustomerState.ready,
                        rx.cond(
                            CustomerState.authenticated
                            & CustomerState.password_change_mode,
                            password_change_form(),
                            rx.fragment(
                                rx.el.h2(
                                    rx.cond(
                                        CustomerState.signup_mode,
                                        "Create your account",
                                        "Welcome back",
                                    ),
                                    class_name="font-['Cormorant_Garamond'] text-4xl mb-6",
                                ),
                                feedback(),
                                rx.el.form(
                                    rx.cond(
                                        CustomerState.signup_mode,
                                        rx.el.div(
                                            field(
                                                "Your name",
                                                "name",
                                                autocomplete="name",
                                            ),
                                            field(
                                                "International phone number",
                                                "phone",
                                                "tel",
                                                placeholder="+91 98765 43210",
                                                autocomplete="tel",
                                            ),
                                            rx.el.p(
                                                "Include + and your country code. This number is not verified by SMS.",
                                                class_name="text-xs leading-6 text-[var(--studio-text)]/60",
                                            ),
                                            field(
                                                "Email (optional)",
                                                "email",
                                                "email",
                                                required=False,
                                                autocomplete="email",
                                            ),
                                            class_name="space-y-5",
                                        ),
                                        field(
                                            "Phone, saved email or owner username",
                                            "identifier",
                                            placeholder="Your phone, email or username",
                                            autocomplete="username",
                                        ),
                                    ),
                                    field(
                                        "Password",
                                        "password",
                                        "password",
                                        autocomplete=rx.cond(
                                            CustomerState.signup_mode,
                                            "new-password",
                                            "current-password",
                                        ),
                                    ),
                                    rx.cond(
                                        CustomerState.signup_mode,
                                        rx.el.div(
                                            rx.el.p(
                                                "Use 12–256 characters. Your optional email can also be used to log in.",
                                                class_name="text-xs leading-6 text-[var(--studio-text)]/60 mb-5",
                                            ),
                                            field(
                                                "Confirm password",
                                                "confirm_password",
                                                "password",
                                                autocomplete="new-password",
                                            ),
                                        ),
                                    ),
                                    rx.el.button(
                                        rx.cond(
                                            CustomerState.busy,
                                            "Please wait…",
                                            rx.cond(
                                                CustomerState.signup_mode,
                                                "Create account",
                                                "Log in",
                                            ),
                                        ),
                                        rx.icon(
                                            "arrow-right", class_name="h-4 w-4"
                                        ),
                                        type="submit",
                                        disabled=CustomerState.busy,
                                        class_name=BUTTON,
                                    ),
                                    on_submit=CustomerState.authenticate_form,
                                    key=CustomerState.signup_mode,
                                    class_name="flex flex-col gap-5 mt-5",
                                ),
                                rx.el.button(
                                    rx.cond(
                                        CustomerState.signup_mode,
                                        "Already have an account? Log in",
                                        "New here? Create an account",
                                    ),
                                    on_click=CustomerState.toggle_signup,
                                    disabled=CustomerState.busy,
                                    type="button",
                                    class_name="text-sm text-[var(--studio-accent)] underline underline-offset-4 mt-6",
                                ),
                            ),
                        ),
                        rx.el.div(
                            rx.el.p(
                                "Loading your account…",
                                role="status",
                                class_name="text-sm text-[var(--studio-text)]/65",
                            ),
                            rx.el.div(
                                class_name="h-64 animate-pulse bg-[var(--studio-text)]/5 mt-5"
                            ),
                        ),
                    ),
                    class_name="p-1 md:p-6",
                ),
                class_name="grid lg:grid-cols-2 gap-10 lg:gap-16 items-start",
            ),
            class_name="w-full max-w-7xl mx-auto px-6 md:px-10 pb-20",
        ),
    )


def order_summary(order: OrderView) -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.el.span(
                f"ORDER #{order['id']}",
                class_name="text-xs tracking-[0.15em] text-[var(--studio-text)]/55",
            ),
            rx.el.span(
                order["created_at"],
                class_name="text-xs text-[var(--studio-text)]/55",
            ),
            class_name="flex flex-wrap items-center justify-between gap-3",
        ),
        rx.el.h2(
            order["title"],
            class_name="font-['Cormorant_Garamond'] text-3xl md:text-4xl mt-5 break-words",
        ),
        rx.el.p(
            f"Quantity {order['quantity']} · ₹{order['unit_price_paise'] / 100:,.2f} each",
            class_name="text-sm text-[var(--studio-text)]/65 mt-3",
        ),
        rx.el.p(
            f"Total ₹{order['total_price_paise'] / 100:,.2f}",
            class_name="text-xl text-[var(--studio-text)] mt-4 font-medium",
        ),
        rx.cond(
            order["provisional"],
            rx.el.p(
                "Provisional example amount — not an artist-confirmed quote. Confirm the final rate with the studio before paying; do not assume this sample amount is payable.",
                class_name="text-xs leading-6 text-[var(--studio-accent)] mt-3",
            ),
        ),
        rx.el.div(
            rx.icon("clock-3", class_name="h-4 w-4"),
            order["status"],
            class_name="w-fit flex items-center gap-2 border border-[var(--studio-accent)]/25 bg-[var(--studio-accent)]/7 text-[var(--studio-accent)] px-3 py-2 text-xs mt-6",
        ),
        rx.el.p(
            order["payment"],
            class_name="text-xs leading-6 text-[var(--studio-text)]/60 mt-3",
        ),
        rx.el.div(
            protected_file_link(
                order["id"],
                "reference",
                order["reference"],
                "Portrait reference",
            ),
            protected_file_link(
                order["id"], "proof", order["proof"], "Payment proof"
            ),
            class_name="flex flex-wrap gap-5 mt-5",
        ),
    )


def order_card(order: OrderView) -> rx.Component:
    return rx.el.article(
        order_summary(order),
        rx.el.a(
            rx.cond(
                order["status"] == "Awaiting payment",
                "Complete checkout",
                "View order",
            ),
            rx.icon("arrow-right", class_name="h-4 w-4"),
            href=f"/checkout?order={order['id']}",
            class_name="inline-flex items-center gap-3 text-sm text-[var(--studio-accent)] border-b border-[var(--studio-accent)]/40 mt-6 pb-1 hover:opacity-70",
        ),
        key=order["id"],
        class_name="border border-[var(--studio-text)]/15 p-6 md:p-8 w-full min-w-0",
    )


def account_guard(content: rx.Component) -> rx.Component:
    return rx.cond(
        CustomerState.ready,
        rx.cond(
            CustomerState.authenticated,
            content,
            rx.el.div(
                feedback(),
                action_link("Log in to continue", "/login"),
                class_name="py-12 space-y-6",
            ),
        ),
        rx.el.div(
            rx.el.p(
                "Loading your account…",
                role="status",
                class_name="text-sm text-[var(--studio-text)]/65",
            ),
            rx.el.div(
                class_name="h-64 animate-pulse bg-[var(--studio-text)]/5 mt-5"
            ),
            class_name="py-12",
        ),
    )


def dashboard_page() -> rx.Component:
    return public_layout(
        rx.el.div(
            account_guard(
                rx.el.div(
                    page_heading(
                        "YOUR ORDERS",
                        f"Hello, {CustomerState.customer_name}.",
                        "Your personal pieces, from first idea to finished work. Payment screenshots are reviewed by the studio; uploading proof does not automatically confirm payment.",
                    ),
                    rx.el.div(
                        action_link("Explore bouquets", "/bouquets"),
                        action_link("Book a portrait", "/portraits"),
                        action_link(
                            "Change password", "/login?password=change"
                        ),
                        rx.el.button(
                            "Refresh orders",
                            rx.icon("refresh-cw", class_name="h-4 w-4"),
                            on_click=CustomerState.load_account_page,
                            class_name="inline-flex items-center gap-2 text-sm text-[var(--studio-accent)] p-3 hover:underline",
                        ),
                        rx.el.button(
                            "Log out",
                            rx.icon("log-out", class_name="h-4 w-4"),
                            on_click=CustomerState.logout,
                            class_name="inline-flex items-center gap-2 text-sm text-[var(--studio-text)] p-3 hover:text-[var(--studio-accent)]",
                        ),
                        class_name="flex flex-wrap items-center gap-4 mb-8",
                    ),
                    feedback(),
                    rx.cond(
                        CustomerState.orders.length() > 0,
                        rx.el.div(
                            rx.foreach(CustomerState.orders, order_card),
                            class_name="grid md:grid-cols-2 gap-6 mt-6",
                        ),
                        rx.el.div(
                            rx.icon(
                                "package-open",
                                class_name="h-10 w-10 text-[var(--studio-accent)]",
                            ),
                            rx.el.h2(
                                "Your story starts here.",
                                class_name="font-['Cormorant_Garamond'] text-4xl",
                            ),
                            rx.el.p(
                                "No orders yet. Choose a bouquet or begin a portrait to see it here.",
                                class_name="text-sm text-[var(--studio-text)]/65",
                            ),
                            class_name="flex flex-col items-center text-center gap-5 py-16 px-6 border border-[var(--studio-text)]/15 mt-6",
                        ),
                    ),
                )
            ),
            class_name="w-full max-w-7xl mx-auto px-6 md:px-10 pb-20",
        )
    )


def checkout_order(order: OrderView) -> rx.Component:
    return rx.el.div(
        rx.el.section(
            order_summary(order),
            class_name="border border-[var(--studio-text)]/15 p-6 md:p-10",
        ),
        rx.el.section(
            rx.cond(
                order["status"] == "Awaiting payment",
                rx.el.div(
                    rx.el.h2(
                        "Payment & proof",
                        class_name="font-['Cormorant_Garamond'] text-4xl mb-5",
                    ),
                    rx.cond(
                        CustomerState.qr_available,
                        rx.el.div(
                            rx.el.div(
                                rx.el.p(
                                    "PAYEE · CONFIRM BEFORE PAYING",
                                    class_name="text-xs tracking-[0.15em] text-gray-600",
                                ),
                                rx.el.h3(
                                    "Sajin",
                                    class_name="font-['Cormorant_Garamond'] text-4xl text-gray-900 mt-2",
                                ),
                                rx.el.p(
                                    "psajin2001@okhdfcbank",
                                    class_name="text-sm font-medium text-gray-900 break-all mt-2",
                                ),
                                rx.el.img(
                                    src=rx.cond(
                                        CustomerState.qr_image_path != "",
                                        rx.get_upload_url(
                                            CustomerState.qr_image_path
                                        ),
                                        CustomerState.qr_image_url,
                                    ),
                                    alt="UPI payment QR — confirm Sajin and psajin2001@okhdfcbank in your payment app",
                                    class_name="w-full max-w-72 aspect-square object-contain bg-white mx-auto mt-5",
                                ),
                                rx.el.p(
                                    rx.cond(
                                        CustomerState.qr_image_path != "",
                                        "Studio-uploaded QR override. Its encoded recipient is not verified by this site; stop and contact the studio if the payee differs from the details above.",
                                        "Built-in UPI QR for Sajin. Enter only the amount agreed with the studio in your UPI app.",
                                    ),
                                    class_name="text-xs leading-6 text-gray-600 mt-4",
                                ),
                                class_name="bg-white text-gray-900 border border-gray-200 p-6 text-center",
                            ),
                            rx.el.p(
                                "Confirm the payee name Sajin and UPI ID psajin2001@okhdfcbank in your UPI app before paying. If either differs, do not pay; contact the studio. Use only the agreed quote. This site does not initiate or verify payments.",
                                class_name="text-xs leading-6 text-[var(--studio-text)]/65 my-5",
                            ),
                            rx.cond(
                                order["provisional"],
                                rx.el.p(
                                    "Portrait quote still provisional: contact the studio before using this QR. Do not pay the example amount without confirmation.",
                                    class_name="text-sm leading-6 text-[var(--studio-accent)] border border-[var(--studio-accent)]/30 p-4 mb-5",
                                ),
                            ),
                            image_picker(
                                "payment-proof",
                                "Choose your payment screenshot",
                            ),
                            rx.el.button(
                                rx.cond(
                                    CustomerState.busy,
                                    "Uploading proof…",
                                    "Upload proof for review",
                                ),
                                rx.icon("upload", class_name="h-4 w-4"),
                                on_click=CustomerState.upload_payment_proof(
                                    rx.upload_files(upload_id="payment-proof")
                                ),
                                disabled=CustomerState.busy
                                | ~CustomerState.qr_available
                                | (
                                    rx.selected_files("payment-proof").length()
                                    != 1
                                ),
                                type="button",
                                class_name=BUTTON,
                            ),
                            rx.el.p(
                                "Submit only a screenshot of a real payment for this order. Crop unrelated balances and personal details. The status changes to payment review only after the file is saved.",
                                class_name="text-xs leading-6 text-[var(--studio-text)]/60 mt-4",
                            ),
                            class_name="space-y-5",
                        ),
                        rx.el.div(
                            rx.icon(
                                "qr-code",
                                class_name="h-10 w-10 text-[var(--studio-accent)]",
                            ),
                            rx.el.h3(
                                "Payment QR unavailable",
                                class_name="font-['Cormorant_Garamond'] text-3xl mt-4",
                            ),
                            rx.el.p(
                                "Your order is saved, but the payment QR could not be loaded. Refresh checkout or contact the studio before paying. Do not use a substitute QR. No payment is claimed and proof submission is disabled until the QR is available.",
                                class_name="text-sm leading-7 text-[var(--studio-text)]/65 mt-4 mb-6",
                            ),
                            contact_links(),
                            class_name="border border-[var(--studio-accent)]/25 bg-[var(--studio-accent)]/5 p-6",
                        ),
                    ),
                ),
                rx.el.div(
                    rx.icon(
                        "clipboard-check",
                        class_name="h-9 w-9 text-[var(--studio-accent)]",
                    ),
                    rx.el.h2(
                        "Follow your order",
                        class_name="font-['Cormorant_Garamond'] text-4xl mt-5",
                    ),
                    rx.el.p(
                        "This order is no longer awaiting payment. You do not need to submit another screenshot. Check your dashboard for the latest status, or contact the studio if you need help.",
                        class_name="text-sm leading-7 text-[var(--studio-text)]/65 mt-5 mb-6",
                    ),
                    contact_links(),
                ),
            ),
            class_name="min-w-0",
        ),
        key=order["id"],
        class_name="grid lg:grid-cols-2 items-start gap-10 lg:gap-16 mt-6",
    )


def checkout_page() -> rx.Component:
    return public_layout(
        rx.el.div(
            account_guard(
                rx.el.div(
                    page_heading(
                        "THE NEXT STEP",
                        "Checkout, thoughtfully.",
                        "Review your saved order. Pay only after confirming the quote, then upload a real payment screenshot for the studio to review.",
                    ),
                    rx.el.div(
                        action_link("Back to my orders", "/dashboard"),
                        rx.el.button(
                            "Refresh checkout",
                            rx.icon("refresh-cw", class_name="h-4 w-4"),
                            on_click=CustomerState.load_account_page,
                            class_name="flex items-center gap-2 p-3 text-sm text-[var(--studio-accent)] hover:underline",
                        ),
                        class_name="flex flex-wrap items-center gap-4 mb-8",
                    ),
                    feedback(),
                    rx.cond(
                        CustomerState.checkout_orders.length() > 0,
                        rx.foreach(
                            CustomerState.checkout_orders, checkout_order
                        ),
                        rx.el.div(
                            rx.el.h2(
                                "Choose an order to continue",
                                class_name="font-['Cormorant_Garamond'] text-3xl",
                            ),
                            rx.el.p(
                                "Open a saved order from your dashboard, or create a new portrait or bouquet order.",
                                class_name="text-sm text-[var(--studio-text)]/65 mt-4",
                            ),
                            class_name="border border-[var(--studio-text)]/15 p-8 mt-6",
                        ),
                    ),
                )
            ),
            class_name="w-full max-w-7xl mx-auto px-6 md:px-10 pb-20",
        )
    )
