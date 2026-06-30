"""
Tests for the Generic Preferences CRUD API.

Endpoints:
  GET    /v3/tenants/{tenantId}/preferences
  GET    /v3/tenants/{tenantId}/preferences/{key}
  PUT    /v3/tenants/{tenantId}/preferences/{key}              (bulk upsert)
  GET    /v3/tenants/{tenantId}/preferences/{key}/{subKey}
  POST   /v3/tenants/{tenantId}/preferences/{key}/{subKey}     (create, 409 if exists)
  PUT    /v3/tenants/{tenantId}/preferences/{key}/{subKey}     (upsert)
  DELETE /v3/tenants/{tenantId}/preferences/{key}/{subKey}
"""

import uuid

import requests

from tests.tenant_preferences.conftest import preferences_url

_TEST_KEY = "test_suite"
_TEST_SUB_KEY = "test_value"
_BULK_KEY = "test_suite_bulk"


class TestListAllPreferences:

    def test_returns_200(self, base_url, auth_headers, tenant_id):
        """GET all preferences returns 200."""
        resp = requests.get(preferences_url(base_url, tenant_id), headers=auth_headers)
        assert resp.status_code == 200

    def test_response_is_array(self, base_url, auth_headers, tenant_id):
        """GET all preferences returns a JSON array."""
        resp = requests.get(preferences_url(base_url, tenant_id), headers=auth_headers)
        assert isinstance(resp.json(), list)

    def test_each_row_has_required_fields(self, base_url, auth_headers, tenant_id):
        """Every preference row contains the required fields from the spec."""
        rows = requests.get(preferences_url(base_url, tenant_id), headers=auth_headers).json()
        for row in rows:
            for field in ("id", "tenantId", "key", "subKey", "value"):
                assert field in row, f"Row missing field '{field}': {row}"

    def test_tenant_id_matches(self, base_url, auth_headers, tenant_id):
        """Every row's tenantId matches the requested tenant."""
        rows = requests.get(preferences_url(base_url, tenant_id), headers=auth_headers).json()
        for row in rows:
            assert row["tenantId"] == tenant_id


class TestListPreferencesByKey:

    def test_known_key_returns_200(self, base_url, auth_headers, tenant_id):
        """GET preferences for a known key (security_settings) returns 200."""
        resp = requests.get(
            preferences_url(base_url, tenant_id, "security_settings"),
            headers=auth_headers,
        )
        assert resp.status_code == 200

    def test_known_key_returns_array(self, base_url, auth_headers, tenant_id):
        """GET by key returns a JSON array."""
        resp = requests.get(
            preferences_url(base_url, tenant_id, "security_settings"),
            headers=auth_headers,
        )
        assert isinstance(resp.json(), list)

    def test_unknown_key_returns_200_empty_array(self, base_url, auth_headers, tenant_id):
        """GET by unknown key returns 200 with empty array (not 404)."""
        resp = requests.get(
            preferences_url(base_url, tenant_id, "key_that_does_not_exist"),
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json() == []

    def test_rows_share_the_requested_key(self, base_url, auth_headers, tenant_id):
        """All rows returned for a key share that key value."""
        rows = requests.get(
            preferences_url(base_url, tenant_id, "security_settings"),
            headers=auth_headers,
        ).json()
        for row in rows:
            assert row["key"] == "security_settings"


class TestGetSinglePreference:

    def test_existing_preference_returns_200(self, base_url, auth_headers, tenant_id, created_preference):
        """GET an existing (key, subKey) returns 200."""
        resp = requests.get(
            preferences_url(base_url, tenant_id, _TEST_KEY, _TEST_SUB_KEY),
            headers=auth_headers,
        )
        assert resp.status_code == 200

    def test_response_contains_required_fields(self, base_url, auth_headers, tenant_id, created_preference):
        """GET single preference response contains all required fields."""
        row = requests.get(
            preferences_url(base_url, tenant_id, _TEST_KEY, _TEST_SUB_KEY),
            headers=auth_headers,
        ).json()
        for field in ("id", "tenantId", "key", "subKey", "value"):
            assert field in row

    def test_response_key_and_subkey_match(self, base_url, auth_headers, tenant_id, created_preference):
        """GET single preference echoes the correct key and subKey."""
        row = requests.get(
            preferences_url(base_url, tenant_id, _TEST_KEY, _TEST_SUB_KEY),
            headers=auth_headers,
        ).json()
        assert row["key"] == _TEST_KEY
        assert row["subKey"] == _TEST_SUB_KEY

    def test_nonexistent_preference_returns_404(self, base_url, auth_headers, tenant_id):
        """GET a (key, subKey) that does not exist returns 404 NOT_FOUND."""
        resp = requests.get(
            preferences_url(base_url, tenant_id, "no_such_key", "no_such_sub"),
            headers=auth_headers,
        )
        assert resp.status_code == 404

    def test_404_error_code_is_not_found(self, base_url, auth_headers, tenant_id):
        """404 response body contains error code NOT_FOUND."""
        resp = requests.get(
            preferences_url(base_url, tenant_id, "no_such_key", "no_such_sub"),
            headers=auth_headers,
        )
        assert resp.json().get("error") == "NOT_FOUND"


class TestCreatePreference:

    def test_post_returns_201(self, base_url, auth_headers, tenant_id):
        """POST a new preference returns 201 Created."""
        sub_key = f"create_test_{uuid.uuid4().hex[:8]}"
        url = preferences_url(base_url, tenant_id, _TEST_KEY, sub_key)
        resp = requests.post(url, json={"value": "hello", "valueType": "STRING"}, headers=auth_headers)
        assert resp.status_code == 201
        requests.delete(url, headers=auth_headers)

    def test_post_response_contains_stored_value(self, base_url, auth_headers, tenant_id):
        """POST response echoes the value that was stored."""
        sub_key = f"create_val_{uuid.uuid4().hex[:8]}"
        url = preferences_url(base_url, tenant_id, _TEST_KEY, sub_key)
        resp = requests.post(url, json={"value": "my_value", "valueType": "STRING"}, headers=auth_headers)
        assert resp.json().get("value") == "my_value"
        requests.delete(url, headers=auth_headers)

    def test_post_integer_value_type(self, base_url, auth_headers, tenant_id):
        """POST with valueType INTEGER stores the value correctly."""
        sub_key = f"create_int_{uuid.uuid4().hex[:8]}"
        url = preferences_url(base_url, tenant_id, _TEST_KEY, sub_key)
        resp = requests.post(url, json={"value": "42", "valueType": "INTEGER"}, headers=auth_headers)
        assert resp.status_code == 201
        assert resp.json().get("value") == "42"
        assert resp.json().get("valueType") == "INTEGER"
        requests.delete(url, headers=auth_headers)

    def test_post_boolean_value_type(self, base_url, auth_headers, tenant_id):
        """POST with valueType BOOLEAN stores the value correctly."""
        sub_key = f"create_bool_{uuid.uuid4().hex[:8]}"
        url = preferences_url(base_url, tenant_id, _TEST_KEY, sub_key)
        resp = requests.post(url, json={"value": "true", "valueType": "BOOLEAN"}, headers=auth_headers)
        assert resp.status_code == 201
        requests.delete(url, headers=auth_headers)

    def test_duplicate_post_returns_409(self, base_url, auth_headers, tenant_id, created_preference):
        """POST on an already-existing (key, subKey) returns 409 CONFLICT."""
        url = preferences_url(base_url, tenant_id, _TEST_KEY, _TEST_SUB_KEY)
        resp = requests.post(url, json={"value": "duplicate", "valueType": "STRING"}, headers=auth_headers)
        assert resp.status_code == 409

    def test_409_error_code_is_conflict(self, base_url, auth_headers, tenant_id, created_preference):
        """409 response body contains error code CONFLICT."""
        url = preferences_url(base_url, tenant_id, _TEST_KEY, _TEST_SUB_KEY)
        resp = requests.post(url, json={"value": "duplicate", "valueType": "STRING"}, headers=auth_headers)
        assert resp.json().get("error") == "CONFLICT"

    def test_missing_value_returns_400(self, base_url, auth_headers, tenant_id):
        """POST without required 'value' field returns 400 VALIDATION_FAILED."""
        sub_key = f"create_novalue_{uuid.uuid4().hex[:8]}"
        url = preferences_url(base_url, tenant_id, _TEST_KEY, sub_key)
        resp = requests.post(url, json={"valueType": "STRING"}, headers=auth_headers)
        assert resp.status_code == 400

    def test_empty_body_returns_400(self, base_url, auth_headers, tenant_id):
        """POST with empty body returns 400 VALIDATION_FAILED."""
        sub_key = f"create_empty_{uuid.uuid4().hex[:8]}"
        url = preferences_url(base_url, tenant_id, _TEST_KEY, sub_key)
        resp = requests.post(url, json={}, headers=auth_headers)
        assert resp.status_code == 400


class TestUpsertSinglePreference:

    def test_put_creates_when_not_exists(self, base_url, auth_headers, tenant_id):
        """PUT on a non-existent (key, subKey) creates it and returns 200."""
        sub_key = f"upsert_new_{uuid.uuid4().hex[:8]}"
        url = preferences_url(base_url, tenant_id, _TEST_KEY, sub_key)
        resp = requests.put(url, json={"value": "created", "valueType": "STRING"}, headers=auth_headers)
        assert resp.status_code == 200
        requests.delete(url, headers=auth_headers)

    def test_put_updates_when_exists(self, base_url, auth_headers, tenant_id, created_preference):
        """PUT on an existing (key, subKey) updates it and returns 200."""
        url = preferences_url(base_url, tenant_id, _TEST_KEY, _TEST_SUB_KEY)
        resp = requests.put(url, json={"value": "updated_value", "valueType": "STRING"}, headers=auth_headers)
        assert resp.status_code == 200

    def test_put_update_value_is_persisted(self, base_url, auth_headers, tenant_id, created_preference):
        """Updated value is reflected in subsequent GET."""
        url = preferences_url(base_url, tenant_id, _TEST_KEY, _TEST_SUB_KEY)
        requests.put(url, json={"value": "new_value", "valueType": "STRING"}, headers=auth_headers)
        row = requests.get(url, headers=auth_headers).json()
        assert row["value"] == "new_value"

    def test_put_missing_value_returns_400(self, base_url, auth_headers, tenant_id):
        """PUT without required 'value' field returns 400 VALIDATION_FAILED."""
        sub_key = f"upsert_novalue_{uuid.uuid4().hex[:8]}"
        url = preferences_url(base_url, tenant_id, _TEST_KEY, sub_key)
        resp = requests.put(url, json={"valueType": "STRING"}, headers=auth_headers)
        assert resp.status_code == 400


class TestBulkUpsertGroup:

    def test_bulk_put_returns_200(self, base_url, auth_headers, tenant_id):
        """PUT bulk group upsert returns 200."""
        url = preferences_url(base_url, tenant_id, _BULK_KEY)
        payload = [
            {"subKey": "field_one", "value": "val1", "valueType": "STRING"},
            {"subKey": "field_two", "value": "42", "valueType": "INTEGER"},
        ]
        resp = requests.put(url, json=payload, headers=auth_headers)
        assert resp.status_code == 200

    def test_bulk_put_response_is_array(self, base_url, auth_headers, tenant_id):
        """Bulk upsert response is a JSON array of the resulting rows."""
        url = preferences_url(base_url, tenant_id, _BULK_KEY)
        payload = [{"subKey": "field_one", "value": "v", "valueType": "STRING"}]
        resp = requests.put(url, json=payload, headers=auth_headers)
        assert isinstance(resp.json(), list)

    def test_bulk_put_all_rows_persisted(self, base_url, auth_headers, tenant_id):
        """All sub-keys sent in bulk upsert are returned in the response."""
        url = preferences_url(base_url, tenant_id, _BULK_KEY)
        payload = [
            {"subKey": "bulk_a", "value": "aaa", "valueType": "STRING"},
            {"subKey": "bulk_b", "value": "bbb", "valueType": "STRING"},
        ]
        resp = requests.put(url, json=payload, headers=auth_headers)
        sub_keys = {r["subKey"] for r in resp.json()}
        assert "bulk_a" in sub_keys
        assert "bulk_b" in sub_keys

    def test_bulk_put_missing_subkey_returns_400(self, base_url, auth_headers, tenant_id):
        """Bulk upsert entry missing required 'subKey' returns 400."""
        url = preferences_url(base_url, tenant_id, _BULK_KEY)
        payload = [{"value": "no_subkey", "valueType": "STRING"}]
        resp = requests.put(url, json=payload, headers=auth_headers)
        assert resp.status_code == 400

    def test_bulk_put_missing_value_returns_400(self, base_url, auth_headers, tenant_id):
        """Bulk upsert entry missing required 'value' returns 400."""
        url = preferences_url(base_url, tenant_id, _BULK_KEY)
        payload = [{"subKey": "no_value", "valueType": "STRING"}]
        resp = requests.put(url, json=payload, headers=auth_headers)
        assert resp.status_code == 400


class TestDeletePreference:

    def test_delete_returns_204(self, base_url, auth_headers, tenant_id):
        """DELETE an existing preference returns 204 No Content."""
        sub_key = f"delete_me_{uuid.uuid4().hex[:8]}"
        url = preferences_url(base_url, tenant_id, _TEST_KEY, sub_key)
        requests.put(url, json={"value": "to_delete", "valueType": "STRING"}, headers=auth_headers)
        resp = requests.delete(url, headers=auth_headers)
        assert resp.status_code == 204

    def test_deleted_preference_returns_404_on_get(self, base_url, auth_headers, tenant_id):
        """After DELETE, GET the same (key, subKey) returns 404."""
        sub_key = f"delete_get_{uuid.uuid4().hex[:8]}"
        url = preferences_url(base_url, tenant_id, _TEST_KEY, sub_key)
        requests.put(url, json={"value": "to_delete", "valueType": "STRING"}, headers=auth_headers)
        requests.delete(url, headers=auth_headers)
        resp = requests.get(url, headers=auth_headers)
        assert resp.status_code == 404


class TestPreferenceLifecycle:

    def test_full_crud_lifecycle(self, base_url, auth_headers, tenant_id):
        """Full lifecycle: POST → GET → PUT → GET (updated) → DELETE → GET (404)."""
        sub_key = f"lifecycle_{uuid.uuid4().hex[:8]}"
        url = preferences_url(base_url, tenant_id, _TEST_KEY, sub_key)

        # CREATE
        r = requests.post(url, json={"value": "v1", "valueType": "STRING"}, headers=auth_headers)
        assert r.status_code == 201
        assert r.json()["value"] == "v1"

        # READ
        r = requests.get(url, headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["value"] == "v1"

        # UPDATE
        r = requests.put(url, json={"value": "v2", "valueType": "STRING"}, headers=auth_headers)
        assert r.status_code == 200

        # READ updated
        r = requests.get(url, headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["value"] == "v2"

        # DELETE
        r = requests.delete(url, headers=auth_headers)
        assert r.status_code == 204

        # READ deleted
        r = requests.get(url, headers=auth_headers)
        assert r.status_code == 404


class TestValueValidation:
    """Edge cases for the value and valueType fields."""

    def test_value_5000_chars_is_accepted(self, base_url, auth_headers, tenant_id):
        """Value of 5000 chars is accepted — no server-side length cap documented.
        Flagged for DB column overflow risk; behaviour recorded here as a baseline."""
        sub_key = f"long_val_{uuid.uuid4().hex[:8]}"
        url = preferences_url(base_url, tenant_id, _TEST_KEY, sub_key)
        resp = requests.post(url, json={"value": "x" * 5000, "valueType": "STRING"}, headers=auth_headers)
        assert resp.status_code == 201
        requests.delete(url, headers=auth_headers)

    def test_valuetype_json_with_invalid_json_returns_400(self, base_url, auth_headers, tenant_id):
        """valueType=JSON with a non-JSON string should return 400.
        [BUG] Currently returns 201 — invalid JSON stored verbatim with type JSON."""
        sub_key = f"json_bad_{uuid.uuid4().hex[:8]}"
        url = preferences_url(base_url, tenant_id, _TEST_KEY, sub_key)
        resp = requests.post(url, json={"value": "not-valid-json", "valueType": "JSON"}, headers=auth_headers)
        assert resp.status_code == 400

    def test_valuetype_json_with_valid_json_returns_201(self, base_url, auth_headers, tenant_id):
        """Control: valueType=JSON with valid JSON string returns 201."""
        sub_key = f"json_ok_{uuid.uuid4().hex[:8]}"
        url = preferences_url(base_url, tenant_id, _TEST_KEY, sub_key)
        resp = requests.post(url, json={"value": '{"key": "value"}', "valueType": "JSON"}, headers=auth_headers)
        assert resp.status_code == 201
        requests.delete(url, headers=auth_headers)

    def test_invalid_valuetype_returns_400(self, base_url, auth_headers, tenant_id):
        """valueType not in [STRING, INTEGER, BOOLEAN, JSON] returns 400."""
        sub_key = f"vtype_{uuid.uuid4().hex[:8]}"
        url = preferences_url(base_url, tenant_id, _TEST_KEY, sub_key)
        resp = requests.post(url, json={"value": "1.5", "valueType": "FLOAT"}, headers=auth_headers)
        assert resp.status_code == 400

    def test_missing_valuetype_is_accepted(self, base_url, auth_headers, tenant_id):
        """valueType is optional per spec — omitting it returns 201."""
        sub_key = f"novtype_{uuid.uuid4().hex[:8]}"
        url = preferences_url(base_url, tenant_id, _TEST_KEY, sub_key)
        resp = requests.post(url, json={"value": "hello"}, headers=auth_headers)
        assert resp.status_code == 201
        requests.delete(url, headers=auth_headers)


class TestBulkUpsertEdgeCases:
    """Edge cases specific to the bulk PUT /preferences/{key} endpoint."""

    def test_bulk_empty_array_returns_200(self, base_url, auth_headers, tenant_id):
        """PUT with empty array [] returns 200 with empty array (no-op)."""
        url = preferences_url(base_url, tenant_id, _BULK_KEY)
        resp = requests.put(url, json=[], headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_bulk_duplicate_subkeys_returns_400_or_deduplicates(
        self, base_url, auth_headers, tenant_id
    ):
        """Duplicate subKey entries in the same bulk request should either return
        400 (reject the request) or deduplicate (last-write-wins, 1 row stored).
        [BUG] Currently stores 2 rows with the same subKey — violates the
        (tenantId, key, subKey) uniqueness invariant."""
        url = preferences_url(base_url, tenant_id, _BULK_KEY)
        payload = [
            {"subKey": "dup_test", "value": "first", "valueType": "STRING"},
            {"subKey": "dup_test", "value": "second", "valueType": "STRING"},
        ]
        resp = requests.put(url, json=payload, headers=auth_headers)
        if resp.status_code == 400:
            return
        assert resp.status_code == 200
        dup_rows = [r for r in resp.json() if r["subKey"] == "dup_test"]
        assert len(dup_rows) == 1, (
            f"Expected 1 row for subKey 'dup_test', got {len(dup_rows)} — "
            "duplicate subKeys stored, violating uniqueness invariant [BUG]"
        )
        requests.delete(preferences_url(base_url, tenant_id, _BULK_KEY, "dup_test"), headers=auth_headers)

    def test_bulk_one_invalid_entry_rejects_whole_batch(self, base_url, auth_headers, tenant_id):
        """A single invalid subKey in a bulk request rejects the whole batch with 400."""
        url = preferences_url(base_url, tenant_id, _BULK_KEY)
        payload = [
            {"subKey": "valid_entry", "value": "ok", "valueType": "STRING"},
            {"subKey": "invalid key!", "value": "bad", "valueType": "STRING"},
        ]
        resp = requests.put(url, json=payload, headers=auth_headers)
        assert resp.status_code == 400
        get_resp = requests.get(
            preferences_url(base_url, tenant_id, _BULK_KEY, "valid_entry"),
            headers=auth_headers,
        )
        assert get_resp.status_code == 404, "Valid entry should not have been stored (atomicity)"


class TestDeleteEdgeCases:

    def test_delete_nonexistent_returns_404(self, base_url, auth_headers, tenant_id):
        """DELETE a (key, subKey) that does not exist returns 404 NOT_FOUND."""
        resp = requests.delete(
            preferences_url(base_url, tenant_id, "no_such_key", "no_such_sub"),
            headers=auth_headers,
        )
        assert resp.status_code == 404

    def test_post_after_delete_returns_201(self, base_url, auth_headers, tenant_id):
        """POST on a previously deleted (key, subKey) returns 201 (not 409)."""
        sub_key = f"redel_{uuid.uuid4().hex[:8]}"
        url = preferences_url(base_url, tenant_id, _TEST_KEY, sub_key)
        requests.post(url, json={"value": "v1", "valueType": "STRING"}, headers=auth_headers)
        requests.delete(url, headers=auth_headers)
        resp = requests.post(url, json={"value": "v2", "valueType": "STRING"}, headers=auth_headers)
        assert resp.status_code == 201
        assert resp.json()["value"] == "v2"
        requests.delete(url, headers=auth_headers)


class TestPreferenceAuth:

    def test_no_api_key_returns_401(self, base_url, tenant_id):
        """GET without any auth headers returns 401."""
        resp = requests.get(preferences_url(base_url, tenant_id))
        assert resp.status_code == 401

    def test_invalid_api_key_returns_403(self, base_url, bad_auth_headers, tenant_id):
        """GET with an invalid API key returns 403."""
        resp = requests.get(preferences_url(base_url, tenant_id), headers=bad_auth_headers)
        assert resp.status_code == 403

    def test_non_uuid_tenant_id_returns_400(self, base_url, auth_headers):
        """Non-UUID tenantId returns 400 (not 500). [BUG-R3 family]"""
        url = f"{base_url}/v3/tenants/not-a-uuid/preferences"
        resp = requests.get(url, headers=auth_headers)
        assert resp.status_code == 400
