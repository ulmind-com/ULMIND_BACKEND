from pymongo import MongoClient

def fix_clients():
    client = MongoClient("mongodb+srv://samiran:samiran2004@cluster2004.eowyegm.mongodb.net/ulmind")
    db = client.get_database("ulmind")
    clients_coll = db.get_collection("clients")
    
    clients = clients_coll.find({})
    
    updated = 0
    for c in clients:
        updates = {}
        
        # If 'companyName' doesn't exist but 'company' does, rename it to companyName
        if "companyName" not in c and "company" in c:
            updates["companyName"] = c["company"]
            
        # Or if 'name' exists but 'company' does not, use 'name' as companyName
        elif "companyName" not in c and "name" in c:
            updates["companyName"] = c["name"]
            
        if "contactEmail" not in c and "email" in c:
            updates["contactEmail"] = c["email"]
            
        if updates:
            clients_coll.update_one({"_id": c["_id"]}, {"$set": updates})
            updated += 1
            
    print(f"Updated {updated} clients")

if __name__ == "__main__":
    fix_clients()
