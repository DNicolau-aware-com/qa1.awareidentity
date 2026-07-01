"""
API Key lifecycle — revoke (PATCH), delete (soft-delete), rotation, get single.

Confirmed behavior:
  DELETE /{id} -> 204, key status becomes INACTIVE (soft-delete, still visible via GET)
  PATCH  /{id} with {"status": "INACTIVE"} -> 200, status updated correctly
  PATCH field is `status` (not `keyStatus`); valid values: ACTIVE, INACTIVE
"""

import uuid
import requests
import pytest

from tests.api_keys.conftest import api_keys_url, valid_create_payload


class TestDelete:

    def test_delete_returns_204(self, base_url, tenant_id, mgmt_headers):
        resp = requests.post(
            api_keys_url(base_url, tenant_id),
            json=valid_create_payload(name=f"del-204-{uuid.uuid4().hex[:6]}"),
            headers=mgmt_headers,
        )
        assert resp.status_code == 200
        key_id = resp.json()["id"]
        del_resp = requests.delete(api_keys_url(base_url, tenant_id, key_id), headers=mgmt_headers)
        assert del_resp.status_code == 204

    def test_delete_soft_deletes_key_to_inactive(self, base_url, tenant_id, mgmt_headers):
        """DELETE is a soft-delete — key becomes INACTIVE, not physically removed."""
        resp = requests.post(
            api_keys_url(base_url, tenant_id),
            json=valid_create_payload(name=f"del-soft-{uuid.uuid4().hex[:6]}"),
            headers=mgmt_headers,
        )
        key_id = resp.json()["id"]
        requests.delete(api_keys_url(base_url, tenant_id, key_id), headers=mgmt_headers)

        get_resp = requests.get(api_keys_url(base_url, tenant_id, key_id), headers=mgmt_headers)
        assert get_resp.status_code == 200, "Soft-deleted key must still be accessible via GET"
        assert get_resp.json().get("status") == "INACTIVE", (
            f"Expected INACTIVE after DELETE, got: {get_resp.json().get('status')}"
        )

    def test_delete_nonexistent_key_returns_404(self, base_url, tenant_id, mgmt_headers):
        resp = requests.delete(
            api_keys_url(base_url, tenant_id, str(uuid.uuid4())), headers=mgmt_headers
        )
        assert resp.status_code == 404

    def test_double_delete_is_idempotent(self, base_url, tenant_id, mgmt_headers):
        """
        Deleting an already-INACTIVE key returns 204 again (idempotent soft-delete).
        Soft-delete just sets status=INACTIVE so a second DELETE has no error to report.
        Spec says confirmation required at UI layer; API layer is idempotent.
        """
        resp = requests.post(
            api_keys_url(base_url, tenant_id),
            json=valid_create_payload(name=f"del-double-{uuid.uuid4().hex[:6]}"),
            headers=mgmt_headers,
        )
        key_id = resp.json()["id"]
        requests.delete(api_keys_url(base_url, tenant_id, key_id), headers=mgmt_headers)
        resp2 = requests.delete(api_keys_url(base_url, tenant_id, key_id), headers=mgmt_headers)
        assert resp2.status_code in (204, 404)


class TestRevoke:

    def test_revoke_changes_status_to_inactive(self, base_url, tenant_id, mgmt_headers):
        """PATCH {"status": "INACTIVE"} returns 200 and updates the key status."""
        resp = requests.post(
            api_keys_url(base_url, tenant_id),
            json=valid_create_payload(name=f"revoke-{uuid.uuid4().hex[:6]}"),
            headers=mgmt_headers,
        )
        key_id = resp.json()["id"]
        patch = requests.patch(
            api_keys_url(base_url, tenant_id, key_id),
            json={"status": "INACTIVE"},
            headers=mgmt_headers,
        )
        assert patch.status_code in (200, 204)
        get_resp = requests.get(api_keys_url(base_url, tenant_id, key_id), headers=mgmt_headers)
        assert get_resp.json().get("status") == "INACTIVE"

    def test_patch_returns_200(self, base_url, tenant_id, mgmt_headers, created_key):
        """PATCH {"status": "INACTIVE"} on an active key returns 200."""
        resp = requests.patch(
            api_keys_url(base_url, tenant_id, created_key["id"]),
            json={"status": "INACTIVE"},
            headers=mgmt_headers,
        )
        assert resp.status_code == 200

    def test_patch_nonexistent_key_returns_404(self, base_url, tenant_id, mgmt_headers):
        """PATCH a non-existent key must return 404 NOT_FOUND."""
        resp = requests.patch(
            api_keys_url(base_url, tenant_id, str(uuid.uuid4())),
            json={"status": "INACTIVE"},
            headers=mgmt_headers,
        )
        assert resp.status_code == 404

    def test_patch_invalid_status_value_returns_400(self, base_url, tenant_id, mgmt_headers, created_key):
        """PATCH with an unrecognised status value returns 400 — REVOKED is not a valid enum value."""
        resp = requests.patch(
            api_keys_url(base_url, tenant_id, created_key["id"]),
            json={"status": "REVOKED"},
            headers=mgmt_headers,
        )
        assert resp.status_code == 400


class TestRotation:

    def test_two_active_keys_both_accessible(self, base_url, tenant_id, mgmt_headers, two_active_keys):
        """Two keys can be active simultaneously — required for zero-downtime rotation."""
        # Use GET /{id} directly — list is paginated and keys may be beyond page 0
        for key in two_active_keys:
            resp = requests.get(api_keys_url(base_url, tenant_id, key["id"]), headers=mgmt_headers)
            assert resp.status_code == 200
            assert resp.json().get("status") == "ACTIVE"

    def test_deleting_one_key_leaves_other_active(self, base_url, tenant_id, mgmt_headers, two_active_keys):
        """Soft-deleting key A must not affect key B."""
        key_a_id = two_active_keys[0]["id"]
        key_b_id = two_active_keys[1]["id"]

        requests.delete(api_keys_url(base_url, tenant_id, key_a_id), headers=mgmt_headers)

        get_b = requests.get(api_keys_url(base_url, tenant_id, key_b_id), headers=mgmt_headers)
        assert get_b.json().get("status") == "ACTIVE", (
            f"Key B changed after deleting Key A: {get_b.json().get('status')}"
        )

    def test_can_create_new_key_while_existing_is_active(
        self, base_url, tenant_id, mgmt_headers, created_key
    ):
        """Replacement key can be created while original is still active (no forced delete-first)."""
        new_resp = requests.post(
            api_keys_url(base_url, tenant_id),
            json=valid_create_payload(name=f"rotation-new-{uuid.uuid4().hex[:6]}"),
            headers=mgmt_headers,
        )
        assert new_resp.status_code == 200
        new_key_id = new_resp.json()["id"]

        orig = requests.get(
            api_keys_url(base_url, tenant_id, created_key["id"]), headers=mgmt_headers
        )
        assert orig.json().get("status") == "ACTIVE", "Original key changed after creating replacement"
        requests.delete(api_keys_url(base_url, tenant_id, new_key_id), headers=mgmt_headers)


class TestGetSingle:

    def test_get_single_returns_200(self, base_url, tenant_id, mgmt_headers, created_key):
        resp = requests.get(
            api_keys_url(base_url, tenant_id, created_key["id"]), headers=mgmt_headers
        )
        assert resp.status_code == 200

    def test_get_single_secret_is_null(self, base_url, tenant_id, mgmt_headers, created_key):
        resp = requests.get(
            api_keys_url(base_url, tenant_id, created_key["id"]), headers=mgmt_headers
        )
        assert resp.json().get("apiKey") is None

    def test_get_nonexistent_key_returns_404(self, base_url, tenant_id, mgmt_headers):
        resp = requests.get(
            api_keys_url(base_url, tenant_id, str(uuid.uuid4())), headers=mgmt_headers
        )
        assert resp.status_code == 404

    def test_get_key_from_wrong_tenant_returns_403_or_404(
        self, base_url, tenant_id, tenant_id_2, mgmt_headers, created_key
    ):
        """Key from tenant A must not be accessible under tenant B's URL."""
        resp = requests.get(
            api_keys_url(base_url, tenant_id_2, created_key["id"]), headers=mgmt_headers
        )
        assert resp.status_code in (403, 404)
