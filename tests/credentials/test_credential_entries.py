"""
Tests for credential entry sub-resource endpoints:
  GET    /credentials/{credentialId}/credentialentries/{entryId}
  PATCH  /credentials/{credentialId}/credentialentries/{entryId}
  DELETE /credentials/{credentialId}/credentialentries/{entryId}

Entries use hard delete (removed from DB, not soft-deleted).
Per-modality limit: 5 entries per modality per credential.
"""

import uuid
import requests
import pytest

from tests.credentials.conftest import (
    credential_url, entry_url, create_credential_payload, _DUMMY_IMAGE_B64,
)

# Modality keys are lower-case in requests and responses (spec: service normalises internally).
_FACE_ENTRY_PAYLOAD = {
    "biometricCredential": {
        "biometrics": {
            "face": [{"data": _DUMMY_IMAGE_B64, "labels": ["front", "visible"]}]
        },
        "updatedBy": "test@aware.com",
    }
}


def _add_face_entry(base_url, auth_headers, tenant_id, collection_id, cred_id):
    """PATCH to add one face entry; return the entry dict.

    Raises AssertionError (not skip) on failure so that the storage bug surfaces as
    a tracked xfail on the consuming test rather than a silent skip."""
    patch_resp = requests.patch(
        credential_url(base_url, tenant_id, collection_id, cred_id),
        json=_FACE_ENTRY_PAYLOAD,
        headers=auth_headers,
    )
    assert patch_resp.status_code == 200, (
        f"Could not add face entry ({patch_resp.status_code}): {patch_resp.text}"
    )

    get_resp = requests.get(credential_url(base_url, tenant_id, collection_id, cred_id), headers=auth_headers)
    entries = get_resp.json()["biometricCredential"].get("biometrics", {}).get("face", [])
    assert entries, "No face entries returned after PATCH"
    return entries[-1]


@pytest.fixture(scope="module")
def cred_with_entry(base_url, auth_headers, tenant_id, collection_id):
    """Create a credential with one FACE entry; yield (cred_id, entry_id). Module-scoped — do not DELETE the entry."""
    user_id = f"entry-ro-{uuid.uuid4().hex[:8]}"
    resp = requests.post(
        credential_url(base_url, tenant_id, collection_id),
        json={"biometricCredential": {"externalUserId": user_id, "biometrics": {}}},
        headers=auth_headers,
    )
    assert resp.status_code == 201, f"Credential setup failed: {resp.text}"
    cred_id = resp.json()["biometricCredential"]["id"]

    entry = _add_face_entry(base_url, auth_headers, tenant_id, collection_id, cred_id)
    entry_id = entry["id"]

    yield cred_id, entry_id
    requests.delete(credential_url(base_url, tenant_id, collection_id, cred_id), headers=auth_headers)


@pytest.fixture
def fresh_entry(base_url, auth_headers, tenant_id, collection_id):
    """Create a credential with one FACE entry; yield (cred_id, entry_id). Credential deleted on teardown."""
    user_id = f"entry-rw-{uuid.uuid4().hex[:8]}"
    resp = requests.post(
        credential_url(base_url, tenant_id, collection_id),
        json={"biometricCredential": {"externalUserId": user_id, "biometrics": {}}},
        headers=auth_headers,
    )
    assert resp.status_code == 201, f"Credential setup failed: {resp.text}"
    cred_id = resp.json()["biometricCredential"]["id"]

    try:
        entry = _add_face_entry(base_url, auth_headers, tenant_id, collection_id, cred_id)
        entry_id = entry["id"]
    except Exception:
        requests.delete(credential_url(base_url, tenant_id, collection_id, cred_id), headers=auth_headers)
        raise

    yield cred_id, entry_id
    requests.delete(credential_url(base_url, tenant_id, collection_id, cred_id), headers=auth_headers)


# ---------------------------------------------------------------------------
# GET entry — 404 cases (no stored entry required; non-xfail tests first so
# collection_id is seeded into the module cache before cred_with_entry runs)
# ---------------------------------------------------------------------------

class TestGetEntryNotFound:

    def test_entry_on_nonexistent_credential_returns_404(self, base_url, auth_headers, tenant_id, collection_id):
        """GET entry on a non-existent credential returns 404."""
        resp = requests.get(
            entry_url(base_url, tenant_id, collection_id, str(uuid.uuid4()), str(uuid.uuid4())),
            headers=auth_headers,
        )
        assert resp.status_code == 404
        assert resp.json().get("error") == "NOT_FOUND"

    def test_random_entry_id_on_real_credential_returns_404(self, base_url, auth_headers, tenant_id, collection_id):
        """Spec: entry 'does not belong to the given credential' → 404.
        Uses a real credential (no entries needed) with a random UUID entryId."""
        cred_resp = requests.post(
            credential_url(base_url, tenant_id, collection_id),
            json=create_credential_payload(),
            headers=auth_headers,
        )
        assert cred_resp.status_code == 201
        cred_id = cred_resp.json()["biometricCredential"]["id"]
        try:
            resp = requests.get(
                entry_url(base_url, tenant_id, collection_id, cred_id, str(uuid.uuid4())),
                headers=auth_headers,
            )
            assert resp.status_code == 404
            assert resp.json().get("error") == "NOT_FOUND"
        finally:
            requests.delete(credential_url(base_url, tenant_id, collection_id, cred_id), headers=auth_headers)

    def test_non_uuid_entry_id_does_not_crash(self, base_url, auth_headers, tenant_id, collection_id):
        """Non-UUID credentialEntryId must not return 500.
        [BUG #4] Currently returns 500 (unhandled MethodArgumentTypeMismatchException). Should be 400."""
        resp = requests.get(
            entry_url(base_url, tenant_id, collection_id, str(uuid.uuid4()), "not-a-uuid"),
            headers=auth_headers,
        )
        assert resp.status_code < 500, f"Server crashed with {resp.status_code}: {resp.text}"

    def test_nonexistent_entry_returns_404(self, base_url, auth_headers, tenant_id, collection_id, cred_with_entry):
        """GET with a random entryId returns 404."""
        cred_id, _ = cred_with_entry
        resp = requests.get(
            entry_url(base_url, tenant_id, collection_id, cred_id, str(uuid.uuid4())),
            headers=auth_headers,
        )
        assert resp.status_code == 404
        assert resp.json().get("error") == "NOT_FOUND"


# ---------------------------------------------------------------------------
# Path ownership validation (GET, PATCH, DELETE)
# ---------------------------------------------------------------------------

class TestEntryPathOwnership:
    """
    Spec: full path /credentials/{credentialId}/credentialentries/{entryId} is validated
    end-to-end. A real entryId accessed via a different credential's path must return 404.
    """

    def test_get_entry_wrong_credential_returns_404(
        self, base_url, auth_headers, tenant_id, collection_id, cred_with_entry
    ):
        """GET a real entryId via a different credential's path returns 404."""
        _, entry_id = cred_with_entry
        other_resp = requests.post(
            credential_url(base_url, tenant_id, collection_id),
            json=create_credential_payload(),
            headers=auth_headers,
        )
        assert other_resp.status_code == 201
        other_cred_id = other_resp.json()["biometricCredential"]["id"]
        try:
            resp = requests.get(
                entry_url(base_url, tenant_id, collection_id, other_cred_id, entry_id),
                headers=auth_headers,
            )
            assert resp.status_code == 404
            assert resp.json().get("error") == "NOT_FOUND"
        finally:
            requests.delete(credential_url(base_url, tenant_id, collection_id, other_cred_id), headers=auth_headers)

    def test_patch_entry_wrong_credential_returns_404(
        self, base_url, auth_headers, tenant_id, collection_id, cred_with_entry
    ):
        """PATCH a real entryId via a different credential's path returns 404."""
        _, entry_id = cred_with_entry
        other_resp = requests.post(
            credential_url(base_url, tenant_id, collection_id),
            json=create_credential_payload(),
            headers=auth_headers,
        )
        assert other_resp.status_code == 201
        other_cred_id = other_resp.json()["biometricCredential"]["id"]
        try:
            resp = requests.patch(
                entry_url(base_url, tenant_id, collection_id, other_cred_id, entry_id),
                json={"credentialEntry": {"labels": ["tampered"]}},
                headers=auth_headers,
            )
            assert resp.status_code == 404
            assert resp.json().get("error") == "NOT_FOUND"
        finally:
            requests.delete(credential_url(base_url, tenant_id, collection_id, other_cred_id), headers=auth_headers)

    def test_delete_entry_wrong_credential_returns_404_and_entry_survives(
        self, base_url, auth_headers, tenant_id, collection_id, cred_with_entry
    ):
        """DELETE a real entryId via a different credential's path returns 404
        and the entry is NOT deleted — still reachable via the correct path."""
        cred_id, entry_id = cred_with_entry
        other_resp = requests.post(
            credential_url(base_url, tenant_id, collection_id),
            json=create_credential_payload(),
            headers=auth_headers,
        )
        assert other_resp.status_code == 201
        other_cred_id = other_resp.json()["biometricCredential"]["id"]
        try:
            resp = requests.delete(
                entry_url(base_url, tenant_id, collection_id, other_cred_id, entry_id),
                headers=auth_headers,
            )
            assert resp.status_code == 404
            assert resp.json().get("error") == "NOT_FOUND"
            verify = requests.get(
                entry_url(base_url, tenant_id, collection_id, cred_id, entry_id),
                headers=auth_headers,
            )
            assert verify.status_code == 200, "Entry must still exist after a failed cross-ownership DELETE"
        finally:
            requests.delete(credential_url(base_url, tenant_id, collection_id, other_cred_id), headers=auth_headers)


# ---------------------------------------------------------------------------
# PATCH entry — validation (no stored entry needed)
# ---------------------------------------------------------------------------

class TestPatchEntryValidation:

    def test_missing_envelope_returns_400(self, base_url, auth_headers, tenant_id, collection_id):
        """PATCH without credentialEntry wrapper returns 400 VALIDATION_FAILED."""
        cred_resp = requests.post(
            credential_url(base_url, tenant_id, collection_id),
            json=create_credential_payload(),
            headers=auth_headers,
        )
        assert cred_resp.status_code == 201
        cred_id = cred_resp.json()["biometricCredential"]["id"]
        try:
            resp = requests.patch(
                entry_url(base_url, tenant_id, collection_id, cred_id, str(uuid.uuid4())),
                json={"labels": ["front"]},
                headers=auth_headers,
            )
            assert resp.status_code == 400
        finally:
            requests.delete(credential_url(base_url, tenant_id, collection_id, cred_id), headers=auth_headers)

    def test_random_entry_id_on_real_credential_returns_404(self, base_url, auth_headers, tenant_id, collection_id):
        """PATCH a random UUID entryId on a real credential returns 404."""
        cred_resp = requests.post(
            credential_url(base_url, tenant_id, collection_id),
            json=create_credential_payload(),
            headers=auth_headers,
        )
        assert cred_resp.status_code == 201
        cred_id = cred_resp.json()["biometricCredential"]["id"]
        try:
            resp = requests.patch(
                entry_url(base_url, tenant_id, collection_id, cred_id, str(uuid.uuid4())),
                json={"credentialEntry": {"labels": ["front"]}},
                headers=auth_headers,
            )
            assert resp.status_code == 404
            assert resp.json().get("error") == "NOT_FOUND"
        finally:
            requests.delete(credential_url(base_url, tenant_id, collection_id, cred_id), headers=auth_headers)

    def test_non_uuid_entry_id_does_not_crash(self, base_url, auth_headers, tenant_id, collection_id):
        """Non-UUID credentialEntryId on PATCH must not return 500.
        [BUG #4] Currently returns 500 (unhandled MethodArgumentTypeMismatchException). Should be 400."""
        resp = requests.patch(
            entry_url(base_url, tenant_id, collection_id, str(uuid.uuid4()), "not-a-uuid"),
            json={"credentialEntry": {"labels": ["front"]}},
            headers=auth_headers,
        )
        assert resp.status_code < 500, f"Server crashed with {resp.status_code}: {resp.text}"


# ---------------------------------------------------------------------------
# GET entry — happy path
# ---------------------------------------------------------------------------

class TestGetEntryHappyPath:

    def test_returns_200(self, base_url, auth_headers, tenant_id, collection_id, cred_with_entry):
        """GET entry by entryId returns 200."""
        cred_id, entry_id = cred_with_entry
        resp = requests.get(entry_url(base_url, tenant_id, collection_id, cred_id, entry_id), headers=auth_headers)
        assert resp.status_code == 200

    def test_response_content_type_is_json(self, base_url, auth_headers, tenant_id, collection_id, cred_with_entry):
        """Response Content-Type is application/json."""
        cred_id, entry_id = cred_with_entry
        resp = requests.get(entry_url(base_url, tenant_id, collection_id, cred_id, entry_id), headers=auth_headers)
        assert "application/json" in resp.headers.get("Content-Type", "")

    def test_response_contains_id(self, base_url, auth_headers, tenant_id, collection_id, cred_with_entry):
        """GET entry response contains an 'id' field matching the requested entryId."""
        cred_id, entry_id = cred_with_entry
        resp = requests.get(entry_url(base_url, tenant_id, collection_id, cred_id, entry_id), headers=auth_headers)
        body = resp.json()
        # Entry may be bare or wrapped; look in common envelope keys
        entry = body.get("biometricCredentialEntry") or body
        assert entry.get("id") == entry_id

    def test_image_data_included_in_get_entry(self, base_url, auth_headers, tenant_id, collection_id, cred_with_entry):
        """GET entry response includes imageData (read endpoint returns stored bytes)."""
        cred_id, entry_id = cred_with_entry
        resp = requests.get(entry_url(base_url, tenant_id, collection_id, cred_id, entry_id), headers=auth_headers)
        body = resp.json()
        entry = body.get("biometricCredentialEntry") or body
        assert "imageData" in entry

    def test_entry_timestamps_are_integer_epoch_ms(self, base_url, auth_headers, tenant_id, collection_id, cred_with_entry):
        """GET entry response includes createdAt and updatedAt as positive epoch-ms integers."""
        cred_id, entry_id = cred_with_entry
        resp = requests.get(entry_url(base_url, tenant_id, collection_id, cred_id, entry_id), headers=auth_headers)
        entry = resp.json().get("biometricCredentialEntry") or resp.json()
        assert isinstance(entry.get("createdAt"), int) and entry["createdAt"] > 0
        assert isinstance(entry.get("updatedAt"), int) and entry["updatedAt"] > 0

    def test_labels_omitted_when_entry_has_no_labels(self, base_url, auth_headers, tenant_id, collection_id):
        """Spec: labels 'Omitted when null or empty' — key must be absent, not [] or null."""
        user_id = f"nolabel-{uuid.uuid4().hex[:8]}"
        cred_resp = requests.post(
            credential_url(base_url, tenant_id, collection_id),
            json={"biometricCredential": {"externalUserId": user_id, "biometrics": {}}},
            headers=auth_headers,
        )
        assert cred_resp.status_code == 201
        cred_id = cred_resp.json()["biometricCredential"]["id"]
        try:
            patch_resp = requests.patch(
                credential_url(base_url, tenant_id, collection_id, cred_id),
                json={"biometricCredential": {"biometrics": {"face": [{"data": _DUMMY_IMAGE_B64}]}, "updatedBy": "test@aware.com"}},
                headers=auth_headers,
            )
            assert patch_resp.status_code == 200
            get_resp = requests.get(credential_url(base_url, tenant_id, collection_id, cred_id), headers=auth_headers)
            face_entries = get_resp.json()["biometricCredential"].get("biometrics", {}).get("face", [])
            assert face_entries, "Expected at least one face entry"
            entry_id = face_entries[-1]["id"]
            entry_resp = requests.get(entry_url(base_url, tenant_id, collection_id, cred_id, entry_id), headers=auth_headers)
            entry = entry_resp.json().get("biometricCredentialEntry") or entry_resp.json()
            assert "labels" not in entry, f"'labels' key must be absent when no labels set; got: {entry.get('labels')!r}"
        finally:
            requests.delete(credential_url(base_url, tenant_id, collection_id, cred_id), headers=auth_headers)


# ---------------------------------------------------------------------------
# PATCH entry
# ---------------------------------------------------------------------------

class TestPatchEntry:

    def test_patch_labels_returns_200(self, base_url, auth_headers, tenant_id, collection_id, fresh_entry):
        """PATCH entry with new labels returns 200."""
        cred_id, entry_id = fresh_entry
        resp = requests.patch(
            entry_url(base_url, tenant_id, collection_id, cred_id, entry_id),
            json={"credentialEntry": {"labels": ["vip"]}},
            headers=auth_headers,
        )
        assert resp.status_code == 200

    def test_patch_labels_persists(self, base_url, auth_headers, tenant_id, collection_id, fresh_entry):
        """Updated labels are reflected in the credential's biometrics after PATCH."""
        cred_id, entry_id = fresh_entry
        requests.patch(
            entry_url(base_url, tenant_id, collection_id, cred_id, entry_id),
            json={"credentialEntry": {"labels": ["vip"]}},
            headers=auth_headers,
        )
        get_resp = requests.get(credential_url(base_url, tenant_id, collection_id, cred_id), headers=auth_headers)
        face_entries = get_resp.json()["biometricCredential"].get("biometrics", {}).get("face", [])
        matching = [e for e in face_entries if e["id"] == entry_id]
        assert matching, "Entry not found in GET after PATCH"
        assert matching[0].get("labels") == ["vip"]

    def test_patch_image_returns_new_entry_id(self, base_url, auth_headers, tenant_id, collection_id, fresh_entry):
        """PATCH entry with new image data creates a replacement entry with a new ID
        (spec: image replacement is a delete-then-create cycle, old entry ID retired)."""
        cred_id, entry_id = fresh_entry
        resp = requests.patch(
            entry_url(base_url, tenant_id, collection_id, cred_id, entry_id),
            json={"credentialEntry": {"data": _DUMMY_IMAGE_B64}},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        new_entry = body.get("biometricCredentialEntry") or body
        # Replacing image yields a new entry ID
        assert new_entry.get("id") != entry_id

    def test_patch_response_does_not_include_image_data(self, base_url, auth_headers, tenant_id, collection_id, fresh_entry):
        """Spec: imageData populated only on GET-by-id, GET-by-userId, and GET-entry — not on PATCH."""
        cred_id, entry_id = fresh_entry
        resp = requests.patch(
            entry_url(base_url, tenant_id, collection_id, cred_id, entry_id),
            json={"credentialEntry": {"labels": ["vip"]}},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        entry = resp.json().get("biometricCredentialEntry") or resp.json()
        assert "imageData" not in entry, "PATCH response must not include imageData (not a read endpoint)"

    def test_data_not_echoed_in_entry_patch_response(self, base_url, auth_headers, tenant_id, collection_id, fresh_entry):
        """Spec: data is 'Write-only — never returned in any response.'"""
        cred_id, entry_id = fresh_entry
        resp = requests.patch(
            entry_url(base_url, tenant_id, collection_id, cred_id, entry_id),
            json={"credentialEntry": {"data": _DUMMY_IMAGE_B64}},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        entry = resp.json().get("biometricCredentialEntry") or resp.json()
        assert "data" not in entry, "data is write-only and must never appear in a response"

    def test_patch_nonexistent_entry_returns_404(self, base_url, auth_headers, tenant_id, collection_id, cred_with_entry):
        """PATCH a non-existent entryId returns 404."""
        cred_id, _ = cred_with_entry
        resp = requests.patch(
            entry_url(base_url, tenant_id, collection_id, cred_id, str(uuid.uuid4())),
            json={"credentialEntry": {"labels": ["front"]}},
            headers=auth_headers,
        )
        assert resp.status_code == 404
        assert resp.json().get("error") == "NOT_FOUND"

    def test_labels_only_retains_same_entry_id(self, base_url, auth_headers, tenant_id, collection_id, fresh_entry):
        """Labels-only PATCH (no data) updates in place — response id must equal the original entryId."""
        cred_id, entry_id = fresh_entry
        resp = requests.patch(
            entry_url(base_url, tenant_id, collection_id, cred_id, entry_id),
            json={"credentialEntry": {"labels": ["vip"]}},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        entry = body.get("biometricCredentialEntry") or body
        assert entry.get("id") == entry_id, "Labels-only PATCH must not change the entry ID"

    def test_data_and_labels_together_returns_new_id(self, base_url, auth_headers, tenant_id, collection_id, fresh_entry):
        """Spec: data and labels may be supplied together — response gets a new UUID (image replace cycle)."""
        cred_id, entry_id = fresh_entry
        resp = requests.patch(
            entry_url(base_url, tenant_id, collection_id, cred_id, entry_id),
            json={"credentialEntry": {"data": _DUMMY_IMAGE_B64, "labels": ["replaced"]}},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        new_entry = body.get("biometricCredentialEntry") or body
        assert new_entry.get("id") != entry_id, "Image replacement must return a new entry UUID"
        assert new_entry.get("labels") == ["replaced"]


# ---------------------------------------------------------------------------
# DELETE entry
# ---------------------------------------------------------------------------

class TestDeleteEntry:

    def test_returns_204(self, base_url, auth_headers, tenant_id, collection_id, fresh_entry):
        """DELETE entry returns 204 No Content."""
        cred_id, entry_id = fresh_entry
        resp = requests.delete(
            entry_url(base_url, tenant_id, collection_id, cred_id, entry_id),
            headers=auth_headers,
        )
        assert resp.status_code == 204

    def test_deleted_entry_get_returns_404(self, base_url, auth_headers, tenant_id, collection_id, fresh_entry):
        """GET on a deleted entry returns 404 (hard delete — entry is permanently removed)."""
        cred_id, entry_id = fresh_entry
        requests.delete(entry_url(base_url, tenant_id, collection_id, cred_id, entry_id), headers=auth_headers)
        resp = requests.get(entry_url(base_url, tenant_id, collection_id, cred_id, entry_id), headers=auth_headers)
        assert resp.status_code == 404
        assert resp.json().get("error") == "NOT_FOUND"

    def test_delete_entry_does_not_delete_credential(self, base_url, auth_headers, tenant_id, collection_id, fresh_entry):
        """Deleting the last entry does not soft-delete the parent credential."""
        cred_id, entry_id = fresh_entry
        requests.delete(entry_url(base_url, tenant_id, collection_id, cred_id, entry_id), headers=auth_headers)
        cred_resp = requests.get(credential_url(base_url, tenant_id, collection_id, cred_id), headers=auth_headers)
        assert cred_resp.status_code == 200

    def test_delete_nonexistent_entry_returns_404(self, base_url, auth_headers, tenant_id, collection_id, cred_with_entry):
        """DELETE a non-existent entryId returns 404."""
        cred_id, _ = cred_with_entry
        resp = requests.delete(
            entry_url(base_url, tenant_id, collection_id, cred_id, str(uuid.uuid4())),
            headers=auth_headers,
        )
        assert resp.status_code == 404
        assert resp.json().get("error") == "NOT_FOUND"


# ---------------------------------------------------------------------------
# Modality entry limit
# ---------------------------------------------------------------------------

class TestPatchEntryUpdatedBy:
    """Spec: updatedBy on BiometricCredentialEntryPatchRequest must be a plain name or email if supplied."""

    def test_updated_by_accepted_on_entry_patch(self, base_url, auth_headers, tenant_id, collection_id, fresh_entry):
        """Valid updatedBy is accepted on entry PATCH."""
        cred_id, entry_id = fresh_entry
        resp = requests.patch(
            entry_url(base_url, tenant_id, collection_id, cred_id, entry_id),
            json={"credentialEntry": {"labels": ["vip"], "updatedBy": "auditor@aware.com"}},
            headers=auth_headers,
        )
        assert resp.status_code == 200

    def test_invalid_updated_by_in_entry_patch_returns_400(self, base_url, auth_headers, tenant_id, collection_id, fresh_entry):
        """XSS payload in updatedBy on entry PATCH must be rejected with 400."""
        cred_id, entry_id = fresh_entry
        resp = requests.patch(
            entry_url(base_url, tenant_id, collection_id, cred_id, entry_id),
            json={"credentialEntry": {"labels": ["vip"], "updatedBy": "<script>alert(1)</script>"}},
            headers=auth_headers,
        )
        assert resp.status_code == 400


class TestModalityEntryLimit:

    def test_sixth_entry_exceeds_limit(self, base_url, auth_headers, tenant_id, collection_id):
        """Adding a 6th entry for the same modality returns 400 MODALITY_ENTRY_LIMIT_EXCEEDED (limit is 5)."""
        user_id = f"limit-{uuid.uuid4().hex[:8]}"
        create_resp = requests.post(
            credential_url(base_url, tenant_id, collection_id),
            json={"biometricCredential": {"externalUserId": user_id, "biometrics": {}}},
            headers=auth_headers,
        )
        assert create_resp.status_code == 201
        cred_id = create_resp.json()["biometricCredential"]["id"]

        try:
            # Add 5 entries — all should succeed
            for i in range(5):
                r = requests.patch(
                    credential_url(base_url, tenant_id, collection_id, cred_id),
                    json={
                        "biometricCredential": {
                            "biometrics": {"face": [{"data": _DUMMY_IMAGE_B64}]},
                            "updatedBy": "test@aware.com",
                        }
                    },
                    headers=auth_headers,
                )
                assert r.status_code in (200, 201), (
                    f"Could not add entry {i + 1} ({r.status_code}): {r.text}"
                )

            # The 6th entry must be rejected
            sixth = requests.patch(
                credential_url(base_url, tenant_id, collection_id, cred_id),
                json={
                    "biometricCredential": {
                        "biometrics": {"face": [{"data": _DUMMY_IMAGE_B64}]},
                        "updatedBy": "test@aware.com",
                    }
                },
                headers=auth_headers,
            )
            assert sixth.status_code == 400
            assert sixth.json().get("error") == "MODALITY_ENTRY_LIMIT_EXCEEDED"
        finally:
            requests.delete(credential_url(base_url, tenant_id, collection_id, cred_id), headers=auth_headers)
