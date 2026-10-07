import reflex as rx
import asyncio
import hashlib
import io
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image
from starlette.datastructures import UploadFile
from starlette.staticfiles import StaticFiles
from starlette.testclient import TestClient

from app.states.store_database import connection
from app.states.store_repository import StoreRepository
from app.states.private_files import (
    migrate_private_files,
    private_file,
    private_directory,
)
from app.states.private_file_api import order_image
from app.states.customer_state import CustomerState
from app.states.admin_state import AdminState


def image_bytes(format: str = "PNG") -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (4, 4), "red").save(output, format=format)
    return output.getvalue()


class PrivateFileTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.public = self.root / "public"
        self.public.mkdir()
        upload_patch = patch.object(
            rx, "get_upload_dir", return_value=self.public
        )
        upload_patch.start()
        self.addCleanup(upload_patch.stop)
        environment = patch.dict(os.environ, {"ARTIST_ADMIN_PHONE": ""})
        environment.start()
        self.addCleanup(environment.stop)
        self.database = self.root / "data" / "store.sqlite3"
        self.repository = StoreRepository(self.database)
        with connection(self.database) as conn:
            owner_id = conn.execute(
                "SELECT id FROM users WHERE username = 'admin'"
            ).fetchone()[0]
        self.repository.change_password(
            owner_id, "password", "a rotated owner password"
        )
        self.admin = self.repository.get_customer(owner_id, owner_id)
        self.owner = self.repository.signup(
            "Customer", "+919876543211", "a secure test password"
        )
        self.other = self.repository.signup(
            "Other", "+919876543212", "a secure test password"
        )
        self.tokens = {
            "owner": self.repository.create_session(self.owner["id"]),
            "other": self.repository.create_session(self.other["id"]),
            "admin": self.repository.create_session(self.admin["id"]),
        }
        self.order = self.new_order("legacy.png")
        (self.public / "legacy.png").write_bytes(image_bytes())
        for name in ("bouquet.png", "hero.png", "qr.png"):
            (self.public / name).write_bytes(image_bytes())
        self.repository.save_bouquet(
            self.admin["id"], "Flowers", 100, "bouquet.png"
        )
        settings = self.repository.get_settings()
        settings.update(hero_image_path="hero.png", payment_qr_path="qr.png")
        self.repository.update_settings(self.admin["id"], settings)

    def new_order(self, reference: str = ""):
        return self.repository.create_order(
            self.owner["id"],
            "portrait",
            {},
            reference_upload_path=reference,
            portrait_size_id=self.repository.list_portrait_sizes()[0]["id"],
            portrait_style_id=self.repository.list_portrait_styles()[0]["id"],
        )

    def backend(self):
        # Same order as the entrypoint: fail-closed migration BEFORE rx.App/static mounts.
        migrate_private_files(self.database)
        from fastapi import FastAPI

        app = FastAPI()
        app.state.studio_database_path = self.database
        app.add_route(
            "/order-files/{order_id}/{kind}", order_image, methods=["GET"]
        )
        app.mount("/uploads", StaticFiles(directory=self.public))
        return app

    def url(self, kind: str = "reference", order_id: int = 0):
        return f"/order-files/{order_id or self.order['id']}/{kind}"

    def get(self, client, kind="reference", actor="owner", order_id=0):
        client.cookies.clear()
        if actor:
            client.cookies.set("studio_session", self.tokens[actor])
        return client.get(self.url(kind, order_id))

    def test_request_authentication_authorization_and_revocation(self):
        with TestClient(self.backend()) as client:
            self.assertEqual(self.get(client, actor="").status_code, 401)
            self.assertEqual(self.get(client, actor="other").status_code, 404)
            for actor in ("owner", "admin"):
                result = self.get(client, actor=actor)
                self.assertEqual(result.status_code, 200)
                self.assertEqual(result.content, image_bytes())
                self.assertEqual(result.headers["content-type"], "image/png")
                self.assertEqual(
                    result.headers["cache-control"], "private, no-store"
                )
                self.assertEqual(
                    result.headers["x-content-type-options"], "nosniff"
                )
                self.assertNotIn("content-disposition", result.headers)
                self.assertNotIn("legacy.png", str(result.headers))
            with connection(self.database) as conn:
                conn.execute(
                    "UPDATE users SET is_admin = 0 WHERE id = ?",
                    (self.admin["id"],),
                )
            self.assertEqual(self.get(client, actor="admin").status_code, 404)
            with patch(
                "app.states.customer_state.StoreRepository",
                return_value=self.repository,
            ):
                state = SimpleNamespace(session_token=self.tokens["owner"])
                state._clear_identity = lambda: CustomerState._clear_identity(
                    state
                )
                CustomerState.logout.fn(state)
            self.assertEqual(self.get(client).status_code, 401)
            with connection(self.database) as conn:
                conn.execute(
                    "UPDATE customer_sessions SET expires_at = 0 WHERE token_hash = ?",
                    (
                        hashlib.sha256(
                            self.tokens["other"].encode()
                        ).hexdigest(),
                    ),
                )
            self.assertEqual(self.get(client, actor="other").status_code, 401)

    def test_pending_owner_denied_private_files_and_rotation_revokes_access(
        self,
    ):
        with TestClient(self.backend()) as client:
            with connection(self.database) as conn:
                conn.execute(
                    "UPDATE users SET must_change_password = 1 WHERE id = ?",
                    (self.admin["id"],),
                )
            self.assertEqual(self.get(client, actor="admin").status_code, 404)
            self.assertEqual(self.get(client, actor="owner").status_code, 200)
            self.repository.change_password(
                self.admin["id"],
                "a rotated owner password",
                "another rotated owner password",
            )
            self.assertEqual(self.get(client, actor="admin").status_code, 401)
            self.tokens["admin"] = self.repository.create_session(
                self.admin["id"]
            )
            self.assertEqual(self.get(client, actor="admin").status_code, 200)

    def test_private_upload_proof_flow_and_actual_mime(self):
        with TestClient(self.backend()) as client:
            upload = UploadFile(
                io.BytesIO(image_bytes("JPEG")), filename="original-secret.jpeg"
            )
            filename = asyncio.run(
                self.repository.save_upload(self.owner["id"], upload)
            )
            self.assertFalse((self.public / filename).exists())
            self.assertNotIn("original-secret", filename)
            self.repository.submit_payment_proof(
                self.owner["id"], self.order["id"], filename
            )
            self.assertEqual(
                self.repository.get_order(self.owner["id"], self.order["id"])[
                    "status"
                ],
                "payment_review",
            )
            for actor in ("owner", "admin"):
                response = self.get(client, "proof", actor)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.headers["content-type"], "image/jpeg")
                self.assertEqual(response.content, image_bytes("JPEG"))
            self.assertEqual(
                self.get(client, "proof", "other").status_code, 404
            )
            view = CustomerState._view(
                SimpleNamespace(),
                self.repository.get_order(self.owner["id"], self.order["id"]),
            )
            self.assertIs(view["proof"], True)
            state = SimpleNamespace(orders=[])
            AdminState._load_orders(state, self.repository, self.admin["id"])
            self.assertIs(state.orders[0]["proof"], True)
            self.assertNotIn(filename, str(view))
            self.assertNotIn(filename, str(state.orders))
            public_upload = UploadFile(
                io.BytesIO(image_bytes()), filename="public.png"
            )
            public_name = asyncio.run(
                self.repository.save_admin_upload(
                    self.admin["id"], public_upload
                )
            )
            self.assertEqual(
                client.get(f"/uploads/{public_name}").status_code, 200
            )

    def test_migration_duplicates_idempotence_permissions_and_static_access(
        self,
    ):
        self.new_order("legacy.png")
        with TestClient(self.backend()) as client:
            migrate_private_files(self.database)
            self.assertFalse((self.public / "legacy.png").exists())
            self.assertEqual(client.get("/uploads/legacy.png").status_code, 404)
            self.assertEqual(
                client.get("/uploads/private_uploads/legacy.png").status_code,
                404,
            )
            for name in ("bouquet.png", "hero.png", "qr.png"):
                self.assertEqual(
                    client.get(f"/uploads/{name}").content, image_bytes()
                )
            self.assertEqual(
                private_directory(self.database).stat().st_mode & 0o777, 0o700
            )
            self.assertEqual(
                private_file("legacy.png", self.database).stat().st_mode
                & 0o777,
                0o600,
            )
            for order in self.repository.list_orders(self.owner["id"]):
                self.assertEqual(
                    self.get(client, order_id=order["id"]).status_code, 200
                )

    def test_invalid_kind_missing_files_traversal_and_symlinks(self):
        with TestClient(self.backend()) as client:
            for kind in (
                "proof",
                "unknown",
                "legacy.png",
                "..%2Flegacy.png",
                "%2Fetc%2Fpasswd",
            ):
                response = self.get(client, kind)
                self.assertEqual(response.status_code, 404)
                self.assertNotIn(str(self.root), response.text)
            self.assertEqual(self.get(client, order_id=999999).status_code, 404)
            client.cookies.set("studio_session", self.tokens["owner"])
            self.assertEqual(
                client.get("/order-files/..%2F1/reference").status_code, 404
            )
            with connection(self.database) as conn:
                conn.execute(
                    "UPDATE orders SET reference_upload_path = '../legacy.png' WHERE id = ?",
                    (self.order["id"],),
                )
            self.assertEqual(self.get(client).status_code, 404)
            with connection(self.database) as conn:
                conn.execute(
                    "UPDATE orders SET reference_upload_path = 'link.png' WHERE id = ?",
                    (self.order["id"],),
                )
            private_file("link.png", self.database).symlink_to(
                self.public / "hero.png"
            )
            self.assertEqual(self.get(client).status_code, 404)

    def test_migration_fails_closed_on_collision_symlink_and_move_failure(self):
        with connection(self.database) as conn:
            conn.execute(
                "UPDATE orders SET payment_proof_path = 'hero.png' WHERE id = ?",
                (self.order["id"],),
            )
        with self.assertRaises(RuntimeError):
            self.backend()
        self.assertTrue((self.public / "hero.png").is_file())
        with connection(self.database) as conn:
            conn.execute(
                "UPDATE orders SET payment_proof_path = '' WHERE id = ?",
                (self.order["id"],),
            )
        (self.public / "legacy.png").unlink()
        (self.public / "legacy.png").symlink_to(self.public / "hero.png")
        with self.assertRaises(RuntimeError):
            self.backend()
        (self.public / "legacy.png").unlink()
        (self.public / "legacy.png").write_bytes(image_bytes())
        with patch.object(Path, "rename", side_effect=OSError("move failed")):
            with self.assertRaises(RuntimeError):
                self.backend()
        self.assertTrue((self.public / "legacy.png").exists())
        (self.public / "legacy.png").unlink()
        with TestClient(self.backend()) as client:
            self.assertEqual(self.get(client).status_code, 404)

    def test_expected_auth_denials_are_quiet_and_non_cacheable(self):
        with TestClient(self.backend()) as client:
            with patch("app.states.private_file_api.logging.exception") as log:
                for token, status in (
                    ("", 401),
                    ("invalid-session", 401),
                    (self.tokens["other"], 404),
                ):
                    with self.subTest(status=status, present=bool(token)):
                        client.cookies.clear()
                        if token:
                            client.cookies.set("studio_session", token)
                        response = client.get(self.url())
                        self.assertEqual(response.status_code, status)
                        self.assertEqual(
                            response.headers["cache-control"],
                            "private, no-store",
                        )
                        self.assertEqual(
                            response.headers["x-content-type-options"],
                            "nosniff",
                        )
                        self.assertNotIn(str(self.root), response.text)
                with connection(self.database) as conn:
                    conn.execute(
                        "UPDATE customer_sessions SET expires_at = 0 WHERE user_id = ?",
                        (self.other["id"],),
                    )
                    conn.execute(
                        "UPDATE users SET must_change_password = 1 WHERE id = ?",
                        (self.admin["id"],),
                    )
                expired = self.get(client, actor="other")
                pending = self.get(client, actor="admin")
                self.assertEqual(expired.status_code, 401)
                self.assertEqual(pending.status_code, 404)
                for response in (expired, pending):
                    self.assertEqual(
                        response.headers["cache-control"], "private, no-store"
                    )
                log.assert_not_called()

    def test_unexpected_private_api_failure_is_reported_without_details(self):
        with TestClient(self.backend()) as client:
            for error in (
                RuntimeError("Unexpected failure"),
                OSError("Disk failure"),
            ):
                with self.subTest(error=type(error).__name__):
                    with patch.object(
                        StoreRepository, "get_order", side_effect=error
                    ):
                        with patch(
                            "app.states.private_file_api.logging.exception"
                        ) as log:
                            response = self.get(client)
                            log.assert_called_once()
                    self.assertEqual(response.status_code, 404)
                    self.assertEqual(
                        response.headers["cache-control"], "private, no-store"
                    )
                    self.assertNotIn(str(error), response.text)


if __name__ == "__main__":
    unittest.main()
