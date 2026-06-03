import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

async def main():
    client = AsyncIOMotorClient("mongodb+srv://admin:ulmind@cluster0.ulmind.mongodb.net/?retryWrites=true&w=majority")
    db = client.get_default_database()
    admins = await db["admins"].find().to_list(10)
    for a in admins:
        print(f"{a['email']} - {a['role']}")

asyncio.run(main())
