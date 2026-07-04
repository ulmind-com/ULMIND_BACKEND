import asyncio
from app.db.database import connect_to_mongo, close_mongo_connection, db

async def main():
    connect_to_mongo()
    session = await db.db["hw_sessions"].find_one({"employee_id": "UL-002", "status": "active"})
    print("Session:")
    print(session)

    close_mongo_connection()

if __name__ == "__main__":
    asyncio.run(main())
