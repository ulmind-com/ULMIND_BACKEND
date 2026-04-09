import asyncio
from datetime import datetime, timezone
from app.db.database import connect_to_mongo, close_mongo_connection, db
from app.core.security import get_password_hash

ADMIN_EMAILS = [
    'soumyajit.banerjee@ulmind.com',
    'arnab.senapati@ulmind.com',
    'samiran.samanta@ulmind.com',
    'sagnik.mondal@ulmind.com',
    'thirtha.ghosh@ulmind.in',
    'swastika.roy@ulmind.in',
    'roni.routh@ulmind.in',
]

INITIAL_PASSWORD = 'ulmind@123'

async def seed():
    connect_to_mongo()
    hashed = get_password_hash(INITIAL_PASSWORD)
    now = datetime.now(timezone.utc)
    
    for email in ADMIN_EMAILS:
        existing = await db.db["admins"].find_one({"email": email})
        if existing:
            print(f"SKIP: Admin already exists -> {email}")
            continue
            
        new_admin = {
            "email": email,
            "password": hashed,
            "role": "admin",
            "must_change_password": True,
            "status": "Active",
            "created_at": now,
            "updated_at": now
        }
        await db.db["admins"].insert_one(new_admin)
        print(f"CREATED: {email}")
        
    print("\nSeeding complete.")
    close_mongo_connection()

if __name__ == "__main__":
    asyncio.run(seed())
