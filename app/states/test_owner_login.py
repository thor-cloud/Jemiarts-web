import reflex as rx
import asyncio
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import MethodType, SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.states.admin_state import AdminState
from app.states.customer_state import CustomerState
from app.states.store_database import connection
from app.states.store_repository import StoreRepository


class OwnerLoginTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.store = StoreRepository(Path(directory.name) / "studio.sqlite3")
        self.owner = self.store.authenticate("admin", "password")

    def state(self, token="", path="/login"):
        state = SimpleNamespace(
            session_token=token,
            authenticated=False,
            admin_access=False,
            must_change_password=False,
            password_change_mode=False,
            customer_name="",
            signup_mode=False,
            busy=False,
            ready=True,
            error="",
            notice="",
            orders=[],
            checkout_orders=[],
            qr_available=False,
            qr_image_path="",
            qr_image_url="",
            _actor_id=0,
            _next_path="/checkout?order=42",
            _auth_attempts=[],
            router=SimpleNamespace(
                url=SimpleNamespace(path=path, query_parameters={})
            ),
        )
        for name in (
            "_repository_customer",
            "_clear_identity",
            "_remember_account_path",
        ):
            setattr(
                state, name, MethodType(getattr(CustomerState, name), state)
            )
        return state

    def consume(self, handler, state, form):
        with patch(
            "app.states.customer_state.StoreRepository", return_value=self.store
        ):
            return list(handler.fn(state, form))

    def test_exact_username_hash_and_customer_login_preservation(self):
        for identifier in ("admin", " ADMIN "):
            owner = self.store.authenticate(identifier, "password")
            self.assertEqual(owner["username"], "admin")
            self.assertTrue(owner["is_admin"])
            self.assertTrue(owner["must_change_password"])
            self.assertNotIn("password_hash", owner)
        for identifier in ("administrator", "admin@example.com", "adminx"):
            self.assertIsNone(self.store.authenticate(identifier, "password"))
        self.assertIsNone(self.store.authenticate("admin", "wrong"))
        with patch.dict("os.environ", {"ARTIST_ADMIN_PHONE": "+919876543210"}):
            buyer = self.store.signup(
                "Buyer",
                "+919876543210",
                "a secure buyer password",
                "Buyer@example.com",
            )
        self.assertFalse(buyer["is_admin"])
        self.assertFalse(buyer["must_change_password"])
        for identifier in ("+91 98765 43210", " BUYER@example.com "):
            self.assertEqual(
                self.store.authenticate(identifier, "a secure buyer password")[
                    "id"
                ],
                buyer["id"],
            )
        with connection(self.store.database_path) as conn:
            conn.execute(
                "UPDATE users SET is_admin = 1 WHERE id = ?", (buyer["id"],)
            )
        self.assertTrue(
            self.store.authenticate(buyer["phone"], "a secure buyer password")[
                "is_admin"
            ]
        )

    def test_pending_owner_denied_all_admin_guards(self):
        actor = self.owner["id"]
        token = self.store.create_session(actor)
        self.assertTrue(
            self.store.session_customer(token)["must_change_password"]
        )
        operations = (
            lambda: self.store.session_admin(token),
            lambda: self.store.list_orders(actor, True),
            lambda: self.store.save_bouquet(actor, "Flower", 100, "flower.png"),
            lambda: self.store.save_portrait_size(
                actor, "Square", "20 cm", 100
            ),
            lambda: self.store.save_portrait_style(actor, "Ink"),
            lambda: self.store.delete_portrait_option(actor, "style", 1),
            lambda: self.store.update_settings(
                actor, self.store.get_settings()
            ),
            lambda: self.store.get_customer(actor, 999),
            lambda: self.store.set_order_status(actor, 999, "cancelled"),
        )
        for operation in operations:
            with self.assertRaises(PermissionError):
                operation()
        file = SimpleNamespace(read=AsyncMock())
        with self.assertRaises(PermissionError):
            asyncio.run(self.store.save_admin_upload(actor, file))
        file.read.assert_not_awaited()
        state = SimpleNamespace(
            get_state=AsyncMock(
                return_value=SimpleNamespace(session_token=token)
            )
        )
        with patch(
            "app.states.admin_state.StoreRepository", return_value=self.store
        ):
            with self.assertRaises(PermissionError):
                asyncio.run(AdminState._authorized(state))

    def test_rotation_validation_atomic_flag_and_all_sessions_revoked(self):
        actor = self.owner["id"]
        tokens = [self.store.create_session(actor) for _ in range(2)]
        for current, replacement, error in (
            ("wrong", "a new secure password", PermissionError),
            ("password", "short", ValueError),
            ("password", "password", ValueError),
        ):
            with self.assertRaises(error):
                self.store.change_password(actor, current, replacement)
            self.assertTrue(
                self.store.session_customer(tokens[0])["must_change_password"]
            )
            self.assertIsNotNone(self.store.authenticate("admin", "password"))
        self.store.change_password(actor, "password", "a new secure password")
        for token in tokens:
            with self.assertRaises(PermissionError):
                self.store.session_customer(token)
        self.assertIsNone(self.store.authenticate("admin", "password"))
        owner = StoreRepository(self.store.database_path).authenticate(
            "admin", "a new secure password"
        )
        self.assertFalse(owner["must_change_password"])
        token = self.store.create_session(actor)
        self.assertTrue(self.store.session_admin(token)["is_admin"])
        with self.assertRaises(ValueError):
            self.store.change_password(
                actor, "a new secure password", "a new secure password"
            )
        self.store.change_password(
            actor, "a new secure password", "another secure password"
        )
        with self.assertRaises(PermissionError):
            self.store.session_admin(token)
        self.assertTrue(
            self.store.session_admin(self.store.create_session(actor))[
                "is_admin"
            ]
        )

    def test_owner_routes_required_form_and_fresh_session(self):
        state = self.state()
        with patch.object(rx, "redirect") as redirect:
            self.consume(
                CustomerState.authenticate_form,
                state,
                {"identifier": "admin", "password": "password"},
            )
            redirect.assert_called_once_with("/login")
        self.assertTrue(state.must_change_password)
        self.assertFalse(state.admin_access)
        old_token = state.session_token
        state.router.url.path = "/dashboard"
        with (
            patch(
                "app.states.customer_state.StoreRepository",
                return_value=self.store,
            ),
            patch.object(rx, "redirect") as redirect,
        ):
            CustomerState.load_account_page.fn(state)
            redirect.assert_called_once_with("/login")
        for form, message in (
            (
                {
                    "current_password": "password",
                    "new_password": "new secure password",
                    "confirm_password": "different",
                },
                "do not match",
            ),
            (
                {
                    "current_password": "wrong",
                    "new_password": "new secure password",
                    "confirm_password": "new secure password",
                },
                "incorrect",
            ),
            (
                {
                    "current_password": "password",
                    "new_password": "short",
                    "confirm_password": "short",
                },
                "12–256",
            ),
        ):
            self.consume(CustomerState.change_password_form, state, form)
            self.assertIn(message, state.error)
            self.assertFalse(state.busy)
            self.assertEqual(state.session_token, old_token)
        with patch.object(rx, "redirect") as redirect:
            self.consume(
                CustomerState.change_password_form,
                state,
                {
                    "current_password": "password",
                    "new_password": "new secure password",
                    "confirm_password": "new secure password",
                },
            )
            redirect.assert_called_once_with("/admin")
        self.assertFalse(state.must_change_password)
        self.assertTrue(state.admin_access)
        self.assertNotEqual(state.session_token, old_token)
        self.store.session_admin(state.session_token)
        with self.assertRaises(PermissionError):
            self.store.session_customer(old_token)
        state._auth_attempts = []
        with patch.object(rx, "redirect") as redirect:
            self.consume(
                CustomerState.authenticate_form,
                state,
                {"identifier": "ADMIN", "password": "new secure password"},
            )
            redirect.assert_called_once_with("/admin")

    def test_customer_remembered_checkout_and_optional_rotation_form(self):
        buyer = self.store.signup(
            "Buyer", "+919876543210", "secure buyer password"
        )
        state = self.state()
        with patch.object(rx, "redirect") as redirect:
            self.consume(
                CustomerState.authenticate_form,
                state,
                {
                    "identifier": buyer["phone"],
                    "password": "secure buyer password",
                },
            )
            redirect.assert_called_once_with("/checkout?order=42")
        state.router.url.query_parameters = {"password": "change"}
        with (
            patch(
                "app.states.customer_state.StoreRepository",
                return_value=self.store,
            ),
            patch.object(rx, "redirect") as redirect,
        ):
            CustomerState.load_account_page.fn(state)
            redirect.assert_not_called()
        self.assertTrue(state.password_change_mode)
        state.busy = True
        self.assertEqual(
            self.consume(CustomerState.change_password_form, state, {}), []
        )
        self.assertIsNotNone(
            self.store.authenticate(buyer["phone"], "secure buyer password")
        )


if __name__ == "__main__":
    unittest.main()
