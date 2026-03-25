from fastapi import APIRouter, Depends, HTTPException
from typing import List
from datetime import datetime, timezone
from bson import ObjectId
from app.db.database import get_db
from app.schemas.project import ProjectCreate, ProjectResponse, ProjectUpdate
from pydantic import BaseModel

router = APIRouter()

@router.get("/", response_model=List[ProjectResponse])
async def get_projects(db=Depends(get_db)):
    projects = await db["projects"].find({}).to_list(length=1000)
    return projects

@router.post("/", response_model=ProjectResponse, status_code=201)
async def create_project(project_in: ProjectCreate, db=Depends(get_db)):
    proj_dict = project_in.model_dump(exclude_unset=True)
    proj_dict["created_at"] = datetime.now(timezone.utc)
    proj_dict["updated_at"] = datetime.now(timezone.utc)
    
    result = await db["projects"].insert_one(proj_dict)
    
    created_project = await db["projects"].find_one({"_id": result.inserted_id})
    return created_project

class StatusUpdate(BaseModel):
    status: str

@router.put("/{id}/status", response_model=ProjectResponse)
async def update_project_status(id: str, status_update: StatusUpdate, db=Depends(get_db)):
    try:
        obj_id = ObjectId(id)
    except:
        raise HTTPException(status_code=400, detail="Invalid project ID format")
        
    result = await db["projects"].find_one_and_update(
        {"_id": obj_id},
        {"$set": {"status": status_update.status, "updated_at": datetime.now(timezone.utc)}},
        return_document=True
    )
    if not result:
        raise HTTPException(status_code=404, detail="Project not found")
    return result

@router.put("/{id}", response_model=ProjectResponse)
async def update_project(id: str, project_in: ProjectUpdate, db=Depends(get_db)):
    try:
        obj_id = ObjectId(id)
    except:
        raise HTTPException(status_code=400, detail="Invalid project ID format")
        
    update_data = project_in.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No data to update")
        
    update_data["updated_at"] = datetime.now(timezone.utc)
        
    result = await db["projects"].find_one_and_update(
        {"_id": obj_id},
        {"$set": update_data},
        return_document=True
    )
    
    if not result:
        raise HTTPException(status_code=404, detail="Project not found")
    return result

@router.delete("/{id}")
async def delete_project(id: str, db=Depends(get_db)):
    try:
        obj_id = ObjectId(id)
    except:
        raise HTTPException(status_code=400, detail="Invalid project ID format")
        
    result = await db["projects"].delete_one({"_id": obj_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Project not found")
        
    return {"message": "Project successfully deleted"}
