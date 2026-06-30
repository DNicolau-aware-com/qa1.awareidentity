"""
Tests for the individual security-settings field accessor endpoints.

Endpoints:
  GET/PUT /v3/tenants/{tenantId}/security-settings/session_timeout_minutes
  GET/PUT /v3/tenants/{tenantId}/security-settings/password_reset_link_lifetime
"""

import requests

from tests.tenant_preferences.conftest import security_accessor_url

_SESSION_FIELD = "session_timeout_minutes"
_PASSWORD_FIELD = "password_reset_link_lifetime"
_VALID_SESSION_VALUES = (15, 30, 60, 120)


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
        """PUT sessionTimeoutMinutes = 16 (not in [15,30,60,120]) returns 400.
        [BUG] Currently returns 200 — will fail until enum validation is enforced."""
        url = security_accessor_url(base_url, tenant_id, _SESSION_FIELD)
        resp = requests.put(url, json=16, headers=auth_headers)
        assert resp.status_code == 400

    def test_put_very_large_value_returns_400(self, base_url, auth_headers, tenant_id, current_session_timeout):
        """PUT sessionTimeoutMinutes = 999999 returns 400.
        [BUG] Currently returns 200 — will fail until enum validation is enforced."""
        url = security_accessor_url(base_url, tenant_id, _SESSION_FIELD)
        resp = requests.put(url, json=999999, headers=auth_headers)
        assert resp.status_code == 400


class TestUpdatePasswordResetLifetime:

    def test_put_valid_minimum_returns_200(self, base_url, auth_headers, tenant_id, current_password_reset_lifetime):
        """PUT passwordResetLinkLifetime = 1 (minimum) returns 200."""
        url = security_accessor_url(base_url, tenant_id, _PASSWORD_FIELD)
        resp = requests.put(url, json=1, headers=auth_headers)
        assert resp.status_code == 200

    def test_put_valid_maximum_returns_200(self, base_url, auth_headers, tenant_id, current_password_reset_lifetime):
        """PUT passwordResetLinkLifetime = 1440 (24h maximum) returns 200."""
        url = security_accessor_url(base_url, tenant_id, _PASSWORD_FIELD)
        resp = requests.put(url, json=1440, headers=auth_headers)
        assert resp.status_code == 200

    def test_put_mid_range_returns_200(self, base_url, auth_headers, tenant_id, current_password_reset_lifetime):
        """PUT passwordResetLinkLifetime = 720 (12h) returns 200."""
        url = security_accessor_url(base_url, tenant_id, _PASSWORD_FIELD)
        resp = requests.put(url, json=720, headers=auth_headers)
        assert resp.status_code == 200

    def test_put_value_is_persisted(self, base_url, auth_headers, tenant_id, current_password_reset_lifetime):
        """PUT value is confirmed by subsequent GET."""
        url = security_accessor_url(base_url, tenant_id, _PASSWORD_FIELD)
        requests.put(url, json=720, headers=auth_headers)
        assert requests.get(url, headers=auth_headers).json() == 720

    def test_put_zero_returns_400(self, base_url, auth_headers, tenant_id, current_password_reset_lifetime):
        """PUT passwordResetLinkLifetime = 0 returns 400 (minimum is 1)."""
        url = security_accessor_url(base_url, tenant_id, _PASSWORD_FIELD)
        resp = requests.put(url, json=0, headers=auth_headers)
        assert resp.status_code == 400

    def test_put_negative_returns_400(self, base_url, auth_headers, tenant_id, current_password_reset_lifetime):
        """PUT passwordResetLinkLifetime = -1 returns 400."""
        url = security_accessor_url(base_url, tenant_id, _PASSWORD_FIELD)
        resp = requests.put(url, json=-1, headers=auth_headers)
        assert resp.status_code == 400

    def test_put_above_max_returns_400(self, base_url, auth_headers, tenant_id, current_password_reset_lifetime):
        """PUT passwordResetLinkLifetime = 1441 (above 24h max) returns 400.
        [BUG] Currently returns 200 — will fail until max=1440 constraint is enforced."""
        url = security_accessor_url(base_url, tenant_id, _PASSWORD_FIELD)
        resp = requests.put(url, json=1441, headers=auth_headers)
        assert resp.status_code == 400

    def test_put_far_above_max_returns_400(self, base_url, auth_headers, tenant_id, current_password_reset_lifetime):
        """PUT passwordResetLinkLifetime = 144055 returns 400.
        [BUG] Currently returns 200 — will fail until max=1440 constraint is enforced."""
        url = security_accessor_url(base_url, tenant_id, _PASSWORD_FIELD)
        resp = requests.put(url, json=144055, headers=auth_headers)
        assert resp.status_code == 400


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
