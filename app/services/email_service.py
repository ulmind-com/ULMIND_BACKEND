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


# ══════════════════════════════════════════════════════════════════════════════
#  GENERIC EMAIL SENDER
# ══════════════════════════════════════════════════════════════════════════════

async def send_email(recipient: str, subject: str, html_body: str, text_body: str = "") -> None:
    """
    Generic email sender via Resend HTTP API.
    Raises RuntimeError on failure.
    """
    api_key = settings.RESEND_API_KEY
    if not api_key or not api_key.strip():
        logger.warning(f"RESEND_API_KEY is not configured. Mocking email delivery to {recipient}.")
        logger.info(f"Subject: {subject}")
        # Return success for testing purposes
        return

    payload = {
        "from": _get_from_address(),
        "to": [recipient],
        "subject": subject,
        "html": html_body,
        "text": text_body or subject,
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

        if response.status_code not in (200, 201):
            body = response.text
            logger.error(f"Resend rejected email to {recipient}. Status: {response.status_code}. Response: {body}")
            raise RuntimeError(f"Failed to send email (Resend {response.status_code}).")

        logger.info(f"Email sent successfully to {recipient} via Resend")

    except httpx.TimeoutException:
        logger.error(f"Resend API timed out while sending email to {recipient}")
        raise RuntimeError("Email service timed out.")
    except httpx.RequestError as e:
        logger.error(f"Network error calling Resend API for {recipient}: {e}")
        raise RuntimeError("Failed to reach the email service.")


# ══════════════════════════════════════════════════════════════════════════════
#  TASK ASSIGNMENT EMAIL — Ultra Premium Design
# ══════════════════════════════════════════════════════════════════════════════

def _build_task_assignment_html(
    assignee_name: str,
    task_title: str,
    task_description: str,
    project_name: str,
    priority: str,
    due_date: str,
    assigned_by: str,
) -> str:
    """Build an ultra-premium, dark-mode task assignment email."""

    # Priority color mapping
    priority_colors = {
        "Urgent": ("#ef4444", "#dc2626", "🔴"),
        "High": ("#f59e0b", "#d97706", "🟠"),
        "Medium": ("#3b82f6", "#2563eb", "🔵"),
        "Low": ("#10b981", "#059669", "🟢"),
    }
    p_color, p_dark, p_emoji = priority_colors.get(priority, ("#3b82f6", "#2563eb", "🔵"))

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>New Task Assignment — ULMiND</title>
</head>
<body style="margin:0;padding:0;background:#050810;font-family:'Segoe UI','Inter',Arial,Helvetica,sans-serif;-webkit-font-smoothing:antialiased;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#050810;padding:40px 16px;">
    <tr>
      <td align="center">
        <table width="560" cellpadding="0" cellspacing="0" style="max-width:560px;width:100%;background:#0d1117;border-radius:24px;overflow:hidden;box-shadow:0 24px 80px rgba(0,0,0,0.6),0 0 0 1px rgba(255,255,255,0.06);">

          <!-- ─── Top accent bar ─── -->
          <tr>
            <td style="height:4px;background:linear-gradient(90deg,#10b981,#3b82f6,#8b5cf6,#ec4899);"></td>
          </tr>

          <!-- ─── Logo & Header ─── -->
          <tr>
            <td style="padding:36px 40px 0;">
              <table width="100%" cellpadding="0" cellspacing="0">
                <tr>
                  <td>
                    <div style="display:inline-block;width:48px;height:48px;border-radius:14px;background:linear-gradient(135deg,#10b981,#059669);text-align:center;line-height:48px;font-size:22px;font-weight:800;color:#fff;letter-spacing:-1px;box-shadow:0 8px 24px rgba(16,185,129,0.3);">U</div>
                  </td>
                  <td align="right">
                    <span style="display:inline-block;padding:6px 14px;border-radius:20px;background:rgba(16,185,129,0.1);border:1px solid rgba(16,185,129,0.2);color:#10b981;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;">New Task</span>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- ─── Greeting ─── -->
          <tr>
            <td style="padding:28px 40px 0;">
              <h1 style="margin:0;font-size:26px;font-weight:800;color:#f0f6fc;letter-spacing:-0.02em;line-height:1.3;">
                You've been assigned a task ✨
              </h1>
              <p style="margin:8px 0 0;font-size:15px;color:#8b949e;line-height:1.6;">
                Hey <strong style="color:#c9d1d9;">{assignee_name}</strong>, a new task has been assigned to you.
              </p>
            </td>
          </tr>

          <!-- ─── Task Card ─── -->
          <tr>
            <td style="padding:24px 40px 0;">
              <div style="background:#161b22;border:1px solid rgba(255,255,255,0.06);border-radius:16px;overflow:hidden;">

                <!-- Task header with gradient -->
                <div style="padding:20px 24px;background:linear-gradient(135deg,rgba(16,185,129,0.08),rgba(59,130,246,0.06));">
                  <table width="100%" cellpadding="0" cellspacing="0">
                    <tr>
                      <td>
                        <span style="font-size:11px;color:#8b949e;text-transform:uppercase;letter-spacing:0.1em;font-weight:600;">Task Title</span>
                      </td>
                      <td align="right">
                        <span style="display:inline-block;padding:4px 12px;border-radius:12px;background:{p_color}18;border:1px solid {p_color}30;color:{p_color};font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:0.06em;">{p_emoji} {priority}</span>
                      </td>
                    </tr>
                  </table>
                  <h2 style="margin:8px 0 0;font-size:18px;font-weight:700;color:#f0f6fc;line-height:1.4;">{task_title}</h2>
                </div>

                <!-- Task details grid -->
                <div style="padding:20px 24px;">
                  <!-- Description -->
                  <div style="margin-bottom:20px;padding:14px 16px;background:#0d1117;border-radius:10px;border-left:3px solid #3b82f6;">
                    <span style="font-size:10px;color:#6e7681;text-transform:uppercase;letter-spacing:0.1em;font-weight:700;">Description</span>
                    <p style="margin:6px 0 0;font-size:14px;color:#c9d1d9;line-height:1.6;">{task_description}</p>
                  </div>

                  <!-- Info grid -->
                  <table width="100%" cellpadding="0" cellspacing="0">
                    <tr>
                      <td width="50%" style="padding-right:8px;">
                        <div style="padding:14px 16px;background:#0d1117;border-radius:10px;">
                          <span style="font-size:10px;color:#6e7681;text-transform:uppercase;letter-spacing:0.1em;font-weight:700;">📁 Project</span>
                          <p style="margin:4px 0 0;font-size:14px;font-weight:600;color:#f0f6fc;">{project_name}</p>
                        </div>
                      </td>
                      <td width="50%" style="padding-left:8px;">
                        <div style="padding:14px 16px;background:#0d1117;border-radius:10px;">
                          <span style="font-size:10px;color:#6e7681;text-transform:uppercase;letter-spacing:0.1em;font-weight:700;">📅 Due Date</span>
                          <p style="margin:4px 0 0;font-size:14px;font-weight:600;color:#f0f6fc;">{due_date}</p>
                        </div>
                      </td>
                    </tr>
                  </table>

                  <!-- Progress tracker -->
                  <div style="margin-top:16px;padding:14px 16px;background:#0d1117;border-radius:10px;">
                    <span style="font-size:10px;color:#6e7681;text-transform:uppercase;letter-spacing:0.1em;font-weight:700;">Progress</span>
                    <div style="margin-top:8px;">
                      <table width="100%" cellpadding="0" cellspacing="0">
                        <tr>
                          <td style="padding:0 4px 0 0;">
                            <div style="height:6px;border-radius:3px;background:linear-gradient(90deg,#10b981,#059669);"></div>
                          </td>
                          <td style="padding:0 4px;">
                            <div style="height:6px;border-radius:3px;background:#21262d;"></div>
                          </td>
                          <td style="padding:0 4px;">
                            <div style="height:6px;border-radius:3px;background:#21262d;"></div>
                          </td>
                          <td style="padding:0 0 0 4px;">
                            <div style="height:6px;border-radius:3px;background:#21262d;"></div>
                          </td>
                        </tr>
                      </table>
                      <table width="100%" cellpadding="0" cellspacing="0" style="margin-top:6px;">
                        <tr>
                          <td style="font-size:9px;color:#10b981;font-weight:700;letter-spacing:0.05em;">ASSIGNED</td>
                          <td style="font-size:9px;color:#484f58;text-align:center;">IN PROGRESS</td>
                          <td style="font-size:9px;color:#484f58;text-align:center;">REVIEW</td>
                          <td style="font-size:9px;color:#484f58;text-align:right;">DONE</td>
                        </tr>
                      </table>
                    </div>
                  </div>
                </div>
              </div>
            </td>
          </tr>

          <!-- ─── CTA Button ─── -->
          <tr>
            <td style="padding:28px 40px 0;" align="center">
              <a href="https://ulmind.com/admin/projects/tasks" style="display:inline-block;padding:14px 36px;background:linear-gradient(135deg,#10b981,#059669);border-radius:12px;color:#fff;font-size:14px;font-weight:700;text-decoration:none;letter-spacing:0.02em;box-shadow:0 8px 24px rgba(16,185,129,0.3),0 0 0 1px rgba(16,185,129,0.2);">
                View Task in Dashboard →
              </a>
            </td>
          </tr>

          <!-- ─── Assigned by ─── -->
          <tr>
            <td style="padding:24px 40px 0;" align="center">
              <p style="margin:0;font-size:13px;color:#6e7681;">
                Assigned by <strong style="color:#c9d1d9;">{assigned_by}</strong>
              </p>
            </td>
          </tr>

          <!-- ─── Footer ─── -->
          <tr>
            <td style="padding:28px 40px 32px;">
              <div style="border-top:1px solid rgba(255,255,255,0.06);padding-top:20px;text-align:center;">
                <p style="margin:0;font-size:11px;color:#484f58;line-height:1.6;">
                  ULMiND • Digital Solutions & IT Services<br>
                  This is an automated notification from your team dashboard.
                </p>
                <p style="margin:8px 0 0;font-size:10px;color:#30363d;">
                  © 2026 ULMiND. All rights reserved.
                </p>
              </div>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


async def send_task_assignment_email(
    recipient: str,
    assignee_name: str,
    task_title: str,
    task_description: str,
    project_name: str,
    priority: str,
    due_date: str,
    assigned_by: str,
) -> None:
    """Send an ultra-premium task assignment notification email."""
    html = _build_task_assignment_html(
        assignee_name=assignee_name,
        task_title=task_title,
        task_description=task_description,
        project_name=project_name,
        priority=priority,
        due_date=due_date,
        assigned_by=assigned_by,
    )

    plain = f"""New Task Assignment — ULMiND

Hi {assignee_name},

You've been assigned a new task:

Task: {task_title}
Project: {project_name}
Priority: {priority}
Due: {due_date}
Assigned by: {assigned_by}

Description: {task_description}

View your tasks at: https://ulmind.com/admin/projects/tasks

— ULMiND Team"""

    await send_email(
        recipient=recipient,
        subject=f"🚀 New Task: {task_title} — ULMiND",
        html_body=html,
        text_body=plain,
    )

