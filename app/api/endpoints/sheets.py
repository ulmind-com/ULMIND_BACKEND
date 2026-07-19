from fastapi import APIRouter, Depends, HTTPException, Body
from typing import List, Dict, Any
from bson import ObjectId
from datetime import datetime
from app.db.database import get_db
from app.models.sheets import SheetCreate, SheetColumn, SheetRowCreate

router = APIRouter()

def serialize_mongo(doc):
    if doc and "_id" in doc:
        doc["_id"] = str(doc["_id"])
    return doc

@router.post("/", response_model=Dict[str, Any])
async def create_sheet(sheet: SheetCreate, db=Depends(get_db)):
    doc = sheet.model_dump()
    doc["columns"] = [c.model_dump() for c in sheet.columns] if sheet.columns else []
    doc["created_at"] = datetime.utcnow()
    doc["updated_at"] = datetime.utcnow()
    
    result = await db.sheets.insert_one(doc)
    created = await db.sheets.find_one({"_id": result.inserted_id})
    return serialize_mongo(created)

@router.get("/", response_model=List[Dict[str, Any]])
async def get_sheets(db=Depends(get_db)):
    sheets = await db.sheets.find().to_list(100)
    return [serialize_mongo(s) for s in sheets]

@router.get("/{sheet_id}", response_model=Dict[str, Any])
async def get_sheet(sheet_id: str, db=Depends(get_db)):
    sheet = await db.sheets.find_one({"_id": ObjectId(sheet_id)})
    if not sheet:
        raise HTTPException(status_code=404, detail="Sheet not found")
    return serialize_mongo(sheet)

@router.put("/{sheet_id}/columns", response_model=Dict[str, Any])
async def update_columns(sheet_id: str, columns: List[SheetColumn], db=Depends(get_db)):
    sheet = await db.sheets.find_one({"_id": ObjectId(sheet_id)})
    if not sheet:
        raise HTTPException(status_code=404, detail="Sheet not found")
    
    col_dicts = [c.model_dump() for c in columns]
    await db.sheets.update_one(
        {"_id": ObjectId(sheet_id)},
        {"$set": {"columns": col_dicts, "updated_at": datetime.utcnow()}}
    )
    updated = await db.sheets.find_one({"_id": ObjectId(sheet_id)})
    return serialize_mongo(updated)

@router.post("/{sheet_id}/rows", response_model=Dict[str, Any])
async def add_row(sheet_id: str, row: SheetRowCreate, db=Depends(get_db)):
    sheet = await db.sheets.find_one({"_id": ObjectId(sheet_id)})
    if not sheet:
        raise HTTPException(status_code=404, detail="Sheet not found")
    
    doc = row.model_dump()
    doc["sheet_id"] = sheet_id
    doc["created_at"] = datetime.utcnow()
    doc["updated_at"] = datetime.utcnow()
    
    result = await db.sheet_rows.insert_one(doc)
    created = await db.sheet_rows.find_one({"_id": result.inserted_id})
    return serialize_mongo(created)

@router.post("/{sheet_id}/rows/bulk", response_model=Dict[str, Any])
async def bulk_add_rows(sheet_id: str, rows: List[SheetRowCreate], db=Depends(get_db)):
    sheet = await db.sheets.find_one({"_id": ObjectId(sheet_id)})
    if not sheet:
        raise HTTPException(status_code=404, detail="Sheet not found")
    
    docs = []
    now = datetime.utcnow()
    for row in rows:
        doc = row.model_dump()
        doc["sheet_id"] = sheet_id
        doc["created_at"] = now
        doc["updated_at"] = now
        docs.append(doc)
        
    if docs:
        result = await db.sheet_rows.insert_many(docs)
        return {"status": "success", "inserted": len(result.inserted_ids)}
    return {"status": "success", "inserted": 0}

@router.get("/{sheet_id}/rows", response_model=List[Dict[str, Any]])
async def get_rows(sheet_id: str, db=Depends(get_db)):
    rows = await db.sheet_rows.find({"sheet_id": sheet_id}).sort("created_at", 1).to_list(1000)
    # Sort by sl_no numerically if the field exists in the data
    def _sl_no_key(row):
        try:
            return int(float(row.get("data", {}).get("sl_no", 0) or 0))
        except (ValueError, TypeError):
            return 0
    if rows and rows[0].get("data", {}).get("sl_no") is not None:
        rows.sort(key=_sl_no_key)
    return [serialize_mongo(r) for r in rows]

@router.put("/{sheet_id}/rows/{row_id}", response_model=Dict[str, Any])
async def update_row(sheet_id: str, row_id: str, payload: Dict[str, Any] = Body(...), db=Depends(get_db)):
    update_doc = {"updated_at": datetime.utcnow()}
    if "data" in payload:
        update_doc["data"] = payload["data"]
    if "styles" in payload:
        update_doc["styles"] = payload["styles"]

    result = await db.sheet_rows.update_one(
        {"_id": ObjectId(row_id), "sheet_id": sheet_id},
        {"$set": update_doc}
    )
    
    updated = await db.sheet_rows.find_one({"_id": ObjectId(row_id)})
    if not updated:
        raise HTTPException(status_code=404, detail="Row not found")
    return serialize_mongo(updated)

@router.delete("/{sheet_id}", response_model=Dict[str, Any])
async def delete_sheet(sheet_id: str, db=Depends(get_db)):
    sheet = await db.sheets.find_one({"_id": ObjectId(sheet_id)})
    if not sheet:
        raise HTTPException(status_code=404, detail="Sheet not found")
    
    # Delete the sheet
    await db.sheets.delete_one({"_id": ObjectId(sheet_id)})
    # Delete all rows associated with the sheet
    await db.sheet_rows.delete_many({"sheet_id": sheet_id})
    
    return {"status": "success", "message": "Sheet deleted successfully"}
