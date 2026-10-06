import reflex as rx
import logging
import os
from enum import StrEnum
from pathlib import Path

from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, Response
from starlette.concurrency import run_in_threadpool

from app.states.store_database import LOCAL_DATABASE
from app.states.store_repository import StoreRepository
from app.states.private_files import ORDER_FILE_FIELDS, open_private_file
from app.states.store_uploads import _image_extension


class FileKind(StrEnum):
    reference = "reference"
    proof = "proof"


HEADERS = {
    "Cache-Control": "private, no-store",
    "X-Content-Type-Options": "nosniff",
}


class PrivateImageResponse(FileResponse):
    def __init__(self, descriptor: int, mime: str):
        self.descriptor = descriptor
        super().__init__(
            path=f"/proc/self/fd/{descriptor}",
            media_type=mime,
            headers=HEADERS,
            stat_result=os.fstat(descriptor),
        )

    async def __call__(self, scope, receive, send):
        # Never hand an fd pseudo-path to an ASGI server's pathsend extension.
        scope = dict(scope)
        scope["extensions"] = {}
        try:
            await super().__call__(scope, receive, send)
        finally:
            os.close(self.descriptor)


def _error(status: int) -> JSONResponse:
    return JSONResponse(
        {
            "detail": "Authentication required."
            if status == 401
            else "Image unavailable."
        },
        status_code=status,
        headers=HEADERS,
    )


def _response(request: Request, database_path: Path) -> Response:
    descriptor = -1
    try:
        repository = StoreRepository(database_path)
        try:
            actor = repository.session_customer(
                request.cookies.get("studio_session", "")
            )
        except PermissionError:
            logging.exception("Unexpected error")
            return _error(401)
        try:
            kind = FileKind(request.path_params["kind"])
            raw_id = request.path_params["order_id"]
            if not raw_id.isascii() or not raw_id.isdigit() or len(raw_id) > 18:
                return _error(404)
            order = repository.get_order(actor["id"], int(raw_id))
            filename = order[ORDER_FILE_FIELDS[kind]]
            descriptor = open_private_file(filename, database_path)
            extension = _image_extension(os.pread(descriptor, 12, 0))
            mime = {
                ".png": "image/png",
                ".jpg": "image/jpeg",
                ".webp": "image/webp",
            }[extension]
            response = PrivateImageResponse(descriptor, mime)
            descriptor = -1
            return response
        except (PermissionError, LookupError, ValueError, OSError):
            logging.exception("Unexpected error")
            return _error(404)
    except Exception as e:
        logging.exception(f"Error: {e}")
        return _error(404)
    finally:
        if descriptor >= 0:
            os.close(descriptor)


async def order_image(request: Request) -> Response:
    database_path = getattr(
        request.app.state, "studio_database_path", LOCAL_DATABASE
    )
    return await run_in_threadpool(_response, request, database_path)
