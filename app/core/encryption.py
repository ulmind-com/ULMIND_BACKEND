import os
from cryptography.fernet import Fernet
import base64
import hashlib
from app.core.config import settings

def get_encryption_key() -> bytes:
    """Generate a consistent 32-url-safe-base64 key from JWT_SECRET or fallback."""
    secret = settings.JWT_SECRET or "super-secret-key-fallback"
    # Hash it to 32 bytes and base64 encode for Fernet
    digest = hashlib.sha256(secret.encode()).digest()
    return base64.urlsafe_b64encode(digest)

_fernet = Fernet(get_encryption_key())

def encrypt_value(value: str) -> str:
    if not value:
        return value
    return _fernet.encrypt(value.encode()).decode()

def decrypt_value(encrypted_value: str) -> str:
    if not encrypted_value:
        return encrypted_value
    try:
        return _fernet.decrypt(encrypted_value.encode()).decode()
    except Exception:
        # If decryption fails (e.g., key changed or not encrypted), return masked or original
        return "[Decryption Failed]"
