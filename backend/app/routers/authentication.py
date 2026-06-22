from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.auth import get_current_session, get_current_user
from app.core.config import get_settings
from app.db.session import get_db
from app.models.inventory import User, UserSession
from app.schemas.authentication import (
    LoginCreate,
    LoginRead,
    MessageRead,
    PasswordChange,
    SetupStatusRead,
)
from app.services.authentication import (
    AccountLockedError,
    InvalidCredentialsError,
    PasswordUnchangedError,
    authenticate,
    change_password,
    close_session,
    current_user_read,
    needs_bootstrap,
)


router = APIRouter(prefix="/auth", tags=["authentication"])
settings = get_settings()


@router.get("/setup-status", response_model=SetupStatusRead)
def read_setup_status(db: Session = Depends(get_db)) -> SetupStatusRead:
    return SetupStatusRead(needs_bootstrap=needs_bootstrap(db))


@router.post("/login", response_model=LoginRead)
def login(
    credentials: LoginCreate,
    response: Response,
    db: Session = Depends(get_db),
) -> LoginRead:
    try:
        result = authenticate(db, credentials)
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contrasena incorrectos.",
        ) from exc
    except AccountLockedError as exc:
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail=f"Cuenta bloqueada temporalmente. Intenta nuevamente en {settings.login_lock_minutes} minutos.",
        ) from exc

    response.set_cookie(
        key=settings.session_cookie_name,
        value=result.token,
        max_age=settings.session_hours * 60 * 60,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )
    return LoginRead(user=current_user_read(result.user), expires_at=result.session.expires_at)


@router.post("/logout", response_model=MessageRead)
def logout(
    response: Response,
    db: Session = Depends(get_db),
    current_session: UserSession = Depends(get_current_session),
) -> MessageRead:
    close_session(db, current_session)
    response.delete_cookie(settings.session_cookie_name, path="/")
    return MessageRead(message="Sesion cerrada.")


@router.post("/change-password", response_model=MessageRead)
def update_own_password(
    change_data: PasswordChange,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MessageRead:
    try:
        change_password(db, current_user, change_data)
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="La contrasena actual no es correcta.",
        ) from exc
    except PasswordUnchangedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La nueva contrasena debe ser diferente.",
        ) from exc

    response.delete_cookie(settings.session_cookie_name, path="/")
    return MessageRead(message="Contrasena cambiada. Inicia sesion nuevamente.")
