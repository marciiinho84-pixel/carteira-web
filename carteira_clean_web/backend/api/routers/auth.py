"""
auth.py — Google OAuth authentication.

Fluxo:
  1. Frontend (NextAuth.js) obtém id_token do Google via OAuth.
  2. NextAuth chama POST /auth/google com {"id_token": "..."}.
  3. Backend valida o token com a API do Google e verifica ALLOWED_EMAIL.
  4. Retorna JWT 30 dias (mesmo formato de antes).

Token de sessão: JWT HS256, 30 dias.
"""
from __future__ import annotations

import os
import secrets
import logging
from datetime import datetime, timedelta, timezone
from typing import Annotated

import requests as _requests
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from jose import jwt, JWTError

log = logging.getLogger("auth")

router = APIRouter(prefix="/auth", tags=["auth"])

# ── Config ────────────────────────────────────────────────────────────────────
_SECRET_KEY    = os.environ.get("JWT_SECRET", secrets.token_hex(32))
_ALGORITHM     = "HS256"
_SESSION_TTL   = timedelta(days=30)

_ALLOWED_EMAIL = os.environ.get("ALLOWED_EMAIL", "marciiinho84@gmail.com").strip().lower()
_GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")


# ── JWT helpers ───────────────────────────────────────────────────────────────

def _create_session_jwt(email: str) -> str:
    expire = datetime.now(timezone.utc) + _SESSION_TTL
    return jwt.encode({"sub": email, "exp": expire}, _SECRET_KEY, algorithm=_ALGORITHM)


def _verify_session_jwt(token: str) -> str:
    try:
        payload = jwt.decode(token, _SECRET_KEY, algorithms=[_ALGORITHM])
        email: str = payload.get("sub", "")
        if not email:
            raise ValueError
        return email
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido ou expirado.",
            headers={"WWW-Authenticate": "Bearer"},
        )


_bearer = HTTPBearer(auto_error=True)


def require_auth(
    creds: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)]
) -> str:
    """Dependency: valida JWT e retorna email do usuário."""
    return _verify_session_jwt(creds.credentials)


# ── Schemas ───────────────────────────────────────────────────────────────────

class GoogleLoginRequest(BaseModel):
    id_token: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/google")
def google_login(body: GoogleLoginRequest) -> TokenResponse:
    """
    Valida um id_token do Google e retorna JWT de sessão.
    Chamado pelo NextAuth.js após o fluxo OAuth.
    """
    try:
        resp = _requests.get(
            "https://oauth2.googleapis.com/tokeninfo",
            params={"id_token": body.id_token},
            timeout=10,
        )
        resp.raise_for_status()
        info = resp.json()
    except Exception as exc:
        log.warning("Google tokeninfo falhou: %s", exc)
        raise HTTPException(status_code=401, detail="Token Google inválido.")

    # Verificar audience quando CLIENT_ID está configurado
    if _GOOGLE_CLIENT_ID and info.get("aud") != _GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=401, detail="Token audience incorreto.")

    email: str = info.get("email", "").strip().lower()
    if not email:
        raise HTTPException(status_code=401, detail="Email ausente no token.")
    if not info.get("email_verified"):
        raise HTTPException(status_code=401, detail="Email não verificado pelo Google.")
    if email != _ALLOWED_EMAIL:
        raise HTTPException(status_code=403, detail="Email não autorizado.")

    log.info("Login Google: %s", email)
    return TokenResponse(access_token=_create_session_jwt(email))


@router.get("/me")
def me(email: Annotated[str, Depends(require_auth)]):
    return {"email": email}
