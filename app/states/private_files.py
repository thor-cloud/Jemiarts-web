import reflex as rx
import logging
import os
import stat
from pathlib import Path

from app.states.store_database import (
    LOCAL_DATABASE,
    connection,
    initialize_database,
)
from app.states.store_validation import upload_path


ORDER_FILE_FIELDS = {
    "reference": "reference_upload_path",
    "proof": "payment_proof_path",
}


def _reject_symlink_components(path: Path) -> None:
    for component in (path, *path.parents):
        if component.is_symlink():
            raise ValueError("Unsafe file storage.")


def private_directory(database_path: Path = LOCAL_DATABASE) -> Path:
    directory = database_path.absolute().parent / "private_uploads"
    _reject_symlink_components(directory)
    public = rx.get_upload_dir().resolve()
    assets = Path("assets").resolve()
    resolved = directory.resolve()
    if resolved.is_relative_to(public) or resolved.is_relative_to(assets):
        raise ValueError("Unsafe file storage.")
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    directory.chmod(0o700)
    return directory


def private_file(filename: str, database_path: Path = LOCAL_DATABASE) -> Path:
    return private_directory(database_path) / upload_path(filename, True)


def require_private_file(
    filename: str, database_path: Path = LOCAL_DATABASE
) -> str:
    filename = upload_path(filename, True)
    path = private_file(filename, database_path)
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise ValueError("Image unavailable.")
    return filename


def open_private_file(
    filename: str, database_path: Path = LOCAL_DATABASE
) -> int:
    path = private_file(filename, database_path)
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValueError("Image unavailable.")
        return descriptor
    except Exception:
        logging.exception("Unexpected error")
        os.close(descriptor)
        raise


def migrate_private_files(database_path: Path = LOCAL_DATABASE) -> None:
    """Run synchronously before constructing the backend, never after static serving starts."""
    try:
        initialize_database(database_path)
        destination = private_directory(database_path)
        public = rx.get_upload_dir().absolute()
        _reject_symlink_components(public)
        with connection(database_path) as conn:
            names = {
                row[0]
                for row in conn.execute(
                    "SELECT reference_upload_path FROM orders UNION SELECT payment_proof_path FROM orders"
                )
                if row[0]
            }
            public_names = {
                row[0]
                for row in conn.execute(
                    "SELECT image_path FROM bouquet_models UNION SELECT hero_image_path FROM site_settings UNION SELECT payment_qr_path FROM site_settings"
                )
                if row[0]
            }
            for name in sorted(names):
                upload_path(name, True)
                if name in public_names:
                    raise ValueError(
                        "Order image conflicts with a public asset."
                    )
                source = public / name
                target = destination / name
                if source.is_symlink() or target.is_symlink():
                    raise ValueError("Unsafe order image.")
                if source.exists():
                    info = source.lstat()
                    if (
                        not stat.S_ISREG(info.st_mode)
                        or info.st_nlink != 1
                        or target.exists()
                    ):
                        raise ValueError("Unsafe order image.")
                    source.chmod(0o600)
                    # rename is atomic; cross-filesystem failures deliberately stop startup.
                    source.rename(target)
                if target.exists():
                    require_private_file(name, database_path)
                    target.chmod(0o600)
    except Exception as e:
        logging.exception(f"Error: {e}")
        raise RuntimeError(
            "Private image migration failed; backend startup refused."
        ) from e
