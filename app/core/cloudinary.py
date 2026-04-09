"""
Cloudinary integration helpers for the ULMIND backend.
All SDK calls are synchronous so we wrap them with asyncio.to_thread
to avoid blocking the event loop.
"""
import asyncio
import logging
import cloudinary
import cloudinary.uploader

from app.core.config import settings

logger = logging.getLogger(__name__)

# ── Configure Cloudinary once at import time ─────────────────────────────────
cloudinary.config(
    cloud_name=settings.CLOUDINARY_CLOUD_NAME,
    api_key=settings.CLOUDINARY_API_KEY,
    api_secret=settings.CLOUDINARY_API_SECRET,
    secure=True,
)

MERCHANDISE_FOLDER = "ulmind/merchandise"


# ── Upload ───────────────────────────────────────────────────────────────────

async def upload_image(file_bytes: bytes, filename: str) -> dict:
    """
    Upload a single image to Cloudinary (merchandise folder).

    Returns a dict with:
        - url        : secure public URL for serving
        - public_id  : Cloudinary public_id needed for future deletion
    """
    def _upload():
        return cloudinary.uploader.upload(
            file_bytes,
            folder=MERCHANDISE_FOLDER,
            resource_type="image",
            use_filename=True,
            unique_filename=True,
        )

    try:
        result = await asyncio.to_thread(_upload)
        return {
            "url": result["secure_url"],
            "public_id": result["public_id"],
        }
    except Exception as e:
        logger.error(f"Cloudinary upload failed for '{filename}': {e}")
        raise


# ── Delete ───────────────────────────────────────────────────────────────────

async def delete_image(public_id: str) -> None:
    """
    Delete a single image from Cloudinary by its public_id.
    Errors are logged but NOT re-raised so a partial failure
    doesn't break the rest of the request.
    """
    def _destroy():
        return cloudinary.uploader.destroy(public_id, resource_type="image")

    try:
        result = await asyncio.to_thread(_destroy)
        if result.get("result") != "ok":
            logger.warning(f"Cloudinary delete returned non-ok for '{public_id}': {result}")
    except Exception as e:
        logger.error(f"Cloudinary delete failed for '{public_id}': {e}")


async def delete_images(public_ids: list[str]) -> None:
    """Delete multiple images concurrently."""
    if not public_ids:
        return
    await asyncio.gather(*[delete_image(pid) for pid in public_ids])
