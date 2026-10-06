import reflex as rx
import asyncio
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace, MethodType
from unittest.mock import AsyncMock, patch

from app.states.store_database import (
    SCHEMA,
    connection,
    initialize_database,
    migrate_v2_to_v3,
)
from app.states.store_repository import StoreRepository
from app.states.public_state import PublicState
from app.states.admin_state import AdminState
from app.states.customer_state import CustomerState


class PortraitOptionTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "store.sqlite3"
        self.store = StoreRepository(self.path)
        with connection(self.path) as conn:
            conn.execute(
                "INSERT INTO users(id, name, phone, password_hash, is_admin) VALUES (1, 'Owner', '+919876543210', 'test', 1)"
            )
            conn.execute(
                "INSERT INTO users(id, name, phone, password_hash, is_admin) VALUES (2, 'Customer', '+919876543211', 'test', 0)"
            )
        self.size = self.store.list_portrait_sizes()[1]
        self.style = self.store.list_portrait_styles()[0]

    def order(self, **overrides):
        arguments = dict(
            portrait_size_id=self.size["id"], portrait_style_id=self.style["id"]
        )
        arguments.update(overrides)
        return self.store.create_order(
            2,
            "portrait",
            {"size": "forged", "style": "forged", "price_paise": "1"},
            **arguments,
        )

    def test_fresh_seed_and_restart_idempotence(self):
        for _ in range(3):
            initialize_database(self.path)
        self.assertEqual(
            [s["name"] for s in self.store.list_portrait_sizes()],
            ["A5", "A4", "A3", "A2"],
        )
        self.assertEqual(
            [s["name"] for s in self.store.list_portrait_styles()],
            ["Water color", "Pencil color"],
        )
        self.assertEqual(
            [s["price_paise"] for s in self.store.list_portrait_sizes()],
            [90000, 150000, 250000, 400000],
        )
        with connection(self.path) as conn:
            self.assertEqual(
                conn.execute("PRAGMA user_version").fetchone()[0], 3
            )
            migrate_v2_to_v3(conn)
        self.assertEqual(len(self.store.list_portrait_sizes()), 4)

    def test_version_two_migration_preserves_all_existing_records(self):
        legacy = self.path.with_name("legacy.sqlite3")
        with connection(legacy) as conn:
            for statement in SCHEMA:
                conn.execute(statement)
            conn.execute(
                "INSERT INTO users(id, name, phone, password_hash) VALUES (17, 'Legacy', '+919876543212', 'unchanged')"
            )
            conn.execute(
                "INSERT INTO site_settings(id, brand_name, background_color, text_color, accent_color, payment_qr_path) VALUES (1, 'Saved studio', '#F7F3EC', '#29231E', '#B76D50', 'saved.png')"
            )
            conn.execute(
                "INSERT INTO orders(id, user_id, kind, details, quantity, unit_price_paise, total_price_paise) VALUES (29, 17, 'portrait', ?, 1, 123456, 123456)",
                (json.dumps({"size": "A4", "note": "legacy"}),),
            )
            conn.execute("PRAGMA user_version = 2")
            before = {
                table: [
                    tuple(row) for row in conn.execute(f"SELECT * FROM {table}")
                ]
                for table in ("users", "orders", "site_settings")
            }
        initialize_database(legacy)
        initialize_database(legacy)
        with connection(legacy) as conn:
            for table, rows in before.items():
                self.assertEqual(
                    [
                        tuple(row)
                        for row in conn.execute(f"SELECT * FROM {table}")
                    ],
                    rows,
                )
            self.assertEqual(
                conn.execute("PRAGMA user_version").fetchone()[0], 3
            )
            self.assertEqual(
                conn.execute("SELECT count(*) FROM portrait_sizes").fetchone()[
                    0
                ],
                4,
            )
        self.assertEqual(
            StoreRepository(legacy).get_order(17, 29)["details"],
            {"size": "A4", "note": "legacy"},
        )

    def test_crud_validation_and_uniqueness(self):
        size_id = self.store.save_portrait_size(
            1, " Square ", "20 × 20 cm", 98765
        )
        style_id = self.store.save_portrait_style(1, " Charcoal ")
        self.store.save_portrait_size(
            1, "Square", "25 × 25 cm", 100000, size_id
        )
        self.store.save_portrait_style(1, "Ink", style_id)
        self.assertEqual(
            StoreRepository(self.path).list_portrait_styles()[-1]["name"], "Ink"
        )
        for name in ("", " ", "x" * 81, "a\x00b", " water COLOR "):
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.store.save_portrait_style(1, name)
        for price in (-1, True, 1.5, "100", 1000000001):
            with self.subTest(price=price), self.assertRaises(ValueError):
                self.store.save_portrait_size(1, "Test", "20 cm", price)
        for dimensions in ("", " ", "x" * 121):
            with self.assertRaises(ValueError):
                self.store.save_portrait_size(1, "Test", dimensions, 100)
        with self.assertRaises(ValueError):
            self.store.save_portrait_size(1, " a4 ", "20 cm", 100)
        for option_id in (0, -1, True, "1"):
            with self.assertRaises(ValueError):
                self.store.save_portrait_style(1, "Test", option_id)
            with self.assertRaises(ValueError):
                self.store.delete_portrait_option(1, "size", option_id)
        with self.assertRaises(LookupError):
            self.store.save_portrait_style(1, "Test", 99999)
        with self.assertRaises(LookupError):
            self.store.delete_portrait_option(1, "style", 99999)
        with self.assertRaises(ValueError):
            self.store.delete_portrait_option(1, "unknown", 1)

    def test_every_write_rechecks_persisted_admin_role(self):
        writes = (
            lambda actor: self.store.save_portrait_size(
                actor, "New", "20 cm", 100
            ),
            lambda actor: self.store.save_portrait_size(
                actor, "A4", "20 cm", 100, self.size["id"]
            ),
            lambda actor: self.store.save_portrait_style(actor, "New"),
            lambda actor: self.store.save_portrait_style(
                actor, "Water color", self.style["id"]
            ),
            lambda actor: self.store.delete_portrait_option(
                actor, "size", self.size["id"]
            ),
            lambda actor: self.store.delete_portrait_option(
                actor, "style", self.style["id"]
            ),
        )
        for actor in (2, 9999):
            for write in writes:
                with self.assertRaises(PermissionError):
                    write(actor)
        with connection(self.path) as conn:
            conn.execute("UPDATE users SET is_admin = 0 WHERE id = 1")
        for write in writes:
            with self.assertRaises(PermissionError):
                write(1)

    def test_current_price_labels_and_historical_snapshots(self):
        old = self.order(quantity=2)
        self.store.save_portrait_size(
            1, "Renamed A4", "22 × 30 cm", 187654, self.size["id"]
        )
        self.store.save_portrait_style(
            1, "Renamed watercolor", self.style["id"]
        )
        current = self.order(quantity=3)
        self.assertEqual(current["unit_price_paise"], 187654)
        self.assertEqual(current["total_price_paise"], 562962)
        self.assertEqual(current["details"]["price_paise"], "187654")
        self.assertEqual(current["details"]["size"], "Renamed A4")
        self.assertEqual(current["details"]["style"], "Renamed watercolor")
        self.assertEqual(current["details"]["dimensions"], "22 × 30 cm")
        self.assertIn(
            "Renamed watercolor",
            CustomerState._view(SimpleNamespace(), current)["title"],
        )
        self.store.delete_portrait_option(1, "size", self.size["id"])
        self.store.delete_portrait_option(1, "style", self.style["id"])
        restarted = StoreRepository(self.path)
        self.assertEqual(restarted.get_order(2, old["id"]), old)
        self.assertEqual(restarted.get_order(2, current["id"]), current)
        self.assertFalse(
            any(
                s["id"] == self.size["id"]
                for s in restarted.list_portrait_sizes()
            )
        )
        new_id = restarted.save_portrait_size(1, "A4", "21 × 29.7 cm", 150000)
        self.assertNotEqual(new_id, self.size["id"])

    def test_missing_removed_and_supplied_price_rejected_atomically(self):
        with self.assertRaises(ValueError):
            self.store.create_order(2, "portrait", {})
        with self.assertRaises(ValueError):
            self.order(portrait_price_paise=1)
        for field in ("portrait_size_id", "portrait_style_id"):
            for value in (0, True, "1"):
                with self.assertRaises(ValueError):
                    self.order(**{field: value})
            with self.assertRaises(LookupError):
                self.order(**{field: 99999})
        self.store.delete_portrait_option(1, "style", self.style["id"])
        with self.assertRaises(LookupError):
            self.order()
        self.assertEqual(self.store.list_orders(2), [])

    def test_selection_reconciles_rename_and_removal(self):
        state = SimpleNamespace(
            portrait_size_id=self.size["id"],
            portrait_style_id=self.style["id"],
            selection_notice="",
        )
        state._refresh_portrait_options = MethodType(
            PublicState._refresh_portrait_options, state
        )
        self.store.save_portrait_size(
            1, "Renamed", "20 cm", 100, self.size["id"]
        )
        state._refresh_portrait_options(self.store)
        self.assertEqual(state.portrait_size_id, self.size["id"])
        self.assertEqual(state.portrait_sizes[1]["name"], "Renamed")
        self.store.delete_portrait_option(1, "size", self.size["id"])
        state._refresh_portrait_options(self.store)
        self.assertEqual(state.portrait_size_id, 0)
        self.assertIn("no longer available", state.selection_notice)
        with patch(
            "app.states.public_state.StoreRepository", return_value=self.store
        ):
            PublicState.choose_style.fn(state, self.style["id"])
            self.assertEqual(state.portrait_style_id, 0)
            PublicState.choose_style.fn(state, self.style["id"])
            self.assertEqual(state.portrait_style_id, self.style["id"])

    def test_admin_events_check_sessions_and_refresh_public_options(self):
        public = SimpleNamespace(
            portrait_size_id=0, portrait_style_id=0, selection_notice=""
        )
        public._refresh_portrait_options = MethodType(
            PublicState._refresh_portrait_options, public
        )
        state = SimpleNamespace(
            busy=False,
            error="",
            notice="",
            delete_id=0,
            delete_kind="",
            _authorized=AsyncMock(return_value=(self.store, 1)),
            get_state=AsyncMock(return_value=public),
        )
        state._deny = lambda: AdminState._deny(state)

        async def consume(handler, *args):
            async for _ in handler.fn(state, *args):
                pass

        asyncio.run(
            consume(
                AdminState.save_portrait_option, "style", 0, {"name": "Ink"}
            )
        )
        state._authorized.assert_awaited_once()
        self.assertEqual(public.portrait_styles[-1]["name"], "Ink")
        ink = public.portrait_styles[-1]["id"]
        asyncio.run(AdminState.request_portrait_delete.fn(state, "style", ink))
        self.assertEqual(state.delete_id, ink)
        asyncio.run(AdminState.cancel_portrait_delete.fn(state))
        self.assertEqual(state.delete_id, 0)
        asyncio.run(AdminState.request_portrait_delete.fn(state, "style", ink))
        asyncio.run(consume(AdminState.confirm_portrait_delete))
        self.assertFalse(
            any(item["id"] == ink for item in public.portrait_styles)
        )
        state._authorized.side_effect = PermissionError("Expired session")
        asyncio.run(
            consume(
                AdminState.save_portrait_option,
                "style",
                0,
                {"name": "Unauthorized"},
            )
        )
        self.assertFalse(state.allowed)
        self.assertFalse(state.busy)
        self.assertFalse(
            any(
                s["name"] == "Unauthorized"
                for s in self.store.list_portrait_styles()
            )
        )


if __name__ == "__main__":
    unittest.main()
