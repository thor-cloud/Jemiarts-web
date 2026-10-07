import reflex as rx
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from app.states.store_database import (
    SCHEMA,
    PORTRAIT_SCHEMA,
    connection,
    initialize_database,
)
from app.states.store_repository import StoreRepository
from app.states.store_validation import hash_password, verify_password


class OwnerMigrationTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.path = self.root / "store.sqlite3"

    def owner(self, path):
        with connection(path) as conn:
            return dict(
                conn.execute(
                    "SELECT * FROM users WHERE username = 'admin'"
                ).fetchone()
            )

    def test_fresh_seed_format_random_salt_and_repository_mapping(self):
        repository = StoreRepository(self.path)
        first = self.owner(self.path)
        self.assertEqual(first["name"], "Studio Owner")
        self.assertEqual(first["phone"], "")
        self.assertEqual(first["email"], "")
        self.assertEqual(first["is_admin"], 1)
        self.assertEqual(first["must_change_password"], 1)
        algorithm, rounds, salt, digest = first["password_hash"].split("$")
        self.assertEqual((algorithm, rounds), ("pbkdf2_sha256", "600000"))
        self.assertEqual(len(bytes.fromhex(salt)), 16)
        self.assertEqual(len(bytes.fromhex(digest)), 32)
        self.assertTrue(verify_password("password", first["password_hash"]))
        self.assertFalse(verify_password("incorrect", first["password_hash"]))
        second_path = self.root / "second.sqlite3"
        initialize_database(second_path)
        self.assertNotEqual(
            salt, self.owner(second_path)["password_hash"].split("$")[2]
        )
        mapped = repository.get_customer(first["id"], first["id"])
        self.assertEqual(mapped["username"], "admin")
        self.assertIs(mapped["must_change_password"], True)
        self.assertNotIn("password_hash", mapped)
        with connection(self.path) as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE id = ?", (first["id"],)
            ).fetchone()
            self.assertEqual(
                repository._account(row)["password_hash"],
                first["password_hash"],
            )
        with self.assertRaises(ValueError):
            hash_password("password")
        with self.assertRaises(ValueError):
            repository.signup("Customer", "+919876543210", "password")

    def test_reinitialization_never_resets_owner_or_session(self):
        repository = StoreRepository(self.path)
        owner = self.owner(self.path)
        token = repository.create_session(owner["id"])
        replacement = hash_password("a replacement password")
        with connection(self.path) as conn:
            conn.execute(
                "UPDATE users SET password_hash = ?, must_change_password = 0, name = 'Saved owner' WHERE id = ?",
                (replacement, owner["id"]),
            )
        saved = self.owner(self.path)
        for _ in range(3):
            initialize_database(self.path)
        self.assertEqual(self.owner(self.path), saved)
        mapped = repository.session_admin(token)
        self.assertEqual(mapped["id"], owner["id"])
        self.assertEqual(mapped["username"], saved["username"])
        self.assertEqual(mapped["name"], saved["name"])
        self.assertIs(mapped["must_change_password"], False)
        self.assertNotIn("password_hash", mapped)
        with connection(self.path) as conn:
            self.assertEqual(
                conn.execute("SELECT count(*) FROM users").fetchone()[0], 1
            )

    def legacy(self, version):
        path = self.root / f"legacy-{version}.sqlite3"
        with connection(path) as conn:
            for statement in SCHEMA:
                conn.execute(statement)
            for statement in PORTRAIT_SCHEMA:
                conn.execute(statement)
            conn.execute(
                "INSERT INTO users(id, name, phone, email, password_hash, is_admin) VALUES (17, 'Historical owner', '+919876543210', 'saved@example.com', 'historical hash', 1)"
            )
            conn.execute(
                "INSERT INTO customer_sessions VALUES ('historical token hash', 17, 4102444800)"
            )
            conn.execute(
                "INSERT INTO bouquet_models(id, name, price_paise, image_path) VALUES (8, 'Saved bouquet', 12345, 'saved.png')"
            )
            conn.execute(
                "INSERT INTO orders(id, user_id, kind, bouquet_id, quantity, unit_price_paise, total_price_paise, reference_upload_path) VALUES (29, 17, 'bouquet', 8, 2, 12345, 24690, 'private.png')"
            )
            conn.execute(
                "INSERT INTO portrait_sizes(id, name, dimensions, price_paise) VALUES (14, 'Custom', '20 cm', 98765)"
            )
            conn.execute(
                "INSERT INTO portrait_styles(id, name) VALUES (16, 'Saved style')"
            )
            conn.execute(
                "INSERT INTO site_settings(id, brand_name, background_color, text_color, accent_color, payment_qr_path) VALUES (1, 'Saved studio', '#F7F3EC', '#29231E', '#B76D50', 'saved-qr.png')"
            )
            conn.execute(f"PRAGMA user_version = {version}")
            before = {
                table: [
                    dict(row) for row in conn.execute(f"SELECT * FROM {table}")
                ]
                for table in (
                    "users",
                    "customer_sessions",
                    "orders",
                    "bouquet_models",
                    "portrait_sizes",
                    "portrait_styles",
                    "site_settings",
                )
            }
        return path, before

    def test_versions_zero_through_three_preserve_every_historical_value(self):
        for version in range(4):
            with self.subTest(version=version):
                path, before = self.legacy(version)
                repository = StoreRepository(path)
                first_owner = self.owner(path)
                initialize_database(path)
                self.assertEqual(self.owner(path), first_owner)
                with connection(path) as conn:
                    self.assertEqual(
                        conn.execute("PRAGMA user_version").fetchone()[0], 4
                    )
                    self.assertEqual(
                        conn.execute("PRAGMA foreign_key_check").fetchall(), []
                    )
                    for table, rows in before.items():
                        for old in rows:
                            key = (
                                "token_hash"
                                if table == "customer_sessions"
                                else "id"
                            )
                            new = dict(
                                conn.execute(
                                    f"SELECT * FROM {table} WHERE {key} = ?",
                                    (old[key],),
                                ).fetchone()
                            )
                            self.assertEqual(
                                {field: new[field] for field in old}, old
                            )
                    self.assertEqual(
                        conn.execute("SELECT count(*) FROM users").fetchone()[
                            0
                        ],
                        len(before["users"]) + 1,
                    )
                    self.assertNotEqual(first_owner["id"], 17)
                    self.assertEqual(first_owner["is_admin"], 1)
                    self.assertEqual(first_owner["must_change_password"], 1)
                    legacy_user = conn.execute(
                        "SELECT * FROM users WHERE id = 17"
                    ).fetchone()
                    self.assertEqual(legacy_user["username"], "")
                    self.assertEqual(legacy_user["must_change_password"], 0)
                self.assertEqual(
                    repository.get_order(17, 29)["total_price_paise"], 24690
                )
                self.assertEqual(
                    repository.get_customer(17, 17)["username"], ""
                )

    def test_partial_upgrade_and_existing_admin_are_not_overwritten(self):
        path, _ = self.legacy(3)
        with connection(path) as conn:
            conn.execute(
                "ALTER TABLE users ADD COLUMN username TEXT NOT NULL DEFAULT ''"
            )
            conn.execute("UPDATE users SET username = 'admin' WHERE id = 17")
            saved = dict(
                conn.execute("SELECT * FROM users WHERE id = 17").fetchone()
            )
        initialize_database(path)
        owner = self.owner(path)
        self.assertEqual({field: owner[field] for field in saved}, saved)
        self.assertEqual(owner["must_change_password"], 0)
        with connection(path) as conn:
            self.assertEqual(
                conn.execute("SELECT count(*) FROM users").fetchone()[0], 1
            )
        initialize_database(path)
        self.assertEqual(self.owner(path), owner)

    def test_partial_unique_index_and_boolean_constraints(self):
        repository = StoreRepository(self.path)
        with patch.dict("os.environ", {"ARTIST_ADMIN_PHONE": ""}):
            first = repository.signup(
                "First", "+919876543210", "a secure customer password"
            )
            second = repository.signup(
                "Second", "+919876543211", "a secure customer password"
            )
        self.assertFalse(first["is_admin"])
        self.assertFalse(second["is_admin"])
        with connection(self.path) as conn:
            index = next(
                row
                for row in conn.execute("PRAGMA index_list(users)")
                if row["name"] == "users_username_unique"
            )
            self.assertEqual((index["unique"], index["partial"]), (1, 1))
        for statement, values in (
            (
                "UPDATE users SET username = 'admin' WHERE id = ?",
                (first["id"],),
            ),
            ("UPDATE users SET username = '   ' WHERE id = ?", (first["id"],)),
            ("UPDATE users SET username = NULL WHERE id = ?", (first["id"],)),
            (
                "UPDATE users SET must_change_password = 2 WHERE id = ?",
                (first["id"],),
            ),
            (
                "UPDATE users SET must_change_password = NULL WHERE id = ?",
                (first["id"],),
            ),
        ):
            with self.assertRaises(sqlite3.IntegrityError):
                with connection(self.path) as conn:
                    conn.execute(statement, values)

    def test_concurrent_initializers_seed_exactly_once(self):
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(initialize_database, [self.path] * 4))
        with connection(self.path) as conn:
            self.assertEqual(
                conn.execute("SELECT count(*) FROM users").fetchone()[0], 1
            )
            self.assertEqual(
                conn.execute("PRAGMA user_version").fetchone()[0], 4
            )

    def test_failed_seed_rolls_back_schema_and_version(self):
        path, before = self.legacy(3)
        with patch(
            "app.states.store_database.seed_owner",
            side_effect=RuntimeError("Seed failed"),
        ):
            with self.assertRaises(RuntimeError):
                initialize_database(path)
        with connection(path) as conn:
            self.assertEqual(
                conn.execute("PRAGMA user_version").fetchone()[0], 3
            )
            self.assertNotIn(
                "username",
                [
                    row["name"]
                    for row in conn.execute("PRAGMA table_info(users)")
                ],
            )
            self.assertEqual(
                [dict(row) for row in conn.execute("SELECT * FROM users")],
                before["users"],
            )
        initialize_database(path)
        self.assertTrue(
            verify_password("password", self.owner(path)["password_hash"])
        )

    def test_unsupported_version_is_not_modified(self):
        initialize_database(self.path)
        owner = self.owner(self.path)
        with connection(self.path) as conn:
            conn.execute("PRAGMA user_version = 5")
        with self.assertRaises(RuntimeError):
            initialize_database(self.path)
        self.assertEqual(self.owner(self.path), owner)
        with connection(self.path) as conn:
            self.assertEqual(
                conn.execute("PRAGMA user_version").fetchone()[0], 5
            )


if __name__ == "__main__":
    unittest.main()
