import reflex as rx
import logging
from urllib.parse import quote

from app.states.store_models import (
    Bouquet,
    SiteSettings,
    PortraitSize,
    PortraitStyle,
)
from app.states.store_repository import StoreRepository
from app.states.store_uploads import require_saved_upload
from app.states.store_validation import color_value, phone_number


class PublicState(rx.State):
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
    bouquets: list[Bouquet] = []
    loading: bool = True
    load_error: str = ""
    menu_open: bool = False
    active_page: str = "/"
    portrait_sizes: list[PortraitSize] = []
    portrait_styles: list[PortraitStyle] = []
    portrait_size_id: int = 0
    portrait_style_id: int = 0
    selection_notice: str = ""

    def _refresh_portrait_options(self, repository: StoreRepository):
        self.portrait_sizes = repository.list_portrait_sizes()
        self.portrait_styles = repository.list_portrait_styles()
        self.selection_notice = ""
        if self.portrait_size_id and not any(
            item["id"] == self.portrait_size_id for item in self.portrait_sizes
        ):
            self.portrait_size_id = 0
            self.selection_notice = "Your selected size is no longer available. Please choose again."
        if self.portrait_style_id and not any(
            item["id"] == self.portrait_style_id
            for item in self.portrait_styles
        ):
            self.portrait_style_id = 0
            self.selection_notice = "Your selected style is no longer available. Please choose again."

    def _public_image(self, filename: str) -> str:
        if not filename:
            return ""
        try:
            return require_saved_upload(filename)
        except (OSError, ValueError) as e:
            logging.exception(f"Error: {e}")
            return ""

    @rx.event
    def load_public(self):
        self.loading = True
        self.load_error = ""
        self.menu_open = False
        self.active_page = self.router.url.path.rstrip("/") or "/"
        yield
        try:
            repository = StoreRepository()
            settings = repository.get_settings()
            for key in ("background_color", "text_color", "accent_color"):
                settings[key] = color_value(settings[key])
            settings["contact_number"] = phone_number(
                settings["contact_number"], False
            )
            settings["hero_image_path"] = self._public_image(
                settings["hero_image_path"]
            )
            bouquets = repository.list_bouquets()
            for bouquet in bouquets:
                bouquet["image_path"] = self._public_image(
                    bouquet["image_path"]
                )
            self.settings = settings
            self.bouquets = bouquets
            self._refresh_portrait_options(repository)
        except (OSError, ValueError, RuntimeError, LookupError) as e:
            logging.exception(f"Error: {e}")
            self.load_error = (
                "The studio could not be loaded. Please try again."
            )
            self.bouquets = []
            self.portrait_sizes = []
            self.portrait_styles = []
            self.portrait_size_id = 0
            self.portrait_style_id = 0
        except Exception as e:
            logging.exception(f"Error: {e}")
            self.load_error = (
                "The studio could not be loaded. Please try again."
            )
            self.bouquets = []
            self.portrait_sizes = []
            self.portrait_styles = []
            self.portrait_size_id = 0
            self.portrait_style_id = 0
        finally:
            self.loading = False

    @rx.event
    def toggle_menu(self):
        self.menu_open = not self.menu_open

    @rx.event
    def choose_size(self, size_id: int):
        try:
            self._refresh_portrait_options(StoreRepository())
            if type(size_id) is not int or not any(
                item["id"] == size_id for item in self.portrait_sizes
            ):
                raise ValueError("This size is no longer available.")
            self.portrait_size_id = (
                0 if self.portrait_size_id == size_id else size_id
            )
        except Exception as e:
            logging.exception(f"Error: {e}")
            self.portrait_size_id = 0
            self.selection_notice = (
                "Size unavailable. Refresh the options and try again."
            )

    @rx.event
    def choose_style(self, style_id: int):
        try:
            self._refresh_portrait_options(StoreRepository())
            if type(style_id) is not int or not any(
                item["id"] == style_id for item in self.portrait_styles
            ):
                raise ValueError("This style is no longer available.")
            self.portrait_style_id = (
                0 if self.portrait_style_id == style_id else style_id
            )
        except Exception as e:
            logging.exception(f"Error: {e}")
            self.portrait_style_id = 0
            self.selection_notice = (
                "Style unavailable. Refresh the options and try again."
            )

    @rx.var
    def portrait_selection(self) -> str:
        size = next(
            (
                item
                for item in self.portrait_sizes
                if item["id"] == self.portrait_size_id
            ),
            None,
        )
        style = next(
            (
                item
                for item in self.portrait_styles
                if item["id"] == self.portrait_style_id
            ),
            None,
        )
        if size is None or style is None:
            return "Choose a size and art style to begin."
        return f"Selected: {size['name']} · {style['name']} · provisional ₹{size['price_paise'] / 100:,.2f}"

    @rx.var
    def whatsapp_url(self) -> str:
        number = self.settings["contact_number"].lstrip("+")
        if not number:
            return ""
        message = f"Hello {self.settings['brand_name']}, I'd like to enquire about your work."
        return f"https://wa.me/{number}?text={quote(message)}"
