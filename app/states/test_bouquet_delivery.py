import reflex as rx
import copy
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.states.admin_state import AdminState
from app.states.customer_state import CustomerState
from app.states.store_database import connection
from app.states.store_repository import StoreRepository
from app.states.store_validation import preferred_delivery_date


class BouquetDeliveryTests(unittest.TestCase):
    def form(self) -> dict[str, str]:
        return {
            "quantity": "2",
            "recipient_name": "  Recipient  ",
            "delivery_address": "  Street\nCity, postal code  ",
            "preferred_delivery_date": date.today().isoformat(),
            "gift_message": "  With love\nFrom us  ",
        }

    def state(self, repository):
        return SimpleNamespace(
            busy=False,
            error="",
            bouquet_id=7,
            session_token="valid",
            _repository_customer=Mock(return_value=(repository, {"id": 11})),
            _clear_identity=Mock(),
            _next_path="/dashboard",
        )

    def repository(self):
        repository = Mock()
        repository.get_bouquet.return_value = {"id": 7, "name": "Saved model"}
        repository.create_order.return_value = {"id": 42}
        return repository

    def submit(self, state, form):
        with patch("app.states.customer_state.logging.exception"):
            return list(CustomerState.order_bouquet.fn(state, form))

    def test_trimmed_snapshot_uses_authenticated_owner_and_checkout(self):
        repository = self.repository()
        state = self.state(repository)
        with patch.object(rx, "redirect") as redirect:
            self.submit(state, self.form())
            redirect.assert_called_once_with("/checkout?order=42")
        repository.create_order.assert_called_once_with(
            11,
            "bouquet",
            {
                "model_name": "Saved model",
                "recipient_name": "Recipient",
                "delivery_address": "Street\nCity, postal code",
                "preferred_delivery_date": date.today().isoformat(),
                "gift_message": "With love\nFrom us",
            },
            quantity=2,
            bouquet_id=7,
        )
        self.assertEqual(state.bouquet_id, 0)
        self.assertEqual(state.error, "")
        self.assertFalse(state.busy)

    def test_field_specific_rejections_do_not_create_orders(self):
        invalid = (
            ("quantity", "1.5", "Quantity"),
            ("quantity", "0", "Quantity"),
            ("quantity", "1000", "Quantity"),
            ("recipient_name", " \n ", "Recipient name"),
            ("recipient_name", "x" * 121, "Recipient name"),
            ("recipient_name", None, "Recipient name"),
            ("delivery_address", "  ", "Delivery address"),
            ("delivery_address", "x" * 1001, "Delivery address"),
            ("delivery_address", "bad\x00address", "Delivery address"),
            ("preferred_delivery_date", "", "Preferred delivery date"),
            ("preferred_delivery_date", "2028-2-29", "Preferred delivery date"),
            ("preferred_delivery_date", "20270228", "Preferred delivery date"),
            (
                "preferred_delivery_date",
                "2027-02-29",
                "Preferred delivery date",
            ),
            (
                "preferred_delivery_date",
                "2030-13-01",
                "Preferred delivery date",
            ),
            (
                "preferred_delivery_date",
                "2030-01-01T00:00:00",
                "Preferred delivery date",
            ),
            (
                "preferred_delivery_date",
                (date.today() - timedelta(days=1)).isoformat(),
                "Preferred delivery date",
            ),
            ("gift_message", "x" * 501, "Gift message"),
        )
        for key, value, label in invalid:
            with self.subTest(key=key, value=value):
                repository = self.repository()
                state = self.state(repository)
                form = self.form()
                form[key] = value
                self.submit(state, form)
                self.assertIn(label, state.error)
                repository.create_order.assert_not_called()
                self.assertFalse(state.busy)
                self.assertEqual(state.bouquet_id, 7)

    def test_limits_and_optional_message(self):
        for message in ("", " \n ", "x" * 500):
            repository = self.repository()
            state = self.state(repository)
            form = self.form()
            form.update(
                recipient_name="x" * 120,
                delivery_address="x" * 1000,
                gift_message=message,
            )
            self.submit(state, form)
            self.assertEqual(state.error, "")
            self.assertEqual(
                repository.create_order.call_args.args[2]["gift_message"],
                message.strip(),
            )
        repository = self.repository()
        form = self.form()
        del form["gift_message"]
        self.submit(self.state(repository), form)
        self.assertEqual(
            repository.create_order.call_args.args[2]["gift_message"], ""
        )

    def test_date_calendar_iso_and_local_today_boundary(self):
        with patch("app.states.store_validation.date") as local_date:
            local_date.today.return_value = date(2028, 2, 29)
            local_date.fromisoformat.side_effect = date.fromisoformat
            self.assertEqual(
                preferred_delivery_date(" 2028-02-29 "), "2028-02-29"
            )
            self.assertEqual(
                preferred_delivery_date("2028-03-01"), "2028-03-01"
            )
            with self.assertRaisesRegex(ValueError, "earlier than today"):
                preferred_delivery_date("2028-02-28")
            for invalid in ("２０２８-02-29", "2028-W09-2", "0000-01-01"):
                with (
                    self.subTest(invalid=invalid),
                    self.assertRaises(ValueError),
                ):
                    preferred_delivery_date(invalid)

    def test_session_failure_and_save_failure_preserve_existing_handling(self):
        repository = self.repository()
        state = self.state(repository)
        state._repository_customer.side_effect = PermissionError("Expired")
        with patch.object(rx, "redirect") as redirect:
            self.submit(state, self.form())
            redirect.assert_called_once_with("/login")
        self.assertEqual(state.session_token, "")
        self.assertEqual(state._next_path, "/bouquets")
        repository.create_order.assert_not_called()
        state = self.state(repository)
        repository.create_order.side_effect = RuntimeError("Save failed")
        self.submit(state, self.form())
        self.assertIn("could not be saved", state.error)
        self.assertFalse(state.busy)
        self.assertEqual(state.bouquet_id, 7)

    def test_snapshot_persistence_views_legacy_and_portrait_privacy(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = StoreRepository(Path(directory) / "store.sqlite3")
            buyer = repository.signup(
                "Buyer", "+919876543210", "a secure test password"
            )
            other = repository.signup(
                "Other", "+919876543211", "another test password"
            )
            with connection(repository.database_path) as conn:
                owner = conn.execute(
                    "SELECT id FROM users WHERE is_admin = 1"
                ).fetchone()[0]
                conn.execute(
                    "UPDATE users SET must_change_password = 0 WHERE id = ?",
                    (owner,),
                )
            bouquet = repository.save_bouquet(
                owner, "Model", 12345, "model.png"
            )
            legacy = repository.create_order(
                buyer["id"],
                "bouquet",
                {"model_name": "Model"},
                bouquet_id=bouquet["id"],
            )
            form = self.form()
            details = {
                key: value.strip()
                for key, value in form.items()
                if key != "quantity"
            }
            details["model_name"] = "Model"
            saved = repository.create_order(
                buyer["id"],
                "bouquet",
                details,
                quantity=2,
                bouquet_id=bouquet["id"],
            )
            portrait = repository.create_order(
                buyer["id"],
                "portrait",
                details,
                portrait_size_id=repository.list_portrait_sizes()[0]["id"],
                portrait_style_id=repository.list_portrait_styles()[0]["id"],
            )
            reopened = StoreRepository(repository.database_path)
            self.assertEqual(
                reopened.customer_order(buyer["id"], saved["id"])["details"],
                details,
            )
            self.assertEqual(saved["total_price_paise"], 24690)
            with self.assertRaises(PermissionError):
                reopened.customer_order(other["id"], saved["id"])
            before = copy.deepcopy(legacy)
            admin = SimpleNamespace(orders=[])
            AdminState._load_orders(admin, reopened, owner)
            for order in (legacy, saved, portrait):
                customer_view = CustomerState._view(SimpleNamespace(), order)
                admin_view = next(
                    row for row in admin.orders if row["id"] == order["id"]
                )
                self.assertEqual(
                    customer_view["is_bouquet"], order["kind"] == "bouquet"
                )
                for key in (
                    "recipient_name",
                    "delivery_address",
                    "preferred_delivery_date",
                    "gift_message",
                ):
                    expected = (
                        details[key] if order["id"] == saved["id"] else ""
                    )
                    self.assertEqual(customer_view[key], expected)
                    self.assertEqual(admin_view[key], expected)
            self.assertEqual(reopened.get_order(owner, legacy["id"]), before)


if __name__ == "__main__":
    unittest.main()
