import reflex as rx
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from app.states.public_state import PORTRAIT_STARTING_PRICES_PAISE
from app.states.store_uploads import require_saved_upload


class PublicStoreTests(unittest.TestCase):
    def test_provisional_prices_are_server_side_paise(self):
        self.assertEqual(set(PORTRAIT_STARTING_PRICES_PAISE), {"A4", "A3"})
        self.assertEqual(PORTRAIT_STARTING_PRICES_PAISE["A4"], 150000)
        self.assertEqual(PORTRAIT_STARTING_PRICES_PAISE["A3"], 250000)
        for price in PORTRAIT_STARTING_PRICES_PAISE.values():
            self.assertIs(type(price), int)
            self.assertGreater(price, 0)

    def test_public_images_must_be_local_existing_uploads(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "bouquet.png").write_bytes(b"image")
            with patch.object(rx, "get_upload_dir", return_value=root):
                self.assertEqual(
                    require_saved_upload("bouquet.png"), "bouquet.png"
                )
                for invalid in (
                    "../proof.png",
                    "/proof.png",
                    "https://example.com/photo.png",
                    "missing.png",
                ):
                    with self.assertRaises(ValueError):
                        require_saved_upload(invalid)


if __name__ == "__main__":
    unittest.main()
