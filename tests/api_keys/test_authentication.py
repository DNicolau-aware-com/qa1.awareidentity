"""
API key authentication tests — AWRNSS-388.

Verifies that a newly issued key authenticates API requests,
that soft-deleted (INACTIVE) keys are rejected, and that the
last-used timestamp is updated on successful authentication.

NOTE: lastUsedAt tracking appears to not be implemented —
existing keys used thousands of times still show null. Marked xfail.
"""

import uuid
import requests
import pytest

from tests.api_keys.conftest import api_keys_url, valid_create_payload


class TestActiveKeyAuthentication:

    def test_newly_issued_key_authenticates_collections_endpoint(
        self, base_url, tenant_id, mgmt_headers, created_key
    ):
        """A freshly created key must authenticate successfully against the API."""
        secret = created_key.get("apiKey")
        if not secret:
            pytest.skip("Secret not in created_key fixture — cannot test authentication")

        headers = {
            "X-Aware-ApiKey": secret,
            "X-Aware-AccountId": "0001",
            "Content-Type": "application/json",
        }
        resp = requests.get(
            f"{base_url}/v3/tenants/{tenant_id}/collections",
            headers=headers,
        )
        assert resp.status_code == 200, (
            f"Newly issued key failed to authenticate: {resp.status_code} {resp.text[:200]}"
        )

    def test_inactive_key_is_rejected(self, base_url, tenant_id, mgmt_headers):
        """A soft-deleted (INACTIVE) key must be rejected by the API."""
        resp = requests.post(
            api_keys_url(base_url, tenant_id),
            json=valid_create_payload(name=f"inactive-auth-{uuid.uuid4().hex[:6]}"),
            headers=mgmt_headers,
        )
        assert resp.status_code == 200
        key = resp.json()
        key_id = key["id"]
        secret = key.get("apiKey")

        if not secret:
            requests.delete(api_keys_url(base_url, tenant_id, key_id), headers=mgmt_headers)
            pytest.skip("Secret not returned in create response")

        # Soft-delete the key
        requests.delete(api_keys_url(base_url, tenant_id, key_id), headers=mgmt_headers)

        # Attempt to use the inactive key
        auth_resp = requests.get(
            f"{base_url}/v3/tenants/{tenant_id}/collections",
            headers={"X-Aware-ApiKey": secret, "X-Aware-AccountId": "0001"},
        )
        assert auth_resp.status_code in (401, 403), (
            f"INACTIVE key was accepted: {auth_resp.status_code}"
        )

    def test_unknown_key_is_rejected(self, base_url, tenant_id):
        """A completely unknown key must be rejected."""
        resp = requests.get(
            f"{base_url}/v3/tenants/{tenant_id}/collections",
            headers={"X-Aware-ApiKey": "0" * 64, "X-Aware-AccountId": "0001"},
        )
        assert resp.status_code in (401, 403)

    def test_inactive_and_unknown_key_return_same_status(self, base_url, tenant_id, mgmt_headers):
        """Auth failures must not disclose whether the key exists (uniform error shape)."""
        resp = requests.post(
            api_keys_url(base_url, tenant_id),
            json=valid_create_payload(name=f"uniform-{uuid.uuid4().hex[:6]}"),
            headers=mgmt_headers,
        )
        key = resp.json()
        key_id = key["id"]
        secret = key.get("apiKey")

        if not secret:
            requests.delete(api_keys_url(base_url, tenant_id, key_id), headers=mgmt_headers)
            pytest.skip("Secret not returned in create response")

        requests.delete(api_keys_url(base_url, tenant_id, key_id), headers=mgmt_headers)

        inactive_resp = requests.get(
            f"{base_url}/v3/tenants/{tenant_id}/collections",
            headers={"X-Aware-ApiKey": secret, "X-Aware-AccountId": "0001"},
        )
        unknown_resp = requests.get(
            f"{base_url}/v3/tenants/{tenant_id}/collections",
            headers={"X-Aware-ApiKey": "0" * 64, "X-Aware-AccountId": "0001"},
        )
        assert inactive_resp.status_code == unknown_resp.status_code, (
            f"INACTIVE key returns {inactive_resp.status_code} but unknown key returns "
            f"{unknown_resp.status_code} — must be uniform to prevent key existence disclosure"
        )


class TestLastUsedTracking:

    def test_last_used_updated_after_successful_auth(
        self, base_url, tenant_id, mgmt_headers, created_key
    ):
        """Successful authentication must update the key's lastUsedAt timestamp."""
        secret = created_key.get("apiKey")
        if not secret:
            pytest.skip("Secret not in created_key fixture")

        requests.get(
            f"{base_url}/v3/tenants/{tenant_id}/collections",
            headers={"X-Aware-ApiKey": secret, "X-Aware-AccountId": "0001"},
        )

        get_resp = requests.get(
            api_keys_url(base_url, tenant_id, created_key["id"]), headers=mgmt_headers
        )
        last_used = get_resp.json().get("lastUsedAt")
        assert last_used is not None, (
            f"lastUsedAt not updated after successful auth: {get_resp.json()}"
        )

    def test_fresh_key_has_null_last_used(self, base_url, tenant_id, mgmt_headers, created_key):
        """A key that has never been used must have lastUsedAt null."""
        resp = requests.get(
            api_keys_url(base_url, tenant_id, created_key["id"]), headers=mgmt_headers
        )
        assert resp.json().get("lastUsedAt") is None


class TestTenantScope:

    def test_key_cannot_access_different_tenant(
        self, base_url, tenant_id, tenant_id_2, mgmt_headers, created_key
    ):
        """A key issued for tenant A must be rejected when accessing tenant B resources."""
        secret = created_key.get("apiKey")
        if not secret:
            pytest.skip("Secret not in created_key fixture")

        resp = requests.get(
            f"{base_url}/v3/tenants/{tenant_id_2}/collections",
            headers={"X-Aware-ApiKey": secret, "X-Aware-AccountId": "0001"},
        )
        assert resp.status_code in (401, 403), (
            f"Key from tenant A accessed tenant B resources: {resp.status_code}"
        )
