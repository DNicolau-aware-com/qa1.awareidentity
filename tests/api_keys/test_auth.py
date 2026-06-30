"""
Auth gate tests for /v3/tenants/{tenantId}/apiKeys.

Two-layer auth (same pattern as retention / tenant-preferences):
  Layer 1 — Istio JWT gate:
    missing bearer   -> 401 "Missing or invalid Authorization header"
    malformed bearer -> 403 (differs from retention which returns 400)
  Layer 2 — App (X-Aware-ApiKey + X-Aware-AccountId):
    bearer only, no API key -> 403

Auth tests run without a valid bearer token.
"""

import requests
import pytest

from tests.api_keys.conftest import api_keys_url, valid_create_payload


class TestGatewayAuth:
    """Layer 1 — Istio JWT gate."""

    def test_get_list_no_auth_returns_401(self, base_url, tenant_id):
        resp = requests.get(api_keys_url(base_url, tenant_id))
        assert resp.status_code == 401

    def test_post_create_no_auth_returns_401(self, base_url, tenant_id):
        resp = requests.post(api_keys_url(base_url, tenant_id), json=valid_create_payload())
        assert resp.status_code == 401

    def test_get_single_no_auth_returns_401(self, base_url, tenant_id):
        resp = requests.get(api_keys_url(base_url, tenant_id, "00000000-0000-0000-0000-000000000001"))
        assert resp.status_code == 401

    def test_delete_no_auth_returns_401(self, base_url, tenant_id):
        resp = requests.delete(api_keys_url(base_url, tenant_id, "00000000-0000-0000-0000-000000000001"))
        assert resp.status_code == 401

    def test_patch_no_auth_returns_401(self, base_url, tenant_id):
        resp = requests.patch(
            api_keys_url(base_url, tenant_id, "00000000-0000-0000-0000-000000000001"),
            json={"keyStatus": "INACTIVE"},
        )
        assert resp.status_code == 401

    def test_malformed_bearer_returns_4xx(self, base_url, tenant_id):
        """Malformed JWT without API key returns 403 on this endpoint (retention returns 400)."""
        resp = requests.get(
            api_keys_url(base_url, tenant_id),
            headers={"Authorization": "Bearer not-a-real-jwt"},
        )
        assert resp.status_code in (400, 403)

    def test_malformed_bearer_on_post_returns_4xx(self, base_url, tenant_id):
        resp = requests.post(
            api_keys_url(base_url, tenant_id),
            json=valid_create_payload(),
            headers={"Authorization": "Bearer not-a-real-jwt", "Content-Type": "application/json"},
        )
        assert resp.status_code in (400, 403)

    def test_api_key_only_no_bearer_returns_401(self, base_url, tenant_id, auth_headers):
        """API key without bearer is rejected at the Istio gate."""
        resp = requests.get(api_keys_url(base_url, tenant_id), headers=auth_headers)
        assert resp.status_code == 401


class TestAppAuth:
    """Layer 2 — app requires X-Aware-ApiKey in addition to bearer."""

    def test_bearer_only_no_apikey_returns_403(self, base_url, tenant_id, bearer_token):
        """Valid bearer without X-Aware-ApiKey is rejected by the app layer."""
        headers = {"Authorization": f"Bearer {bearer_token}", "Content-Type": "application/json"}
        resp = requests.get(api_keys_url(base_url, tenant_id), headers=headers)
        assert resp.status_code == 403

    def test_bearer_and_apikey_returns_200(self, base_url, tenant_id, mgmt_headers):
        """Valid bearer + valid API key succeeds."""
        resp = requests.get(api_keys_url(base_url, tenant_id), headers=mgmt_headers)
        assert resp.status_code == 200
