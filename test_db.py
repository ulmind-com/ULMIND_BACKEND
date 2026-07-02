import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import json
from bson import ObjectId

async def main():
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    db = client["ulmind_db"]
    sessions = await db["hw_sessions"].find({"employee_id": "UL-002"}).sort("login_time", -1).limit(1).to_list(1)
    if sessions:
        s = sessions[0]
        print(f"Session ID: {s['_id']}")
        print(f"total_active_seconds: {s.get('total_active_seconds')}")
        print(f"face_present_seconds: {s.get('face_present_seconds')}")
    else:
        print("No sessions found")

asyncio.run(main())
