"""
Edge case tests for API Key Management.

Covers:
  1. INACTIVE key still authenticates (security)
  2. Cross-tenant key usage (security)
  3. GET /secret on INACTIVE key (security)
  4. expiresAt field — can it be set, does it enforce expiry
  5. Very long keyName (DoS / crash)
  6. Injection in keyName (XSS / SQLi)
  7. Rotate credentials on INACTIVE key
  8. PATCH on INACTIVE key
  9. Invalid pagination params (page=-1, size=0, size=99999)
"""

import uuid
import requests
import pytest

from tests.api_keys.conftest import api_keys_url, valid_create_payload


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def create_key(base_url, tenant_id, mgmt_headers, name=None):
    resp = requests.post(
        api_keys_url(base_url, tenant_id),
        json=valid_create_payload(name=name or f"edge-{uuid.uuid4().hex[:8]}"),
        headers=mgmt_headers,
    )
    assert resp.status_code == 200, f"Setup failed: {resp.status_code} {resp.text[:200]}"
    return resp.json()


def soft_delete(base_url, tenant_id, key_id, mgmt_headers):
    requests.delete(api_keys_url(base_url, tenant_id, key_id), headers=mgmt_headers)


# ---------------------------------------------------------------------------
# 1. INACTIVE key authentication
# ---------------------------------------------------------------------------

class TestInactiveKeyAuthentication:

    def test_inactive_key_cannot_authenticate(self, base_url, tenant_id, mgmt_headers):
        """A soft-deleted (INACTIVE) key must be rejected when used to authenticate."""
        key = create_key(base_url, tenant_id, mgmt_headers, name=f"inactive-auth-{uuid.uuid4().hex[:6]}")
        secret = key["apiKey"]
        key_id = key["id"]

        # Confirm key works before deletion
        pre_resp = requests.get(
            f"{base_url}/v3/tenants/{tenant_id}/collections",
            headers={"X-Aware-ApiKey": secret, "X-Aware-AccountId": "0001"},
        )
        assert pre_resp.status_code == 200, f"Key did not authenticate before delete: {pre_resp.status_code}"

        # Soft-delete
        soft_delete(base_url, tenant_id, key_id, mgmt_headers)

        # Confirm status is INACTIVE
        get_resp = requests.get(api_keys_url(base_url, tenant_id, key_id), headers=mgmt_headers)
        assert get_resp.json().get("status") == "INACTIVE"

        # Try to authenticate with the deleted key
        post_resp = requests.get(
            f"{base_url}/v3/tenants/{tenant_id}/collections",
            headers={"X-Aware-ApiKey": secret, "X-Aware-AccountId": "0001"},
        )
        assert post_resp.status_code in (401, 403), (
            f"INACTIVE key still authenticates — got {post_resp.status_code}. "
            "Soft-deleted keys must be rejected."
        )


# ---------------------------------------------------------------------------
# 2. Cross-tenant key usage
# ---------------------------------------------------------------------------

class TestCrossTenantKeyUsage:

    def test_tenant_a_key_cannot_access_tenant_b(
        self, base_url, tenant_id, tenant_id_2, mgmt_headers
    ):
        """Key issued for tenant A must not authenticate requests on tenant B's endpoints."""
        key = create_key(base_url, tenant_id, mgmt_headers, name=f"cross-tenant-{uuid.uuid4().hex[:6]}")
        secret = key["apiKey"]
        key_id = key["id"]

        # Try to use tenant A key against tenant B endpoint
        resp = requests.get(
            f"{base_url}/v3/tenants/{tenant_id_2}/collections",
            headers={"X-Aware-ApiKey": secret, "X-Aware-AccountId": "0001"},
        )

        # Cleanup before asserting
        soft_delete(base_url, tenant_id, key_id, mgmt_headers)

        assert resp.status_code in (401, 403), (
            f"Tenant A key accessed tenant B endpoint — got {resp.status_code}. "
            "Cross-tenant access must be blocked."
        )


# ---------------------------------------------------------------------------
# 3. GET /secret on INACTIVE key
# ---------------------------------------------------------------------------

class TestSecretOnInactiveKey:

    def test_secret_not_retrievable_after_soft_delete(self, base_url, tenant_id, mgmt_headers):
        """GET /secret on a soft-deleted key must return 404 — secret must not be retrievable."""
        key = create_key(base_url, tenant_id, mgmt_headers, name=f"secret-inactive-{uuid.uuid4().hex[:6]}")
        key_id = key["id"]

        soft_delete(base_url, tenant_id, key_id, mgmt_headers)

        resp = requests.get(
            api_keys_url(base_url, tenant_id, key_id, sub="secret"),
            headers=mgmt_headers,
        )
        assert resp.status_code == 404, (
            f"GET /secret returned {resp.status_code} on INACTIVE key — "
            "soft-deleted key secret must not be retrievable."
        )


# ---------------------------------------------------------------------------
# 4. expiresAt field
# ---------------------------------------------------------------------------

class TestExpiresAt:

    def test_expires_at_can_be_set_at_creation(self, base_url, tenant_id, mgmt_headers):
        """expiresAt can be set at creation time."""
        payload = valid_create_payload(name=f"expires-{uuid.uuid4().hex[:6]}")
        payload["expiresAt"] = "2030-01-01T00:00:00Z"

        resp = requests.post(api_keys_url(base_url, tenant_id), json=payload, headers=mgmt_headers)
        key_id = resp.json().get("id")

        result = resp.json().get("expiresAt")
        if key_id:
            soft_delete(base_url, tenant_id, key_id, mgmt_headers)

        assert resp.status_code == 200
        assert result is not None, "expiresAt was ignored — field not stored"

    def test_expired_key_cannot_authenticate(self, base_url, tenant_id, mgmt_headers):
        """A key with expiresAt in the past must not authenticate."""
        payload = valid_create_payload(name=f"expired-{uuid.uuid4().hex[:6]}")
        payload["expiresAt"] = "2000-01-01T00:00:00Z"  # already expired

        resp = requests.post(api_keys_url(base_url, tenant_id), json=payload, headers=mgmt_headers)
        key = resp.json()
        key_id = key.get("id")
        secret = key.get("apiKey")

        if not secret:
            soft_delete(base_url, tenant_id, key_id, mgmt_headers)
            pytest.skip("No secret returned — cannot test auth")

        auth_resp = requests.get(
            f"{base_url}/v3/tenants/{tenant_id}/collections",
            headers={"X-Aware-ApiKey": secret, "X-Aware-AccountId": "0001"},
        )

        soft_delete(base_url, tenant_id, key_id, mgmt_headers)

        assert auth_resp.status_code in (401, 403), (
            f"Expired key (expiresAt=2000-01-01) still authenticated — got {auth_resp.status_code}"
        )


# ---------------------------------------------------------------------------
# 5. Very long keyName
# ---------------------------------------------------------------------------

class TestLongKeyName:

    def test_very_long_key_name_returns_4xx(self, base_url, tenant_id, mgmt_headers):
        """keyName of 10,000 characters must return 400, not crash with 500."""
        long_name = "a" * 10000
        resp = requests.post(
            api_keys_url(base_url, tenant_id),
            json={"keyName": long_name, "description": "long name test", "visibility": "ORGANIZATION"},
            headers=mgmt_headers,
        )
        key_id = resp.json().get("id") if resp.status_code == 200 else None
        if key_id:
            soft_delete(base_url, tenant_id, key_id, mgmt_headers)

        assert resp.status_code in (400, 422), (
            f"Expected 400/422 for 10,000-char keyName, got {resp.status_code}: {resp.text[:300]}"
        )

    def test_boundary_key_name_255_chars(self, base_url, tenant_id, mgmt_headers):
        """keyName of 255 characters — document whether it is accepted or rejected."""
        name_255 = "a" * 255
        resp = requests.post(
            api_keys_url(base_url, tenant_id),
            json={"keyName": name_255, "description": "255-char name", "visibility": "ORGANIZATION"},
            headers=mgmt_headers,
        )
        key_id = resp.json().get("id") if resp.status_code == 200 else None
        if key_id:
            soft_delete(base_url, tenant_id, key_id, mgmt_headers)

        assert resp.status_code in (200, 400, 422), (
            f"Unexpected status for 255-char keyName: {resp.status_code}"
        )


# ---------------------------------------------------------------------------
# 6. Injection in keyName
# ---------------------------------------------------------------------------

class TestInjectionInKeyName:

    @pytest.mark.parametrize("payload,label", [
        ("'; DROP TABLE api_keys; --", "sql_injection"),
        ("<script>alert(1)</script>", "xss_html"),
        ("{{7*7}}", "ssti_template"),
        ("../../../etc/passwd", "path_traversal"),
        ("\x00nullbyte", "null_byte"),
    ])
    def test_injection_payload_stored_safely(self, base_url, tenant_id, mgmt_headers, payload, label):
        """Injection payloads must be stored as literal strings or rejected — never executed."""
        resp = requests.post(
            api_keys_url(base_url, tenant_id),
            json={"keyName": payload, "description": f"injection test: {label}", "visibility": "ORGANIZATION"},
            headers=mgmt_headers,
        )
        key_id = resp.json().get("id") if resp.status_code == 200 else None

        if resp.status_code == 200:
            # If accepted, the stored value must match the literal input
            stored_name = resp.json().get("keyName")
            if key_id:
                soft_delete(base_url, tenant_id, key_id, mgmt_headers)
            assert stored_name == payload, (
                f"Stored keyName does not match input for {label} — "
                f"possible injection processing: input={payload!r}, stored={stored_name!r}"
            )
        else:
            # Rejected with 400/422 is also acceptable
            assert resp.status_code in (400, 422), (
                f"Unexpected status {resp.status_code} for {label} payload"
            )


# ---------------------------------------------------------------------------
# 7. Rotate credentials on INACTIVE key
# ---------------------------------------------------------------------------

class TestRotateOnInactiveKey:

    def test_rotate_on_inactive_key_returns_4xx(self, base_url, tenant_id, mgmt_headers):
        """Rotating credentials on a soft-deleted (INACTIVE) key must return 400 or 404."""
        key = create_key(base_url, tenant_id, mgmt_headers, name=f"rotate-inactive-{uuid.uuid4().hex[:6]}")
        key_id = key["id"]

        soft_delete(base_url, tenant_id, key_id, mgmt_headers)

        resp = requests.post(
            api_keys_url(base_url, tenant_id, key_id, sub="rotate-credentials"),
            headers=mgmt_headers,
        )
        assert resp.status_code in (400, 404), (
            f"Rotate on INACTIVE key returned {resp.status_code} — "
            f"expected 400/404. Body: {resp.text[:200]}"
        )


# ---------------------------------------------------------------------------
# 8. PATCH on INACTIVE key
# ---------------------------------------------------------------------------

class TestPatchOnInactiveKey:

    def test_patch_on_inactive_key_returns_4xx(self, base_url, tenant_id, mgmt_headers):
        """PATCH on a soft-deleted (INACTIVE) key must return 400 or 404."""
        key = create_key(base_url, tenant_id, mgmt_headers, name=f"patch-inactive-{uuid.uuid4().hex[:6]}")
        key_id = key["id"]

        soft_delete(base_url, tenant_id, key_id, mgmt_headers)

        resp = requests.patch(
            api_keys_url(base_url, tenant_id, key_id),
            json={"keyStatus": "REVOKED"},
            headers=mgmt_headers,
        )
        assert resp.status_code in (400, 404), (
            f"PATCH on INACTIVE key returned {resp.status_code} — "
            f"expected 400/404. Body: {resp.text[:200]}"
        )


# ---------------------------------------------------------------------------
# 9. Invalid pagination params
# ---------------------------------------------------------------------------

class TestInvalidPagination:

    def test_negative_page_returns_4xx_or_200(self, base_url, tenant_id, mgmt_headers):
        """page=-1 must not crash with 500."""
        resp = requests.get(
            api_keys_url(base_url, tenant_id),
            params={"page": -1, "size": 20},
            headers=mgmt_headers,
        )
        assert resp.status_code != 500, (
            f"page=-1 crashed with 500: {resp.text[:200]}"
        )

    def test_zero_size_returns_4xx_or_200(self, base_url, tenant_id, mgmt_headers):
        """size=0 must not crash with 500."""
        resp = requests.get(
            api_keys_url(base_url, tenant_id),
            params={"page": 0, "size": 0},
            headers=mgmt_headers,
        )
        assert resp.status_code != 500, (
            f"size=0 crashed with 500: {resp.text[:200]}"
        )

    def test_huge_size_returns_4xx_or_200(self, base_url, tenant_id, mgmt_headers):
        """size=99999 must not crash with 500."""
        resp = requests.get(
            api_keys_url(base_url, tenant_id),
            params={"page": 0, "size": 99999},
            headers=mgmt_headers,
        )
        assert resp.status_code != 500, (
            f"size=99999 crashed with 500: {resp.text[:200]}"
        )

    def test_non_numeric_page_returns_4xx(self, base_url, tenant_id, mgmt_headers):
        """page=abc must return 400, not 500."""
        resp = requests.get(
            api_keys_url(base_url, tenant_id),
            params={"page": "abc", "size": 20},
            headers=mgmt_headers,
        )
        assert resp.status_code in (400, 422), (
            f"Non-numeric page param returned {resp.status_code}: {resp.text[:200]}"
        )
