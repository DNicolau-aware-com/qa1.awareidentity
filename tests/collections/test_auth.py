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
        """Invalid API key returns 401 on GET list."""
        headers = {"X-Aware-ApiKey": "0" * 64, "X-Aware-AccountId": "0001", "Content-Type": "application/json"}
        resp = requests.get(collection_url(base_url, tenant_id), headers=headers)
        assert resp.status_code == 401

    def test_invalid_api_key_on_post_returns_401(self, base_url, tenant_id):
        """Invalid API key returns 401 on POST."""
        headers = {"X-Aware-ApiKey": "0" * 64, "X-Aware-AccountId": "0001", "Content-Type": "application/json"}
        payload = {"biometricCollection": {"name": "x", "storageType": "STANDARD", "createdBy": "x"}}
        resp = requests.post(collection_url(base_url, tenant_id), json=payload, headers=headers)
        assert resp.status_code == 401

    def test_invalid_api_key_on_get_by_id_returns_401(self, base_url, tenant_id):
        """Invalid API key returns 401 on GET by ID."""
        headers = {"X-Aware-ApiKey": "0" * 64, "X-Aware-AccountId": "0001", "Content-Type": "application/json"}
        resp = requests.get(collection_url(base_url, tenant_id, str(uuid.uuid4())), headers=headers)
        assert resp.status_code == 401

    def test_invalid_api_key_on_patch_returns_401(self, base_url, tenant_id):
        """Invalid API key returns 401 on PATCH."""
        headers = {"X-Aware-ApiKey": "0" * 64, "X-Aware-AccountId": "0001", "Content-Type": "application/json"}
        payload = {"biometricCollection": {"updatedBy": "x"}}
        resp = requests.patch(collection_url(base_url, tenant_id, str(uuid.uuid4())), json=payload, headers=headers)
        assert resp.status_code == 401

    def test_invalid_api_key_on_delete_returns_401(self, base_url, tenant_id):
        """Invalid API key returns 401 on DELETE."""
        headers = {"X-Aware-ApiKey": "0" * 64, "X-Aware-AccountId": "0001", "Content-Type": "application/json"}
        resp = requests.delete(collection_url(base_url, tenant_id, str(uuid.uuid4())), headers=headers)
        assert resp.status_code == 401

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
