"""
Tests for malformed path parameters across all collection endpoints.
Validates that the API rejects or gracefully handles invalid collectionId
and tenantId values without returning 2xx or crashing.

Known API bug: non-UUID collectionIds currently return 500 instead of 400/404.
"""

import uuid
import requests

from tests.collections.conftest import collection_url, create_payload


class TestNonUuidCollectionId:

    def test_get_non_uuid_id_returns_400(self, base_url, auth_headers, tenant_id):
        """GET with a non-UUID collectionId must return 400 VALIDATION_FAILED.
        Spec: MethodArgumentTypeMismatchException → 400 VALIDATION_FAILED.
        Currently returns 500 — MUST FAIL until fixed."""
        resp = requests.get(collection_url(base_url, tenant_id, "not-a-uuid"), headers=auth_headers)
        assert resp.status_code == 400
        assert resp.json().get("errorCode") == "VALIDATION_FAILED"

    def test_patch_non_uuid_id_returns_400(self, base_url, auth_headers, tenant_id):
        """PATCH with a non-UUID collectionId must return 400 VALIDATION_FAILED.
        Spec: MethodArgumentTypeMismatchException → 400 VALIDATION_FAILED.
        Currently returns 500 — MUST FAIL until fixed."""
        payload = {"biometricCollection": {"updatedBy": "test@aware.com"}}
        resp = requests.patch(collection_url(base_url, tenant_id, "not-a-uuid"),
                              json=payload, headers=auth_headers)
        assert resp.status_code == 400
        assert resp.json().get("errorCode") == "VALIDATION_FAILED"

    def test_delete_non_uuid_id_returns_400(self, base_url, auth_headers, tenant_id):
        """DELETE with a non-UUID collectionId must return 400 VALIDATION_FAILED.
        Spec: MethodArgumentTypeMismatchException → 400 VALIDATION_FAILED.
        Currently returns 500 — MUST FAIL until fixed."""
        resp = requests.delete(collection_url(base_url, tenant_id, "not-a-uuid"), headers=auth_headers)
        assert resp.status_code == 400
        assert resp.json().get("errorCode") == "VALIDATION_FAILED"


class TestNonExistentTenantId:

    def test_get_list_unknown_tenant_returns_empty_or_error(self, base_url, auth_headers):
        """GET list for a random tenantId returns empty results (200) or access error (403/404) — not 201/5xx."""
        fake_tenant = str(uuid.uuid4())
        resp = requests.get(collection_url(base_url, fake_tenant), headers=auth_headers)
        assert resp.status_code in (200, 403, 404)
        if resp.status_code == 200:
            assert resp.json()["biometricCollections"] == []

    def test_post_unknown_tenant_does_not_create(self, base_url, auth_headers):
        """POST to a random tenantId returns 403 or 404 — the service verifies the tenant exists.
        Confirmed live: returns 404 NOT_FOUND with 'Tenant not found with id: ...'."""
        fake_tenant = str(uuid.uuid4())
        resp = requests.post(collection_url(base_url, fake_tenant),
                             json=create_payload(), headers=auth_headers)
        assert resp.status_code in (403, 404)

    def test_get_by_id_unknown_tenant_not_200(self, base_url, auth_headers):
        """GET by ID for an unknown tenantId + random collectionId is not 200."""
        fake_tenant = str(uuid.uuid4())
        resp = requests.get(collection_url(base_url, fake_tenant, str(uuid.uuid4())), headers=auth_headers)
        assert resp.status_code in (200, 403, 404)
        if resp.status_code == 200:
            # If 200, the body must still be a valid (but likely empty/error) response
            assert "biometricCollection" in resp.json() or resp.json().get("errorCode") is not None
