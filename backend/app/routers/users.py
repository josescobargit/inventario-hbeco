from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_permission
from app.core.permissions import Permission
from app.db.session import get_db
from app.models.inventory import User
from app.schemas.users import (
    CurrentUserRead,
    UserBootstrapCreate,
    UserCreate,
    UserPasswordReset,
    UserRead,
    UserUpdate,
)
from app.services.authentication import current_user_read
from app.services.users import (
    LastPrincipalError,
    UserAlreadyExistsError,
    UserBootstrapClosedError,
    UserNotFoundError,
    bootstrap_principal,
    create_user,
    list_users,
    reset_user_password,
    update_user,
)


router = APIRouter(prefix="/users", tags=["users"])


@router.post("/bootstrap", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_first_principal(
    user_data: UserBootstrapCreate,
    db: Session = Depends(get_db),
) -> User:
    try:
        return bootstrap_principal(db, user_data)
    except UserBootstrapClosedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El usuario principal inicial ya fue creado.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.get("/me", response_model=CurrentUserRead)
def read_current_user(current_user: User = Depends(get_current_user)) -> CurrentUserRead:
    return current_user_read(current_user)


@router.get("", response_model=list[UserRead])
def read_users(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(Permission.manage_users)),
) -> list[User]:
    return list_users(db)


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def add_user(
    user_data: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.manage_users)),
) -> User:
    try:
        return create_user(db, user_data, current_user.id)
    except UserAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ya existe un usuario con el identificador {exc}.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.patch("/{user_id}", response_model=UserRead)
def edit_user(
    user_id: int,
    user_data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.manage_users)),
) -> User:
    try:
        return update_user(db, user_id, user_data, current_user.id)
    except UserNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Usuario no encontrado: {exc}.",
        ) from exc
    except LastPrincipalError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Debe quedar al menos un usuario principal activo.",
        ) from exc


@router.post("/{user_id}/reset-password", response_model=UserRead)
def reset_password(
    user_id: int,
    reset_data: UserPasswordReset,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.manage_users)),
) -> User:
    try:
        return reset_user_password(db, user_id, reset_data, current_user.id)
    except UserNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Usuario no encontrado: {exc}.",
        ) from exc
