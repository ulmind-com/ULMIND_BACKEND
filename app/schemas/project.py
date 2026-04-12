from datetime import datetime
from typing import Optional, List, Annotated
from app.core.datetime_utils import get_now
from pydantic import BaseModel, EmailStr, Field
from pydantic.functional_validators import BeforeValidator
import uuid

PyObjectId = Annotated[str, BeforeValidator(str)]


# ── Sub-model: Deployment Entry ───────────────────────────────────────────────

class DeploymentBase(BaseModel):
    service_name: str = Field(..., description="e.g. 'Frontend', 'Backend', 'Database'")
    platform: str = Field(..., description="e.g. 'Render', 'Vercel', 'AWS', 'Railway', 'MongoDB Atlas'")
    url: Optional[str] = Field(default=None, description="Live URL of the deployed service")
    login_email: Optional[str] = Field(default=None, description="Account email used for this platform")
    login_password: Optional[str] = Field(default=None, description="Account password for this platform")
    notes: Optional[str] = Field(default=None, description="Any extra notes")
    deployed_at: Optional[datetime] = None


class DeploymentCreate(DeploymentBase):
    pass


class DeploymentUpdate(BaseModel):
    service_name: Optional[str] = None
    platform: Optional[str] = None
    url: Optional[str] = None
    login_email: Optional[str] = None
    login_password: Optional[str] = None
    notes: Optional[str] = None
    deployed_at: Optional[datetime] = None


class DeploymentInDB(DeploymentBase):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))


# ── Sub-model: Environment Variable ──────────────────────────────────────────

class EnvVarBase(BaseModel):
    key: str = Field(..., description="Variable name, e.g. 'MONGO_URI'")
    value: str = Field(..., description="The secret value")
    environment: str = Field(
        default="production",
        description="Target environment: 'production', 'staging', or 'development'"
    )
    description: Optional[str] = Field(default=None, description="What this variable is for")


class EnvVarCreate(EnvVarBase):
    pass


class EnvVarUpdate(BaseModel):
    key: Optional[str] = None
    value: Optional[str] = None
    environment: Optional[str] = None
    description: Optional[str] = None


class EnvVarInDB(EnvVarBase):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))


# ── Main Project Model ────────────────────────────────────────────────────────

class ProjectBase(BaseModel):
    name: str = Field(..., description="Project name")
    status: str = Field(
        default="Planning",
        description="'Planning' | 'Active' | 'On Hold' | 'Completed'"
    )
    notes: Optional[str] = Field(default=None, description="General project notes")
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None

    # Client Info
    client_name: str = Field(..., description="Client's full name")
    client_email: EmailStr = Field(..., description="Client's email address")
    client_phone: Optional[str] = None
    client_company: Optional[str] = None

    # Financials
    cost: float = Field(..., ge=0, description="Total project cost")
    currency: str = Field(default="INR", description="Currency code, e.g. 'INR', 'USD'")
    payment_status: str = Field(
        default="Pending",
        description="'Pending' | 'Partial' | 'Paid'"
    )


class ProjectCreate(ProjectBase):
    deployments: List[DeploymentCreate] = Field(default_factory=list)
    env_vars: List[EnvVarCreate] = Field(default_factory=list)


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    client_name: Optional[str] = None
    client_email: Optional[EmailStr] = None
    client_phone: Optional[str] = None
    client_company: Optional[str] = None
    cost: Optional[float] = Field(default=None, ge=0)
    currency: Optional[str] = None
    payment_status: Optional[str] = None


class ProjectResponse(ProjectBase):
    id: PyObjectId = Field(alias="_id")
    deployments: List[DeploymentInDB] = []
    env_vars: List[EnvVarInDB] = []
    created_at: datetime = Field(alias="createdAt", default_factory=get_now)
    updated_at: datetime = Field(alias="updatedAt", default_factory=get_now)

    model_config = {"populate_by_name": True}


class ProjectSummaryResponse(BaseModel):
    """Lightweight response for list view — omits env_vars and deployments."""
    id: PyObjectId = Field(alias="_id")
    name: str
    status: str
    client_name: str
    client_email: str
    cost: float
    currency: str
    payment_status: str
    created_at: datetime = Field(alias="createdAt", default_factory=get_now)
    updated_at: datetime = Field(alias="updatedAt", default_factory=get_now)

    model_config = {"populate_by_name": True}
