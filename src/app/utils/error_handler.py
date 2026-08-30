import logging
from fastapi import HTTPException, status

logger = logging.getLogger(__name__)

def parse_and_raise_http_error(exc: Exception, model_name: str = "", context: str = ""):
    """
    Translates raw backend / Google GenAI exceptions into descriptive, user-actionable HTTPExceptions.
    """
    err_str = str(exc)
    logger.error(f"Error in {context}: {err_str}", exc_info=True)

    if "404" in err_str or "NOT_FOUND" in err_str:
        extra_note = ""
        if "lite" in (model_name or "").lower():
            extra_note = " Note: Lite image models only support standard 1K resolution."
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Google AI Model Not Found (404): The model '{model_name}' was not found "
                f"or is not enabled for your API key. Please check your VISION_MODEL / IMAGEN_MODEL "
                f"settings in .env and verify model access in Google AI Studio (https://aistudio.google.com).{extra_note} "
                f"Raw details: {err_str}"
            ),
        )

    if "401" in err_str or "API_KEY_INVALID" in err_str or "UNAUTHENTICATED" in err_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=(
                "Google AI Authentication Error (401 Unauthorized): Your GEMINI_API_KEY in .env "
                "is invalid, expired, or missing. Please verify your API key at https://aistudio.google.com."
            ),
        )

    if "403" in err_str or "PERMISSION_DENIED" in err_str:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Google AI Permission Denied (403 Forbidden): Your API key does not have permission "
                f"to access model '{model_name}'. Check your project permissions in Google AI Studio. "
                f"Raw details: {err_str}"
            ),
        )

    if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                "Google AI Quota Exceeded (429 Too Many Requests): Rate limit or quota limit reached "
                "in Google AI Studio. Please wait a few moments before retrying."
            ),
        )

    if "400" in err_str or "INVALID_ARGUMENT" in err_str:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Google AI Invalid Request (400 Bad Request): {err_str}",
        )

    if isinstance(exc, FileNotFoundError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Resource Not Found: {err_str}",
        )

    # General 502 Bad Gateway
    prefix = f"{context} failed" if context else "Service error"
    raise HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail=f"{prefix}: {err_str}",
    )
