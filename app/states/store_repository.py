import reflex as rx
import hmac
import hashlib
import secrets
import time
import json
import os
import sqlite3
from pathlib import Path
from typing import cast

from app.states.store_database import (
    LOCAL_DATABASE,
    connection,
    initialize_database,
)
from app.states.store_models import (
    Account,
    Bouquet,
    Customer,
    Order,
    OrderKind,
    OrderStatus,
    SiteSettings,
)
from app.states.store_uploads import (
    save_image_upload,
    require_saved_upload,
    require_saved_png,
)
from app.states.store_validation import (
    ORDER_STATUSES,
    ORDER_TRANSITIONS,
    color_value,
    email_address,
    hash_password,
    order_details,
    phone_number,
    positive_id,
    price_value,
    quantity_value,
    text,
    upload_path,
    verify_password,
)
import logging


class DuplicateAccountError(ValueError):
    pass


class StoreRepository:
    """Backend-only access. Actor IDs must come from a trusted authenticated session."""

    def __init__(self, database_path: Path = LOCAL_DATABASE):
        self.database_path = database_path
        initialize_database(database_path)

    def _account(self, row: sqlite3.Row) -> Account:
        return Account(
            id=row["id"],
            name=row["name"],
            phone=row["phone"],
            email=row["email"],
            is_admin=bool(row["is_admin"]),
            password_hash=row["password_hash"],
            created_at=row["created_at"],
        )

    def _customer(self, row: sqlite3.Row) -> Customer:
        return Customer(
            id=row["id"],
            name=row["name"],
            phone=row["phone"],
            email=row["email"],
            is_admin=bool(row["is_admin"]),
            created_at=row["created_at"],
        )

    def _bouquet(self, row: sqlite3.Row) -> Bouquet:
        return Bouquet(
            id=row["id"],
            name=row["name"],
            price_paise=row["price_paise"],
            image_path=row["image_path"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _order(self, row: sqlite3.Row) -> Order:
        return Order(
            id=row["id"],
            user_id=row["user_id"],
            kind=cast(OrderKind, row["kind"]),
            bouquet_id=row["bouquet_id"],
            details=json.loads(row["details"]),
            quantity=row["quantity"],
            unit_price_paise=row["unit_price_paise"],
            total_price_paise=row["total_price_paise"],
            status=cast(OrderStatus, row["status"]),
            reference_upload_path=row["reference_upload_path"],
            payment_proof_path=row["payment_proof_path"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _require_admin(self, conn: sqlite3.Connection, actor_id: int) -> None:
        row = conn.execute(
            "SELECT is_admin FROM users WHERE id = ?", (positive_id(actor_id),)
        ).fetchone()
        if row is None or not row["is_admin"]:
            raise PermissionError("Administrator access required.")

    def _require_order_access(
        self, conn: sqlite3.Connection, actor_id: int, order_id: int
    ) -> sqlite3.Row:
        row = conn.execute(
            "SELECT * FROM orders WHERE id = ?", (positive_id(order_id),)
        ).fetchone()
        if row is None:
            raise LookupError("Order not found.")
        if row["user_id"] != positive_id(actor_id):
            self._require_admin(conn, actor_id)
        return row

    def signup(
        self, name: str, phone: str, password: str, email: str = ""
    ) -> Customer:
        name, phone, email = (
            text(name, "Name", 120),
            phone_number(phone),
            email_address(email),
        )
        encoded = hash_password(password)
        designated_phone = os.environ.get("ARTIST_ADMIN_PHONE", "").strip()
        designated_admin = bool(designated_phone) and hmac.compare_digest(
            phone, phone_number(designated_phone)
        )
        try:
            with connection(self.database_path) as conn:
                is_admin = (
                    designated_admin
                    if designated_phone
                    else conn.execute("SELECT 1 FROM users LIMIT 1").fetchone()
                    is None
                )
                cursor = conn.execute(
                    "INSERT INTO users(name, phone, email, password_hash, is_admin) VALUES (?, ?, ?, ?, ?)",
                    (name, phone, email, encoded, int(is_admin)),
                )
                row = conn.execute(
                    "SELECT * FROM users WHERE id = ?", (cursor.lastrowid,)
                ).fetchone()
                return self._customer(row)
        except sqlite3.IntegrityError as error:
            logging.exception("Unexpected error")
            raise DuplicateAccountError(
                "An account with these contact details already exists."
            ) from error

    def authenticate(self, phone: str, password: str) -> Customer | None:
        try:
            identifier = phone.strip()
            if "@" in identifier:
                normalized = email_address(identifier)
                column = "email"
            else:
                normalized = phone_number(identifier)
                column = "phone"
        except ValueError:
            normalized, column = "", "phone"
        with connection(self.database_path) as conn:
            row = conn.execute(
                f"SELECT * FROM users WHERE {column} = ? AND {column} != ''",
                (normalized,),
            ).fetchone()
        if row is None:
            dummy = f"pbkdf2_sha256$600000${'00' * 16}${'00' * 32}"
            verify_password(password, dummy)
            return None
        account = self._account(row)
        if not verify_password(password, account["password_hash"]):
            return None
        return self._customer(row)

    def create_session(self, customer_id: int) -> str:
        self.get_customer(customer_id, customer_id)
        token = secrets.token_urlsafe(48)
        digest = hashlib.sha256(token.encode()).hexdigest()
        with connection(self.database_path) as conn:
            conn.execute(
                "DELETE FROM customer_sessions WHERE expires_at <= ?",
                (int(time.time()),),
            )
            conn.execute(
                "INSERT INTO customer_sessions(token_hash, user_id, expires_at) VALUES (?, ?, ?)",
                (digest, customer_id, int(time.time()) + 604800),
            )
        return token

    def session_customer(self, token: str) -> Customer:
        if not token or len(token) > 128:
            raise PermissionError("Please log in to continue.")
        digest = hashlib.sha256(token.encode()).hexdigest()
        with connection(self.database_path) as conn:
            row = conn.execute(
                "SELECT users.* FROM users JOIN customer_sessions ON users.id = customer_sessions.user_id WHERE token_hash = ? AND expires_at > ?",
                (digest, int(time.time())),
            ).fetchone()
            if row is None:
                raise PermissionError(
                    "Your session has expired. Please log in again."
                )
            return self._customer(row)

    def session_admin(self, token: str) -> Customer:
        customer = self.session_customer(token)
        if not self.is_admin(customer["id"]):
            raise PermissionError("Administrator access required.")
        return customer

    def revoke_session(self, token: str) -> None:
        digest = hashlib.sha256(token.encode()).hexdigest()
        with connection(self.database_path) as conn:
            conn.execute(
                "DELETE FROM customer_sessions WHERE token_hash = ?", (digest,)
            )

    def customer_order(self, actor_id: int, order_id: int) -> Order:
        order = self.get_order(actor_id, order_id)
        if order["user_id"] != actor_id:
            raise PermissionError("This order does not belong to your account.")
        return order

    def submit_payment_proof(
        self, actor_id: int, order_id: int, filename: str
    ) -> Order:
        proof = require_saved_upload(filename)
        with connection(self.database_path) as conn:
            row = self._require_order_access(conn, actor_id, order_id)
            if row["user_id"] != actor_id:
                raise PermissionError(
                    "This order does not belong to your account."
                )
            if row["status"] != "awaiting_payment":
                raise ValueError(
                    "This order is no longer awaiting payment. Refresh your orders."
                )
            conn.execute(
                "UPDATE orders SET payment_proof_path = ?, status = 'payment_review', updated_at = strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id = ?",
                (proof, order_id),
            )
            return self._order(
                conn.execute(
                    "SELECT * FROM orders WHERE id = ?", (order_id,)
                ).fetchone()
            )

    def get_customer(self, actor_id: int, customer_id: int) -> Customer:
        with connection(self.database_path) as conn:
            if positive_id(actor_id) != positive_id(customer_id):
                self._require_admin(conn, actor_id)
            row = conn.execute(
                "SELECT * FROM users WHERE id = ?", (customer_id,)
            ).fetchone()
            if row is None:
                raise LookupError("Customer not found.")
            return self._customer(row)

    async def save_upload(self, actor_id: int, file: rx.UploadFile) -> str:
        self.get_customer(actor_id, actor_id)
        return await save_image_upload(file)

    async def save_admin_upload(
        self, actor_id: int, file: rx.UploadFile, png_only: bool = False
    ) -> str:
        with connection(self.database_path) as conn:
            self._require_admin(conn, actor_id)
        return await save_image_upload(file, png_only=png_only)

    def is_admin(self, actor_id: int) -> bool:
        with connection(self.database_path) as conn:
            row = conn.execute(
                "SELECT is_admin FROM users WHERE id = ?",
                (positive_id(actor_id),),
            ).fetchone()
            return bool(row is not None and row["is_admin"])

    def change_password(
        self, actor_id: int, current_password: str, new_password: str
    ) -> None:
        with connection(self.database_path) as conn:
            row = conn.execute(
                "SELECT password_hash FROM users WHERE id = ?",
                (positive_id(actor_id),),
            ).fetchone()
        if row is None or not verify_password(
            current_password, row["password_hash"]
        ):
            raise PermissionError("Current password is incorrect.")
        encoded = hash_password(new_password)
        with connection(self.database_path) as conn:
            cursor = conn.execute(
                "UPDATE users SET password_hash = ? WHERE id = ? AND password_hash = ?",
                (encoded, actor_id, row["password_hash"]),
            )
            if cursor.rowcount != 1:
                raise PermissionError("Account changed; authenticate again.")

    def list_bouquets(self) -> list[Bouquet]:
        with connection(self.database_path) as conn:
            return [
                self._bouquet(row)
                for row in conn.execute(
                    "SELECT * FROM bouquet_models ORDER BY id DESC"
                )
            ]

    def get_bouquet(self, bouquet_id: int) -> Bouquet:
        with connection(self.database_path) as conn:
            row = conn.execute(
                "SELECT * FROM bouquet_models WHERE id = ?",
                (positive_id(bouquet_id),),
            ).fetchone()
            if row is None:
                raise LookupError("Bouquet not found.")
            return self._bouquet(row)

    def save_bouquet(
        self,
        actor_id: int,
        name: str,
        price_paise: int,
        image_path: str,
        bouquet_id: int | None = None,
    ) -> Bouquet:
        values = (
            text(name, "Bouquet name", 160),
            price_value(price_paise),
            upload_path(image_path, True),
        )
        with connection(self.database_path) as conn:
            self._require_admin(conn, actor_id)
            if bouquet_id is None:
                cursor = conn.execute(
                    "INSERT INTO bouquet_models(name, price_paise, image_path) VALUES (?, ?, ?)",
                    values,
                )
                bouquet_id = int(cursor.lastrowid)
            else:
                positive_id(bouquet_id)
                cursor = conn.execute(
                    """UPDATE bouquet_models SET name = ?, price_paise = ?, image_path = ?,
                    updated_at = strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id = ?""",
                    (*values, bouquet_id),
                )
                if cursor.rowcount != 1:
                    raise LookupError("Bouquet not found.")
            return self._bouquet(
                conn.execute(
                    "SELECT * FROM bouquet_models WHERE id = ?", (bouquet_id,)
                ).fetchone()
            )

    def create_order(
        self,
        actor_id: int,
        kind: OrderKind,
        details: dict[str, str],
        quantity: int = 1,
        bouquet_id: int | None = None,
        portrait_price_paise: int | None = None,
        reference_upload_path: str = "",
    ) -> Order:
        actor_id, quantity = positive_id(actor_id), quantity_value(quantity)
        payload = json.dumps(order_details(details), ensure_ascii=False)
        reference = upload_path(reference_upload_path)
        with connection(self.database_path) as conn:
            if (
                conn.execute(
                    "SELECT id FROM users WHERE id = ?", (actor_id,)
                ).fetchone()
                is None
            ):
                raise PermissionError("A customer account is required.")
            if kind == "bouquet":
                if bouquet_id is None or portrait_price_paise is not None:
                    raise ValueError(
                        "Bouquet orders require a model, not a supplied price."
                    )
                row = conn.execute(
                    "SELECT price_paise FROM bouquet_models WHERE id = ?",
                    (positive_id(bouquet_id),),
                ).fetchone()
                if row is None:
                    raise LookupError("Bouquet not found.")
                unit_price = row["price_paise"]
            elif kind == "portrait":
                if bouquet_id is not None or portrait_price_paise is None:
                    raise ValueError(
                        "Portrait orders require a trusted server-side price."
                    )
                unit_price = price_value(portrait_price_paise)
            else:
                raise ValueError("Unknown order type.")
            cursor = conn.execute(
                """INSERT INTO orders(user_id, kind, bouquet_id, details, quantity,
                unit_price_paise, total_price_paise, reference_upload_path) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    actor_id,
                    kind,
                    bouquet_id,
                    payload,
                    quantity,
                    unit_price,
                    unit_price * quantity,
                    reference,
                ),
            )
            return self._order(
                conn.execute(
                    "SELECT * FROM orders WHERE id = ?", (cursor.lastrowid,)
                ).fetchone()
            )

    def get_order(self, actor_id: int, order_id: int) -> Order:
        with connection(self.database_path) as conn:
            return self._order(
                self._require_order_access(conn, actor_id, order_id)
            )

    def list_orders(
        self, actor_id: int, all_customers: bool = False
    ) -> list[Order]:
        with connection(self.database_path) as conn:
            positive_id(actor_id)
            if all_customers:
                self._require_admin(conn, actor_id)
                rows = conn.execute(
                    "SELECT * FROM orders ORDER BY created_at DESC, id DESC"
                )
            else:
                rows = conn.execute(
                    "SELECT * FROM orders WHERE user_id = ? ORDER BY created_at DESC, id DESC",
                    (actor_id,),
                )
            return [self._order(row) for row in rows]

    def set_order_status(
        self, actor_id: int, order_id: int, status: OrderStatus
    ) -> None:
        if status not in ORDER_STATUSES:
            raise ValueError("Unknown order status.")
        with connection(self.database_path) as conn:
            self._require_admin(conn, actor_id)
            row = self._require_order_access(conn, actor_id, order_id)
            if (
                status != row["status"]
                and status not in ORDER_TRANSITIONS[row["status"]]
            ):
                raise ValueError(
                    "This status transition is not allowed. Refresh the order."
                )
            if status == "confirmed" and not row["payment_proof_path"]:
                raise ValueError(
                    "Review a submitted payment proof before confirming the order."
                )
            conn.execute(
                "UPDATE orders SET status = ?, updated_at = strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id = ?",
                (status, order_id),
            )

    def attach_order_uploads(
        self,
        actor_id: int,
        order_id: int,
        reference_path: str | None = None,
        payment_proof_path: str | None = None,
    ) -> None:
        with connection(self.database_path) as conn:
            row = self._require_order_access(conn, actor_id, order_id)
            reference = (
                row["reference_upload_path"]
                if reference_path is None
                else upload_path(reference_path)
            )
            proof = (
                row["payment_proof_path"]
                if payment_proof_path is None
                else upload_path(payment_proof_path)
            )
            conn.execute(
                """UPDATE orders SET reference_upload_path = ?, payment_proof_path = ?,
                updated_at = strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id = ?""",
                (reference, proof, order_id),
            )

    def get_settings(self) -> SiteSettings:
        with connection(self.database_path) as conn:
            row = conn.execute(
                "SELECT * FROM site_settings WHERE id = 1"
            ).fetchone()
            return SiteSettings(
                id=1,
                brand_name=row["brand_name"],
                background_color=row["background_color"],
                text_color=row["text_color"],
                accent_color=row["accent_color"],
                hero_image_path=row["hero_image_path"],
                payment_qr_path=row["payment_qr_path"],
                welcome_text=row["welcome_text"],
                artist_biography=row["artist_biography"],
                contact_number=row["contact_number"],
                updated_at=row["updated_at"],
            )

    def update_settings(
        self, actor_id: int, settings: SiteSettings
    ) -> SiteSettings:
        with connection(self.database_path) as conn:
            self._require_admin(conn, actor_id)
        if settings["id"] != 1:
            raise ValueError("Site settings must use the singleton record.")
        values = (
            text(settings["brand_name"], "Brand name", 120),
            color_value(settings["background_color"]),
            color_value(settings["text_color"]),
            color_value(settings["accent_color"]),
            upload_path(settings["hero_image_path"]),
            require_saved_png(settings["payment_qr_path"])
            if settings["payment_qr_path"]
            else "",
            text(settings["welcome_text"], "Welcome text", 4000, False),
            text(settings["artist_biography"], "Biography", 12000, False),
            phone_number(settings["contact_number"], False),
        )
        with connection(self.database_path) as conn:
            self._require_admin(conn, actor_id)
            conn.execute(
                """UPDATE site_settings SET brand_name = ?, background_color = ?, text_color = ?, accent_color = ?,
                hero_image_path = ?, payment_qr_path = ?, welcome_text = ?, artist_biography = ?, contact_number = ?,
                updated_at = strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id = 1""",
                values,
            )
        return self.get_settings()
