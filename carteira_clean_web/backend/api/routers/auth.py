"""
auth.py — Magic link authentication.

Fluxo:
  1. POST /auth/request-link  {"email": "..."}
     → gera token, loga no console, retorna {"message": "Link logged"}
  2. GET  /auth/verify?token=...
     → valida token, retorna {"access_token": JWT, "token_type": "bearer"}
  3. GET  /auth/me  (Bearer JWT)
     → retorna {"email": "..."}

Token de sessão: JWT HS256, 30 dias.
Magic token: uuid4 armazenado em memória, TTL 1h.

Para app pessoal: apenas e-mails na ALLOWED_EMAILS list podem solicitar link.
"""
from __future__ import annotations

import os
import secrets
import logging
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from jose import jwt, JWTError

log = logging.getLogger("auth")

router = APIRouter(prefix="/auth", tags=["auth"])

# ── Config ────────────────────────────────────────────────────────────────────
_SECRET_KEY = os.environ.get("JWT_SECRET", secrets.token_hex(32))
_ALGORITHM   = "HS256"
_SESSION_TTL = timedelta(days=30)
_MAGIC_TTL   = timedelta(hours=1)

ALLOWED_EMAILS: set[str] = {
    e.strip().lower()
    for e in os.environ.get("ALLOWED_EMAILS", "marciiinho84@gmail.com").split(",")
    if e.strip()
}

# ── In-memory magic token store ───────────────────────────────────────────────
# {token: {"email": str, "expires": datetime}}
_magic_tokens: dict[str, dict] = {}


# ── Helpers ───────────────────────────────────────────────────────────────────

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

class MagicLinkRequest(BaseModel):
    email: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/request-link", status_code=200)
def request_magic_link(body: MagicLinkRequest):
    email = body.email.strip().lower()
    if email not in ALLOWED_EMAILS:
        # Não vaza se o e-mail está na lista (segurança básica)
        return {"message": "Se o e-mail estiver autorizado, o link foi registrado."}

    token = secrets.token_urlsafe(32)
    _magic_tokens[token] = {
        "email": email,
        "expires": datetime.now(timezone.utc) + _MAGIC_TTL,
    }

    # Base URL: env var ou fallback para o domínio público
    base_url = os.environ.get("FRONTEND_URL", "https://minhacarteira.duckdns.org")
    link = f"{base_url}/auth/verify?token={token}"

    # Loga no stdout do container (usuário copia do `docker logs`)
    log.warning("=" * 60)
    log.warning("🔗  MAGIC LINK (válido por 1h):")
    log.warning("    %s", link)
    log.warning("=" * 60)

    return {"message": "Link de acesso registrado nos logs do servidor."}


@router.get("/verify")
def verify_magic_token(token: str):
    entry = _magic_tokens.get(token)
    if not entry:
        raise HTTPException(status_code=400, detail="Token inválido.")
    if datetime.now(timezone.utc) > entry["expires"]:
        _magic_tokens.pop(token, None)
        raise HTTPException(status_code=400, detail="Token expirado.")

    _magic_tokens.pop(token)  # one-time use
    access_token = _create_session_jwt(entry["email"])
    return TokenResponse(access_token=access_token)


@router.get("/me")
def me(email: Annotated[str, Depends(require_auth)]):
    return {"email": email}
