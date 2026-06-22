from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Annotated, Optional

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.permissions import Permission, has_permission
from app.core.security import hash_session_token
from app.db.session import get_db
from app.models.inventory import User, UserSession


settings = get_settings()


def get_current_session(
    session_token: Annotated[
        Optional[str],
        Cookie(alias=settings.session_cookie_name),
    ] = None,
    db: Session = Depends(get_db),
) -> UserSession:
    if not session_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Debes iniciar sesion.",
        )

    session = db.scalar(
        select(UserSession).where(UserSession.token_hash == hash_session_token(session_token))
    )
    if session is None or session.revoked_at is not None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="La sesion no es valida.",
        )

    expires_at = session.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="La sesion vencio. Inicia sesion nuevamente.",
        )
    return session


def get_current_user(
    current_session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
) -> User:
    user = db.get(User, current_session.user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario inexistente o inactivo.",
        )
    return user


def require_permission(permission: Permission) -> Callable[..., User]:
    def permission_dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.must_change_password:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Debes cambiar tu contrasena provisional antes de continuar.",
            )
        if not has_permission(current_user.role, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Tu rol no permite realizar esta operacion.",
            )
        return current_user

    return permission_dependency
