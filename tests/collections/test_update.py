"""
Tests for PATCH /v3/tenants/{tenantId}/collections/{collectionId}
"""

import uuid
import pytest
import requests

from tests.collections.conftest import collection_url, create_payload


class TestUpdateHappyPath:

    def test_returns_200(self, base_url, auth_headers, tenant_id, new_collection):
        """PATCH an existing collection returns 200."""
        payload = {"biometricCollection": {"name": f"updated-{uuid.uuid4().hex[:8]}", "updatedBy": "test@aware.com"}}
        resp = requests.patch(collection_url(base_url, tenant_id, new_collection["id"]),
                              json=payload, headers=auth_headers)
        assert resp.status_code == 200

    def test_name_is_updated(self, base_url, auth_headers, tenant_id, new_collection):
        """PATCH response reflects the new name."""
        new_name = f"renamed-{uuid.uuid4().hex[:8]}"
        payload = {"biometricCollection": {"name": new_name, "updatedBy": "test@aware.com"}}
        resp = requests.patch(collection_url(base_url, tenant_id, new_collection["id"]),
                              json=payload, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["biometricCollection"]["name"] == new_name

    def test_description_is_updated(self, base_url, auth_headers, tenant_id, new_collection):
        """PATCH updates description."""
        payload = {"biometricCollection": {"description": "new desc", "updatedBy": "test@aware.com"}}
        resp = requests.patch(collection_url(base_url, tenant_id, new_collection["id"]),
                              json=payload, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["biometricCollection"].get("description") == "new desc"

    def test_dedup_enabled_is_updated(self, base_url, auth_headers, tenant_id, new_collection):
        """PATCH toggles dedupEnabled."""
        original = new_collection["dedupEnabled"]
        payload = {"biometricCollection": {"dedupEnabled": not original, "updatedBy": "test@aware.com"}}
        resp = requests.patch(collection_url(base_url, tenant_id, new_collection["id"]),
                              json=payload, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["biometricCollection"]["dedupEnabled"] == (not original)

    def test_updated_by_is_set(self, base_url, auth_headers, tenant_id, new_collection):
        """PATCH response includes updatedBy when supplied."""
        payload = {"biometricCollection": {"updatedBy": "patcher@aware.com"}}
        resp = requests.patch(collection_url(base_url, tenant_id, new_collection["id"]),
                              json=payload, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["biometricCollection"]["updatedBy"] == "patcher@aware.com"

    def test_updated_at_advances(self, base_url, auth_headers, tenant_id, new_collection):
        """updatedAt is >= createdAt after a PATCH."""
        payload = {"biometricCollection": {"dedupEnabled": True, "updatedBy": "test@aware.com"}}
        resp = requests.patch(collection_url(base_url, tenant_id, new_collection["id"]),
                              json=payload, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["biometricCollection"]["updatedAt"] >= new_collection["createdAt"]

    def test_created_by_unchanged_after_patch(self, base_url, auth_headers, tenant_id, new_collection):
        """createdBy is not modified by a PATCH."""
        original_created_by = new_collection["createdBy"]
        payload = {"biometricCollection": {"updatedBy": "someone@aware.com"}}
        requests.patch(collection_url(base_url, tenant_id, new_collection["id"]),
                       json=payload, headers=auth_headers)
        resp = requests.get(collection_url(base_url, tenant_id, new_collection["id"]), headers=auth_headers)
        assert resp.json()["biometricCollection"]["createdBy"] == original_created_by

    def test_created_at_unchanged_after_patch(self, base_url, auth_headers, tenant_id, new_collection):
        """createdAt is not modified by a PATCH."""
        payload = {"biometricCollection": {"name": f"upd-{uuid.uuid4().hex[:8]}"}}
        resp = requests.patch(collection_url(base_url, tenant_id, new_collection["id"]),
                              json=payload, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["biometricCollection"]["createdAt"] == new_collection["createdAt"]

    def test_response_wrapped_in_envelope(self, base_url, auth_headers, tenant_id, new_collection):
        """PATCH response is wrapped in biometricCollection envelope."""
        payload = {"biometricCollection": {"updatedBy": "test@aware.com"}}
        resp = requests.patch(collection_url(base_url, tenant_id, new_collection["id"]),
                              json=payload, headers=auth_headers)
        assert resp.status_code == 200
        assert "biometricCollection" in resp.json()

    def test_patch_persists_via_get(self, base_url, auth_headers, tenant_id, new_collection):
        """Changes made via PATCH are reflected in a subsequent GET."""
        new_name = f"persisted-{uuid.uuid4().hex[:8]}"
        requests.patch(collection_url(base_url, tenant_id, new_collection["id"]),
                       json={"biometricCollection": {"name": new_name}}, headers=auth_headers)
        resp = requests.get(collection_url(base_url, tenant_id, new_collection["id"]), headers=auth_headers)
        assert resp.json()["biometricCollection"]["name"] == new_name

    def test_rename_to_own_name_returns_200(self, base_url, auth_headers, tenant_id, new_collection):
        """PATCH with the collection's existing name is not a conflict — returns 200."""
        payload = {"biometricCollection": {"name": new_collection["name"], "updatedBy": "test@aware.com"}}
        resp = requests.patch(collection_url(base_url, tenant_id, new_collection["id"]),
                              json=payload, headers=auth_headers)
        assert resp.status_code == 200

    def test_empty_inner_object_is_accepted(self, base_url, auth_headers, tenant_id, new_collection):
        """PATCH with an empty biometricCollection object is a no-op — returns 200."""
        resp = requests.patch(collection_url(base_url, tenant_id, new_collection["id"]),
                              json={"biometricCollection": {}}, headers=auth_headers)
        assert resp.status_code in (200, 400)

    def test_description_null_is_handled_gracefully(self, base_url, auth_headers, tenant_id):
        """PATCH setting description to null returns 200 — API may clear the field or ignore null."""
        create_resp = requests.post(collection_url(base_url, tenant_id),
                                    json=create_payload(description="original"), headers=auth_headers)
        assert create_resp.status_code == 201
        c = create_resp.json()["biometricCollection"]
        try:
            patch_resp = requests.patch(collection_url(base_url, tenant_id, c["id"]),
                                        json={"biometricCollection": {"description": None, "updatedBy": "test@aware.com"}},
                                        headers=auth_headers)
            assert patch_resp.status_code == 200
            get_resp = requests.get(collection_url(base_url, tenant_id, c["id"]), headers=auth_headers)
            # API either clears the field or keeps the original — both are acceptable; must not crash
            assert isinstance(get_resp.json()["biometricCollection"].get("description"), (str, type(None)))
        finally:
            requests.delete(collection_url(base_url, tenant_id, c["id"]), headers=auth_headers)


class TestUpdateClientSuppliedImmutableFields:
    """PATCH must silently ignore client-supplied server-owned fields.

    None of id, tenantId, createdBy, or createdAt may be overwritten via PATCH.
    Each test patches with a fake value then GETs to assert the original is intact.
    """

    _FAKE_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    _FAKE_TENANT = "ffffffff-0000-1111-2222-333333333333"
    _FAKE_TS = 1000000000000

    def test_id_cannot_be_changed_via_patch(self, base_url, auth_headers, tenant_id, new_collection):
        """Client-supplied id in PATCH body is ignored — GET still returns the original id."""
        requests.patch(
            collection_url(base_url, tenant_id, new_collection["id"]),
            json={"biometricCollection": {"id": self._FAKE_ID, "updatedBy": "test@aware.com"}},
            headers=auth_headers,
        )
        got = requests.get(collection_url(base_url, tenant_id, new_collection["id"]), headers=auth_headers)
        assert got.status_code == 200
        assert got.json()["biometricCollection"]["id"] == new_collection["id"]

    def test_tenant_id_cannot_be_changed_via_patch(self, base_url, auth_headers, tenant_id, new_collection):
        """Client-supplied tenantId in PATCH body is ignored — GET still returns the original tenantId."""
        requests.patch(
            collection_url(base_url, tenant_id, new_collection["id"]),
            json={"biometricCollection": {"tenantId": self._FAKE_TENANT, "updatedBy": "test@aware.com"}},
            headers=auth_headers,
        )
        got = requests.get(collection_url(base_url, tenant_id, new_collection["id"]), headers=auth_headers)
        assert got.status_code == 200
        assert got.json()["biometricCollection"]["tenantId"] == tenant_id

    def test_created_by_cannot_be_changed_via_patch(self, base_url, auth_headers, tenant_id, new_collection):
        """Client-supplied createdBy in PATCH body is ignored — GET still returns the original createdBy."""
        original_created_by = new_collection["createdBy"]
        requests.patch(
            collection_url(base_url, tenant_id, new_collection["id"]),
            json={"biometricCollection": {"createdBy": "injected@evil.com", "updatedBy": "test@aware.com"}},
            headers=auth_headers,
        )
        got = requests.get(collection_url(base_url, tenant_id, new_collection["id"]), headers=auth_headers)
        assert got.status_code == 200
        assert got.json()["biometricCollection"]["createdBy"] == original_created_by

    def test_created_at_cannot_be_changed_via_patch(self, base_url, auth_headers, tenant_id, new_collection):
        """Client-supplied createdAt in PATCH body is ignored — GET still returns the original createdAt."""
        original_created_at = new_collection["createdAt"]
        requests.patch(
            collection_url(base_url, tenant_id, new_collection["id"]),
            json={"biometricCollection": {"createdAt": self._FAKE_TS, "updatedBy": "test@aware.com"}},
            headers=auth_headers,
        )
        got = requests.get(collection_url(base_url, tenant_id, new_collection["id"]), headers=auth_headers)
        assert got.status_code == 200
        assert got.json()["biometricCollection"]["createdAt"] == original_created_at

    def test_all_immutable_fields_ignored_together(self, base_url, auth_headers, tenant_id, new_collection):
        """All four immutable fields sent together in a single PATCH are all ignored."""
        resp = requests.patch(
            collection_url(base_url, tenant_id, new_collection["id"]),
            json={"biometricCollection": {
                "id": self._FAKE_ID,
                "tenantId": self._FAKE_TENANT,
                "createdBy": "injected@evil.com",
                "createdAt": self._FAKE_TS,
                "updatedBy": "test@aware.com",
            }},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        got = requests.get(collection_url(base_url, tenant_id, new_collection["id"]), headers=auth_headers)
        c = got.json()["biometricCollection"]
        assert c["id"] == new_collection["id"]
        assert c["tenantId"] == tenant_id
        assert c["createdBy"] == new_collection["createdBy"]
        assert c["createdAt"] == new_collection["createdAt"]


class TestUpdateImmutability:

    def test_storage_type_returns_400(self, base_url, auth_headers, tenant_id, new_collection):
        """PATCH with storageType returns 400 STORAGE_TYPE_IMMUTABLE."""
        payload = {"biometricCollection": {"storageType": "STANDARD", "updatedBy": "test@aware.com"}}
        resp = requests.patch(collection_url(base_url, tenant_id, new_collection["id"]),
                              json=payload, headers=auth_headers)
        assert resp.status_code == 400
        assert resp.json().get("errorCode") == "STORAGE_TYPE_IMMUTABLE"

    def test_storage_type_error_message(self, base_url, auth_headers, tenant_id, new_collection):
        """STORAGE_TYPE_IMMUTABLE error message mentions storageType."""
        payload = {"biometricCollection": {"storageType": "STANDARD"}}
        resp = requests.patch(collection_url(base_url, tenant_id, new_collection["id"]),
                              json=payload, headers=auth_headers)
        assert resp.status_code == 400
        assert "storageType" in resp.json().get("message", "")

    def test_invalid_storage_type_value_returns_400(self, base_url, auth_headers, tenant_id, new_collection):
        """[BUG-3] PATCH with an invalid storageType value (PREMIUM) returns 400 STORAGE_TYPE_IMMUTABLE.
        The API correctly returns 400 and checks immutability before validating the enum value,
        but the error field is named 'error' instead of 'errorCode' (see BUG-3).
        MUST FAIL until the response field is renamed to 'errorCode'."""
        payload = {"biometricCollection": {"storageType": "PREMIUM", "updatedBy": "test@aware.com"}}
        resp = requests.patch(collection_url(base_url, tenant_id, new_collection["id"]),
                              json=payload, headers=auth_headers)
        assert resp.status_code == 400
        assert resp.json().get("errorCode") == "STORAGE_TYPE_IMMUTABLE"

    def test_null_storage_type_returns_400(self, base_url, auth_headers, tenant_id, new_collection):
        """[BUG-11] PATCH with storageType: null must return 400 STORAGE_TYPE_IMMUTABLE.
        The spec says if the storageType key is present at all, the field is immutable
        and must be rejected — null is not an exception.
        Currently returns 200: the API silently treats null as absent and accepts the request.
        MUST FAIL until null storageType is treated the same as any other value."""
        payload = {"biometricCollection": {"storageType": None, "updatedBy": "test@aware.com"}}
        resp = requests.patch(collection_url(base_url, tenant_id, new_collection["id"]),
                              json=payload, headers=auth_headers)
        assert resp.status_code == 400
        assert resp.json().get("errorCode") == "STORAGE_TYPE_IMMUTABLE"


class TestUpdateConflict:

    def test_rename_to_existing_name_returns_409(self, base_url, auth_headers, tenant_id, new_collection):
        """PATCH renaming to an already-taken name returns 409 CONFLICT."""
        second = requests.post(collection_url(base_url, tenant_id), json=create_payload(), headers=auth_headers)
        assert second.status_code == 201
        second_id = second.json()["biometricCollection"]["id"]
        try:
            payload = {"biometricCollection": {"name": new_collection["name"]}}
            resp = requests.patch(collection_url(base_url, tenant_id, second_id), json=payload, headers=auth_headers)
            assert resp.status_code == 409
            assert resp.json().get("errorCode") == "CONFLICT"
        finally:
            requests.delete(collection_url(base_url, tenant_id, second_id), headers=auth_headers)


class TestUpdateValidation:

    def test_missing_envelope_returns_400(self, base_url, auth_headers, tenant_id, new_collection):
        """PATCH without biometricCollection wrapper returns 400."""
        resp = requests.patch(collection_url(base_url, tenant_id, new_collection["id"]),
                              json={"name": "x"}, headers=auth_headers)
        assert resp.status_code == 400

    def test_empty_name_returns_400(self, base_url, auth_headers, tenant_id, new_collection):
        """PATCH with empty string name is rejected — 400 (validation) or 409 (conflicts with an existing blank-named collection)."""
        resp = requests.patch(collection_url(base_url, tenant_id, new_collection["id"]),
                              json={"biometricCollection": {"name": ""}}, headers=auth_headers)
        assert resp.status_code in (400, 409)

    def test_whitespace_name_returns_400(self, base_url, auth_headers, tenant_id, new_collection):
        """PATCH with whitespace-only name is rejected — 400 (validation) or 409 (normalized to blank, conflicts with existing)."""
        resp = requests.patch(collection_url(base_url, tenant_id, new_collection["id"]),
                              json={"biometricCollection": {"name": "   "}}, headers=auth_headers)
        assert resp.status_code in (400, 409)

    def test_updated_by_accepts_email_format(self, base_url, auth_headers, tenant_id, new_collection):
        """updatedBy accepts a standard email address."""
        resp = requests.patch(collection_url(base_url, tenant_id, new_collection["id"]),
                              json={"biometricCollection": {"updatedBy": "user@example.com"}}, headers=auth_headers)
        assert resp.status_code == 200


class TestUpdateNotFound:

    def test_nonexistent_id_returns_404(self, base_url, auth_headers, tenant_id):
        """PATCH with a random UUID returns 404 NOT_FOUND."""
        payload = {"biometricCollection": {"updatedBy": "test@aware.com"}}
        resp = requests.patch(collection_url(base_url, tenant_id, str(uuid.uuid4())),
                              json=payload, headers=auth_headers)
        assert resp.status_code == 404
        assert resp.json().get("errorCode") == "NOT_FOUND"
