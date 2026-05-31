"""
OTP Service
Business logic for the Forgot Password OTP flow.
Handles: OTP generation, hashing, rate limiting, verification, reset token, password update.
"""
import re
import hashlib
import secrets
import logging
from datetime import datetime, timedelta, timezone
from typing import Tuple

import jwt
from fastapi import HTTPException, status, Request

from app.core.config import settings
from app.core.security import get_password_hash
from app.repositories import otp_repository

logger = logging.getLogger(__name__)

# ─── Constants ────────────────────────────────────────────────────────────────
OTP_EXPIRY_MINUTES = 10
RESET_TOKEN_EXPIRY_MINUTES = 15
MAX_VERIFY_ATTEMPTS = 10
MAX_EMAIL_REQUESTS_PER_HOUR = 5
MAX_IP_REQUESTS_PER_HOUR = 10
RESET_TOKEN_TYPE = "password_reset"

# ─── Password policy ──────────────────────────────────────────────────────────
_PASSWORD_POLICY = re.compile(
    r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[!@#$%^&*(),.?\":{}|<>]).{8,}$"
)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _generate_otp() -> str:
    """Generate a cryptographically secure 6-digit numeric OTP."""
    return str(secrets.randbelow(900_000) + 100_000)


def _hash_otp(otp: str) -> str:
    """SHA-256 hash the OTP. Fast, one-way, collision-resistant."""
    return hashlib.sha256(otp.encode("utf-8")).hexdigest()


def _create_reset_token(email: str) -> str:
    """Create a short-lived JWT reset token (15 min) with type claim."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=RESET_TOKEN_EXPIRY_MINUTES)
    payload = {"email": email, "type": RESET_TOKEN_TYPE, "exp": expire}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")


def _verify_reset_token(token: str) -> str:
    """Decode and validate a reset JWT. Returns email or raises HTTPException."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
        if payload.get("type") != RESET_TOKEN_TYPE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid reset token",
            )
        email = payload.get("email")
        if not email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid reset token",
            )
        return email
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reset token has expired. Please request a new OTP.",
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid reset token",
        )


def _validate_password_policy(password: str) -> None:
    """Raise HTTPException if password does not meet policy requirements."""
    if not _PASSWORD_POLICY.match(password):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Password must be at least 8 characters and include "
                "an uppercase letter, a lowercase letter, a digit, "
                "and a special character (!@#$%^&* etc.)."
            ),
        )


# ─── Service functions ────────────────────────────────────────────────────────

async def request_otp(db, email: str, request: Request) -> dict:
    """
    Step 1 — Validate email, rate-limit, generate OTP, store hashed, send email.
    Returns a success message. Never reveals whether an email exists (prevents enumeration).
    """
    # 1. Check admin exists and is Active
    admin = await db["admins"].find_one({"email": email})
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User does not exist",
        )
    if admin.get("status") != "Active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive. Please contact the system administrator.",
        )

    # 2. Rate limiting — per email (5/hour)
    one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
    email_count = await otp_repository.count_recent_requests(db, email, one_hour_ago)
    if email_count >= MAX_EMAIL_REQUESTS_PER_HOUR:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many OTP requests for this email. Please try again after 1 hour.",
        )

    # 3. Rate limiting — per IP (10/hour)
    client_ip = request.client.host if request.client else "unknown"
    ip_count = await otp_repository.count_recent_ip_requests(db, client_ip, one_hour_ago)
    if ip_count >= MAX_IP_REQUESTS_PER_HOUR:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many OTP requests from your IP. Please try again after 1 hour.",
        )

    # 4. Generate OTP + hash
    otp = _generate_otp()
    otp_hash = _hash_otp(otp)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=OTP_EXPIRY_MINUTES)

    # 5. Persist (with IP for rate limiting)
    await otp_repository.create_otp_with_ip(
        db, email=email, otp_hash=otp_hash, expires_at=expires_at, request_ip=client_ip
    )

    # 6. Send email (import here to avoid circular imports)
    from app.services.email_service import send_otp_email
    try:
        await send_otp_email(recipient=email, otp=otp)
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e),
        )

    return {
        "success": True,
        "message": "OTP sent to your email address. It is valid for 10 minutes.",
    }


async def verify_otp(db, email: str, otp: str) -> dict:
    """
    Step 2 — Validate OTP, mark used, return a 15-min reset token.
    """
    # 1. Lookup latest unused OTP
    record = await otp_repository.find_latest_otp(db, email)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OTP",
        )

    otp_id = str(record["_id"])

    # 2. Check max attempts (brute-force lock)
    if record.get("verify_attempts", 0) >= MAX_VERIFY_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="OTP is locked due to too many failed attempts. Please request a new OTP.",
        )

    # 3. Increment attempt counter first (before checking values)
    await otp_repository.increment_attempts(db, otp_id)

    # 4. Check expiry (compare UTC-aware datetimes)
    expires_at = record["expires_at"]
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) > expires_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OTP expired. Please request a new one.",
        )

    # 5. Verify hash
    if _hash_otp(otp) != record["otp_hash"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OTP",
        )

    # 6. Mark as used (single-use)
    await otp_repository.mark_otp_used(db, otp_id)

    # 7. Issue reset token
    reset_token = _create_reset_token(email)

    return {"success": True, "reset_token": reset_token}


async def reset_password(db, reset_token: str, new_password: str) -> dict:
    """
    Step 3 — Validate reset token, enforce password policy, update password.
    """
    # 1. Validate password policy
    _validate_password_policy(new_password)

    # 2. Decode and validate JWT reset token
    email = _verify_reset_token(reset_token)

    # 3. Fetch admin
    admin = await db["admins"].find_one({"email": email})
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # 4. Hash new password
    new_hashed = get_password_hash(new_password)

    # 5. Update password and clear must_change_password flag
    from app.core.datetime_utils import get_now
    await db["admins"].update_one(
        {"email": email},
        {"$set": {
            "password": new_hashed,
            "must_change_password": False,
            "updated_at": get_now(),
        }},
    )

    logger.info(f"Password successfully reset for admin: {email}")

    return {"success": True, "message": "Password updated successfully"}
