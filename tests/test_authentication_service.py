import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.security import hash_password, hash_session_token, verify_password
from app.models.inventory import AuditLog, User, UserSession
from app.schemas.authentication import LoginCreate, PasswordChange
from app.services.authentication import InvalidCredentialsError, authenticate, change_password


@pytest.fixture
def db():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    for table in (User.__table__, UserSession.__table__, AuditLog.__table__):
        table.create(engine)
    with Session(engine) as session:
        yield session


def create_test_user(db: Session) -> User:
    user = User(
        username="bodega1",
        email="bodega1@example.com",
        full_name="Usuario Bodega",
        password_hash=hash_password("provisional-123"),
        role="bodega",
        must_change_password=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_login_creates_hashed_session_and_resets_failures(db):
    user = create_test_user(db)
    user.failed_login_attempts = 2
    db.commit()

    result = authenticate(
        db,
        LoginCreate(username="BODEGA1", password="provisional-123"),
    )

    assert result.user.id == user.id
    assert result.session.token_hash == hash_session_token(result.token)
    assert result.token not in result.session.token_hash
    assert result.user.failed_login_attempts == 0


def test_wrong_password_is_rejected_and_counted(db):
    user = create_test_user(db)

    with pytest.raises(InvalidCredentialsError):
        authenticate(db, LoginCreate(username="bodega1", password="incorrecta"))

    db.refresh(user)
    assert user.failed_login_attempts == 1


def test_password_change_revokes_sessions_and_removes_provisional_flag(db):
    user = create_test_user(db)
    result = authenticate(
        db,
        LoginCreate(username="bodega1", password="provisional-123"),
    )

    change_password(
        db,
        user,
        PasswordChange(
            current_password="provisional-123",
            new_password="definitiva-456",
            reason="Cambio obligatorio de contrasena provisional",
        ),
    )

    db.refresh(user)
    session = db.scalar(select(UserSession).where(UserSession.id == result.session.id))
    assert not user.must_change_password
    assert verify_password("definitiva-456", user.password_hash)
    assert session.revoked_at is not None
