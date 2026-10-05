import reflex as rx
import asyncio
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs, urlparse

from app.states.admin_state import AdminState
from app.states.store_database import connection
from app.states.store_repository import StoreRepository


class AdminTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.store = StoreRepository(self.root / "store.sqlite3")
        environment = patch.dict("os.environ", {"ARTIST_ADMIN_PHONE": ""})
        environment.start()
        self.addCleanup(environment.stop)

    def signup(self, suffix: int):
        return self.store.signup(
            "Test owner", f"+9198765432{suffix:02d}", "a secure test password"
        )

    def test_atomic_first_signup_and_designated_owner(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            users = list(pool.map(self.signup, [10, 11]))
        self.assertEqual(sum(user["is_admin"] for user in users), 1)
        self.assertFalse(self.signup(12)["is_admin"])
        configured = StoreRepository(self.root / "configured.sqlite3")
        with patch.dict("os.environ", {"ARTIST_ADMIN_PHONE": "+919876543214"}):
            self.assertFalse(
                configured.signup(
                    "Customer", "+919876543213", "a secure test password"
                )["is_admin"]
            )
            self.assertTrue(
                configured.signup(
                    "Owner", "+919876543214", "a secure test password"
                )["is_admin"]
            )

    def test_session_role_revocation_and_mutation_guards(self):
        admin = self.signup(10)
        customer = self.signup(11)
        token = self.store.create_session(admin["id"])
        self.assertEqual(self.store.session_admin(token)["id"], admin["id"])
        with self.assertRaises(PermissionError):
            self.store.session_admin(self.store.create_session(customer["id"]))
        with self.assertRaises(PermissionError):
            self.store.save_bouquet(
                customer["id"], "Flower", 10000, "image.png"
            )
        with self.assertRaises(PermissionError):
            self.store.update_settings(
                customer["id"], self.store.get_settings()
            )
        with connection(self.store.database_path) as conn:
            conn.execute(
                "UPDATE users SET is_admin = 0 WHERE id = ?", (admin["id"],)
            )
        with self.assertRaises(PermissionError):
            self.store.session_admin(token)
        self.store.revoke_session(token)
        with self.assertRaises(PermissionError):
            self.store.session_admin(token)

    def test_status_workflow_and_whatsapp_draft(self):
        admin = self.signup(10)
        customer = self.signup(11)
        order = self.store.create_order(
            customer["id"],
            "portrait",
            {"size": "A4"},
            portrait_price_paise=150000,
        )
        with self.assertRaises(ValueError):
            self.store.set_order_status(admin["id"], order["id"], "completed")
        (self.root / "proof.png").write_bytes(b"proof")
        with patch.object(rx, "get_upload_dir", return_value=self.root):
            self.store.submit_payment_proof(
                customer["id"], order["id"], "proof.png"
            )
            self.store.set_order_status(admin["id"], order["id"], "confirmed")
            state = SimpleNamespace(orders=[], _image=lambda filename: filename)
            AdminState._load_orders(state, self.store, admin["id"])
        row = state.orders[0]
        url = urlparse(row["whatsapp"])
        self.assertEqual(url.netloc, "wa.me")
        self.assertEqual(url.path, f"/{customer['phone'].lstrip('+')}")
        self.assertIn("confirmed", parse_qs(url.query)["text"][0])
        self.store.set_order_status(admin["id"], order["id"], "in_progress")
        self.store.set_order_status(admin["id"], order["id"], "completed")
        with self.assertRaises(ValueError):
            self.store.set_order_status(admin["id"], order["id"], "confirmed")

    def test_load_admin_denies_guest_without_authorization_or_traceback(self):
        self._assert_load_denied("")

    def test_load_admin_denies_non_admin_without_traceback(self):
        self._assert_load_denied("customer-session")

    def _assert_load_denied(self, token: str):
        from app.states.customer_state import CustomerState

        state = SimpleNamespace(
            ready=False,
            allowed=True,
            orders=[],
            bouquets=[{"id": 1}],
            error="",
            notice="",
            get_state=AsyncMock(
                return_value=SimpleNamespace(session_token=token)
            ),
            _authorized=AsyncMock(side_effect=PermissionError("Access denied")),
        )
        state._deny = lambda: AdminState._deny(state)

        async def load():
            async for _ in AdminState.load_admin.fn(state):
                pass

        with patch("app.states.admin_state.logging.exception") as log_error:
            asyncio.run(load())
            log_error.assert_not_called()
        state.get_state.assert_awaited_once_with(CustomerState)
        if token:
            state._authorized.assert_awaited_once()
        else:
            state._authorized.assert_not_awaited()
        self.assertTrue(state.ready)
        self.assertFalse(state.allowed)
        self.assertEqual(state.orders, [])
        self.assertEqual(state.bouquets, [])
        self.assertIn("Administrator access is required", state.error)

    def test_state_authorization_uses_current_customer_session(self):
        admin = self.signup(10)
        token = self.store.create_session(admin["id"])
        state = SimpleNamespace(
            get_state=AsyncMock(
                return_value=SimpleNamespace(session_token=token)
            )
        )
        with patch(
            "app.states.admin_state.StoreRepository", return_value=self.store
        ):
            repository, actor = asyncio.run(AdminState._authorized(state))
            self.assertIs(repository, self.store)
            self.assertEqual(actor, admin["id"])
            self.store.revoke_session(token)
            with self.assertRaises(PermissionError):
                asyncio.run(AdminState._authorized(state))


if __name__ == "__main__":
    unittest.main()
