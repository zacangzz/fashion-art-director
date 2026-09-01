from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field

from app.auth.firebase_auth import get_current_user_profile, get_admin_user, get_current_user
from app.dependencies import get_db_manager
from app.db.database import FirestoreManager
from app.utils.logger import get_logger

logger = get_logger("api_auth")

router = APIRouter(prefix="/api/auth", tags=["auth"])


class InviteUserRequest(BaseModel):
    email: str = Field(..., description="Email address to invite / pre-authorize")
    role: str = Field("user", description="Role to assign: 'user' or 'admin'")


class UpdateUserStatusRequest(BaseModel):
    status: Optional[str] = Field(None, description="'approved', 'pending_invite', 'disabled', or 'unauthorized'")
    role: Optional[str] = Field(None, description="'user' or 'admin'")


class UserProfileResponse(BaseModel):
    id: str
    uid: str
    email: Optional[str] = None
    display_name: Optional[str] = None
    photo_url: Optional[str] = None
    role: str
    status: str
    is_approved: bool
    is_admin: bool
    total_spend_usd: float = 0.0
    total_tokens: int = 0
    created_at: Optional[str] = None
    approved_at: Optional[str] = None
    last_login_at: Optional[str] = None


@router.get("/me", response_model=UserProfileResponse)
def get_my_profile(request: Request):
    """
    Returns the authenticated user's profile and approval status.
    Does not throw 403 if unapproved, so clients can display restriction details.
    """
    profile = get_current_user_profile(request)
    return UserProfileResponse(
        id=profile.get("id") or profile.get("uid") or "anonymous",
        uid=profile.get("uid") or profile.get("id") or "anonymous",
        email=profile.get("email"),
        display_name=profile.get("display_name"),
        photo_url=profile.get("photo_url"),
        role=profile.get("role", "user"),
        status=profile.get("status", "unauthorized"),
        is_approved=profile.get("is_approved", False),
        is_admin=profile.get("is_admin", False),
        total_spend_usd=profile.get("total_spend_usd", 0.0),
        total_tokens=profile.get("total_tokens", 0),
        created_at=profile.get("created_at"),
        approved_at=profile.get("approved_at"),
        last_login_at=profile.get("last_login_at"),
    )


@router.get("/users")
def list_authorized_users(
    admin_user: dict = Depends(get_admin_user),
    db: FirestoreManager = Depends(get_db_manager),
):
    """
    (Admin only) Returns all registered users and pending invitations in the studio whitelist.
    """
    users = db.list_users(limit=200)
    
    # Calculate summary metrics
    total_users = len(users)
    approved_count = sum(1 for u in users if u.get("status") == "approved")
    pending_count = sum(1 for u in users if u.get("status") == "pending_invite")
    disabled_count = sum(1 for u in users if u.get("status") == "disabled")
    total_spend = sum(u.get("total_spend_usd", 0.0) for u in users)

    return {
        "users": users,
        "summary": {
            "total_users": total_users,
            "approved_count": approved_count,
            "pending_count": pending_count,
            "disabled_count": disabled_count,
            "total_spend_usd": round(total_spend, 4),
        }
    }


@router.post("/invite")
def invite_user(
    body: InviteUserRequest,
    admin_user: dict = Depends(get_admin_user),
    db: FirestoreManager = Depends(get_db_manager),
):
    """
    (Admin only) Pre-authorizes an email address to join the Fashion Art Director Studio.
    """
    email = body.email.strip().lower()
    if not email or "@" not in email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A valid email address is required.",
        )

    if body.role not in ("user", "admin"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Role must be either 'user' or 'admin'.",
        )

    invited_by = admin_user.get("uid") or admin_user.get("email") or "admin"
    record = db.create_user_invite(email=email, role=body.role, invited_by=invited_by)
    return {
        "status": "success",
        "message": f"Successfully pre-authorized {email} as {body.role}.",
        "user": record,
    }


@router.patch("/users/{user_id}/status")
def update_user_status_endpoint(
    user_id: str,
    body: UpdateUserStatusRequest,
    admin_user: dict = Depends(get_admin_user),
    db: FirestoreManager = Depends(get_db_manager),
):
    """
    (Admin only) Updates a user's approval status or role.
    """
    # Prevent admin from disabling themselves
    if user_id == admin_user.get("uid") and body.status == "disabled":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot disable your own administrator account.",
        )

    updated = db.update_user_status(user_id=user_id, status=body.status, role=body.role)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID '{user_id}' not found.",
        )

    return {
        "status": "success",
        "message": f"User '{user_id}' updated successfully.",
        "user": updated,
    }


@router.delete("/users/{user_id}")
def delete_user_endpoint(
    user_id: str,
    admin_user: dict = Depends(get_admin_user),
    db: FirestoreManager = Depends(get_db_manager),
):
    """
    (Admin only) Removes a user or pending invite from the whitelist.
    """
    if user_id == admin_user.get("uid"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot delete your own administrator account.",
        )

    success = db.delete_user(user_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID '{user_id}' not found.",
        )

    return {
        "status": "success",
        "message": f"User '{user_id}' deleted successfully.",
    }
