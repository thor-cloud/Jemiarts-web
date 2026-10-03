import reflex as rx
import logging
import secrets
from pathlib import Path

from app.states.store_validation import upload_path


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


async def save_image_upload(file: rx.UploadFile) -> str:
    """Returns only the generated filename for storage in SQLite."""
    path: Path | None = None
    try:
        data = await file.read(MAX_UPLOAD_BYTES + 1)
        if not data or len(data) > MAX_UPLOAD_BYTES:
            raise ValueError(
                "Images must be nonempty and no larger than 10 MB."
            )
        extension = _image_extension(data)
        directory = rx.get_upload_dir()
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
