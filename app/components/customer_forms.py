import reflex as rx

from app.states.customer_state import CustomerState


BUTTON = "inline-flex items-center justify-center gap-3 bg-[var(--studio-accent)] text-[var(--studio-bg)] px-6 py-4 text-sm font-medium hover:opacity-85 disabled:opacity-50 disabled:cursor-not-allowed focus-visible:outline-2 focus-visible:outline-offset-4"
INPUT = "w-full bg-transparent text-[var(--studio-text)] border border-[var(--studio-text)]/25 px-4 py-3 text-sm focus:border-[var(--studio-accent)] focus-visible:outline-2 focus-visible:outline-[var(--studio-accent)]"


def feedback() -> rx.Component:
    return rx.el.div(
        rx.cond(
            CustomerState.error != "",
            rx.el.p(
                CustomerState.error,
                role="alert",
                class_name="bg-red-100 text-red-700 p-4 text-sm leading-6",
            ),
        ),
        rx.cond(
            CustomerState.notice != "",
            rx.el.p(
                CustomerState.notice,
                role="status",
                class_name="bg-green-100 text-green-700 p-4 text-sm leading-6",
            ),
        ),
        class_name="space-y-3",
    )


def field(
    label: str,
    name: str,
    kind: str = "text",
    required: bool = True,
    placeholder: str = "",
    autocomplete: str = "",
) -> rx.Component:
    return rx.el.div(
        rx.el.label(
            label,
            html_for=name,
            class_name="block text-sm text-[var(--studio-text)] mb-2",
        ),
        rx.el.input(
            id=name,
            name=name,
            type=kind,
            required=required,
            placeholder=placeholder,
            auto_complete=autocomplete,
            max_length=256,
            class_name=INPUT,
        ),
    )


def password_change_form() -> rx.Component:
    return rx.el.div(
        rx.icon(
            "shield-check",
            class_name="h-8 w-8 text-[var(--studio-accent)] mb-5",
        ),
        rx.el.h2(
            rx.cond(
                CustomerState.must_change_password,
                "Make this account yours.",
                "Change your password",
            ),
            class_name="font-['Cormorant_Garamond'] text-4xl text-[var(--studio-text)] mb-5",
        ),
        rx.el.p(
            rx.cond(
                CustomerState.must_change_password,
                "Before opening the studio workspace, choose a personal password. Orders and workspace controls remain locked until this step is complete.",
                "Choose a new password to keep your account secure. Other signed-in sessions will be signed out; you will stay signed in here.",
            ),
            class_name="text-sm leading-7 text-[var(--studio-text)]/65 mb-6",
        ),
        feedback(),
        rx.el.form(
            rx.el.fieldset(
                field(
                    "Current password",
                    "current_password",
                    "password",
                    autocomplete="current-password",
                ),
                field(
                    "New password",
                    "new_password",
                    "password",
                    autocomplete="new-password",
                ),
                rx.el.p(
                    "Use 12–256 characters, different from your current password.",
                    class_name="text-xs leading-6 text-[var(--studio-text)]/60",
                ),
                field(
                    "Confirm new password",
                    "confirm_password",
                    "password",
                    autocomplete="new-password",
                ),
                disabled=CustomerState.busy,
                class_name="flex flex-col gap-5",
            ),
            rx.el.button(
                rx.cond(
                    CustomerState.busy,
                    "Updating password…",
                    "Save password & continue",
                ),
                rx.icon("arrow-right", class_name="h-4 w-4"),
                type="submit",
                disabled=CustomerState.busy,
                class_name=BUTTON,
            ),
            on_submit=CustomerState.change_password_form,
            reset_on_submit=True,
            aria_busy=CustomerState.busy,
            class_name="flex flex-col gap-5 mt-5",
        ),
        rx.el.div(
            rx.cond(
                ~CustomerState.must_change_password,
                rx.el.a(
                    "Cancel & return to your account",
                    href=rx.cond(
                        CustomerState.admin_access, "/admin", "/dashboard"
                    ),
                    class_name="text-sm text-[var(--studio-accent)] underline underline-offset-4",
                ),
            ),
            rx.el.button(
                "Log out",
                on_click=CustomerState.logout,
                disabled=CustomerState.busy,
                type="button",
                class_name="text-sm text-[var(--studio-text)] underline underline-offset-4",
            ),
            class_name="flex flex-wrap gap-5 mt-6",
        ),
    )


def image_picker(upload_id: str, label: str) -> rx.Component:
    return rx.el.div(
        rx.upload.root(
            rx.el.div(
                rx.icon(
                    "image-plus",
                    class_name="h-7 w-7 text-[var(--studio-accent)]",
                ),
                rx.el.p(label, class_name="text-sm font-medium"),
                rx.el.p(
                    "Click or drop one image · JPEG, PNG or WebP · up to 10 MB",
                    class_name="text-xs leading-6 text-[var(--studio-text)]/60",
                ),
                class_name="flex flex-col items-center text-center gap-3 p-7",
            ),
            id=upload_id,
            multiple=False,
            max_files=1,
            accept={
                "image/jpeg": [".jpg", ".jpeg"],
                "image/png": [".png"],
                "image/webp": [".webp"],
            },
            disabled=CustomerState.busy,
            class_name="w-full border border-dashed border-[var(--studio-text)]/25 bg-transparent cursor-pointer hover:border-[var(--studio-accent)] text-[var(--studio-text)]",
        ),
        rx.foreach(
            rx.selected_files(upload_id),
            lambda filename: rx.el.div(
                rx.icon(
                    "file-image",
                    class_name="h-4 w-4 shrink-0 text-[var(--studio-accent)]",
                ),
                rx.el.p(
                    "One image selected",
                    class_name="min-w-0 text-sm text-[var(--studio-text)]",
                ),
                rx.el.button(
                    "Remove",
                    on_click=rx.clear_selected_files(upload_id),
                    type="button",
                    disabled=CustomerState.busy,
                    class_name="text-xs underline text-[var(--studio-accent)] ml-auto",
                ),
                class_name="mt-3 flex items-center gap-3 border border-[var(--studio-text)]/15 p-3",
            ),
        ),
        rx.el.p(
            "Invalid or oversized images are rejected when submitted. Saved references and payment proof are private: only your signed-in account and the studio owner can view them. Share only what is needed.",
            class_name="text-xs leading-6 text-[var(--studio-text)]/60 mt-3",
        ),
    )


def bouquet_order_panel() -> rx.Component:
    return rx.el.section(
        feedback(),
        rx.cond(
            CustomerState.bouquet_id > 0,
            rx.el.div(
                rx.el.p(
                    "YOUR BOUQUET",
                    class_name="text-xs tracking-[0.2em] text-[var(--studio-accent)]",
                ),
                rx.el.h2(
                    CustomerState.bouquet_name,
                    class_name="font-['Cormorant_Garamond'] text-4xl mt-3",
                ),
                rx.el.p(
                    f"₹{CustomerState.bouquet_price_paise / 100:,.2f} per bouquet",
                    class_name="text-sm mt-4 text-[var(--studio-text)]/70",
                ),
                rx.el.form(
                    rx.el.label(
                        "Quantity",
                        html_for="quantity",
                        class_name="block text-sm mb-2",
                    ),
                    rx.el.input(
                        id="quantity",
                        name="quantity",
                        type="number",
                        min=1,
                        max=999,
                        step=1,
                        default_value="1",
                        key=CustomerState.bouquet_id,
                        required=True,
                        class_name=INPUT,
                    ),
                    rx.el.p(
                        "The current catalog price is checked again when your order is saved. Your checkout will show the exact amount snapshot. No payment is taken by this button.",
                        class_name="text-xs leading-6 text-[var(--studio-text)]/60 my-4",
                    ),
                    rx.el.button(
                        rx.cond(
                            CustomerState.busy,
                            "Saving your order…",
                            "Create order & continue",
                        ),
                        rx.icon("arrow-right", class_name="h-4 w-4"),
                        type="submit",
                        disabled=CustomerState.busy,
                        class_name=BUTTON,
                    ),
                    on_submit=CustomerState.order_bouquet,
                    class_name="max-w-xl mt-6",
                ),
                class_name="border border-[var(--studio-accent)]/40 p-6 md:p-10 bg-[var(--studio-accent)]/5 mt-5",
            ),
        ),
        id="bouquet-order",
        class_name="scroll-mt-10 mt-10",
    )
