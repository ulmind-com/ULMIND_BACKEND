from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from typing import Annotated
from pydantic.functional_validators import BeforeValidator

PyObjectId = Annotated[str, BeforeValidator(str)]


class EnvStoreCreate(BaseModel):
    project_name: str
    env_content: str


class EnvStoreUpdate(BaseModel):
    project_name: Optional[str] = None
    env_content: Optional[str] = None


class EnvStoreInDB(BaseModel):
    id: PyObjectId = Field(alias="_id")
    project_name: str
    env_content: str
    var_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"populate_by_name": True}


class EnvStoreListItem(BaseModel):
    """Lightweight model for list view — content truncated."""
    id: PyObjectId = Field(alias="_id")
    project_name: str
    var_count: int = 0
    preview: str = ""
    created_at: datetime
    updated_at: datetime

    model_config = {"populate_by_name": True}
