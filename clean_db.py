import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()

async def clean_database():
    print("Connecting to DB...")
    client = AsyncIOMotorClient(os.getenv("MONGO_URI"))
    db = client["ulmind"]
    
    print("Dropping projects collection...")
    await db.projects.drop()
    
    print("Dropping tasks collection...")
    await db.tasks.drop()
    
    print("Resetting project_id and task_id counters...")
    await db.counters.delete_many({"_id": {"$in": ["project_id", "task_id"]}})
    
    print("Cleanup successful. New projects will start at PROJ-UL-001.")

if __name__ == "__main__":
    asyncio.run(clean_database())
