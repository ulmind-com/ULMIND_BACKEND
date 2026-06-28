import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from cryptography.fernet import Fernet
import base64
import hashlib

def try_decrypt(encrypted_content, secret):
    digest = hashlib.sha256(secret.encode()).digest()
    key = base64.urlsafe_b64encode(digest)
    f = Fernet(key)
    try:
        return f.decrypt(encrypted_content.encode()).decode()
    except Exception:
        return None

async def main():
    client = AsyncIOMotorClient("mongodb+srv://samiran:samiran2004@cluster2004.eowyegm.mongodb.net/ulmind")
    db = client.get_database()
    env_stores = await db.env_store.find().to_list(1)
    if not env_stores:
        print("No entries.")
        return
        
    store = env_stores[0]
    encrypted_content = store.get('env_content', '')
    
    secrets_to_try = [
        "CHANGE_THIS_TO_A_STRONG_RANDOM_SECRET_BEFORE_PRODUCTION",
        "super-secret-key-fallback"
    ]
    
    for secret in secrets_to_try:
        dec = try_decrypt(encrypted_content, secret)
        if dec:
            print(f"SUCCESS with secret: {secret}")
            print(f"Decrypted preview: {dec[:50]}")
            return
    print("FAILED with all secrets.")

asyncio.run(main())
