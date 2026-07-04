import asyncio
from app.db.database import connect_to_mongo, close_mongo_connection, db

async def main():
    connect_to_mongo()
    db_instance = db.db
    
    await db_instance["test_inc"].insert_one({"_id": 1, "val": 0})
    
    update_op = {"$set": {"updated": True}, "$inc": {}}
    
    try:
        await db_instance["test_inc"].update_one({"_id": 1}, update_op)
        print("Success")
    except Exception as e:
        print(f"Error: {e}")
        
    await db_instance["test_inc"].drop()
    close_mongo_connection()

if __name__ == "__main__":
    asyncio.run(main())
