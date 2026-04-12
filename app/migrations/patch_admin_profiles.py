import asyncio
import os
import sys
from datetime import datetime, timezone

# Add parent directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.db.database import connect_to_mongo, close_mongo_connection, db

async def patch_admins():
    print("--- Patching Admins Profiles ---")
    now = datetime.now(timezone.utc)
    
    # Check all admins
    cursor = db.db["admins"].find({})
    count = 0
    
    async for doc in cursor:
        update_fields = {}
        
        # 1. Handle missing full_name
        if not doc.get("full_name"):
            # Use email name part as default full_name
            email = doc.get("email", "Admin")
            name_part = email.split("@")[0].title().replace(".", " ").replace("_", " ")
            update_fields["full_name"] = name_part
            
        # 2. Handle specialization migration (str -> List[str])
        spec = doc.get("specialization")
        if spec is None:
            update_fields["specialization"] = []
        elif isinstance(spec, str):
            # Convert single string to a list with one item
            update_fields["specialization"] = [spec]
            
        # 3. Handle position, experience, socials (optional fields)
        # We ensure they exist as None if missing to avoid potential future crashes
        for field in ["position", "experience", "linkedin_url", "x_url", "github_url"]:
            if field not in doc:
                update_fields[field] = None

        if update_fields:
            await db.db["admins"].update_one({"_id": doc["_id"]}, {"$set": update_fields})
            count += 1
            print(f"Updated Admin: {doc.get('email', 'Unknown')} with {list(update_fields.keys())}")
            
    print(f"\nPatched {count} admin records.")

async def run_migration():
    connect_to_mongo()
    await patch_admins()
    print("\nMigration complete.")
    close_mongo_connection()

if __name__ == "__main__":
    asyncio.run(run_migration())
