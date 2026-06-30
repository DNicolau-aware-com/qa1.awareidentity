"""
Auth tests for /v3/tenants/{tenantId}/data-retention-policy.

These endpoints use a TWO-LAYER auth scheme (see conftest docstring):

  Layer 1 — Gateway (Istio), the `Authorization` bearer JWT:
    - missing Authorization        -> 401 "Missing or invalid Authorization header"
    - malformed / non-Keycloak JWT -> 400 "Cannot derive JWKS URL ..."

  Layer 2 — App, the `X-Aware-ApiKey` (+ `X-Aware-AccountId`) headers
            (only reached once a valid bearer passes the gateway):
    - missing / invalid API key    -> 403
    - valid API key                -> 200

`auth_headers` here is the combined, fully-valid set (bearer + test02 key);
`bearer_token`, `second_api_key`, `auth_headers_2` come from the root conftest.
"""

import requests

from tests.retention.conftest import retention_url, valid_policy


class TestRetentionGatewayAuth:
    """Layer 1 — the Istio bearer-JWT gate, checked before the app sees the request."""

    def test_no_authorization_header_returns_401(self, base_url, tenant_id, auth_headers_2):
        """No Authorization header → 401 at the gateway, even with a valid API key."""
        resp = requests.get(retention_url(base_url, tenant_id), headers=auth_headers_2)
        assert resp.status_code == 401

    def test_no_authorization_header_on_put_returns_401(self, base_url, tenant_id, auth_headers_2):
        """No Authorization header on PUT → 401 at the gateway."""
        resp = requests.put(
            retention_url(base_url, tenant_id), json=valid_policy(), headers=auth_headers_2
        )
        assert resp.status_code == 401

    def test_malformed_bearer_returns_400(self, base_url, tenant_id, auth_headers_2):
        """A bearer that is not a Keycloak-issued JWT → 400 (gateway can't resolve JWKS)."""
        headers = {**auth_headers_2, "Authorization": "Bearer not-a-real-jwt"}
        resp = requests.get(retention_url(base_url, tenant_id), headers=headers)
        assert resp.status_code == 400

    def test_no_auth_at_all_returns_401(self, base_url, tenant_id):
        """No headers at all → 401 at the gateway (Authorization checked first)."""
        resp = requests.get(retention_url(base_url, tenant_id), headers={})
        assert resp.status_code == 401


class TestRetentionAppAuth:
    """Layer 2 — the X-Aware-ApiKey check, reached only with a valid bearer."""

    def test_valid_bearer_and_key_returns_200(self, base_url, tenant_id, auth_headers):
        """Valid bearer + valid API key → 200."""
        resp = requests.get(retention_url(base_url, tenant_id), headers=auth_headers)
        assert resp.status_code == 200

    def test_valid_bearer_no_api_key_returns_403(self, base_url, tenant_id, bearer_token):
        """Valid bearer but NO X-Aware-ApiKey → 403 from the app layer."""
        headers = {"Authorization": f"Bearer {bearer_token}", "Content-Type": "application/json"}
        resp = requests.get(retention_url(base_url, tenant_id), headers=headers)
        assert resp.status_code == 403

    def test_valid_bearer_invalid_api_key_returns_403(self, base_url, tenant_id, bearer_token):
        """Valid bearer but an invalid X-Aware-ApiKey → 403 from the app layer."""
        headers = {
            "Authorization": f"Bearer {bearer_token}",
            "X-Aware-ApiKey": "0" * 64,
            "X-Aware-AccountId": "0001",
            "Content-Type": "application/json",
        }
        resp = requests.get(retention_url(base_url, tenant_id), headers=headers)
        assert resp.status_code == 403

    def test_valid_bearer_invalid_api_key_on_put_returns_403(self, base_url, tenant_id, bearer_token):
        """Valid bearer but an invalid X-Aware-ApiKey on PUT → 403."""
        headers = {
            "Authorization": f"Bearer {bearer_token}",
            "X-Aware-ApiKey": "0" * 64,
            "X-Aware-AccountId": "0001",
            "Content-Type": "application/json",
        }
        resp = requests.put(retention_url(base_url, tenant_id), json=valid_policy(), headers=headers)
        assert resp.status_code == 403
