import asyncio
from datetime import timezone
from app.db.database import connect_to_mongo, close_mongo_connection, db
from app.core.datetime_utils import get_now

async def main():
    connect_to_mongo()
    db_instance = db.db
    
    # Store now
    now_store = get_now()
    print(f"Storing: {now_store}")
    
    await db_instance["test_tz"].insert_one({"time": now_store})
    doc = await db_instance["test_tz"].find_one()
    
    read_time = doc["time"]
    print(f"Read: {read_time}")
    
    if read_time.tzinfo is None:
        read_time = read_time.replace(tzinfo=timezone.utc)
        
    print(f"Read replaced: {read_time}")
    
    now_read = get_now()
    print(f"Now: {now_read}")
    
    print(f"Diff: {(now_read - read_time).total_seconds()}")
    
    await db_instance["test_tz"].drop()
    close_mongo_connection()

if __name__ == "__main__":
    asyncio.run(main())
