import reflex as rx
import logging
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from collections.abc import Iterator


LOCAL_DATABASE = (
    Path(__file__).resolve().parents[2] / ".local" / "artist_store.sqlite3"
)
SCHEMA_VERSION = 3

SCHEMA = (
    """CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL CHECK(length(trim(name)) BETWEEN 1 AND 120),
        phone TEXT NOT NULL UNIQUE,
        email TEXT NOT NULL DEFAULT '',
        password_hash TEXT NOT NULL,
        is_admin INTEGER NOT NULL DEFAULT 0 CHECK(is_admin IN (0, 1)),
        created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
    )""",
    "CREATE UNIQUE INDEX IF NOT EXISTS users_email_unique ON users(email) WHERE email != ''",
    """CREATE TABLE IF NOT EXISTS customer_sessions (
        token_hash TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        expires_at INTEGER NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS bouquet_models (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL CHECK(length(trim(name)) BETWEEN 1 AND 160),
        price_paise INTEGER NOT NULL CHECK(typeof(price_paise) = 'integer' AND price_paise BETWEEN 0 AND 1000000000),
        image_path TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
        updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
    )""",
    """CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
        kind TEXT NOT NULL CHECK(kind IN ('portrait','bouquet')),
        bouquet_id INTEGER REFERENCES bouquet_models(id) ON DELETE RESTRICT,
        details TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(details)),
        quantity INTEGER NOT NULL CHECK(typeof(quantity) = 'integer' AND quantity BETWEEN 1 AND 999),
        unit_price_paise INTEGER NOT NULL CHECK(typeof(unit_price_paise) = 'integer' AND unit_price_paise BETWEEN 0 AND 1000000000),
        total_price_paise INTEGER NOT NULL CHECK(total_price_paise = quantity * unit_price_paise),
        status TEXT NOT NULL DEFAULT 'awaiting_payment' CHECK(status IN ('awaiting_payment','payment_review','confirmed','in_progress','completed','cancelled')),
        reference_upload_path TEXT NOT NULL DEFAULT '',
        payment_proof_path TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
        updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
        CHECK((kind = 'portrait' AND bouquet_id IS NULL) OR (kind = 'bouquet' AND bouquet_id IS NOT NULL))
    )""",
    "CREATE INDEX IF NOT EXISTS orders_user_created ON orders(user_id, created_at DESC, id DESC)",
    "CREATE INDEX IF NOT EXISTS orders_status_created ON orders(status, created_at DESC, id DESC)",
    """CREATE TABLE IF NOT EXISTS site_settings (
        id INTEGER PRIMARY KEY CHECK(id = 1),
        brand_name TEXT NOT NULL,
        background_color TEXT NOT NULL,
        text_color TEXT NOT NULL,
        accent_color TEXT NOT NULL,
        hero_image_path TEXT NOT NULL DEFAULT '',
        payment_qr_path TEXT NOT NULL DEFAULT '',
        welcome_text TEXT NOT NULL DEFAULT '',
        artist_biography TEXT NOT NULL DEFAULT '',
        contact_number TEXT NOT NULL DEFAULT '',
        updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
    )""",
)


PORTRAIT_SCHEMA = (
    """CREATE TABLE IF NOT EXISTS portrait_sizes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL COLLATE NOCASE UNIQUE CHECK(length(trim(name)) BETWEEN 1 AND 80),
        dimensions TEXT NOT NULL CHECK(length(trim(dimensions)) BETWEEN 1 AND 120),
        price_paise INTEGER NOT NULL CHECK(typeof(price_paise) = 'integer' AND price_paise BETWEEN 0 AND 1000000000)
    )""",
    """CREATE TABLE IF NOT EXISTS portrait_styles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL COLLATE NOCASE UNIQUE CHECK(length(trim(name)) BETWEEN 1 AND 80)
    )""",
)


def migrate_v2_to_v3(conn: sqlite3.Connection) -> None:
    for statement in PORTRAIT_SCHEMA:
        conn.execute(statement)
    conn.executemany(
        "INSERT INTO portrait_sizes(name, dimensions, price_paise) VALUES (?, ?, ?) ON CONFLICT(name) DO NOTHING",
        (
            ("A5", "14.8 × 21 cm", 90000),
            ("A4", "21 × 29.7 cm", 150000),
            ("A3", "29.7 × 42 cm", 250000),
            ("A2", "42 × 59.4 cm", 400000),
        ),
    )
    conn.executemany(
        "INSERT INTO portrait_styles(name) VALUES (?) ON CONFLICT(name) DO NOTHING",
        (("Water color",), ("Pencil color",)),
    )
    conn.execute("PRAGMA user_version = 3")


@contextmanager
def connection(
    database_path: Path = LOCAL_DATABASE,
) -> Iterator[sqlite3.Connection]:
    conn = None
    try:
        database_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        conn = sqlite3.connect(database_path, timeout=15, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 15000")
        conn.execute("BEGIN IMMEDIATE")
        yield conn
        conn.commit()
    except (sqlite3.Error, OSError) as error:
        if conn is not None:
            conn.rollback()
        logging.exception(f"Error: {error}")
        raise
    except (PermissionError, ValueError, LookupError):
        logging.exception("Unexpected error")
        logging.info("Request validation or access denied")
        if conn is not None:
            conn.rollback()
        raise
    except Exception:
        if conn is not None:
            conn.rollback()
        logging.exception("Unexpected error")
        raise
    finally:
        if conn is not None:
            conn.close()


def initialize_database(database_path: Path = LOCAL_DATABASE) -> None:
    with connection(database_path) as conn:
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        if version not in (0, 1, 2, SCHEMA_VERSION):
            raise RuntimeError(
                "Unsupported SQLite schema version; migration required."
            )
        for statement in SCHEMA:
            conn.execute(statement)
        columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(site_settings)")
        }
        if "payment_qr_path" not in columns:
            conn.execute(
                "ALTER TABLE site_settings ADD COLUMN payment_qr_path TEXT NOT NULL DEFAULT ''"
            )
        conn.execute(
            """INSERT INTO site_settings
            (id, brand_name, background_color, text_color, accent_color, welcome_text)
            VALUES (1, ?, ?, ?, ?, ?) ON CONFLICT(id) DO NOTHING""",
            (
                "Artist Studio",
                "#F7F3EC",
                "#29231E",
                "#B76D50",
                "Art made personal. Flowers made to keep.",
            ),
        )
        if version < 2:
            conn.execute("PRAGMA user_version = 2")
            version = 2
        if version == 2:
            migrate_v2_to_v3(conn)
        else:
            for statement in PORTRAIT_SCHEMA:
                conn.execute(statement)
