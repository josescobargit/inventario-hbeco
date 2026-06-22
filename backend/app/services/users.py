import json
from datetime import datetime, timezone

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.inventory import AuditLog, User, UserRole, UserSession
from app.schemas.users import UserBootstrapCreate, UserCreate, UserPasswordReset, UserUpdate


class UserAlreadyExistsError(Exception):
    pass


class UserNotFoundError(Exception):
    pass


class UserBootstrapClosedError(Exception):
    pass


class LastPrincipalError(Exception):
    pass


def _normalized_email(email: str) -> str:
    normalized = email.strip().lower()
    if "@" not in normalized:
        raise ValueError("El correo no es valido.")
    return normalized


def _normalized_username(username: str) -> str:
    return username.strip().lower()


def bootstrap_principal(db: Session, user_data: UserBootstrapCreate) -> User:
    if db.scalar(select(func.count(User.id))) != 0:
        raise UserBootstrapClosedError()

    user = User(
        username=_normalized_username(user_data.username),
        email=_normalized_email(user_data.email),
        full_name=user_data.full_name.strip(),
        password_hash=hash_password(user_data.password),
        role=UserRole.principal.value,
        must_change_password=False,
    )
    db.add(user)
    db.flush()
    db.add(
        AuditLog(
            user_id=user.id,
            action="bootstrap_principal",
            entity_type="user",
            entity_id=user.id,
            before_json=None,
            after_json=json.dumps(
                {"username": user.username, "email": user.email, "role": user.role},
                ensure_ascii=True,
            ),
            reason=user_data.reason,
        )
    )
    db.commit()
    db.refresh(user)
    return user


def list_users(db: Session) -> list[User]:
    return list(db.scalars(select(User).order_by(User.full_name, User.id)).all())


def create_user(db: Session, user_data: UserCreate, actor_user_id: int) -> User:
    email = _normalized_email(user_data.email)
    username = _normalized_username(user_data.username)
    if db.scalar(select(User.id).where(User.email == email)) is not None:
        raise UserAlreadyExistsError(email)
    if db.scalar(select(User.id).where(User.username == username)) is not None:
        raise UserAlreadyExistsError(username)

    user = User(
        username=username,
        email=email,
        full_name=user_data.full_name.strip(),
        password_hash=hash_password(user_data.temporary_password),
        role=user_data.role.value,
        must_change_password=True,
    )
    db.add(user)
    db.flush()
    db.add(
        AuditLog(
            user_id=actor_user_id,
            action="create_user",
            entity_type="user",
            entity_id=user.id,
            before_json=None,
            after_json=json.dumps(
                {
                    "username": user.username,
                    "email": user.email,
                    "full_name": user.full_name,
                    "role": user.role,
                },
                ensure_ascii=True,
            ),
            reason=user_data.reason,
        )
    )
    db.commit()
    db.refresh(user)
    return user


def update_user(db: Session, user_id: int, user_data: UserUpdate, actor_user_id: int) -> User:
    user = db.scalar(select(User).where(User.id == user_id).with_for_update())
    if user is None:
        raise UserNotFoundError(str(user_id))

    before = {
        "full_name": user.full_name,
        "role": user.role,
        "is_active": user.is_active,
    }
    next_role = user_data.role.value if user_data.role is not None else user.role
    next_active = user.is_active if user_data.is_active is None else user_data.is_active

    removes_active_principal = (
        user.role == UserRole.principal.value
        and user.is_active
        and (next_role != UserRole.principal.value or not next_active)
    )
    if removes_active_principal:
        principal_count = db.scalar(
            select(func.count(User.id)).where(
                User.role == UserRole.principal.value,
                User.is_active.is_(True),
            )
        )
        if int(principal_count or 0) <= 1:
            raise LastPrincipalError()

    if user_data.full_name is not None:
        user.full_name = user_data.full_name.strip()
    user.role = next_role
    user.is_active = next_active

    if not user.is_active:
        now = datetime.now(timezone.utc)
        db.execute(
            update(UserSession)
            .where(UserSession.user_id == user.id, UserSession.revoked_at.is_(None))
            .values(revoked_at=now)
        )

    after = {
        "full_name": user.full_name,
        "role": user.role,
        "is_active": user.is_active,
    }
    db.add(
        AuditLog(
            user_id=actor_user_id,
            action="update_user",
            entity_type="user",
            entity_id=user.id,
            before_json=json.dumps(before, ensure_ascii=True),
            after_json=json.dumps(after, ensure_ascii=True),
            reason=user_data.reason,
        )
    )
    db.commit()
    db.refresh(user)
    return user


def reset_user_password(
    db: Session,
    user_id: int,
    reset_data: UserPasswordReset,
    actor_user_id: int,
) -> User:
    user = db.scalar(select(User).where(User.id == user_id).with_for_update())
    if user is None:
        raise UserNotFoundError(str(user_id))

    user.password_hash = hash_password(reset_data.temporary_password)
    user.must_change_password = True
    user.failed_login_attempts = 0
    user.locked_until = None

    now = datetime.now(timezone.utc)
    db.execute(
        update(UserSession)
        .where(UserSession.user_id == user.id, UserSession.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    db.add(
        AuditLog(
            user_id=actor_user_id,
            action="reset_user_password",
            entity_type="user",
            entity_id=user.id,
            before_json=None,
            after_json=json.dumps({"must_change_password": True}, ensure_ascii=True),
            reason=reset_data.reason,
        )
    )
    db.commit()
    db.refresh(user)
    return user
