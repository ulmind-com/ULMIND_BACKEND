import asyncio
import os
import sys
from datetime import datetime, timezone

# Add parent directory to sys.path so we can import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.db.database import connect_to_mongo, close_mongo_connection, db

async def patch_collection(name: str):
    print(f"--- Patching collection: {name} ---")
    now = datetime.now(timezone.utc)
    
    # Find documents missing created_at or updated_at
    filter_query = {
        "$or": [
            {"created_at": {"$exists": False}},
            {"updated_at": {"$exists": False}}
        ]
    }
    
    cursor = db.db[name].find(filter_query)
    count = 0
    
    async for doc in cursor:
        update_fields = {}
        if "created_at" not in doc:
            update_fields["created_at"] = doc.get("_id").generation_time if hasattr(doc.get("_id"), "generation_time") else now
        if "updated_at" not in doc:
            update_fields["updated_at"] = now
            
        if update_fields:
            await db.db[name].update_one({"_id": doc["_id"]}, {"$set": update_fields})
            count += 1
            
    print(f"Patched {count} documents in {name}.")

async def run_migration():
    connect_to_mongo()
    
    collections = ["admins", "projects", "merchandise", "clients", "credentials"]
    
    for collection in collections:
        await patch_collection(collection)
        
    print("\nMigration complete.")
    close_mongo_connection()

if __name__ == "__main__":
    asyncio.run(run_migration())
