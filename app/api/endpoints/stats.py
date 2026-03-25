from fastapi import APIRouter, Depends
from app.db.database import get_db
from typing import Optional

router = APIRouter()

@router.get("/kpi")
async def get_kpi_stats(db=Depends(get_db)):
    active_projects = await db["projects"].count_documents({"status": "Active"})
    total_clients = await db["clients"].count_documents({})
    
    return {
        "active_projects": active_projects or 0,
        "total_clients": total_clients or 0,
        "monthly_revenue": 12500, # Mocked
        "pending_tickets": 3      # Mocked
    }

@router.get("/charts")
async def get_chart_stats(period: Optional[str] = "monthly"):
    if period == "weekly":
        return [
            {"name": "Week 1", "sales": 1200, "orders": 400},
            {"name": "Week 2", "sales": 1500, "orders": 500},
            {"name": "Week 3", "sales": 1100, "orders": 350},
            {"name": "Week 4", "sales": 1800, "orders": 600},
        ]
    else:
        return [
            {"name": "Jan", "sales": 4000, "orders": 2400},
            {"name": "Feb", "sales": 3000, "orders": 1398},
            {"name": "Mar", "sales": 2000, "orders": 9800},
            {"name": "Apr", "sales": 2780, "orders": 3908},
            {"name": "May", "sales": 1890, "orders": 4800},
            {"name": "Jun", "sales": 2390, "orders": 3800},
        ]
