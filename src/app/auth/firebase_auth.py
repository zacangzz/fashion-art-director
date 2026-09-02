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
    Supports secure admin proxying/impersonation via `X-Proxy-User-Id` header.
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
            "is_proxy": False,
            "proxied_by": None,
            "real_user": None,
        }

    settings = get_settings()
    uid = raw_user["uid"]
    email = raw_user.get("email") or f"{uid}@local.user"
    name = raw_user.get("name")
    picture = raw_user.get("picture")

    # Local dev user is always admin, sync with DB for real-time spend tracking
    if uid == "local_dev_user":
        try:
            db = get_db_manager()
            caller_record = db.activate_user_on_login(
                uid="local_dev_user",
                email=email,
                display_name=name or "Local Developer",
                photo_url=picture,
                is_bootstrap_admin=True,
            )
            caller_record["uid"] = "local_dev_user"
            caller_record["is_approved"] = True
            caller_record["is_admin"] = True
        except Exception:
            caller_record = {
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
                "total_spend_sgd": 0.0,
                "total_tokens": 0,
            }
    else:
        try:
            db = get_db_manager()
            is_bootstrap_admin = settings.is_admin_email(email)
            caller_record = db.activate_user_on_login(
                uid=uid,
                email=email,
                display_name=name,
                photo_url=picture,
                is_bootstrap_admin=is_bootstrap_admin,
            )
            caller_record["uid"] = caller_record.get("id", uid)
            caller_record["is_approved"] = caller_record.get("status") == "approved"
            caller_record["is_admin"] = caller_record.get("role") == "admin"
        except Exception as exc:
            logger.warning(f"Failed to load or activate user in DB ({uid}): {exc}")
            # Fallback profile if DB lookup fails
            is_bootstrap = settings.is_admin_email(email)
            caller_record = {
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

    # Check for proxy / impersonation header
    proxy_target_id = request.headers.get("X-Proxy-User-Id") or request.headers.get("X-Impersonate-User-Id")
    if proxy_target_id:
        proxy_target_id = proxy_target_id.strip()

    # If no proxy header or proxying self, return regular authentic profile
    if not proxy_target_id or proxy_target_id == caller_record.get("id") or proxy_target_id == caller_record.get("uid") or proxy_target_id == caller_record.get("email"):
        caller_record["is_proxy"] = False
        caller_record["proxied_by"] = None
        caller_record["real_user"] = None
        return caller_record

    # Verify that the authentic caller has admin privileges
    if not caller_record.get("is_admin") and caller_record.get("role") != "admin":
        logger.warning(
            f"Unauthorized proxy attempt: user '{caller_record.get('email')}' attempted to proxy '{proxy_target_id}'"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrative privileges required to proxy as another user.",
        )

    # Locate the target user from database
    db = get_db_manager()
    target_user = db.get_user(proxy_target_id)
    if not target_user and "@" in proxy_target_id:
        target_user = db.get_user_by_email(proxy_target_id)

    if not target_user:
        # Fallback search across list of users
        try:
            users_list = db.list_users(limit=200)
            for u in users_list:
                if u.get("id") == proxy_target_id or u.get("uid") == proxy_target_id or u.get("email") == proxy_target_id:
                    target_user = u
                    break
        except Exception as err:
            logger.debug(f"User list fallback search note: {err}")

    if not target_user:
        logger.warning(f"Admin '{caller_record.get('email')}' attempted to proxy non-existent user '{proxy_target_id}'")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Proxy target user '{proxy_target_id}' not found on the studio whitelist.",
        )

    # Construct the proxy profile reflecting the target user's perspective
    target_uid = target_user.get("id") or target_user.get("uid") or proxy_target_id
    target_email = target_user.get("email")
    target_role = target_user.get("role", "user")
    target_status = target_user.get("status", "approved")

    proxy_profile = {
        "id": target_uid,
        "uid": target_uid,
        "email": target_email,
        "display_name": target_user.get("display_name") or (target_email.split("@")[0] if target_email else "Studio Member"),
        "photo_url": target_user.get("photo_url"),
        "role": target_role,
        "status": target_status,
        "is_approved": target_status == "approved",
        "is_admin": target_role == "admin",
        "total_spend_usd": float(target_user.get("total_spend_usd") or 0.0),
        "total_spend_sgd": float(target_user.get("total_spend_sgd") or 0.0),
        "total_tokens": int(target_user.get("total_tokens") or 0),
        "created_at": target_user.get("created_at"),
        "approved_at": target_user.get("approved_at"),
        "last_login_at": target_user.get("last_login_at"),
        "is_proxy": True,
        "proxied_by": {
            "id": caller_record.get("id"),
            "uid": caller_record.get("uid"),
            "email": caller_record.get("email"),
            "display_name": caller_record.get("display_name"),
            "role": caller_record.get("role"),
        },
        "real_user": caller_record,
    }
    logger.info(f"Admin '{caller_record.get('email')}' active proxy as user '{target_email}' (uid={target_uid})")
    return proxy_profile


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
    Grants access if current profile is admin OR if the authentic caller who is proxying is admin.
    """
    profile = get_current_user_profile(request)

    # If effective profile is admin
    if profile.get("role") == "admin":
        return profile

    # If proxying as a non-admin, verify that the real caller is an admin
    if profile.get("is_proxy") and profile.get("real_user", {}).get("role") == "admin":
        return profile.get("real_user")

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Administrative privileges required to access this resource.",
    )
