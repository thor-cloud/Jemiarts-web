import reflex as rx


def delivery_item(label: str, value: str, empty: str) -> rx.Component:
    return rx.el.div(
        rx.el.dt(
            label,
            class_name="text-xs font-medium text-[var(--studio-text)]/65",
        ),
        rx.el.dd(
            rx.cond(value != "", value, empty),
            class_name="mt-1 text-sm leading-7 text-[var(--studio-text)] whitespace-pre-wrap break-words [overflow-wrap:anywhere]",
        ),
    )


def bouquet_delivery_details(
    is_bouquet: bool,
    recipient_name: str,
    delivery_address: str,
    preferred_date: str,
    gift_message: str,
) -> rx.Component:
    return rx.cond(
        is_bouquet,
        rx.el.div(
            rx.el.p(
                "Bouquet delivery details",
                class_name="text-sm font-medium text-[var(--studio-accent)] mb-4",
            ),
            rx.cond(
                (recipient_name != "")
                | (delivery_address != "")
                | (preferred_date != "")
                | (gift_message != ""),
                rx.el.div(
                    rx.el.dl(
                        delivery_item(
                            "Recipient name", recipient_name, "Not recorded"
                        ),
                        delivery_item(
                            "Delivery address", delivery_address, "Not recorded"
                        ),
                        delivery_item(
                            "Preferred delivery date",
                            preferred_date,
                            "Not recorded",
                        ),
                        delivery_item(
                            "Gift message", gift_message, "No gift message"
                        ),
                        class_name="flex flex-col gap-4",
                    ),
                    rx.el.p(
                        "The preferred date is a request, not a guaranteed delivery booking. Confirm arrangements with the studio.",
                        class_name="mt-4 text-xs leading-6 text-[var(--studio-text)]/65",
                    ),
                ),
                rx.el.p(
                    "Delivery details not recorded for this order.",
                    class_name="text-sm leading-7 text-[var(--studio-text)]/65",
                ),
            ),
            class_name="mt-6 border-t border-[var(--studio-text)]/15 pt-5 font-['DM_Sans']",
        ),
    )
