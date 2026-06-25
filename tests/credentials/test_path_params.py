"""
Malformed path-parameter tests for the credentials endpoints.

Per spec (Error table): a non-UUID path variable must return 400 VALIDATION_FAILED.
[BUG #4] The service currently returns 500 Internal Server Error for any
non-UUID / oversized tenantId, collectionId, or credentialId
(MethodArgumentTypeMismatchException → UUID conversion failure is unhandled).
These tests MUST FAIL until the bug is fixed.

Origin: discovered via a malformed request where a UUID had extra text appended
(e.g. `{{tenantId}}tenantId`), yielding "UUID string too large" → 500.
"""

import uuid
import requests

from tests.credentials.conftest import credential_url


class TestNonUuidTenantId:

    def test_non_uuid_tenant_get_list_returns_400(self, base_url, auth_headers, collection_id):
        """GET list with a non-UUID tenantId must return 400 VALIDATION_FAILED."""
        resp = requests.get(credential_url(base_url, "not-a-uuid", collection_id), headers=auth_headers)
        assert resp.status_code == 400
        assert resp.json().get("error") == "VALIDATION_FAILED"

    def test_oversized_tenant_get_list_returns_400(self, base_url, auth_headers, tenant_id, collection_id):
        """GET list with an oversized tenantId (UUID + extra chars) must return 400, not 500.
        Reproduces the 'UUID string too large' 500 from a malformed request."""
        resp = requests.get(credential_url(base_url, f"{tenant_id}extra", collection_id), headers=auth_headers)
        assert resp.status_code == 400
        assert resp.json().get("error") == "VALIDATION_FAILED"

    def test_non_uuid_tenant_get_by_id_returns_400(self, base_url, auth_headers, collection_id):
        """GET by credentialId with a non-UUID tenantId must return 400 VALIDATION_FAILED."""
        resp = requests.get(
            credential_url(base_url, "not-a-uuid", collection_id, str(uuid.uuid4())),
            headers=auth_headers,
        )
        assert resp.status_code == 400
        assert resp.json().get("error") == "VALIDATION_FAILED"


class TestNonUuidCollectionId:

    def test_non_uuid_collection_get_list_returns_400(self, base_url, auth_headers, tenant_id):
        """GET list with a non-UUID collectionId must return 400 VALIDATION_FAILED."""
        resp = requests.get(credential_url(base_url, tenant_id, "not-a-uuid"), headers=auth_headers)
        assert resp.status_code == 400
        assert resp.json().get("error") == "VALIDATION_FAILED"

    def test_oversized_collection_get_list_returns_400(self, base_url, auth_headers, tenant_id, collection_id):
        """GET list with an oversized collectionId (UUID + extra chars) must return 400, not 500."""
        resp = requests.get(credential_url(base_url, tenant_id, f"{collection_id}extra"), headers=auth_headers)
        assert resp.status_code == 400
        assert resp.json().get("error") == "VALIDATION_FAILED"

    def test_non_uuid_collection_get_by_id_returns_400(self, base_url, auth_headers, tenant_id):
        """GET by credentialId with a non-UUID collectionId must return 400 VALIDATION_FAILED."""
        resp = requests.get(
            credential_url(base_url, tenant_id, "not-a-uuid", str(uuid.uuid4())),
            headers=auth_headers,
        )
        assert resp.status_code == 400
        assert resp.json().get("error") == "VALIDATION_FAILED"
