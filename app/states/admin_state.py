import reflex as rx
import logging
import re
from typing import Any, TypedDict, cast
from urllib.parse import quote

from app.states.store_models import (
    Bouquet,
    OrderStatus,
    SiteSettings,
    PortraitSize,
    PortraitStyle,
)
from app.states.store_repository import StoreRepository
from app.states.store_uploads import (
    require_saved_upload,
    saved_upload_file,
    require_saved_png,
)
from app.states.store_validation import ORDER_TRANSITIONS, rupees_to_paise, text
from app.states.order_report import (
    ReportRow,
    build_order_report,
    format_paise,
    report_scope,
    validate_report_filters,
)


class AdminOrder(TypedDict):
    id: int
    name: str
    phone: str
    title: str
    date: str
    amount: float
    amount_paise: int
    status: str
    options: list[str]
    reference: bool
    proof: bool
    whatsapp: str
    is_bouquet: bool
    recipient_name: str
    delivery_address: str
    preferred_delivery_date: str
    gift_message: str


class AdminState(rx.State):
    ready: bool = False
    allowed: bool = False
    busy: bool = False
    error: str = ""
    notice: str = ""
    orders: list[AdminOrder] = []
    order_query: str = ""
    order_status_filter: str = ""
    report_start: str = ""
    report_end: str = ""
    report_status: str = ""
    report_error: str = ""
    report_form_version: int = 0
    bouquets: list[Bouquet] = []
    portrait_sizes: list[PortraitSize] = []
    portrait_styles: list[PortraitStyle] = []
    delete_kind: str = ""
    delete_id: int = 0
    delete_name: str = ""
    bouquet_id: int = 0
    bouquet_name: str = ""
    bouquet_price: str = ""
    bouquet_image: str = ""
    hero_image: str = ""
    payment_qr_image: str = ""
    settings: SiteSettings = {
        "id": 1,
        "brand_name": "Artist Studio",
        "background_color": "#F7F3EC",
        "text_color": "#29231E",
        "accent_color": "#B76D50",
        "hero_image_path": "",
        "payment_qr_path": "",
        "welcome_text": "",
        "artist_biography": "",
        "contact_number": "",
        "updated_at": "",
    }
    _bouquet_upload: str = ""
    _hero_upload: str = ""
    _payment_qr_upload: str = ""

    @rx.var
    def filtered_orders(self) -> list[AdminOrder]:
        if not self.allowed:
            return []
        query = self.order_query.strip().casefold()
        numeric_query = re.fullmatch(r"#?([0-9]+)", query)
        order_number = ""
        if numeric_query:
            order_number = numeric_query.group(1).lstrip("0") or "0"
        result: list[AdminOrder] = []
        for order in self.orders:
            if (
                self.order_status_filter
                and order["status"] != self.order_status_filter
            ):
                continue
            if numeric_query:
                matches = str(order["id"]) == order_number
            else:
                matches = (
                    not query
                    or query in order["name"].casefold()
                    or query in order["status"].casefold()
                    or query in order["status"].replace("_", " ").casefold()
                )
            if matches:
                result.append(order)
        return result

    @rx.var
    def report_rows(self) -> list[ReportRow]:
        if not self.allowed:
            return []
        return build_order_report(
            self.orders, self.report_start, self.report_end, self.report_status
        )["rows"]

    @rx.var
    def report_order_count(self) -> int:
        if not self.allowed:
            return 0
        return build_order_report(
            self.orders, self.report_start, self.report_end, self.report_status
        )["count"]

    @rx.var
    def report_order_value(self) -> str:
        if not self.allowed:
            return format_paise(0)
        return format_paise(
            build_order_report(
                self.orders,
                self.report_start,
                self.report_end,
                self.report_status,
            )["order_value_paise"]
        )

    @rx.var
    def report_confirmed_value(self) -> str:
        if not self.allowed:
            return format_paise(0)
        return format_paise(
            build_order_report(
                self.orders,
                self.report_start,
                self.report_end,
                self.report_status,
            )["confirmed_value_paise"]
        )

    @rx.var
    def report_scope_label(self) -> str:
        if not self.allowed:
            return ""
        return report_scope(
            self.report_start, self.report_end, self.report_status
        )

    @rx.var
    def report_filters_active(self) -> bool:
        return self.allowed and bool(
            self.report_start or self.report_end or self.report_status
        )

    @rx.event
    async def apply_report_filters(self, form_data: dict[str, Any]):
        if not self.allowed:
            self.report_start = ""
            self.report_end = ""
            self.report_status = ""
            self.report_error = ""
            return
        try:
            await self._authorized()
            start, end, status = validate_report_filters(
                form_data.get("report_start", ""),
                form_data.get("report_end", ""),
                form_data.get("report_status", ""),
            )
            self.report_start = start
            self.report_end = end
            self.report_status = status
            self.report_error = ""
        except Exception as e:
            if isinstance(e, PermissionError):
                self._deny()
            elif isinstance(e, ValueError):
                self.report_error = str(e)
            else:
                logging.exception(f"Error: {e}")
                self.report_error = (
                    "Report filters could not be applied. Please retry."
                )

    @rx.event
    async def reset_report_filters(self):
        self.report_start = ""
        self.report_end = ""
        self.report_status = ""
        self.report_error = ""
        if not self.allowed:
            return
        try:
            await self._authorized()
            self.report_form_version += 1
        except Exception as e:
            if isinstance(e, PermissionError):
                self._deny()
            else:
                logging.exception(f"Error: {e}")
                self.report_error = (
                    "Report filters could not be reset. Please retry."
                )

    @rx.event
    def set_order_query(self, value: str):
        if not self.allowed:
            self.order_query = ""
            self.order_status_filter = ""
            return
        self.order_query = value

    @rx.event
    def set_order_status_filter(self, value: str):
        if not self.allowed:
            self.order_query = ""
            self.order_status_filter = ""
            return
        self.order_status_filter = value if value in ORDER_TRANSITIONS else ""

    @rx.event
    def reset_order_filters(self):
        self.order_query = ""
        self.order_status_filter = ""

    async def _authorized(self) -> tuple[StoreRepository, int]:
        from app.states.customer_state import CustomerState

        customer = await self.get_state(CustomerState)
        repository = StoreRepository()
        actor = repository.session_admin(customer.session_token)
        return repository, actor["id"]

    def _deny(self):
        self.allowed = False
        self.orders = []
        self.order_query = ""
        self.order_status_filter = ""
        self.report_start = ""
        self.report_end = ""
        self.report_status = ""
        self.report_error = ""
        self.bouquets = []
        self.portrait_sizes = []
        self.portrait_styles = []
        self.delete_id = 0
        self.delete_kind = ""
        self.delete_name = ""
        self.notice = ""
        self._bouquet_upload = ""
        self._hero_upload = ""
        self._payment_qr_upload = ""
        self.bouquet_id = 0
        self.bouquet_name = ""
        self.bouquet_price = ""
        self.bouquet_image = ""
        self.hero_image = ""
        self.payment_qr_image = ""
        self.settings = {
            "id": 1,
            "brand_name": "Artist Studio",
            "background_color": "#F7F3EC",
            "text_color": "#29231E",
            "accent_color": "#B76D50",
            "hero_image_path": "",
            "payment_qr_path": "",
            "welcome_text": "",
            "artist_biography": "",
            "contact_number": "",
            "updated_at": "",
        }
        self.error = "Administrator access is required. Sign in with the studio owner's account and complete any required password change."

    def _image(self, filename: str) -> str:
        if not filename:
            return ""
        try:
            return require_saved_upload(filename)
        except (ValueError, FileNotFoundError):
            logging.exception("Unexpected error")
            return ""
        except OSError as e:
            logging.exception(f"Error: {e}")
            return ""

    def _load_orders(self, repository: StoreRepository, actor: int):
        result: list[AdminOrder] = []
        for order in repository.list_orders(actor, all_customers=True):
            customer = repository.get_customer(actor, order["user_id"])
            title = (
                f"{order['details'].get('size', 'Custom')} portrait · {order['details'].get('style', 'Style not recorded')}"
                if order["kind"] == "portrait"
                else order["details"].get("model_name", "Bouquet")
            )
            status = order["status"]
            message = f"Hello {customer['name']}, your order #{order['id']} ({title}) is {status.replace('_', ' ')}. Please contact the studio with any questions."
            result.append(
                AdminOrder(
                    id=order["id"],
                    name=customer["name"],
                    phone=customer["phone"],
                    title=f"{title} · quantity {order['quantity']}",
                    date=order["created_at"][:10],
                    amount=order["total_price_paise"] / 100,
                    amount_paise=int(order["total_price_paise"]),
                    status=status,
                    options=[status, *ORDER_TRANSITIONS[status]],
                    is_bouquet=order["kind"] == "bouquet",
                    recipient_name=order["details"].get("recipient_name", "")
                    if order["kind"] == "bouquet"
                    else "",
                    delivery_address=order["details"].get(
                        "delivery_address", ""
                    )
                    if order["kind"] == "bouquet"
                    else "",
                    preferred_delivery_date=order["details"].get(
                        "preferred_delivery_date", ""
                    )
                    if order["kind"] == "bouquet"
                    else "",
                    gift_message=order["details"].get("gift_message", "")
                    if order["kind"] == "bouquet"
                    else "",
                    reference=bool(order["reference_upload_path"]),
                    proof=bool(order["payment_proof_path"]),
                    whatsapp=f"https://wa.me/{customer['phone'].lstrip('+')}?text={quote(message, safe='')}",
                )
            )
        self.orders = result

    def _discard(self, filename: str):
        if filename:
            try:
                saved_upload_file(filename).unlink(missing_ok=True)
            except OSError as e:
                logging.exception(f"Error: {e}")

    @rx.event
    async def load_admin(self):
        self.ready = False
        self.allowed = False
        self.bouquets = []
        self.portrait_sizes = []
        self.portrait_styles = []
        self.delete_id = 0
        self.delete_kind = ""
        self.orders = []
        self.error = ""
        self.notice = ""
        yield
        try:
            from app.states.customer_state import CustomerState

            customer = await self.get_state(CustomerState)
            if not customer.session_token:
                self._deny()
                self.ready = True
                return
            repository, actor = await self._authorized()
            self._load_orders(repository, actor)
            self.bouquets = repository.list_bouquets()
            self.portrait_sizes = repository.list_portrait_sizes()
            self.portrait_styles = repository.list_portrait_styles()
            self.settings = repository.get_settings()
            self.hero_image = self._image(
                self._hero_upload or self.settings["hero_image_path"]
            )
            self.payment_qr_image = self._image(
                self._payment_qr_upload or self.settings["payment_qr_path"]
            )
            self.allowed = True
        except Exception as e:
            if isinstance(e, PermissionError):
                self._deny()
            else:
                logging.exception(f"Error: {e}")
                self.error = "The workspace could not be loaded. Please retry."
        finally:
            self.ready = True

    @rx.event
    async def save_status(self, order_id: int, form_data: dict[str, Any]):
        if self.busy:
            return
        self.busy = True
        self.error = ""
        self.notice = ""
        yield
        try:
            repository, actor = await self._authorized()
            repository.set_order_status(
                actor,
                order_id,
                cast(OrderStatus, str(form_data.get("status", ""))),
            )
            self._load_orders(repository, actor)
            self.notice = f"Order #{order_id} status saved. WhatsApp only opens a draft; nothing has been sent."
        except Exception as e:
            if isinstance(e, PermissionError):
                self._deny()
            elif isinstance(e, (ValueError, LookupError)):
                self.error = str(e)
            else:
                logging.exception(f"Error: {e}")
                self.error = "Status could not be saved. Refresh and try again."
        finally:
            self.busy = False

    @rx.event
    async def edit_bouquet(self, bouquet_id: int):
        if self.busy:
            return
        try:
            repository, _ = await self._authorized()
            bouquet = repository.get_bouquet(bouquet_id)
            self._discard(self._bouquet_upload)
            self._bouquet_upload = ""
            self.bouquet_id = bouquet_id
            self.bouquet_name = bouquet["name"]
            self.bouquet_price = f"{bouquet['price_paise'] / 100:.2f}"
            self.bouquet_image = self._image(bouquet["image_path"])
            return [
                rx.clear_selected_files("admin-bouquet"),
                rx.call_script(
                    "document.getElementById('bouquet-editor')?.scrollIntoView({behavior:'smooth'})"
                ),
            ]
        except Exception as e:
            if isinstance(e, PermissionError):
                self._deny()
            elif isinstance(e, (ValueError, LookupError)):
                self.error = "This bouquet could not be opened."
            else:
                logging.exception(f"Error: {e}")
                self.error = "This bouquet could not be opened."

    @rx.event
    async def new_bouquet(self):
        try:
            await self._authorized()
            self._discard(self._bouquet_upload)
            self._bouquet_upload = ""
            self.bouquet_id = 0
            self.bouquet_name = ""
            self.bouquet_price = ""
            self.bouquet_image = ""
            return rx.clear_selected_files("admin-bouquet")
        except Exception as e:
            if isinstance(e, PermissionError):
                self._deny()
            else:
                logging.exception(f"Error: {e}")
                self.error = "A new bouquet could not be started. Please retry."

    @rx.event
    async def stage_bouquet_image(self, files: list[rx.UploadFile]):
        return await self._stage_image("bouquet", files)

    @rx.event
    async def stage_hero_image(self, files: list[rx.UploadFile]):
        return await self._stage_image("hero", files)

    @rx.event
    async def stage_payment_qr_image(self, files: list[rx.UploadFile]):
        return await self._stage_image("payment-qr", files)

    async def _stage_image(self, target: str, files: list[rx.UploadFile]):
        if self.busy:
            for file in files:
                await file.close()
            return
        self.busy = True
        self.error = ""
        self.notice = ""
        filename = ""
        staged = False
        try:
            repository, actor = await self._authorized()
            if (
                target not in ("bouquet", "hero", "payment-qr")
                or len(files) != 1
            ):
                raise ValueError(
                    "Choose exactly one JPEG, PNG or WebP image, up to 10 MB."
                )
            filename = await repository.save_admin_upload(
                actor, files[0], png_only=target == "payment-qr"
            )
            await self._authorized()
            if target == "bouquet":
                self._discard(self._bouquet_upload)
                self._bouquet_upload = filename
                self.bouquet_image = filename
            elif target == "payment-qr":
                self._discard(self._payment_qr_upload)
                self._payment_qr_upload = filename
                self.payment_qr_image = filename
            else:
                self._discard(self._hero_upload)
                self._hero_upload = filename
                self.hero_image = filename
            staged = True
            self.notice = "Image uploaded. Save the form below to publish it."
            return rx.clear_selected_files(f"admin-{target}")
        except Exception as e:
            if isinstance(e, PermissionError):
                self._deny()
            elif isinstance(e, (ValueError, LookupError)):
                self.error = str(e)
            else:
                logging.exception(f"Error: {e}")
                self.error = "Image upload failed. Please try again."
        finally:
            if filename and not staged:
                self._discard(filename)
            for file in files:
                await file.close()
            self.busy = False

    @rx.event
    async def save_bouquet(self, form_data: dict[str, Any]):
        if self.busy:
            return
        self.busy = True
        self.error = ""
        self.notice = ""
        yield
        try:
            repository, actor = await self._authorized()
            name = text(str(form_data.get("name", "")), "Bouquet name", 160)
            price = rupees_to_paise(str(form_data.get("price", "")))
            image = self._bouquet_upload
            if not image and self.bouquet_id:
                image = repository.get_bouquet(self.bouquet_id)["image_path"]
            image = require_saved_upload(image)
            bouquet = repository.save_bouquet(
                actor, name, price, image, self.bouquet_id or None
            )
            self._bouquet_upload = ""
            self.bouquet_id = bouquet["id"]
            self.bouquet_name = bouquet["name"]
            self.bouquet_price = f"{price / 100:.2f}"
            self.bouquet_image = image
            self.bouquets = repository.list_bouquets()
            self.notice = "Bouquet saved and published to the gallery."
            from app.states.public_state import PublicState

            yield PublicState.load_public
        except Exception as e:
            if isinstance(e, PermissionError):
                self._deny()
            elif isinstance(e, (ValueError, LookupError)):
                self.error = str(e)
            else:
                logging.exception(f"Error: {e}")
                self.error = "Bouquet could not be saved. Your uploaded image is retained for retry."
        finally:
            self.busy = False

    @rx.event
    async def save_portrait_option(
        self, kind: str, option_id: int, form_data: dict[str, Any]
    ):
        if self.busy:
            return
        self.busy = True
        self.error = ""
        self.notice = ""
        yield
        try:
            repository, actor = await self._authorized()
            if type(option_id) is not int or option_id < 0:
                raise ValueError("Invalid option ID.")
            if kind == "size":
                repository.save_portrait_size(
                    actor,
                    str(form_data.get("name", "")),
                    str(form_data.get("dimensions", "")),
                    rupees_to_paise(str(form_data.get("price", ""))),
                    option_id or None,
                )
            elif kind == "style":
                repository.save_portrait_style(
                    actor, str(form_data.get("name", "")), option_id or None
                )
            else:
                raise ValueError("Unknown option type.")
            self.portrait_sizes = repository.list_portrait_sizes()
            self.portrait_styles = repository.list_portrait_styles()
            self.notice = "Portrait option published. Existing orders keep their saved labels and prices."
            from app.states.public_state import PublicState

            public = await self.get_state(PublicState)
            public._refresh_portrait_options(repository)
        except Exception as e:
            if isinstance(e, PermissionError):
                self._deny()
            elif isinstance(e, (ValueError, LookupError)):
                self.error = str(e)
            else:
                logging.exception(f"Error: {e}")
                self.error = "Portrait option could not be saved. Please retry."
        finally:
            self.busy = False

    @rx.event
    async def request_portrait_delete(self, kind: str, option_id: int):
        if self.busy:
            return
        try:
            repository, _ = await self._authorized()
            if kind not in ("size", "style") or type(option_id) is not int:
                raise ValueError("Invalid portrait option.")
            options = (
                repository.list_portrait_sizes()
                if kind == "size"
                else repository.list_portrait_styles()
            )
            option = next(
                (item for item in options if item["id"] == option_id), None
            )
            if option is None:
                raise LookupError(
                    "Option is no longer available. Refresh the workspace."
                )
            self.delete_kind = kind
            self.delete_id = option_id
            self.delete_name = option["name"]
        except Exception as e:
            if isinstance(e, PermissionError):
                self._deny()
            elif isinstance(e, (ValueError, LookupError)):
                self.error = str(e)
            else:
                logging.exception(f"Error: {e}")
                self.error = str(e)

    @rx.event
    async def cancel_portrait_delete(self):
        if self.busy:
            return
        try:
            await self._authorized()
            self.delete_id = 0
            self.delete_kind = ""
        except Exception as e:
            if isinstance(e, PermissionError):
                self._deny()
            else:
                logging.exception(f"Error: {e}")
                self.error = "Could not refresh access. Please retry."

    @rx.event
    async def confirm_portrait_delete(self):
        if self.busy:
            return
        self.busy = True
        self.error = ""
        self.notice = ""
        yield
        try:
            repository, actor = await self._authorized()
            repository.delete_portrait_option(
                actor, self.delete_kind, self.delete_id
            )
            self.delete_id = 0
            self.delete_kind = ""
            self.portrait_sizes = repository.list_portrait_sizes()
            self.portrait_styles = repository.list_portrait_styles()
            from app.states.public_state import PublicState

            public = await self.get_state(PublicState)
            public._refresh_portrait_options(repository)
            self.notice = (
                "Portrait option removed. Historical orders are unchanged."
            )
        except Exception as e:
            if isinstance(e, PermissionError):
                self._deny()
            elif isinstance(e, (ValueError, LookupError)):
                self.error = str(e)
            else:
                logging.exception(f"Error: {e}")
                self.error = "Option could not be removed. Please retry."
        finally:
            self.busy = False

    @rx.event
    async def save_settings(self, form_data: dict[str, Any]):
        if self.busy:
            return
        self.busy = True
        self.error = ""
        self.notice = ""
        yield
        try:
            repository, actor = await self._authorized()
            settings = repository.get_settings()
            for key in (
                "brand_name",
                "background_color",
                "text_color",
                "accent_color",
                "welcome_text",
                "artist_biography",
                "contact_number",
            ):
                settings[key] = str(form_data.get(key, ""))
            if self._hero_upload:
                settings["hero_image_path"] = require_saved_upload(
                    self._hero_upload
                )
            if self._payment_qr_upload:
                settings["payment_qr_path"] = require_saved_png(
                    self._payment_qr_upload
                )
            self.settings = repository.update_settings(actor, settings)
            self._payment_qr_upload = ""
            self.payment_qr_image = self._image(
                self.settings["payment_qr_path"]
            )
            self._hero_upload = ""
            self.hero_image = self._image(self.settings["hero_image_path"])
            self.notice = "Site settings saved. The public storefront now uses your changes."
            from app.states.public_state import PublicState

            yield PublicState.load_public
        except Exception as e:
            if isinstance(e, PermissionError):
                self._deny()
            elif isinstance(e, (ValueError, LookupError)):
                self.error = str(e)
            else:
                logging.exception(f"Error: {e}")
                self.error = "Settings could not be saved. Please retry."
        finally:
            self.busy = False
