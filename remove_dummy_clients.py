from pymongo import MongoClient

def remove_dummy_clients():
    client = MongoClient("mongodb+srv://samiran:samiran2004@cluster2004.eowyegm.mongodb.net/ulmind")
    db = client.get_database("ulmind")
    clients_coll = db.get_collection("clients")
    
    # Delete all clients where contactEmail ends with @example.com
    # as well as any other known dummy ones if necessary.
    result = clients_coll.delete_many({
        "contactEmail": {"$regex": "@example\\.com$"}
    })
    
    print(f"Deleted {result.deleted_count} dummy clients from the database.")

if __name__ == "__main__":
    remove_dummy_clients()
