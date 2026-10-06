import reflex as rx
import logging
import time
import base64
import io
from urllib.parse import urlencode

import qrcode
from typing import Any, TypedDict

from app.states.store_models import Customer, Order
from app.states.store_repository import StoreRepository
from app.states.store_uploads import require_saved_png
from app.states.private_files import private_file
from app.states.store_validation import quantity_value


class OrderView(TypedDict):
    id: int
    title: str
    quantity: int
    unit_price_paise: int
    total_price_paise: int
    status: str
    payment: str
    created_at: str
    provisional: bool
    reference: bool
    proof: bool


class CustomerState(rx.State):
    session_token: str = rx.Cookie(
        "", name="studio_session", max_age=604800, same_site="strict", path="/"
    )
    authenticated: bool = False
    admin_access: bool = False
    customer_name: str = ""
    signup_mode: bool = False
    busy: bool = False
    ready: bool = False
    error: str = ""
    notice: str = ""
    orders: list[OrderView] = []
    checkout_orders: list[OrderView] = []
    qr_available: bool = False
    qr_image_path: str = ""
    qr_image_url: str = ""
    bouquet_id: int = 0
    bouquet_name: str = ""
    bouquet_price_paise: int = 0
    _actor_id: int = 0
    _next_path: str = "/dashboard"
    _auth_attempts: list[float] = []

    def _repository_customer(self) -> tuple[StoreRepository, Customer]:
        repository = StoreRepository()
        customer = repository.session_customer(self.session_token)
        self._actor_id = customer["id"]
        self.authenticated = True
        self.customer_name = customer["name"]
        self.admin_access = customer["is_admin"]
        return repository, customer

    def _clear_identity(self):
        self._actor_id = 0
        self.authenticated = False
        self.admin_access = False
        self.customer_name = ""
        self.orders = []
        self.checkout_orders = []
        self.qr_available = False
        self.qr_image_path = ""
        self.qr_image_url = ""
        self.ready = False

    def _view(self, order: Order) -> OrderView:
        portrait = order["kind"] == "portrait"
        title = (
            f"{order['details'].get('size', 'Custom')} portrait · {order['details'].get('style', 'Style not recorded')}"
            if portrait
            else order["details"].get(
                "model_name", f"Bouquet model {order['bouquet_id']}"
            )
        )
        labels = {
            "awaiting_payment": "Awaiting payment",
            "payment_review": "Payment under review",
            "confirmed": "Confirmed",
            "in_progress": "In progress",
            "completed": "Completed",
            "cancelled": "Cancelled",
        }
        payment = (
            "Proof submitted · not yet verified"
            if order["payment_proof_path"]
            else "No payment proof submitted"
        )
        if order["payment_proof_path"] and order["status"] in (
            "confirmed",
            "in_progress",
            "completed",
        ):
            payment = "Proof submitted · order confirmed"
        return OrderView(
            id=order["id"],
            title=title,
            quantity=order["quantity"],
            unit_price_paise=order["unit_price_paise"],
            total_price_paise=order["total_price_paise"],
            status=labels[order["status"]],
            payment=payment,
            created_at=order["created_at"][:10],
            provisional=portrait,
            reference=bool(order.get("reference_upload_path", "")),
            proof=bool(order["payment_proof_path"]),
        )

    def _built_in_payment_qr(self) -> str:
        uri = f"upi://pay?{urlencode({'pa': 'psajin2001@okhdfcbank', 'pn': 'Sajin', 'cu': 'INR'})}"
        qr = qrcode.QRCode(
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=9,
            border=4,
        )
        qr.add_data(uri, optimize=0)
        qr.make(fit=True)
        with io.BytesIO() as output:
            qr.make_image(fill_color="black", back_color="white").save(
                output, format="PNG"
            )
            encoded = base64.b64encode(output.getvalue()).decode("ascii")
        return f"data:image/png;base64,{encoded}"

    def _load_payment_qr(self, repository: StoreRepository) -> None:
        self.qr_available = False
        self.qr_image_path = ""
        self.qr_image_url = ""
        filename = repository.get_settings()["payment_qr_path"]
        if filename:
            try:
                self.qr_image_path = require_saved_png(filename)
                self.qr_available = True
                return
            except (OSError, ValueError) as e:
                logging.exception(f"Error: {e}")
        self.qr_image_url = self._built_in_payment_qr()
        self.qr_available = True

    def _remember_account_path(self):
        path = self.router.url.path.rstrip("/")
        query = self.router.url.query_parameters.get("order", "")
        self._next_path = (
            f"/checkout?order={query}"
            if path == "/checkout" and query.isascii() and query.isdigit()
            else "/dashboard"
        )

    @rx.event
    def restore(self):
        if not self.session_token:
            self._clear_identity()
            return
        try:
            self._repository_customer()
        except PermissionError:
            logging.exception("Unexpected error")
            self.session_token = ""
            self._clear_identity()
        except Exception as e:
            logging.exception(f"Error: {e}")
            self._clear_identity()
            self.error = "Your account could not be loaded. Please try again."

    @rx.event
    def toggle_signup(self):
        self.signup_mode = not self.signup_mode
        self.error = ""

    @rx.event
    def load_account_page(self):
        self.ready = False
        self.error = ""
        self.notice = ""
        self.checkout_orders = []
        self.qr_available = False
        path = self.router.url.path.rstrip("/")
        if not self.session_token:
            self._clear_identity()
            self.ready = True
            if path in ("/dashboard", "/checkout"):
                self._remember_account_path()
                return rx.redirect("/login")
            return
        try:
            repository, customer = self._repository_customer()
            if path == "/login":
                return rx.redirect(self._next_path)
            self.orders = [
                self._view(order)
                for order in repository.list_orders(customer["id"])
            ]
            self.checkout_orders = []
            if path == "/checkout":
                self._load_payment_qr(repository)
                raw_id = self.router.url.query_parameters.get("order", "")
                if raw_id:
                    try:
                        order = repository.customer_order(
                            customer["id"], int(raw_id)
                        )
                    except PermissionError as e:
                        logging.exception(f"Error: {e}")
                        raise LookupError(
                            "Order not found for your account."
                        ) from e
                    self.checkout_orders = [self._view(order)]
        except PermissionError as e:
            logging.exception("Unexpected error")
            self.session_token = ""
            self._clear_identity()
            if path != "/login":
                self.error = str(e)
                query = self.router.url.query_parameters.get("order", "")
                self._next_path = (
                    f"/checkout?order={query}"
                    if path == "/checkout" and query.isdigit()
                    else "/dashboard"
                )
                return rx.redirect("/login")
        except (ValueError, LookupError) as e:
            logging.exception(f"Error: {e}")
            self.error = "This order could not be found for your account. Choose an order from your dashboard."
        except Exception as e:
            logging.exception(f"Error: {e}")
            self.error = "Your orders could not be loaded. Please try again."
        finally:
            self.ready = True

    @rx.event
    def authenticate_form(self, form_data: dict[str, Any]):
        if self.busy:
            return
        self.error = ""
        now = time.time()
        self._auth_attempts = [
            stamp for stamp in self._auth_attempts if now - stamp < 60
        ]
        if len(self._auth_attempts) >= 5:
            self.error = (
                "Too many attempts. Please wait one minute and try again."
            )
            return
        self._auth_attempts.append(now)
        self.busy = True
        yield
        try:
            repository = StoreRepository()
            password = str(form_data.get("password", ""))
            if self.signup_mode:
                if password != str(form_data.get("confirm_password", "")):
                    raise ValueError("Passwords do not match.")
                customer = repository.signup(
                    str(form_data.get("name", "")),
                    str(form_data.get("phone", "")),
                    password,
                    str(form_data.get("email", "")),
                )
            else:
                customer = repository.authenticate(
                    str(form_data.get("identifier", "")), password
                )
                if customer is None:
                    self.error = "Phone/email or password is incorrect."
                    return
            repository.revoke_session(self.session_token)
            self.session_token = repository.create_session(customer["id"])
            self._actor_id = customer["id"]
            self.authenticated = True
            self.customer_name = customer["name"]
            self.admin_access = customer["is_admin"]
            self.orders = []
            self.checkout_orders = []
            yield rx.redirect(self._next_path)
        except ValueError as e:
            logging.exception(f"Error: {e}")
            self.error = str(e)
        except Exception as e:
            logging.exception(f"Error: {e}")
            self.error = "We could not sign you in. Please try again."
        finally:
            self.busy = False

    @rx.event
    def logout(self):
        try:
            StoreRepository().revoke_session(self.session_token)
        except Exception as e:
            logging.exception(f"Error: {e}")
        self.session_token = ""
        self._clear_identity()
        self.bouquet_id = 0
        self._next_path = "/dashboard"
        self.error = ""
        self.notice = ""
        return [
            rx.clear_selected_files("portrait-reference"),
            rx.clear_selected_files("payment-proof"),
            rx.redirect("/login"),
        ]

    @rx.event
    def select_bouquet(self, model_id: int):
        self.error = ""
        self.notice = ""
        try:
            repository, _ = self._repository_customer()
            bouquet = repository.get_bouquet(model_id)
            self.bouquet_id = bouquet["id"]
            self.bouquet_name = bouquet["name"]
            self.bouquet_price_paise = bouquet["price_paise"]
            return rx.call_script(
                "document.getElementById('bouquet-order')?.scrollIntoView({behavior:'smooth',block:'center'})"
            )
        except PermissionError:
            logging.exception("Unexpected error")
            self.session_token = ""
            self._clear_identity()
            self._next_path = "/bouquets"
            return rx.redirect("/login")
        except Exception as e:
            logging.exception(f"Error: {e}")
            self.error = (
                "This bouquet could not be opened. Refresh and try again."
            )

    @rx.event
    def order_bouquet(self, form_data: dict[str, Any]):
        if self.busy:
            return
        self.busy = True
        self.error = ""
        yield
        try:
            repository, customer = self._repository_customer()
            quantity = quantity_value(int(str(form_data.get("quantity", ""))))
            bouquet = repository.get_bouquet(self.bouquet_id)
            order = repository.create_order(
                customer["id"],
                "bouquet",
                {"model_name": bouquet["name"]},
                quantity=quantity,
                bouquet_id=bouquet["id"],
            )
            self.bouquet_id = 0
            yield rx.redirect(f"/checkout?order={order['id']}")
        except PermissionError:
            logging.exception("Unexpected error")
            self.session_token = ""
            self._clear_identity()
            self._next_path = "/bouquets"
            yield rx.redirect("/login")
        except (ValueError, LookupError) as e:
            logging.exception(f"Error: {e}")
            self.error = "Choose an available model and a whole-number quantity between 1 and 999."
        except Exception as e:
            logging.exception(f"Error: {e}")
            self.error = "Your order could not be saved. Please try again."
        finally:
            self.busy = False

    @rx.event
    async def order_portrait(self, files: list[rx.UploadFile]):
        if self.busy:
            return
        self.busy = True
        self.error = ""
        filename = ""
        committed = False
        invalid_reference_count = False
        try:
            if not self.session_token:
                self._clear_identity()
                self._next_path = "/portraits"
                return rx.redirect("/login")
            try:
                repository, customer = self._repository_customer()
            except PermissionError:
                logging.exception("Unexpected error")
                logging.info("Portrait order requires sign-in")
                self.session_token = ""
                self._clear_identity()
                self._next_path = "/portraits"
                return rx.redirect("/login")
            from app.states.public_state import PublicState

            public = await self.get_state(PublicState)
            if len(files) != 1:
                invalid_reference_count = True
                raise ValueError("Select one reference image before ordering.")
            if not public.portrait_size_id or not public.portrait_style_id:
                raise ValueError("Choose an available portrait size and style.")
            filename = await repository.save_upload(customer["id"], files[0])
            order = repository.create_order(
                customer["id"],
                "portrait",
                {},
                portrait_size_id=public.portrait_size_id,
                portrait_style_id=public.portrait_style_id,
                reference_upload_path=filename,
            )
            committed = True
            return [
                rx.clear_selected_files("portrait-reference"),
                rx.redirect(f"/checkout?order={order['id']}"),
            ]
        except (ValueError, LookupError) as e:
            if not invalid_reference_count:
                logging.exception(f"Error: {e}")
            self.error = str(e)
            if isinstance(e, LookupError):
                try:
                    public = await self.get_state(PublicState)
                    public._refresh_portrait_options(repository)
                except Exception as refresh_error:
                    logging.exception(f"Error: {refresh_error}")
        except Exception as e:
            logging.exception(f"Error: {e}")
            self.error = (
                "Your reference and order could not be saved. Please try again."
            )
        finally:
            if filename and not committed:
                try:
                    private_file(filename, repository.database_path).unlink(
                        missing_ok=True
                    )
                except OSError as e:
                    logging.exception(f"Error: {e}")
            for file in files:
                await file.close()
            self.busy = False

    @rx.event
    async def upload_payment_proof(self, files: list[rx.UploadFile]):
        if self.busy:
            return
        self.busy = True
        self.error = ""
        self.notice = ""
        filename = ""
        committed = False
        try:
            repository, customer = self._repository_customer()
            order_id = int(self.router.url.query_parameters.get("order", "0"))
            try:
                order = repository.customer_order(customer["id"], order_id)
            except PermissionError as e:
                logging.exception(f"Error: {e}")
                raise LookupError(
                    "This order could not be found for your account."
                ) from e
            if order["status"] != "awaiting_payment":
                raise ValueError(
                    "This order is not awaiting payment. Refresh your dashboard."
                )
            self._load_payment_qr(repository)
            if not self.qr_available:
                raise ValueError(
                    "Payment QR unavailable. Refresh checkout or contact the studio before paying or submitting proof."
                )
            if len(files) != 1:
                raise ValueError("Select one payment screenshot first.")
            filename = await repository.save_upload(customer["id"], files[0])
            self._load_payment_qr(repository)
            if not self.qr_available:
                raise ValueError(
                    "Payment QR unavailable. Refresh checkout or contact the studio before paying or submitting proof."
                )
            order = repository.submit_payment_proof(
                customer["id"], order_id, filename
            )
            committed = True
            self.checkout_orders = [self._view(order)]
            self.orders = [
                self._view(item)
                for item in repository.list_orders(customer["id"])
            ]
            self.notice = (
                "Proof submitted for review. This is not payment confirmation."
            )
            return rx.clear_selected_files("payment-proof")
        except PermissionError as e:
            logging.exception(f"Error: {e}")
            self.session_token = ""
            self._remember_account_path()
            self._clear_identity()
            return rx.redirect("/login")
        except (ValueError, LookupError) as e:
            logging.exception(f"Error: {e}")
            self.error = str(e)
        except Exception as e:
            logging.exception(f"Error: {e}")
            self.error = (
                "Your payment proof could not be saved. Please try again."
            )
        finally:
            if filename and not committed:
                try:
                    saved_upload_file(filename).unlink(missing_ok=True)
                except OSError as e:
                    logging.exception(f"Error: {e}")
            for file in files:
                await file.close()
            self.busy = False
