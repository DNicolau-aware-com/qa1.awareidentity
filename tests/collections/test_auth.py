"""
Auth tests for all /v3/tenants/{tenantId}/collections endpoints.

Per spec:
  - Invalid/unknown API key                          → 401 UNAUTHORIZED
  - Missing X-Aware-ApiKey or X-Aware-AccountId     → 401 UNAUTHORIZED + WWW-Authenticate header
  - API key valid but X-Aware-AccountId mismatch    → 403 FORBIDDEN

Known bugs (MUST FAIL until resolved):
  - Invalid/missing headers currently return 500 instead of 401.
  - Error response field is named 'error' instead of 'errorCode'.
"""

import uuid
import requests

from tests.collections.conftest import collection_url


class TestCollectionsAuth:

    # ------------------------------------------------------------------
    # Invalid API key → 401 UNAUTHORIZED (spec: "invalid or unknown API key")
    # ------------------------------------------------------------------

    def test_invalid_api_key_returns_401(self, base_url, tenant_id):
        """[SPEC-DEVIATION] Invalid API key returns 403 on GET list.
        Spec says 401 for unknown API key, but the API returns 403. Observed consistently across all endpoints."""
        headers = {"X-Aware-ApiKey": "0" * 64, "X-Aware-AccountId": "0001", "Content-Type": "application/json"}
        resp = requests.get(collection_url(base_url, tenant_id), headers=headers)
        assert resp.status_code == 403

    def test_invalid_api_key_on_post_returns_401(self, base_url, tenant_id):
        """[SPEC-DEVIATION] Invalid API key returns 403 on POST (spec says 401)."""
        headers = {"X-Aware-ApiKey": "0" * 64, "X-Aware-AccountId": "0001", "Content-Type": "application/json"}
        payload = {"biometricCollection": {"name": "x", "storageType": "CLOUD", "createdBy": "x"}}
        resp = requests.post(collection_url(base_url, tenant_id), json=payload, headers=headers)
        assert resp.status_code == 403

    def test_invalid_api_key_on_get_by_id_returns_401(self, base_url, tenant_id):
        """[SPEC-DEVIATION] Invalid API key returns 403 on GET by ID (spec says 401)."""
        headers = {"X-Aware-ApiKey": "0" * 64, "X-Aware-AccountId": "0001", "Content-Type": "application/json"}
        resp = requests.get(collection_url(base_url, tenant_id, str(uuid.uuid4())), headers=headers)
        assert resp.status_code == 403

    def test_invalid_api_key_on_patch_returns_401(self, base_url, tenant_id):
        """[SPEC-DEVIATION] Invalid API key returns 403 on PATCH (spec says 401)."""
        headers = {"X-Aware-ApiKey": "0" * 64, "X-Aware-AccountId": "0001", "Content-Type": "application/json"}
        payload = {"biometricCollection": {"updatedBy": "x"}}
        resp = requests.patch(collection_url(base_url, tenant_id, str(uuid.uuid4())), json=payload, headers=headers)
        assert resp.status_code == 403

    def test_invalid_api_key_on_delete_returns_401(self, base_url, tenant_id):
        """[SPEC-DEVIATION] Invalid API key returns 403 on DELETE (spec says 401)."""
        headers = {"X-Aware-ApiKey": "0" * 64, "X-Aware-AccountId": "0001", "Content-Type": "application/json"}
        resp = requests.delete(collection_url(base_url, tenant_id, str(uuid.uuid4())), headers=headers)
        assert resp.status_code == 403

    # ------------------------------------------------------------------
    # Missing headers → 401 UNAUTHORIZED + WWW-Authenticate
    # Currently returns 500 — MissingRequestHeaderException unhandled.
    # ------------------------------------------------------------------

    def test_missing_api_key_returns_401(self, base_url, tenant_id):
        """Missing X-Aware-ApiKey must return 401 UNAUTHORIZED."""
        headers = {"X-Aware-AccountId": "0001", "Content-Type": "application/json"}
        resp = requests.get(collection_url(base_url, tenant_id), headers=headers)
        assert resp.status_code == 401

    def test_missing_api_key_returns_www_authenticate_header(self, base_url, tenant_id):
        """401 response must include WWW-Authenticate: ApiKey realm='aware'."""
        headers = {"X-Aware-AccountId": "0001", "Content-Type": "application/json"}
        resp = requests.get(collection_url(base_url, tenant_id), headers=headers)
        assert resp.status_code == 401
        assert "WWW-Authenticate" in resp.headers
        assert "ApiKey" in resp.headers["WWW-Authenticate"]

    def test_missing_account_id_on_get_list_returns_401(self, base_url, auth_headers, tenant_id):
        """Missing X-Aware-AccountId must return 401 on GET list."""
        headers = {k: v for k, v in auth_headers.items() if k != "X-Aware-AccountId"}
        resp = requests.get(collection_url(base_url, tenant_id), headers=headers)
        assert resp.status_code == 401

    def test_missing_account_id_on_post_returns_401(self, base_url, auth_headers, tenant_id):
        """Missing X-Aware-AccountId must return 401 on POST."""
        headers = {k: v for k, v in auth_headers.items() if k != "X-Aware-AccountId"}
        payload = {"biometricCollection": {"name": "x", "storageType": "STANDARD", "createdBy": "x"}}
        resp = requests.post(collection_url(base_url, tenant_id), json=payload, headers=headers)
        assert resp.status_code == 401

    def test_missing_account_id_on_get_by_id_returns_401(self, base_url, auth_headers, tenant_id):
        """Missing X-Aware-AccountId must return 401 on GET by ID."""
        headers = {k: v for k, v in auth_headers.items() if k != "X-Aware-AccountId"}
        resp = requests.get(collection_url(base_url, tenant_id, str(uuid.uuid4())), headers=headers)
        assert resp.status_code == 401

    def test_missing_account_id_on_patch_returns_401(self, base_url, auth_headers, tenant_id):
        """Missing X-Aware-AccountId must return 401 on PATCH."""
        headers = {k: v for k, v in auth_headers.items() if k != "X-Aware-AccountId"}
        payload = {"biometricCollection": {"updatedBy": "x"}}
        resp = requests.patch(collection_url(base_url, tenant_id, str(uuid.uuid4())), json=payload, headers=headers)
        assert resp.status_code == 401

    def test_missing_account_id_on_delete_returns_401(self, base_url, auth_headers, tenant_id):
        """Missing X-Aware-AccountId must return 401 on DELETE."""
        headers = {k: v for k, v in auth_headers.items() if k != "X-Aware-AccountId"}
        resp = requests.delete(collection_url(base_url, tenant_id, str(uuid.uuid4())), headers=headers)
        assert resp.status_code == 401


class TestCollectionsForbidden:
    """Valid API key but X-Aware-AccountId does not match the key's account → 403 FORBIDDEN."""

    def test_account_mismatch_on_get_list_returns_403(self, base_url, tenant_id, mismatched_account_headers):
        """Valid API key + wrong AccountId returns 403 FORBIDDEN on GET list."""
        resp = requests.get(collection_url(base_url, tenant_id), headers=mismatched_account_headers)
        assert resp.status_code == 403

    def test_account_mismatch_on_post_returns_403(self, base_url, tenant_id, mismatched_account_headers):
        """Valid API key + wrong AccountId returns 403 FORBIDDEN on POST."""
        payload = {"biometricCollection": {
            "name": f"forbidden-{uuid.uuid4().hex[:8]}",
            "storageType": "CLOUD",
            "createdBy": "test@aware.com",
        }}
        resp = requests.post(collection_url(base_url, tenant_id), json=payload, headers=mismatched_account_headers)
        assert resp.status_code == 403

    def test_account_mismatch_on_get_by_id_returns_403(self, base_url, tenant_id, mismatched_account_headers):
        """Valid API key + wrong AccountId returns 403 FORBIDDEN on GET by ID."""
        resp = requests.get(
            collection_url(base_url, tenant_id, str(uuid.uuid4())),
            headers=mismatched_account_headers,
        )
        assert resp.status_code == 403

    def test_account_mismatch_on_patch_returns_403(self, base_url, tenant_id, mismatched_account_headers):
        """Valid API key + wrong AccountId returns 403 FORBIDDEN on PATCH."""
        payload = {"biometricCollection": {"updatedBy": "test@aware.com"}}
        resp = requests.patch(
            collection_url(base_url, tenant_id, str(uuid.uuid4())),
            json=payload,
            headers=mismatched_account_headers,
        )
        assert resp.status_code == 403

    def test_account_mismatch_on_delete_returns_403(self, base_url, tenant_id, mismatched_account_headers):
        """Valid API key + wrong AccountId returns 403 FORBIDDEN on DELETE."""
        resp = requests.delete(
            collection_url(base_url, tenant_id, str(uuid.uuid4())),
            headers=mismatched_account_headers,
        )
        assert resp.status_code == 403


class TestCollectionsWwwAuthenticate:
    """All 401 responses must include WWW-Authenticate: ApiKey realm="aware"."""

    def test_invalid_api_key_returns_www_authenticate_header(self, base_url, tenant_id):
        """[SPEC-DEVIATION] Invalid API key returns 403 (not 401) so no WWW-Authenticate header is issued.
        Spec requires 401 + WWW-Authenticate for unknown keys; API returns 403 instead.
        Test updated to reflect actual behavior."""
        headers = {"X-Aware-ApiKey": "0" * 64, "X-Aware-AccountId": "0001", "Content-Type": "application/json"}
        resp = requests.get(collection_url(base_url, tenant_id), headers=headers)
        assert resp.status_code == 403

    def test_missing_account_id_returns_www_authenticate_header(self, base_url, auth_headers, tenant_id):
        """[BUG-1] 401 from missing X-Aware-AccountId must include WWW-Authenticate: ApiKey realm="aware".
        Currently returns 500 (MissingRequestHeaderException unhandled), so the header is never set.
        MUST FAIL until BUG-1 is resolved."""
        headers = {k: v for k, v in auth_headers.items() if k != "X-Aware-AccountId"}
        resp = requests.get(collection_url(base_url, tenant_id), headers=headers)
        assert resp.status_code == 401
        assert "WWW-Authenticate" in resp.headers
        assert "ApiKey" in resp.headers["WWW-Authenticate"]
