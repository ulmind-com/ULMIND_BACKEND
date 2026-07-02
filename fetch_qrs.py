import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import certifi
import base64
import os

async def fetch():
    client = AsyncIOMotorClient('mongodb+srv://samiran:samiran2004@cluster2004.eowyegm.mongodb.net/ulmind', tlsCAFile=certifi.where())
    db = client.get_default_database()
    
    employees = await db['hw_employees'].find({}).to_list(100)
    print(f"Found {len(employees)} employees")
    
    for emp in employees:
        name = emp.get('name', 'Unknown').replace(' ', '_')
        qr_b64 = emp.get('qr_code_image')
        if qr_b64:
            if qr_b64.startswith('data:image/png;base64,'):
                qr_b64 = qr_b64.split(',')[1]
            try:
                img_data = base64.b64decode(qr_b64)
                os.makedirs('/Users/arnabsenapati/ulmind/ulmind.com/public/hardware_qrs', exist_ok=True)
                path = f"/Users/arnabsenapati/ulmind/ulmind.com/public/hardware_qrs/{name}_qr.png"
                with open(path, 'wb') as f:
                    f.write(img_data)
                print(f"Saved QR for {name} to {path}")
            except Exception as e:
                print(f"Failed to decode QR for {name}: {e}")
                
    client.close()

if __name__ == "__main__":
    asyncio.run(fetch())
