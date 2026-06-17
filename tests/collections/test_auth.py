"""
Auth tests for all /v3/tenants/{tenantId}/collections endpoints.

Known bugs tracked here:
  [BUG-1] Missing required headers return 500/404 instead of 401/403.
  [BUG-2] Error response field is named 'error' instead of 'errorCode' (spec mismatch).
          Tests using .get("errorCode") will FAIL until both bugs are resolved.
"""

import uuid
import requests

from tests.collections.conftest import collection_url


class TestCollectionsAuth:

    def test_invalid_api_key_returns_403(self, base_url, tenant_id):
        """Invalid API key returns 403 on GET list."""
        headers = {"X-Aware-ApiKey": "0" * 64, "X-Aware-AccountId": "0001", "Content-Type": "application/json"}
        resp = requests.get(collection_url(base_url, tenant_id), headers=headers)
        assert resp.status_code == 403

    def test_invalid_api_key_on_post_returns_403(self, base_url, tenant_id):
        """Invalid API key returns 403 on POST."""
        headers = {"X-Aware-ApiKey": "0" * 64, "X-Aware-AccountId": "0001", "Content-Type": "application/json"}
        payload = {"biometricCollection": {"name": "x", "storageType": "STANDARD", "createdBy": "x"}}
        resp = requests.post(collection_url(base_url, tenant_id), json=payload, headers=headers)
        assert resp.status_code == 403

    def test_invalid_api_key_on_get_by_id_returns_403(self, base_url, tenant_id):
        """Invalid API key returns 403 on GET by ID."""
        headers = {"X-Aware-ApiKey": "0" * 64, "X-Aware-AccountId": "0001", "Content-Type": "application/json"}
        resp = requests.get(collection_url(base_url, tenant_id, str(uuid.uuid4())), headers=headers)
        assert resp.status_code == 403

    def test_invalid_api_key_on_patch_returns_403(self, base_url, tenant_id):
        """Invalid API key returns 403 on PATCH."""
        headers = {"X-Aware-ApiKey": "0" * 64, "X-Aware-AccountId": "0001", "Content-Type": "application/json"}
        payload = {"biometricCollection": {"updatedBy": "x"}}
        resp = requests.patch(collection_url(base_url, tenant_id, str(uuid.uuid4())), json=payload, headers=headers)
        assert resp.status_code == 403

    def test_invalid_api_key_on_delete_returns_403(self, base_url, tenant_id):
        """Invalid API key returns 403 on DELETE."""
        headers = {"X-Aware-ApiKey": "0" * 64, "X-Aware-AccountId": "0001", "Content-Type": "application/json"}
        resp = requests.delete(collection_url(base_url, tenant_id, str(uuid.uuid4())), headers=headers)
        assert resp.status_code == 403

    # ------------------------------------------------------------------
    # [BUG AWRNSS-XXX] Missing required headers return 500 / 404 instead
    # of 401 / 403. These tests MUST FAIL until the bug is resolved.
    # ------------------------------------------------------------------

    def test_missing_api_key_returns_401(self, base_url, tenant_id):
        """[BUG AWRNSS-XXX] Missing X-Aware-ApiKey must return 401.
        Currently returns 500: Spring throws MissingRequestHeaderException
        because no global handler is registered for it."""
        headers = {"X-Aware-AccountId": "0001", "Content-Type": "application/json"}
        resp = requests.get(collection_url(base_url, tenant_id), headers=headers)
        assert resp.status_code == 401

    def test_missing_account_id_on_get_list_returns_403(self, base_url, auth_headers, tenant_id):
        """[BUG AWRNSS-XXX] Missing X-Aware-AccountId must return 403 on GET list.
        Currently returns 500 (absent header) or 404 (empty header)."""
        headers = {k: v for k, v in auth_headers.items() if k != "X-Aware-AccountId"}
        resp = requests.get(collection_url(base_url, tenant_id), headers=headers)
        assert resp.status_code == 403

    def test_missing_account_id_on_post_returns_403(self, base_url, auth_headers, tenant_id):
        """[BUG AWRNSS-XXX] Missing X-Aware-AccountId must return 403 on POST.
        Currently returns 500 (absent header) or 404 (empty header)."""
        headers = {k: v for k, v in auth_headers.items() if k != "X-Aware-AccountId"}
        payload = {"biometricCollection": {"name": "x", "storageType": "STANDARD", "createdBy": "x"}}
        resp = requests.post(collection_url(base_url, tenant_id), json=payload, headers=headers)
        assert resp.status_code == 403

    def test_missing_account_id_on_get_by_id_returns_403(self, base_url, auth_headers, tenant_id):
        """[BUG AWRNSS-XXX] Missing X-Aware-AccountId must return 403 on GET by ID.
        Currently returns 500 (absent header) or 404 (empty header)."""
        headers = {k: v for k, v in auth_headers.items() if k != "X-Aware-AccountId"}
        resp = requests.get(collection_url(base_url, tenant_id, str(uuid.uuid4())), headers=headers)
        assert resp.status_code == 403

    def test_missing_account_id_on_patch_returns_403(self, base_url, auth_headers, tenant_id):
        """[BUG AWRNSS-XXX] Missing X-Aware-AccountId must return 403 on PATCH.
        Currently returns 500 (absent header) or 404 (empty header)."""
        headers = {k: v for k, v in auth_headers.items() if k != "X-Aware-AccountId"}
        payload = {"biometricCollection": {"updatedBy": "x"}}
        resp = requests.patch(collection_url(base_url, tenant_id, str(uuid.uuid4())), json=payload, headers=headers)
        assert resp.status_code == 403

    def test_missing_account_id_on_delete_returns_403(self, base_url, auth_headers, tenant_id):
        """[BUG AWRNSS-XXX] Missing X-Aware-AccountId must return 403 on DELETE.
        Currently returns 500 (absent header) or 404 (empty header)."""
        headers = {k: v for k, v in auth_headers.items() if k != "X-Aware-AccountId"}
        resp = requests.delete(collection_url(base_url, tenant_id, str(uuid.uuid4())), headers=headers)
        assert resp.status_code == 403
