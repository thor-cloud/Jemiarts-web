import reflex as rx
import tempfile
import unittest
import asyncio
import ast
from pathlib import Path
from types import MethodType, SimpleNamespace
from unittest.mock import patch, Mock

from app.states.customer_state import CustomerState

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


class CustomerFlowRegressionTests(unittest.TestCase):
    def state(self, path="/checkout", order="42", token=""):
        state = SimpleNamespace(
            router=SimpleNamespace(
                url=SimpleNamespace(
                    path=path, query_parameters={"order": order}
                )
            ),
            session_token=token,
            authenticated=False,
            customer_name="",
            _actor_id=0,
            _next_path="/dashboard",
            ready=False,
            error="",
            notice="",
            orders=[],
            checkout_orders=[],
            qr_available=False,
            busy=False,
        )
        for name in (
            "_clear_identity",
            "_remember_account_path",
            "_view",
            "_repository_customer",
            "_qr_exists",
        ):
            setattr(
                state, name, MethodType(getattr(CustomerState, name), state)
            )
        return state

    def test_anonymous_checkout_remembers_order_for_login(self):
        state = self.state()
        CustomerState.load_account_page.fn(state)
        self.assertEqual(state._next_path, "/checkout?order=42")
        self.assertTrue(state.ready)
        self.assertFalse(state.authenticated)
        state.router.url.path = "/login"
        state.session_token = "valid-session"
        state._repository_customer = Mock(return_value=(Mock(), {"id": 1}))
        with patch.object(rx, "redirect") as redirect:
            CustomerState.load_account_page.fn(state)
            redirect.assert_called_once_with("/checkout?order=42")

    def test_invalid_return_targets_are_not_reflected(self):
        for order in ("42&next=https://example.com", "../42", "²", ""):
            state = self.state(order=order)
            CustomerState.load_account_page.fn(state)
            self.assertEqual(state._next_path, "/dashboard")

    def test_foreign_checkout_does_not_log_out_valid_customer(self):
        state = self.state(token="valid-session")
        state.authenticated = True
        repository = Mock()
        repository.list_orders.return_value = []
        repository.customer_order.side_effect = PermissionError("Not yours")
        state._repository_customer = Mock(return_value=(repository, {"id": 1}))
        state._qr_exists = Mock(return_value=False)
        CustomerState.load_account_page.fn(state)
        repository.customer_order.assert_called_once_with(1, 42)
        self.assertTrue(state.authenticated)
        self.assertEqual(state.session_token, "valid-session")
        self.assertEqual(state.checkout_orders, [])
        self.assertIn("could not be found", state.error)

    def test_expired_proof_submission_returns_to_same_checkout(self):
        state = self.state(token="expired")
        state._repository_customer = Mock(
            side_effect=PermissionError("Expired")
        )
        with patch.object(rx, "redirect") as redirect:
            asyncio.run(CustomerState.upload_payment_proof.fn(state, []))
            redirect.assert_called_once_with("/login")
        self.assertEqual(state._next_path, "/checkout?order=42")
        self.assertEqual(state.session_token, "")
        self.assertFalse(state.busy)

    def test_missing_qr_blocks_server_side_proof_submission(self):
        state = self.state(token="valid")
        repository = Mock()
        repository.customer_order.return_value = {"status": "awaiting_payment"}
        state._repository_customer = Mock(return_value=(repository, {"id": 1}))
        state._qr_exists = Mock(return_value=False)
        state.qr_available = True
        asyncio.run(CustomerState.upload_payment_proof.fn(state, []))
        self.assertFalse(state.qr_available)
        self.assertIn("QR not configured", state.error)
        repository.save_upload.assert_not_called()
        repository.submit_payment_proof.assert_not_called()

    def test_qr_presence_check_fails_closed(self):
        state = self.state()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            module = root / "app" / "states" / "customer_state.py"
            assets = root / "assets"
            assets.mkdir()
            with patch("app.states.customer_state.__file__", str(module)):
                self.assertFalse(state._qr_exists())
                qr = assets / "upi-qr.png"
                qr.touch()
                self.assertFalse(state._qr_exists())
                qr.write_bytes(b"studio-provided asset")
                self.assertTrue(state._qr_exists())
                qr.unlink()
                qr.symlink_to(assets / "missing.png")
                self.assertFalse(state._qr_exists())
        with patch(
            "app.states.customer_state.Path.is_file", side_effect=OSError
        ):
            self.assertFalse(state._qr_exists())

    def test_checkout_qr_and_customer_event_wiring(self):
        root = Path(__file__).resolve().parents[1]
        checkout = (root / "components" / "customer_pages.py").read_text()
        self.assertIn('src="/upi-qr.png"', checkout)
        self.assertNotIn("placeholder.svg", checkout)
        self.assertIn("CustomerState.qr_available", checkout)
        self.assertIn("CustomerState.upload_payment_proof(", checkout)
        self.assertIn('rx.upload_files(upload_id="payment-proof")', checkout)
        forms = (root / "components" / "customer_forms.py").read_text()
        self.assertIn("on_submit=CustomerState.order_bouquet", forms)
        self.assertIn("on_submit=CustomerState.authenticate_form", checkout)
        portrait = (root / "components" / "public_pages.py").read_text()
        self.assertIn("CustomerState.order_portrait(", portrait)
        self.assertIn(
            'rx.upload_files(upload_id="portrait-reference")', portrait
        )
        layout = (root / "components" / "public_layout.py").read_text()
        self.assertEqual(layout.count('nav_link("My orders", "/dashboard")'), 2)
        self.assertEqual(layout.count('nav_link("Log in", "/login")'), 2)
        tree = ast.parse((root / "app.py").read_text())
        pages = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "add_page"
        ]
        bouquet = next(
            node
            for node in pages
            if any(
                keyword.arg == "route"
                and isinstance(keyword.value, ast.Constant)
                and keyword.value.value == "/bouquets"
                for keyword in node.keywords
            )
        )
        on_load = next(
            keyword.value
            for keyword in bouquet.keywords
            if keyword.arg == "on_load"
        )
        self.assertEqual(
            ast.unparse(on_load),
            "[PublicState.load_public, CustomerState.restore]",
        )


if __name__ == "__main__":
    unittest.main()
