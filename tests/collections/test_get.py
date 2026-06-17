"""
Tests for GET /v3/tenants/{tenantId}/collections/{collectionId}
"""

import uuid
import requests

from tests.collections.conftest import collection_url


class TestGetByIdHappyPath:

    def test_returns_200(self, base_url, auth_headers, tenant_id, new_collection):
        """GET by ID returns 200 for an existing collection."""
        resp = requests.get(collection_url(base_url, tenant_id, new_collection["id"]), headers=auth_headers)
        assert resp.status_code == 200

    def test_response_contains_required_fields(self, base_url, auth_headers, tenant_id, new_collection):
        """Response contains all required fields per spec."""
        resp = requests.get(collection_url(base_url, tenant_id, new_collection["id"]), headers=auth_headers)
        c = resp.json()["biometricCollection"]
        for field in ("id", "tenantId", "name", "storageType", "dedupEnabled", "createdBy", "createdAt", "updatedAt"):
            assert field in c, f"Missing field: {field}"

    def test_response_wrapped_in_envelope(self, base_url, auth_headers, tenant_id, new_collection):
        """Response is wrapped in biometricCollection envelope."""
        resp = requests.get(collection_url(base_url, tenant_id, new_collection["id"]), headers=auth_headers)
        assert "biometricCollection" in resp.json()

    def test_returned_id_matches_requested_id(self, base_url, auth_headers, tenant_id, new_collection):
        """Returned collection id matches the requested collectionId."""
        resp = requests.get(collection_url(base_url, tenant_id, new_collection["id"]), headers=auth_headers)
        assert resp.json()["biometricCollection"]["id"] == new_collection["id"]

    def test_timestamps_are_integer_milliseconds(self, base_url, auth_headers, tenant_id, new_collection):
        """createdAt and updatedAt are positive integers (epoch ms)."""
        resp = requests.get(collection_url(base_url, tenant_id, new_collection["id"]), headers=auth_headers)
        c = resp.json()["biometricCollection"]
        assert isinstance(c["createdAt"], int) and c["createdAt"] > 0
        assert isinstance(c["updatedAt"], int) and c["updatedAt"] > 0

    def test_response_content_type_is_json(self, base_url, auth_headers, tenant_id, new_collection):
        """Response Content-Type is application/json."""
        resp = requests.get(collection_url(base_url, tenant_id, new_collection["id"]), headers=auth_headers)
        assert "application/json" in resp.headers.get("Content-Type", "")


class TestGetByIdDataIntegrity:

    def test_fields_match_create_payload(self, base_url, auth_headers, tenant_id, new_collection):
        """GET returns the exact field values that were supplied on creation."""
        resp = requests.get(collection_url(base_url, tenant_id, new_collection["id"]), headers=auth_headers)
        c = resp.json()["biometricCollection"]
        assert c["name"] == new_collection["name"]
        assert c["storageType"] == new_collection["storageType"]
        assert c["createdBy"] == new_collection["createdBy"]

    def test_tenant_id_matches_path(self, base_url, auth_headers, tenant_id, new_collection):
        """tenantId in the response body matches the tenantId in the URL path."""
        resp = requests.get(collection_url(base_url, tenant_id, new_collection["id"]), headers=auth_headers)
        assert resp.json()["biometricCollection"]["tenantId"] == tenant_id


class TestGetByIdNotFound:

    def test_nonexistent_id_returns_404(self, base_url, auth_headers, tenant_id):
        """GET with a random UUID returns 404 NOT_FOUND."""
        resp = requests.get(collection_url(base_url, tenant_id, str(uuid.uuid4())), headers=auth_headers)
        assert resp.status_code == 404
        assert resp.json().get("errorCode") == "NOT_FOUND"

    def test_soft_deleted_collection_returns_404(self, base_url, auth_headers, tenant_id):
        """GET a soft-deleted collection returns 404 NOT_FOUND."""
        import requests as req
        from tests.collections.conftest import create_payload
        create_resp = req.post(collection_url(base_url, tenant_id), json=create_payload(), headers=auth_headers)
        assert create_resp.status_code == 201
        cid = create_resp.json()["biometricCollection"]["id"]
        req.delete(collection_url(base_url, tenant_id, cid), headers=auth_headers)

        resp = req.get(collection_url(base_url, tenant_id, cid), headers=auth_headers)
        assert resp.status_code == 404
        assert resp.json().get("errorCode") == "NOT_FOUND"
