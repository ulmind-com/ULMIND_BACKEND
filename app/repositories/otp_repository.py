"""
OTP Repository
Raw MongoDB operations for the password_reset_otps collection.
Follows the same Motor pattern used throughout the project (raw dict, get_db).
"""
from datetime import datetime, timezone
from bson import ObjectId
from app.db.database import get_db


COLLECTION = "password_reset_otps"


async def create_otp(db, email: str, otp_hash: str, expires_at: datetime) -> str:
    """Insert a new OTP record. Returns the inserted document ID."""
    doc = {
        "email": email,
        "otp_hash": otp_hash,
        "expires_at": expires_at,
        "used": False,
        "verify_attempts": 0,
        "created_at": datetime.now(timezone.utc),
    }
    result = await db[COLLECTION].insert_one(doc)
    return str(result.inserted_id)


async def find_latest_otp(db, email: str) -> dict | None:
    """Return the most recent unused OTP for an email, sorted newest first."""
    return await db[COLLECTION].find_one(
        {"email": email, "used": False},
        sort=[("created_at", -1)],
    )


async def increment_attempts(db, otp_id: str) -> None:
    """Increment the verify_attempts counter for an OTP."""
    await db[COLLECTION].update_one(
        {"_id": ObjectId(otp_id)},
        {"$inc": {"verify_attempts": 1}},
    )


async def mark_otp_used(db, otp_id: str) -> None:
    """Mark an OTP record as consumed so it cannot be reused."""
    await db[COLLECTION].update_one(
        {"_id": ObjectId(otp_id)},
        {"$set": {"used": True}},
    )


async def count_recent_requests(db, email: str, since: datetime) -> int:
    """Count how many OTP requests have been made for an email since a given time."""
    return await db[COLLECTION].count_documents(
        {"email": email, "created_at": {"$gte": since}}
    )


async def count_recent_ip_requests(db, ip: str, since: datetime) -> int:
    """Count how many OTP requests have been made from an IP since a given time."""
    return await db[COLLECTION].count_documents(
        {"request_ip": ip, "created_at": {"$gte": since}}
    )


async def create_otp_with_ip(
    db, email: str, otp_hash: str, expires_at: datetime, request_ip: str
) -> str:
    """Insert OTP record including the requester's IP for rate limiting."""
    doc = {
        "email": email,
        "otp_hash": otp_hash,
        "expires_at": expires_at,
        "used": False,
        "verify_attempts": 0,
        "request_ip": request_ip,
        "created_at": datetime.now(timezone.utc),
    }
    result = await db[COLLECTION].insert_one(doc)
    return str(result.inserted_id)
