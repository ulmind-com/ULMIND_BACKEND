"""
Email Service — Resend HTTP API
==================================
Resend is the simplest, most modern HTTP email API.
Free tier: 3,000 emails/month (100/day).
No domain verification needed to get started.
Uses httpx (already installed) — no new packages needed.

Setup (2 minutes):
  1. Sign up at https://resend.com (free, no credit card)
  2. Go to API Keys → Create API Key
  3. Add RESEND_API_KEY=re_xxxxxxxxx to .env and Render environment variables
  4. (Optional) Go to Domains → Add Domain → verify your domain to send from
     your own address. Until then, Resend sends from onboarding@resend.dev.
"""
import logging
import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

RESEND_API_URL = "https://api.resend.com/emails"


def _get_from_address() -> str:
    """
    If a verified custom domain email is configured, use it.
    Otherwise, fallback to Resend's default onboarding@resend.dev.
    Resend strictly forbids sending FROM public webmail addresses (like @gmail.com).
    """
    mail_addr = settings.MAIL_ADDRESS
    if mail_addr and mail_addr.strip():
        mail_addr = mail_addr.strip().lower()
        # List of public domains that cannot be verified in Resend
        public_domains = ["gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "live.com", "icloud.com", "mail.com", "gmx.com", "aol.com"]
        domain = mail_addr.split("@")[-1]
        
        if domain not in public_domains:
            name = settings.MAIL_FROM_NAME or "ULMiND Team"
            return f"{name} <{settings.MAIL_ADDRESS}>"
            
    # Fallback to Resend's default sender for unverified custom domains/testing
    return "ULMiND Team <onboarding@resend.dev>"



def _build_html_body(otp: str) -> str:
    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Password Reset OTP</title>
</head>
<body style="margin:0;padding:0;background:#0a0e1a;font-family:'Inter',Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0"
         style="background:#0a0e1a;padding:40px 20px;">
    <tr>
      <td align="center">
        <table width="480" cellpadding="0" cellspacing="0"
               style="background:#111827;border:1px solid #1e293b;
                      border-radius:20px;overflow:hidden;max-width:480px;width:100%;">
          <tr>
            <td style="height:3px;background:linear-gradient(90deg,#7c3aed,#e11d48);"></td>
          </tr>
          <tr>
            <td style="padding:32px 40px 0;text-align:center;">
              <div style="display:inline-block;width:56px;height:56px;border-radius:16px;
                          background:linear-gradient(135deg,#7c3aed,#e11d48);
                          line-height:56px;text-align:center;font-size:26px;">&#128272;</div>
              <h1 style="color:#f1f5f9;font-size:22px;font-weight:700;
                          margin:16px 0 4px;">Password Reset</h1>
              <p style="color:#64748b;font-size:13px;margin:0;">ULMiND Admin Panel</p>
            </td>
          </tr>
          <tr>
            <td style="padding:32px 40px;">
              <p style="color:#94a3b8;font-size:14px;line-height:1.6;margin:0 0 24px;">
                Hello,<br><br>
                We received a request to reset your password. Use the OTP below to proceed.
                This code is valid for <strong style="color:#f1f5f9;">10 minutes</strong> only.
              </p>
              <div style="background:#1a1f36;border:2px solid #7c3aed;border-radius:16px;
                          padding:24px;text-align:center;margin:0 0 24px;">
                <p style="color:#64748b;font-size:11px;text-transform:uppercase;
                           letter-spacing:0.1em;margin:0 0 8px;font-weight:600;">
                  Your OTP Code
                </p>
                <div style="font-size:40px;font-weight:800;letter-spacing:12px;
                            color:#f1f5f9;font-family:monospace;line-height:1.2;">
                  {otp}
                </div>
                <p style="color:#64748b;font-size:12px;margin:12px 0 0;">
                  Expires in 10 minutes
                </p>
              </div>
              <p style="color:#475569;font-size:13px;line-height:1.6;margin:0;">
                If you did not request this password reset, you can safely ignore this email.
                Your account remains secure.
              </p>
            </td>
          </tr>
          <tr>
            <td style="padding:16px 40px 32px;text-align:center;border-top:1px solid #1e293b;">
              <p style="color:#334155;font-size:11px;margin:0;text-transform:uppercase;
                        letter-spacing:0.08em;font-weight:600;">
                ULMiND Internal Dashboard &mdash; Do Not Reply
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def _build_plain_body(otp: str) -> str:
    return f"""Hello,

Your ULMiND admin password reset OTP is:

    {otp}

This OTP will expire in 10 minutes. Do not share it with anyone.

If you did not request this, please ignore this email.

-- ULMiND Team"""


async def send_otp_email(recipient: str, otp: str) -> None:
    """
    Send OTP email via Resend HTTP API (HTTPS — works on Render).
    Raises RuntimeError on failure so the caller returns HTTP 503.
    """
    api_key = settings.RESEND_API_KEY

    if not api_key or not api_key.strip():
        raise RuntimeError(
            "RESEND_API_KEY is not configured. "
            "Get a free key at https://resend.com and add it to your Render environment variables."
        )

    payload = {
        "from": _get_from_address(),
        "to": [recipient],
        "subject": "Password Reset OTP — ULMiND",
        "html": _build_html_body(otp),
        "text": _build_plain_body(otp),
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                RESEND_API_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )

        # Resend returns 200 on success
        if response.status_code not in (200, 201):
            body = response.text
            logger.error(
                f"Resend rejected OTP email to {recipient}. "
                f"Status: {response.status_code}. Response: {body}"
            )
            # Give a clear hint for the most common error
            if response.status_code == 403:
                raise RuntimeError(
                    "Resend API: permission denied. "
                    "Check that RESEND_API_KEY is correct and your sender domain is verified."
                )
            raise RuntimeError(
                f"Failed to send OTP email (Resend {response.status_code}). "
                "Please try again later."
            )

        logger.info(f"OTP email sent successfully to {recipient} via Resend")

    except httpx.TimeoutException:
        logger.error(f"Resend API timed out while sending email to {recipient}")
        raise RuntimeError("Email service timed out. Please try again.")
    except httpx.RequestError as e:
        logger.error(f"Network error calling Resend API for {recipient}: {e}")
        raise RuntimeError("Failed to reach the email service. Please try again later.")
