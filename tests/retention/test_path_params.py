"""
Tests for path-parameter validation on /v3/tenants/{tenantId}/data-retention-policy.

The spec declares tenantId as a UUID (format: uuid). Non-UUID values should
return 400 before any business logic runs.

[BUG-R3] All three tests below FAIL on the current build: a malformed tenantId
returns 500 "Internal Server Error" instead of 400 — the path parameter is not
validated/handled as a UUID, so the bad value reaches the data layer and throws.
MUST FAIL until path-param validation is added.
"""

import requests

from tests.retention.conftest import retention_url, valid_policy


class TestRetentionPathParams:

    def test_non_uuid_tenant_id_on_get_returns_400(self, base_url, auth_headers):
        """GET with a non-UUID tenantId returns 400.
        [BUG-R3] Server returns 500 instead of 400 — tenantId format not validated. MUST FAIL."""
        resp = requests.get(retention_url(base_url, "not-a-uuid"), headers=auth_headers)
        assert resp.status_code == 400

    def test_non_uuid_tenant_id_on_put_returns_400(self, base_url, auth_headers):
        """PUT with a non-UUID tenantId returns 400.
        [BUG-R3] Server returns 500 instead of 400 — tenantId format not validated. MUST FAIL."""
        resp = requests.put(
            retention_url(base_url, "not-a-uuid"),
            json=valid_policy(),
            headers=auth_headers,
        )
        assert resp.status_code == 400

    def test_integer_tenant_id_on_get_returns_400(self, base_url, auth_headers):
        """GET with an integer tenantId returns 400.
        [BUG-R3] Server returns 500 instead of 400 — tenantId format not validated. MUST FAIL."""
        resp = requests.get(retention_url(base_url, "12345"), headers=auth_headers)
        assert resp.status_code == 400
