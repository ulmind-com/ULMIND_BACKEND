import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from app.core.encryption import decrypt_value, get_encryption_key
import os

async def main():
    print(f"Encryption Key (Base64): {get_encryption_key()}")
    print(f"JWT_SECRET used: {os.getenv('JWT_SECRET', 'super-secret-key-fallback')}")
    client = AsyncIOMotorClient("mongodb+srv://samiran:samiran2004@cluster2004.eowyegm.mongodb.net/ulmind")
    db = client.get_database()
    env_stores = await db.env_store.find().to_list(10)
    for store in env_stores:
        print(f"Project: {store.get('project_name')}")
        encrypted_content = store.get('env_content', '')
        print(f"Encrypted content preview: {encrypted_content[:50]}")
        decrypted = decrypt_value(encrypted_content)
        print(f"Decrypted: {decrypted[:50]}...\n")

asyncio.run(main())
