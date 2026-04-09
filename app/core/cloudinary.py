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

# ── Configure Cloudinary ─────────────────────────────────────────────────────
cloudinary.config(
    cloud_name=settings.CLOUDINARY_CLOUD_NAME,
    api_key=settings.CLOUDINARY_API_KEY,
    api_secret=settings.CLOUDINARY_API_SECRET,
    secure=True,
)

# ── Folder Constants ──────────────────────────────────────────────────────────
# Organizing images into folders as requested.
MERCHANDISE_FOLDER = "ulmind/merchandise"
PROFILE_FOLDER = "ulmind/profiles"
USER_FOLDER = "ulmind/users"
GENERAL_FOLDER = "ulmind/general"


# ── Upload ───────────────────────────────────────────────────────────────────

async def upload_image(file_bytes: bytes, filename: str, folder: str = GENERAL_FOLDER) -> dict:
    """
    Upload a single image to Cloudinary in a specific folder.
    
    Guarantees Original Quality:
    By NOT passing any width, height, crop, or quality parameters, 
    Cloudinary stores and serves the original, unmodified file.
    """
    def _upload():
        return cloudinary.uploader.upload(
            file_bytes,
            folder=folder,
            resource_type="image",
            use_filename=True,
            unique_filename=True,
            # We explicitly OMIT transformations to keep original quality
        )

    try:
        result = await asyncio.to_thread(_upload)
        return {
            "url": result["secure_url"],
            "public_id": result["public_id"],
        }
    except Exception as e:
        logger.error(f"Cloudinary upload failed for '{filename}' in folder '{folder}': {e}")
        raise


# ── Delete ───────────────────────────────────────────────────────────────────

async def delete_image(public_id: str) -> None:
    """
    Delete a single image from Cloudinary by its public_id.
    """
    def _destroy():
        return cloudinary.uploader.destroy(public_id, resource_type="image")

    try:
        if not public_id:
            return
        result = await asyncio.to_thread(_destroy)
        if result.get("result") != "ok":
            logger.warning(f"Cloudinary delete returned non-ok for '{public_id}': {result}")
    except Exception as e:
        logger.error(f"Cloudinary delete failed for '{public_id}': {e}")


async def delete_images(public_ids: list[str]) -> None:
    """Delete multiple images concurrently."""
    if not public_ids:
        return
    # Filter out any empty/missing IDs
    valid_ids = [pid for pid in public_ids if pid]
    if not valid_ids:
        return
    await asyncio.gather(*[delete_image(pid) for pid in valid_ids])
