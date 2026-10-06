import reflex as rx
import logging
import secrets
import struct
import zlib
from pathlib import Path

from app.states.store_validation import upload_path
from app.states.private_files import private_directory
from app.states.store_database import LOCAL_DATABASE


MAX_UPLOAD_BYTES = 10 * 1024 * 1024


def _image_extension(data: bytes) -> str:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if data.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp"
    raise ValueError("Use a PNG, JPEG, or WebP image.")


def saved_upload_file(filename: str) -> Path:
    return rx.get_upload_dir() / upload_path(filename, True)


def require_saved_upload(filename: str) -> str:
    validated = upload_path(filename, True)
    path = saved_upload_file(validated)
    if path.is_symlink() or not path.is_file():
        raise ValueError("Uploaded file does not exist.")
    return validated


def _verify_png(data: bytes) -> None:
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("The payment QR must be a PNG image.")
    offset = 8
    seen_header = False
    seen_data = False
    compressed_parts: list[bytes] = []
    while offset + 12 <= len(data):
        length = int.from_bytes(data[offset : offset + 4], "big")
        end = offset + 12 + length
        if end > len(data):
            break
        kind = data[offset + 4 : offset + 8]
        payload = data[offset + 8 : end - 4]
        crc = int.from_bytes(data[end - 4 : end], "big")
        if zlib.crc32(data[offset + 4 : end - 4]) != crc:
            break
        if not seen_header:
            if kind != b"IHDR" or length != 13:
                break
            width, height, depth, color, compression, filtering, interlace = (
                struct.unpack(">IIBBBBB", payload)
            )
            depths = {
                0: (1, 2, 4, 8, 16),
                2: (8, 16),
                3: (1, 2, 4, 8),
                4: (8, 16),
                6: (8, 16),
            }
            if not (
                width
                and height
                and width * height <= 40_000_000
                and depth in depths.get(color, ())
                and compression == 0
                and filtering == 0
                and interlace in (0, 1)
            ):
                break
            seen_header = True
        elif kind == b"IHDR":
            break
        if kind == b"IDAT" and length:
            seen_data = True
            compressed_parts.append(payload)
        if kind == b"IEND":
            if length == 0 and seen_header and seen_data and end == len(data):
                try:
                    decoder = zlib.decompressobj()
                    decoded = decoder.decompress(
                        b"".join(compressed_parts), 64 * 1024 * 1024 + 1
                    )
                    if (
                        not decoded
                        or len(decoded) > 64 * 1024 * 1024
                        or not decoder.eof
                        or decoder.unused_data
                    ):
                        raise ValueError(
                            "Payment QR PNG image data is invalid or too large."
                        )
                except zlib.error as e:
                    logging.exception(f"Error: {e}")
                    raise ValueError(
                        "Payment QR PNG image data is invalid."
                    ) from e
                return
            break
        offset = end
    raise ValueError("Use a complete, valid PNG image for the payment QR.")


def require_saved_png(filename: str) -> str:
    validated = require_saved_upload(filename)
    if not validated.lower().endswith(".png"):
        raise ValueError("The payment QR must be a PNG image.")
    with saved_upload_file(validated).open("rb") as source:
        data = source.read(MAX_UPLOAD_BYTES + 1)
    if not data or len(data) > MAX_UPLOAD_BYTES:
        raise ValueError(
            "The payment QR must be nonempty and no larger than 10 MB."
        )
    _verify_png(data)
    return validated


async def save_image_upload(
    file: rx.UploadFile,
    png_only: bool = False,
    private: bool = False,
    database_path: Path = LOCAL_DATABASE,
) -> str:
    """Returns only the generated filename for storage in SQLite."""
    path: Path | None = None
    try:
        data = await file.read(MAX_UPLOAD_BYTES + 1)
        if not data or len(data) > MAX_UPLOAD_BYTES:
            raise ValueError(
                "Images must be nonempty and no larger than 10 MB."
            )
        extension = _image_extension(data)
        if png_only:
            _verify_png(data)
        directory = (
            private_directory(database_path) if private else rx.get_upload_dir()
        )
        directory.mkdir(parents=True, exist_ok=True)
        filename = f"{secrets.token_hex(24)}{extension}"
        path = directory / filename
        with path.open("xb") as output:
            output.write(data)
        path.chmod(0o600)
        return filename
    except (OSError, ValueError) as error:
        logging.exception(f"Error: {error}")
        if path is not None:
            path.unlink(missing_ok=True)
        raise
    finally:
        await file.close()
