import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

async def main():
    client = AsyncIOMotorClient("mongodb+srv://samiran:samiran2004@cluster2004.eowyegm.mongodb.net/ulmind")
    db = client.get_database()
    collections = await db.list_collection_names()
    print("Collections:", collections)
    env_stores = await db.env_store.find().to_list(100)
    print("env_store count:", len(env_stores))
    
    # Check if there are env entries in other collections? Like `project_env`?
    project_envs = await db.project_env.find().to_list(100) if "project_env" in collections else []
    print("project_env count:", len(project_envs))
    
    # Or maybe it's named something else
    envs = await db.envs.find().to_list(100) if "envs" in collections else []
    print("envs count:", len(envs))

asyncio.run(main())
