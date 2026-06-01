"""
Migration: Add indexes to password_reset_otps collection
Run once: python -m app.migrations.add_otp_indexes

Creates:
  1. TTL index on expires_at (auto-delete OTP docs 24h after expiry)
  2. Compound index on email + created_at (for rate-limit queries)
  3. Index on request_ip + created_at (for IP rate-limit queries)
"""
import asyncio
import logging
from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

COLLECTION = "password_reset_otps"


async def run():
    client = AsyncIOMotorClient(settings.MONGO_URI)
    db = client.get_default_database()
    col = db[COLLECTION]

    # 1. TTL index — auto-purge OTP docs 24 hours after expiry (86400 seconds)
    await col.create_index(
        "expires_at",
        expireAfterSeconds=86400,
        name="ttl_expires_at",
    )
    logger.info("Created TTL index on expires_at")

    # 2. Compound index for per-email rate limiting
    await col.create_index(
        [("email", 1), ("created_at", -1)],
        name="idx_email_created_at",
    )
    logger.info("Created compound index on email + created_at")

    # 3. Compound index for per-IP rate limiting
    await col.create_index(
        [("request_ip", 1), ("created_at", -1)],
        name="idx_ip_created_at",
    )
    logger.info("Created compound index on request_ip + created_at")

    client.close()
    logger.info("Migration complete — all OTP indexes created.")


if __name__ == "__main__":
    asyncio.run(run())
