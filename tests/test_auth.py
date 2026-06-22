from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.auth import get_current_session, get_current_user, require_permission
from app.core.permissions import Permission
from app.core.security import hash_password, hash_session_token, verify_password


class FakeSession:
    def __init__(self, user):
        self.user = user

    def get(self, model, user_id):
        return self.user if self.user and self.user.id == user_id else None


def test_missing_session_cookie_is_rejected():
    with pytest.raises(HTTPException) as error:
        get_current_session(None, FakeSession(None))

    assert error.value.status_code == 401


def test_inactive_user_is_rejected():
    user = SimpleNamespace(id=3, is_active=False, role="ventas", must_change_password=False)
    session = SimpleNamespace(user_id=3)
    with pytest.raises(HTTPException) as error:
        get_current_user(session, FakeSession(user))

    assert error.value.status_code == 401


def test_role_without_permission_is_rejected():
    user = SimpleNamespace(id=4, is_active=True, role="ventas", must_change_password=False)
    dependency = require_permission(Permission.confirm_dispatch)

    with pytest.raises(HTTPException) as error:
        dependency(user)

    assert error.value.status_code == 403


def test_allowed_role_returns_the_identified_user():
    user = SimpleNamespace(id=5, is_active=True, role="bodega", must_change_password=False)
    dependency = require_permission(Permission.confirm_dispatch)

    assert dependency(user) is user


def test_temporary_password_blocks_business_operations():
    user = SimpleNamespace(id=6, is_active=True, role="bodega", must_change_password=True)
    dependency = require_permission(Permission.confirm_dispatch)

    with pytest.raises(HTTPException) as error:
        dependency(user)

    assert error.value.status_code == 403


def test_password_is_hashed_and_verified_without_plain_text_storage():
    encoded = hash_password("una-contrasena-segura")

    assert "una-contrasena-segura" not in encoded
    assert verify_password("una-contrasena-segura", encoded)
    assert not verify_password("incorrecta", encoded)


def test_session_tokens_are_stored_as_hashes():
    token = "token-visible-solo-en-cookie"

    assert hash_session_token(token) != token
    assert len(hash_session_token(token)) == 64
