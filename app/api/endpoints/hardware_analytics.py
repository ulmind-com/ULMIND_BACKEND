"""
Hardware Analytics — AI-Powered Productivity Analysis
======================================================
Endpoints for computing productivity scores, salary
recommendations, and daily reports using Groq AI.
"""

import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from bson import ObjectId
from app.db.database import get_db
from app.core.config import settings
from app.core.datetime_utils import get_now
import httpx

logger = logging.getLogger(__name__)

router = APIRouter()

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"


async def _call_groq(prompt: str, system_prompt: str = "") -> str:
    """Call Groq API for AI analysis."""
    if not settings.GROQ_API_KEY:
        return "AI analysis unavailable — GROQ_API_KEY not configured."
    
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                GROQ_API_URL,
                headers={
                    "Authorization": f"Bearer {settings.GROQ_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "llama-3.1-8b-instant",
                    "messages": messages,
                    "temperature": 0.3,
                    "max_tokens": 1024,
                }
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
    except Exception as e:
        logger.error(f"Groq API error: {e}")
        return f"AI analysis temporarily unavailable: {str(e)}"


def _aggregate_end_time(sessions: list) -> Optional[datetime]:
    """End time for a day's aggregate: the latest logout, but only if
    every session has ended. If any session is still live, return None so
    the score measures against the current clock."""
    if any(not s.get("logout_time") for s in sessions):
        return None
    return max(s["logout_time"] for s in sessions)


def _compute_productivity_score(session: dict) -> dict:
    """Compute productivity scores from session data."""
    total_active = session.get("total_active_seconds", 0)
    total_idle = session.get("total_idle_seconds", 0)
    total_absent = session.get("total_absent_seconds", 0)
    face_present = session.get("face_present_seconds", 0)
    mobile_seconds = session.get("mobile_detected_seconds", 0)
    sleeping_seconds = session.get("sleeping_detected_seconds", 0)
    camera_covered = session.get("camera_covered_seconds", 0)
    looking_away = session.get("looking_away_seconds", 0)
    mobile_count = session.get("mobile_detected_count", 0)
    sleeping_count = session.get("sleeping_detected_count", 0)
    
    login_time = session.get("login_time")
    # For a finished session use its recorded end time; only a still-live
    # session should measure against "now". Otherwise historical sessions
    # would keep inflating their denominator against the current clock.
    end_time = session.get("logout_time")
    now = get_now()
    if login_time:
        if login_time.tzinfo is None:
            login_time = login_time.replace(tzinfo=timezone.utc)
        ref_time = end_time or now
        if hasattr(ref_time, "tzinfo") and ref_time.tzinfo is None:
            ref_time = ref_time.replace(tzinfo=timezone.utc)
        total_session = (ref_time - login_time).total_seconds()
    else:
        total_session = total_active + total_idle + total_absent
    
    if total_session <= 0:
        total_session = 1  # Prevent division by zero
    
    # Score computation (0-100 each)
    attendance_score = min(100, (total_session / (8 * 3600)) * 100)
    presence_score = min(100, (face_present / max(total_session, 1)) * 100)
    focus_score = max(0, 100 - (looking_away / max(total_session, 1)) * 100)
    activity_score = min(100, (total_active / max(total_session, 1)) * 100)
    
    # Penalties
    mobile_penalty = min(50, (mobile_seconds / max(total_session, 1)) * 100 * 2)
    sleeping_penalty = min(50, (sleeping_seconds / max(total_session, 1)) * 100 * 3)
    absence_penalty = min(30, (total_absent / max(total_session, 1)) * 100)
    camera_penalty = min(40, (camera_covered / max(total_session, 1)) * 100 * 5)
    
    # Overall score
    raw_score = (attendance_score * 0.15 + presence_score * 0.25 + focus_score * 0.3 + activity_score * 0.3)
    total_penalty = mobile_penalty + sleeping_penalty + absence_penalty + camera_penalty
    overall = max(0, min(100, raw_score - total_penalty))
    
    return {
        "attendance_score": round(attendance_score, 1),
        "presence_score": round(presence_score, 1),
        "focus_score": round(focus_score, 1),
        "activity_score": round(activity_score, 1),
        "mobile_penalty": round(mobile_penalty, 1),
        "sleeping_penalty": round(sleeping_penalty, 1),
        "absence_penalty": round(absence_penalty, 1),
        "camera_tampering_penalty": round(camera_penalty, 1),
        "overall_productivity_score": round(overall, 1),
        "total_hours": round(total_session / 3600, 2),
        "active_hours": round(total_active / 3600, 2),
        "idle_hours": round(total_idle / 3600, 2),
        "absent_hours": round(total_absent / 3600, 2),
        "mobile_hours": round(mobile_seconds / 3600, 2),
        "sleeping_hours": round(sleeping_seconds / 3600, 2),
        "mobile_detections": mobile_count,
        "sleep_detections": sleeping_count,
        "absence_events": int(total_absent > 60),  # Count significant absences
    }


# ═══════════════════════════════════════════════════════════════
#  PRODUCTIVITY SCORE
# ═══════════════════════════════════════════════════════════════

@router.get("/productivity/{employee_db_id}")
async def get_productivity_score(
    employee_db_id: str,
    date: Optional[str] = None,  # YYYY-MM-DD
    db=Depends(get_db)
):
    """Get productivity score for an employee."""
    # Find employee
    employee = await db["hw_employees"].find_one({"_id": ObjectId(employee_db_id)})
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    # Find session(s) for the given date
    if date:
        try:
            target_date = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
        
        day_start = target_date
        day_end = target_date + timedelta(days=1)
    else:
        # Today
        now = get_now()
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        date = now.strftime("%Y-%m-%d")
    
    sessions = await db["hw_sessions"].find({
        "employee_db_id": employee_db_id,
        "login_time": {"$gte": day_start, "$lt": day_end}
    }).to_list(10)
    
    if not sessions:
        return {
            "status": "success",
            "employee_id": employee["employee_id"],
            "employee_name": employee["name"],
            "date": date,
            "message": "No sessions found for this date",
            "scores": {
                "overall_productivity_score": 0,
                "attendance_score": 0,
            }
        }
    
    # Aggregate scores across all sessions for the day
    combined = {
        "total_active_seconds": sum(s.get("total_active_seconds", 0) for s in sessions),
        "total_idle_seconds": sum(s.get("total_idle_seconds", 0) for s in sessions),
        "total_absent_seconds": sum(s.get("total_absent_seconds", 0) for s in sessions),
        "face_present_seconds": sum(s.get("face_present_seconds", 0) for s in sessions),
        "mobile_detected_seconds": sum(s.get("mobile_detected_seconds", 0) for s in sessions),
        "sleeping_detected_seconds": sum(s.get("sleeping_detected_seconds", 0) for s in sessions),
        "camera_covered_seconds": sum(s.get("camera_covered_seconds", 0) for s in sessions),
        "looking_away_seconds": sum(s.get("looking_away_seconds", 0) for s in sessions),
        "mobile_detected_count": sum(s.get("mobile_detected_count", 0) for s in sessions),
        "sleeping_detected_count": sum(s.get("sleeping_detected_count", 0) for s in sessions),
        "login_time": sessions[0]["login_time"],
        "logout_time": _aggregate_end_time(sessions),
    }
    
    scores = _compute_productivity_score(combined)
    
    return {
        "status": "success",
        "employee_id": employee["employee_id"],
        "employee_name": employee["name"],
        "date": date,
        "scores": scores
    }


# ═══════════════════════════════════════════════════════════════
#  SALARY RECOMMENDATION
# ═══════════════════════════════════════════════════════════════

@router.get("/salary-recommendation/{employee_db_id}")
async def get_salary_recommendation(
    employee_db_id: str,
    month: Optional[str] = None,  # YYYY-MM
    db=Depends(get_db)
):
    """Get AI-powered salary recommendation based on monitoring data."""
    employee = await db["hw_employees"].find_one({"_id": ObjectId(employee_db_id)})
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    now = get_now()
    if month:
        try:
            target_month = datetime.strptime(month + "-01", "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid month format. Use YYYY-MM")
    else:
        target_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        month = now.strftime("%Y-%m")
    
    next_month = (target_month + timedelta(days=32)).replace(day=1)
    
    # Get all sessions for the month
    sessions = await db["hw_sessions"].find({
        "employee_db_id": employee_db_id,
        "login_time": {"$gte": target_month, "$lt": next_month}
    }).to_list(100)
    
    total_working_days = len(set(s["login_time"].strftime("%Y-%m-%d") for s in sessions))
    
    total_mobile_hours = sum(s.get("mobile_detected_seconds", 0) for s in sessions) / 3600
    total_sleeping_hours = sum(s.get("sleeping_detected_seconds", 0) for s in sessions) / 3600
    total_absence_hours = sum(s.get("total_absent_seconds", 0) for s in sessions) / 3600
    total_active_hours = sum(s.get("total_active_seconds", 0) for s in sessions) / 3600
    total_idle_hours = sum(s.get("total_idle_seconds", 0) for s in sessions) / 3600
    
    # Compute average productivity
    daily_scores = []
    for session in sessions:
        scores = _compute_productivity_score(session)
        daily_scores.append(scores["overall_productivity_score"])
    
    avg_productivity = sum(daily_scores) / len(daily_scores) if daily_scores else 0
    
    # Ask Groq for AI analysis
    prompt = f"""Analyze this employee's monthly performance data and provide a salary recommendation.

Employee: {employee['name']} ({employee['designation']})
Month: {month}

Data:
- Days present: {total_working_days}
- Average productivity score: {avg_productivity:.1f}/100
- Total active hours: {total_active_hours:.1f}
- Total idle hours: {total_idle_hours:.1f}
- Total absence hours: {total_absence_hours:.1f}
- Mobile phone usage hours: {total_mobile_hours:.1f}
- Sleeping/drowsy hours: {total_sleeping_hours:.1f}

Based on this data:
1. What percentage of base salary should be paid? (100% = full)
2. Any deduction percentage?
3. Any bonus percentage?
4. Brief analysis (2-3 sentences)
5. 2-3 recommendations for improvement

Respond in JSON format:
{{"base_salary_percent": number, "deduction_percent": number, "bonus_percent": number, "final_salary_percent": number, "analysis": "string", "recommendations": ["string"]}}"""

    system_prompt = "You are an HR analytics AI. Provide fair, data-driven salary recommendations. Be objective and professional. Always respond in valid JSON only."
    
    ai_response = await _call_groq(prompt, system_prompt)
    
    # Parse AI response
    try:
        # Try to extract JSON from the response
        import re
        json_match = re.search(r'\{[^{}]*\}', ai_response, re.DOTALL)
        if json_match:
            ai_data = json.loads(json_match.group())
        else:
            ai_data = json.loads(ai_response)
    except (json.JSONDecodeError, AttributeError):
        ai_data = {
            "base_salary_percent": 100,
            "deduction_percent": max(0, (100 - avg_productivity) * 0.5),
            "bonus_percent": max(0, (avg_productivity - 80) * 0.5) if avg_productivity > 80 else 0,
            "analysis": ai_response[:500],
            "recommendations": ["Maintain consistent work schedule", "Minimize mobile phone usage during work hours"]
        }
    
    final_percent = ai_data.get("base_salary_percent", 100) - ai_data.get("deduction_percent", 0) + ai_data.get("bonus_percent", 0)
    
    result = {
        "employee_id": employee["employee_id"],
        "employee_name": employee["name"],
        "month": month,
        "total_working_days": total_working_days,
        "days_present": total_working_days,
        "avg_productivity_score": round(avg_productivity, 1),
        "total_mobile_hours": round(total_mobile_hours, 2),
        "total_sleeping_hours": round(total_sleeping_hours, 2),
        "total_absence_hours": round(total_absence_hours, 2),
        "base_salary_percent": ai_data.get("base_salary_percent", 100),
        "deduction_percent": round(ai_data.get("deduction_percent", 0), 1),
        "bonus_percent": round(ai_data.get("bonus_percent", 0), 1),
        "final_salary_percent": round(final_percent, 1),
        "ai_analysis": ai_data.get("analysis", ""),
        "recommendations": ai_data.get("recommendations", []),
    }
    
    # Store recommendation
    await db["hw_salary_recommendations"].update_one(
        {"employee_db_id": employee_db_id, "month": month},
        {"$set": {**result, "employee_db_id": employee_db_id, "computed_at": now}},
        upsert=True
    )
    
    return {"status": "success", "recommendation": result}


# ═══════════════════════════════════════════════════════════════
#  DAILY REPORT
# ═══════════════════════════════════════════════════════════════

@router.get("/daily-report/{employee_db_id}")
async def get_daily_report(
    employee_db_id: str,
    date: Optional[str] = None,
    db=Depends(get_db)
):
    """Get comprehensive daily monitoring report with AI summary."""
    employee = await db["hw_employees"].find_one({"_id": ObjectId(employee_db_id)})
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    now = get_now()
    if date:
        try:
            target_date = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format")
    else:
        target_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        date = now.strftime("%Y-%m-%d")
    
    day_start = target_date
    day_end = target_date + timedelta(days=1)
    
    # Get events for the day
    events = await db["hw_monitoring_events"].find({
        "employee_db_id": employee_db_id,
        "timestamp": {"$gte": day_start, "$lt": day_end}
    }).sort("timestamp", 1).to_list(1000)
    
    for e in events:
        e["_id"] = str(e["_id"])
    
    # Get session
    sessions = await db["hw_sessions"].find({
        "employee_db_id": employee_db_id,
        "login_time": {"$gte": day_start, "$lt": day_end}
    }).to_list(10)
    
    scores = {}
    if sessions:
        combined = {
            "total_active_seconds": sum(s.get("total_active_seconds", 0) for s in sessions),
            "total_idle_seconds": sum(s.get("total_idle_seconds", 0) for s in sessions),
            "total_absent_seconds": sum(s.get("total_absent_seconds", 0) for s in sessions),
            "face_present_seconds": sum(s.get("face_present_seconds", 0) for s in sessions),
            "mobile_detected_seconds": sum(s.get("mobile_detected_seconds", 0) for s in sessions),
            "sleeping_detected_seconds": sum(s.get("sleeping_detected_seconds", 0) for s in sessions),
            "camera_covered_seconds": sum(s.get("camera_covered_seconds", 0) for s in sessions),
            "looking_away_seconds": sum(s.get("looking_away_seconds", 0) for s in sessions),
            "mobile_detected_count": sum(s.get("mobile_detected_count", 0) for s in sessions),
            "sleeping_detected_count": sum(s.get("sleeping_detected_count", 0) for s in sessions),
            "login_time": sessions[0]["login_time"],
            "logout_time": _aggregate_end_time(sessions),
        }
        scores = _compute_productivity_score(combined)
    
    # Event type counts
    event_counts = {}
    for e in events:
        t = e.get("event_type", "unknown")
        event_counts[t] = event_counts.get(t, 0) + 1
    
    # AI Summary
    event_summary = ", ".join(f"{k}: {v}" for k, v in event_counts.items())
    prompt = f"""Summarize this employee's daily work monitoring report.

Employee: {employee['name']} ({employee['designation']})
Date: {date}

Productivity Score: {scores.get('overall_productivity_score', 0)}/100
Active Hours: {scores.get('active_hours', 0)}
Idle Hours: {scores.get('idle_hours', 0)}
Mobile Usage Hours: {scores.get('mobile_hours', 0)}
Events: {event_summary}

Provide:
1. A 2-3 sentence summary of the day
2. 2-3 specific recommendations

Respond in JSON: {{"summary": "string", "recommendations": ["string"]}}"""

    ai_response = await _call_groq(prompt, "You are an HR analytics AI. Be concise and professional. Respond in valid JSON only.")
    
    try:
        import re
        json_match = re.search(r'\{[^{}]*\}', ai_response, re.DOTALL)
        if json_match:
            ai_data = json.loads(json_match.group())
        else:
            ai_data = json.loads(ai_response)
    except Exception:
        ai_data = {"summary": ai_response[:300], "recommendations": []}
    
    return {
        "status": "success",
        "employee_id": employee["employee_id"],
        "employee_name": employee["name"],
        "date": date,
        "events": events[:100],  # Limit for response size
        "event_counts": event_counts,
        "scores": scores,
        "ai_summary": ai_data.get("summary", ""),
        "ai_recommendations": ai_data.get("recommendations", []),
    }


# ═══════════════════════════════════════════════════════════════
#  LEADERBOARD
# ═══════════════════════════════════════════════════════════════

@router.get("/leaderboard")
async def get_leaderboard(
    date: Optional[str] = None,
    db=Depends(get_db)
):
    """Get employee productivity leaderboard."""
    now = get_now()
    if date:
        try:
            target_date = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format")
    else:
        target_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        date = now.strftime("%Y-%m-%d")
    
    day_start = target_date
    day_end = target_date + timedelta(days=1)
    
    employees = await db["hw_employees"].find({"status": "Active"}).to_list(100)
    
    leaderboard = []
    for emp in employees:
        sessions = await db["hw_sessions"].find({
            "employee_db_id": str(emp["_id"]),
            "login_time": {"$gte": day_start, "$lt": day_end}
        }).to_list(10)
        
        if sessions:
            combined = {
                "total_active_seconds": sum(s.get("total_active_seconds", 0) for s in sessions),
                "total_idle_seconds": sum(s.get("total_idle_seconds", 0) for s in sessions),
                "total_absent_seconds": sum(s.get("total_absent_seconds", 0) for s in sessions),
                "face_present_seconds": sum(s.get("face_present_seconds", 0) for s in sessions),
                "mobile_detected_seconds": sum(s.get("mobile_detected_seconds", 0) for s in sessions),
                "sleeping_detected_seconds": sum(s.get("sleeping_detected_seconds", 0) for s in sessions),
                "camera_covered_seconds": sum(s.get("camera_covered_seconds", 0) for s in sessions),
                "looking_away_seconds": sum(s.get("looking_away_seconds", 0) for s in sessions),
                "mobile_detected_count": sum(s.get("mobile_detected_count", 0) for s in sessions),
                "sleeping_detected_count": sum(s.get("sleeping_detected_count", 0) for s in sessions),
                "login_time": sessions[0]["login_time"],
                "logout_time": _aggregate_end_time(sessions),
            }
            scores = _compute_productivity_score(combined)
        else:
            scores = {"overall_productivity_score": 0, "active_hours": 0, "mobile_penalty": 0, "attendance_score": 0}
        
        leaderboard.append({
            "employee_id": emp["employee_id"],
            "employee_name": emp["name"],
            "designation": emp["designation"],
            "productivity_score": scores["overall_productivity_score"],
            "active_hours": scores.get("active_hours", 0),
            "mobile_penalty": scores.get("mobile_penalty", 0),
            "attendance_score": scores.get("attendance_score", 0),
        })
    
    # Sort by productivity score
    leaderboard.sort(key=lambda x: x["productivity_score"], reverse=True)
    
    # Add rank
    for i, entry in enumerate(leaderboard):
        entry["rank"] = i + 1
    
    return {"status": "success", "date": date, "leaderboard": leaderboard}
