import calendar
import re
from collections.abc import Mapping, Sequence
from typing import TypedDict

from app.states.store_validation import ORDER_STATUSES


CONFIRMED_PAYMENT_STATUSES = ("confirmed", "in_progress", "completed")
STATUS_LABELS: dict[str, str] = {
    "awaiting_payment": "Awaiting payment",
    "payment_review": "Payment review",
    "confirmed": "Confirmed",
    "in_progress": "In progress",
    "completed": "Completed",
    "cancelled": "Cancelled",
}
_DATE = re.compile(r"([0-9]{4})-([0-9]{2})-([0-9]{2})")


class ReportRow(TypedDict):
    status: str
    label: str
    count: int
    order_value_paise: int
    confirmed_value_paise: int
    order_value: str
    confirmed_value: str
    counts_as_confirmed: bool


class OrderReport(TypedDict):
    rows: list[ReportRow]
    count: int
    order_value_paise: int
    confirmed_value_paise: int


def format_paise(value: int) -> str:
    if type(value) is not int:
        raise TypeError("Money must be integer paise.")
    sign = "-" if value < 0 else ""
    value = abs(value)
    return f"{sign}₹{value // 100:,}.{value % 100:02d}"


def report_date(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be text in YYYY-MM-DD format.")
    if value == "":
        return ""
    match = _DATE.fullmatch(value)
    if not match:
        raise ValueError(f"{label} must use the YYYY-MM-DD format.")
    year, month, day = (int(part) for part in match.groups())
    if (
        year < 1
        or not 1 <= month <= 12
        or not 1 <= day <= calendar.monthrange(year, month)[1]
    ):
        raise ValueError(f"{label} must be a real calendar date.")
    return value


def validate_report_filters(
    start: object, end: object, status: object
) -> tuple[str, str, str]:
    start_date = report_date(start, "Start date")
    end_date = report_date(end, "End date")
    if start_date and end_date and start_date > end_date:
        raise ValueError("Start date must be on or before the end date.")
    if not isinstance(status, str) or (status and status not in ORDER_STATUSES):
        raise ValueError("Choose All statuses or one saved order status.")
    return start_date, end_date, status


def build_order_report(
    orders: Sequence[Mapping[str, object]],
    start: str,
    end: str,
    status: str,
) -> OrderReport:
    if status and status not in ORDER_STATUSES:
        return OrderReport(
            rows=[], count=0, order_value_paise=0, confirmed_value_paise=0
        )
    statuses = (status,) if status else ORDER_STATUSES
    totals: dict[str, list[int]] = {item: [0, 0, 0] for item in statuses}
    for order in orders:
        current = order.get("status")
        if not isinstance(current, str) or current not in totals:
            continue
        placed = str(order.get("date", ""))[:10]
        if start and placed < start:
            continue
        if end and placed > end:
            continue
        paise = order.get("amount_paise")
        if type(paise) is not int:
            raise TypeError("Order amounts must be integer paise.")
        bucket = totals[current]
        bucket[0] += 1
        bucket[1] += paise
        if current in CONFIRMED_PAYMENT_STATUSES:
            bucket[2] += paise
    rows: list[ReportRow] = []
    for item in statuses:
        count, value, confirmed = totals[item]
        rows.append(
            ReportRow(
                status=item,
                label=STATUS_LABELS.get(item, item.replace("_", " ")),
                count=count,
                order_value_paise=value,
                confirmed_value_paise=confirmed,
                order_value=format_paise(value),
                confirmed_value=format_paise(confirmed),
                counts_as_confirmed=item in CONFIRMED_PAYMENT_STATUSES,
            )
        )
    return OrderReport(
        rows=rows,
        count=sum(row["count"] for row in rows),
        order_value_paise=sum(row["order_value_paise"] for row in rows),
        confirmed_value_paise=sum(row["confirmed_value_paise"] for row in rows),
    )


def report_scope(start: str, end: str, status: str) -> str:
    label = STATUS_LABELS.get(status, "All statuses")
    if start and end:
        dates = f"placed {start} to {end} (UTC, inclusive)"
    elif start:
        dates = f"placed on or after {start} (UTC)"
    elif end:
        dates = f"placed on or before {end} (UTC)"
    else:
        dates = "placed on any date"
    return f"{label} · {dates}"
