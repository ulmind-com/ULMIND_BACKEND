import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import certifi
import json
from app.api.endpoints.hardware_auth import _generate_qr_payload, _generate_qr_image_base64
from app.core.datetime_utils import get_now

async def generate():
    client = AsyncIOMotorClient('mongodb+srv://samiran:samiran2004@cluster2004.eowyegm.mongodb.net/ulmind', tlsCAFile=certifi.where())
    db = client.get_default_database()
    
    admins = await db['admins'].find({}).to_list(100)
    
    for idx, admin in enumerate(admins):
        employee_id = f"UL-{idx+1:03d}"
        email = admin.get('email')
        
        # Check if exists
        existing = await db["hw_employees"].find_one({"email": email})
        if existing:
            print(f"Employee {email} already exists")
            continue
            
        name = admin.get('full_name', email.split('@')[0].replace('.', ' ').title())
        designation = admin.get('role', 'employee').replace('_', ' ').title()
        
        now = get_now()
        doc = {
            "name": name,
            "email": email,
            "designation": designation,
            "employee_id": employee_id,
            "department": "Engineering",
            "status": "Active",
            "total_working_hours": 0,
            "total_sessions": 0,
            "avg_productivity_score": 0,
            "created_at": now,
            "updated_at": now,
        }
        
        result = await db["hw_employees"].insert_one(doc)
        doc["_id"] = result.inserted_id
        
        qr_payload = _generate_qr_payload(doc)
        qr_image = _generate_qr_image_base64(qr_payload)
        
        await db["hw_employees"].update_one(
            {"_id": result.inserted_id},
            {"$set": {"qr_code_data": qr_payload, "qr_code_image": qr_image}}
        )
        print(f"Created HW employee and QR for {name} ({email}) - {employee_id}")
        
    client.close()

if __name__ == "__main__":
    asyncio.run(generate())
