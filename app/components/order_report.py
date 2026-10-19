import reflex as rx

from app.components.admin_pages import section_title
from app.states.admin_state import AdminState
from app.states.order_report import ReportRow


LABEL_CLASS = "block mb-2 text-sm font-medium text-[var(--studio-text)]"
DATE_FIELD_CLASS = "w-full border border-[var(--studio-text)]/25 bg-[var(--studio-bg)] pl-10 pr-4 py-3 text-sm text-[var(--studio-text)] placeholder:text-[var(--studio-text)]/50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--studio-accent)]"
SELECT_CLASS = "w-full appearance-none border border-[var(--studio-text)]/25 bg-[var(--studio-bg)] pl-4 pr-10 py-3 text-sm text-[var(--studio-text)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--studio-accent)]"
HEAD_LEFT = "px-4 py-3 text-left font-medium text-[var(--studio-text)]"
HEAD_RIGHT = "px-4 py-3 text-right font-medium text-[var(--studio-text)]"


def report_date_field(
    field_id: str, name: str, label: str, value: rx.Var
) -> rx.Component:
    return rx.el.div(
        rx.el.label(label, html_for=field_id, class_name=LABEL_CLASS),
        rx.el.div(
            rx.icon(
                "calendar",
                class_name="absolute left-3 top-3.5 h-4 w-4 pointer-events-none text-[var(--studio-accent)]",
            ),
            rx.el.input(
                id=field_id,
                name=name,
                type="text",
                input_mode="numeric",
                placeholder="YYYY-MM-DD",
                max_length=10,
                auto_complete="off",
                default_value=value,
                aria_describedby="report-filter-help",
                aria_invalid=AdminState.report_error != "",
                class_name=DATE_FIELD_CLASS,
            ),
            class_name="relative",
        ),
        class_name="w-full min-w-0",
    )


def report_status_field() -> rx.Component:
    return rx.el.div(
        rx.el.label(
            "Current status", html_for="report-status", class_name=LABEL_CLASS
        ),
        rx.el.div(
            rx.el.select(
                rx.el.option("All statuses", value=""),
                rx.el.option("Awaiting payment", value="awaiting_payment"),
                rx.el.option("Payment review", value="payment_review"),
                rx.el.option("Confirmed", value="confirmed"),
                rx.el.option("In progress", value="in_progress"),
                rx.el.option("Completed", value="completed"),
                rx.el.option("Cancelled", value="cancelled"),
                id="report-status",
                name="report_status",
                default_value=AdminState.report_status,
                class_name=SELECT_CLASS,
            ),
            rx.icon(
                "chevron-down",
                class_name="absolute right-3 top-3.5 h-4 w-4 pointer-events-none text-[var(--studio-text)]",
            ),
            class_name="relative",
        ),
        class_name="w-full min-w-0",
    )


def report_filters() -> rx.Component:
    return rx.el.form(
        rx.el.div(
            report_date_field(
                "report-start",
                "report_start",
                "Placed from",
                AdminState.report_start,
            ),
            report_date_field(
                "report-end",
                "report_end",
                "Placed until",
                AdminState.report_end,
            ),
            report_status_field(),
            class_name="grid grid-cols-1 md:grid-cols-3 gap-4 w-full",
        ),
        rx.el.p(
            "Dates are order placement dates in UTC and both ends are inclusive. Leave either date blank for an open-ended range. These filters are separate from the order search above.",
            id="report-filter-help",
            class_name="mt-3 text-xs leading-6 text-[var(--studio-text)]/60",
        ),
        rx.cond(
            AdminState.report_error != "",
            rx.el.p(
                rx.icon("circle-alert", class_name="h-4 w-4 shrink-0"),
                AdminState.report_error,
                role="alert",
                class_name="mt-3 flex items-center gap-2 bg-red-100 text-red-700 p-3 text-sm",
            ),
        ),
        rx.el.div(
            rx.el.button(
                rx.icon("filter", class_name="h-4 w-4"),
                "Apply report filters",
                type="submit",
                class_name="inline-flex items-center gap-2 bg-[var(--studio-accent)] text-[var(--studio-bg)] px-5 py-3 text-sm font-medium hover:opacity-85 focus-visible:outline-2 focus-visible:outline-offset-4",
            ),
            rx.el.button(
                rx.icon("rotate-ccw", class_name="h-4 w-4"),
                "Reset report",
                type="button",
                on_click=AdminState.reset_report_filters,
                class_name="inline-flex items-center gap-2 border border-[var(--studio-accent)]/35 px-5 py-3 text-sm text-[var(--studio-accent)] hover:bg-[var(--studio-accent)]/5 focus-visible:outline-2 focus-visible:outline-offset-4",
            ),
            class_name="flex flex-wrap items-center gap-3 mt-5",
        ),
        key=AdminState.report_form_version.to_string(),
        on_submit=AdminState.apply_report_filters,
        aria_label="Order report filters",
        class_name="w-full border border-[var(--studio-text)]/15 p-6 mb-6 font-['DM_Sans']",
    )


def summary_card(
    icon: str, label: str, value: rx.Var, note: str
) -> rx.Component:
    return rx.el.article(
        rx.icon(icon, class_name="h-5 w-5 text-[var(--studio-accent)]"),
        rx.el.p(label, class_name="mt-4 text-sm text-[var(--studio-text)]/65"),
        rx.el.p(
            value,
            class_name="mt-2 font-['Cormorant_Garamond'] text-4xl text-[var(--studio-text)] break-words",
        ),
        rx.el.p(
            note,
            class_name="mt-3 text-xs leading-6 text-[var(--studio-text)]/60",
        ),
        class_name="w-full min-w-0 border border-[var(--studio-text)]/15 p-6",
    )


def report_summary() -> rx.Component:
    return rx.el.div(
        summary_card(
            "clipboard-list",
            "Selected orders",
            AdminState.report_order_count,
            "Orders matching the report filters, by current status.",
        ),
        summary_card(
            "receipt",
            "Total order value",
            AdminState.report_order_value,
            "All selected orders, including awaiting payment, payment review and cancelled. This is not paid revenue.",
        ),
        summary_card(
            "badge-check",
            "Confirmed-payment value",
            AdminState.report_confirmed_value,
            "Manually reviewed order value for orders currently confirmed, in progress or completed. Not bank-settled revenue.",
        ),
        class_name="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6",
    )


def report_explanation() -> rx.Component:
    return rx.el.div(
        rx.icon(
            "info", class_name="h-5 w-5 shrink-0 text-[var(--studio-accent)]"
        ),
        rx.el.ul(
            rx.el.li(
                "Totals are grouped by each order's CURRENT status and filtered by its ORDER PLACEMENT date (UTC), not by when a status changed."
            ),
            rx.el.li(
                "A payment screenshot or uploaded proof alone is not payment confirmation. Only orders you have moved to confirmed, in progress or completed count toward confirmed-payment value."
            ),
            rx.el.li(
                "No bank reconciliation occurs here. Check your bank or UPI statement before treating any amount as received."
            ),
            class_name="list-disc pl-5 space-y-2 text-sm leading-7 text-[var(--studio-text)]/65",
        ),
        class_name="flex items-start gap-3 border-l-2 border-[var(--studio-accent)] pl-5 mb-8",
    )


def report_row(row: ReportRow) -> rx.Component:
    return rx.el.tr(
        rx.el.th(
            row["label"],
            scope="row",
            class_name="px-4 py-3 text-left font-medium text-[var(--studio-text)]",
        ),
        rx.el.td(
            row["count"],
            class_name="px-4 py-3 text-right tabular-nums text-[var(--studio-text)]",
        ),
        rx.el.td(
            row["order_value"],
            class_name="px-4 py-3 text-right tabular-nums text-[var(--studio-text)]",
        ),
        rx.el.td(
            rx.cond(
                row["counts_as_confirmed"],
                row["confirmed_value"],
                rx.el.span(
                    "₹0.00 · excluded",
                    class_name="text-[var(--studio-text)]/60",
                ),
            ),
            class_name="px-4 py-3 text-right tabular-nums text-[var(--studio-text)]",
        ),
        key=row["status"],
        class_name="border-t border-[var(--studio-text)]/10 even:bg-[var(--studio-text)]/[0.03] hover:bg-[var(--studio-accent)]/5",
    )


def header_cell(icon: str, label: str, cell_class: str) -> rx.Component:
    return rx.el.th(
        rx.el.span(
            rx.icon(icon, class_name="h-4 w-4 text-[var(--studio-accent)]"),
            label,
            class_name="inline-flex items-center gap-2",
        ),
        scope="col",
        class_name=cell_class,
    )


def report_table() -> rx.Component:
    return rx.el.div(
        rx.el.table(
            rx.el.caption(
                f"Status breakdown · {AdminState.report_scope_label}",
                class_name="caption-top px-4 py-3 text-left text-sm text-[var(--studio-text)]/65",
            ),
            rx.el.thead(
                rx.el.tr(
                    header_cell("tag", "Current status", HEAD_LEFT),
                    header_cell("hash", "Orders", HEAD_RIGHT),
                    header_cell("receipt", "Order value", HEAD_RIGHT),
                    header_cell(
                        "badge-check", "Confirmed-payment value", HEAD_RIGHT
                    ),
                    class_name="bg-[var(--studio-text)]/5",
                ),
            ),
            rx.el.tbody(rx.foreach(AdminState.report_rows, report_row)),
            rx.el.tfoot(
                rx.el.tr(
                    rx.el.th(
                        "Total",
                        scope="row",
                        class_name="px-4 py-3 text-left font-semibold text-[var(--studio-text)]",
                    ),
                    rx.el.td(
                        AdminState.report_order_count,
                        class_name="px-4 py-3 text-right font-semibold tabular-nums text-[var(--studio-text)]",
                    ),
                    rx.el.td(
                        AdminState.report_order_value,
                        class_name="px-4 py-3 text-right font-semibold tabular-nums text-[var(--studio-text)]",
                    ),
                    rx.el.td(
                        AdminState.report_confirmed_value,
                        class_name="px-4 py-3 text-right font-semibold tabular-nums text-[var(--studio-text)]",
                    ),
                    class_name="border-t-2 border-[var(--studio-text)]/20",
                ),
            ),
            class_name="table-auto w-full min-w-[640px] text-sm font-['DM_Sans']",
        ),
        class_name="w-full overflow-x-auto overflow-y-hidden border border-[var(--studio-text)]/15",
    )


def report_empty_state() -> rx.Component:
    return rx.cond(
        AdminState.orders.length() == 0,
        rx.el.div(
            rx.icon(
                "package-open",
                class_name="h-5 w-5 shrink-0 text-[var(--studio-accent)]",
            ),
            rx.el.p(
                "No customer orders are saved yet, so every status shows zero. The report fills in as orders arrive.",
                class_name="text-sm leading-7 text-[var(--studio-text)]/65",
            ),
            class_name="flex items-center gap-3 border border-[var(--studio-text)]/15 p-5 mb-6",
        ),
        rx.cond(
            AdminState.report_order_count == 0,
            rx.el.div(
                rx.icon(
                    "search-x",
                    class_name="h-5 w-5 shrink-0 text-[var(--studio-accent)]",
                ),
                rx.el.p(
                    "No saved orders match these report filters. Widen the date range, choose All statuses or reset the report.",
                    class_name="flex-1 text-sm leading-7 text-[var(--studio-text)]/65",
                ),
                rx.el.button(
                    rx.icon("rotate-ccw", class_name="h-4 w-4"),
                    "Reset report",
                    type="button",
                    on_click=AdminState.reset_report_filters,
                    class_name="inline-flex items-center gap-2 py-2 text-sm text-[var(--studio-accent)] hover:underline focus-visible:outline-2 focus-visible:outline-offset-4",
                ),
                class_name="flex flex-wrap items-center gap-3 border border-[var(--studio-text)]/15 p-5 mb-6",
            ),
        ),
    )


def order_report_panel() -> rx.Component:
    return rx.el.section(
        section_title(
            "Order report",
            "A status breakdown of saved orders with integer-accurate totals. Choose a placement date range and status, then apply.",
        ),
        report_explanation(),
        report_filters(),
        rx.el.p(
            f"Report shows {AdminState.report_order_count} of {AdminState.orders.length()} saved orders · {AdminState.report_scope_label}",
            role="status",
            aria_live="polite",
            aria_atomic=True,
            class_name="mb-4 text-sm text-[var(--studio-text)]/65",
        ),
        report_empty_state(),
        report_summary(),
        report_table(),
        id="admin-report",
        aria_label="Order report",
        class_name="w-full min-w-0 pb-12 scroll-mt-8",
    )
