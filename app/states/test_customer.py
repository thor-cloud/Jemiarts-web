import reflex as rx
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.states.store_repository import StoreRepository
from app.states.store_database import connection


class CustomerIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.repository = StoreRepository(self.root / "test.sqlite3")
        self.environment = patch.dict("os.environ", {"ARTIST_ADMIN_PHONE": ""})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.customer = self.repository.signup(
            "Customer",
            "+919876543210",
            "a secure test password",
            "Customer@example.com",
        )
        self.other = self.repository.signup(
            "Other Customer", "+919876543211", "another secure password"
        )

    def test_email_login_and_session_revocation(self):
        result = self.repository.authenticate(
            " CUSTOMER@example.com ", "a secure test password"
        )
        self.assertEqual(result["id"], self.customer["id"])
        self.assertIsNone(
            self.repository.authenticate(
                "unknown@example.com", "a secure test password"
            )
        )
        self.assertIsNone(
            self.repository.authenticate(
                "Customer@example.com", "wrong password"
            )
        )
        token = self.repository.create_session(self.customer["id"])
        self.assertEqual(
            self.repository.session_customer(token)["id"], self.customer["id"]
        )
        with connection(self.repository.database_path) as conn:
            stored = conn.execute(
                "SELECT token_hash FROM customer_sessions"
            ).fetchone()[0]
            self.assertNotEqual(token, stored)
        self.repository.revoke_session(token)
        with self.assertRaises(PermissionError):
            self.repository.session_customer(token)

    def test_real_proof_is_required_and_customer_ownership_enforced(self):
        order = self.repository.create_order(
            self.customer["id"],
            "portrait",
            {"size": "A4"},
            portrait_price_paise=150000,
            reference_upload_path="reference.png",
        )
        with patch.object(rx, "get_upload_dir", return_value=self.root):
            with self.assertRaises(ValueError):
                self.repository.submit_payment_proof(
                    self.customer["id"], order["id"], "missing.png"
                )
            self.assertEqual(
                self.repository.get_order(self.customer["id"], order["id"])[
                    "status"
                ],
                "awaiting_payment",
            )
            (self.root / "proof.png").write_bytes(b"saved image")
            with self.assertRaises(PermissionError):
                self.repository.customer_order(self.other["id"], order["id"])
            with self.assertRaises(PermissionError):
                self.repository.submit_payment_proof(
                    self.other["id"], order["id"], "proof.png"
                )
            result = self.repository.submit_payment_proof(
                self.customer["id"], order["id"], "proof.png"
            )
            self.assertEqual(result["status"], "payment_review")
            self.assertEqual(result["payment_proof_path"], "proof.png")
            with self.assertRaises(ValueError):
                self.repository.submit_payment_proof(
                    self.customer["id"], order["id"], "proof.png"
                )
        self.assertEqual(self.repository.list_orders(self.other["id"]), [])

    def test_expired_session_fails_closed(self):
        token = self.repository.create_session(self.customer["id"])
        with connection(self.repository.database_path) as conn:
            conn.execute("UPDATE customer_sessions SET expires_at = 0")
        with self.assertRaises(PermissionError):
            self.repository.session_customer(token)


if __name__ == "__main__":
    unittest.main()
