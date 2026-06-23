import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

from app.db.database import connect_to_mongo, close_mongo_connection, db

async def update_roles():
    connect_to_mongo()
    database = db.db
    
    # Keep arnab.senapati@ulmind.com as super_admin, others become editor
    result = await database["admins"].update_many(
        {"email": {"$ne": "arnab.senapati@ulmind.com"}},
        {"$set": {"role": "editor"}}
    )
    
    print(f"Matched {result.matched_count} admins, updated {result.modified_count} admins to 'editor' role.")
    
    close_mongo_connection()

if __name__ == "__main__":
    asyncio.run(update_roles())
