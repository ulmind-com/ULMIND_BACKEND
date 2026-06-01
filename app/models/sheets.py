from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime

class SheetColumn(BaseModel):
    field: str
    headerName: str
    type: str = "text" # text, number, date, boolean, etc.
    editable: bool = True
    width: Optional[int] = None

class SheetCreate(BaseModel):
    name: str
    description: Optional[str] = ""
    columns: Optional[List[SheetColumn]] = []

class SheetInDB(SheetCreate):
    id: str = Field(alias="_id")
    columns: List[SheetColumn] = []
    created_at: datetime
    updated_at: datetime

class SheetRowCreate(BaseModel):
    data: Dict[str, Any]
    styles: Optional[Dict[str, Dict[str, Any]]] = Field(default_factory=dict)

class SheetRowInDB(SheetRowCreate):
    id: str = Field(alias="_id")
    sheet_id: str
    created_at: datetime
    updated_at: datetime
