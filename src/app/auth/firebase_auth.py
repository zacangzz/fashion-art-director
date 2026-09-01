from fastapi import Request, HTTPException, status
from firebase_admin import auth
from app.config import get_settings
from app.dependencies import get_db_manager
from app.utils.logger import get_logger

logger = get_logger("auth")

PUBLIC_ROUTES = {
    "/health",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/",
    "/telemetry",
    "/observability",
    "/api/config",
    "/api/models/config",
}


def get_raw_user(request: Request) -> dict:
    """
    Extracts and verifies raw authentication identity from the Authorization header.
    Handles public routes, local dev bypass, and Firebase JWT verification.
    """
    settings = get_settings()
    path = request.url.path

    # Public route check
    if (
        path in PUBLIC_ROUTES
        or path.startswith("/assets/")
        or path.startswith("/api/images/")
        or path.startswith("/api/models")
        or path.startswith("/api/wardrobe/sources/")
        or (path.startswith("/api/wardrobe/items/") and ("/image" in path or "/upscaled-image" in path))
        or path == "/favicon.ico"
    ):
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return {"uid": "public_anonymous", "email": None, "name": "Anonymous", "is_anonymous": True}

    auth_header = request.headers.get("Authorization")

    # Local dev bypass fallback
    if (not auth_header or auth_header == "Bearer local_dev_token") and settings.ENVIRONMENT == "local":
        return {
            "uid": "local_dev_user",
            "email": "developer@local.studio",
            "name": "Local Developer",
            "picture": None,
            "is_anonymous": False,
        }

    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required: Please sign in to access the Fashion Art Director Studio.",
        )

    token = auth_header.split("Bearer ")[1].strip()
    if token == "local_dev_token" and settings.ENVIRONMENT == "local":
        return {
            "uid": "local_dev_user",
            "email": "developer@local.studio",
            "name": "Local Developer",
            "picture": None,
            "is_anonymous": False,
        }

    try:
        decoded_token = auth.verify_id_token(token)
        return {
            "uid": decoded_token["uid"],
            "email": decoded_token.get("email"),
            "name": decoded_token.get("name"),
            "picture": decoded_token.get("picture"),
            "is_anonymous": False,
        }
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired authentication session: {exc}",
        )


def get_current_user_profile(request: Request) -> dict:
    """
    Retrieves user profile and syncs with database without throwing 403 on unapproved status.
    Useful for the `/api/auth/me` endpoint to let users inspect their current status.
    """
    raw_user = get_raw_user(request)
    if raw_user.get("is_anonymous"):
        return {
            "id": raw_user["uid"],
            "uid": raw_user["uid"],
            "email": None,
            "display_name": "Anonymous",
            "role": "guest",
            "status": "anonymous",
            "is_approved": False,
            "is_admin": False,
        }

    settings = get_settings()
    uid = raw_user["uid"]
    email = raw_user.get("email") or f"{uid}@local.user"
    name = raw_user.get("name")
    picture = raw_user.get("picture")

    # Local dev user is always admin
    if uid == "local_dev_user":
        return {
            "id": "local_dev_user",
            "uid": "local_dev_user",
            "email": email,
            "display_name": name or "Local Developer",
            "photo_url": picture,
            "role": "admin",
            "status": "approved",
            "is_approved": True,
            "is_admin": True,
            "total_spend_usd": 0.0,
            "total_tokens": 0,
        }

    try:
        db = get_db_manager()
        is_bootstrap_admin = settings.is_admin_email(email)
        user_record = db.activate_user_on_login(
            uid=uid,
            email=email,
            display_name=name,
            photo_url=picture,
            is_bootstrap_admin=is_bootstrap_admin,
        )
        user_record["uid"] = user_record.get("id", uid)
        user_record["is_approved"] = user_record.get("status") == "approved"
        user_record["is_admin"] = user_record.get("role") == "admin"
        return user_record
    except Exception as exc:
        logger.warning(f"Failed to load or activate user in DB ({uid}): {exc}")
        # Fallback profile if DB lookup fails
        is_bootstrap = settings.is_admin_email(email)
        return {
            "id": uid,
            "uid": uid,
            "email": email,
            "display_name": name or email.split("@")[0],
            "photo_url": picture,
            "role": "admin" if is_bootstrap else "user",
            "status": "approved" if is_bootstrap else "pending_invite",
            "is_approved": is_bootstrap,
            "is_admin": is_bootstrap,
        }


def get_current_user(request: Request) -> dict:
    """
    Main dependency for protected API endpoints.
    Enforces that user is authenticated and is approved on the whitelist.
    """
    profile = get_current_user_profile(request)

    if profile.get("status") == "anonymous":
        return profile

    if profile.get("status") == "disabled":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your studio account has been disabled. Please contact your administrator.",
        )

    if profile.get("status") != "approved":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Access restricted: This studio is invite-only. "
                "Your email is not on the authorized whitelist. Please request access from an administrator."
            ),
        )

    return profile


def get_admin_user(request: Request) -> dict:
    """
    Dependency for administrator-only routes (user management, whitelist control).
    """
    profile = get_current_user(request)
    if profile.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrative privileges required to access this resource.",
        )
    return profile
