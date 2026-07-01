"""
Tests for the bulk Security Settings API (external, typed layer over preferences).

Endpoint:
  GET  /v3/tenants/{tenantId}/security-settings
  PUT  /v3/tenants/{tenantId}/security-settings

Body: {"sessionTimeoutMinutes": <enum>, "passwordResetLinkLifetimeMinutes": <enum>}
  - sessionTimeoutMinutes enum: 15, 30, 60, 120
  - passwordResetLinkLifetimeMinutes enum: 15, 30, 60, 120, 1440
  - both fields required; additionalProperties: false (unknown fields rejected)

Distinct from test_security_accessors.py, which covers the internal per-field
accessors (GET/PUT .../security-settings/{field}) one at a time.
"""

import json

import requests

from tests.tenant_preferences.conftest import security_settings_url

_VALID_SESSION_VALUES = (15, 30, 60, 120)
_VALID_PASSWORD_RESET_VALUES = (15, 30, 60, 120, 1440)


class TestGetSecuritySettingsBulk:

    def test_returns_200(self, base_url, auth_headers, tenant_id):
        """GET security-settings returns 200."""
        resp = requests.get(security_settings_url(base_url, tenant_id), headers=auth_headers)
        assert resp.status_code == 200

    def test_response_contains_both_fields(self, base_url, auth_headers, tenant_id):
        """GET response contains both sessionTimeoutMinutes and passwordResetLinkLifetimeMinutes."""
        body = requests.get(security_settings_url(base_url, tenant_id), headers=auth_headers).json()
        assert "sessionTimeoutMinutes" in body
        assert "passwordResetLinkLifetimeMinutes" in body

    def test_session_timeout_is_in_enum(self, base_url, auth_headers, tenant_id):
        """sessionTimeoutMinutes is one of the allowed enum values."""
        body = requests.get(security_settings_url(base_url, tenant_id), headers=auth_headers).json()
        assert body["sessionTimeoutMinutes"] in _VALID_SESSION_VALUES

    def test_password_reset_lifetime_is_in_enum(self, base_url, auth_headers, tenant_id):
        """passwordResetLinkLifetimeMinutes is one of the allowed enum values."""
        body = requests.get(security_settings_url(base_url, tenant_id), headers=auth_headers).json()
        assert body["passwordResetLinkLifetimeMinutes"] in _VALID_PASSWORD_RESET_VALUES

    def test_response_is_json(self, base_url, auth_headers, tenant_id):
        """GET response has Content-Type application/json."""
        resp = requests.get(security_settings_url(base_url, tenant_id), headers=auth_headers)
        assert "application/json" in resp.headers.get("Content-Type", "")


class TestUpdateSecuritySettingsBulk:

    def test_put_valid_returns_200(self, base_url, auth_headers, tenant_id, current_security_settings):
        """PUT with both fields set to allowed enum values returns 200."""
        url = security_settings_url(base_url, tenant_id)
        payload = {"sessionTimeoutMinutes": 60, "passwordResetLinkLifetimeMinutes": 30}
        resp = requests.put(url, json=payload, headers=auth_headers)
        assert resp.status_code == 200

    def test_put_response_echoes_saved_values(self, base_url, auth_headers, tenant_id, current_security_settings):
        """PUT response body reflects the saved values."""
        url = security_settings_url(base_url, tenant_id)
        payload = {"sessionTimeoutMinutes": 30, "passwordResetLinkLifetimeMinutes": 60}
        body = requests.put(url, json=payload, headers=auth_headers).json()
        assert body["sessionTimeoutMinutes"] == 30
        assert body["passwordResetLinkLifetimeMinutes"] == 60

    def test_put_value_is_persisted(self, base_url, auth_headers, tenant_id, current_security_settings):
        """Updated values are confirmed by a subsequent GET."""
        url = security_settings_url(base_url, tenant_id)
        payload = {"sessionTimeoutMinutes": 120, "passwordResetLinkLifetimeMinutes": 15}
        requests.put(url, json=payload, headers=auth_headers)
        body = requests.get(url, headers=auth_headers).json()
        assert body["sessionTimeoutMinutes"] == 120
        assert body["passwordResetLinkLifetimeMinutes"] == 15


class TestPutValidation:

    def test_missing_session_timeout_returns_400(self, base_url, auth_headers, tenant_id, current_security_settings):
        """PUT without sessionTimeoutMinutes returns 400 VALIDATION_FAILED."""
        url = security_settings_url(base_url, tenant_id)
        resp = requests.put(url, json={"passwordResetLinkLifetimeMinutes": 30}, headers=auth_headers)
        assert resp.status_code == 400
        assert resp.json().get("error") == "VALIDATION_FAILED"

    def test_missing_password_reset_lifetime_returns_400(
        self, base_url, auth_headers, tenant_id, current_security_settings
    ):
        """PUT without passwordResetLinkLifetimeMinutes returns 400 VALIDATION_FAILED."""
        url = security_settings_url(base_url, tenant_id)
        resp = requests.put(url, json={"sessionTimeoutMinutes": 30}, headers=auth_headers)
        assert resp.status_code == 400
        assert resp.json().get("error") == "VALIDATION_FAILED"

    def test_string_session_timeout_returns_400(self, base_url, auth_headers, tenant_id, current_security_settings):
        """A string sessionTimeoutMinutes returns 400 (field is typed integer)."""
        url = security_settings_url(base_url, tenant_id)
        payload = {"sessionTimeoutMinutes": "thirty", "passwordResetLinkLifetimeMinutes": 1440}
        resp = requests.put(url, json=payload, headers=auth_headers)
        assert resp.status_code == 400

    def test_float_session_timeout_returns_400(self, base_url, auth_headers, tenant_id, current_security_settings):
        """A decimal sessionTimeoutMinutes returns 400 (field must be a whole number)."""
        url = security_settings_url(base_url, tenant_id)
        payload = {"sessionTimeoutMinutes": 30.5, "passwordResetLinkLifetimeMinutes": 1440}
        resp = requests.put(url, json=payload, headers=auth_headers)
        assert resp.status_code == 400

    def test_unknown_field_returns_400(self, base_url, auth_headers, tenant_id, current_security_settings):
        """An unrecognized field is rejected — additionalProperties: false on this schema."""
        url = security_settings_url(base_url, tenant_id)
        payload = {"sessionTimeoutMinutes": 30, "passwordResetLinkLifetimeMinutes": 1440, "extra": "x"}
        resp = requests.put(url, json=payload, headers=auth_headers)
        assert resp.status_code == 400

    def test_empty_body_returns_400(self, base_url, auth_headers, tenant_id, current_security_settings):
        """PUT with an empty JSON object returns 400 (both fields required)."""
        url = security_settings_url(base_url, tenant_id)
        resp = requests.put(url, json={}, headers=auth_headers)
        assert resp.status_code == 400

    def test_null_body_returns_400(self, base_url, auth_headers, tenant_id, current_security_settings):
        """PUT with a null body returns 400 (body is required)."""
        url = security_settings_url(base_url, tenant_id)
        resp = requests.put(url, json=None, headers=auth_headers)
        assert resp.status_code == 400


class TestPutBusinessRules:

    def test_session_timeout_out_of_enum_returns_400(
        self, base_url, auth_headers, tenant_id, current_security_settings
    ):
        """sessionTimeoutMinutes = 16 (not in [15,30,60,120]) returns 400 SETTINGS_INVALID."""
        url = security_settings_url(base_url, tenant_id)
        payload = {"sessionTimeoutMinutes": 16, "passwordResetLinkLifetimeMinutes": 1440}
        resp = requests.put(url, json=payload, headers=auth_headers)
        assert resp.status_code == 400
        assert resp.json().get("error") == "SETTINGS_INVALID"

    def test_password_reset_lifetime_out_of_enum_returns_400(
        self, base_url, auth_headers, tenant_id, current_security_settings
    ):
        """passwordResetLinkLifetimeMinutes = 45 (not in the allowed enum) returns 400 SETTINGS_INVALID."""
        url = security_settings_url(base_url, tenant_id)
        payload = {"sessionTimeoutMinutes": 30, "passwordResetLinkLifetimeMinutes": 45}
        resp = requests.put(url, json=payload, headers=auth_headers)
        assert resp.status_code == 400
        assert resp.json().get("error") == "SETTINGS_INVALID"


class TestUnsupportedMethods:
    """Only GET and PUT are defined on this resource — other methods must return
    405 with an Allow header listing the supported methods (RFC 9110 §15.5.6)."""

    def test_post_returns_405(self, base_url, auth_headers, tenant_id):
        """POST to a GET/PUT-only resource returns 405 (not 500)."""
        resp = requests.post(
            security_settings_url(base_url, tenant_id),
            json={"sessionTimeoutMinutes": 30, "passwordResetLinkLifetimeMinutes": 30},
            headers=auth_headers,
        )
        assert resp.status_code == 405
        assert "PUT" in resp.headers.get("Allow", "")
        assert "GET" in resp.headers.get("Allow", "")

    def test_delete_returns_405(self, base_url, auth_headers, tenant_id):
        """DELETE to a GET/PUT-only resource returns 405 (not 500)."""
        resp = requests.delete(security_settings_url(base_url, tenant_id), headers=auth_headers)
        assert resp.status_code == 405


class TestUnsupportedMediaType:

    def test_non_json_content_type_returns_415(self, base_url, auth_headers, tenant_id, current_security_settings):
        """PUT with Content-Type text/plain returns 415."""
        url = security_settings_url(base_url, tenant_id)
        headers = {**auth_headers, "Content-Type": "text/plain"}
        payload = {"sessionTimeoutMinutes": 30, "passwordResetLinkLifetimeMinutes": 30}
        resp = requests.put(url, data=json.dumps(payload), headers=headers)
        assert resp.status_code == 415


class TestSecuritySettingsBulkAuth:

    def test_no_api_key_returns_401(self, base_url, tenant_id):
        """GET without any auth headers returns 401."""
        resp = requests.get(security_settings_url(base_url, tenant_id))
        assert resp.status_code == 401

    def test_invalid_api_key_returns_403(self, base_url, bad_auth_headers, tenant_id):
        """GET with an invalid API key returns 403."""
        resp = requests.get(security_settings_url(base_url, tenant_id), headers=bad_auth_headers)
        assert resp.status_code == 403

    def test_non_uuid_tenant_id_returns_400(self, base_url, auth_headers):
        """Non-UUID tenantId returns 400 (not 500)."""
        url = f"{base_url}/v3/tenants/not-a-uuid/security-settings"
        resp = requests.get(url, headers=auth_headers)
        assert resp.status_code == 400
