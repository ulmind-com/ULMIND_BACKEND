"""
Email Service
Reusable SMTP email sender using Gmail SMTP (TLS on port 587).
Credentials come from settings.MAIL_ADDRESS / settings.MAIL_PASSWORD.
"""
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from app.core.config import settings

logger = logging.getLogger(__name__)


def _build_otp_email(recipient: str, otp: str) -> MIMEMultipart:
    """Build the OTP email MIME message."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Password Reset OTP — ULMiND"
    msg["From"] = f"ULMiND Team <{settings.MAIL_ADDRESS}>"
    msg["To"] = recipient

    plain_body = f"""Hello,

Your password reset OTP is:

    {otp}

This OTP will expire in 10 minutes.

If you did not request this password reset, please ignore this email.

Regards,
ULMIND Team
"""

    html_body = f"""<!DOCTYPE html>
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
          <!-- Top gradient bar -->
          <tr>
            <td style="height:3px;background:linear-gradient(90deg,#7c3aed,#e11d48);"></td>
          </tr>
          <!-- Header -->
          <tr>
            <td style="padding:32px 40px 0;text-align:center;">
              <div style="display:inline-block;width:56px;height:56px;border-radius:16px;
                          background:linear-gradient(135deg,#7c3aed,#e11d48);
                          line-height:56px;text-align:center;font-size:24px;">🔐</div>
              <h1 style="color:#f1f5f9;font-size:22px;font-weight:700;
                          margin:16px 0 4px;">Password Reset</h1>
              <p style="color:#64748b;font-size:13px;margin:0;">ULMiND Admin Panel</p>
            </td>
          </tr>
          <!-- Body -->
          <tr>
            <td style="padding:32px 40px;">
              <p style="color:#94a3b8;font-size:14px;line-height:1.6;margin:0 0 24px;">
                Hello,<br><br>
                We received a request to reset your password. Use the OTP below to proceed.
                This code is valid for <strong style="color:#f1f5f9;">10 minutes</strong> only.
              </p>
              <!-- OTP Box -->
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
          <!-- Footer -->
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
</html>
"""

    msg.attach(MIMEText(plain_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))
    return msg


async def send_otp_email(recipient: str, otp: str) -> None:
    """
    Send OTP email using Gmail SMTP (TLS, port 587).
    Raises RuntimeError on SMTP failure so the caller can return a 503.
    """
    if not settings.MAIL_ADDRESS or not settings.MAIL_PASSWORD:
        raise RuntimeError("MAIL_ADDRESS or MAIL_PASSWORD is not configured in .env")

    msg = _build_otp_email(recipient, otp)

    try:
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=10) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(settings.MAIL_ADDRESS, settings.MAIL_PASSWORD)
            server.sendmail(settings.MAIL_ADDRESS, recipient, msg.as_string())
        logger.info(f"OTP email sent successfully to {recipient}")
    except smtplib.SMTPAuthenticationError:
        logger.error("SMTP authentication failed — check MAIL_ADDRESS and MAIL_PASSWORD in .env")
        raise RuntimeError("Email authentication failed. Please contact the system administrator.")
    except smtplib.SMTPException as e:
        logger.error(f"SMTP error while sending OTP email to {recipient}: {e}")
        raise RuntimeError("Failed to send OTP email. Please try again later.")
    except Exception as e:
        logger.error(f"Unexpected error sending OTP email to {recipient}: {e}")
        raise RuntimeError("Failed to send OTP email. Please try again later.")
