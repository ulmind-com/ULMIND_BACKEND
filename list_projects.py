import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv

load_dotenv()

async def main():
    client = AsyncIOMotorClient(os.getenv("MONGO_URI"))
    db = client["ulmind"]
    projects = await db.projects.find().to_list(100)
    for p in projects:
        print(f"ID: {p.get('_id')} Name: {p.get('name')} Project_ID: {p.get('project_id')}")
    print(f"Total projects: {len(projects)}")

asyncio.run(main())
