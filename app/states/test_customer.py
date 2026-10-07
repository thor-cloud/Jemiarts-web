import reflex as rx
import tempfile
import unittest
import asyncio
import ast
from pathlib import Path
from types import MethodType, SimpleNamespace
from unittest.mock import patch, Mock, AsyncMock

from app.states.customer_state import CustomerState

from app.states.store_repository import StoreRepository
from app.states.store_database import connection
from app.states.private_files import private_file
from app.states.test_payment_qr import png_test_image


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
            portrait_size_id=self.repository.list_portrait_sizes()[1]["id"],
            portrait_style_id=self.repository.list_portrait_styles()[0]["id"],
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
            private_file(
                "proof.png", self.repository.database_path
            ).write_bytes(b"saved image")
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

    def test_invalid_proof_count_keeps_saved_order_awaiting_payment(self):
        order = self.repository.create_order(
            self.customer["id"],
            "portrait",
            {},
            portrait_size_id=self.repository.list_portrait_sizes()[0]["id"],
            portrait_style_id=self.repository.list_portrait_styles()[0]["id"],
        )
        for count in (0, 2):
            with self.subTest(count=count):
                state = CustomerFlowRegressionTests().state(
                    order=str(order["id"]), token="valid"
                )
                state._repository_customer = Mock(
                    return_value=(self.repository, self.customer)
                )
                files = [
                    SimpleNamespace(close=AsyncMock()) for _ in range(count)
                ]
                with (
                    patch("app.states.customer_state.logging.exception") as log,
                    patch.object(self.repository, "save_upload") as save,
                    patch.object(
                        self.repository, "submit_payment_proof"
                    ) as submit,
                ):
                    result = asyncio.run(
                        CustomerState.upload_payment_proof.fn(state, files)
                    )
                    self.assertIsNone(result)
                    log.assert_not_called()
                    save.assert_not_called()
                    submit.assert_not_called()
                saved = self.repository.customer_order(
                    self.customer["id"], order["id"]
                )
                self.assertEqual(saved["status"], "awaiting_payment")
                self.assertEqual(saved["payment_proof_path"], "")
                self.assertEqual(
                    state.error, "Select one payment screenshot first."
                )
                self.assertEqual(state.notice, "")
                self.assertEqual(state.session_token, "valid")
                self.assertFalse(state.busy)
                for file in files:
                    file.close.assert_awaited_once()

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
            admin_access=False,
            must_change_password=False,
            password_change_mode=False,
            customer_name="",
            _actor_id=0,
            _next_path="/dashboard",
            ready=False,
            error="",
            notice="",
            orders=[],
            checkout_orders=[],
            qr_available=False,
            qr_image_path="",
            qr_image_url="",
            busy=False,
        )
        for name in (
            "_clear_identity",
            "_remember_account_path",
            "_view",
            "_repository_customer",
            "_load_payment_qr",
            "_built_in_payment_qr",
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
        state._repository_customer = Mock(
            return_value=(
                Mock(),
                {"id": 1, "must_change_password": False, "is_admin": False},
            )
        )
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
        state._repository_customer = Mock(
            return_value=(
                repository,
                {"id": 1, "must_change_password": False, "is_admin": False},
            )
        )
        repository.get_settings.return_value = {"payment_qr_path": ""}
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

    def test_missing_override_uses_fallback_but_requires_a_proof(self):
        state = self.state(token="valid")
        repository = Mock()
        repository.customer_order.return_value = {"status": "awaiting_payment"}
        state._repository_customer = Mock(
            return_value=(
                repository,
                {"id": 1, "must_change_password": False, "is_admin": False},
            )
        )
        repository.get_settings.return_value = {"payment_qr_path": ""}
        state.qr_available = True
        with patch("app.states.customer_state.logging.exception") as log:
            result = asyncio.run(
                CustomerState.upload_payment_proof.fn(state, [])
            )
            log.assert_not_called()
        self.assertIsNone(result)
        self.assertFalse(state.busy)
        self.assertEqual(state.notice, "")
        self.assertTrue(state.qr_available)
        self.assertEqual(state.qr_image_path, "")
        self.assertTrue(state.qr_image_url.startswith("data:image/png;base64,"))
        repository.get_settings.assert_called_once_with()
        self.assertEqual(state.error, "Select one payment screenshot first.")
        repository.save_upload.assert_not_called()
        repository.submit_payment_proof.assert_not_called()

    def test_expected_proof_validation_shows_message_without_error_logging(
        self,
    ):
        for error in (
            ValueError("Invalid screenshot."),
            LookupError("Order unavailable."),
        ):
            with self.subTest(error=type(error).__name__):
                state = self.state(token="valid")
                repository = Mock()
                repository.customer_order.return_value = {
                    "status": "awaiting_payment"
                }
                repository.get_settings.return_value = {"payment_qr_path": ""}
                repository.save_upload = AsyncMock(side_effect=error)
                state._repository_customer = Mock(
                    return_value=(repository, {"id": 1})
                )
                file = SimpleNamespace(close=AsyncMock())
                with patch(
                    "app.states.customer_state.logging.exception"
                ) as log:
                    asyncio.run(
                        CustomerState.upload_payment_proof.fn(state, [file])
                    )
                    log.assert_not_called()
                self.assertEqual(state.error, str(error))
                self.assertFalse(state.busy)
                self.assertEqual(state.notice, "")
                repository.submit_payment_proof.assert_not_called()
                file.close.assert_awaited_once()

    def test_unexpected_proof_failure_still_logs_and_cleans_saved_file(self):
        state = self.state(token="valid")
        repository = Mock()
        repository.customer_order.return_value = {"status": "awaiting_payment"}
        repository.get_settings.return_value = {"payment_qr_path": ""}
        repository.save_upload = AsyncMock(return_value="proof.png")
        repository.submit_payment_proof.side_effect = RuntimeError(
            "Save failed"
        )
        state._repository_customer = Mock(
            return_value=(
                repository,
                {"id": 1, "must_change_password": False, "is_admin": False},
            )
        )
        file = SimpleNamespace(close=AsyncMock())
        saved_file = Mock()
        with (
            patch("app.states.customer_state.logging.exception") as log,
            patch(
                "app.states.customer_state.private_file",
                return_value=saved_file,
            ),
        ):
            asyncio.run(CustomerState.upload_payment_proof.fn(state, [file]))
            log.assert_called_once_with("Error: Save failed")
        saved_file.unlink.assert_called_once_with(missing_ok=True)
        file.close.assert_awaited_once()
        self.assertFalse(state.busy)
        self.assertEqual(state.notice, "")
        self.assertEqual(
            state.error,
            "Your payment proof could not be saved. Please try again.",
        )

    def test_checkout_proof_button_requires_exactly_one_selected_file(self):
        root = Path(__file__).resolve().parents[1]
        source = (root / "components" / "customer_pages.py").read_text()
        tree = ast.parse(source)
        checkout = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "checkout_order"
        )
        button = next(
            node
            for node in ast.walk(checkout)
            if isinstance(node, ast.Call)
            and any(
                keyword.arg == "on_click"
                and "CustomerState.upload_payment_proof"
                in ast.unparse(keyword.value)
                for keyword in node.keywords
            )
        )
        props = {keyword.arg: keyword.value for keyword in button.keywords}
        guard = props["disabled"]
        self.assertIsInstance(guard, ast.BinOp)
        self.assertIsInstance(guard.op, ast.BitOr)
        self.assertEqual(
            ast.unparse(guard),
            "CustomerState.busy | ~CustomerState.qr_available | "
            "(rx.selected_files('payment-proof').length() != 1)",
        )
        self.assertIn(
            "rx.upload_files(upload_id='payment-proof')",
            ast.unparse(props["on_click"]),
        )
        self.assertIn("Upload proof for review", ast.unparse(button))
        self.assertIn("Choose your payment screenshot", ast.unparse(checkout))
        self.assertIn(
            "The status changes to payment review only after the file is saved.",
            ast.unparse(checkout),
        )

    def test_saved_qr_priority_and_invalid_override_fallback(self):
        state = self.state()
        repository = Mock()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(rx, "get_upload_dir", return_value=root):
                repository.get_settings.return_value = {
                    "payment_qr_path": "artist.png"
                }
                state._load_payment_qr(repository)
                self.assertTrue(state.qr_available)
                qr = root / "artist.png"
                qr.touch()
                state._load_payment_qr(repository)
                self.assertFalse(state.qr_available)
                qr.write_bytes(b"not an image or QR")
                state._load_payment_qr(repository)
                self.assertFalse(state.qr_available)
                qr.write_bytes(png_test_image())
                state._load_payment_qr(repository)
                self.assertTrue(state.qr_available)
                self.assertEqual(state.qr_image_path, "artist.png")
                for invalid in (
                    "",
                    "../artist.png",
                    "missing.png",
                    "https://example.com/qr.png",
                ):
                    repository.get_settings.return_value = {
                        "payment_qr_path": invalid
                    }
                    state._load_payment_qr(repository)
                    self.assertFalse(state.qr_available)
                    self.assertEqual(state.qr_image_path, "")
                repository.get_settings.return_value = {
                    "payment_qr_path": "artist.png"
                }
                qr.unlink()
                qr.symlink_to(root / "missing.png")
                state._load_payment_qr(repository)
                self.assertFalse(state.qr_available)
                self.assertEqual(state.qr_image_path, "")
        with patch(
            "app.states.store_uploads.Path.is_file", side_effect=OSError
        ):
            state._load_payment_qr(repository)
            self.assertTrue(state.qr_available)
            self.assertEqual(state.qr_image_path, "")

    def test_checkout_loads_saved_qr_and_rechecks_after_upload(self):
        state = self.state(token="valid")
        repository = Mock()
        order = {
            "id": 42,
            "kind": "bouquet",
            "bouquet_id": 1,
            "details": {"model_name": "Ordered bouquet"},
            "quantity": 1,
            "unit_price_paise": 100,
            "total_price_paise": 100,
            "status": "awaiting_payment",
            "payment_proof_path": "",
            "created_at": "2026-01-01",
        }
        repository.customer_order.return_value = order
        repository.list_orders.return_value = [order]
        state._repository_customer = Mock(
            return_value=(
                repository,
                {"id": 1, "must_change_password": False, "is_admin": False},
            )
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "artist.png").write_bytes(png_test_image())
            with patch.object(rx, "get_upload_dir", return_value=root):
                repository.get_settings.return_value = {
                    "payment_qr_path": "artist.png"
                }
                CustomerState.load_account_page.fn(state)
                self.assertTrue(state.qr_available)
                self.assertEqual(state.qr_image_path, "artist.png")
                repository.get_settings.return_value = {"payment_qr_path": ""}
                file = SimpleNamespace(close=AsyncMock())
                repository.save_upload = AsyncMock(return_value="proof.png")
                repository.submit_payment_proof.return_value = {
                    **order,
                    "status": "payment_review",
                    "payment_proof_path": "proof.png",
                }
                asyncio.run(
                    CustomerState.upload_payment_proof.fn(state, [file])
                )
                repository.save_upload.assert_awaited_once()
                repository.submit_payment_proof.assert_called_once_with(
                    1, 42, "proof.png"
                )
                file.close.assert_awaited()
                self.assertTrue(state.qr_available)
                self.assertIn("not payment confirmation", state.notice)
                repository.submit_payment_proof.reset_mock()
                repository.get_settings.side_effect = [
                    {"payment_qr_path": "artist.png"},
                    {"payment_qr_path": ""},
                ]
                (root / "proof.png").write_bytes(png_test_image())
                repository.save_upload = AsyncMock(return_value="proof.png")
                asyncio.run(
                    CustomerState.upload_payment_proof.fn(state, [file])
                )
                repository.submit_payment_proof.assert_called_once_with(
                    1, 42, "proof.png"
                )
                self.assertTrue((root / "proof.png").exists())
                self.assertFalse(state.qr_available)
                self.assertEqual(state.qr_image_path, "")

    def test_portrait_requires_exactly_one_reference_without_error_logging(
        self,
    ):
        for count in (0, 2):
            with self.subTest(count=count):
                state = self.state(token="valid")
                repository = Mock()
                state._repository_customer = Mock(
                    return_value=(repository, {"id": 1})
                )
                state.get_state = AsyncMock(
                    return_value=SimpleNamespace(
                        portrait_size_id=2, portrait_style_id=1
                    )
                )
                files = [
                    SimpleNamespace(close=AsyncMock()) for _ in range(count)
                ]
                with patch(
                    "app.states.customer_state.logging.exception"
                ) as log:
                    asyncio.run(CustomerState.order_portrait.fn(state, files))
                    log.assert_not_called()
                self.assertEqual(
                    state.error, "Select one reference image before ordering."
                )
                self.assertFalse(state.busy)
                self.assertEqual(state.session_token, "valid")
                repository.save_upload.assert_not_called()
                repository.create_order.assert_not_called()
                for file in files:
                    file.close.assert_awaited_once()

    def test_anonymous_portrait_redirect_does_not_log_expected_error(self):
        state = self.state()
        state._repository_customer = Mock(
            side_effect=PermissionError("Please log in to continue.")
        )
        file = SimpleNamespace(close=AsyncMock())
        with (
            patch("app.states.customer_state.logging.exception") as log,
            patch.object(rx, "redirect") as redirect,
        ):
            asyncio.run(CustomerState.order_portrait.fn(state, [file]))
            log.assert_not_called()
            redirect.assert_called_once_with("/login")
        self.assertEqual(state._next_path, "/portraits")
        self.assertEqual(state.session_token, "")
        self.assertFalse(state.authenticated)
        self.assertFalse(state.busy)
        file.close.assert_awaited_once()

    def test_unexpected_portrait_failure_logs_and_cleans_saved_reference(self):
        state = self.state(token="valid")
        repository = Mock()
        repository.save_upload = AsyncMock(return_value="reference.png")
        repository.create_order.side_effect = RuntimeError("Save failed")
        repository.database_path = Path("test.sqlite3")
        state._repository_customer = Mock(
            return_value=(
                repository,
                {"id": 1, "must_change_password": False, "is_admin": False},
            )
        )
        state.get_state = AsyncMock(
            return_value=SimpleNamespace(
                portrait_size_id=2, portrait_style_id=1
            )
        )
        file = SimpleNamespace(close=AsyncMock())
        saved_file = Mock()
        with (
            patch("app.states.customer_state.logging.exception") as log,
            patch(
                "app.states.customer_state.private_file",
                return_value=saved_file,
            ),
        ):
            asyncio.run(CustomerState.order_portrait.fn(state, [file]))
            log.assert_called_once()
        saved_file.unlink.assert_called_once_with(missing_ok=True)
        file.close.assert_awaited_once()
        self.assertFalse(state.busy)
        self.assertIn("could not be saved", state.error)

    def test_portrait_action_disabled_guard_and_accessible_help(self):
        root = Path(__file__).resolve().parents[1]
        source = (root / "components" / "public_pages.py").read_text()
        tree = ast.parse(source)
        page = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "portraits_page"
        )
        button = next(
            node
            for node in ast.walk(page)
            if isinstance(node, ast.Call)
            and any(
                keyword.arg == "on_click"
                and "CustomerState.order_portrait" in ast.unparse(keyword.value)
                for keyword in node.keywords
            )
        )
        props = {keyword.arg: keyword.value for keyword in button.keywords}
        guard = props["disabled"]
        self.assertIsInstance(guard, ast.BinOp)
        self.assertIsInstance(guard.op, ast.BitOr)
        guard_source = ast.unparse(guard)
        self.assertIn(
            "rx.selected_files('portrait-reference').length() != 1",
            guard_source,
        )
        self.assertIn("CustomerState.busy", guard_source)
        self.assertIn("PublicState.portrait_size_id == 0", guard_source)
        self.assertIn("PublicState.portrait_style_id == 0", guard_source)
        self.assertEqual(
            ast.literal_eval(props["aria_describedby"]), "portrait-order-help"
        )
        self.assertIn('id="portrait-order-help"', source)
        self.assertIn(
            "Choose a size, art style and one reference photo before ordering.",
            source,
        )
        self.assertIn(
            "rx.upload_files(upload_id='portrait-reference')",
            ast.unparse(props["on_click"]),
        )

    def test_checkout_qr_and_customer_event_wiring(self):
        root = Path(__file__).resolve().parents[1]
        checkout = (root / "components" / "customer_pages.py").read_text()
        self.assertIn(
            "rx.get_upload_url(CustomerState.qr_image_path)", checkout
        )
        self.assertNotIn("upi-qr.png", checkout)
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
