from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional

class DeleteRequestCreate(BaseModel):
    item_type: str = Field(..., example="Team Member")
    item_description: str = Field(..., example="Soumyajit Banerjee")
    endpoint: str = Field(..., example="/api/v1/team/12345")

class DeleteRequestUpdate(BaseModel):
    status: str = Field(..., example="approved")

class DeleteRequestInDB(BaseModel):
    id: str = Field(..., alias="_id")
    user_id: str
    user_name: str
    user_email: str
    item_type: str
    item_description: str
    endpoint: str
    status: str = "pending"
    created_at: datetime
    updated_at: datetime

    class Config:
        populate_by_name = True
