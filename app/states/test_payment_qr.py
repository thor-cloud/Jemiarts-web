import reflex as rx
import asyncio
import struct
import tempfile
import unittest
import zlib
from pathlib import Path
from types import MethodType, SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.states.admin_state import AdminState
from app.states.store_database import SCHEMA, connection, initialize_database
from app.states.store_repository import StoreRepository
from app.states.store_uploads import require_saved_png


def png_test_image() -> bytes:
    """A one-pixel image for format tests, not a QR or payment recipient."""

    def chunk(kind: bytes, payload: bytes) -> bytes:
        body = b"".join((kind, payload))
        return b"".join(
            (
                struct.pack(">I", len(payload)),
                body,
                struct.pack(">I", zlib.crc32(body)),
            )
        )

    return b"".join(
        (
            b"\x89PNG\r\n\x1a\n",
            chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)),
            chunk(b"IDAT", zlib.compress(b"\x00\xff\xff\xff")),
            chunk(b"IEND", b""),
        )
    )


class PaymentQRTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        uploads = patch.object(rx, "get_upload_dir", return_value=self.root)
        uploads.start()
        self.addCleanup(uploads.stop)
        environment = patch.dict("os.environ", {"ARTIST_ADMIN_PHONE": ""})
        environment.start()
        self.addCleanup(environment.stop)

    def file(self, data: bytes):
        return SimpleNamespace(
            read=AsyncMock(return_value=data), close=AsyncMock()
        )

    def accounts(self):
        store = StoreRepository(self.root / "store.sqlite3")
        admin = store.signup("Owner", "+919876543210", "a secure test password")
        customer = store.signup(
            "Customer", "+919876543211", "another secure password"
        )
        return store, admin["id"], customer["id"]

    def test_version_one_upgrade_retains_all_existing_rows(self):
        database = self.root / "legacy.sqlite3"
        with connection(database) as conn:
            for statement in SCHEMA:
                conn.execute(
                    statement.replace(
                        "        payment_qr_path TEXT NOT NULL DEFAULT '',\n",
                        "",
                    )
                )
            conn.execute(
                "INSERT INTO users(id, name, phone, password_hash, is_admin) VALUES (1, 'Owner', '+919876543210', 'unchanged hash', 1)"
            )
            conn.execute(
                "INSERT INTO bouquet_models(id, name, price_paise, image_path) VALUES (1, 'Saved bouquet', 12345, 'saved.png')"
            )
            conn.execute(
                "INSERT INTO orders(id, user_id, kind, bouquet_id, quantity, unit_price_paise, total_price_paise) VALUES (1, 1, 'bouquet', 1, 2, 12345, 24690)"
            )
            conn.execute(
                "INSERT INTO site_settings(id, brand_name, background_color, text_color, accent_color, hero_image_path, welcome_text, artist_biography, contact_number) VALUES (1, 'Saved studio', '#F7F3EC', '#29231E', '#B76D50', 'hero.png', 'Saved welcome', 'Saved biography', '+919876543210')"
            )
            conn.execute("PRAGMA user_version = 1")
            before = {
                table: [
                    tuple(row) for row in conn.execute(f"SELECT * FROM {table}")
                ]
                for table in ("users", "bouquet_models", "orders")
            }
            old_settings = dict(
                conn.execute("SELECT * FROM site_settings").fetchone()
            )
        initialize_database(database)
        initialize_database(database)
        with connection(database) as conn:
            self.assertEqual(
                conn.execute("PRAGMA user_version").fetchone()[0], 2
            )
            for table, rows in before.items():
                self.assertEqual(
                    [
                        tuple(row)
                        for row in conn.execute(f"SELECT * FROM {table}")
                    ],
                    rows,
                )
            new_settings = dict(
                conn.execute("SELECT * FROM site_settings").fetchone()
            )
            self.assertEqual(new_settings.pop("payment_qr_path"), "")
            self.assertEqual(new_settings, old_settings)
            column = next(
                row
                for row in conn.execute("PRAGMA table_info(site_settings)")
                if row["name"] == "payment_qr_path"
            )
            self.assertEqual(column["type"], "TEXT")
            self.assertEqual(column["notnull"], 1)
            self.assertEqual(column["dflt_value"], "''")

    def test_saved_qr_persists_and_requires_admin_and_valid_png(self):
        store, admin, customer = self.accounts()
        self.assertEqual(store.get_settings()["payment_qr_path"], "")
        file = self.file(png_test_image())
        filename = asyncio.run(
            store.save_admin_upload(admin, file, png_only=True)
        )
        self.assertEqual(require_saved_png(filename), filename)
        settings = store.get_settings()
        settings["payment_qr_path"] = filename
        with self.assertRaises(PermissionError):
            store.update_settings(customer, settings)
        self.assertEqual(store.get_settings()["payment_qr_path"], "")
        store.update_settings(admin, settings)
        self.assertEqual(
            StoreRepository(store.database_path).get_settings()[
                "payment_qr_path"
            ],
            filename,
        )
        for invalid in (
            "missing.png",
            "../other.png",
            "invalid.png",
            "photo.jpg",
        ):
            (self.root / "invalid.png").write_bytes(
                b"\x89PNG\r\n\x1a\nnot a valid image"
            )
            (self.root / "photo.jpg").write_bytes(png_test_image())
            settings["payment_qr_path"] = invalid
            with self.assertRaises(ValueError):
                store.update_settings(admin, settings)
            self.assertEqual(store.get_settings()["payment_qr_path"], filename)
        denied = self.file(png_test_image())
        with self.assertRaises(PermissionError):
            asyncio.run(
                store.save_admin_upload(customer, denied, png_only=True)
            )
        denied.read.assert_not_awaited()
        before = set(self.root.iterdir())
        for data in (
            b"\xff\xd8\xffnot PNG",
            b"\x89PNG\r\n\x1a\n",
            b"",
            png_test_image()[:-1],
        ):
            with self.assertRaises(ValueError):
                asyncio.run(
                    store.save_admin_upload(
                        admin, self.file(data), png_only=True
                    )
                )
            self.assertEqual(set(self.root.iterdir()), before)

    def staging_state(self, store, actor):
        state = SimpleNamespace(
            busy=False,
            error="",
            notice="",
            allowed=True,
            orders=[],
            bouquets=[],
            _authorized=AsyncMock(return_value=(store, actor)),
            _payment_qr_upload="",
            payment_qr_image="",
            _hero_upload="",
            hero_image="",
            _bouquet_upload="",
            bouquet_image="",
        )
        for name in ("_stage_image", "_discard", "_deny", "_image"):
            setattr(state, name, MethodType(getattr(AdminState, name), state))
        return state

    def test_staging_is_authorized_and_not_published_until_saved(self):
        store, admin, customer = self.accounts()
        state = self.staging_state(store, admin)
        file = self.file(png_test_image())
        asyncio.run(AdminState.stage_payment_qr_image.fn(state, [file]))
        filename = state._payment_qr_upload
        self.assertTrue(filename)
        self.assertEqual(state.payment_qr_image, filename)
        self.assertEqual(store.get_settings()["payment_qr_path"], "")
        self.assertEqual(state._authorized.await_count, 2)
        state.settings = store.get_settings()
        form = {
            key: state.settings[key]
            for key in (
                "brand_name",
                "background_color",
                "text_color",
                "accent_color",
                "welcome_text",
                "artist_biography",
                "contact_number",
            )
        }
        form["payment_qr_path"] = "client-injected.png"

        async def save():
            async for _ in AdminState.save_settings.fn(state, form):
                pass

        asyncio.run(save())
        self.assertEqual(store.get_settings()["payment_qr_path"], filename)
        self.assertEqual(state._payment_qr_upload, "")
        denied = self.staging_state(store, customer)
        denied._authorized.side_effect = PermissionError("Access denied")
        file = self.file(png_test_image())
        before = set(self.root.iterdir())
        asyncio.run(AdminState.stage_payment_qr_image.fn(denied, [file]))
        file.read.assert_not_awaited()
        file.close.assert_awaited()
        self.assertEqual(set(self.root.iterdir()), before)
        self.assertFalse(denied.allowed)

    def test_revoked_session_discards_staged_qr(self):
        store, admin, _ = self.accounts()
        state = self.staging_state(store, admin)
        state._authorized.side_effect = [
            (store, admin),
            PermissionError("Revoked"),
        ]
        before = set(self.root.iterdir())
        asyncio.run(
            AdminState.stage_payment_qr_image.fn(
                state, [self.file(png_test_image())]
            )
        )
        self.assertEqual(set(self.root.iterdir()), before)
        self.assertEqual(state._payment_qr_upload, "")
        self.assertFalse(state.allowed)


if __name__ == "__main__":
    unittest.main()
