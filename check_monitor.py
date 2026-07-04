import asyncio
from app.db.database import connect_to_mongo, close_mongo_connection, db

async def main():
    connect_to_mongo()
    db_instance = db.db
    
    employees = await db_instance["hw_employees"].find({}).to_list(100)
    print("Employees:")
    for e in employees:
        print(f"- {e['name']} (_id: {e['_id']}, emp_id: {e.get('employee_id')}, status: {e.get('status')})")
        
    sessions = await db_instance["hw_sessions"].find({}).to_list(100)
    print("\nSessions:")
    for s in sessions:
        print(f"- {s.get('employee_name')} (db_id: {s.get('employee_db_id')}, status: {s.get('status')})")
        
    live = await db_instance["hw_live_status"].find({}).to_list(100)
    print("\nLive Status:")
    for l in live:
        print(f"- {l.get('employee_id')}: status={l.get('status')}, last_heartbeat={l.get('last_heartbeat')}")

    close_mongo_connection()

if __name__ == "__main__":
    asyncio.run(main())
