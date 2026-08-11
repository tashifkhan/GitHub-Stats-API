"""Cache middleware must accept collection endpoint responses."""

import json

from core.middleware import _is_invalid_user


def _body(payload) -> bytes:
    return json.dumps(payload).encode("utf-8")


def test_successful_json_array_is_not_an_invalid_user():
    assert _is_invalid_user(200, _body([{"name": "jportal"}])) is False


def test_error_envelope_can_still_mark_an_invalid_user():
    payload = {"status": "error", "message": "User not found"}
    assert _is_invalid_user(400, _body(payload)) is True


def test_404_is_always_an_invalid_user():
    assert _is_invalid_user(404, _body([])) is True
