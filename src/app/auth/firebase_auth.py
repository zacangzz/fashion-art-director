from fastapi import Request, HTTPException, status
from firebase_admin import auth
from app.config import get_settings

PUBLIC_ROUTES = {
    "/health",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/",
    "/telemetry",
    "/observability",
    "/api/config",
}


def get_current_user(request: Request) -> dict:
    settings = get_settings()
    path = request.url.path

    # Allow public routes without authentication
    if path in PUBLIC_ROUTES or path.startswith("/assets/") or path.startswith("/api/images/") or path == "/favicon.ico":
        return {"uid": "public_anonymous", "email": None, "name": "Anonymous"}

    auth_header = request.headers.get("Authorization")

    # Local dev bypass fallback if no header provided
    if not auth_header and settings.ENVIRONMENT == "local":
        return {
            "uid": "local_dev_user",
            "email": "developer@local.studio",
            "name": "Local Developer",
        }

    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or malformed Authorization Bearer token header.",
        )

    token = auth_header.split("Bearer ")[1].strip()
    try:
        decoded_token = auth.verify_id_token(token)
        return {
            "uid": decoded_token["uid"],
            "email": decoded_token.get("email"),
            "name": decoded_token.get("name"),
        }
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired Firebase Auth token: {exc}",
        )
