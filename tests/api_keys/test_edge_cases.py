"""
Edge case tests for API Key Management.

Covers:
  1.  INACTIVE key still authenticates (security)
  2.  Cross-tenant key usage (security)
  3.  GET /secret on INACTIVE key (security)
  4.  expiresAt field — can it be set, does it enforce expiry
  5.  Very long keyName (DoS / crash)
  6.  Injection in keyName (XSS / SQLi)
  7.  Rotate credentials on INACTIVE key
  8.  PATCH on INACTIVE key
  9.  Invalid pagination params (page=-1, size=0, size=99999)
  10. SUSPENDED / PENDING / FAILED status via PATCH
  11. clearExpiresAt flag in PATCH
  12. description max length (spec: 1024)
  13. Unknown fields on create / PATCH (additionalProperties: false)
  14. PERSONAL visibility + X-User-Id filtering
  15. sort param — valid, unknown field, bad format
  16. expiresAt format edge cases (timezone, invalid, far future)
  17. PATCH expiresAt to past date — key becomes immediately expired
  18. PATCH body edge cases (empty body, clearExpiresAt: false, conflict with expiresAt)
  19. Rotation security — old secret immediately invalidated after rotation
  20. Additional input validation (visibility invalid value, whitespace keyName, description injection, malformed header)
  21. List pagination edge cases (page beyond total, multiple sort params, size=1)
  22. Security misc (API key in query param, cross-tenant PATCH)
"""

import uuid
import requests
import pytest

from tests.api_keys.conftest import api_keys_url, valid_create_payload


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def create_key(base_url, tenant_id, mgmt_headers, name=None):
    resp = requests.post(
        api_keys_url(base_url, tenant_id),
        json=valid_create_payload(name=name or f"edge-{uuid.uuid4().hex[:8]}"),
        headers=mgmt_headers,
    )
    assert resp.status_code == 200, f"Setup failed: {resp.status_code} {resp.text[:200]}"
    return resp.json()


def soft_delete(base_url, tenant_id, key_id, mgmt_headers):
    requests.delete(api_keys_url(base_url, tenant_id, key_id), headers=mgmt_headers)


# ---------------------------------------------------------------------------
# 1. INACTIVE key authentication
# ---------------------------------------------------------------------------

class TestInactiveKeyAuthentication:

    def test_inactive_key_cannot_authenticate(self, base_url, tenant_id, mgmt_headers):
        """A soft-deleted (INACTIVE) key must be rejected when used to authenticate."""
        key = create_key(base_url, tenant_id, mgmt_headers, name=f"inactive-auth-{uuid.uuid4().hex[:6]}")
        secret = key["apiKey"]
        key_id = key["id"]

        # Confirm key works before deletion
        pre_resp = requests.get(
            f"{base_url}/v3/tenants/{tenant_id}/collections",
            headers={"X-Aware-ApiKey": secret, "X-Aware-AccountId": "0001"},
        )
        assert pre_resp.status_code == 200, f"Key did not authenticate before delete: {pre_resp.status_code}"

        # Soft-delete
        soft_delete(base_url, tenant_id, key_id, mgmt_headers)

        # Confirm status is INACTIVE
        get_resp = requests.get(api_keys_url(base_url, tenant_id, key_id), headers=mgmt_headers)
        assert get_resp.json().get("status") == "INACTIVE"

        # Try to authenticate with the deleted key
        post_resp = requests.get(
            f"{base_url}/v3/tenants/{tenant_id}/collections",
            headers={"X-Aware-ApiKey": secret, "X-Aware-AccountId": "0001"},
        )
        assert post_resp.status_code in (401, 403), (
            f"INACTIVE key still authenticates — got {post_resp.status_code}. "
            "Soft-deleted keys must be rejected."
        )


# ---------------------------------------------------------------------------
# 2. Cross-tenant key usage
# ---------------------------------------------------------------------------

class TestCrossTenantKeyUsage:

    def test_tenant_a_key_cannot_access_tenant_b(
        self, base_url, tenant_id, tenant_id_2, mgmt_headers
    ):
        """Key issued for tenant A must not authenticate requests on tenant B's endpoints."""
        key = create_key(base_url, tenant_id, mgmt_headers, name=f"cross-tenant-{uuid.uuid4().hex[:6]}")
        secret = key["apiKey"]
        key_id = key["id"]

        # Try to use tenant A key against tenant B endpoint
        resp = requests.get(
            f"{base_url}/v3/tenants/{tenant_id_2}/collections",
            headers={"X-Aware-ApiKey": secret, "X-Aware-AccountId": "0001"},
        )

        # Cleanup before asserting
        soft_delete(base_url, tenant_id, key_id, mgmt_headers)

        assert resp.status_code in (401, 403), (
            f"Tenant A key accessed tenant B endpoint — got {resp.status_code}. "
            "Cross-tenant access must be blocked."
        )


# ---------------------------------------------------------------------------
# 3. GET /secret on INACTIVE key
# ---------------------------------------------------------------------------

class TestSecretOnInactiveKey:

    def test_secret_not_retrievable_after_soft_delete(self, base_url, tenant_id, mgmt_headers):
        """GET /secret on a soft-deleted key must return 404 — secret must not be retrievable."""
        key = create_key(base_url, tenant_id, mgmt_headers, name=f"secret-inactive-{uuid.uuid4().hex[:6]}")
        key_id = key["id"]

        soft_delete(base_url, tenant_id, key_id, mgmt_headers)

        resp = requests.get(
            api_keys_url(base_url, tenant_id, key_id, sub="secret"),
            headers=mgmt_headers,
        )
        assert resp.status_code == 404, (
            f"GET /secret returned {resp.status_code} on INACTIVE key — "
            "soft-deleted key secret must not be retrievable."
        )


# ---------------------------------------------------------------------------
# 4. expiresAt field
# ---------------------------------------------------------------------------

class TestExpiresAt:

    def test_expires_at_can_be_set_at_creation(self, base_url, tenant_id, mgmt_headers):
        """expiresAt can be set at creation time."""
        payload = valid_create_payload(name=f"expires-{uuid.uuid4().hex[:6]}")
        payload["expiresAt"] = "2030-01-01T00:00:00Z"

        resp = requests.post(api_keys_url(base_url, tenant_id), json=payload, headers=mgmt_headers)
        key_id = resp.json().get("id")

        result = resp.json().get("expiresAt")
        if key_id:
            soft_delete(base_url, tenant_id, key_id, mgmt_headers)

        assert resp.status_code == 200
        assert result is not None, "expiresAt was ignored — field not stored"

    def test_expired_key_cannot_authenticate(self, base_url, tenant_id, mgmt_headers):
        """A key with expiresAt in the past must not authenticate."""
        payload = valid_create_payload(name=f"expired-{uuid.uuid4().hex[:6]}")
        payload["expiresAt"] = "2000-01-01T00:00:00Z"  # already expired

        resp = requests.post(api_keys_url(base_url, tenant_id), json=payload, headers=mgmt_headers)
        key = resp.json()
        key_id = key.get("id")
        secret = key.get("apiKey")

        if not secret:
            soft_delete(base_url, tenant_id, key_id, mgmt_headers)
            pytest.skip("No secret returned — cannot test auth")

        auth_resp = requests.get(
            f"{base_url}/v3/tenants/{tenant_id}/collections",
            headers={"X-Aware-ApiKey": secret, "X-Aware-AccountId": "0001"},
        )

        soft_delete(base_url, tenant_id, key_id, mgmt_headers)

        assert auth_resp.status_code in (401, 403), (
            f"Expired key (expiresAt=2000-01-01) still authenticated — got {auth_resp.status_code}"
        )


# ---------------------------------------------------------------------------
# 5. Very long keyName
# ---------------------------------------------------------------------------

class TestLongKeyName:

    def test_very_long_key_name_returns_4xx(self, base_url, tenant_id, mgmt_headers):
        """keyName of 10,000 characters must return 400, not crash with 500."""
        long_name = "a" * 10000
        resp = requests.post(
            api_keys_url(base_url, tenant_id),
            json={"keyName": long_name, "description": "long name test", "visibility": "ORGANIZATION"},
            headers=mgmt_headers,
        )
        key_id = resp.json().get("id") if resp.status_code == 200 else None
        if key_id:
            soft_delete(base_url, tenant_id, key_id, mgmt_headers)

        assert resp.status_code in (400, 422), (
            f"Expected 400/422 for 10,000-char keyName, got {resp.status_code}: {resp.text[:300]}"
        )

    def test_boundary_key_name_255_chars(self, base_url, tenant_id, mgmt_headers):
        """keyName of 255 characters — document whether it is accepted or rejected."""
        name_255 = "a" * 255
        resp = requests.post(
            api_keys_url(base_url, tenant_id),
            json={"keyName": name_255, "description": "255-char name", "visibility": "ORGANIZATION"},
            headers=mgmt_headers,
        )
        key_id = resp.json().get("id") if resp.status_code == 200 else None
        if key_id:
            soft_delete(base_url, tenant_id, key_id, mgmt_headers)

        assert resp.status_code in (200, 400, 422), (
            f"Unexpected status for 255-char keyName: {resp.status_code}"
        )


# ---------------------------------------------------------------------------
# 6. Injection in keyName
# ---------------------------------------------------------------------------

class TestInjectionInKeyName:

    @pytest.mark.parametrize("payload,label", [
        ("'; DROP TABLE api_keys; --", "sql_injection"),
        ("<script>alert(1)</script>", "xss_html"),
        ("{{7*7}}", "ssti_template"),
        ("../../../etc/passwd", "path_traversal"),
        ("\x00nullbyte", "null_byte"),
    ])
    def test_injection_payload_stored_safely(self, base_url, tenant_id, mgmt_headers, payload, label):
        """Injection payloads must be stored as literal strings or rejected — never executed."""
        resp = requests.post(
            api_keys_url(base_url, tenant_id),
            json={"keyName": payload, "description": f"injection test: {label}", "visibility": "ORGANIZATION"},
            headers=mgmt_headers,
        )
        key_id = resp.json().get("id") if resp.status_code == 200 else None

        if resp.status_code == 200:
            # If accepted, the stored value must match the literal input
            stored_name = resp.json().get("keyName")
            if key_id:
                soft_delete(base_url, tenant_id, key_id, mgmt_headers)
            assert stored_name == payload, (
                f"Stored keyName does not match input for {label} — "
                f"possible injection processing: input={payload!r}, stored={stored_name!r}"
            )
        else:
            # Rejected with 400/422 is also acceptable
            assert resp.status_code in (400, 422), (
                f"Unexpected status {resp.status_code} for {label} payload"
            )


# ---------------------------------------------------------------------------
# 7. Rotate credentials on INACTIVE key
# ---------------------------------------------------------------------------

class TestRotateOnInactiveKey:

    def test_rotate_on_inactive_key_returns_4xx(self, base_url, tenant_id, mgmt_headers):
        """Rotating credentials on a soft-deleted (INACTIVE) key must return 400 or 404."""
        key = create_key(base_url, tenant_id, mgmt_headers, name=f"rotate-inactive-{uuid.uuid4().hex[:6]}")
        key_id = key["id"]

        soft_delete(base_url, tenant_id, key_id, mgmt_headers)

        resp = requests.post(
            api_keys_url(base_url, tenant_id, key_id, sub="rotate-credentials"),
            headers=mgmt_headers,
        )
        assert resp.status_code in (400, 404), (
            f"Rotate on INACTIVE key returned {resp.status_code} — "
            f"expected 400/404. Body: {resp.text[:200]}"
        )


# ---------------------------------------------------------------------------
# 8. PATCH on INACTIVE key
# ---------------------------------------------------------------------------

class TestPatchOnInactiveKey:

    def test_patch_on_inactive_key_returns_4xx(self, base_url, tenant_id, mgmt_headers):
        """PATCH on a soft-deleted (INACTIVE) key must return 400 or 404."""
        key = create_key(base_url, tenant_id, mgmt_headers, name=f"patch-inactive-{uuid.uuid4().hex[:6]}")
        key_id = key["id"]

        soft_delete(base_url, tenant_id, key_id, mgmt_headers)

        resp = requests.patch(
            api_keys_url(base_url, tenant_id, key_id),
            json={"status": "ACTIVE"},
            headers=mgmt_headers,
        )
        assert resp.status_code in (400, 404), (
            f"PATCH on INACTIVE key returned {resp.status_code} — "
            f"expected 400/404. Body: {resp.text[:200]}"
        )


# ---------------------------------------------------------------------------
# 9. Invalid pagination params
# ---------------------------------------------------------------------------

class TestInvalidPagination:

    def test_negative_page_returns_4xx_or_200(self, base_url, tenant_id, mgmt_headers):
        """page=-1 must not crash with 500."""
        resp = requests.get(
            api_keys_url(base_url, tenant_id),
            params={"page": -1, "size": 20},
            headers=mgmt_headers,
        )
        assert resp.status_code != 500, (
            f"page=-1 crashed with 500: {resp.text[:200]}"
        )

    def test_zero_size_returns_4xx_or_200(self, base_url, tenant_id, mgmt_headers):
        """size=0 must not crash with 500."""
        resp = requests.get(
            api_keys_url(base_url, tenant_id),
            params={"page": 0, "size": 0},
            headers=mgmt_headers,
        )
        assert resp.status_code != 500, (
            f"size=0 crashed with 500: {resp.text[:200]}"
        )

    def test_huge_size_returns_4xx_or_200(self, base_url, tenant_id, mgmt_headers):
        """size=99999 must not crash with 500."""
        resp = requests.get(
            api_keys_url(base_url, tenant_id),
            params={"page": 0, "size": 99999},
            headers=mgmt_headers,
        )
        assert resp.status_code != 500, (
            f"size=99999 crashed with 500: {resp.text[:200]}"
        )

    def test_non_numeric_page_returns_4xx(self, base_url, tenant_id, mgmt_headers):
        """page=abc must return 400, not 500.
        [BUG] Non-numeric page param returns non-400 — MUST FAIL until input validation is added."""
        resp = requests.get(
            api_keys_url(base_url, tenant_id),
            params={"page": "abc", "size": 20},
            headers=mgmt_headers,
        )
        assert resp.status_code in (400, 422), (
            f"Non-numeric page param returned {resp.status_code}: {resp.text[:200]}"
        )


# ---------------------------------------------------------------------------
# 10. SUSPENDED / PENDING / FAILED status via PATCH
# ---------------------------------------------------------------------------

class TestStatusTransitions:

    def test_patch_status_suspended(self, base_url, tenant_id, mgmt_headers):
        """PATCH {"status": "SUSPENDED"} — document whether accepted or rejected.
        SUSPENDED = temporarily disabled (spec enum value). If accepted, key must not authenticate."""
        key = create_key(base_url, tenant_id, mgmt_headers, name=f"suspended-{uuid.uuid4().hex[:6]}")
        key_id = key["id"]
        secret = key["apiKey"]

        resp = requests.patch(
            api_keys_url(base_url, tenant_id, key_id),
            json={"status": "SUSPENDED"},
            headers=mgmt_headers,
        )

        if resp.status_code == 200:
            assert resp.json().get("status") == "SUSPENDED"
            # If accepted, SUSPENDED key must not authenticate
            auth_resp = requests.get(
                f"{base_url}/v3/tenants/{tenant_id}/collections",
                headers={"X-Aware-ApiKey": secret, "X-Aware-AccountId": "0001"},
            )
            soft_delete(base_url, tenant_id, key_id, mgmt_headers)
            assert auth_resp.status_code in (401, 403), (
                f"SUSPENDED key still authenticated — got {auth_resp.status_code}"
            )
        else:
            soft_delete(base_url, tenant_id, key_id, mgmt_headers)
            assert resp.status_code in (400, 422), (
                f"Unexpected status for SUSPENDED PATCH: {resp.status_code} {resp.text[:200]}"
            )

    @pytest.mark.parametrize("status_val", ["PENDING", "FAILED"])
    def test_patch_provisioning_status_rejected(self, base_url, tenant_id, mgmt_headers, status_val):
        """PENDING and FAILED are provisioning states — must not be settable via PATCH.
        [BUG] API accepts PATCH to PENDING/FAILED (200) — provisioning statuses must be rejected."""
        key = create_key(base_url, tenant_id, mgmt_headers, name=f"prov-{uuid.uuid4().hex[:6]}")
        key_id = key["id"]

        resp = requests.patch(
            api_keys_url(base_url, tenant_id, key_id),
            json={"status": status_val},
            headers=mgmt_headers,
        )
        soft_delete(base_url, tenant_id, key_id, mgmt_headers)

        assert resp.status_code in (400, 422), (
            f"PATCH to {status_val} returned {resp.status_code} — "
            f"provisioning statuses must not be settable via PATCH. Body: {resp.text[:200]}"
        )


# ---------------------------------------------------------------------------
# 11. clearExpiresAt flag in PATCH
# ---------------------------------------------------------------------------

class TestClearExpiresAt:

    def test_clear_expires_at_removes_expiry(self, base_url, tenant_id, mgmt_headers):
        """PATCH {"clearExpiresAt": true} must remove an existing expiry date."""
        payload = valid_create_payload(name=f"clear-exp-{uuid.uuid4().hex[:6]}")
        payload["expiresAt"] = "2030-01-01T00:00:00"
        resp = requests.post(api_keys_url(base_url, tenant_id), json=payload, headers=mgmt_headers)
        assert resp.status_code == 200
        key_id = resp.json()["id"]
        assert resp.json().get("expiresAt") is not None, "expiresAt not set at creation"

        patch = requests.patch(
            api_keys_url(base_url, tenant_id, key_id),
            json={"clearExpiresAt": True},
            headers=mgmt_headers,
        )
        soft_delete(base_url, tenant_id, key_id, mgmt_headers)

        assert patch.status_code == 200, (
            f"clearExpiresAt PATCH returned {patch.status_code}: {patch.text[:200]}"
        )
        assert patch.json().get("expiresAt") is None, (
            f"expiresAt not cleared — still: {patch.json().get('expiresAt')}"
        )

    def test_clear_expires_at_on_key_without_expiry(self, base_url, tenant_id, mgmt_headers):
        """PATCH {"clearExpiresAt": true} on a key that has no expiry must not error."""
        key = create_key(base_url, tenant_id, mgmt_headers, name=f"clear-noexp-{uuid.uuid4().hex[:6]}")
        key_id = key["id"]

        resp = requests.patch(
            api_keys_url(base_url, tenant_id, key_id),
            json={"clearExpiresAt": True},
            headers=mgmt_headers,
        )
        soft_delete(base_url, tenant_id, key_id, mgmt_headers)

        assert resp.status_code in (200, 204), (
            f"clearExpiresAt on key with no expiry returned {resp.status_code}: {resp.text[:200]}"
        )


# ---------------------------------------------------------------------------
# 12. description max length
# ---------------------------------------------------------------------------

class TestLongDescription:

    def test_description_at_1024_chars_accepted(self, base_url, tenant_id, mgmt_headers):
        """description of exactly 1024 characters must be accepted (spec maxLength: 1024)."""
        payload = valid_create_payload(name=f"desc-1024-{uuid.uuid4().hex[:6]}")
        payload["description"] = "a" * 1024
        resp = requests.post(api_keys_url(base_url, tenant_id), json=payload, headers=mgmt_headers)
        key_id = resp.json().get("id") if resp.status_code == 200 else None
        if key_id:
            soft_delete(base_url, tenant_id, key_id, mgmt_headers)

        assert resp.status_code == 200, (
            f"1024-char description rejected with {resp.status_code}: {resp.text[:200]}"
        )

    def test_description_over_1024_chars_rejected(self, base_url, tenant_id, mgmt_headers):
        """description over 1024 characters must return 400 (spec maxLength: 1024)."""
        payload = valid_create_payload(name=f"desc-long-{uuid.uuid4().hex[:6]}")
        payload["description"] = "a" * 1025
        resp = requests.post(api_keys_url(base_url, tenant_id), json=payload, headers=mgmt_headers)
        key_id = resp.json().get("id") if resp.status_code == 200 else None
        if key_id:
            soft_delete(base_url, tenant_id, key_id, mgmt_headers)

        assert resp.status_code in (400, 422), (
            f"1025-char description accepted with {resp.status_code} — "
            f"spec maxLength is 1024. Body: {resp.text[:200]}"
        )


# ---------------------------------------------------------------------------
# 13. Unknown fields (additionalProperties: false)
# ---------------------------------------------------------------------------

class TestUnknownFields:

    def test_unknown_field_in_create_returns_400(self, base_url, tenant_id, mgmt_headers):
        """POST body with unknown field must return 400 (spec: additionalProperties: false).
        [BUG] Unknown field in POST body silently accepted (200) — MUST FAIL until fixed."""
        resp = requests.post(
            api_keys_url(base_url, tenant_id),
            json={
                "keyName": f"unknown-field-{uuid.uuid4().hex[:6]}",
                "visibility": "ORGANIZATION",
                "unknownField": "should-be-rejected",
            },
            headers=mgmt_headers,
        )
        key_id = resp.json().get("id") if resp.status_code == 200 else None
        if key_id:
            soft_delete(base_url, tenant_id, key_id, mgmt_headers)

        assert resp.status_code in (400, 422), (
            f"Unknown field in POST body accepted with {resp.status_code}: {resp.text[:200]}"
        )

    def test_unknown_field_in_patch_returns_400(self, base_url, tenant_id, mgmt_headers):
        """PATCH body with unknown field must return 400 (spec: additionalProperties: false)."""
        key = create_key(base_url, tenant_id, mgmt_headers, name=f"patch-unknown-{uuid.uuid4().hex[:6]}")
        key_id = key["id"]

        resp = requests.patch(
            api_keys_url(base_url, tenant_id, key_id),
            json={"unknownField": "should-be-rejected"},
            headers=mgmt_headers,
        )
        soft_delete(base_url, tenant_id, key_id, mgmt_headers)

        assert resp.status_code in (400, 422), (
            f"Unknown field in PATCH body accepted with {resp.status_code}: {resp.text[:200]}"
        )

    def test_apikey_field_in_patch_returns_400(self, base_url, tenant_id, mgmt_headers):
        """PATCH with 'apiKey' field must return 400 — secret can only be changed via rotate-credentials."""
        key = create_key(base_url, tenant_id, mgmt_headers, name=f"patch-apikey-{uuid.uuid4().hex[:6]}")
        key_id = key["id"]

        resp = requests.patch(
            api_keys_url(base_url, tenant_id, key_id),
            json={"apiKey": "0" * 64},
            headers=mgmt_headers,
        )
        soft_delete(base_url, tenant_id, key_id, mgmt_headers)

        assert resp.status_code in (400, 422), (
            f"PATCH apiKey field accepted with {resp.status_code} — "
            f"must use rotate-credentials. Body: {resp.text[:200]}"
        )


# ---------------------------------------------------------------------------
# 14. PERSONAL visibility + X-User-Id filtering
# ---------------------------------------------------------------------------

class TestPersonalVisibility:

    def test_personal_key_not_visible_in_list_without_user_id(self, base_url, tenant_id, mgmt_headers):
        """A PERSONAL key must not appear in list responses that omit X-User-Id.
        [BUG] PERSONAL keys are visible without X-User-Id — MUST FAIL until visibility filtering is fixed."""
        user_id = f"test-user-{uuid.uuid4().hex[:8]}"
        headers_with_user = {**mgmt_headers, "X-User-Id": user_id}

        resp = requests.post(
            api_keys_url(base_url, tenant_id),
            json={"keyName": f"personal-{uuid.uuid4().hex[:6]}", "visibility": "PERSONAL"},
            headers=headers_with_user,
        )
        assert resp.status_code == 200
        key_id = resp.json()["id"]

        # Sort newest-first so the freshly created key is on page 0
        list_resp = requests.get(
            api_keys_url(base_url, tenant_id),
            params={"sort": "createdAt,desc", "size": 5},
            headers=mgmt_headers,
        )
        soft_delete(base_url, tenant_id, key_id, mgmt_headers)

        assert list_resp.status_code == 200
        ids_in_list = [k["id"] for k in list_resp.json().get("content", [])]
        assert key_id not in ids_in_list, (
            "PERSONAL key visible in list without X-User-Id — must be filtered"
        )

    def test_personal_key_visible_with_matching_user_id(self, base_url, tenant_id, mgmt_headers):
        """A PERSONAL key must appear in list when X-User-Id matches the creating user."""
        user_id = f"test-user-{uuid.uuid4().hex[:8]}"
        headers_with_user = {**mgmt_headers, "X-User-Id": user_id}

        resp = requests.post(
            api_keys_url(base_url, tenant_id),
            json={"keyName": f"personal-vis-{uuid.uuid4().hex[:6]}", "visibility": "PERSONAL"},
            headers=headers_with_user,
        )
        assert resp.status_code == 200
        key_id = resp.json()["id"]

        # Sort newest-first so the freshly created key is on page 0
        list_resp = requests.get(
            api_keys_url(base_url, tenant_id),
            params={"sort": "createdAt,desc", "size": 5},
            headers=headers_with_user,
        )
        soft_delete(base_url, tenant_id, key_id, mgmt_headers)

        assert list_resp.status_code == 200
        ids_in_list = [k["id"] for k in list_resp.json().get("content", [])]
        assert key_id in ids_in_list, (
            "PERSONAL key not visible in list with matching X-User-Id"
        )

    def test_personal_key_not_visible_with_different_user_id(self, base_url, tenant_id, mgmt_headers):
        """A PERSONAL key must not appear when X-User-Id belongs to a different user."""
        creator_id = f"creator-{uuid.uuid4().hex[:8]}"
        other_id = f"other-{uuid.uuid4().hex[:8]}"
        headers_creator = {**mgmt_headers, "X-User-Id": creator_id}
        headers_other = {**mgmt_headers, "X-User-Id": other_id}

        resp = requests.post(
            api_keys_url(base_url, tenant_id),
            json={"keyName": f"personal-other-{uuid.uuid4().hex[:6]}", "visibility": "PERSONAL"},
            headers=headers_creator,
        )
        assert resp.status_code == 200
        key_id = resp.json()["id"]

        # Sort newest-first so the freshly created key would appear if it were visible
        list_resp = requests.get(
            api_keys_url(base_url, tenant_id),
            params={"sort": "createdAt,desc", "size": 5},
            headers=headers_other,
        )
        soft_delete(base_url, tenant_id, key_id, mgmt_headers)

        assert list_resp.status_code == 200
        ids_in_list = [k["id"] for k in list_resp.json().get("content", [])]
        assert key_id not in ids_in_list, (
            "PERSONAL key visible to a different user — must be filtered by X-User-Id"
        )


# ---------------------------------------------------------------------------
# 15. sort param
# ---------------------------------------------------------------------------

class TestSortParam:

    @pytest.mark.parametrize("sort_val", ["createdAt,desc", "createdAt,asc"])
    def test_valid_sort_returns_200(self, base_url, tenant_id, mgmt_headers, sort_val):
        """Well-formed sort by createdAt must return 200."""
        resp = requests.get(
            api_keys_url(base_url, tenant_id),
            params={"sort": sort_val},
            headers=mgmt_headers,
        )
        assert resp.status_code == 200, (
            f"sort={sort_val!r} returned {resp.status_code}: {resp.text[:200]}"
        )

    def test_sort_by_key_name_returns_200(self, base_url, tenant_id, mgmt_headers):
        """sort=keyName,asc must return 200 — keyName is a valid spec field.
        [BUG] sort=keyName,asc crashes with 500 — MUST FAIL until sort validation is fixed."""
        resp = requests.get(
            api_keys_url(base_url, tenant_id),
            params={"sort": "keyName,asc"},
            headers=mgmt_headers,
        )
        assert resp.status_code == 200, (
            f"sort=keyName,asc returned {resp.status_code}: {resp.text[:200]}"
        )

    def test_unknown_sort_field_does_not_crash(self, base_url, tenant_id, mgmt_headers):
        """sort=nonexistent,asc must return 400, not crash with 500.
        [BUG] Unknown sort field crashes with 500 — MUST FAIL until sort validation is fixed."""
        resp = requests.get(
            api_keys_url(base_url, tenant_id),
            params={"sort": "nonexistent,asc"},
            headers=mgmt_headers,
        )
        assert resp.status_code != 500, (
            f"Unknown sort field crashed with 500: {resp.text[:200]}"
        )

    def test_malformed_sort_does_not_crash(self, base_url, tenant_id, mgmt_headers):
        """sort=INVALID (no comma, no direction) must return 400, not crash with 500.
        [BUG] Malformed sort param crashes with 500 — MUST FAIL until sort validation is fixed."""
        resp = requests.get(
            api_keys_url(base_url, tenant_id),
            params={"sort": "INVALID"},
            headers=mgmt_headers,
        )
        assert resp.status_code != 500, (
            f"Malformed sort param crashed with 500: {resp.text[:200]}"
        )


# ---------------------------------------------------------------------------
# 16. expiresAt format edge cases
# ---------------------------------------------------------------------------

class TestExpiresAtFormats:

    def test_expires_at_with_timezone_offset_rejected_or_accepted(
        self, base_url, tenant_id, mgmt_headers
    ):
        """expiresAt with timezone offset — spec says ISO-8601 local datetime (no timezone).
        Document whether timezone is accepted or rejected."""
        payload = valid_create_payload(name=f"exp-tz-{uuid.uuid4().hex[:6]}")
        payload["expiresAt"] = "2030-01-01T00:00:00+05:30"
        resp = requests.post(api_keys_url(base_url, tenant_id), json=payload, headers=mgmt_headers)
        key_id = resp.json().get("id") if resp.status_code == 200 else None
        if key_id:
            soft_delete(base_url, tenant_id, key_id, mgmt_headers)

        assert resp.status_code != 500, (
            f"Timezone offset in expiresAt crashed with 500: {resp.text[:200]}"
        )

    def test_expires_at_invalid_format_returns_400(self, base_url, tenant_id, mgmt_headers):
        """expiresAt with non-datetime string must return 400."""
        payload = valid_create_payload(name=f"exp-inv-{uuid.uuid4().hex[:6]}")
        payload["expiresAt"] = "not-a-date"
        resp = requests.post(api_keys_url(base_url, tenant_id), json=payload, headers=mgmt_headers)
        key_id = resp.json().get("id") if resp.status_code == 200 else None
        if key_id:
            soft_delete(base_url, tenant_id, key_id, mgmt_headers)

        assert resp.status_code in (400, 422), (
            f"Invalid expiresAt format accepted with {resp.status_code}: {resp.text[:200]}"
        )

    def test_expires_at_far_future_accepted(self, base_url, tenant_id, mgmt_headers):
        """expiresAt far in the future must be accepted without error."""
        payload = valid_create_payload(name=f"exp-far-{uuid.uuid4().hex[:6]}")
        payload["expiresAt"] = "9999-12-31T23:59:59"
        resp = requests.post(api_keys_url(base_url, tenant_id), json=payload, headers=mgmt_headers)
        key_id = resp.json().get("id") if resp.status_code == 200 else None
        if key_id:
            soft_delete(base_url, tenant_id, key_id, mgmt_headers)

        assert resp.status_code == 200, (
            f"Far-future expiresAt rejected with {resp.status_code}: {resp.text[:200]}"
        )


# ---------------------------------------------------------------------------
# 17. PATCH expiresAt to past date
# ---------------------------------------------------------------------------

class TestPatchExpiresAtInPast:

    def test_patch_expires_at_to_past_makes_key_immediately_expired(
        self, base_url, tenant_id, mgmt_headers
    ):
        """PATCH {"expiresAt": "<past>"} on an ACTIVE key should make it immediately expired."""
        key = create_key(base_url, tenant_id, mgmt_headers, name=f"patch-exp-past-{uuid.uuid4().hex[:6]}")
        key_id = key["id"]
        secret = key["apiKey"]

        patch = requests.patch(
            api_keys_url(base_url, tenant_id, key_id),
            json={"expiresAt": "2000-01-01T00:00:00"},
            headers=mgmt_headers,
        )

        if patch.status_code not in (200, 204):
            soft_delete(base_url, tenant_id, key_id, mgmt_headers)
            pytest.skip(f"PATCH to past expiresAt returned {patch.status_code} — cannot test auth")

        auth_resp = requests.get(
            f"{base_url}/v3/tenants/{tenant_id}/collections",
            headers={"X-Aware-ApiKey": secret, "X-Aware-AccountId": "0001"},
        )
        soft_delete(base_url, tenant_id, key_id, mgmt_headers)

        assert auth_resp.status_code in (401, 403), (
            f"Key with past expiresAt still authenticated — got {auth_resp.status_code}. "
            "PATCH to past expiresAt must immediately expire the key."
        )


# ---------------------------------------------------------------------------
# 18. PATCH body edge cases
# ---------------------------------------------------------------------------

class TestPatchBodyEdgeCases:

    def test_patch_empty_body_returns_400(self, base_url, tenant_id, mgmt_headers):
        """PATCH with empty body {} must return 400 — spec requires at least one field."""
        key = create_key(base_url, tenant_id, mgmt_headers, name=f"patch-empty-{uuid.uuid4().hex[:6]}")
        key_id = key["id"]

        resp = requests.patch(
            api_keys_url(base_url, tenant_id, key_id),
            json={},
            headers=mgmt_headers,
        )
        soft_delete(base_url, tenant_id, key_id, mgmt_headers)

        assert resp.status_code in (400, 422), (
            f"PATCH with empty body returned {resp.status_code} — "
            f"spec requires at least one of status/expiresAt/clearExpiresAt. Body: {resp.text[:200]}"
        )

    def test_patch_clear_expires_at_false_does_not_clear_expiry(
        self, base_url, tenant_id, mgmt_headers
    ):
        """PATCH {"clearExpiresAt": false} must not remove an existing expiry date."""
        payload = valid_create_payload(name=f"clear-false-{uuid.uuid4().hex[:6]}")
        payload["expiresAt"] = "2030-01-01T00:00:00"
        resp = requests.post(api_keys_url(base_url, tenant_id), json=payload, headers=mgmt_headers)
        assert resp.status_code == 200
        key_id = resp.json()["id"]
        assert resp.json().get("expiresAt") is not None, "expiresAt not set at creation"

        patch = requests.patch(
            api_keys_url(base_url, tenant_id, key_id),
            json={"clearExpiresAt": False},
            headers=mgmt_headers,
        )
        soft_delete(base_url, tenant_id, key_id, mgmt_headers)

        if patch.status_code in (400, 422):
            return  # Treating false as no-op/invalid is also acceptable

        assert patch.status_code in (200, 204), (
            f"PATCH clearExpiresAt:false returned {patch.status_code}: {patch.text[:200]}"
        )
        assert patch.json().get("expiresAt") is not None, (
            "expiresAt was cleared by clearExpiresAt:false — must only clear when true"
        )

    def test_patch_expires_at_and_clear_expires_at_true_together(
        self, base_url, tenant_id, mgmt_headers
    ):
        """When both expiresAt and clearExpiresAt:true are sent, clearExpiresAt wins — spec defined."""
        key = create_key(base_url, tenant_id, mgmt_headers, name=f"clear-conflict-{uuid.uuid4().hex[:6]}")
        key_id = key["id"]

        patch = requests.patch(
            api_keys_url(base_url, tenant_id, key_id),
            json={"expiresAt": "2030-01-01T00:00:00", "clearExpiresAt": True},
            headers=mgmt_headers,
        )
        soft_delete(base_url, tenant_id, key_id, mgmt_headers)

        assert patch.status_code in (200, 204), (
            f"PATCH expiresAt+clearExpiresAt:true returned {patch.status_code}: {patch.text[:200]}"
        )
        assert patch.json().get("expiresAt") is None, (
            f"clearExpiresAt:true did not win over expiresAt — "
            f"expiresAt still set: {patch.json().get('expiresAt')}"
        )


# ---------------------------------------------------------------------------
# 19. Rotation security — old secret immediately invalidated
# ---------------------------------------------------------------------------

class TestRotationSecurity:

    def test_old_secret_rejected_after_rotation(self, base_url, tenant_id, mgmt_headers):
        """After rotation the previous secret must be immediately rejected for authentication."""
        key = create_key(base_url, tenant_id, mgmt_headers, name=f"rotate-sec-{uuid.uuid4().hex[:6]}")
        key_id = key["id"]
        old_secret = key["apiKey"]

        # Confirm old secret works before rotation
        pre_auth = requests.get(
            f"{base_url}/v3/tenants/{tenant_id}/collections",
            headers={"X-Aware-ApiKey": old_secret, "X-Aware-AccountId": "0001"},
        )
        assert pre_auth.status_code == 200, "Old secret did not authenticate before rotation"

        # Rotate
        rotate_resp = requests.post(
            api_keys_url(base_url, tenant_id, key_id, sub="rotate-credentials"),
            headers=mgmt_headers,
        )
        assert rotate_resp.status_code == 200
        new_secret = rotate_resp.json().get("apiKey")
        assert new_secret != old_secret, "New secret matches old secret — rotation did not change key"

        # Old secret must now be rejected
        post_auth = requests.get(
            f"{base_url}/v3/tenants/{tenant_id}/collections",
            headers={"X-Aware-ApiKey": old_secret, "X-Aware-AccountId": "0001"},
        )

        # New secret must still work
        new_auth = requests.get(
            f"{base_url}/v3/tenants/{tenant_id}/collections",
            headers={"X-Aware-ApiKey": new_secret, "X-Aware-AccountId": "0001"},
        )

        soft_delete(base_url, tenant_id, key_id, mgmt_headers)

        assert post_auth.status_code in (401, 403), (
            f"Old secret still authenticates after rotation — got {post_auth.status_code}. "
            "Previous secret must be immediately invalidated."
        )
        assert new_auth.status_code == 200, (
            f"New secret failed to authenticate after rotation — got {new_auth.status_code}."
        )


# ---------------------------------------------------------------------------
# 20. Additional input validation
# ---------------------------------------------------------------------------

class TestAdditionalInputValidation:

    def test_invalid_visibility_value_returns_400(self, base_url, tenant_id, mgmt_headers):
        """visibility field only accepts PERSONAL or ORGANIZATION — any other value must return 400."""
        resp = requests.post(
            api_keys_url(base_url, tenant_id),
            json={
                "keyName": f"inv-vis-{uuid.uuid4().hex[:6]}",
                "visibility": "INVALID",
            },
            headers=mgmt_headers,
        )
        key_id = resp.json().get("id") if resp.status_code == 200 else None
        if key_id:
            soft_delete(base_url, tenant_id, key_id, mgmt_headers)

        assert resp.status_code in (400, 422), (
            f"Invalid visibility value accepted with {resp.status_code}: {resp.text[:200]}"
        )

    @pytest.mark.parametrize("name,label", [
        ("  leading-trailing  ", "whitespace_padded"),
        (" ", "whitespace_only_single"),
    ])
    def test_keyname_whitespace_handling(self, base_url, tenant_id, mgmt_headers, name, label):
        """keyName with leading/trailing whitespace — document whether trimmed, rejected, or stored as-is."""
        resp = requests.post(
            api_keys_url(base_url, tenant_id),
            json={"keyName": name, "visibility": "ORGANIZATION"},
            headers=mgmt_headers,
        )
        key_id = resp.json().get("id") if resp.status_code == 200 else None

        if resp.status_code == 200:
            stored = resp.json().get("keyName")
            if key_id:
                soft_delete(base_url, tenant_id, key_id, mgmt_headers)
            # If accepted, document whether it was trimmed or stored verbatim
            # Either outcome is acceptable — this test documents behavior
            assert stored is not None, f"keyName missing from response for {label}"
        else:
            assert resp.status_code in (400, 422), (
                f"Unexpected status {resp.status_code} for {label}: {resp.text[:200]}"
            )

    @pytest.mark.parametrize("payload,label", [
        ("'; DROP TABLE api_keys; --", "sql_injection"),
        ("<script>alert(1)</script>", "xss_html"),
        ("{{7*7}}", "ssti_template"),
    ])
    def test_injection_in_description_stored_safely(
        self, base_url, tenant_id, mgmt_headers, payload, label
    ):
        """Injection payloads in description must be stored as literal strings or rejected."""
        resp = requests.post(
            api_keys_url(base_url, tenant_id),
            json={
                "keyName": f"desc-inject-{uuid.uuid4().hex[:6]}",
                "description": payload,
                "visibility": "ORGANIZATION",
            },
            headers=mgmt_headers,
        )
        key_id = resp.json().get("id") if resp.status_code == 200 else None

        if resp.status_code == 200:
            stored = resp.json().get("description")
            if key_id:
                soft_delete(base_url, tenant_id, key_id, mgmt_headers)
            assert stored == payload, (
                f"Description {label} not stored verbatim — "
                f"input={payload!r}, stored={stored!r}"
            )
        else:
            if key_id:
                soft_delete(base_url, tenant_id, key_id, mgmt_headers)
            assert resp.status_code in (400, 422), (
                f"Unexpected status {resp.status_code} for description {label}"
            )

    def test_malformed_api_key_header_short(self, base_url, tenant_id):
        """X-Aware-ApiKey of 1 character must return 401, not crash."""
        resp = requests.get(
            f"{base_url}/v3/tenants/{tenant_id}/collections",
            headers={"X-Aware-ApiKey": "x", "X-Aware-AccountId": "0001"},
        )
        assert resp.status_code in (401, 403), (
            f"1-char API key returned {resp.status_code} — expected 401/403"
        )

    def test_malformed_api_key_header_very_long(self, base_url, tenant_id):
        """X-Aware-ApiKey of 10,000 characters must return 401, not crash with 500."""
        resp = requests.get(
            f"{base_url}/v3/tenants/{tenant_id}/collections",
            headers={"X-Aware-ApiKey": "a" * 10000, "X-Aware-AccountId": "0001"},
        )
        assert resp.status_code != 500, (
            f"10,000-char API key header crashed with 500: {resp.text[:200]}"
        )
        assert resp.status_code in (400, 401, 403), (
            f"10,000-char API key returned unexpected {resp.status_code}"
        )


# ---------------------------------------------------------------------------
# 21. List pagination edge cases
# ---------------------------------------------------------------------------

class TestListPaginationEdgeCases:

    def test_page_beyond_total_returns_empty_list(self, base_url, tenant_id, mgmt_headers):
        """Requesting a page number beyond the last page must return an empty content array, not an error."""
        resp = requests.get(
            api_keys_url(base_url, tenant_id),
            params={"page": 99999, "size": 20},
            headers=mgmt_headers,
        )
        assert resp.status_code == 200, (
            f"page=99999 returned {resp.status_code}: {resp.text[:200]}"
        )
        assert resp.json().get("content") == [], (
            f"page=99999 did not return empty content: {resp.json().get('content')}"
        )

    def test_size_one_returns_single_result(self, base_url, tenant_id, mgmt_headers):
        """size=1 must return exactly one key and a valid pagination envelope."""
        resp = requests.get(
            api_keys_url(base_url, tenant_id),
            params={"page": 0, "size": 1},
            headers=mgmt_headers,
        )
        assert resp.status_code == 200, (
            f"size=1 returned {resp.status_code}: {resp.text[:200]}"
        )
        content = resp.json().get("content", [])
        assert len(content) <= 1, f"size=1 returned {len(content)} results"
        assert resp.json().get("size") == 1

    def test_multiple_sort_params_do_not_crash(self, base_url, tenant_id, mgmt_headers):
        """Multiple sort params (Spring Data format) must not crash with 500."""
        resp = requests.get(
            api_keys_url(base_url, tenant_id),
            params=[("sort", "createdAt,desc"), ("sort", "status,asc")],
            headers=mgmt_headers,
        )
        assert resp.status_code != 500, (
            f"Multiple sort params crashed with 500: {resp.text[:200]}"
        )


# ---------------------------------------------------------------------------
# 22. Security misc
# ---------------------------------------------------------------------------

class TestSecurityMisc:

    def test_api_key_in_query_param_not_accepted(self, base_url, tenant_id, mgmt_headers):
        """API key passed as query param instead of header must not authenticate."""
        key = create_key(base_url, tenant_id, mgmt_headers, name=f"queryparam-{uuid.uuid4().hex[:6]}")
        key_id = key["id"]
        secret = key["apiKey"]

        resp = requests.get(
            f"{base_url}/v3/tenants/{tenant_id}/collections",
            params={"X-Aware-ApiKey": secret},
            headers={"X-Aware-AccountId": "0001"},
        )
        soft_delete(base_url, tenant_id, key_id, mgmt_headers)

        assert resp.status_code in (401, 403), (
            f"API key in query param was accepted — got {resp.status_code}. "
            "Key must only be accepted via X-Aware-ApiKey header."
        )

    def test_cross_tenant_patch_returns_403_or_404(
        self, base_url, tenant_id, tenant_id_2, mgmt_headers
    ):
        """PATCH on a key using credentials from a different tenant must return 403 or 404."""
        key = create_key(base_url, tenant_id, mgmt_headers, name=f"xtenant-patch-{uuid.uuid4().hex[:6]}")
        key_id = key["id"]

        resp = requests.patch(
            api_keys_url(base_url, tenant_id_2, key_id),
            json={"status": "INACTIVE"},
            headers=mgmt_headers,
        )
        soft_delete(base_url, tenant_id, key_id, mgmt_headers)

        assert resp.status_code in (403, 404), (
            f"Cross-tenant PATCH returned {resp.status_code} — "
            f"expected 403/404. Body: {resp.text[:200]}"
        )
