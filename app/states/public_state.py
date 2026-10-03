import reflex as rx
import logging
from urllib.parse import quote

from app.states.store_models import Bouquet, SiteSettings
from app.states.store_repository import StoreRepository
from app.states.store_uploads import require_saved_upload
from app.states.store_validation import color_value, phone_number


PORTRAIT_STARTING_PRICES_PAISE: dict[str, int] = {"A4": 150000, "A3": 250000}


class PublicState(rx.State):
    settings: SiteSettings = {
        "id": 1,
        "brand_name": "Artist Studio",
        "background_color": "#F7F3EC",
        "text_color": "#29231E",
        "accent_color": "#B76D50",
        "hero_image_path": "",
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
    portrait_size: str = "A4"

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
        except (OSError, ValueError, RuntimeError, LookupError) as e:
            logging.exception(f"Error: {e}")
            self.load_error = (
                "The studio could not be loaded. Please try again."
            )
            self.bouquets = []
        except Exception as e:
            logging.exception(f"Error: {e}")
            self.load_error = (
                "The studio could not be loaded. Please try again."
            )
            self.bouquets = []
        finally:
            self.loading = False

    @rx.event
    def toggle_menu(self):
        self.menu_open = not self.menu_open

    @rx.event
    def choose_size(self, size: str):
        if size in PORTRAIT_STARTING_PRICES_PAISE:
            self.portrait_size = size

    @rx.var
    def a4_price(self) -> float:
        return PORTRAIT_STARTING_PRICES_PAISE["A4"] / 100

    @rx.var
    def a3_price(self) -> float:
        return PORTRAIT_STARTING_PRICES_PAISE["A3"] / 100

    @rx.var
    def portrait_price(self) -> float:
        return PORTRAIT_STARTING_PRICES_PAISE[self.portrait_size] / 100

    @rx.var
    def whatsapp_url(self) -> str:
        number = self.settings["contact_number"].lstrip("+")
        if not number:
            return ""
        message = f"Hello {self.settings['brand_name']}, I'd like to enquire about your work."
        return f"https://wa.me/{number}?text={quote(message)}"
