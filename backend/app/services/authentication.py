from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.permissions import permission_values_for_role
from app.core.security import generate_session_token, hash_password, hash_session_token, verify_password
from app.models.inventory import AuditLog, User, UserSession
from app.schemas.authentication import LoginCreate, PasswordChange
from app.schemas.users import CurrentUserRead


settings = get_settings()
DUMMY_PASSWORD_HASH = hash_password("invalid-password-placeholder")


class InvalidCredentialsError(Exception):
    pass


class AccountLockedError(Exception):
    pass


class PasswordUnchangedError(Exception):
    pass


@dataclass
class LoginResult:
    user: User
    session: UserSession
    token: str


def needs_bootstrap(db: Session) -> bool:
    return int(db.scalar(select(func.count(User.id))) or 0) == 0


def authenticate(db: Session, credentials: LoginCreate) -> LoginResult:
    username = credentials.username.strip().lower()
    user = db.scalar(select(User).where(User.username == username).with_for_update())
    now = datetime.now(timezone.utc)

    if user is None:
        verify_password(credentials.password, DUMMY_PASSWORD_HASH)
        raise InvalidCredentialsError()
    if not user.is_active:
        raise InvalidCredentialsError()
    if user.locked_until is not None:
        locked_until = user.locked_until
        if locked_until.tzinfo is None:
            locked_until = locked_until.replace(tzinfo=timezone.utc)
        if locked_until > now:
            raise AccountLockedError()

    if not verify_password(credentials.password, user.password_hash):
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= settings.login_max_attempts:
            user.locked_until = now + timedelta(minutes=settings.login_lock_minutes)
        db.add(
            AuditLog(
                user_id=user.id,
                action="login_failed",
                entity_type="user",
                entity_id=user.id,
                before_json=None,
                after_json=None,
                reason="Credenciales internas incorrectas",
            )
        )
        db.commit()
        raise InvalidCredentialsError()

    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login_at = now

    token = generate_session_token()
    session = UserSession(
        user_id=user.id,
        token_hash=hash_session_token(token),
        expires_at=now + timedelta(hours=settings.session_hours),
    )
    db.add(session)
    db.flush()
    db.add(
        AuditLog(
            user_id=user.id,
            action="login_success",
            entity_type="user_session",
            entity_id=session.id,
            before_json=None,
            after_json=None,
            reason="Inicio de sesion interno",
        )
    )
    db.commit()
    db.refresh(user)
    db.refresh(session)
    return LoginResult(user=user, session=session, token=token)


def current_user_read(user: User) -> CurrentUserRead:
    return CurrentUserRead(
        id=user.id,
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        is_active=user.is_active,
        must_change_password=user.must_change_password,
        created_at=user.created_at,
        permissions=permission_values_for_role(user.role),
    )


def close_session(db: Session, session: UserSession) -> None:
    if session.revoked_at is None:
        session.revoked_at = datetime.now(timezone.utc)
        db.add(
            AuditLog(
                user_id=session.user_id,
                action="logout",
                entity_type="user_session",
                entity_id=session.id,
                before_json=None,
                after_json=None,
                reason="Cierre de sesion",
            )
        )
        db.commit()


def change_password(
    db: Session,
    user: User,
    change_data: PasswordChange,
) -> None:
    locked_user = db.scalar(select(User).where(User.id == user.id).with_for_update())
    if locked_user is None or not verify_password(change_data.current_password, locked_user.password_hash):
        raise InvalidCredentialsError()
    if verify_password(change_data.new_password, locked_user.password_hash):
        raise PasswordUnchangedError()

    locked_user.password_hash = hash_password(change_data.new_password)
    locked_user.must_change_password = False
    locked_user.failed_login_attempts = 0
    locked_user.locked_until = None
    now = datetime.now(timezone.utc)
    db.execute(
        update(UserSession)
        .where(UserSession.user_id == locked_user.id, UserSession.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    db.add(
        AuditLog(
            user_id=locked_user.id,
            action="change_password",
            entity_type="user",
            entity_id=locked_user.id,
            before_json=None,
            after_json=None,
            reason=change_data.reason,
        )
    )
    db.commit()
