"""Firebase Auth token verification for FastAPI.

Validates Firebase ID tokens on protected endpoints.
/health remains public. All other routes require valid Bearer token.
"""
from __future__ import annotations

import os
from typing import Optional

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import structlog

logger = structlog.get_logger(__name__)

# Firebase project ID for token verification
FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "secret-medium-491502-n8")

# Optional: disable auth for local development
AUTH_DISABLED = os.getenv("AUTH_DISABLED", "").lower() in ("true", "1", "yes")

_bearer_scheme = HTTPBearer(auto_error=False)


async def verify_firebase_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
) -> dict:
    """Verify Firebase ID token. Returns decoded token claims or raises 401."""
    if AUTH_DISABLED:
        return {"uid": "dev-user", "email": "dev@localhost", "auth_disabled": True}

    if not credentials or not credentials.credentials:
        raise HTTPException(status_code=401, detail="Authentication required")

    token = credentials.credentials

    try:
        from google.oauth2 import id_token
        from google.auth.transport import requests as google_requests

        # Verify the token against Firebase/Google
        claims = id_token.verify_firebase_token(
            token,
            google_requests.Request(),
            audience=FIREBASE_PROJECT_ID,
        )

        # Firebase tokens use 'sub' or 'user_id', not 'uid'
        uid = claims.get("sub") or claims.get("user_id") or claims.get("uid")
        if not uid:
            raise HTTPException(status_code=401, detail="Invalid token: no user identifier")
        claims["uid"] = uid  # Normalize to 'uid' for downstream code

        return claims

    except HTTPException:
        # Re-raise our own HTTPExceptions (don't catch them below)
        raise
    except ValueError as e:
        logger.warning("auth.invalid_token", error=str(e))
        raise HTTPException(status_code=401, detail=f"Invalid or expired token: {e}")
    except Exception as e:
        logger.error("auth.verification_failed", error=str(e), error_type=type(e).__name__)
        raise HTTPException(status_code=401, detail=f"Token verification failed: {type(e).__name__}: {e}")


# Convenience alias
require_auth = Depends(verify_firebase_token)
