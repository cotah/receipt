from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.utils.auth_utils import get_current_user
from app.database import get_service_client
from app.services.email_service import send_email

router = APIRouter(prefix="/feedback", tags=["feedback"])


class FeedbackRequest(BaseModel):
    message: str
    category: str = "bug"  # bug, suggestion, other


@router.post("")
async def submit_feedback(
    body: FeedbackRequest,
    user_id: str = Depends(get_current_user),
):
    if not body.message or len(body.message.strip()) < 5:
        raise HTTPException(status_code=400, detail="Message too short")

    db = get_service_client()

    # Get user info
    profile = (
        db.table("profiles")
        .select("email, full_name")
        .eq("id", user_id)
        .maybe_single()
        .execute()
    )
    user_email = (profile.data or {}).get("email", "unknown")
    user_name = ((profile.data or {}).get("full_name") or "User")

    # Save to DB
    db.table("feedback").insert({
        "user_id": user_id,
        "email": user_email,
        "category": body.category,
        "message": body.message.strip(),
    }).execute()

    # Send notification to team
    await send_email(
        to="report@smartdocket.ie",
        subject=f"[{body.category.upper()}] New feedback from {user_name}",
        html=f"""
        <h2>New Feedback</h2>
        <p><strong>From:</strong> {user_name} ({user_email})</p>
        <p><strong>Category:</strong> {body.category}</p>
        <p><strong>Message:</strong></p>
        <blockquote style="border-left: 3px solid #1A4D35; padding-left: 12px; color: #333;">
            {body.message.strip()}
        </blockquote>
        """,
    )

    # Send auto-reply to user
    first_name = user_name.split()[0] if user_name else "there"
    await send_email(
        to=user_email,
        subject="We received your report — SmartDocket",
        html=f"""
        <div style="font-family: 'Segoe UI', Arial, sans-serif; max-width: 500px; margin: 0 auto; padding: 24px;">
            <div style="background: #1A4D35; border-radius: 12px 12px 0 0; padding: 20px; text-align: center;">
                <h1 style="color: #fff; margin: 0; font-size: 22px;">SmartDocket</h1>
            </div>
            <div style="background: #fff; border: 1px solid #E5E7EB; border-top: none; border-radius: 0 0 12px 12px; padding: 24px;">
                <p style="font-size: 16px; color: #1A1A1A;">Hi {first_name},</p>
                <p style="font-size: 14px; color: #4B5563; line-height: 1.6;">
                    Thank you for taking the time to report this issue. We've received your feedback
                    and our team is looking into it.
                </p>
                <p style="font-size: 14px; color: #4B5563; line-height: 1.6;">
                    We'll get back to you within <strong>48 hours</strong> with an update.
                </p>
                <p style="font-size: 14px; color: #4B5563; line-height: 1.6;">
                    Your help makes SmartDocket better for everyone in the community. We truly appreciate it! 💚
                </p>
                <p style="font-size: 14px; color: #6B7280; margin-top: 24px;">
                    — The SmartDocket Team
                </p>
            </div>
        </div>
        """,
    )

    return {"status": "sent", "message": "Thank you for your feedback!"}
