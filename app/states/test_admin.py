import reflex as rx
import asyncio
import tempfile
import unittest
import sqlite3
import inspect
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs, urlparse

from app.states.admin_state import AdminState
from app.states.store_database import connection
from app.states.store_repository import StoreRepository
from app.states.private_files import private_file


class AdminTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.public = self.root / "public"
        self.public.mkdir()
        uploads = patch.object(rx, "get_upload_dir", return_value=self.public)
        uploads.start()
        self.addCleanup(uploads.stop)
        self.store = StoreRepository(self.root / "data" / "store.sqlite3")
        environment = patch.dict("os.environ", {"ARTIST_ADMIN_PHONE": ""})
        environment.start()
        self.addCleanup(environment.stop)

    def signup(self, suffix: int):
        if suffix == 10:
            with connection(self.store.database_path) as conn:
                owner_id = conn.execute(
                    "SELECT id FROM users WHERE username = 'admin'"
                ).fetchone()[0]
            owner = self.store.get_customer(owner_id, owner_id)
            if owner["must_change_password"]:
                self.store.change_password(
                    owner_id, "password", "a rotated owner password"
                )
            return self.store.get_customer(owner_id, owner_id)
        return self.store.signup(
            "Test owner", f"+9198765432{suffix:02d}", "a secure test password"
        )

    def test_seeded_owner_keeps_concurrent_signups_unprivileged(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            users = list(pool.map(self.signup, [11, 13]))
        self.assertEqual(sum(user["is_admin"] for user in users), 0)
        self.assertTrue(self.signup(10)["is_admin"])
        self.assertFalse(self.signup(12)["is_admin"])
        configured = StoreRepository(self.root / "configured.sqlite3")
        with patch.dict("os.environ", {"ARTIST_ADMIN_PHONE": "+919876543214"}):
            self.assertFalse(
                configured.signup(
                    "Customer", "+919876543213", "a secure test password"
                )["is_admin"]
            )
            self.assertFalse(
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
            portrait_size_id=self.store.list_portrait_sizes()[1]["id"],
            portrait_style_id=self.store.list_portrait_styles()[0]["id"],
        )
        with self.assertRaises(ValueError):
            self.store.set_order_status(admin["id"], order["id"], "completed")
        private_file("proof.png", self.store.database_path).write_bytes(
            b"proof"
        )
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

    def workspace_state(self, token: str):
        state = SimpleNamespace(
            ready=False,
            allowed=False,
            busy=False,
            error="",
            notice="",
            orders=[],
            bouquets=[],
            portrait_sizes=[],
            portrait_styles=[],
            delete_kind="",
            delete_id=0,
            delete_name="",
            bouquet_id=0,
            bouquet_name="",
            bouquet_price="",
            bouquet_image="",
            hero_image="",
            payment_qr_image="",
            settings=self.store.get_settings(),
            _bouquet_upload="",
            _hero_upload="",
            _payment_qr_upload="",
            get_state=AsyncMock(
                return_value=SimpleNamespace(session_token=token)
            ),
        )
        state._authorized = lambda: AdminState._authorized(state)
        state._deny = lambda: AdminState._deny(state)
        state._load_orders = lambda repository, actor: AdminState._load_orders(
            state, repository, actor
        )
        state._image = lambda filename: AdminState._image(state, filename)
        state._stage_image = lambda target, files: AdminState._stage_image(
            state, target, files
        )
        return state

    def run_handler(self, state, handler, *args):
        async def run():
            result = handler.fn(state, *args)
            if inspect.isasyncgen(result):
                async for _ in result:
                    pass
            else:
                await result

        with patch(
            "app.states.admin_state.StoreRepository", return_value=self.store
        ):
            asyncio.run(run())

    def test_owner_workspace_review_saved_gallery_settings_and_snapshot(self):
        owner = self.signup(10)
        buyer = self.signup(11)
        other = self.signup(12)
        bouquet = self.store.save_bouquet(
            owner["id"], "Roses", 125000, "roses.png"
        )
        (self.public / "roses.png").write_bytes(b"saved gallery image")
        order = self.store.create_order(
            buyer["id"],
            "bouquet",
            {"model_name": bouquet["name"]},
            quantity=2,
            bouquet_id=bouquet["id"],
        )
        portrait = self.store.create_order(
            other["id"],
            "portrait",
            {},
            portrait_size_id=self.store.list_portrait_sizes()[0]["id"],
            portrait_style_id=self.store.list_portrait_styles()[0]["id"],
        )
        state = self.workspace_state(self.store.create_session(owner["id"]))
        self.run_handler(state, AdminState.load_admin)
        self.assertTrue(state.allowed)
        self.assertTrue(state.ready)
        self.assertEqual(
            {row["id"] for row in state.orders}, {order["id"], portrait["id"]}
        )
        row = next(row for row in state.orders if row["id"] == order["id"])
        self.assertEqual(row["name"], buyer["name"])
        self.assertEqual(row["phone"], buyer["phone"])
        self.assertEqual(row["amount"], 2500.0)
        self.assertIn("Roses", row["title"])
        self.assertEqual(state.bouquets, self.store.list_bouquets())
        self.assertEqual(state.portrait_sizes, self.store.list_portrait_sizes())
        self.assertEqual(
            state.portrait_styles, self.store.list_portrait_styles()
        )
        state.bouquet_id = bouquet["id"]
        self.run_handler(
            state,
            AdminState.save_bouquet,
            {"name": "Evening roses", "price": "1500.00"},
        )
        self.assertEqual(state.error, "")
        self.assertIn("saved", state.notice)
        settings = self.store.get_settings()
        settings.update(
            brand_name="Evening Studio",
            welcome_text="Made personally.",
            artist_biography="A small independent studio.",
            contact_number="+919876543210",
        )
        self.run_handler(state, AdminState.save_settings, settings)
        self.assertEqual(state.error, "")
        reopened = StoreRepository(self.store.database_path)
        saved = reopened.get_bouquet(bouquet["id"])
        self.assertEqual(saved["name"], "Evening roses")
        self.assertEqual(saved["price_paise"], 150000)
        self.assertEqual(saved["image_path"], "roses.png")
        self.assertEqual(reopened.list_bouquets(), state.bouquets)
        for key, value in settings.items():
            if key != "updated_at":
                self.assertEqual(reopened.get_settings()[key], value)
        self.assertEqual(reopened.get_order(owner["id"], order["id"]), order)
        self.assertEqual(
            reopened.get_order(owner["id"], portrait["id"]), portrait
        )
        self.run_handler(state, AdminState.load_admin)
        self.assertEqual(state.settings, reopened.get_settings())

    def test_portrait_edits_and_deletes_preserve_historical_order(self):
        owner = self.signup(10)
        buyer = self.signup(11)
        size = self.store.list_portrait_sizes()[0]
        style = self.store.list_portrait_styles()[0]
        order = self.store.create_order(
            buyer["id"],
            "portrait",
            {},
            quantity=2,
            portrait_size_id=size["id"],
            portrait_style_id=style["id"],
        )
        self.store.save_portrait_size(
            owner["id"], "Small", "15 × 22 cm", 170000, size["id"]
        )
        self.store.save_portrait_style(owner["id"], "Ink", style["id"])
        self.store.delete_portrait_option(owner["id"], "size", size["id"])
        self.store.delete_portrait_option(owner["id"], "style", style["id"])
        reopened = StoreRepository(self.store.database_path)
        self.assertEqual(reopened.get_order(owner["id"], order["id"]), order)
        self.assertNotIn(
            size["id"], [item["id"] for item in reopened.list_portrait_sizes()]
        )
        self.assertNotIn(
            style["id"],
            [item["id"] for item in reopened.list_portrait_styles()],
        )

    def test_non_admin_reads_writes_denied_quietly_and_database_unchanged(self):
        owner = self.signup(10)
        buyer = self.signup(11)
        other = self.signup(12)
        bouquet = self.store.save_bouquet(
            owner["id"], "Roses", 125000, "roses.png"
        )
        order = self.store.create_order(
            buyer["id"],
            "bouquet",
            {"model_name": "Roses"},
            bouquet_id=bouquet["id"],
        )
        settings = self.store.get_settings()
        size = self.store.list_portrait_sizes()[0]
        style = self.store.list_portrait_styles()[0]
        sizes = self.store.list_portrait_sizes()
        styles = self.store.list_portrait_styles()
        operations = (
            lambda: self.store.session_admin(
                self.store.create_session(other["id"])
            ),
            lambda: self.store.list_orders(other["id"], all_customers=True),
            lambda: self.store.get_order(other["id"], order["id"]),
            lambda: self.store.get_customer(other["id"], buyer["id"]),
            lambda: self.store.save_bouquet(
                other["id"], "Wrong", 1, "wrong.png"
            ),
            lambda: self.store.save_bouquet(
                other["id"], "Wrong", 1, "wrong.png", bouquet["id"]
            ),
            lambda: self.store.update_settings(other["id"], settings),
            lambda: self.store.set_order_status(
                other["id"], order["id"], "cancelled"
            ),
            lambda: self.store.save_portrait_size(
                other["id"], "Wrong", "1 cm", 1, size["id"]
            ),
            lambda: self.store.save_portrait_style(
                other["id"], "Wrong", style["id"]
            ),
            lambda: self.store.delete_portrait_option(
                other["id"], "size", size["id"]
            ),
            lambda: self.store.delete_portrait_option(
                other["id"], "style", style["id"]
            ),
        )
        with patch("app.states.store_database.logging.exception") as log:
            for operation in operations:
                with (
                    self.subTest(operation=operation),
                    self.assertRaises(PermissionError),
                ):
                    operation()
            log.assert_not_called()
        self.assertEqual(self.store.get_order(owner["id"], order["id"]), order)
        self.assertEqual(self.store.list_bouquets(), [bouquet])
        self.assertEqual(self.store.get_settings(), settings)
        self.assertEqual(self.store.list_portrait_sizes(), sizes)
        self.assertEqual(self.store.list_portrait_styles(), styles)

    def test_revoked_owner_handlers_clear_every_loaded_and_staged_field_quietly(
        self,
    ):
        owner = self.signup(10)
        token = self.store.create_session(owner["id"])
        self.store.revoke_session(token)
        handlers = (
            (AdminState.load_admin, ()),
            (AdminState.save_status, (1, {"status": "cancelled"})),
            (AdminState.edit_bouquet, (1,)),
            (AdminState.new_bouquet, ()),
            (AdminState.stage_bouquet_image, ([],)),
            (AdminState.stage_hero_image, ([],)),
            (AdminState.stage_payment_qr_image, ([],)),
            (AdminState.save_bouquet, ({"name": "Wrong", "price": "1"},)),
            (AdminState.save_portrait_option, ("size", 0, {})),
            (AdminState.request_portrait_delete, ("size", 1)),
            (AdminState.cancel_portrait_delete, ()),
            (AdminState.confirm_portrait_delete, ()),
            (AdminState.save_settings, ({},)),
        )
        for handler, args in handlers:
            with self.subTest(handler=handler.fn.__name__):
                state = self.workspace_state(token)
                state.allowed = True
                for field in (
                    "orders",
                    "bouquets",
                    "portrait_sizes",
                    "portrait_styles",
                ):
                    setattr(state, field, [{"private": "previous owner data"}])
                for field in (
                    "delete_kind",
                    "delete_name",
                    "bouquet_name",
                    "bouquet_price",
                    "bouquet_image",
                    "hero_image",
                    "payment_qr_image",
                    "notice",
                    "_bouquet_upload",
                    "_hero_upload",
                    "_payment_qr_upload",
                ):
                    setattr(state, field, "previous owner data")
                state.delete_id = state.bouquet_id = 42
                state.settings = dict.fromkeys(
                    state.settings, "previous owner data"
                )
                with patch("app.states.admin_state.logging.exception") as log:
                    self.run_handler(state, handler, *args)
                    log.assert_not_called()
                self.assertFalse(state.allowed)
                self.assertFalse(state.busy)
                for field in (
                    "orders",
                    "bouquets",
                    "portrait_sizes",
                    "portrait_styles",
                ):
                    self.assertEqual(getattr(state, field), [])
                for field in (
                    "delete_kind",
                    "delete_name",
                    "bouquet_name",
                    "bouquet_price",
                    "bouquet_image",
                    "hero_image",
                    "payment_qr_image",
                    "notice",
                    "_bouquet_upload",
                    "_hero_upload",
                    "_payment_qr_upload",
                ):
                    self.assertEqual(getattr(state, field), "")
                self.assertEqual(state.delete_id, 0)
                self.assertEqual(state.bouquet_id, 0)
                self.assertNotIn("previous owner data", str(state.settings))
                self.assertEqual(
                    set(state.settings), set(self.store.get_settings())
                )
                self.assertIn("Administrator access is required", state.error)

    def test_connection_rolls_back_expected_rejections_without_tracebacks(self):
        for error in (
            PermissionError("Denied"),
            ValueError("Invalid"),
            LookupError("Missing"),
        ):
            with self.subTest(error=type(error).__name__):
                with patch(
                    "app.states.store_database.logging.exception"
                ) as log:
                    with self.assertRaises(type(error)):
                        with connection(self.store.database_path) as conn:
                            conn.execute(
                                "UPDATE site_settings SET brand_name = 'Rejected' WHERE id = 1"
                            )
                            raise error
                    log.assert_not_called()
                self.assertEqual(
                    self.store.get_settings()["brand_name"], "Artist Studio"
                )

    def test_connection_unexpected_failures_still_log_and_rollback(self):
        for error in (
            sqlite3.OperationalError("Database failure"),
            OSError("Disk failure"),
            RuntimeError("Unexpected"),
        ):
            with self.subTest(error=type(error).__name__):
                with patch(
                    "app.states.store_database.logging.exception"
                ) as log:
                    with self.assertRaises(type(error)):
                        with connection(self.store.database_path) as conn:
                            conn.execute(
                                "UPDATE site_settings SET brand_name = 'Failed' WHERE id = 1"
                            )
                            raise error
                    log.assert_called_once()
                self.assertEqual(
                    self.store.get_settings()["brand_name"], "Artist Studio"
                )

    def test_unexpected_workspace_load_failure_still_reports_error(self):
        state = self.workspace_state("session")
        state._authorized = AsyncMock(
            side_effect=RuntimeError("Unexpected failure")
        )
        with patch("app.states.admin_state.logging.exception") as log:
            self.run_handler(state, AdminState.load_admin)
            log.assert_called_once()
        self.assertTrue(state.ready)
        self.assertFalse(state.allowed)
        self.assertIn("could not be loaded", state.error)


if __name__ == "__main__":
    unittest.main()
