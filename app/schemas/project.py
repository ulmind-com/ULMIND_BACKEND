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


# ── Sub-model: Milestone ─────────────────────────────────────────────────────

class MilestoneItem(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    description: Optional[str] = None
    due_date: Optional[datetime] = None
    status: str = "Pending"  # Pending, In Progress, Completed, Delayed
    completion_pct: float = 0


# ── Main Project Model ────────────────────────────────────────────────────────

class ProjectBase(BaseModel):
    name: str = Field(..., description="Project name")
    project_id: Optional[str] = Field(default=None, description="Auto-generated PROJ-UL-XXX")
    description: Optional[str] = Field(default=None, description="Project description")
    category: str = Field(default="Web Development", description="e.g. 'Web Development', 'Mobile App', 'AI/ML', 'DevOps', 'Design', 'Marketing'")
    status: str = Field(
        default="Planning",
        description="'Planning' | 'Active' | 'On Hold' | 'Completed' | 'Cancelled'"
    )
    priority: str = Field(default="Medium", description="'Low' | 'Medium' | 'High' | 'Urgent'")
    notes: Optional[str] = Field(default=None, description="General project notes")
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    tags: List[str] = Field(default_factory=list, description="Project tags for filtering")

    # Client Info
    client_name: str = Field(default="Unknown", description="Client's full name")
    client_email: Optional[EmailStr] = None
    client_phone: Optional[str] = None
    client_company: Optional[str] = None
    client_id: Optional[str] = Field(default=None, description="CRM Client ID reference")

    # Team
    team_members: List[str] = Field(default_factory=list, description="List of employee IDs assigned to this project")
    project_manager: Optional[str] = Field(default=None, description="Employee ID of the project manager")

    # Progress
    progress: float = Field(default=0, ge=0, le=100, description="Auto-calculated from task completion")
    completion_percent: float = Field(default=0, ge=0, le=100, description="Overall completion percentage")

    # Milestones (embedded)
    milestones: List[MilestoneItem] = Field(default_factory=list, description="Project milestones")

    # Financials
    budget: float = Field(default=0, ge=0, description="Total project budget (INR)")
    cost: float = Field(default=0, ge=0, description="Total project cost")
    currency: str = Field(default="INR", description="Currency code, e.g. 'INR'")
    payment_status: str = Field(
        default="Pending",
        description="'Pending' | 'Partial' | 'Paid'"
    )


class ProjectCreate(ProjectBase):
    deployments: List[DeploymentCreate] = Field(default_factory=list)
    env_vars: List[EnvVarCreate] = Field(default_factory=list)


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    notes: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    tags: Optional[List[str]] = None
    client_name: Optional[str] = None
    client_email: Optional[EmailStr] = None
    client_phone: Optional[str] = None
    client_company: Optional[str] = None
    client_id: Optional[str] = None
    team_members: Optional[List[str]] = None
    project_manager: Optional[str] = None
    progress: Optional[float] = Field(default=None, ge=0, le=100)
    completion_percent: Optional[float] = Field(default=None, ge=0, le=100)
    milestones: Optional[List[MilestoneItem]] = None
    budget: Optional[float] = Field(default=None, ge=0)
    cost: Optional[float] = Field(default=None, ge=0)
    currency: Optional[str] = None
    payment_status: Optional[str] = None


class ProjectResponse(ProjectBase):
    id: PyObjectId = Field(alias="_id")
    deployments: List[DeploymentInDB] = []
    env_vars: List[EnvVarInDB] = []
    created_at: datetime = Field(default_factory=get_now)
    updated_at: datetime = Field(default_factory=get_now)

    model_config = {"populate_by_name": True}


class ProjectSummaryResponse(BaseModel):
    """Lightweight response for list view — omits env_vars and deployments."""
    id: PyObjectId = Field(alias="_id")
    project_id: Optional[str] = None
    name: str
    description: Optional[str] = None
    category: str = "Web Development"
    status: str = "Planning"
    priority: str = "Medium"
    tags: List[str] = []
    client_name: Optional[str] = "Unknown"
    client_email: Optional[str] = None
    client_id: Optional[str] = None
    team_members: List[str] = []
    project_manager: Optional[str] = None
    progress: float = 0
    completion_percent: float = 0
    budget: float = 0
    cost: float = 0
    currency: str = "INR"
    payment_status: str = "Pending"
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    created_at: datetime = Field(default_factory=get_now)
    updated_at: datetime = Field(default_factory=get_now)

    model_config = {"populate_by_name": True}
