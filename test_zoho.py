import asyncio
import os
from dotenv import load_dotenv
import aiosmtplib
from email.message import EmailMessage

load_dotenv()

async def test_zoho():
    smtp_user = "contact@ulmind.com"
    smtp_pass = "KJg6N7We48cC"
    
    if not smtp_pass:
        print("No SMTP password found in .env")
        return

    msg = EmailMessage()
    msg["Subject"] = "Zoho SMTP Test - ULMiND"
    msg["From"] = f"ULMiND Team <{smtp_user}>"
    msg["To"] = "arnab.senapati@ulmind.com"
    msg.set_content("This is a test email directly from Zoho SMTP!")

    print(f"Sending test email from {smtp_user} to arnab...")
    
    try:
        await aiosmtplib.send(
            msg,
            hostname="smtp.zoho.in",
            port=465,
            use_tls=True,
            username=smtp_user,
            password=smtp_pass,
            timeout=15.0
        )
        print("Success! Sent via smtp.zoho.in")
    except Exception as e:
        print(f"smtp.zoho.in failed: {e}")
        try:
            await aiosmtplib.send(
                msg,
                hostname="smtp.zoho.com",
                port=465,
                use_tls=True,
                username=smtp_user,
                password=smtp_pass,
                timeout=15.0
            )
            print("Success! Sent via smtp.zoho.com")
        except Exception as e2:
            print(f"smtp.zoho.com failed: {e2}")

asyncio.run(test_zoho())
