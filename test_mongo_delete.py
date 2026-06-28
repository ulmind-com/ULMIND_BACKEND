from pymongo import MongoClient

client = MongoClient("mongodb+srv://samiran:samiran2004@cluster2004.eowyegm.mongodb.net/ulmind")
db = client["ulmind"]

# Delete all tasks with title "Develop feature X" across all statuses
result = db["pm_tasks"].delete_many({"title": "Develop feature X"})
print(f"Deleted {result.deleted_count} dummy tasks from the entire Kanban board.")
