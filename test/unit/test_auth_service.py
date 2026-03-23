from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from services.auth import build_auth_status_payload, ensure_auth_platform


def test_ensure_auth_platform_rejects_unsupported_platform():
    with pytest.raises(HTTPException) as exc_info:
        ensure_auth_platform("unknown", None)

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "不支持的平台: unknown"


def test_ensure_auth_platform_rejects_platform_without_login():
    with pytest.raises(HTTPException) as exc_info:
        ensure_auth_platform("tencent", SimpleNamespace())

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "平台 tencent 不支持登录"


def test_build_auth_status_payload_for_logged_in_user():
    payload = build_auth_status_payload(
        platform="manhuagui",
        is_logged_in=True,
        user_info={"user_id": "u1", "user_name": "Tester"},
    )

    assert payload == {
        "status": "logged_in",
        "platform": "manhuagui",
        "user_id": "u1",
        "user_name": "Tester",
    }
