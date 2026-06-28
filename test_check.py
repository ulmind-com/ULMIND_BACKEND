import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import certifi

async def main():
    client = AsyncIOMotorClient("mongodb+srv://samiran:samiran2004@cluster2004.eowyegm.mongodb.net/ulmind", tlsCAFile=certifi.where())
    db = client.get_database()
    
    # Check existing team members (admins)
    admins = await db["admins"].find({}, {"password": 0, "hashed_password": 0}).to_list(100)
    print(f"=== ADMINS ({len(admins)}) ===")
    for a in admins:
        print(f"  {a.get('full_name', 'N/A')} | {a.get('email', 'N/A')} | role={a.get('role', 'N/A')} | status={a.get('status', 'N/A')} | id={a['_id']}")
    
    # Check existing projects
    projects = await db["projects"].find({}).to_list(100)
    print(f"\n=== PROJECTS ({len(projects)}) ===")
    for p in projects:
        print(f"  {p.get('name', 'N/A')} | status={p.get('status', 'N/A')} | id={p['_id']}")
    
    # Check existing tasks
    tasks = await db["tasks"].find({}).to_list(100)
    print(f"\n=== TASKS ({len(tasks)}) ===")
    for t in tasks:
        print(f"  {t.get('title', 'N/A')} | status={t.get('status', 'N/A')} | assigned_to={t.get('assigned_to', 'N/A')} | id={t['_id']}")
    
    # Check PM tasks  
    pm_tasks = await db["pm_tasks"].find({}).to_list(100)
    print(f"\n=== PM_TASKS ({len(pm_tasks)}) ===")
    for t in pm_tasks:
        print(f"  {t.get('title', 'N/A')} | status={t.get('status', 'N/A')} | assigned_to={t.get('assigned_to', 'N/A')} | id={t['_id']}")
    
    # Check team attendance, work logs, performance, leaves, payroll
    for coll in ["team_attendance", "team_work_logs", "team_performance", "team_leaves", "team_payroll"]:
        count = await db[coll].count_documents({})
        print(f"\n{coll}: {count} records")
    
    client.close()

asyncio.run(main())
