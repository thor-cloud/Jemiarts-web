import reflex as rx
import hashlib
import hmac
import re
import secrets
from decimal import Decimal, InvalidOperation
from pathlib import PurePosixPath
import logging


PASSWORD_ITERATIONS = 600_000
ORDER_STATUSES = (
    "awaiting_payment",
    "payment_review",
    "confirmed",
    "in_progress",
    "completed",
    "cancelled",
)


def text(value: str, label: str, maximum: int, required: bool = True) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be text.")
    result = value.strip()
    if (required and not result) or len(result) > maximum or "\x00" in result:
        raise ValueError(f"{label} is missing or too long.")
    return result


def phone_number(value: str, required: bool = True) -> str:
    value = text(value, "Phone number", 40, required)
    if not value and not required:
        return ""
    if not re.fullmatch(r"\+?[0-9 ()-]+", value):
        raise ValueError("Use a phone number with an explicit country code.")
    digits = re.sub(r"[ ()-]", "", value)
    if not re.fullmatch(r"\+[1-9][0-9]{7,14}", digits):
        raise ValueError(
            "Use an international phone number, including + and country code."
        )
    return digits


def email_address(value: str) -> str:
    value = text(value, "Email", 254, False).lower()
    if value and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
        raise ValueError("Enter a valid email address.")
    return value


def color_value(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(
        r"#[0-9a-fA-F]{6}", value
    ):
        raise ValueError("Colors must use six-digit hex notation.")
    return value.upper()


def upload_path(value: str, required: bool = False) -> str:
    value = text(value, "Upload path", 255, required)
    if not value:
        return ""
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or len(path.parts) != 1
        or value in (".", "..")
        or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]*", value)
    ):
        raise ValueError(
            "Store only an upload filename, never an absolute path or URL."
        )
    return value


def positive_id(value: int) -> int:
    if type(value) is not int or value < 1:
        raise ValueError("Record ID must be a positive integer.")
    return value


def quantity_value(value: int) -> int:
    if type(value) is not int or not 1 <= value <= 999:
        raise ValueError("Quantity must be between 1 and 999.")
    return value


def price_value(value: int) -> int:
    if type(value) is not int or not 0 <= value <= 1_000_000_000:
        raise ValueError("Price must be a nonnegative integer in paise.")
    return value


def rupees_to_paise(value: str) -> int:
    try:
        amount = Decimal(value)
        if (
            not amount.is_finite()
            or amount < 0
            or amount.as_tuple().exponent < -2
        ):
            raise ValueError("Price must have at most two decimal places.")
        return price_value(int(amount * 100))
    except (InvalidOperation, TypeError) as error:
        logging.exception("Unexpected error")
        raise ValueError("Enter a valid price.") from error


def order_details(value: dict[str, str]) -> dict[str, str]:
    if not isinstance(value, dict) or len(value) > 30:
        raise ValueError("Order details must be a small text dictionary.")
    return {
        text(key, "Detail key", 80): text(item, "Detail value", 2000, False)
        for key, item in value.items()
    }


def hash_password(password: str) -> str:
    if not isinstance(password, str) or not 12 <= len(password) <= 256:
        raise ValueError("Password must contain 12–256 characters.")
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), salt, PASSWORD_ITERATIONS
    )
    return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    if not isinstance(password, str) or len(password) > 256:
        return False
    try:
        algorithm, rounds, salt_hex, digest_hex = encoded.split("$")
        if algorithm != "pbkdf2_sha256" or not rounds.isdigit():
            return False
        iterations = int(rounds)
        salt, expected = bytes.fromhex(salt_hex), bytes.fromhex(digest_hex)
        if (
            not 100_000 <= iterations <= 2_000_000
            or len(salt) != 16
            or len(expected) != 32
        ):
            return False
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), salt, iterations
        )
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError, AttributeError):
        logging.exception("Unexpected error")
        return False
