"""
Tests for:
  PATCH /v3/tenants/{tenantId}/collections/{collectionId}/credentials/{credentialId}
  PATCH /v3/tenants/{tenantId}/collections/{collectionId}/credentials?externalUserId={userId}

PATCH ?externalUserId= is an upsert:
  - 201 when no credential exists for that externalUserId (creates)
  - 200 when a credential already exists (updates)
"""

import uuid
import pytest
import requests

from tests.credentials.conftest import credential_url, create_credential_payload, _DUMMY_IMAGE_B64


class TestUpdateByIdHappyPath:

    def test_returns_200(self, base_url, auth_headers, tenant_id, collection_id, new_credential):
        """PATCH by credentialId returns 200."""
        payload = {"biometricCredential": {"updatedBy": "test@aware.com"}}
        resp = requests.patch(
            credential_url(base_url, tenant_id, collection_id, new_credential["id"]),
            json=payload,
            headers=auth_headers,
        )
        assert resp.status_code == 200

    def test_response_wrapped_in_envelope(self, base_url, auth_headers, tenant_id, collection_id, new_credential):
        """PATCH response is wrapped in biometricCredential envelope."""
        payload = {"biometricCredential": {"updatedBy": "test@aware.com"}}
        resp = requests.patch(
            credential_url(base_url, tenant_id, collection_id, new_credential["id"]),
            json=payload,
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert "biometricCredential" in resp.json()

    def test_updated_by_is_set(self, base_url, auth_headers, tenant_id, collection_id, new_credential):
        """PATCH response includes updatedBy when supplied."""
        payload = {"biometricCredential": {"updatedBy": "patcher@aware.com"}}
        resp = requests.patch(
            credential_url(base_url, tenant_id, collection_id, new_credential["id"]),
            json=payload,
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["biometricCredential"]["updatedBy"] == "patcher@aware.com"

    def test_updated_at_advances(self, base_url, auth_headers, tenant_id, collection_id, new_credential):
        """updatedAt is >= createdAt after a PATCH."""
        payload = {"biometricCredential": {"updatedBy": "test@aware.com"}}
        resp = requests.patch(
            credential_url(base_url, tenant_id, collection_id, new_credential["id"]),
            json=payload,
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["biometricCredential"]["updatedAt"] >= new_credential["createdAt"]

    def test_created_by_unchanged_after_patch(self, base_url, auth_headers, tenant_id, collection_id, new_credential):
        """createdBy is not modified by a PATCH."""
        original_created_by = new_credential.get("createdBy")
        requests.patch(
            credential_url(base_url, tenant_id, collection_id, new_credential["id"]),
            json={"biometricCredential": {"updatedBy": "someone@aware.com"}},
            headers=auth_headers,
        )
        resp = requests.get(
            credential_url(base_url, tenant_id, collection_id, new_credential["id"]),
            headers=auth_headers,
        )
        assert resp.json()["biometricCredential"].get("createdBy") == original_created_by

    def test_created_at_unchanged_after_patch(self, base_url, auth_headers, tenant_id, collection_id, new_credential):
        """createdAt is not modified by a PATCH."""
        payload = {"biometricCredential": {"updatedBy": "test@aware.com"}}
        resp = requests.patch(
            credential_url(base_url, tenant_id, collection_id, new_credential["id"]),
            json=payload,
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["biometricCredential"]["createdAt"] == new_credential["createdAt"]

    def test_patch_persists_via_get(self, base_url, auth_headers, tenant_id, collection_id, new_credential):
        """Changes made via PATCH are reflected in a subsequent GET."""
        requests.patch(
            credential_url(base_url, tenant_id, collection_id, new_credential["id"]),
            json={"biometricCredential": {"updatedBy": "persisted@aware.com"}},
            headers=auth_headers,
        )
        resp = requests.get(
            credential_url(base_url, tenant_id, collection_id, new_credential["id"]),
            headers=auth_headers,
        )
        assert resp.json()["biometricCredential"]["updatedBy"] == "persisted@aware.com"

    def test_data_not_echoed_in_patch_response(self, base_url, auth_headers, tenant_id, collection_id, new_credential):
        """data field is write-only: entries in PATCH response must not contain 'data'."""
        payload = {"biometricCredential": {"updatedBy": "test@aware.com"}}
        resp = requests.patch(
            credential_url(base_url, tenant_id, collection_id, new_credential["id"]),
            json=payload,
            headers=auth_headers,
        )
        assert resp.status_code == 200
        cred = resp.json()["biometricCredential"]
        for entries in cred.get("biometrics", {}).values():
            for entry in entries:
                assert "data" not in entry

    def test_image_data_not_in_patch_response(self, base_url, auth_headers, tenant_id, collection_id, new_credential):
        """PATCH-credential response carries no imageData (spec: 'Returns full updated credential (no imageData)')."""
        payload = {"biometricCredential": {"updatedBy": "test@aware.com"}}
        resp = requests.patch(
            credential_url(base_url, tenant_id, collection_id, new_credential["id"]),
            json=payload,
            headers=auth_headers,
        )
        assert resp.status_code == 200
        cred = resp.json()["biometricCredential"]
        for entries in cred.get("biometrics", {}).values():
            for entry in entries:
                assert "imageData" not in entry

    def test_correlation_id_updated(self, base_url, auth_headers, tenant_id, collection_id, new_credential):
        """correlationId supplied on PATCH replaces the stored value and is echoed back."""
        corr = f"corr-{uuid.uuid4().hex[:8]}"
        resp = requests.patch(
            credential_url(base_url, tenant_id, collection_id, new_credential["id"]),
            json={"biometricCredential": {"correlationId": corr, "updatedBy": "test@aware.com"}},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["biometricCredential"].get("correlationId") == corr

    def test_updated_by_absent_on_new_credential(self, new_credential):
        """Spec: updatedBy 'Omitted when null' — key must be absent on a credential that has never been PATCHed."""
        assert "updatedBy" not in new_credential, \
            f"updatedBy must be absent when null, got {new_credential.get('updatedBy')!r}"


class TestUpdateByIdImmutableFields:
    """PATCH must silently ignore client-supplied server-owned fields."""

    _FAKE_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    _FAKE_TS = 1000000000000

    def test_id_cannot_be_changed_via_patch(self, base_url, auth_headers, tenant_id, collection_id, new_credential):
        """Client-supplied id in PATCH body is ignored."""
        requests.patch(
            credential_url(base_url, tenant_id, collection_id, new_credential["id"]),
            json={"biometricCredential": {"id": self._FAKE_ID, "updatedBy": "test@aware.com"}},
            headers=auth_headers,
        )
        got = requests.get(
            credential_url(base_url, tenant_id, collection_id, new_credential["id"]),
            headers=auth_headers,
        )
        assert got.status_code == 200
        assert got.json()["biometricCredential"]["id"] == new_credential["id"]

    def test_created_by_cannot_be_changed_via_patch(self, base_url, auth_headers, tenant_id, collection_id, new_credential):
        """Client-supplied createdBy in PATCH body is ignored."""
        original = new_credential.get("createdBy")
        requests.patch(
            credential_url(base_url, tenant_id, collection_id, new_credential["id"]),
            json={"biometricCredential": {"createdBy": "injected@evil.com", "updatedBy": "test@aware.com"}},
            headers=auth_headers,
        )
        got = requests.get(
            credential_url(base_url, tenant_id, collection_id, new_credential["id"]),
            headers=auth_headers,
        )
        assert got.json()["biometricCredential"].get("createdBy") == original

    def test_created_at_cannot_be_changed_via_patch(self, base_url, auth_headers, tenant_id, collection_id, new_credential):
        """Client-supplied createdAt in PATCH body is ignored."""
        original_created_at = new_credential["createdAt"]
        requests.patch(
            credential_url(base_url, tenant_id, collection_id, new_credential["id"]),
            json={"biometricCredential": {"createdAt": self._FAKE_TS, "updatedBy": "test@aware.com"}},
            headers=auth_headers,
        )
        got = requests.get(
            credential_url(base_url, tenant_id, collection_id, new_credential["id"]),
            headers=auth_headers,
        )
        assert got.json()["biometricCredential"]["createdAt"] == original_created_at

    def test_status_cannot_be_changed_via_patch(self, base_url, auth_headers, tenant_id, collection_id, new_credential):
        """Client-supplied status in PATCH body is ignored — status is server-managed."""
        requests.patch(
            credential_url(base_url, tenant_id, collection_id, new_credential["id"]),
            json={"biometricCredential": {"status": "INACTIVE", "updatedBy": "test@aware.com"}},
            headers=auth_headers,
        )
        got = requests.get(
            credential_url(base_url, tenant_id, collection_id, new_credential["id"]),
            headers=auth_headers,
        )
        assert got.json()["biometricCredential"]["status"] == "ACTIVE"

    def test_external_user_id_cannot_be_changed_via_patch(self, base_url, auth_headers, tenant_id, collection_id, new_credential):
        """Client-supplied externalUserId in PATCH body is ignored — it is immutable after creation."""
        original = new_credential["externalUserId"]
        requests.patch(
            credential_url(base_url, tenant_id, collection_id, new_credential["id"]),
            json={"biometricCredential": {"externalUserId": "injected-user", "updatedBy": "test@aware.com"}},
            headers=auth_headers,
        )
        got = requests.get(
            credential_url(base_url, tenant_id, collection_id, new_credential["id"]),
            headers=auth_headers,
        )
        assert got.json()["biometricCredential"]["externalUserId"] == original


class TestUpdateByIdNotFound:

    def test_nonexistent_id_returns_404(self, base_url, auth_headers, tenant_id, collection_id):
        """PATCH with a random UUID returns 404 NOT_FOUND.
        """
        payload = {"biometricCredential": {"updatedBy": "test@aware.com"}}
        resp = requests.patch(
            credential_url(base_url, tenant_id, collection_id, str(uuid.uuid4())),
            json=payload,
            headers=auth_headers,
        )
        assert resp.status_code == 404
        assert resp.json().get("error") == "NOT_FOUND"

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


class TestUpdateByIdValidation:

    def test_missing_envelope_returns_400(self, base_url, auth_headers, tenant_id, collection_id, new_credential):
        """PATCH without biometricCredential wrapper returns 400."""
        resp = requests.patch(
            credential_url(base_url, tenant_id, collection_id, new_credential["id"]),
            json={"updatedBy": "x"},
            headers=auth_headers,
        )
        assert resp.status_code == 400

    def test_non_uuid_id_returns_400(self, base_url, auth_headers, tenant_id, collection_id):
        """PATCH with a non-UUID credentialId returns 400 VALIDATION_FAILED."""
        resp = requests.patch(
            credential_url(base_url, tenant_id, collection_id, "not-a-uuid"),
            json={"biometricCredential": {"updatedBy": "test@aware.com"}},
            headers=auth_headers,
        )
        assert resp.status_code == 400
        assert resp.json().get("error") == "VALIDATION_FAILED"

    def test_empty_biometrics_map_returns_400(self, base_url, auth_headers, tenant_id, collection_id, new_credential):
        """PATCH with biometrics:{} must return 400 — an empty map has nothing to append."""
        resp = requests.patch(
            credential_url(base_url, tenant_id, collection_id, new_credential["id"]),
            json={"biometricCredential": {"biometrics": {}}},
            headers=auth_headers,
        )
        assert resp.status_code == 400

    def test_invalid_base64_in_entry_data_returns_400(self, base_url, auth_headers, tenant_id, collection_id, new_credential):
        """PATCH with invalid Base64 in an entry's data field must return 400 VALIDATION_FAILED.
        Spec: 'invalid Base64' → errorCode VALIDATION_FAILED."""
        resp = requests.patch(
            credential_url(base_url, tenant_id, collection_id, new_credential["id"]),
            json={"biometricCredential": {"biometrics": {"face": [{"data": "!!!not-valid-base64!!!"}]}}},
            headers=auth_headers,
        )
        assert resp.status_code == 400
        assert resp.json().get("error") == "VALIDATION_FAILED"

    def test_modality_entry_limit_exceeded_returns_400(self, base_url, auth_headers, tenant_id, collection_id, new_credential):
        """Adding entries that would push a modality past 5 returns 400 MODALITY_ENTRY_LIMIT_EXCEEDED.
        Spec: 'per-modality entry limit of 5 is enforced against the total existing + incoming count'."""
        dummy = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        six_entries = [{"data": dummy} for _ in range(6)]
        resp = requests.patch(
            credential_url(base_url, tenant_id, collection_id, new_credential["id"]),
            json={"biometricCredential": {"biometrics": {"face": six_entries}}},
            headers=auth_headers,
        )
        assert resp.status_code == 400
        assert resp.json().get("error") == "MODALITY_ENTRY_LIMIT_EXCEEDED"

    def test_modality_entry_limit_enforced_cumulatively_on_patch_by_id(
        self, base_url, auth_headers, tenant_id, collection_id
    ):
        """Spec: limit is enforced against existing + incoming count, not just incoming.
        A credential with 3 face entries already stored must reject a PATCH adding 3 more (3+3=6 > 5)
        and accept a PATCH adding 2 (3+2=5 == limit)."""
        from tests.credentials.conftest import _DUMMY_IMAGE_B64
        three_entries = [{"labels": [f"s{i}"], "data": _DUMMY_IMAGE_B64} for i in range(3)]
        create_resp = requests.post(
            credential_url(base_url, tenant_id, collection_id),
            json={
                "biometricCredential": {
                    "externalUserId": f"climit-{uuid.uuid4().hex[:8]}",
                    "biometrics": {"face": three_entries},
                }
            },
            headers=auth_headers,
        )
        assert create_resp.status_code == 201
        cred_id = create_resp.json()["biometricCredential"]["id"]
        try:
            # 3 existing + 3 incoming = 6 → must be rejected
            over_limit = requests.patch(
                credential_url(base_url, tenant_id, collection_id, cred_id),
                json={"biometricCredential": {"biometrics": {"face": three_entries}}},
                headers=auth_headers,
            )
            assert over_limit.status_code == 400
            assert over_limit.json().get("error") == "MODALITY_ENTRY_LIMIT_EXCEEDED"

            # 3 existing + 2 incoming = 5 → must be accepted
            two_entries = [{"labels": [f"s{i}"], "data": _DUMMY_IMAGE_B64} for i in range(2)]
            at_limit = requests.patch(
                credential_url(base_url, tenant_id, collection_id, cred_id),
                json={"biometricCredential": {"biometrics": {"face": two_entries}}},
                headers=auth_headers,
            )
            assert at_limit.status_code == 200
        finally:
            requests.delete(credential_url(base_url, tenant_id, collection_id, cred_id), headers=auth_headers)

    def test_empty_modality_array_returns_400(self, base_url, auth_headers, tenant_id, collection_id, new_credential):
        """PATCH with a modality key mapped to an empty array must return 400 (spec: minItems 1 per modality).
        [BUG] Server may accept this silently — MUST FAIL until validation is enforced."""
        resp = requests.patch(
            credential_url(base_url, tenant_id, collection_id, new_credential["id"]),
            json={"biometricCredential": {"biometrics": {"face": []}}},
            headers=auth_headers,
        )
        assert resp.status_code == 400

    def test_missing_data_in_biometrics_entry_returns_400(self, base_url, auth_headers, tenant_id, collection_id, new_credential):
        """Spec: BiometricCredentialEntryRequest.data is required ('*'). PATCH entry without data must return 400."""
        resp = requests.patch(
            credential_url(base_url, tenant_id, collection_id, new_credential["id"]),
            json={"biometricCredential": {"biometrics": {"face": [{"labels": ["front"]}]}}},
            headers=auth_headers,
        )
        assert resp.status_code == 400
        assert resp.json().get("error") == "VALIDATION_FAILED"

    def test_credential_in_wrong_collection_returns_404(self, base_url, auth_headers, tenant_id, collection_id):
        """PATCH a valid credentialId via a different collectionId returns 404."""
        resp = requests.post(
            credential_url(base_url, tenant_id, collection_id),
            json=create_credential_payload(f"wrong-coll-{uuid.uuid4().hex[:8]}"),
            headers=auth_headers,
        )
        assert resp.status_code == 201
        cred_id = resp.json()["biometricCredential"]["id"]
        try:
            wrong_coll = str(uuid.uuid4())
            patch_resp = requests.patch(
                credential_url(base_url, tenant_id, wrong_coll, cred_id),
                json={"biometricCredential": {"updatedBy": "test@aware.com"}},
                headers=auth_headers,
            )
            assert patch_resp.status_code == 404
        finally:
            requests.delete(credential_url(base_url, tenant_id, collection_id, cred_id), headers=auth_headers)


class TestUpdateByIdUpdatedByValidation:
    """updatedBy must be a plain name or email (PATTERN_NAME_OR_EMAIL) if supplied."""

    def test_plain_name_accepted(self, base_url, auth_headers, tenant_id, collection_id, new_credential):
        """A plain name in updatedBy is accepted."""
        resp = requests.patch(
            credential_url(base_url, tenant_id, collection_id, new_credential["id"]),
            json={"biometricCredential": {"updatedBy": "Jane Doe"}},
            headers=auth_headers,
        )
        assert resp.status_code == 200

    def test_xss_in_updated_by_returns_400(self, base_url, auth_headers, tenant_id, collection_id, new_credential):
        """An XSS payload in updatedBy is rejected with 400."""
        resp = requests.patch(
            credential_url(base_url, tenant_id, collection_id, new_credential["id"]),
            json={"biometricCredential": {"updatedBy": "<script>alert(1)</script>"}},
            headers=auth_headers,
        )
        assert resp.status_code == 400

    def test_symbols_in_updated_by_returns_400(self, base_url, auth_headers, tenant_id, collection_id, new_credential):
        """Disallowed symbols in updatedBy are rejected with 400."""
        resp = requests.patch(
            credential_url(base_url, tenant_id, collection_id, new_credential["id"]),
            json={"biometricCredential": {"updatedBy": "robert');DROP TABLE--"}},
            headers=auth_headers,
        )
        assert resp.status_code == 400

    # ------------------------------------------------------------------
    # Blank / control-character updatedBy → 400
    # [BUG TICKET 4] Values below currently return 200 — MUST FAIL until fixed.
    # ------------------------------------------------------------------

    def test_blank_updated_by_returns_400(self, base_url, auth_headers, tenant_id, collection_id, new_credential):
        """[BUG TICKET 4] Empty string updatedBy must fail PATTERN_NAME_OR_EMAIL validation."""
        resp = requests.patch(
            credential_url(base_url, tenant_id, collection_id, new_credential["id"]),
            json={"biometricCredential": {"updatedBy": ""}},
            headers=auth_headers,
        )
        assert resp.status_code == 400

    def test_whitespace_updated_by_returns_400(self, base_url, auth_headers, tenant_id, collection_id, new_credential):
        """[BUG TICKET 4] Whitespace-only updatedBy must fail PATTERN_NAME_OR_EMAIL validation."""
        resp = requests.patch(
            credential_url(base_url, tenant_id, collection_id, new_credential["id"]),
            json={"biometricCredential": {"updatedBy": "   "}},
            headers=auth_headers,
        )
        assert resp.status_code == 400

    def test_newline_in_updated_by_returns_400(self, base_url, auth_headers, tenant_id, collection_id, new_credential):
        """[BUG TICKET 4] Newline in updatedBy must fail PATTERN_NAME_OR_EMAIL validation."""
        resp = requests.patch(
            credential_url(base_url, tenant_id, collection_id, new_credential["id"]),
            json={"biometricCredential": {"updatedBy": "user\nname"}},
            headers=auth_headers,
        )
        assert resp.status_code == 400


class TestUpdateByIdLabelValidation:
    """Labels within biometrics entries on credential PATCH must pass content validation."""

    def test_xss_in_label_returns_400(self, base_url, auth_headers, tenant_id, collection_id, new_credential):
        """XSS payload as a label value on credential PATCH is rejected with 400."""
        resp = requests.patch(
            credential_url(base_url, tenant_id, collection_id, new_credential["id"]),
            json={"biometricCredential": {"biometrics": {"face": [{"data": _DUMMY_IMAGE_B64, "labels": ["<script>alert(1)</script>"]}]}}},
            headers=auth_headers,
        )
        assert resp.status_code == 400

    def test_sql_injection_in_label_returns_400(self, base_url, auth_headers, tenant_id, collection_id, new_credential):
        """SQL injection payload as a label value on credential PATCH is rejected with 400."""
        resp = requests.patch(
            credential_url(base_url, tenant_id, collection_id, new_credential["id"]),
            json={"biometricCredential": {"biometrics": {"face": [{"data": _DUMMY_IMAGE_B64, "labels": ["' OR 1=1 --"]}]}}},
            headers=auth_headers,
        )
        assert resp.status_code == 400

    def test_empty_string_label_returns_400(self, base_url, auth_headers, tenant_id, collection_id, new_credential):
        """Empty string in the labels array on credential PATCH is rejected with 400."""
        resp = requests.patch(
            credential_url(base_url, tenant_id, collection_id, new_credential["id"]),
            json={"biometricCredential": {"biometrics": {"face": [{"data": _DUMMY_IMAGE_B64, "labels": [""]}]}}},
            headers=auth_headers,
        )
        assert resp.status_code == 400


class TestUpdateByIdCorrelationIdValidation:

    def test_xss_in_correlation_id_returns_400(self, base_url, auth_headers, tenant_id, collection_id, new_credential):
        """XSS payload in correlationId on PATCH is rejected with 400."""
        resp = requests.patch(
            credential_url(base_url, tenant_id, collection_id, new_credential["id"]),
            json={"biometricCredential": {"correlationId": "<script>alert(1)</script>"}},
            headers=auth_headers,
        )
        assert resp.status_code == 400


class TestUpdateByIdShape:
    """PATCH-by-id response must satisfy the full BiometricCredentialEnvelope spec."""

    def test_required_fields_present_in_patch_response(self, base_url, auth_headers, tenant_id, collection_id, new_credential):
        """PATCH response contains all spec-required BiometricCredential fields."""
        resp = requests.patch(
            credential_url(base_url, tenant_id, collection_id, new_credential["id"]),
            json={"biometricCredential": {"updatedBy": "shape-check@aware.com"}},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        cred = resp.json()["biometricCredential"]
        for field in ("id", "collectionId", "externalUserId", "status", "biometrics", "createdBy", "createdAt", "updatedAt"):
            assert field in cred, f"Missing required field '{field}' in PATCH response"

    def test_status_enum_valid_in_patch_response(self, base_url, auth_headers, tenant_id, collection_id, new_credential):
        """status in PATCH response is ACTIVE or INACTIVE."""
        resp = requests.patch(
            credential_url(base_url, tenant_id, collection_id, new_credential["id"]),
            json={"biometricCredential": {"updatedBy": "shape-check@aware.com"}},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        status = resp.json()["biometricCredential"]["status"]
        assert status in ("ACTIVE", "INACTIVE"), f"Invalid status: {status!r}"

    def test_updated_by_omitted_when_null_in_patch_response(self, base_url, auth_headers, tenant_id, collection_id):
        """Spec: updatedBy 'Omitted when null' — PATCH without updatedBy on a never-patched credential
        must not introduce a null updatedBy key in the response."""
        resp_create = requests.post(
            credential_url(base_url, tenant_id, collection_id),
            json=create_credential_payload(),
            headers=auth_headers,
        )
        assert resp_create.status_code == 201
        cred_id = resp_create.json()["biometricCredential"]["id"]
        try:
            from tests.credentials.conftest import _DUMMY_IMAGE_B64
            resp = requests.patch(
                credential_url(base_url, tenant_id, collection_id, cred_id),
                json={"biometricCredential": {"biometrics": {"face": [{"data": _DUMMY_IMAGE_B64}]}}},
                headers=auth_headers,
            )
            assert resp.status_code == 200
            cred = resp.json()["biometricCredential"]
            assert "updatedBy" not in cred, \
                f"updatedBy must be absent when null, got {cred.get('updatedBy')!r}"
        finally:
            requests.delete(credential_url(base_url, tenant_id, collection_id, cred_id), headers=auth_headers)

    def test_correlation_id_omitted_when_null_in_patch_response(self, base_url, auth_headers, tenant_id, collection_id, new_credential):
        """Spec: correlationId 'Omitted when null' — PATCH response must not include the key when never set."""
        resp = requests.patch(
            credential_url(base_url, tenant_id, collection_id, new_credential["id"]),
            json={"biometricCredential": {"updatedBy": "shape-check@aware.com"}},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        cred = resp.json()["biometricCredential"]
        assert "correlationId" not in cred, \
            f"correlationId must be absent when null, got {cred.get('correlationId')!r}"


class TestUpdateByUserIdUpsert:
    # Per spec, PATCH ?userId= is an upsert: 201 when no credential exists for that userId
    # (creates), 200 when one already exists (appends entries). `externalUserId` is taken
    # from the `userId` query param, not the body.

    def test_existing_user_returns_200(self, base_url, auth_headers, tenant_id, collection_id, new_credential):
        """PATCH ?userId= returns 200 when a credential already exists for that user."""
        payload = {"biometricCredential": {"updatedBy": "test@aware.com"}}
        resp = requests.patch(
            credential_url(base_url, tenant_id, collection_id),
            params={"userId": new_credential["externalUserId"]},
            json=payload,
            headers=auth_headers,
        )
        assert resp.status_code == 200

    def test_new_user_creates_credential_returns_201(self, base_url, auth_headers, tenant_id, collection_id):
        """PATCH ?userId= returns 201 (upsert creates) for a userId with no existing credential.
        [BUG] Currently returns 200 for both create and update — MUST FAIL until fixed.
        Spec: 201 on first call (creates), 200 on subsequent calls (updates)."""
        new_user = f"upsert-{uuid.uuid4().hex[:8]}"
        payload = {"biometricCredential": {"updatedBy": "test@aware.com"}}
        resp = requests.patch(
            credential_url(base_url, tenant_id, collection_id),
            params={"userId": new_user},
            json=payload,
            headers=auth_headers,
        )
        assert resp.status_code == 201
        cid = resp.json()["biometricCredential"]["id"]
        requests.delete(credential_url(base_url, tenant_id, collection_id, cid), headers=auth_headers)

    def test_update_persists_via_get_by_user_id(self, base_url, auth_headers, tenant_id, collection_id, new_credential):
        """Changes via PATCH ?userId= are reflected in a subsequent GET ?userId=."""
        requests.patch(
            credential_url(base_url, tenant_id, collection_id),
            params={"userId": new_credential["externalUserId"]},
            json={"biometricCredential": {"updatedBy": "persisted@aware.com"}},
            headers=auth_headers,
        )
        resp = requests.get(
            credential_url(base_url, tenant_id, collection_id),
            params={"userId": new_credential["externalUserId"]},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        credentials = resp.json().get("biometricCredentials", [])
        assert any(c.get("updatedBy") == "persisted@aware.com" for c in credentials)


class TestUpdateByUserIdValidation:

    def test_empty_user_id_returns_400(self, base_url, auth_headers, tenant_id, collection_id):
        """PATCH ?userId= with an empty string must return 400 VALIDATION_FAILED.
        [BUG] Currently returns 200 and creates a credential with externalUserId: '' — MUST FAIL until fixed.
        The blank-userId credential poisons the unique slot permanently even after soft-delete."""
        resp = requests.patch(
            credential_url(base_url, tenant_id, collection_id),
            params={"userId": ""},
            json={"biometricCredential": {"updatedBy": "test@aware.com"}},
            headers=auth_headers,
        )
        if resp.status_code == 200:
            cid = resp.json()["biometricCredential"]["id"]
            requests.delete(credential_url(base_url, tenant_id, collection_id, cid), headers=auth_headers)
        assert resp.status_code == 400

    def test_missing_user_id_param_returns_400(self, base_url, auth_headers, tenant_id, collection_id):
        """PATCH to the credentials collection without ?userId= must return 400.
        [BUG] Currently returns 500 (unhandled MissingServletRequestParameterException) — MUST FAIL until fixed."""
        resp = requests.patch(
            credential_url(base_url, tenant_id, collection_id),
            json={"biometricCredential": {"updatedBy": "test@aware.com"}},
            headers=auth_headers,
        )
        assert resp.status_code == 400

    def test_soft_deleted_user_id_returns_409(self, base_url, auth_headers, tenant_id, collection_id):
        """PATCH ?userId= where that userId was soft-deleted returns 409 (DB unique constraint on
        soft-deleted record prevents upsert). Documents current behavior — ideally should create a
        new credential (201) instead of exposing a raw constraint violation."""
        user_id = f"deleted-upsert-{uuid.uuid4().hex[:8]}"
        create_resp = requests.post(
            credential_url(base_url, tenant_id, collection_id),
            json=create_credential_payload(user_id),
            headers=auth_headers,
        )
        assert create_resp.status_code == 201
        cid = create_resp.json()["biometricCredential"]["id"]
        requests.delete(credential_url(base_url, tenant_id, collection_id, cid), headers=auth_headers)

        resp = requests.patch(
            credential_url(base_url, tenant_id, collection_id),
            params={"userId": user_id},
            json={"biometricCredential": {"updatedBy": "test@aware.com"}},
            headers=auth_headers,
        )
        assert resp.status_code == 409
        assert resp.json().get("error") == "CONFLICT"

    def test_modality_entry_limit_enforced_cumulatively_on_patch_by_user_id(
        self, base_url, auth_headers, tenant_id, collection_id
    ):
        """Spec: for PATCH ?userId=, the 5-entry limit is checked against existing + incoming total.
        A user with 3 face entries must be rejected when PATCHing 3 more (3+3=6 > 5)."""
        from tests.credentials.conftest import _DUMMY_IMAGE_B64
        user_id = f"ulimit-{uuid.uuid4().hex[:8]}"
        three_entries = [{"labels": [f"s{i}"], "data": _DUMMY_IMAGE_B64} for i in range(3)]
        create_resp = requests.post(
            credential_url(base_url, tenant_id, collection_id),
            json={
                "biometricCredential": {
                    "externalUserId": user_id,
                    "biometrics": {"face": three_entries},
                }
            },
            headers=auth_headers,
        )
        assert create_resp.status_code == 201
        cred_id = create_resp.json()["biometricCredential"]["id"]
        try:
            resp = requests.patch(
                credential_url(base_url, tenant_id, collection_id),
                params={"userId": user_id},
                json={"biometricCredential": {"biometrics": {"face": three_entries}}},
                headers=auth_headers,
            )
            assert resp.status_code == 400
            assert resp.json().get("error") == "MODALITY_ENTRY_LIMIT_EXCEEDED"
        finally:
            requests.delete(credential_url(base_url, tenant_id, collection_id, cred_id), headers=auth_headers)
