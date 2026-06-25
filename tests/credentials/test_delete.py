"""
Tests for:
  DELETE /v3/tenants/{tenantId}/collections/{collectionId}/credentials/{credentialId}
  DELETE /v3/tenants/{tenantId}/collections/{collectionId}/credentials?externalUserId={userId}

Credentials use soft delete — deleted records are excluded from queries but not purged.
"""

import uuid
import requests

from tests.credentials.conftest import credential_url, create_credential_payload


class TestDeleteByIdHappyPath:

    def test_returns_204(self, base_url, auth_headers, tenant_id, collection_id):
        """DELETE by credentialId returns 204 No Content."""
        resp = requests.post(
            credential_url(base_url, tenant_id, collection_id),
            json=create_credential_payload(),
            headers=auth_headers,
        )
        assert resp.status_code == 201
        cid = resp.json()["biometricCredential"]["id"]
        assert requests.delete(
            credential_url(base_url, tenant_id, collection_id, cid), headers=auth_headers
        ).status_code == 204

    def test_response_has_no_body(self, base_url, auth_headers, tenant_id, collection_id):
        """DELETE 204 response has an empty body."""
        resp = requests.post(
            credential_url(base_url, tenant_id, collection_id),
            json=create_credential_payload(),
            headers=auth_headers,
        )
        cid = resp.json()["biometricCredential"]["id"]
        del_resp = requests.delete(credential_url(base_url, tenant_id, collection_id, cid), headers=auth_headers)
        assert del_resp.status_code == 204
        assert del_resp.text == ""


class TestDeleteByIdSoftDelete:

    def test_deleted_credential_get_returns_404(self, base_url, auth_headers, tenant_id, collection_id):
        """GET a deleted credential returns 404 NOT_FOUND.
        """
        resp = requests.post(
            credential_url(base_url, tenant_id, collection_id),
            json=create_credential_payload(),
            headers=auth_headers,
        )
        assert resp.status_code == 201
        cid = resp.json()["biometricCredential"]["id"]
        requests.delete(credential_url(base_url, tenant_id, collection_id, cid), headers=auth_headers)

        resp = requests.get(credential_url(base_url, tenant_id, collection_id, cid), headers=auth_headers)
        assert resp.status_code == 404
        assert resp.json().get("error") == "NOT_FOUND"

    def test_deleted_credential_excluded_from_user_id_search(self, base_url, auth_headers, tenant_id, collection_id):
        """GET ?userId= for a deleted credential returns 404 (not found, not empty list)."""
        user_id = f"user-{uuid.uuid4().hex[:8]}"
        resp = requests.post(
            credential_url(base_url, tenant_id, collection_id),
            json={"biometricCredential": {"externalUserId": user_id, "biometrics": {}}},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        cid = resp.json()["biometricCredential"]["id"]
        requests.delete(credential_url(base_url, tenant_id, collection_id, cid), headers=auth_headers)

        list_resp = requests.get(
            credential_url(base_url, tenant_id, collection_id),
            params={"userId": user_id},
            headers=auth_headers,
        )
        assert list_resp.status_code == 404
        assert list_resp.json().get("error") == "NOT_FOUND"

    def test_deleted_credential_patch_returns_404(self, base_url, auth_headers, tenant_id, collection_id):
        """PATCH a deleted credential returns 404."""
        resp = requests.post(
            credential_url(base_url, tenant_id, collection_id),
            json=create_credential_payload(),
            headers=auth_headers,
        )
        cid = resp.json()["biometricCredential"]["id"]
        requests.delete(credential_url(base_url, tenant_id, collection_id, cid), headers=auth_headers)

        patch_resp = requests.patch(
            credential_url(base_url, tenant_id, collection_id, cid),
            json={"biometricCredential": {"updatedBy": "x"}},
            headers=auth_headers,
        )
        assert patch_resp.status_code == 404
        assert patch_resp.json().get("error") == "NOT_FOUND"


class TestDeleteByIdNotFound:

    def test_nonexistent_id_returns_404(self, base_url, auth_headers, tenant_id, collection_id):
        """DELETE a random UUID returns 404 NOT_FOUND.
        """
        resp = requests.delete(
            credential_url(base_url, tenant_id, collection_id, str(uuid.uuid4())),
            headers=auth_headers,
        )
        assert resp.status_code == 404
        assert resp.json().get("error") == "NOT_FOUND"

    def test_already_deleted_returns_404(self, base_url, auth_headers, tenant_id, collection_id):
        """DELETE a credential a second time returns 404."""
        resp = requests.post(
            credential_url(base_url, tenant_id, collection_id),
            json=create_credential_payload(),
            headers=auth_headers,
        )
        cid = resp.json()["biometricCredential"]["id"]
        requests.delete(credential_url(base_url, tenant_id, collection_id, cid), headers=auth_headers)

        resp = requests.delete(credential_url(base_url, tenant_id, collection_id, cid), headers=auth_headers)
        assert resp.status_code == 404
        assert resp.json().get("error") == "NOT_FOUND"

    def test_non_uuid_id_returns_400(self, base_url, auth_headers, tenant_id, collection_id):
        """DELETE with a non-UUID credentialId must return 400 VALIDATION_FAILED.
        Currently returns 500 — MethodArgumentTypeMismatchException unhandled. MUST FAIL until fixed."""
        resp = requests.delete(
            credential_url(base_url, tenant_id, collection_id, "not-a-uuid"),
            headers=auth_headers,
        )
        assert resp.status_code == 400
        assert resp.json().get("error") == "VALIDATION_FAILED"


class TestDeleteByUserIdHappyPath:
    # Per spec, the delete-by-user query param is `userId` (matched against `externalUserId`).

    def test_returns_204(self, base_url, auth_headers, tenant_id, collection_id):
        """DELETE ?userId= returns 204 No Content."""
        user_id = f"user-{uuid.uuid4().hex[:8]}"
        resp = requests.post(
            credential_url(base_url, tenant_id, collection_id),
            json={"biometricCredential": {"externalUserId": user_id, "biometrics": {}}},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        del_resp = requests.delete(
            credential_url(base_url, tenant_id, collection_id),
            params={"userId": user_id},
            headers=auth_headers,
        )
        assert del_resp.status_code == 204

    def test_delete_by_user_id_removes_credential(self, base_url, auth_headers, tenant_id, collection_id):
        """DELETE ?userId= soft-deletes the credential — GET ?userId= returns 404 after."""
        user_id = f"user-{uuid.uuid4().hex[:8]}"
        resp = requests.post(
            credential_url(base_url, tenant_id, collection_id),
            json={"biometricCredential": {"externalUserId": user_id, "biometrics": {}}},
            headers=auth_headers,
        )
        assert resp.status_code == 201

        requests.delete(
            credential_url(base_url, tenant_id, collection_id),
            params={"userId": user_id},
            headers=auth_headers,
        )

        get_resp = requests.get(
            credential_url(base_url, tenant_id, collection_id),
            params={"userId": user_id},
            headers=auth_headers,
        )
        assert get_resp.status_code == 404

    def test_delete_by_user_id_does_not_affect_other_users(self, base_url, auth_headers, tenant_id, collection_id):
        """DELETE ?userId= only removes the credential for the specified user."""
        user_a = f"user-a-{uuid.uuid4().hex[:8]}"
        user_b = f"user-b-{uuid.uuid4().hex[:8]}"

        resp_a = requests.post(
            credential_url(base_url, tenant_id, collection_id),
            json={"biometricCredential": {"externalUserId": user_a, "biometrics": {}}},
            headers=auth_headers,
        )
        resp_b = requests.post(
            credential_url(base_url, tenant_id, collection_id),
            json={"biometricCredential": {"externalUserId": user_b, "biometrics": {}}},
            headers=auth_headers,
        )
        assert resp_a.status_code == 201
        assert resp_b.status_code == 201
        id_b = resp_b.json()["biometricCredential"]["id"]

        requests.delete(
            credential_url(base_url, tenant_id, collection_id),
            params={"userId": user_a},
            headers=auth_headers,
        )

        try:
            list_resp = requests.get(
                credential_url(base_url, tenant_id, collection_id),
                params={"userId": user_b},
                headers=auth_headers,
            )
            assert list_resp.status_code == 200
            ids = [c["id"] for c in list_resp.json().get("biometricCredentials", [])]
            assert id_b in ids
        finally:
            requests.delete(credential_url(base_url, tenant_id, collection_id, id_b), headers=auth_headers)


class TestDeleteByUserIdNotFound:

    def test_unknown_user_id_returns_404(self, base_url, auth_headers, tenant_id, collection_id):
        """DELETE ?userId= for an unknown userId returns 404."""
        resp = requests.delete(
            credential_url(base_url, tenant_id, collection_id),
            params={"userId": f"ghost-{uuid.uuid4().hex}"},
            headers=auth_headers,
        )
        assert resp.status_code == 404
        assert resp.json().get("error") == "NOT_FOUND"


class TestDeleteByIdWrongCollection:

    def test_credential_in_wrong_collection_returns_404(self, base_url, auth_headers, tenant_id, collection_id):
        """DELETE a valid credentialId via a different collectionId returns 404."""
        resp = requests.post(
            credential_url(base_url, tenant_id, collection_id),
            json={"biometricCredential": {"externalUserId": f"wrong-coll-{uuid.uuid4().hex[:8]}", "biometrics": {}}},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        cred_id = resp.json()["biometricCredential"]["id"]
        try:
            wrong_coll = str(uuid.uuid4())
            del_resp = requests.delete(
                credential_url(base_url, tenant_id, wrong_coll, cred_id),
                headers=auth_headers,
            )
            assert del_resp.status_code == 404
            assert del_resp.json().get("error") == "NOT_FOUND"
        finally:
            requests.delete(credential_url(base_url, tenant_id, collection_id, cred_id), headers=auth_headers)


class TestDeleteByUserIdValidation:

    def test_empty_user_id_returns_404(self, base_url, auth_headers, tenant_id, collection_id):
        """DELETE ?userId= with empty string returns 404 — spec defines no 400 for this case.
        Empty string is a valid string; server looks for externalUserId='' and finds none."""
        resp = requests.delete(
            credential_url(base_url, tenant_id, collection_id),
            params={"userId": ""},
            headers=auth_headers,
        )
        assert resp.status_code == 404
        assert resp.json().get("error") == "NOT_FOUND"

    def test_missing_user_id_param_does_not_crash(self, base_url, auth_headers, tenant_id, collection_id):
        """DELETE without ?userId= (required param) must not return 500.
        [BUG] Currently crashes with unhandled MissingServletRequestParameterException → 500.
        Spec does not define a 400 for this case but a server crash is never acceptable."""
        resp = requests.delete(
            credential_url(base_url, tenant_id, collection_id),
            headers=auth_headers,
        )
        assert resp.status_code < 500, f"Server crashed with {resp.status_code}: {resp.text}"
