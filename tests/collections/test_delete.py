"""
Tests for DELETE /v3/tenants/{tenantId}/collections/{collectionId}
"""

import uuid
import requests

from tests.collections.conftest import collection_url, create_payload


class TestDeleteHappyPath:

    def test_returns_204(self, base_url, auth_headers, tenant_id):
        """DELETE returns 204 No Content."""
        resp = requests.post(collection_url(base_url, tenant_id), json=create_payload(), headers=auth_headers)
        assert resp.status_code == 201
        cid = resp.json()["biometricCollection"]["id"]
        assert requests.delete(collection_url(base_url, tenant_id, cid), headers=auth_headers).status_code == 204

    def test_response_has_no_body(self, base_url, auth_headers, tenant_id):
        """DELETE 204 response has an empty body."""
        resp = requests.post(collection_url(base_url, tenant_id), json=create_payload(), headers=auth_headers)
        cid = resp.json()["biometricCollection"]["id"]
        del_resp = requests.delete(collection_url(base_url, tenant_id, cid), headers=auth_headers)
        assert del_resp.status_code == 204
        assert del_resp.text == ""

    def test_delete_decrements_total_elements(self, base_url, auth_headers, tenant_id):
        """totalElements for the collection's name drops to 0 after DELETE."""
        resp = requests.post(collection_url(base_url, tenant_id), json=create_payload(), headers=auth_headers)
        assert resp.status_code == 201
        c = resp.json()["biometricCollection"]

        requests.delete(collection_url(base_url, tenant_id, c["id"]), headers=auth_headers)

        list_resp = requests.get(collection_url(base_url, tenant_id),
                                 params={"name": c["name"]}, headers=auth_headers)
        assert list_resp.json()["totalElements"] == 0


class TestDeleteSoftDelete:

    def test_deleted_collection_get_returns_404(self, base_url, auth_headers, tenant_id):
        """GET a soft-deleted collection returns 404 NOT_FOUND."""
        resp = requests.post(collection_url(base_url, tenant_id), json=create_payload(), headers=auth_headers)
        assert resp.status_code == 201
        cid = resp.json()["biometricCollection"]["id"]
        requests.delete(collection_url(base_url, tenant_id, cid), headers=auth_headers)

        resp = requests.get(collection_url(base_url, tenant_id, cid), headers=auth_headers)
        assert resp.status_code == 404
        assert resp.json().get("error") == "NOT_FOUND"

    def test_deleted_collection_excluded_from_list(self, base_url, auth_headers, tenant_id):
        """Soft-deleted collection does not appear in list results."""
        resp = requests.post(collection_url(base_url, tenant_id), json=create_payload(), headers=auth_headers)
        assert resp.status_code == 201
        c = resp.json()["biometricCollection"]
        requests.delete(collection_url(base_url, tenant_id, c["id"]), headers=auth_headers)

        list_resp = requests.get(collection_url(base_url, tenant_id),
                                 params={"name": c["name"]}, headers=auth_headers)
        ids = [x["id"] for x in list_resp.json()["biometricCollections"]]
        assert c["id"] not in ids

    def test_deleted_collection_patch_returns_404(self, base_url, auth_headers, tenant_id):
        """PATCH a soft-deleted collection returns 404."""
        resp = requests.post(collection_url(base_url, tenant_id), json=create_payload(), headers=auth_headers)
        cid = resp.json()["biometricCollection"]["id"]
        requests.delete(collection_url(base_url, tenant_id, cid), headers=auth_headers)

        patch_resp = requests.patch(collection_url(base_url, tenant_id, cid),
                                    json={"biometricCollection": {"updatedBy": "x"}}, headers=auth_headers)
        assert patch_resp.status_code == 404


class TestDeleteNotFound:

    def test_nonexistent_id_returns_404(self, base_url, auth_headers, tenant_id):
        """DELETE a random UUID returns 404 NOT_FOUND."""
        resp = requests.delete(collection_url(base_url, tenant_id, str(uuid.uuid4())), headers=auth_headers)
        assert resp.status_code == 404
        assert resp.json().get("error") == "NOT_FOUND"

    def test_already_deleted_returns_404(self, base_url, auth_headers, tenant_id):
        """DELETE a soft-deleted collection a second time returns 404."""
        resp = requests.post(collection_url(base_url, tenant_id), json=create_payload(), headers=auth_headers)
        cid = resp.json()["biometricCollection"]["id"]
        requests.delete(collection_url(base_url, tenant_id, cid), headers=auth_headers)

        resp = requests.delete(collection_url(base_url, tenant_id, cid), headers=auth_headers)
        assert resp.status_code == 404

    def test_non_uuid_id_returns_400_or_404(self, base_url, auth_headers, tenant_id):
        """[BUG-2] DELETE with a non-UUID collectionId must return 400 or 404.
        Currently returns 500 — MethodArgumentTypeMismatchException is unhandled.
        MUST FAIL until fixed."""
        resp = requests.delete(collection_url(base_url, tenant_id, "not-a-uuid"), headers=auth_headers)
        assert resp.status_code in (400, 404)
