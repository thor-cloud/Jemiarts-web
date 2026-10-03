import reflex as rx
from typing import Literal, TypedDict


OrderKind = Literal["portrait", "bouquet"]
OrderStatus = Literal[
    "awaiting_payment",
    "payment_review",
    "confirmed",
    "in_progress",
    "completed",
    "cancelled",
]


class Customer(TypedDict):
    id: int
    name: str
    phone: str
    email: str
    is_admin: bool
    created_at: str


class Account(Customer):
    password_hash: str


class Bouquet(TypedDict):
    id: int
    name: str
    price_paise: int
    image_path: str
    created_at: str
    updated_at: str


class Order(TypedDict):
    id: int
    user_id: int
    kind: OrderKind
    bouquet_id: int | None
    details: dict[str, str]
    quantity: int
    unit_price_paise: int
    total_price_paise: int
    status: OrderStatus
    reference_upload_path: str
    payment_proof_path: str
    created_at: str
    updated_at: str


class SiteSettings(TypedDict):
    id: int
    brand_name: str
    background_color: str
    text_color: str
    accent_color: str
    hero_image_path: str
    welcome_text: str
    artist_biography: str
    contact_number: str
    updated_at: str
