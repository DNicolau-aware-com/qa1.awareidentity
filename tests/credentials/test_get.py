"""
Tests for:
  GET /v3/tenants/{tenantId}/collections/{collectionId}/credentials/{credentialId}
  GET /v3/tenants/{tenantId}/collections/{collectionId}/credentials?externalUserId={userId}
"""

import uuid
import pytest
import requests

from tests.credentials.conftest import credential_url, collection_url, create_collection_payload, create_credential_payload, _DUMMY_IMAGE_B64


class TestGetByIdHappyPath:

    def test_returns_200(self, base_url, auth_headers, tenant_id, collection_id, new_credential):
        """GET by credentialId returns 200 for an existing credential."""
        resp = requests.get(
            credential_url(base_url, tenant_id, collection_id, new_credential["id"]),
            headers=auth_headers,
        )
        assert resp.status_code == 200

    def test_response_wrapped_in_envelope(self, base_url, auth_headers, tenant_id, collection_id, new_credential):
        """Response is wrapped in biometricCredential envelope."""
        resp = requests.get(
            credential_url(base_url, tenant_id, collection_id, new_credential["id"]),
            headers=auth_headers,
        )
        assert "biometricCredential" in resp.json()

    def test_response_contains_required_fields(self, base_url, auth_headers, tenant_id, collection_id, new_credential):
        """Response contains id, collectionId, externalUserId, status, biometrics, createdAt, updatedAt."""
        resp = requests.get(
            credential_url(base_url, tenant_id, collection_id, new_credential["id"]),
            headers=auth_headers,
        )
        c = resp.json()["biometricCredential"]
        for field in ("id", "collectionId", "externalUserId", "status", "biometrics", "createdBy", "createdAt", "updatedAt"):
            assert field in c, f"Missing field: {field}"

    def test_returned_id_matches_requested_id(self, base_url, auth_headers, tenant_id, collection_id, new_credential):
        """Returned id matches the requested credentialId."""
        resp = requests.get(
            credential_url(base_url, tenant_id, collection_id, new_credential["id"]),
            headers=auth_headers,
        )
        assert resp.json()["biometricCredential"]["id"] == new_credential["id"]

    def test_collection_id_matches_path(self, base_url, auth_headers, tenant_id, collection_id, new_credential):
        """collectionId in response matches the URL path."""
        resp = requests.get(
            credential_url(base_url, tenant_id, collection_id, new_credential["id"]),
            headers=auth_headers,
        )
        assert resp.json()["biometricCredential"]["collectionId"] == collection_id

    def test_timestamps_are_integer_milliseconds(self, base_url, auth_headers, tenant_id, collection_id, new_credential):
        """createdAt and updatedAt are positive integers (epoch ms)."""
        resp = requests.get(
            credential_url(base_url, tenant_id, collection_id, new_credential["id"]),
            headers=auth_headers,
        )
        c = resp.json()["biometricCredential"]
        assert isinstance(c["createdAt"], int) and c["createdAt"] > 0
        assert isinstance(c["updatedAt"], int) and c["updatedAt"] > 0

    def test_response_content_type_is_json(self, base_url, auth_headers, tenant_id, collection_id, new_credential):
        """Response Content-Type is application/json."""
        resp = requests.get(
            credential_url(base_url, tenant_id, collection_id, new_credential["id"]),
            headers=auth_headers,
        )
        assert "application/json" in resp.headers.get("Content-Type", "")

    def test_biometrics_is_dict(self, base_url, auth_headers, tenant_id, collection_id, new_credential):
        """biometrics field is a dict (modality → entries map)."""
        resp = requests.get(
            credential_url(base_url, tenant_id, collection_id, new_credential["id"]),
            headers=auth_headers,
        )
        assert isinstance(resp.json()["biometricCredential"]["biometrics"], dict)

    def test_entries_in_get_by_id_do_not_contain_raw_data(self, base_url, auth_headers, tenant_id, collection_id, new_credential):
        """Entry objects in GET-by-ID response do not expose the raw 'data' field (write-only)."""
        resp = requests.get(
            credential_url(base_url, tenant_id, collection_id, new_credential["id"]),
            headers=auth_headers,
        )
        cred = resp.json()["biometricCredential"]
        for entries in cred.get("biometrics", {}).values():
            for entry in entries:
                assert "data" not in entry

    def test_image_data_populated_in_get_by_id_entries(self, base_url, auth_headers, tenant_id, collection_id):
        """Spec: imageData 'Populated only on GET-by-id...' — entry objects must include imageData."""
        user_id = f"img-get-{uuid.uuid4().hex[:8]}"
        payload = {
            "biometricCredential": {
                "externalUserId": user_id,
                "biometrics": {"face": [{"data": _DUMMY_IMAGE_B64, "labels": ["front"]}]},
            }
        }
        create_resp = requests.post(credential_url(base_url, tenant_id, collection_id), json=payload, headers=auth_headers)
        assert create_resp.status_code == 201
        cred_id = create_resp.json()["biometricCredential"]["id"]
        try:
            get_resp = requests.get(credential_url(base_url, tenant_id, collection_id, cred_id), headers=auth_headers)
            assert get_resp.status_code == 200
            entries = [
                e
                for modality_entries in get_resp.json()["biometricCredential"].get("biometrics", {}).values()
                for e in modality_entries
            ]
            assert len(entries) > 0, "Expected at least one entry to verify imageData"
            for entry in entries:
                assert "imageData" in entry, "GET-by-id must include imageData in each entry"
                assert entry["imageData"], "imageData must be non-empty"
        finally:
            requests.delete(credential_url(base_url, tenant_id, collection_id, cred_id), headers=auth_headers)


class TestGetByIdShape:
    """BiometricCredential spec: required fields, status enum, optional fields omitted when null."""

    def test_status_enum_valid_on_get_by_id(self, base_url, auth_headers, tenant_id, collection_id, new_credential):
        """status on GET-by-id response is ACTIVE or INACTIVE."""
        resp = requests.get(
            credential_url(base_url, tenant_id, collection_id, new_credential["id"]),
            headers=auth_headers,
        )
        status = resp.json()["biometricCredential"]["status"]
        assert status in ("ACTIVE", "INACTIVE"), f"Invalid status: {status!r}"

    def test_updated_by_omitted_when_null_on_get_by_id(self, base_url, auth_headers, tenant_id, collection_id, new_credential):
        """Spec: updatedBy 'Omitted when null' — key must be absent on a credential never PATCHed."""
        resp = requests.get(
            credential_url(base_url, tenant_id, collection_id, new_credential["id"]),
            headers=auth_headers,
        )
        cred = resp.json()["biometricCredential"]
        assert "updatedBy" not in cred, \
            f"updatedBy must be absent when null, got {cred.get('updatedBy')!r}"

    def test_correlation_id_omitted_when_null_on_get_by_id(self, base_url, auth_headers, tenant_id, collection_id, new_credential):
        """Spec: correlationId 'Omitted when null' — key must be absent when not set."""
        resp = requests.get(
            credential_url(base_url, tenant_id, collection_id, new_credential["id"]),
            headers=auth_headers,
        )
        cred = resp.json()["biometricCredential"]
        assert "correlationId" not in cred, \
            f"correlationId must be absent when null, got {cred.get('correlationId')!r}"


class TestGetByIdDataIntegrity:

    def test_external_user_id_matches_create_payload(self, base_url, auth_headers, tenant_id, collection_id, new_credential):
        """GET returns the externalUserId that was supplied on creation."""
        resp = requests.get(
            credential_url(base_url, tenant_id, collection_id, new_credential["id"]),
            headers=auth_headers,
        )
        c = resp.json()["biometricCredential"]
        assert c["externalUserId"] == new_credential["externalUserId"]

    def test_created_by_matches_create_payload(self, base_url, auth_headers, tenant_id, collection_id):
        """GET returns the createdBy that was supplied on creation."""
        payload = create_credential_payload(createdBy="verifier@aware.com")
        resp = requests.post(credential_url(base_url, tenant_id, collection_id), json=payload, headers=auth_headers)
        assert resp.status_code == 201
        cred = resp.json()["biometricCredential"]
        try:
            get_resp = requests.get(
                credential_url(base_url, tenant_id, collection_id, cred["id"]),
                headers=auth_headers,
            )
            assert get_resp.json()["biometricCredential"]["createdBy"] == "verifier@aware.com"
        finally:
            requests.delete(credential_url(base_url, tenant_id, collection_id, cred["id"]), headers=auth_headers)


class TestGetByIdNotFound:

    def test_nonexistent_id_returns_404(self, base_url, auth_headers, tenant_id, collection_id):
        """GET with a random UUID returns 404 NOT_FOUND.
        """
        resp = requests.get(
            credential_url(base_url, tenant_id, collection_id, str(uuid.uuid4())),
            headers=auth_headers,
        )
        assert resp.status_code == 404
        assert resp.json().get("error") == "NOT_FOUND"

    def test_nonexistent_collection_returns_404(self, base_url, auth_headers, tenant_id):
        """GET into a non-existent collection returns 404."""
        resp = requests.get(
            credential_url(base_url, tenant_id, str(uuid.uuid4()), str(uuid.uuid4())),
            headers=auth_headers,
        )
        assert resp.status_code == 404

    def test_credential_in_wrong_collection_returns_404(self, base_url, auth_headers, tenant_id, collection_id):
        """Spec: credential 'belongs to a different collection' → 404.
        A valid credentialId accessed via a different real collectionId must be rejected."""
        cred_resp = requests.post(
            credential_url(base_url, tenant_id, collection_id),
            json=create_credential_payload(),
            headers=auth_headers,
        )
        assert cred_resp.status_code == 201
        cred_id = cred_resp.json()["biometricCredential"]["id"]

        other_coll_resp = requests.post(
            collection_url(base_url, tenant_id),
            json=create_collection_payload(),
            headers=auth_headers,
        )
        assert other_coll_resp.status_code == 201
        other_coll_id = other_coll_resp.json()["biometricCollection"]["id"]

        try:
            resp = requests.get(
                credential_url(base_url, tenant_id, other_coll_id, cred_id),
                headers=auth_headers,
            )
            assert resp.status_code == 404
        finally:
            requests.delete(credential_url(base_url, tenant_id, collection_id, cred_id), headers=auth_headers)
            requests.delete(collection_url(base_url, tenant_id, other_coll_id), headers=auth_headers)

    def test_non_uuid_id_returns_400(self, base_url, auth_headers, tenant_id, collection_id):
        """GET with a non-UUID credentialId returns 400 VALIDATION_FAILED."""
        resp = requests.get(
            credential_url(base_url, tenant_id, collection_id, "not-a-uuid"),
            headers=auth_headers,
        )
        assert resp.status_code == 400
        assert resp.json().get("error") == "VALIDATION_FAILED"

    def test_deleted_credential_returns_404(self, base_url, auth_headers, tenant_id, collection_id):
        """GET a deleted credential returns 404 NOT_FOUND.
        """
        create_resp = requests.post(
            credential_url(base_url, tenant_id, collection_id),
            json=create_credential_payload(),
            headers=auth_headers,
        )
        assert create_resp.status_code == 201
        cid = create_resp.json()["biometricCredential"]["id"]
        requests.delete(credential_url(base_url, tenant_id, collection_id, cid), headers=auth_headers)

        resp = requests.get(credential_url(base_url, tenant_id, collection_id, cid), headers=auth_headers)
        assert resp.status_code == 404
        assert resp.json().get("error") == "NOT_FOUND"


class TestGetByUserId:
    # Per spec, the query param is `userId` (matched against the body's `externalUserId` field).
    # When `userId` is present the response is a page envelope with at most one credential,
    # imageData populated, and all other filters ignored.

    def test_returns_200_for_existing_user(self, base_url, auth_headers, tenant_id, collection_id, new_credential):
        """GET ?userId= returns 200 for a known externalUserId."""
        resp = requests.get(
            credential_url(base_url, tenant_id, collection_id),
            params={"userId": new_credential["externalUserId"]},
            headers=auth_headers,
        )
        assert resp.status_code == 200

    def test_response_contains_page_envelope_fields(self, base_url, auth_headers, tenant_id, collection_id, new_credential):
        """GET ?userId= response contains pagination envelope fields."""
        resp = requests.get(
            credential_url(base_url, tenant_id, collection_id),
            params={"userId": new_credential["externalUserId"]},
            headers=auth_headers,
        )
        body = resp.json()
        for field in ("biometricCredentials", "page", "size", "totalElements"):
            assert field in body, f"Missing field: {field}"

    def test_response_contains_matching_credential(self, base_url, auth_headers, tenant_id, collection_id, new_credential):
        """GET ?userId= result contains the credential created for that user."""
        resp = requests.get(
            credential_url(base_url, tenant_id, collection_id),
            params={"userId": new_credential["externalUserId"]},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        ids = [c["id"] for c in resp.json().get("biometricCredentials", [])]
        assert new_credential["id"] in ids

    def test_unknown_user_id_returns_404(self, base_url, auth_headers, tenant_id, collection_id):
        """GET ?userId= for an unknown userId returns 404 NOT_FOUND (not empty 200)."""
        resp = requests.get(
            credential_url(base_url, tenant_id, collection_id),
            params={"userId": f"ghost-{uuid.uuid4().hex}"},
            headers=auth_headers,
        )
        assert resp.status_code == 404
        assert resp.json().get("error") == "NOT_FOUND"

    def test_credentials_filtered_by_user_id(self, base_url, auth_headers, tenant_id, collection_id):
        """GET ?userId= returns only the credential for the specified user, not others."""
        user_a = f"user-a-{uuid.uuid4().hex[:8]}"
        user_b = f"user-b-{uuid.uuid4().hex[:8]}"

        resp_a = requests.post(
            credential_url(base_url, tenant_id, collection_id),
            json=create_credential_payload(user_a),
            headers=auth_headers,
        )
        resp_b = requests.post(
            credential_url(base_url, tenant_id, collection_id),
            json=create_credential_payload(user_b),
            headers=auth_headers,
        )
        assert resp_a.status_code == 201
        assert resp_b.status_code == 201
        id_a = resp_a.json()["biometricCredential"]["id"]
        id_b = resp_b.json()["biometricCredential"]["id"]

        try:
            resp = requests.get(
                credential_url(base_url, tenant_id, collection_id),
                params={"userId": user_a},
                headers=auth_headers,
            )
            assert resp.status_code == 200
            ids = [c["id"] for c in resp.json().get("biometricCredentials", [])]
            assert id_a in ids
            assert id_b not in ids
        finally:
            requests.delete(credential_url(base_url, tenant_id, collection_id, id_a), headers=auth_headers)
            requests.delete(credential_url(base_url, tenant_id, collection_id, id_b), headers=auth_headers)

    def test_image_data_populated_in_entries(self, base_url, auth_headers, tenant_id, collection_id):
        """GET ?userId= must include imageData in entry objects — spec: same as GET by ID.
        Requires a credential with at least one biometric entry to verify the field is present."""
        user_id = f"img-user-{uuid.uuid4().hex[:8]}"
        payload = {
            "biometricCredential": {
                "externalUserId": user_id,
                "biometrics": {
                    "face": [{"labels": ["front"], "data": _DUMMY_IMAGE_B64}]
                },
            }
        }
        create_resp = requests.post(
            credential_url(base_url, tenant_id, collection_id),
            json=payload,
            headers=auth_headers,
        )
        assert create_resp.status_code == 201
        cred_id = create_resp.json()["biometricCredential"]["id"]
        try:
            resp = requests.get(
                credential_url(base_url, tenant_id, collection_id),
                params={"userId": user_id},
                headers=auth_headers,
            )
            assert resp.status_code == 200
            creds = resp.json().get("biometricCredentials", [])
            assert len(creds) == 1
            entries = [e for modality_entries in creds[0].get("biometrics", {}).values() for e in modality_entries]
            assert len(entries) > 0, "Expected at least one entry to verify imageData"
            for entry in entries:
                assert "imageData" in entry, "GET ?userId= must include imageData in each entry"
                assert entry["imageData"], "imageData must be non-empty"
        finally:
            requests.delete(credential_url(base_url, tenant_id, collection_id, cred_id), headers=auth_headers)

    def test_deleted_credential_returns_404_by_user_id(self, base_url, auth_headers, tenant_id, collection_id):
        """GET ?userId= for a soft-deleted credential returns 404, same as GET by ID after delete."""
        create_resp = requests.post(
            credential_url(base_url, tenant_id, collection_id),
            json=create_credential_payload(),
            headers=auth_headers,
        )
        assert create_resp.status_code == 201
        cred = create_resp.json()["biometricCredential"]
        requests.delete(credential_url(base_url, tenant_id, collection_id, cred["id"]), headers=auth_headers)

        resp = requests.get(
            credential_url(base_url, tenant_id, collection_id),
            params={"userId": cred["externalUserId"]},
            headers=auth_headers,
        )
        assert resp.status_code == 404
