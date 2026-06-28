import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()

async def update_phones():
    uri = os.getenv("MONGO_URI", "mongodb+srv://arnabsenapati:arnab123@cluster0.p711c1q.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
    client = AsyncIOMotorClient(uri)
    # The config uses the default DB provided in the URI
    db = client.get_default_database()
    
    # Phone mapping
    phones = {
        "Soumyajit": "7908288829",
        "Arnab": "7384708532",
        "Sagnik": "8389802690",
        "Tirtha": "8348267151",
        "Swastika": "8092681269"
    }
    
    for name, phone in phones.items():
        result = await db.admins.update_many(
            {"full_name": {"$regex": name, "$options": "i"}},
            {"$set": {"phone": phone}}
        )
        print(f"Updated {result.modified_count} records for {name} with phone {phone}")

if __name__ == "__main__":
    asyncio.run(update_phones())
