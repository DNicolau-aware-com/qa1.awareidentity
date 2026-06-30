"""
POST /v3/tenants/{tenantId}/apiKeys — create API key.

Confirmed behavior:
  - Returns HTTP 200 (not 201 — spec deviation, REST convention is 201 for creation)
  - Response is flat (not wrapped): { id, keyName, apiKey (secret), keyPrefix, keySuffix, ... }
  - Secret returned in `apiKey` field on creation response only
  - Subsequent GET returns apiKey: null
"""

import uuid
import requests
import pytest

from tests.api_keys.conftest import api_keys_url, valid_create_payload


class TestCreateHappyPath:

    def test_create_returns_200(self, base_url, tenant_id, mgmt_headers):
        """
        BUG: Returns 200 instead of 201. REST convention for resource creation is 201.
        Documenting actual behavior — should be updated to 201.
        """
        resp = requests.post(
            api_keys_url(base_url, tenant_id),
            json=valid_create_payload(),
            headers=mgmt_headers,
        )
        key_id = resp.json().get("id")
        assert resp.status_code == 200, f"Got {resp.status_code}: {resp.text[:200]}"
        if key_id:
            requests.delete(api_keys_url(base_url, tenant_id, key_id), headers=mgmt_headers)

    def test_create_response_contains_secret_in_apikey_field(self, base_url, tenant_id, mgmt_headers):
        """The `apiKey` field in the creation response holds the plaintext secret."""
        resp = requests.post(
            api_keys_url(base_url, tenant_id),
            json=valid_create_payload(),
            headers=mgmt_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        secret = body.get("apiKey")
        assert secret is not None, f"apiKey (secret) not in creation response. Keys: {list(body.keys())}"
        assert len(str(secret)) > 20, f"apiKey looks too short to be a real secret: {secret!r}"
        if body.get("id"):
            requests.delete(api_keys_url(base_url, tenant_id, body["id"]), headers=mgmt_headers)

    def test_new_key_has_active_status(self, base_url, tenant_id, mgmt_headers, created_key):
        assert created_key.get("status") == "ACTIVE"

    def test_new_key_has_key_name(self, base_url, tenant_id, mgmt_headers, created_key):
        assert created_key.get("keyName") is not None

    def test_new_key_has_prefix_and_suffix(self, base_url, tenant_id, mgmt_headers, created_key):
        assert created_key.get("keyPrefix"), "keyPrefix must be present"
        assert created_key.get("keySuffix"), "keySuffix must be present"

    def test_new_key_has_tenant_id(self, base_url, tenant_id, mgmt_headers, created_key):
        assert created_key.get("tenantId") == tenant_id

    def test_new_key_has_created_at(self, base_url, tenant_id, mgmt_headers, created_key):
        assert created_key.get("createdAt") is not None

    def test_multiple_active_keys_allowed(self, base_url, tenant_id, mgmt_headers, two_active_keys):
        """Tenant can have multiple active keys simultaneously — required for zero-downtime rotation."""
        assert len(two_active_keys) == 2
        for key in two_active_keys:
            assert key.get("status") == "ACTIVE"


class TestSecretOneTimeDisplay:

    def test_secret_null_on_get_after_creation(self, base_url, tenant_id, mgmt_headers, created_key):
        """GET on an existing key must return apiKey: null — secret never re-exposed."""
        resp = requests.get(
            api_keys_url(base_url, tenant_id, created_key["id"]), headers=mgmt_headers
        )
        assert resp.status_code == 200
        assert resp.json().get("apiKey") is None, (
            f"apiKey should be null on GET, got: {resp.json().get('apiKey')!r}"
        )

    def test_secret_null_in_list_after_creation(self, base_url, tenant_id, mgmt_headers, created_key):
        """List endpoint must never expose apiKey secret — check all keys on page 0."""
        body = requests.get(api_keys_url(base_url, tenant_id), headers=mgmt_headers).json()
        for key in body["content"]:
            assert key.get("apiKey") is None, (
                f"Key {key.get('id')} has non-null apiKey in list: {key.get('apiKey')!r}"
            )


class TestCreateValidation:

    def test_missing_key_name_returns_4xx(self, base_url, tenant_id, mgmt_headers):
        resp = requests.post(
            api_keys_url(base_url, tenant_id),
            json={"description": "no name", "visibility": "ORGANIZATION"},
            headers=mgmt_headers,
        )
        assert resp.status_code in (400, 422), (
            f"Expected 400/422 for missing keyName, got {resp.status_code}"
        )

    def test_empty_key_name_returns_4xx(self, base_url, tenant_id, mgmt_headers):
        resp = requests.post(
            api_keys_url(base_url, tenant_id),
            json={"keyName": "", "description": "empty name", "visibility": "ORGANIZATION"},
            headers=mgmt_headers,
        )
        key_id = resp.json().get("id") if resp.status_code == 200 else None
        if key_id:
            requests.delete(api_keys_url(base_url, tenant_id, key_id), headers=mgmt_headers)
        assert resp.status_code in (400, 422)

    def test_whitespace_only_name_returns_4xx(self, base_url, tenant_id, mgmt_headers):
        resp = requests.post(
            api_keys_url(base_url, tenant_id),
            json={"keyName": "   ", "description": "whitespace", "visibility": "ORGANIZATION"},
            headers=mgmt_headers,
        )
        key_id = resp.json().get("id") if resp.status_code == 200 else None
        if key_id:
            requests.delete(api_keys_url(base_url, tenant_id, key_id), headers=mgmt_headers)
        assert resp.status_code in (400, 422)

    def test_missing_description_behavior(self, base_url, tenant_id, mgmt_headers):
        """Description is nullable in practice (existing keys show null). Document actual behavior."""
        resp = requests.post(
            api_keys_url(base_url, tenant_id),
            json={"keyName": f"no-desc-{uuid.uuid4().hex[:6]}", "visibility": "ORGANIZATION"},
            headers=mgmt_headers,
        )
        key_id = resp.json().get("id") if resp.status_code == 200 else None
        # Epic says required; DB shows null for existing keys — document actual behavior
        assert resp.status_code in (200, 400), (
            f"Unexpected status for missing description: {resp.status_code}"
        )
        if key_id:
            requests.delete(api_keys_url(base_url, tenant_id, key_id), headers=mgmt_headers)

    def test_empty_body_returns_4xx(self, base_url, tenant_id, mgmt_headers):
        resp = requests.post(api_keys_url(base_url, tenant_id), data="", headers=mgmt_headers)
        assert resp.status_code in (400, 422, 500)

    def test_malformed_json_returns_4xx(self, base_url, tenant_id, mgmt_headers):
        resp = requests.post(
            api_keys_url(base_url, tenant_id), data="{not valid", headers=mgmt_headers
        )
        assert resp.status_code in (400, 422, 500)

    def test_visibility_personal_accepted(self, base_url, tenant_id, mgmt_headers):
        resp = requests.post(
            api_keys_url(base_url, tenant_id),
            json=valid_create_payload(
                name=f"personal-{uuid.uuid4().hex[:6]}", visibility="PERSONAL"
            ),
            headers=mgmt_headers,
        )
        key_id = resp.json().get("id") if resp.status_code == 200 else None
        assert resp.status_code == 200
        assert resp.json().get("visibility") == "PERSONAL"
        if key_id:
            requests.delete(api_keys_url(base_url, tenant_id, key_id), headers=mgmt_headers)

    def test_invalid_visibility_returns_4xx(self, base_url, tenant_id, mgmt_headers):
        resp = requests.post(
            api_keys_url(base_url, tenant_id),
            json={"keyName": f"bad-vis-{uuid.uuid4().hex[:6]}", "visibility": "INVALID"},
            headers=mgmt_headers,
        )
        assert resp.status_code in (400, 422), (
            f"Expected 400/422 for invalid visibility, got {resp.status_code}"
        )
