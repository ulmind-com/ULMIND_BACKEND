import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import certifi

async def main():
    client = AsyncIOMotorClient("mongodb+srv://samiran:samiran2004@cluster2004.eowyegm.mongodb.net/ulmind", tlsCAFile=certifi.where())
    db = client.get_database()
    
    admins = await db["admins"].find({}, {"password": 0, "hashed_password": 0}).to_list(100)
    print(f"=== ADMINS ({len(admins)}) ===")
    for a in admins:
        print(f"  name={a.get('full_name', 'N/A')} | email={a.get('email', 'N/A')} | role={a.get('role', 'N/A')} | status={a.get('status', 'N/A')} | id={a['_id']}")
    
    projects = await db["projects"].find({}, {"env_vars": 0, "deployments": 0}).to_list(100)
    print(f"\n=== PROJECTS ({len(projects)}) ===")
    for p in projects:
        print(f"  name={p.get('name', 'N/A')} | status={p.get('status', 'N/A')} | id={p['_id']}")
    
    client.close()

asyncio.run(main())
