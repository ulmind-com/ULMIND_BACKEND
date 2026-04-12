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
    print("--- 🗑️  Clearing Existing Admin Data ---")
    connect_to_mongo()
    
    # 1. Clear existing admins
    await db.db["admins"].delete_many({})
    
    hashed = get_password_hash(INITIAL_PASSWORD)
    now = datetime.now(timezone.utc)
    
    print(f"--- 🌱 Seeding {len(ADMIN_EMAILS)} Admins ---")
    
    for email in ADMIN_EMAILS:
        # Derive full_name from email
        name_part = email.split("@")[0].title().replace(".", " ").replace("_", " ")
        
        new_admin = {
            "full_name": name_part,
            "email": email,
            "password": hashed,
            "role": "admin",
            "must_change_password": True,
            "status": "Active",
            "position": None,
            "experience": None,
            "specialization": [],
            "linkedin_url": None,
            "x_url": None,
            "github_url": None,
            "created_at": now,
            "updated_at": now
        }
        await db.db["admins"].insert_one(new_admin)
        print(f"CREATED: {email} (ID: {name_part})")
        
    print("\n✅ Reset and Seeding complete.")
    close_mongo_connection()

if __name__ == "__main__":
    asyncio.run(seed())
