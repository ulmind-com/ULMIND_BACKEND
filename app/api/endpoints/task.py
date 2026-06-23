from fastapi import APIRouter, Depends, HTTPException
from typing import List
from app.core.datetime_utils import get_now
from bson import ObjectId
from app.db.database import get_db
from app.api.deps import get_current_active_admin
from app.schemas.task import TaskCreate, TaskUpdate, TaskInDB

router = APIRouter()

def _parse_id(id: str) -> ObjectId:
    try:
        return ObjectId(id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ID format")

@router.get("/", response_model=List[TaskInDB])
async def list_tasks(project_id: str = None, db=Depends(get_db), _admin=Depends(get_current_active_admin)):
    query = {}
    if project_id:
        query["project_id"] = project_id
    tasks = await db["tasks"].find(query).to_list(length=1000)
    return tasks

@router.post("/", response_model=TaskInDB, status_code=201)
async def create_task(task_in: TaskCreate, db=Depends(get_db), _admin=Depends(get_current_active_admin)):
    now = get_now()
    doc = task_in.model_dump()
    doc.update({
        "comments": [],
        "created_at": now,
        "updated_at": now
    })
    result = await db["tasks"].insert_one(doc)
    created = await db["tasks"].find_one({"_id": result.inserted_id})
    return created

@router.put("/{id}", response_model=TaskInDB)
async def update_task(id: str, task_in: TaskUpdate, db=Depends(get_db), _admin=Depends(get_current_active_admin)):
    update_data = task_in.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields provided for update")
    update_data["updated_at"] = get_now()
    result = await db["tasks"].find_one_and_update(
        {"_id": _parse_id(id)},
        {"$set": update_data},
        return_document=True
    )
    if not result:
        raise HTTPException(status_code=404, detail="Task not found")
    return result

@router.delete("/{id}")
async def delete_task(id: str, db=Depends(get_db), _admin=Depends(get_current_active_admin)):
    result = await db["tasks"].delete_one({"_id": _parse_id(id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"status": "success", "message": "Task deleted"}
