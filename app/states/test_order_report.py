import unittest
from unittest.mock import AsyncMock

from app.states.admin_state import AdminState
from app.states.order_report import (
    ORDER_STATUSES,
    build_order_report,
    format_paise,
    validate_report_filters,
)
from app.states.private_files import private_file
from app.states.store_database import connection
from app.states import test_admin


def order(order_id: int, status: str, placed: str, paise: int, proof=False):
    return {
        "id": order_id,
        "status": status,
        "date": placed,
        "amount_paise": paise,
        "amount": paise / 100,
        "proof": proof,
    }


class OrderReportCalculationTests(unittest.TestCase):
    def test_strict_dates_and_ranges(self):
        self.assertEqual(
            validate_report_filters("2024-02-29", "2024-03-01", ""),
            ("2024-02-29", "2024-03-01", ""),
        )
        self.assertEqual(
            validate_report_filters("", "2024-01-31", "confirmed"),
            ("", "2024-01-31", "confirmed"),
        )
        self.assertEqual(
            validate_report_filters("2024-01-01", "", ""),
            ("2024-01-01", "", ""),
        )
        self.assertEqual(
            validate_report_filters("2024-01-05", "2024-01-05", ""),
            ("2024-01-05", "2024-01-05", ""),
        )
        for bad in (
            "2023-02-29",
            "2024-13-01",
            "2024-04-31",
            "0000-01-01",
            "2024-1-01",
            "20240101",
            "2024-01-01T00:00",
            " 2024-01-01",
            "2024/01/01",
            "٢٠٢٤-٠١-٠١",
        ):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                validate_report_filters(bad, "", "")
        with self.assertRaises(ValueError):
            validate_report_filters("2024-02-02", "2024-02-01", "")
        with self.assertRaises(ValueError):
            validate_report_filters("", "", "paid")
        with self.assertRaises(ValueError):
            validate_report_filters(None, "", "")

    def test_inclusive_boundaries_and_open_ranges(self):
        orders = [
            order(1, "confirmed", "2024-01-31", 100),
            order(2, "confirmed", "2024-02-01", 200),
            order(3, "confirmed", "2024-02-29", 400),
            order(4, "confirmed", "2024-03-01", 800),
        ]
        closed = build_order_report(orders, "2024-02-01", "2024-02-29", "")
        self.assertEqual(closed["count"], 2)
        self.assertEqual(closed["order_value_paise"], 600)
        self.assertEqual(
            build_order_report(orders, "2024-02-01", "", "")["count"], 3
        )
        self.assertEqual(
            build_order_report(orders, "", "2024-02-01", "")["count"], 2
        )
        self.assertEqual(build_order_report(orders, "", "", "")["count"], 4)
        single = build_order_report(orders, "2024-03-01", "2024-03-01", "")
        self.assertEqual(single["order_value_paise"], 800)

    def test_zero_rows_and_single_status_selector(self):
        report = build_order_report([], "", "", "")
        self.assertEqual(
            [row["status"] for row in report["rows"]], list(ORDER_STATUSES)
        )
        self.assertTrue(all(row["count"] == 0 for row in report["rows"]))
        self.assertEqual(report["rows"][0]["order_value"], "₹0.00")
        orders = [
            order(1, "cancelled", "2024-01-01", 500),
            order(2, "completed", "2024-01-01", 700),
        ]
        selected = build_order_report(orders, "", "", "cancelled")
        self.assertEqual(
            [row["status"] for row in selected["rows"]], ["cancelled"]
        )
        self.assertEqual(selected["count"], 1)
        self.assertEqual(selected["confirmed_value_paise"], 0)
        self.assertEqual(
            build_order_report(orders, "", "", "bogus")["rows"], []
        )

    def test_payment_value_excludes_unconfirmed_even_with_proof(self):
        orders = [
            order(1, "awaiting_payment", "2024-01-01", 1000, proof=True),
            order(2, "payment_review", "2024-01-01", 2000, proof=True),
            order(3, "cancelled", "2024-01-01", 4000, proof=True),
            order(4, "confirmed", "2024-01-01", 8000),
            order(5, "in_progress", "2024-01-01", 16000),
            order(6, "completed", "2024-01-01", 32000, proof=True),
        ]
        report = build_order_report(orders, "", "", "")
        self.assertEqual(report["count"], 6)
        self.assertEqual(report["order_value_paise"], 63000)
        self.assertEqual(report["confirmed_value_paise"], 56000)
        rows = {row["status"]: row for row in report["rows"]}
        for status in ("awaiting_payment", "payment_review", "cancelled"):
            self.assertEqual(rows[status]["confirmed_value_paise"], 0)
            self.assertFalse(rows[status]["counts_as_confirmed"])

    def test_integer_money_accuracy_and_formatting(self):
        orders = [order(i, "confirmed", "2024-01-01", 10) for i in range(3)]
        orders += [order(9, "completed", "2024-01-01", 20)]
        report = build_order_report(orders, "", "", "")
        self.assertIs(type(report["order_value_paise"]), int)
        self.assertEqual(report["order_value_paise"], 50)
        self.assertEqual(format_paise(report["order_value_paise"]), "₹0.50")
        many = [order(i, "confirmed", "2024-01-01", 33) for i in range(1000)]
        self.assertEqual(
            build_order_report(many, "", "", "")["order_value_paise"], 33000
        )
        self.assertEqual(format_paise(1234567890), "₹12,345,678.90")
        self.assertEqual(format_paise(5), "₹0.05")
        with self.assertRaises(TypeError):
            format_paise(1.5)
        with self.assertRaises(TypeError):
            build_order_report(
                [
                    {
                        "status": "confirmed",
                        "date": "2024-01-01",
                        "amount_paise": 0.1,
                    }
                ],
                "",
                "",
                "",
            )


class OrderReportWorkspaceTests(unittest.TestCase):
    setUp = test_admin.AdminTests.setUp
    signup = test_admin.AdminTests.signup
    run_handler = test_admin.AdminTests.run_handler

    def workspace_state(self, token: str):
        state = test_admin.AdminTests.workspace_state(self, token)
        state.report_start = ""
        state.report_end = ""
        state.report_status = ""
        state.report_error = ""
        state.report_form_version = 0
        return state

    def report(self, state):
        return build_order_report(
            state.orders,
            state.report_start,
            state.report_end,
            state.report_status,
        )

    def portrait_order(self, customer_id: int):
        return self.store.create_order(
            customer_id,
            "portrait",
            {"size": "A4"},
            quantity=3,
            portrait_size_id=self.store.list_portrait_sizes()[1]["id"],
            portrait_style_id=self.store.list_portrait_styles()[0]["id"],
        )

    def test_amount_paise_loaded_from_saved_total(self):
        owner = self.signup(10)
        buyer = self.signup(11)
        saved = self.portrait_order(buyer["id"])
        state = self.workspace_state(self.store.create_session(owner["id"]))
        self.run_handler(state, AdminState.load_admin)
        row = state.orders[0]
        self.assertIs(type(row["amount_paise"]), int)
        self.assertEqual(row["amount_paise"], saved["total_price_paise"])
        self.assertEqual(row["amount"], saved["total_price_paise"] / 100)
        self.assertEqual(row["date"], saved["created_at"][:10])

    def test_filters_apply_validate_reset_and_survive_refresh(self):
        owner = self.signup(10)
        buyer = self.signup(11)
        saved = self.portrait_order(buyer["id"])
        with connection(self.store.database_path) as conn:
            conn.execute(
                "UPDATE orders SET created_at = '2024-05-31T23:59:59.000Z' WHERE id = ?",
                (saved["id"],),
            )
        state = self.workspace_state(self.store.create_session(owner["id"]))
        self.run_handler(state, AdminState.load_admin)
        state.order_query = "nobody"
        form = {
            "report_start": "2024-05-31",
            "report_end": "2024-05-31",
            "report_status": "awaiting_payment",
        }
        self.run_handler(state, AdminState.apply_report_filters, form)
        self.assertEqual(state.report_error, "")
        self.assertEqual(
            (state.report_start, state.report_end, state.report_status),
            ("2024-05-31", "2024-05-31", "awaiting_payment"),
        )
        self.assertEqual(self.report(state)["count"], 1)
        self.assertEqual(state.order_query, "nobody")
        self.run_handler(
            state,
            AdminState.apply_report_filters,
            {"report_start": "2024-06-02", "report_end": "2024-06-01"},
        )
        self.assertIn("on or before", state.report_error)
        self.assertEqual(state.report_start, "2024-05-31")
        self.run_handler(
            state,
            AdminState.apply_report_filters,
            {
                "report_start": "2024-06-01",
                "report_end": "",
                "report_status": "",
            },
        )
        self.assertEqual(self.report(state)["count"], 0)
        self.run_handler(state, AdminState.load_admin)
        self.assertTrue(state.allowed)
        self.assertEqual(state.report_start, "2024-06-01")
        self.assertEqual(self.report(state)["count"], 0)
        self.run_handler(state, AdminState.reset_report_filters)
        self.assertEqual(
            (
                state.report_start,
                state.report_end,
                state.report_status,
                state.report_error,
            ),
            ("", "", "", ""),
        )
        self.assertEqual(state.report_form_version, 1)
        self.assertEqual(self.report(state)["count"], 1)
        self.assertEqual(state.order_query, "nobody")

    def test_status_change_refreshes_report_and_proof_alone_is_excluded(self):
        owner = self.signup(10)
        buyer = self.signup(11)
        saved = self.portrait_order(buyer["id"])
        total = saved["total_price_paise"]
        private_file("report-proof.png", self.store.database_path).write_bytes(
            b"proof"
        )
        self.store.submit_payment_proof(
            buyer["id"], saved["id"], "report-proof.png"
        )
        state = self.workspace_state(self.store.create_session(owner["id"]))
        self.run_handler(state, AdminState.load_admin)
        report = self.report(state)
        self.assertTrue(state.orders[0]["proof"])
        self.assertEqual(report["order_value_paise"], total)
        self.assertEqual(report["confirmed_value_paise"], 0)
        self.run_handler(
            state, AdminState.save_status, saved["id"], {"status": "confirmed"}
        )
        self.assertEqual(state.error, "")
        self.assertEqual(self.report(state)["confirmed_value_paise"], total)
        self.run_handler(
            state, AdminState.save_status, saved["id"], {"status": "cancelled"}
        )
        report = self.report(state)
        rows = {row["status"]: row for row in report["rows"]}
        self.assertEqual(rows["cancelled"]["count"], 1)
        self.assertEqual(rows["confirmed"]["count"], 0)
        self.assertEqual(report["order_value_paise"], total)
        self.assertEqual(report["confirmed_value_paise"], 0)

    def test_denial_clears_report_and_handlers_fail_closed(self):
        owner = self.signup(10)
        customer = self.signup(11)
        for token in (
            self.store.create_session(customer["id"]),
            "revoked",
        ):
            for handler, args in (
                (
                    AdminState.apply_report_filters,
                    (
                        {
                            "report_start": "2024-01-01",
                            "report_status": "confirmed",
                        },
                    ),
                ),
                (AdminState.reset_report_filters, ()),
            ):
                with self.subTest(token=token, handler=handler.fn.__name__):
                    state = self.workspace_state(token)
                    state.allowed = True
                    state.orders = [order(1, "confirmed", "2024-01-01", 999)]
                    state.report_start = "2023-01-01"
                    state.report_end = "2023-12-31"
                    state.report_status = "completed"
                    state.report_error = "previous"
                    self.run_handler(state, handler, *args)
                    self.assertFalse(state.allowed)
                    self.assertEqual(state.orders, [])
                    self.assertEqual(
                        (
                            state.report_start,
                            state.report_end,
                            state.report_status,
                            state.report_error,
                        ),
                        ("", "", "", ""),
                    )
                    self.assertIn(
                        "Administrator access is required", state.error
                    )
        state = self.workspace_state(self.store.create_session(owner["id"]))
        state._authorized = AsyncMock()
        state.report_start = "2024-01-01"
        self.run_handler(
            state,
            AdminState.apply_report_filters,
            {"report_start": "2024-02-01"},
        )
        state._authorized.assert_not_awaited()
        self.assertEqual(state.report_start, "")
        state.allowed = True
        state.report_start = "2024-01-01"
        state.report_status = "confirmed"
        AdminState._deny(state)
        self.assertEqual((state.report_start, state.report_status), ("", ""))

    def test_load_denial_clears_report(self):
        customer = self.signup(11)
        state = self.workspace_state(self.store.create_session(customer["id"]))
        state.report_start = "2024-01-01"
        state.report_status = "confirmed"
        self.run_handler(state, AdminState.load_admin)
        self.assertFalse(state.allowed)
        self.assertEqual((state.report_start, state.report_status), ("", ""))


if __name__ == "__main__":
    unittest.main()
