import reflex as rx

from app.components.public_layout import public_layout, action_link
from app.components.customer_pages import page_heading
from app.components.customer_forms import BUTTON, INPUT
from app.components.public_collection import public_image
from app.states.admin_state import AdminState, AdminOrder
from app.states.store_models import Bouquet


SETTINGS_FIELDS: list[dict[str, str]] = [
    {"key": "brand_name", "label": "Brand name", "type": "text"},
    {
        "key": "background_color",
        "label": "Ivory / background color",
        "type": "color",
    },
    {"key": "text_color", "label": "Charcoal / text color", "type": "color"},
    {
        "key": "accent_color",
        "label": "Terracotta / accent color",
        "type": "color",
    },
    {
        "key": "contact_number",
        "label": "Contact / WhatsApp number (include + and country code)",
        "type": "tel",
    },
]


def admin_feedback() -> rx.Component:
    return rx.el.div(
        rx.cond(
            AdminState.error != "",
            rx.el.p(
                AdminState.error,
                role="alert",
                class_name="bg-red-100 text-red-700 p-4 text-sm leading-6",
            ),
        ),
        rx.cond(
            AdminState.notice != "",
            rx.el.p(
                AdminState.notice,
                role="status",
                class_name="bg-green-100 text-green-700 p-4 text-sm leading-6",
            ),
        ),
        aria_live="polite",
        class_name="space-y-3 mb-6",
    )


def section_title(title: str, description: str) -> rx.Component:
    return rx.el.div(
        rx.el.h2(
            title,
            class_name="font-['Cormorant_Garamond'] text-4xl text-[var(--studio-text)]",
        ),
        rx.el.p(
            description,
            class_name="mt-3 text-sm leading-7 text-[var(--studio-text)]/65",
        ),
        class_name="mb-7",
    )


def upload_link(filename: str, label: str) -> rx.Component:
    return rx.cond(
        filename != "",
        rx.el.a(
            rx.icon("image", class_name="h-4 w-4"),
            label,
            href=rx.get_upload_url(filename),
            target="_blank",
            rel="noopener noreferrer",
            class_name="inline-flex items-center gap-2 text-sm text-[var(--studio-accent)] underline underline-offset-4",
        ),
        rx.el.span(
            f"{label}: not submitted",
            class_name="text-xs text-[var(--studio-text)]/55",
        ),
    )


def admin_order(order: AdminOrder) -> rx.Component:
    return rx.el.article(
        rx.el.div(
            rx.el.div(
                rx.el.p(
                    f"ORDER #{order['id']} · {order['date']}",
                    class_name="text-xs tracking-widest text-[var(--studio-text)]/55",
                ),
                rx.el.h3(
                    order["title"],
                    class_name="font-['Cormorant_Garamond'] text-3xl mt-3 text-[var(--studio-text)] break-words",
                ),
                rx.el.p(
                    order["name"],
                    class_name="text-sm font-medium mt-3 text-[var(--studio-text)]",
                ),
                rx.el.a(
                    order["phone"],
                    href=f"tel:{order['phone']}",
                    class_name="text-sm text-[var(--studio-text)]/65 hover:underline",
                ),
            ),
            rx.el.p(
                f"₹{order['amount']:,.2f}",
                class_name="text-xl font-medium text-[var(--studio-text)]",
            ),
            class_name="flex flex-wrap justify-between gap-5",
        ),
        rx.el.p(
            order["status"].split("_").join(" "),
            class_name="w-fit mt-5 px-3 py-2 text-xs bg-[var(--studio-accent)]/10 text-[var(--studio-accent)]",
        ),
        rx.el.div(
            upload_link(order["reference"], "Portrait reference"),
            upload_link(order["proof"], "Payment proof"),
            class_name="flex flex-wrap gap-5 mt-5",
        ),
        rx.el.form(
            rx.el.label(
                "Next status",
                html_for=f"order-status-{order['id']}",
                class_name="text-sm text-[var(--studio-text)]",
            ),
            rx.el.div(
                rx.el.select(
                    rx.foreach(
                        order["options"],
                        lambda status: rx.el.option(
                            status.split("_").join(" "), value=status
                        ),
                    ),
                    name="status",
                    id=f"order-status-{order['id']}",
                    default_value=order["status"],
                    key=order["status"],
                    disabled=AdminState.busy,
                    class_name="w-full appearance-none bg-[var(--studio-bg)] text-[var(--studio-text)] border border-[var(--studio-text)]/25 px-4 py-3 pr-10 text-sm focus-visible:outline-2",
                ),
                rx.icon(
                    "chevron-down",
                    class_name="absolute right-3 top-3.5 h-4 w-4 pointer-events-none text-[var(--studio-text)]",
                ),
                class_name="relative flex-1 min-w-48",
            ),
            rx.el.button(
                "Save status",
                type="submit",
                disabled=AdminState.busy | (order["options"].length() == 1),
                class_name=BUTTON,
            ),
            on_submit=lambda data: AdminState.save_status(order["id"], data),
            class_name="flex flex-wrap items-center gap-3 mt-6",
        ),
        rx.el.a(
            rx.icon("message-circle", class_name="h-4 w-4"),
            "Open WhatsApp draft",
            href=order["whatsapp"],
            target="_blank",
            rel="noopener noreferrer",
            class_name="inline-flex gap-2 items-center text-sm text-[var(--studio-accent)] hover:underline mt-5",
        ),
        key=order["id"],
        class_name="w-full min-w-0 border border-[var(--studio-text)]/15 p-6 md:p-8",
    )


def admin_picker(upload_id: str, target: str) -> rx.Component:
    return rx.el.div(
        rx.upload.root(
            rx.icon(
                "image-plus", class_name="h-7 w-7 text-[var(--studio-accent)]"
            ),
            rx.el.p(
                rx.cond(
                    target == "payment-qr",
                    "Choose an optional studio UPI QR PNG override",
                    "Choose one image",
                ),
                class_name="text-sm text-[var(--studio-text)]",
            ),
            rx.el.p(
                rx.cond(
                    target == "payment-qr",
                    "PNG only · up to 10 MB",
                    "JPEG, PNG or WebP · up to 10 MB",
                ),
                class_name="text-xs text-[var(--studio-text)]/60",
            ),
            id=upload_id,
            multiple=False,
            max_files=1,
            disabled=AdminState.busy,
            accept=rx.cond(
                target == "payment-qr",
                {"image/png": [".png"]},
                {
                    "image/jpeg": [".jpg", ".jpeg"],
                    "image/png": [".png"],
                    "image/webp": [".webp"],
                },
            ),
            class_name="flex flex-col items-center gap-3 p-6 border border-dashed border-[var(--studio-text)]/25 bg-transparent cursor-pointer",
        ),
        rx.foreach(
            rx.selected_files(upload_id),
            lambda name: rx.el.p(
                name,
                class_name="text-xs break-all mt-3 text-[var(--studio-text)]/65",
            ),
        ),
        rx.el.div(
            rx.el.button(
                "Upload selected image",
                rx.icon("upload", class_name="h-4 w-4"),
                type="button",
                on_click=rx.match(
                    target,
                    (
                        "bouquet",
                        AdminState.stage_bouquet_image(
                            rx.upload_files(upload_id=upload_id)
                        ),
                    ),
                    (
                        "hero",
                        AdminState.stage_hero_image(
                            rx.upload_files(upload_id=upload_id)
                        ),
                    ),
                    AdminState.stage_payment_qr_image(
                        rx.upload_files(upload_id=upload_id)
                    ),
                ),
                disabled=AdminState.busy
                | (rx.selected_files(upload_id).length() == 0),
                class_name=BUTTON,
            ),
            rx.el.button(
                "Clear selection",
                type="button",
                on_click=rx.clear_selected_files(upload_id),
                disabled=AdminState.busy,
                class_name="text-sm text-[var(--studio-accent)] underline p-3",
            ),
            class_name="flex flex-wrap gap-3 mt-4",
        ),
        rx.el.p(
            "Upload first, then save the form to publish. A failed save keeps the uploaded image for retry.",
            class_name="text-xs leading-6 mt-3 text-[var(--studio-text)]/60",
        ),
        class_name="space-y-3",
    )


def edit_card(bouquet: Bouquet) -> rx.Component:
    return rx.el.article(
        public_image(
            bouquet["image_path"],
            bouquet["name"],
            "w-full aspect-[4/5] object-cover bg-[var(--studio-text)]/5",
        ),
        rx.el.h3(
            bouquet["name"],
            class_name="font-['Cormorant_Garamond'] text-2xl mt-4 text-[var(--studio-text)] break-words",
        ),
        rx.el.p(
            f"₹{bouquet['price_paise'] / 100:,.2f}",
            class_name="text-sm text-[var(--studio-text)]/65 mt-2",
        ),
        rx.el.button(
            "Edit bouquet",
            rx.icon("pencil", class_name="h-4 w-4"),
            on_click=lambda: AdminState.edit_bouquet(bouquet["id"]),
            disabled=AdminState.busy,
            class_name="flex gap-2 items-center mt-4 text-sm text-[var(--studio-accent)] hover:underline",
        ),
        key=bouquet["id"],
        class_name="w-full min-w-0",
    )


def bouquet_panel() -> rx.Component:
    return rx.el.section(
        section_title(
            "The bouquet collection",
            "Publish a new piece or edit a saved design. Existing orders keep their original price.",
        ),
        rx.el.div(
            rx.el.div(
                rx.el.h3(
                    rx.cond(
                        AdminState.bouquet_id > 0, "Edit bouquet", "New bouquet"
                    ),
                    class_name="font-['Cormorant_Garamond'] text-3xl mb-5",
                ),
                rx.cond(
                    AdminState.bouquet_image != "",
                    rx.el.img(
                        src=rx.get_upload_url(AdminState.bouquet_image),
                        alt="Bouquet image ready for saving",
                        class_name="w-40 aspect-[4/5] object-cover mb-5",
                    ),
                ),
                admin_picker("admin-bouquet", "bouquet"),
                rx.el.form(
                    rx.el.label(
                        "Bouquet name",
                        html_for="bouquet-name",
                        class_name="text-sm",
                    ),
                    rx.el.input(
                        name="name",
                        id="bouquet-name",
                        required=True,
                        max_length=160,
                        default_value=AdminState.bouquet_name,
                        key=AdminState.bouquet_name,
                        class_name=INPUT,
                    ),
                    rx.el.label(
                        "Price in rupees",
                        html_for="bouquet-price",
                        class_name="text-sm",
                    ),
                    rx.el.input(
                        name="price",
                        id="bouquet-price",
                        type="number",
                        min="0",
                        max="10000000",
                        step="0.01",
                        required=True,
                        default_value=AdminState.bouquet_price,
                        key=AdminState.bouquet_price,
                        class_name=INPUT,
                    ),
                    rx.el.button(
                        "Save & publish bouquet",
                        type="submit",
                        disabled=AdminState.busy,
                        class_name=BUTTON,
                    ),
                    on_submit=AdminState.save_bouquet,
                    class_name="flex flex-col gap-3 mt-6",
                ),
                rx.el.button(
                    "Start a new bouquet",
                    type="button",
                    on_click=AdminState.new_bouquet,
                    disabled=AdminState.busy,
                    class_name="text-sm text-[var(--studio-accent)] underline mt-5",
                ),
                id="bouquet-editor",
                class_name="w-full border border-[var(--studio-text)]/15 p-6 md:p-8 scroll-mt-6",
            ),
            rx.cond(
                AdminState.bouquets.length() > 0,
                rx.el.div(
                    rx.foreach(AdminState.bouquets, edit_card),
                    class_name="grid sm:grid-cols-2 gap-x-6 gap-y-10",
                ),
                rx.el.p(
                    "No bouquets published yet. Add your first design here.",
                    class_name="text-sm leading-7 text-[var(--studio-text)]/65 border border-[var(--studio-text)]/15 p-8",
                ),
            ),
            class_name="grid lg:grid-cols-2 gap-10 items-start",
        ),
        id="admin-bouquets",
        class_name="py-12 border-t border-[var(--studio-text)]/15",
    )


def setting_field(item: dict[str, str]) -> rx.Component:
    return rx.el.div(
        rx.el.label(
            item["label"],
            html_for=item["key"],
            class_name="block text-sm text-[var(--studio-text)] mb-2",
        ),
        rx.el.input(
            name=item["key"],
            id=item["key"],
            type=item["type"],
            default_value=AdminState.settings[item["key"]],
            key=AdminState.settings[item["key"]],
            required=item["type"] != "tel",
            max_length=120,
            class_name=INPUT,
        ),
    )


def settings_panel() -> rx.Component:
    return rx.el.section(
        section_title(
            "Make the studio yours",
            "Saved changes appear throughout the storefront. Keep the current banner by leaving its upload unchanged.",
        ),
        rx.el.div(
            rx.el.form(
                rx.foreach(SETTINGS_FIELDS, setting_field),
                rx.el.label(
                    "Welcome text",
                    html_for="welcome_text",
                    class_name="text-sm",
                ),
                rx.el.textarea(
                    name="welcome_text",
                    id="welcome_text",
                    default_value=AdminState.settings["welcome_text"],
                    key=AdminState.settings["welcome_text"],
                    max_length=4000,
                    rows=4,
                    class_name=INPUT,
                ),
                rx.el.label(
                    "Artist biography",
                    html_for="artist_biography",
                    class_name="text-sm",
                ),
                rx.el.textarea(
                    name="artist_biography",
                    id="artist_biography",
                    default_value=AdminState.settings["artist_biography"],
                    key=AdminState.settings["artist_biography"],
                    max_length=12000,
                    rows=7,
                    class_name=INPUT,
                ),
                rx.el.button(
                    "Save site settings",
                    type="submit",
                    disabled=AdminState.busy,
                    class_name=BUTTON,
                ),
                on_submit=AdminState.save_settings,
                class_name="flex flex-col gap-4",
            ),
            rx.el.div(
                rx.el.h3(
                    "Hero banner (optional)",
                    class_name="font-['Cormorant_Garamond'] text-3xl mb-5",
                ),
                rx.cond(
                    AdminState.hero_image != "",
                    rx.el.img(
                        src=rx.get_upload_url(AdminState.hero_image),
                        alt="Current or staged studio banner",
                        class_name="w-full aspect-[16/9] object-cover mb-6",
                    ),
                ),
                admin_picker("admin-hero", "hero"),
                rx.el.h3(
                    "Artist UPI payment QR",
                    class_name="font-['Cormorant_Garamond'] text-3xl mt-10 mb-5",
                ),
                rx.el.p(
                    "Checkout automatically generates a scannable UPI QR for Sajin at psajin2001@okhdfcbank; no upload is required. To override it, upload your studio-owned QR as a PNG, then save site settings. A valid saved PNG takes priority; a missing or invalid saved image falls back to the built-in QR. Keep the override addressed to the same payee. PNG validation does not verify the encoded recipient or any payment. Customers must confirm the name and UPI ID in their UPI app, and you must review payment proof manually.",
                    class_name="text-sm leading-7 text-[var(--studio-text)]/65 mb-5",
                ),
                rx.cond(
                    AdminState.payment_qr_image != "",
                    rx.el.img(
                        src=rx.get_upload_url(AdminState.payment_qr_image),
                        alt="Artist-uploaded current or staged UPI QR",
                        class_name="w-full max-w-64 aspect-square object-contain bg-white p-4 mb-6",
                    ),
                    rx.el.p(
                        "No override image selected. Without a valid saved override, checkout uses the built-in QR for Sajin. Proof submission still requires a signed-in customer and their own order awaiting payment.",
                        class_name="text-sm leading-7 text-[var(--studio-accent)] mb-5",
                    ),
                ),
                admin_picker("admin-payment-qr", "payment-qr"),
                class_name="border border-[var(--studio-text)]/15 p-6 md:p-8",
            ),
            class_name="grid lg:grid-cols-2 gap-10 items-start",
        ),
        id="admin-settings",
        class_name="py-12 border-t border-[var(--studio-text)]/15",
    )


def admin_workspace() -> rx.Component:
    return rx.el.div(
        rx.el.nav(
            action_link("Orders", "#admin-orders"),
            action_link("Bouquets", "#admin-bouquets"),
            action_link("Site settings", "#admin-settings"),
            aria_label="Studio workspace sections",
            class_name="flex flex-wrap gap-4 mb-10",
        ),
        rx.el.section(
            section_title(
                "Every personal piece",
                "Review reference images and payment proof before confirming. WhatsApp links open editable drafts only — you choose whether to send.",
            ),
            rx.cond(
                AdminState.orders.length() > 0,
                rx.el.div(
                    rx.foreach(AdminState.orders, admin_order),
                    class_name="grid xl:grid-cols-2 gap-6",
                ),
                rx.el.p(
                    "No orders yet. Customer orders will appear here when they are placed.",
                    class_name="text-sm text-[var(--studio-text)]/65 border border-[var(--studio-text)]/15 p-8",
                ),
            ),
            id="admin-orders",
            class_name="pb-12",
        ),
        bouquet_panel(),
        settings_panel(),
    )


def admin_page() -> rx.Component:
    return public_layout(
        rx.el.div(
            page_heading(
                "YOUR STUDIO WORKSPACE",
                "Behind every personal piece.",
                "A thoughtful place to review orders, curate bouquets and update your storefront.",
            ),
            rx.el.button(
                rx.icon("refresh-cw", class_name="h-4 w-4"),
                "Refresh workspace",
                on_click=AdminState.load_admin,
                disabled=AdminState.busy,
                class_name="inline-flex items-center gap-2 text-sm text-[var(--studio-accent)] hover:underline mb-6",
            ),
            admin_feedback(),
            rx.cond(
                AdminState.busy,
                rx.el.p(
                    "Saving / uploading…",
                    role="status",
                    class_name="text-sm text-[var(--studio-accent)] mb-5",
                ),
            ),
            rx.cond(
                AdminState.ready,
                rx.cond(
                    AdminState.allowed,
                    admin_workspace(),
                    rx.el.div(
                        rx.icon(
                            "lock-keyhole",
                            class_name="h-9 w-9 text-[var(--studio-accent)]",
                        ),
                        rx.el.h2(
                            "For the studio owner",
                            class_name="font-['Cormorant_Garamond'] text-4xl",
                        ),
                        rx.el.p(
                            "Guest and customer accounts cannot access this workspace. Sign in with an administrator account to continue.",
                            class_name="text-sm leading-7 text-[var(--studio-text)]/65",
                        ),
                        action_link("Go to your account", "/login"),
                        class_name="border border-[var(--studio-text)]/15 p-8 flex flex-col gap-5",
                    ),
                ),
                rx.el.div(
                    rx.el.p(
                        "Loading studio workspace…",
                        role="status",
                        class_name="text-sm text-[var(--studio-text)]/65",
                    ),
                    rx.el.div(
                        class_name="h-64 bg-[var(--studio-text)]/5 animate-pulse mt-5"
                    ),
                ),
            ),
            class_name="w-full max-w-7xl mx-auto px-6 md:px-10 pb-20",
        ),
    )
