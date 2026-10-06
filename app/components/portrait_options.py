import reflex as rx

from app.components.customer_forms import BUTTON, INPUT
from app.states.admin_state import AdminState
from app.states.store_models import PortraitSize, PortraitStyle


def option_field(
    label: str, name: str, field_id: str, value: str, maximum: int
) -> rx.Component:
    return rx.el.div(
        rx.el.label(
            label,
            html_for=field_id,
            class_name="block text-sm text-[var(--studio-text)] mb-2",
        ),
        rx.el.input(
            name=name,
            id=field_id,
            default_value=value,
            key=value,
            required=True,
            max_length=maximum,
            disabled=AdminState.busy,
            class_name=INPUT,
        ),
    )


def size_editor(size: PortraitSize) -> rx.Component:
    return rx.el.article(
        rx.el.h3(
            size["name"],
            class_name="font-['Cormorant_Garamond'] text-3xl text-[var(--studio-text)] break-words",
        ),
        rx.el.p(
            f"{size['dimensions']} · provisional ₹{size['price_paise'] / 100:,.2f}",
            class_name="text-sm text-[var(--studio-text)]/65 mt-2 mb-5",
        ),
        rx.el.form(
            option_field(
                "Size label",
                "name",
                f"size-name-{size['id']}",
                size["name"],
                80,
            ),
            option_field(
                "Dimensions",
                "dimensions",
                f"size-dimensions-{size['id']}",
                size["dimensions"],
                120,
            ),
            option_field(
                "Provisional price in rupees (up to 2 decimals)",
                "price",
                f"size-price-{size['id']}",
                f"{size['price_paise'] / 100:.2f}",
                16,
            ),
            rx.el.button(
                rx.cond(AdminState.busy, "Saving…", "Save size"),
                rx.icon("check", class_name="h-4 w-4"),
                type="submit",
                disabled=AdminState.busy,
                class_name=BUTTON,
            ),
            on_submit=lambda data: AdminState.save_portrait_option(
                "size", size["id"], data
            ),
            class_name="flex flex-col gap-4",
        ),
        rx.el.button(
            "Remove size",
            rx.icon("trash-2", class_name="h-4 w-4"),
            type="button",
            on_click=lambda: AdminState.request_portrait_delete(
                "size", size["id"]
            ),
            disabled=AdminState.busy,
            class_name="flex items-center gap-2 mt-5 text-sm text-[var(--studio-accent)] hover:underline",
        ),
        key=size["id"],
        class_name="w-full min-w-0 border border-[var(--studio-text)]/15 p-6",
    )


def style_editor(style: PortraitStyle) -> rx.Component:
    return rx.el.article(
        rx.el.h3(
            style["name"],
            class_name="font-['Cormorant_Garamond'] text-3xl text-[var(--studio-text)] mb-5 break-words",
        ),
        rx.el.form(
            option_field(
                "Art style label",
                "name",
                f"style-name-{style['id']}",
                style["name"],
                80,
            ),
            rx.el.button(
                rx.cond(AdminState.busy, "Saving…", "Save style"),
                rx.icon("check", class_name="h-4 w-4"),
                type="submit",
                disabled=AdminState.busy,
                class_name=BUTTON,
            ),
            on_submit=lambda data: AdminState.save_portrait_option(
                "style", style["id"], data
            ),
            class_name="flex flex-col gap-4",
        ),
        rx.el.button(
            "Remove style",
            rx.icon("trash-2", class_name="h-4 w-4"),
            type="button",
            on_click=lambda: AdminState.request_portrait_delete(
                "style", style["id"]
            ),
            disabled=AdminState.busy,
            class_name="flex items-center gap-2 mt-5 text-sm text-[var(--studio-accent)] hover:underline",
        ),
        key=style["id"],
        class_name="w-full min-w-0 border border-[var(--studio-text)]/15 p-6",
    )


def portrait_options_panel() -> rx.Component:
    return rx.el.section(
        rx.el.h2(
            "Portrait options",
            class_name="font-['Cormorant_Garamond'] text-4xl text-[var(--studio-text)]",
        ),
        rx.el.p(
            "Publish sizes, dimensions, provisional prices and art styles. Names must be unique within each list. Removing an option stops new bookings with it; existing orders retain their original labels and price.",
            class_name="mt-3 mb-7 text-sm leading-7 text-[var(--studio-text)]/65",
        ),
        rx.cond(
            AdminState.error != "",
            rx.el.p(
                AdminState.error,
                role="alert",
                class_name="mb-5 p-4 bg-red-100 text-red-700 text-sm",
            ),
        ),
        rx.cond(
            AdminState.notice != "",
            rx.el.p(
                AdminState.notice,
                role="status",
                class_name="mb-5 p-4 bg-green-100 text-green-700 text-sm",
            ),
        ),
        rx.cond(
            AdminState.busy,
            rx.el.p(
                "Saving portrait options…",
                role="status",
                class_name="mb-5 text-sm text-[var(--studio-accent)]",
            ),
        ),
        rx.cond(
            AdminState.delete_id > 0,
            rx.el.div(
                rx.el.h3(
                    f"Remove {AdminState.delete_name}?",
                    class_name="font-['Cormorant_Garamond'] text-3xl text-[var(--studio-text)]",
                ),
                rx.el.p(
                    "This cannot be undone. Customers must choose another option. Past orders will not change.",
                    class_name="mt-3 text-sm text-[var(--studio-text)]/65",
                ),
                rx.el.div(
                    rx.el.button(
                        "Confirm removal",
                        rx.icon("trash-2", class_name="h-4 w-4"),
                        type="button",
                        on_click=AdminState.confirm_portrait_delete,
                        disabled=AdminState.busy,
                        class_name=BUTTON,
                    ),
                    rx.el.button(
                        "Keep option",
                        type="button",
                        on_click=AdminState.cancel_portrait_delete,
                        disabled=AdminState.busy,
                        class_name="text-sm text-[var(--studio-accent)] underline px-4 py-3",
                    ),
                    class_name="flex flex-wrap gap-3 mt-5",
                ),
                role="alert",
                class_name="border border-[var(--studio-accent)] bg-[var(--studio-accent)]/7 p-6 mb-8",
            ),
        ),
        rx.el.div(
            rx.el.div(
                rx.el.h3(
                    "Add a size",
                    class_name="font-['Cormorant_Garamond'] text-3xl text-[var(--studio-text)] mb-5",
                ),
                rx.el.form(
                    option_field("Size label", "name", "new-size-name", "", 80),
                    option_field(
                        "Dimensions (e.g. 21 × 29.7 cm)",
                        "dimensions",
                        "new-size-dimensions",
                        "",
                        120,
                    ),
                    option_field(
                        "Provisional price in rupees (up to 2 decimals)",
                        "price",
                        "new-size-price",
                        "",
                        16,
                    ),
                    rx.el.button(
                        "Add & publish size",
                        rx.icon("plus", class_name="h-4 w-4"),
                        type="submit",
                        disabled=AdminState.busy,
                        class_name=BUTTON,
                    ),
                    on_submit=lambda data: AdminState.save_portrait_option(
                        "size", 0, data
                    ),
                    class_name="flex flex-col gap-4",
                ),
                class_name="border border-[var(--studio-text)]/15 p-6",
            ),
            rx.el.div(
                rx.el.h3(
                    "Add an art style",
                    class_name="font-['Cormorant_Garamond'] text-3xl text-[var(--studio-text)] mb-5",
                ),
                rx.el.form(
                    option_field(
                        "Art style label", "name", "new-style-name", "", 80
                    ),
                    rx.el.button(
                        "Add & publish style",
                        rx.icon("plus", class_name="h-4 w-4"),
                        type="submit",
                        disabled=AdminState.busy,
                        class_name=BUTTON,
                    ),
                    on_submit=lambda data: AdminState.save_portrait_option(
                        "style", 0, data
                    ),
                    class_name="flex flex-col gap-4",
                ),
                class_name="border border-[var(--studio-text)]/15 p-6",
            ),
            class_name="grid md:grid-cols-2 gap-6 items-start mb-10",
        ),
        rx.el.h3(
            "Current sizes",
            class_name="font-['Cormorant_Garamond'] text-3xl text-[var(--studio-text)] mb-5",
        ),
        rx.cond(
            AdminState.portrait_sizes.length() > 0,
            rx.el.div(
                rx.foreach(AdminState.portrait_sizes, size_editor),
                class_name="grid md:grid-cols-2 xl:grid-cols-3 gap-6",
            ),
            rx.el.p(
                "No sizes published. Add a size above to enable portrait bookings.",
                class_name="p-6 border border-[var(--studio-text)]/15 text-sm text-[var(--studio-text)]/65",
            ),
        ),
        rx.el.h3(
            "Current art styles",
            class_name="font-['Cormorant_Garamond'] text-3xl text-[var(--studio-text)] mt-10 mb-5",
        ),
        rx.cond(
            AdminState.portrait_styles.length() > 0,
            rx.el.div(
                rx.foreach(AdminState.portrait_styles, style_editor),
                class_name="grid md:grid-cols-2 xl:grid-cols-3 gap-6",
            ),
            rx.el.p(
                "No styles published. Add an art style above to enable portrait bookings.",
                class_name="p-6 border border-[var(--studio-text)]/15 text-sm text-[var(--studio-text)]/65",
            ),
        ),
        id="admin-portraits",
        aria_busy=AdminState.busy,
        class_name="w-full min-w-0 py-12 border-t border-[var(--studio-text)]/15 scroll-mt-8",
    )
