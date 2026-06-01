from fastapi import APIRouter, Depends, HTTPException, Body
from typing import Dict, Any, List
from bson import ObjectId
from app.db.database import get_db
from app.core.config import settings
import httpx

router = APIRouter()

@router.post("/{sheet_id}/query")
async def query_sheet_ai(sheet_id: str, payload: Dict[str, Any] = Body(...), db=Depends(get_db)):
    query = payload.get("query")
    if not query:
        raise HTTPException(status_code=400, detail="Query is required")
        
    # 1. Get the sheet schema and some sample rows
    sheet = await db.sheets.find_one({"_id": ObjectId(sheet_id)})
    if not sheet:
        raise HTTPException(status_code=404, detail="Sheet not found")
        
    rows = await db.sheet_rows.find({"sheet_id": sheet_id}).limit(20).to_list(20)
    
    # 2. Prepare the prompt context
    columns_str = ", ".join([c["headerName"] for c in sheet.get("columns", [])])
    sample_data = [r.get("data", {}) for r in rows]
    
    system_prompt = f"""You are an advanced enterprise spreadsheet AI assistant.
You are analyzing a database sheet named '{sheet.get("name")}'.
Columns available: {columns_str}
Sample Data: {sample_data}

Provide a concise, helpful answer to the user's query based ONLY on the data provided. 
If the user asks to generate a report, format it beautifully in Markdown.
"""

    if not settings.OPENROUTER_API_KEY:
        # Fallback if no key is set for local development
        return {"response": f"AI Integration simulated. You asked: {query}. (OpenRouter API key missing in .env)"}
        
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
                    "HTTP-Referer": "https://ulmind.com", 
                    "X-Title": "ULMIND Internal OS",
                },
                json={
                    "model": "google/gemini-pro", # Can swap for claude-3-haiku
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": query}
                    ]
                },
                timeout=30.0
            )
            response.raise_for_status()
            data = response.json()
            return {"response": data["choices"][0]["message"]["content"]}
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
