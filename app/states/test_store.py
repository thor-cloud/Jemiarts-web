import reflex as rx
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.states.store_database import connection, initialize_database
from app.states.store_repository import DuplicateAccountError, StoreRepository
from app.states.store_validation import (
    hash_password,
    upload_path,
    verify_password,
)


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "store.sqlite3"
        self.store = StoreRepository(self.path)
        self.environment = patch.dict(
            "os.environ", {"ARTIST_ADMIN_PHONE": "+919876543211"}
        )
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def customer(self):
        return self.store.signup(
            "Test Customer", "+919876543210", "a long test password"
        )

    def admin(self):
        with patch.dict("os.environ", {"ARTIST_ADMIN_PHONE": "+919876543211"}):
            return self.store.signup(
                "Test Administrator", "+919876543211", "another long password"
            )

    def test_only_settings_seeded_and_initialization_idempotent(self):
        initialize_database(self.path)
        with connection(self.path) as conn:
            self.assertEqual(
                conn.execute("SELECT count(*) FROM users").fetchone()[0], 0
            )
            self.assertEqual(
                conn.execute("SELECT count(*) FROM bouquet_models").fetchone()[
                    0
                ],
                0,
            )
            self.assertEqual(
                conn.execute("SELECT count(*) FROM orders").fetchone()[0], 0
            )
            self.assertEqual(
                conn.execute("SELECT count(*) FROM site_settings").fetchone()[
                    0
                ],
                1,
            )
            self.assertEqual(
                conn.execute("PRAGMA foreign_keys").fetchone()[0], 1
            )
        self.assertEqual(
            self.store.get_settings()["background_color"], "#F7F3EC"
        )

    def test_password_salts_and_verification(self):
        password = "secure testing password"
        first, second = hash_password(password), hash_password(password)
        self.assertNotEqual(first, second)
        self.assertTrue(verify_password(password, first))
        self.assertFalse(verify_password("incorrect", first))
        self.assertFalse(verify_password(password, "malformed"))

    def test_signup_authentication_and_explicit_admin(self):
        customer = self.customer()
        self.assertFalse(customer["is_admin"])
        self.assertNotIn("password_hash", customer)
        self.assertTrue(self.admin()["is_admin"])
        self.assertEqual(
            self.store.authenticate("+91 98765 43210", "a long test password")[
                "id"
            ],
            customer["id"],
        )
        self.assertIsNone(self.store.authenticate(customer["phone"], "wrong"))
        with self.assertRaises(DuplicateAccountError):
            self.customer()
        self.store.change_password(
            customer["id"], "a long test password", "new long test password"
        )
        self.assertIsNone(
            self.store.authenticate(customer["phone"], "a long test password")
        )
        self.assertIsNotNone(
            self.store.authenticate(customer["phone"], "new long test password")
        )

    def test_admin_configuration_fails_closed(self):
        with patch.dict("os.environ", {"ARTIST_ADMIN_PHONE": "invalid"}):
            with self.assertRaises(ValueError):
                self.customer()
        with connection(self.path) as conn:
            self.assertEqual(
                conn.execute("SELECT count(*) FROM users").fetchone()[0], 0
            )

    def test_price_snapshot_paths_and_authorization(self):
        customer, admin = self.customer(), self.admin()
        bouquet = self.store.save_bouquet(
            admin["id"], "Test model", 12500, "test.png"
        )
        order = self.store.create_order(
            customer["id"], "bouquet", {"note": "test"}, 2, bouquet["id"]
        )
        self.assertEqual(order["total_price_paise"], 25000)
        self.store.save_bouquet(
            admin["id"], "Updated test model", 15000, "test.png", bouquet["id"]
        )
        self.assertEqual(
            self.store.get_order(customer["id"], order["id"])[
                "unit_price_paise"
            ],
            12500,
        )
        self.store.attach_order_uploads(
            customer["id"], order["id"], "reference.png", "proof.jpg"
        )
        self.assertEqual(
            self.store.get_order(customer["id"], order["id"])[
                "payment_proof_path"
            ],
            "proof.jpg",
        )
        with self.assertRaises(PermissionError):
            self.store.set_order_status(
                customer["id"], order["id"], "confirmed"
            )
        with self.assertRaises(PermissionError):
            self.store.list_orders(customer["id"], True)
        with self.assertRaises(PermissionError):
            self.store.get_order(999, order["id"])
        with connection(self.path) as conn:
            conn.execute(
                "UPDATE orders SET status = 'payment_review' WHERE id = ?",
                (order["id"],),
            )
        self.store.set_order_status(admin["id"], order["id"], "confirmed")
        self.assertEqual(
            StoreRepository(self.path).get_order(customer["id"], order["id"])[
                "status"
            ],
            "confirmed",
        )

    def test_settings_survive_restart_and_singleton_constraint(self):
        admin = self.admin()
        settings = self.store.get_settings()
        settings["brand_name"] = "A real saved name"
        settings["accent_color"] = "#b76d50"
        self.store.update_settings(admin["id"], settings)
        self.assertEqual(
            StoreRepository(self.path).get_settings()["brand_name"],
            "A real saved name",
        )
        with self.assertRaises(sqlite3.IntegrityError):
            with connection(self.path) as conn:
                conn.execute(
                    "INSERT INTO site_settings SELECT 2, brand_name, background_color, text_color, accent_color, hero_image_path, welcome_text, artist_biography, contact_number, updated_at FROM site_settings"
                )

    def test_validation_and_rollback(self):
        for filename in (
            "../secret.png",
            "/tmp/file.jpg",
            "https://example.com/a.png",
            "a\\b.png",
        ):
            with self.assertRaises(ValueError):
                upload_path(filename)
        customer = self.customer()
        with self.assertRaises(ValueError):
            self.store.create_order(
                customer["id"],
                "portrait",
                {},
                quantity=0,
                portrait_price_paise=100,
            )
        with self.assertRaises(ValueError):
            self.store.create_order(
                customer["id"], "portrait", {}, portrait_price_paise=-1
            )
        with self.assertRaises(RuntimeError):
            with connection(self.path) as conn:
                conn.execute(
                    "UPDATE site_settings SET brand_name = 'rolled back' WHERE id = 1"
                )
                raise RuntimeError("Force rollback")
        self.assertNotEqual(
            self.store.get_settings()["brand_name"], "rolled back"
        )


if __name__ == "__main__":
    unittest.main()
