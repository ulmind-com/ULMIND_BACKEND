import asyncio
from datetime import timezone
from app.db.database import connect_to_mongo, close_mongo_connection, db
from app.core.datetime_utils import get_now

async def main():
    connect_to_mongo()
    db_instance = db.db
    
    live = await db_instance["hw_live_status"].find_one({"employee_id": "UL-002"})
    session = await db_instance["hw_sessions"].find_one({"employee_id": "UL-002", "status": "active"})
    
    now = get_now()
    print(f"Now (IST): {now}")
    
    if session:
        login_time = session["login_time"]
        if login_time.tzinfo is None:
            login_time = login_time.replace(tzinfo=timezone.utc)
        print(f"Login Time: {login_time}")
        print(f"Duration: {(now - login_time).total_seconds()}")
        
        hb = None
        if live and live.get("last_heartbeat"):
            hb = live["last_heartbeat"]
        else:
            hb = session["login_time"]
            
        print(f"HB DB value: {hb}")
        if hb and hb.tzinfo is None:
            hb = hb.replace(tzinfo=timezone.utc)
        print(f"HB with tz: {hb}")
        
        diff = (now - hb).total_seconds()
        print(f"Diff: {diff} seconds")
        print(f"Is Stale: {diff > 45}")

    close_mongo_connection()

if __name__ == "__main__":
    asyncio.run(main())
