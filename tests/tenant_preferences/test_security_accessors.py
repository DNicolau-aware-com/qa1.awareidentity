"""
Tests for the individual security-settings field accessor endpoints.

Endpoints:
  GET/PUT /v3/tenants/{tenantId}/security-settings/session_timeout_minutes
  GET/PUT /v3/tenants/{tenantId}/security-settings/password_reset_link_lifetime
"""

import pytest
import requests

from tests.tenant_preferences.conftest import security_accessor_url

_SESSION_FIELD = "session_timeout_minutes"
_PASSWORD_FIELD = "password_reset_link_lifetime"
_VALID_SESSION_VALUES = (15, 30, 60, 120)
_FIELDS_WITH_VALID_VALUE = (
    (_SESSION_FIELD, 30),
    (_PASSWORD_FIELD, 60),
)


class TestGetSecuritySettings:

    def test_get_session_timeout_returns_200(self, base_url, auth_headers, tenant_id):
        """GET session_timeout_minutes returns 200."""
        resp = requests.get(security_accessor_url(base_url, tenant_id, _SESSION_FIELD), headers=auth_headers)
        assert resp.status_code == 200

    def test_get_session_timeout_returns_integer(self, base_url, auth_headers, tenant_id):
        """GET session_timeout_minutes response body is an integer."""
        resp = requests.get(security_accessor_url(base_url, tenant_id, _SESSION_FIELD), headers=auth_headers)
        assert isinstance(resp.json(), int)

    def test_get_session_timeout_is_positive(self, base_url, auth_headers, tenant_id):
        """GET session_timeout_minutes value is positive (≥ 1)."""
        resp = requests.get(security_accessor_url(base_url, tenant_id, _SESSION_FIELD), headers=auth_headers)
        assert resp.json() >= 1

    def test_get_password_reset_lifetime_returns_200(self, base_url, auth_headers, tenant_id):
        """GET password_reset_link_lifetime returns 200."""
        resp = requests.get(security_accessor_url(base_url, tenant_id, _PASSWORD_FIELD), headers=auth_headers)
        assert resp.status_code == 200

    def test_get_password_reset_lifetime_returns_integer(self, base_url, auth_headers, tenant_id):
        """GET password_reset_link_lifetime response body is an integer."""
        resp = requests.get(security_accessor_url(base_url, tenant_id, _PASSWORD_FIELD), headers=auth_headers)
        assert isinstance(resp.json(), int)

    def test_get_password_reset_lifetime_is_positive(self, base_url, auth_headers, tenant_id):
        """GET password_reset_link_lifetime value is positive (≥ 1)."""
        resp = requests.get(security_accessor_url(base_url, tenant_id, _PASSWORD_FIELD), headers=auth_headers)
        assert resp.json() >= 1

    def test_response_is_json(self, base_url, auth_headers, tenant_id):
        """Both fields return Content-Type application/json."""
        for field in (_SESSION_FIELD, _PASSWORD_FIELD):
            resp = requests.get(security_accessor_url(base_url, tenant_id, field), headers=auth_headers)
            assert "application/json" in resp.headers.get("Content-Type", ""), f"{field} missing JSON content-type"


class TestUpdateSessionTimeout:

    def test_put_15_returns_200(self, base_url, auth_headers, tenant_id, current_session_timeout):
        """PUT sessionTimeoutMinutes = 15 returns 200."""
        url = security_accessor_url(base_url, tenant_id, _SESSION_FIELD)
        resp = requests.put(url, json=15, headers=auth_headers)
        assert resp.status_code == 200

    def test_put_30_returns_200(self, base_url, auth_headers, tenant_id, current_session_timeout):
        """PUT sessionTimeoutMinutes = 30 returns 200."""
        url = security_accessor_url(base_url, tenant_id, _SESSION_FIELD)
        resp = requests.put(url, json=30, headers=auth_headers)
        assert resp.status_code == 200

    def test_put_60_returns_200(self, base_url, auth_headers, tenant_id, current_session_timeout):
        """PUT sessionTimeoutMinutes = 60 returns 200."""
        url = security_accessor_url(base_url, tenant_id, _SESSION_FIELD)
        resp = requests.put(url, json=60, headers=auth_headers)
        assert resp.status_code == 200

    def test_put_120_returns_200(self, base_url, auth_headers, tenant_id, current_session_timeout):
        """PUT sessionTimeoutMinutes = 120 returns 200."""
        url = security_accessor_url(base_url, tenant_id, _SESSION_FIELD)
        resp = requests.put(url, json=120, headers=auth_headers)
        assert resp.status_code == 200

    def test_put_value_is_persisted(self, base_url, auth_headers, tenant_id, current_session_timeout):
        """PUT value is confirmed by subsequent GET."""
        url = security_accessor_url(base_url, tenant_id, _SESSION_FIELD)
        requests.put(url, json=30, headers=auth_headers)
        assert requests.get(url, headers=auth_headers).json() == 30

    def test_put_zero_returns_400(self, base_url, auth_headers, tenant_id, current_session_timeout):
        """PUT sessionTimeoutMinutes = 0 returns 400 (minimum is 1)."""
        url = security_accessor_url(base_url, tenant_id, _SESSION_FIELD)
        resp = requests.put(url, json=0, headers=auth_headers)
        assert resp.status_code == 400

    def test_put_negative_returns_400(self, base_url, auth_headers, tenant_id, current_session_timeout):
        """PUT sessionTimeoutMinutes = -1 returns 400."""
        url = security_accessor_url(base_url, tenant_id, _SESSION_FIELD)
        resp = requests.put(url, json=-1, headers=auth_headers)
        assert resp.status_code == 400

    def test_put_out_of_enum_returns_400(self, base_url, auth_headers, tenant_id, current_session_timeout):
        """PUT sessionTimeoutMinutes = 16 (not in [15,30,60,120]) returns 400."""
        url = security_accessor_url(base_url, tenant_id, _SESSION_FIELD)
        resp = requests.put(url, json=16, headers=auth_headers)
        assert resp.status_code == 400

    def test_put_very_large_value_returns_400(self, base_url, auth_headers, tenant_id, current_session_timeout):
        """PUT sessionTimeoutMinutes = 999999 returns 400."""
        url = security_accessor_url(base_url, tenant_id, _SESSION_FIELD)
        resp = requests.put(url, json=999999, headers=auth_headers)
        assert resp.status_code == 400

    def test_put_bulk_object_shape_returns_400(self, base_url, auth_headers, tenant_id, current_session_timeout):
        """This endpoint takes a bare integer body, not the bulk SecuritySettings object
        shape — the field to set is identified by the URL path segment
        (.../session_timeout_minutes), not by a field name in the body."""
        url = security_accessor_url(base_url, tenant_id, _SESSION_FIELD)
        payload = {"sessionTimeoutMinutes": 60, "passwordResetLinkLifetimeMinutes": 1440}
        resp = requests.put(url, json=payload, headers=auth_headers)
        assert resp.status_code == 400


class TestUpdatePasswordResetLifetime:

    def test_put_valid_maximum_returns_200(self, base_url, auth_headers, tenant_id, current_password_reset_lifetime):
        """PUT passwordResetLinkLifetime = 1440 (in the allowed enum) returns 200."""
        url = security_accessor_url(base_url, tenant_id, _PASSWORD_FIELD)
        resp = requests.put(url, json=1440, headers=auth_headers)
        assert resp.status_code == 200

    def test_put_out_of_enum_low_returns_400(self, base_url, auth_headers, tenant_id, current_password_reset_lifetime):
        """PUT passwordResetLinkLifetime = 1 (not in [15,30,60,120,1440]) returns 400."""
        url = security_accessor_url(base_url, tenant_id, _PASSWORD_FIELD)
        resp = requests.put(url, json=1, headers=auth_headers)
        assert resp.status_code == 400

    def test_put_out_of_enum_mid_returns_400(self, base_url, auth_headers, tenant_id, current_password_reset_lifetime):
        """PUT passwordResetLinkLifetime = 720 (not in [15,30,60,120,1440]) returns 400."""
        url = security_accessor_url(base_url, tenant_id, _PASSWORD_FIELD)
        resp = requests.put(url, json=720, headers=auth_headers)
        assert resp.status_code == 400

    def test_put_value_is_persisted(self, base_url, auth_headers, tenant_id, current_password_reset_lifetime):
        """PUT with an allowed enum value is confirmed by subsequent GET."""
        url = security_accessor_url(base_url, tenant_id, _PASSWORD_FIELD)
        requests.put(url, json=60, headers=auth_headers)
        assert requests.get(url, headers=auth_headers).json() == 60

    def test_put_zero_returns_400(self, base_url, auth_headers, tenant_id, current_password_reset_lifetime):
        """PUT passwordResetLinkLifetime = 0 returns 400 (not in the allowed enum)."""
        url = security_accessor_url(base_url, tenant_id, _PASSWORD_FIELD)
        resp = requests.put(url, json=0, headers=auth_headers)
        assert resp.status_code == 400

    def test_put_negative_returns_400(self, base_url, auth_headers, tenant_id, current_password_reset_lifetime):
        """PUT passwordResetLinkLifetime = -1 returns 400."""
        url = security_accessor_url(base_url, tenant_id, _PASSWORD_FIELD)
        resp = requests.put(url, json=-1, headers=auth_headers)
        assert resp.status_code == 400

    def test_put_above_max_returns_400(self, base_url, auth_headers, tenant_id, current_password_reset_lifetime):
        """PUT passwordResetLinkLifetime = 1441 (above the max enum value, 1440) returns 400."""
        url = security_accessor_url(base_url, tenant_id, _PASSWORD_FIELD)
        resp = requests.put(url, json=1441, headers=auth_headers)
        assert resp.status_code == 400

    def test_put_far_above_max_returns_400(self, base_url, auth_headers, tenant_id, current_password_reset_lifetime):
        """PUT passwordResetLinkLifetime = 144055 returns 400."""
        url = security_accessor_url(base_url, tenant_id, _PASSWORD_FIELD)
        resp = requests.put(url, json=144055, headers=auth_headers)
        assert resp.status_code == 400

    def test_put_bulk_object_shape_returns_400(self, base_url, auth_headers, tenant_id, current_password_reset_lifetime):
        """This endpoint takes a bare integer body, not the bulk SecuritySettings object
        shape ({"sessionTimeoutMinutes": ..., "passwordResetLinkLifetimeMinutes": ...}).

        The team's Postman collection currently documents the wrong example for this
        endpoint (the bulk object) — this test locks in the real contract so that if the
        docs are ever "fixed" by changing the endpoint instead of the example, it's caught."""
        url = security_accessor_url(base_url, tenant_id, _PASSWORD_FIELD)
        payload = {"sessionTimeoutMinutes": 60, "passwordResetLinkLifetimeMinutes": 1440}
        resp = requests.put(url, json=payload, headers=auth_headers)
        assert resp.status_code == 400


class TestAccessorFieldIsolation:
    """Each individual accessor's URL path segment identifies the field to set — the
    body carries only the value, not a field name. These tests confirm that PUTting
    one field's accessor never touches the other field.

    Snapshots the live value of the *other* field immediately before mutating, rather
    than relying on the session-scoped current_session_timeout/current_password_reset_lifetime
    fixtures — those snapshot once at the start of the whole test run and go stale as
    soon as any other test in the session mutates the value without restoring it."""

    def test_put_session_timeout_does_not_change_password_reset_lifetime(
        self, base_url, auth_headers, tenant_id, current_session_timeout
    ):
        """PUT .../session_timeout_minutes leaves passwordResetLinkLifetimeMinutes unchanged."""
        session_url = security_accessor_url(base_url, tenant_id, _SESSION_FIELD)
        password_url = security_accessor_url(base_url, tenant_id, _PASSWORD_FIELD)
        password_before = requests.get(password_url, headers=auth_headers).json()
        new_value = 60 if current_session_timeout != 60 else 30
        requests.put(session_url, json=new_value, headers=auth_headers)
        assert requests.get(password_url, headers=auth_headers).json() == password_before

    def test_put_password_reset_lifetime_does_not_change_session_timeout(
        self, base_url, auth_headers, tenant_id, current_password_reset_lifetime
    ):
        """PUT .../password_reset_link_lifetime leaves sessionTimeoutMinutes unchanged."""
        session_url = security_accessor_url(base_url, tenant_id, _SESSION_FIELD)
        password_url = security_accessor_url(base_url, tenant_id, _PASSWORD_FIELD)
        session_before = requests.get(session_url, headers=auth_headers).json()
        new_value = 30 if current_password_reset_lifetime != 30 else 60
        requests.put(password_url, json=new_value, headers=auth_headers)
        assert requests.get(session_url, headers=auth_headers).json() == session_before


class TestAccessorTypeCoercion:
    """Both fields are `type: integer` with an enum constraint. Per spec: "Must be a
    whole number — a decimal, string, boolean, or out-of-range value returns 400
    VALIDATION_FAILED." The bulk endpoint (test_security_settings_bulk.py) enforces
    this correctly for both fields; these individual accessors do not for numeric
    strings and decimals."""

    @pytest.mark.parametrize("field,valid_value", _FIELDS_WITH_VALID_VALUE)
    def test_numeric_string_returns_400(self, base_url, auth_headers, tenant_id, field, valid_value):
        """A numeric string matching a valid enum value (e.g. "30") returns 400, not 200
        with silent coercion to int.
        [BUG] Currently returns 200 on both accessors — the bulk endpoint gets this right."""
        url = security_accessor_url(base_url, tenant_id, field)
        snap = requests.get(url, headers=auth_headers).json()
        resp = requests.put(url, json=str(valid_value), headers=auth_headers)
        assert resp.status_code == 400
        requests.put(url, json=snap, headers=auth_headers)

    @pytest.mark.parametrize("field,valid_value", _FIELDS_WITH_VALID_VALUE)
    def test_decimal_returns_400(self, base_url, auth_headers, tenant_id, field, valid_value):
        """A decimal value (e.g. 30.5) returns 400 — the field must be a whole number.
        [BUG] Currently returns 200 (silently truncated to the integer part) on both accessors."""
        url = security_accessor_url(base_url, tenant_id, field)
        snap = requests.get(url, headers=auth_headers).json()
        resp = requests.put(url, json=valid_value + 0.5, headers=auth_headers)
        assert resp.status_code == 400
        requests.put(url, json=snap, headers=auth_headers)

    @pytest.mark.parametrize("field,valid_value", _FIELDS_WITH_VALID_VALUE)
    def test_boolean_returns_400(self, base_url, auth_headers, tenant_id, field, valid_value):
        """A boolean value returns 400 (field is typed integer)."""
        url = security_accessor_url(base_url, tenant_id, field)
        snap = requests.get(url, headers=auth_headers).json()
        resp = requests.put(url, json=True, headers=auth_headers)
        assert resp.status_code == 400
        requests.put(url, json=snap, headers=auth_headers)

    @pytest.mark.parametrize("field,valid_value", _FIELDS_WITH_VALID_VALUE)
    def test_null_returns_400(self, base_url, auth_headers, tenant_id, field, valid_value):
        """A null value returns 400."""
        url = security_accessor_url(base_url, tenant_id, field)
        snap = requests.get(url, headers=auth_headers).json()
        resp = requests.put(url, json=None, headers=auth_headers)
        assert resp.status_code == 400
        requests.put(url, json=snap, headers=auth_headers)

    @pytest.mark.parametrize("field,valid_value", _FIELDS_WITH_VALID_VALUE)
    def test_array_returns_400(self, base_url, auth_headers, tenant_id, field, valid_value):
        """A JSON array value returns 400."""
        url = security_accessor_url(base_url, tenant_id, field)
        snap = requests.get(url, headers=auth_headers).json()
        resp = requests.put(url, json=[valid_value], headers=auth_headers)
        assert resp.status_code == 400
        requests.put(url, json=snap, headers=auth_headers)

    @pytest.mark.parametrize("field,valid_value", _FIELDS_WITH_VALID_VALUE)
    def test_huge_number_returns_400_not_500(self, base_url, auth_headers, tenant_id, field, valid_value):
        """A value far beyond Long range returns 400, not a 500 numeric-overflow crash
        (the failure mode seen elsewhere in this API, e.g. retention's maxRetentionDays)."""
        url = security_accessor_url(base_url, tenant_id, field)
        snap = requests.get(url, headers=auth_headers).json()
        resp = requests.put(url, json=99999999999999999999, headers=auth_headers)
        assert resp.status_code == 400
        requests.put(url, json=snap, headers=auth_headers)


class TestAccessorUnsupportedMethods:
    """Only GET and PUT are defined on these resources — other methods must return
    405 with an Allow header listing the supported methods (RFC 9110 §15.5.6)."""

    @pytest.mark.parametrize("field", (_SESSION_FIELD, _PASSWORD_FIELD))
    def test_post_returns_405(self, base_url, auth_headers, tenant_id, field):
        resp = requests.post(security_accessor_url(base_url, tenant_id, field), json=30, headers=auth_headers)
        assert resp.status_code == 405
        assert "PUT" in resp.headers.get("Allow", "")

    @pytest.mark.parametrize("field", (_SESSION_FIELD, _PASSWORD_FIELD))
    def test_delete_returns_405(self, base_url, auth_headers, tenant_id, field):
        resp = requests.delete(security_accessor_url(base_url, tenant_id, field), headers=auth_headers)
        assert resp.status_code == 405


class TestAccessorUnsupportedMediaType:

    @pytest.mark.parametrize("field,valid_value", _FIELDS_WITH_VALID_VALUE)
    def test_non_json_content_type_returns_415(self, base_url, auth_headers, tenant_id, field, valid_value):
        """PUT with Content-Type text/plain returns 415."""
        url = security_accessor_url(base_url, tenant_id, field)
        headers = {**auth_headers, "Content-Type": "text/plain"}
        resp = requests.put(url, data=str(valid_value), headers=headers)
        assert resp.status_code == 415


class TestSecurityAccessorAuth:

    def test_no_api_key_returns_401(self, base_url, tenant_id):
        """GET without auth returns 401."""
        resp = requests.get(security_accessor_url(base_url, tenant_id, _SESSION_FIELD))
        assert resp.status_code == 401

    def test_invalid_api_key_returns_403(self, base_url, bad_auth_headers, tenant_id):
        """GET with invalid API key returns 403."""
        resp = requests.get(
            security_accessor_url(base_url, tenant_id, _SESSION_FIELD),
            headers=bad_auth_headers,
        )
        assert resp.status_code == 403

    def test_non_uuid_tenant_id_returns_400(self, base_url, auth_headers):
        """Non-UUID tenantId returns 400 (not 500). [BUG-R3 family]"""
        url = f"{base_url}/v3/tenants/not-a-uuid/security-settings/{_SESSION_FIELD}"
        resp = requests.get(url, headers=auth_headers)
        assert resp.status_code == 400
