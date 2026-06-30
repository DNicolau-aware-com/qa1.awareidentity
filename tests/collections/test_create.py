"""
Tests for POST /v3/tenants/{tenantId}/collections
"""

import uuid
import requests
import pytest

from tests.collections.conftest import collection_url, create_payload


class TestCreateHappyPath:

    def test_returns_201(self, base_url, auth_headers, tenant_id, new_collection):
        """POST returns 201 Created."""
        assert new_collection["id"] is not None

    def test_response_wrapped_in_envelope(self, base_url, auth_headers, tenant_id):
        """Response is wrapped in biometricCollection envelope."""
        resp = requests.post(collection_url(base_url, tenant_id), json=create_payload(), headers=auth_headers)
        assert resp.status_code == 201
        assert "biometricCollection" in resp.json()
        requests.delete(collection_url(base_url, tenant_id, resp.json()["biometricCollection"]["id"]), headers=auth_headers)

    def test_response_contains_required_fields(self, base_url, auth_headers, tenant_id, new_collection):
        """Response contains all required fields per spec."""
        for field in ("id", "tenantId", "name", "storageType", "dedupEnabled", "createdBy", "createdAt", "updatedAt"):
            assert field in new_collection, f"Missing field: {field}"

    def test_id_is_uuid(self, base_url, auth_headers, tenant_id, new_collection):
        """id is a valid UUID."""
        uuid.UUID(new_collection["id"])

    def test_storage_type_matches_request(self, base_url, auth_headers, tenant_id, new_collection):
        """storageType in response matches the value sent in the request (CLOUD)."""
        assert new_collection["storageType"] == "CLOUD"

    def test_tenant_id_matches_path(self, base_url, auth_headers, tenant_id, new_collection):
        """tenantId in response matches the tenantId in the URL path."""
        assert new_collection["tenantId"] == tenant_id

    def test_dedup_enabled_defaults_to_false(self, base_url, auth_headers, tenant_id):
        """dedupEnabled defaults to false when omitted."""
        resp = requests.post(collection_url(base_url, tenant_id), json=create_payload(), headers=auth_headers)
        assert resp.status_code == 201
        c = resp.json()["biometricCollection"]
        assert c["dedupEnabled"] is False
        requests.delete(collection_url(base_url, tenant_id, c["id"]), headers=auth_headers)

    def test_dedup_enabled_true_when_supplied(self, base_url, auth_headers, tenant_id):
        """dedupEnabled is true when explicitly set."""
        resp = requests.post(collection_url(base_url, tenant_id), json=create_payload(dedupEnabled=True), headers=auth_headers)
        assert resp.status_code == 201
        c = resp.json()["biometricCollection"]
        assert c["dedupEnabled"] is True
        requests.delete(collection_url(base_url, tenant_id, c["id"]), headers=auth_headers)

    def test_timestamps_are_integer_milliseconds(self, base_url, auth_headers, tenant_id, new_collection):
        """createdAt and updatedAt are positive integers (epoch ms)."""
        assert isinstance(new_collection["createdAt"], int) and new_collection["createdAt"] > 0
        assert isinstance(new_collection["updatedAt"], int) and new_collection["updatedAt"] > 0

    def test_description_omitted_when_not_supplied(self, base_url, auth_headers, tenant_id, new_collection):
        """description is absent when not provided."""
        assert "description" not in new_collection

    def test_description_present_when_supplied(self, base_url, auth_headers, tenant_id):
        """description is returned when provided."""
        resp = requests.post(collection_url(base_url, tenant_id),
                             json=create_payload(description="My desc"), headers=auth_headers)
        assert resp.status_code == 201
        c = resp.json()["biometricCollection"]
        assert c.get("description") == "My desc"
        requests.delete(collection_url(base_url, tenant_id, c["id"]), headers=auth_headers)

    def test_response_content_type_is_json(self, base_url, auth_headers, tenant_id, new_collection):
        """Response Content-Type is application/json."""
        resp = requests.post(collection_url(base_url, tenant_id), json=create_payload(), headers=auth_headers)
        assert resp.status_code == 201
        assert "application/json" in resp.headers.get("Content-Type", "")
        requests.delete(collection_url(base_url, tenant_id, resp.json()["biometricCollection"]["id"]), headers=auth_headers)


class TestCreateValidation:

    def test_missing_envelope_returns_400(self, base_url, auth_headers, tenant_id):
        """POST without biometricCollection wrapper returns 400."""
        resp = requests.post(collection_url(base_url, tenant_id),
                             json={"name": "x", "storageType": "CLOUD", "createdBy": "x"},
                             headers=auth_headers)
        assert resp.status_code == 400

    def test_empty_body_returns_400(self, base_url, auth_headers, tenant_id):
        """POST with empty body returns 400."""
        resp = requests.post(collection_url(base_url, tenant_id), json={}, headers=auth_headers)
        assert resp.status_code == 400

    def test_missing_name_returns_400(self, base_url, auth_headers, tenant_id):
        """POST without name returns 400 VALIDATION_FAILED."""
        payload = {"biometricCollection": {"storageType": "CLOUD", "createdBy": "test@aware.com"}}
        resp = requests.post(collection_url(base_url, tenant_id), json=payload, headers=auth_headers)
        assert resp.status_code == 400
        assert resp.json().get("error") == "VALIDATION_FAILED"

    def test_blank_name_returns_400(self, base_url, auth_headers, tenant_id):
        """POST with a blank name returns 400 VALIDATION_FAILED."""
        payload = {"biometricCollection": {"name": "   ", "storageType": "CLOUD", "createdBy": "test@aware.com"}}
        resp = requests.post(collection_url(base_url, tenant_id), json=payload, headers=auth_headers)
        assert resp.status_code == 400
        assert resp.json().get("error") == "VALIDATION_FAILED"

    def test_missing_storage_type_returns_400(self, base_url, auth_headers, tenant_id):
        """POST without storageType returns 400 VALIDATION_FAILED."""
        payload = {"biometricCollection": {"name": "Test", "createdBy": "test@aware.com"}}
        resp = requests.post(collection_url(base_url, tenant_id), json=payload, headers=auth_headers)
        assert resp.status_code == 400
        assert resp.json().get("error") == "VALIDATION_FAILED"

    def test_invalid_storage_type_returns_400(self, base_url, auth_headers, tenant_id):
        """POST with an unsupported storageType value returns 400."""
        payload = {"biometricCollection": {"name": "Test", "storageType": "PREMIUM", "createdBy": "test@aware.com"}}
        resp = requests.post(collection_url(base_url, tenant_id), json=payload, headers=auth_headers)
        assert resp.status_code == 400

    def test_missing_created_by_returns_400(self, base_url, auth_headers, tenant_id):
        """POST without createdBy returns 400 VALIDATION_FAILED."""
        payload = {"biometricCollection": {"name": "Test", "storageType": "CLOUD"}}
        resp = requests.post(collection_url(base_url, tenant_id), json=payload, headers=auth_headers)
        assert resp.status_code == 400
        assert resp.json().get("error") == "VALIDATION_FAILED"

    def test_empty_name_returns_400(self, base_url, auth_headers, tenant_id):
        """POST with empty string name returns 400."""
        payload = {"biometricCollection": {"name": "", "storageType": "CLOUD", "createdBy": "test@aware.com"}}
        resp = requests.post(collection_url(base_url, tenant_id), json=payload, headers=auth_headers)
        assert resp.status_code == 400

    def test_empty_created_by_returns_400(self, base_url, auth_headers, tenant_id):
        """POST with empty string createdBy returns 400."""
        payload = {"biometricCollection": {"name": f"test-{uuid.uuid4().hex[:8]}", "storageType": "CLOUD", "createdBy": ""}}
        resp = requests.post(collection_url(base_url, tenant_id), json=payload, headers=auth_headers)
        assert resp.status_code == 400

    def test_validation_error_includes_field_errors(self, base_url, auth_headers, tenant_id):
        """400 VALIDATION_FAILED body includes a fieldErrors map."""
        payload = {"biometricCollection": {"storageType": "CLOUD"}}  # missing name + createdBy
        resp = requests.post(collection_url(base_url, tenant_id), json=payload, headers=auth_headers)
        assert resp.status_code == 400
        body = resp.json()
        assert body.get("error") == "VALIDATION_FAILED"
        assert "fieldErrors" in body

    def test_xss_in_created_by_returns_400(self, base_url, auth_headers, tenant_id):
        """createdBy with an XSS payload is rejected — must match PATTERN_NAME_OR_EMAIL."""
        payload = {"biometricCollection": {
            "name": f"test-{uuid.uuid4().hex[:8]}",
            "storageType": "CLOUD",
            "createdBy": "<script>alert(1)</script>",
        }}
        resp = requests.post(collection_url(base_url, tenant_id), json=payload, headers=auth_headers)
        assert resp.status_code == 400

    def test_symbols_in_created_by_returns_400(self, base_url, auth_headers, tenant_id):
        """createdBy with arbitrary symbols is rejected — must match PATTERN_NAME_OR_EMAIL."""
        payload = {"biometricCollection": {
            "name": f"test-{uuid.uuid4().hex[:8]}",
            "storageType": "CLOUD",
            "createdBy": "user; DROP TABLE tenants;--",
        }}
        resp = requests.post(collection_url(base_url, tenant_id), json=payload, headers=auth_headers)
        assert resp.status_code == 400

    def test_plain_name_in_created_by_is_accepted(self, base_url, auth_headers, tenant_id):
        """createdBy accepts a plain name (no @) per PATTERN_NAME_OR_EMAIL."""
        resp = requests.post(collection_url(base_url, tenant_id),
                             json=create_payload(createdBy="John Smith"), headers=auth_headers)
        assert resp.status_code == 201
        requests.delete(collection_url(base_url, tenant_id, resp.json()["biometricCollection"]["id"]),
                        headers=auth_headers)

    def test_whitespace_only_created_by_returns_400(self, base_url, auth_headers, tenant_id):
        """createdBy with whitespace-only value must be rejected — PATTERN_NAME_OR_EMAIL requires at least one
        letter or digit at the start. May reveal the same root cause as credentials BUG-3 if accepted."""
        payload = {"biometricCollection": {
            "name": f"test-{uuid.uuid4().hex[:8]}",
            "storageType": "CLOUD",
            "createdBy": "   ",
        }}
        resp = requests.post(collection_url(base_url, tenant_id), json=payload, headers=auth_headers)
        assert resp.status_code == 400

    def test_newline_in_created_by_returns_400(self, base_url, auth_headers, tenant_id):
        """[BUG] createdBy containing a newline must be rejected. PATTERN_NAME_OR_EMAIL uses \\s as its
        word-separator token; Java's \\s matches \\n, so "admin\\ninjected" satisfies the regex and is
        accepted. Same root cause as credentials BUG-3. MUST FAIL until the pattern is tightened."""
        payload = {"biometricCollection": {
            "name": f"test-{uuid.uuid4().hex[:8]}",
            "storageType": "CLOUD",
            "createdBy": "admin\ninjected",
        }}
        resp = requests.post(collection_url(base_url, tenant_id), json=payload, headers=auth_headers)
        assert resp.status_code == 400

    def test_tab_in_created_by_returns_400(self, base_url, auth_headers, tenant_id):
        """[BUG] createdBy containing a tab must be rejected. PATTERN_NAME_OR_EMAIL uses \\s as its
        word-separator token; Java's \\s matches \\t, so "admin\\tinjected" satisfies the regex and is
        accepted. Same root cause as credentials BUG-3. MUST FAIL until the pattern is tightened."""
        payload = {"biometricCollection": {
            "name": f"test-{uuid.uuid4().hex[:8]}",
            "storageType": "CLOUD",
            "createdBy": "admin\tinjected",
        }}
        resp = requests.post(collection_url(base_url, tenant_id), json=payload, headers=auth_headers)
        assert resp.status_code == 400


class TestStorageTypeValidation:
    """storageType must be CLOUD or DECENTRALIZED — STANDARD was removed."""

    def test_cloud_storage_type_returns_201(self, base_url, auth_headers, tenant_id):
        """storageType=CLOUD is accepted and returned in the response."""
        resp = requests.post(collection_url(base_url, tenant_id),
                             json=create_payload(storageType="CLOUD"), headers=auth_headers)
        assert resp.status_code == 201
        c = resp.json()["biometricCollection"]
        assert c["storageType"] == "CLOUD"
        requests.delete(collection_url(base_url, tenant_id, c["id"]), headers=auth_headers)

    def test_decentralized_storage_type_returns_201(self, base_url, auth_headers, tenant_id):
        """storageType=DECENTRALIZED is accepted and returned in the response."""
        resp = requests.post(collection_url(base_url, tenant_id),
                             json=create_payload(storageType="DECENTRALIZED"), headers=auth_headers)
        assert resp.status_code == 201
        c = resp.json()["biometricCollection"]
        assert c["storageType"] == "DECENTRALIZED"
        requests.delete(collection_url(base_url, tenant_id, c["id"]), headers=auth_headers)

    def test_standard_storage_type_returns_400(self, base_url, auth_headers, tenant_id):
        """storageType=STANDARD is no longer valid — must return 400 VALIDATION_FAILED."""
        payload = {"biometricCollection": {
            "name": f"test-{uuid.uuid4().hex[:8]}",
            "storageType": "STANDARD",
            "createdBy": "test@aware.com",
        }}
        resp = requests.post(collection_url(base_url, tenant_id), json=payload, headers=auth_headers)
        assert resp.status_code == 400
        assert resp.json().get("error") == "VALIDATION_FAILED"

    def test_lowercase_cloud_returns_400(self, base_url, auth_headers, tenant_id):
        """storageType is case-sensitive — lowercase 'cloud' returns 400."""
        payload = {"biometricCollection": {
            "name": f"test-{uuid.uuid4().hex[:8]}",
            "storageType": "cloud",
            "createdBy": "test@aware.com",
        }}
        resp = requests.post(collection_url(base_url, tenant_id), json=payload, headers=auth_headers)
        assert resp.status_code == 400

    def test_unknown_storage_type_returns_400(self, base_url, auth_headers, tenant_id):
        """An unrecognised storageType value returns 400 VALIDATION_FAILED."""
        payload = {"biometricCollection": {
            "name": f"test-{uuid.uuid4().hex[:8]}",
            "storageType": "PREMIUM",
            "createdBy": "test@aware.com",
        }}
        resp = requests.post(collection_url(base_url, tenant_id), json=payload, headers=auth_headers)
        assert resp.status_code == 400

    def test_missing_storage_type_returns_400(self, base_url, auth_headers, tenant_id):
        """Omitting storageType returns 400 VALIDATION_FAILED."""
        payload = {"biometricCollection": {"name": f"test-{uuid.uuid4().hex[:8]}", "createdBy": "test@aware.com"}}
        resp = requests.post(collection_url(base_url, tenant_id), json=payload, headers=auth_headers)
        assert resp.status_code == 400
        assert resp.json().get("error") == "VALIDATION_FAILED"

    def test_empty_storage_type_returns_400(self, base_url, auth_headers, tenant_id):
        """Empty string storageType returns 400 VALIDATION_FAILED."""
        payload = {"biometricCollection": {
            "name": f"test-{uuid.uuid4().hex[:8]}",
            "storageType": "",
            "createdBy": "test@aware.com",
        }}
        resp = requests.post(collection_url(base_url, tenant_id), json=payload, headers=auth_headers)
        assert resp.status_code == 400


class TestCreateNameBoundaries:

    def test_name_at_255_chars_is_accepted(self, base_url, auth_headers, tenant_id):
        """Name exactly 255 characters long is accepted."""
        name = "a" * 245 + uuid.uuid4().hex[:10]  # 255 chars, unique
        resp = requests.post(collection_url(base_url, tenant_id), json=create_payload(name=name), headers=auth_headers)
        assert resp.status_code == 201
        requests.delete(collection_url(base_url, tenant_id, resp.json()["biometricCollection"]["id"]), headers=auth_headers)

    def test_very_long_name_is_accepted_or_rejected(self, base_url, auth_headers, tenant_id):
        """Name of 300 characters returns 201 (no limit) or 400 (length limit enforced) — not a 500."""
        name = "b" * 290 + uuid.uuid4().hex[:10]  # 300 chars, unique
        resp = requests.post(collection_url(base_url, tenant_id), json=create_payload(name=name), headers=auth_headers)
        assert resp.status_code in (201, 400)
        if resp.status_code == 201:
            requests.delete(collection_url(base_url, tenant_id, resp.json()["biometricCollection"]["id"]), headers=auth_headers)

    def test_unicode_name_is_accepted(self, base_url, auth_headers, tenant_id):
        """Name with Unicode characters (accents, CJK) is stored and returned correctly."""
        name = f"Colección-日本語-{uuid.uuid4().hex[:6]}"
        resp = requests.post(collection_url(base_url, tenant_id), json=create_payload(name=name), headers=auth_headers)
        assert resp.status_code == 201
        c = resp.json()["biometricCollection"]
        assert c["name"] == name
        requests.delete(collection_url(base_url, tenant_id, c["id"]), headers=auth_headers)

    def test_long_description_is_accepted(self, base_url, auth_headers, tenant_id):
        """Description of 1000 characters is stored and returned."""
        desc = "d" * 1000
        resp = requests.post(collection_url(base_url, tenant_id),
                             json=create_payload(description=desc), headers=auth_headers)
        assert resp.status_code == 201
        c = resp.json()["biometricCollection"]
        assert c.get("description") == desc
        requests.delete(collection_url(base_url, tenant_id, c["id"]), headers=auth_headers)


class TestCreateServerManagedFields:
    """Client-supplied server-managed fields must be ignored on POST.

    The API must never allow a caller to inject their own id, tenantId,
    createdAt, updatedAt, or updatedBy. All five must be generated or
    assigned server-side regardless of what the request body contains.
    """

    _FAKE_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    _FAKE_TENANT_ID = "ffffffff-0000-1111-2222-333333333333"
    _FAKE_TS = 1000000000000  # year 2001 — obviously not now

    def _post_with_server_fields(self, base_url, auth_headers, tenant_id):
        payload = {"biometricCollection": {
            "name": f"srv-fields-{uuid.uuid4().hex[:8]}",
            "storageType": "CLOUD",
            "createdBy": "test@aware.com",
            "id": self._FAKE_ID,
            "tenantId": self._FAKE_TENANT_ID,
            "createdAt": self._FAKE_TS,
            "updatedAt": self._FAKE_TS,
            "updatedBy": "attacker@evil.com",
        }}
        resp = requests.post(collection_url(base_url, tenant_id), json=payload, headers=auth_headers)
        assert resp.status_code == 201, f"Setup failed: {resp.text}"
        return resp.json()["biometricCollection"]

    def test_client_id_is_ignored(self, base_url, auth_headers, tenant_id):
        """Client-supplied id is ignored — the server generates a new UUID."""
        c = self._post_with_server_fields(base_url, auth_headers, tenant_id)
        try:
            assert c["id"] != self._FAKE_ID, "Server must not accept a client-supplied id"
            uuid.UUID(c["id"])  # must still be a valid UUID
        finally:
            requests.delete(collection_url(base_url, tenant_id, c["id"]), headers=auth_headers)

    def test_client_tenant_id_is_ignored(self, base_url, auth_headers, tenant_id):
        """Client-supplied tenantId is ignored — the server assigns from the URL path."""
        c = self._post_with_server_fields(base_url, auth_headers, tenant_id)
        try:
            assert c["tenantId"] != self._FAKE_TENANT_ID, "Server must not accept a client-supplied tenantId"
            assert c["tenantId"] == tenant_id, "tenantId must match the URL path tenant"
        finally:
            requests.delete(collection_url(base_url, tenant_id, c["id"]), headers=auth_headers)

    def test_client_created_at_is_ignored(self, base_url, auth_headers, tenant_id):
        """Client-supplied createdAt is ignored — the server sets it to now."""
        c = self._post_with_server_fields(base_url, auth_headers, tenant_id)
        try:
            assert c["createdAt"] != self._FAKE_TS, "Server must not accept a client-supplied createdAt"
            assert c["createdAt"] > self._FAKE_TS, "Server-generated createdAt must be a recent timestamp"
        finally:
            requests.delete(collection_url(base_url, tenant_id, c["id"]), headers=auth_headers)

    def test_client_updated_at_is_ignored(self, base_url, auth_headers, tenant_id):
        """Client-supplied updatedAt is ignored — the server sets it to now."""
        c = self._post_with_server_fields(base_url, auth_headers, tenant_id)
        try:
            assert c["updatedAt"] != self._FAKE_TS, "Server must not accept a client-supplied updatedAt"
            assert c["updatedAt"] > self._FAKE_TS, "Server-generated updatedAt must be a recent timestamp"
        finally:
            requests.delete(collection_url(base_url, tenant_id, c["id"]), headers=auth_headers)

    def test_client_updated_by_is_ignored_on_create(self, base_url, auth_headers, tenant_id):
        """Client-supplied updatedBy is ignored on create — field should be absent."""
        c = self._post_with_server_fields(base_url, auth_headers, tenant_id)
        try:
            assert c.get("updatedBy") != "attacker@evil.com", \
                "Server must not store a client-supplied updatedBy on create"
        finally:
            requests.delete(collection_url(base_url, tenant_id, c["id"]), headers=auth_headers)


class TestCreateConflict:

    def test_duplicate_name_returns_409(self, base_url, auth_headers, tenant_id, new_collection):
        """POST with a name already used by this tenant returns 409 CONFLICT."""
        payload = {"biometricCollection": {
            "name": new_collection["name"],
            "storageType": "CLOUD",
            "createdBy": "test@aware.com",
        }}
        resp = requests.post(collection_url(base_url, tenant_id), json=payload, headers=auth_headers)
        assert resp.status_code == 409
        assert resp.json().get("error") == "CONFLICT"


class TestFailedCreateDoesNotPersist:
    """A failed POST must not leave any collection behind.

    These tests issue a failing POST then list by the attempted name and assert
    zero results — verifying the transaction was fully rolled back.
    """

    def test_validation_failure_does_not_persist(self, base_url, auth_headers, tenant_id):
        """A 400 validation failure creates no collection — list returns 0 results for that name."""
        name = f"ghost-validation-{uuid.uuid4().hex[:8]}"
        payload = {"biometricCollection": {"name": name, "storageType": "CLOUD"}}  # missing createdBy
        resp = requests.post(collection_url(base_url, tenant_id), json=payload, headers=auth_headers)
        assert resp.status_code == 400

        list_resp = requests.get(
            collection_url(base_url, tenant_id),
            params={"name": name},
            headers=auth_headers,
        )
        assert list_resp.status_code == 200
        assert list_resp.json()["totalElements"] == 0, \
            f"Validation-failed POST left a ghost collection named '{name}'"

    def test_duplicate_name_failure_does_not_create_second(self, base_url, auth_headers, tenant_id):
        """A 409 duplicate failure creates no second collection — list returns exactly 1 result."""
        name = f"ghost-duplicate-{uuid.uuid4().hex[:8]}"
        first = requests.post(collection_url(base_url, tenant_id),
                              json=create_payload(name=name), headers=auth_headers)
        assert first.status_code == 201
        first_id = first.json()["biometricCollection"]["id"]
        try:
            dup = requests.post(collection_url(base_url, tenant_id),
                                json=create_payload(name=name), headers=auth_headers)
            assert dup.status_code == 409

            list_resp = requests.get(
                collection_url(base_url, tenant_id),
                params={"name": name},
                headers=auth_headers,
            )
            assert list_resp.status_code == 200
            assert list_resp.json()["totalElements"] == 1, \
                f"Duplicate POST left a second collection: found {list_resp.json()['totalElements']} with name '{name}'"
        finally:
            requests.delete(collection_url(base_url, tenant_id, first_id), headers=auth_headers)


class TestErrorResponseShape:
    """Error responses must carry a machine-readable timestamp."""

    def test_error_response_includes_timestamp(self, base_url, auth_headers, tenant_id):
        """A 400 error body includes a 'timestamp' field."""
        payload = {"biometricCollection": {"storageType": "CLOUD"}}  # missing name + createdBy
        resp = requests.post(collection_url(base_url, tenant_id), json=payload, headers=auth_headers)
        assert resp.status_code == 400
        assert "timestamp" in resp.json(), "Error response must include a 'timestamp' field"

    def test_error_timestamp_is_iso8601(self, base_url, auth_headers, tenant_id):
        """The timestamp field in a 400 error body is a valid ISO-8601 string."""
        from datetime import datetime
        payload = {"biometricCollection": {"storageType": "CLOUD"}}  # missing name + createdBy
        resp = requests.post(collection_url(base_url, tenant_id), json=payload, headers=auth_headers)
        assert resp.status_code == 400
        ts = resp.json().get("timestamp", "")
        assert ts, "timestamp must be non-empty"
        try:
            datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except ValueError:
            assert False, f"timestamp {repr(ts)} is not valid ISO-8601"
