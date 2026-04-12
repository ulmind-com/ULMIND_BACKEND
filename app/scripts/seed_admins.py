import asyncio
import os
import sys
from datetime import datetime, timezone

# Add parent directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.db.database import connect_to_mongo, close_mongo_connection, db
from app.core.security import get_password_hash

async def seed_data():
    print("--- 🗑️  Clearing Existing Admin Data ---")
    
    # 1. Connect to MongoDB
    connect_to_mongo()
    
    # 2. Drop or clear the admins collection
    # Using delete_many({}) to keep the collection structure/indexes if any
    del_res = await db.db["admins"].delete_many({})
    print(f"Deleted {del_res.deleted_count} admins.")
    
    print("\n--- 🌱 Seeding Super-Admin ---")
    
    # 3. New Super-Admin Data
    seed_password = "Admin@12345678"
    hashed_pass = get_password_hash(seed_password)
    now = datetime.now(timezone.utc)
    
    super_admin = {
        "full_name": "System Super Admin",
        "email": "admin@ulmind.com",
        "password": hashed_pass,
        "role": "admin",
        "status": "Active",
        "must_change_password": True,
        "position": "CEO & Founder",
        "experience": "10+ Years",
        "specialization": ["System Architecture", "Security", "Team Leadership"],
        "created_at": now,
        "updated_at": now,
        "linkedin_url": None,
        "x_url": None,
        "github_url": None
    }
    
    # 4. Insert
    ins_res = await db.db["admins"].insert_one(super_admin)
    print(f"✅ Created Super Admin with ID: {ins_res.inserted_id}")
    print(f"📧 Email: admin@ulmind.com")
    print(f"🔑 Password: {seed_password}")
    
    print("\n--- Database Re-Seeding Complete ---")
    close_mongo_connection()

if __name__ == "__main__":
    asyncio.run(seed_data())
