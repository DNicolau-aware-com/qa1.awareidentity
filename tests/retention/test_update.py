"""
Tests for PUT /v3/tenants/{tenantId}/data-retention-policy

All state-modifying tests use the `current_policy` fixture so the tenant's
policy is restored on teardown.  Tests that need boundary values use the
`system_ceilings` session fixture to stay environment-agnostic.
"""

import requests

from tests.retention.conftest import retention_url

_CATEGORIES = ("templates", "enrollmentImages", "logs")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _strip_server_fields(policy):
    """Remove read-only fields before using as a PUT body."""
    return {k: v for k, v in policy.items() if k != "systemMaxRetentionDays"}


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

class TestUpdateHappyPath:

    def test_put_returns_200(self, base_url, auth_headers, tenant_id, current_policy):
        """PUT with the existing policy echoed back returns 200."""
        payload = _strip_server_fields(current_policy)
        resp = requests.put(retention_url(base_url, tenant_id), json=payload, headers=auth_headers)
        assert resp.status_code == 200

    def test_put_response_is_json(self, base_url, auth_headers, tenant_id, current_policy):
        """PUT response has Content-Type application/json."""
        payload = _strip_server_fields(current_policy)
        resp = requests.put(retention_url(base_url, tenant_id), json=payload, headers=auth_headers)
        assert "application/json" in resp.headers.get("Content-Type", "")

    def test_put_response_contains_all_three_categories(self, base_url, auth_headers, tenant_id, current_policy):
        """PUT response body contains templates, enrollmentImages, and logs."""
        payload = _strip_server_fields(current_policy)
        body = requests.put(retention_url(base_url, tenant_id), json=payload, headers=auth_headers).json()
        for cat in _CATEGORIES:
            assert cat in body, f"PUT response missing category: {cat}"

    def test_put_response_contains_system_max_retention_days(self, base_url, auth_headers, tenant_id, current_policy):
        """PUT response includes systemMaxRetentionDays even though it was not in the request body."""
        payload = _strip_server_fields(current_policy)
        body = requests.put(retention_url(base_url, tenant_id), json=payload, headers=auth_headers).json()
        assert "systemMaxRetentionDays" in body

    def test_put_toggles_salt_logs_flag(self, base_url, auth_headers, tenant_id, current_policy):
        """PUT with saltLogsToRemovePii toggled persists the new value."""
        payload = _strip_server_fields(current_policy)
        original = payload["saltLogsToRemovePii"]
        payload["saltLogsToRemovePii"] = not original
        body = requests.put(retention_url(base_url, tenant_id), json=payload, headers=auth_headers).json()
        assert body["saltLogsToRemovePii"] == (not original)

    def test_auto_delete_for_templates_ignored_on_put(self, base_url, auth_headers, tenant_id, current_policy):
        """autoDeleteExpired is readOnly and ignored on PUT input per spec (auto-delete
        is always enforced, cannot be disabled) — sending the opposite value has no
        effect and the field remains true in the response."""
        payload = _strip_server_fields(current_policy)
        payload["templates"]["autoDeleteExpired"] = False
        body = requests.put(retention_url(base_url, tenant_id), json=payload, headers=auth_headers).json()
        assert body["templates"]["autoDeleteExpired"] is True

    def test_put_changes_max_retention_days(self, base_url, auth_headers, tenant_id, current_policy, system_ceilings):
        """PUT with a different valid maxRetentionDays for logs is reflected in the response."""
        payload = _strip_server_fields(current_policy)
        ceiling = system_ceilings.get("logs", 365)
        current_max = payload["logs"]["maxRetentionDays"]
        # Pick a value different from current that stays ≤ ceiling
        new_max = max(1, current_max - 1) if current_max > 1 else min(current_max + 1, ceiling)
        # Modalities must not exceed the new max
        for mod in payload["logs"]["modalities"]:
            payload["logs"]["modalities"][mod] = min(payload["logs"]["modalities"][mod], new_max)
        payload["logs"]["maxRetentionDays"] = new_max
        body = requests.put(retention_url(base_url, tenant_id), json=payload, headers=auth_headers).json()
        assert body["logs"]["maxRetentionDays"] == new_max

    def test_put_changes_modality_value(self, base_url, auth_headers, tenant_id, current_policy):
        """PUT with a changed modality value for Face in templates persists correctly."""
        payload = _strip_server_fields(current_policy)
        cat_max = payload["templates"]["maxRetentionDays"]
        current_face = payload["templates"]["modalities"].get("Face", 0)
        new_face = max(0, current_face - 1) if current_face > 0 else min(current_face + 1, cat_max)
        payload["templates"]["modalities"]["Face"] = new_face
        body = requests.put(retention_url(base_url, tenant_id), json=payload, headers=auth_headers).json()
        assert body["templates"]["modalities"]["Face"] == new_face


# ---------------------------------------------------------------------------
# Server-managed fields
# ---------------------------------------------------------------------------

class TestPutServerManagedFields:

    def test_system_max_retention_days_not_changed_by_client(self, base_url, auth_headers, tenant_id, current_policy):
        """Including systemMaxRetentionDays in the PUT body is ignored — value stays server-computed."""
        original_ceilings = current_policy["systemMaxRetentionDays"]
        payload = _strip_server_fields(current_policy)
        # Inject a bogus ceiling — server must ignore it
        payload["systemMaxRetentionDays"] = {
            "templates": 9999,
            "enrollmentImages": 9999,
            "logs": 9999,
        }
        body = requests.put(retention_url(base_url, tenant_id), json=payload, headers=auth_headers).json()
        for cat in _CATEGORIES:
            assert body["systemMaxRetentionDays"].get(cat) == original_ceilings.get(cat), \
                f"systemMaxRetentionDays.{cat} was mutated by client"

    def test_system_max_retention_days_in_response_matches_get(self, base_url, auth_headers, tenant_id, current_policy):
        """systemMaxRetentionDays in the PUT response matches the value returned by a GET."""
        payload = _strip_server_fields(current_policy)
        put_body = requests.put(retention_url(base_url, tenant_id), json=payload, headers=auth_headers).json()
        get_body = requests.get(retention_url(base_url, tenant_id), headers=auth_headers).json()
        assert put_body["systemMaxRetentionDays"] == get_body["systemMaxRetentionDays"]


# ---------------------------------------------------------------------------
# Business rules
# ---------------------------------------------------------------------------

class TestPutBusinessRules:

    def test_modality_exceeding_category_max_returns_400(self, base_url, auth_headers, tenant_id, current_policy):
        """A modality value > category maxRetentionDays returns 400 SETTINGS_INVALID."""
        payload = _strip_server_fields(current_policy)
        cat_max = payload["templates"]["maxRetentionDays"]
        payload["templates"]["modalities"]["Face"] = cat_max + 1
        resp = requests.put(retention_url(base_url, tenant_id), json=payload, headers=auth_headers)
        assert resp.status_code == 400

    def test_modality_exceeding_category_max_error_code_is_settings_invalid(
        self, base_url, auth_headers, tenant_id, current_policy
    ):
        """Error code for modality > category max is SETTINGS_INVALID."""
        payload = _strip_server_fields(current_policy)
        cat_max = payload["templates"]["maxRetentionDays"]
        payload["templates"]["modalities"]["Face"] = cat_max + 1
        body = requests.put(retention_url(base_url, tenant_id), json=payload, headers=auth_headers).json()
        assert body.get("error") == "SETTINGS_INVALID"

    def test_category_max_exceeding_system_ceiling_returns_400(
        self, base_url, auth_headers, tenant_id, current_policy, system_ceilings
    ):
        """category maxRetentionDays > system ceiling returns 400 SETTINGS_INVALID."""
        payload = _strip_server_fields(current_policy)
        ceiling = system_ceilings.get("logs", 365)
        payload["logs"]["maxRetentionDays"] = ceiling + 1
        # Push all log modalities to the same value so they don't trigger a different error first
        for mod in payload["logs"]["modalities"]:
            payload["logs"]["modalities"][mod] = ceiling + 1
        resp = requests.put(retention_url(base_url, tenant_id), json=payload, headers=auth_headers)
        assert resp.status_code == 400

    def test_category_max_exceeding_system_ceiling_error_code(
        self, base_url, auth_headers, tenant_id, current_policy, system_ceilings
    ):
        """Error code for category max > system ceiling is SETTINGS_INVALID."""
        payload = _strip_server_fields(current_policy)
        ceiling = system_ceilings.get("logs", 365)
        payload["logs"]["maxRetentionDays"] = ceiling + 1
        for mod in payload["logs"]["modalities"]:
            payload["logs"]["modalities"][mod] = ceiling + 1
        body = requests.put(retention_url(base_url, tenant_id), json=payload, headers=auth_headers).json()
        assert body.get("error") == "SETTINGS_INVALID"

    def test_modality_value_of_zero_is_accepted(self, base_url, auth_headers, tenant_id, current_policy):
        """Modality value of 0 (opt-out) is a valid setting and should be accepted."""
        payload = _strip_server_fields(current_policy)
        payload["templates"]["modalities"]["Face"] = 0
        resp = requests.put(retention_url(base_url, tenant_id), json=payload, headers=auth_headers)
        assert resp.status_code == 200

    def test_category_max_of_one_is_accepted(self, base_url, auth_headers, tenant_id, current_policy):
        """The minimum valid maxRetentionDays is 1 and should be accepted."""
        payload = _strip_server_fields(current_policy)
        # Set logs to minimum; also set modalities to 0 so they don't exceed the category max
        payload["logs"]["maxRetentionDays"] = 1
        for mod in payload["logs"]["modalities"]:
            payload["logs"]["modalities"][mod] = 0
        resp = requests.put(retention_url(base_url, tenant_id), json=payload, headers=auth_headers)
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Validation errors (VALIDATION_FAILED)
# ---------------------------------------------------------------------------

class TestPutValidation:

    def test_missing_templates_returns_400(self, base_url, auth_headers, tenant_id, current_policy):
        """Omitting the templates category returns 400."""
        payload = _strip_server_fields(current_policy)
        del payload["templates"]
        resp = requests.put(retention_url(base_url, tenant_id), json=payload, headers=auth_headers)
        assert resp.status_code == 400

    def test_missing_enrollment_images_returns_400(self, base_url, auth_headers, tenant_id, current_policy):
        """Omitting the enrollmentImages category returns 400."""
        payload = _strip_server_fields(current_policy)
        del payload["enrollmentImages"]
        resp = requests.put(retention_url(base_url, tenant_id), json=payload, headers=auth_headers)
        assert resp.status_code == 400

    def test_missing_logs_returns_400(self, base_url, auth_headers, tenant_id, current_policy):
        """Omitting the logs category returns 400."""
        payload = _strip_server_fields(current_policy)
        del payload["logs"]
        resp = requests.put(retention_url(base_url, tenant_id), json=payload, headers=auth_headers)
        assert resp.status_code == 400

    def test_missing_salt_logs_flag_returns_400(self, base_url, auth_headers, tenant_id, current_policy):
        """Omitting saltLogsToRemovePii returns 400 — it IS in the schema's required list
        (DataRetentionPolicy.required = [templates, enrollmentImages, logs, saltLogsToRemovePii]),
        and the field description states it's required on PUT. Confirmed correct against spec."""
        payload = _strip_server_fields(current_policy)
        del payload["saltLogsToRemovePii"]
        resp = requests.put(retention_url(base_url, tenant_id), json=payload, headers=auth_headers)
        assert resp.status_code == 400

    def test_missing_max_retention_days_in_category_returns_400(
        self, base_url, auth_headers, tenant_id, current_policy
    ):
        """Omitting maxRetentionDays from a category returns 400."""
        payload = _strip_server_fields(current_policy)
        del payload["templates"]["maxRetentionDays"]
        resp = requests.put(retention_url(base_url, tenant_id), json=payload, headers=auth_headers)
        assert resp.status_code == 400

    def test_missing_auto_delete_in_category_is_accepted(self, base_url, auth_headers, tenant_id, current_policy):
        """Omitting autoDeleteExpired from a category returns 200 — the field is readOnly
        and ignored on PUT input, so it isn't required in the request body."""
        payload = _strip_server_fields(current_policy)
        del payload["templates"]["autoDeleteExpired"]
        resp = requests.put(retention_url(base_url, tenant_id), json=payload, headers=auth_headers)
        assert resp.status_code == 200

    def test_missing_modalities_in_category_returns_400(self, base_url, auth_headers, tenant_id, current_policy):
        """Omitting modalities from a category returns 400."""
        payload = _strip_server_fields(current_policy)
        del payload["templates"]["modalities"]
        resp = requests.put(retention_url(base_url, tenant_id), json=payload, headers=auth_headers)
        assert resp.status_code == 400

    def test_max_retention_days_of_zero_returns_400(self, base_url, auth_headers, tenant_id, current_policy):
        """maxRetentionDays of 0 (below minimum of 1) returns 400."""
        payload = _strip_server_fields(current_policy)
        payload["templates"]["maxRetentionDays"] = 0
        resp = requests.put(retention_url(base_url, tenant_id), json=payload, headers=auth_headers)
        assert resp.status_code == 400

    def test_max_retention_days_of_zero_error_code(self, base_url, auth_headers, tenant_id, current_policy):
        """Error code for maxRetentionDays = 0 is VALIDATION_FAILED."""
        payload = _strip_server_fields(current_policy)
        payload["templates"]["maxRetentionDays"] = 0
        body = requests.put(retention_url(base_url, tenant_id), json=payload, headers=auth_headers).json()
        assert body.get("error") == "VALIDATION_FAILED"

    def test_negative_max_retention_days_returns_400(self, base_url, auth_headers, tenant_id, current_policy):
        """Negative maxRetentionDays returns 400."""
        payload = _strip_server_fields(current_policy)
        payload["templates"]["maxRetentionDays"] = -1
        resp = requests.put(retention_url(base_url, tenant_id), json=payload, headers=auth_headers)
        assert resp.status_code == 400

    def test_string_max_retention_days_returns_400(self, base_url, auth_headers, tenant_id, current_policy):
        """String value for maxRetentionDays returns 400.
        [BUG-R1] Server returns 500 (Jackson JSON parse error) instead of 400. MUST FAIL until
        deserialization errors are mapped to 400 VALIDATION_FAILED."""
        payload = _strip_server_fields(current_policy)
        payload["templates"]["maxRetentionDays"] = "thirty"
        resp = requests.put(retention_url(base_url, tenant_id), json=payload, headers=auth_headers)
        assert resp.status_code == 400

    def test_negative_modality_value_returns_400(self, base_url, auth_headers, tenant_id, current_policy):
        """A negative modality value is below the allowed range (0 … category max) and returns 400."""
        payload = _strip_server_fields(current_policy)
        payload["templates"]["modalities"]["Face"] = -1
        resp = requests.put(retention_url(base_url, tenant_id), json=payload, headers=auth_headers)
        assert resp.status_code == 400

    def test_string_modality_value_returns_400(self, base_url, auth_headers, tenant_id, current_policy):
        """A non-integer modality value returns 400 (modalities values are integers).
        [BUG-R1] Server returns 500 (JSON parse error) instead of 400. MUST FAIL until fixed."""
        payload = _strip_server_fields(current_policy)
        payload["templates"]["modalities"]["Face"] = "lots"
        resp = requests.put(retention_url(base_url, tenant_id), json=payload, headers=auth_headers)
        assert resp.status_code == 400

    def test_non_boolean_auto_delete_is_ignored(self, base_url, auth_headers, tenant_id, current_policy):
        """A non-boolean autoDeleteExpired (e.g. "yes") is accepted with 200 — the field
        is ignored on PUT input entirely, so its value/type in the request is irrelevant."""
        payload = _strip_server_fields(current_policy)
        payload["templates"]["autoDeleteExpired"] = "yes"
        resp = requests.put(retention_url(base_url, tenant_id), json=payload, headers=auth_headers)
        assert resp.status_code == 200

    def test_non_boolean_salt_logs_returns_400(self, base_url, auth_headers, tenant_id, current_policy):
        """A non-boolean saltLogsToRemovePii returns 400 (field is typed boolean).
        [BUG-R1] Server returns 500 (JSON parse error) instead of 400. MUST FAIL until fixed."""
        payload = _strip_server_fields(current_policy)
        payload["saltLogsToRemovePii"] = "nope"
        resp = requests.put(retention_url(base_url, tenant_id), json=payload, headers=auth_headers)
        assert resp.status_code == 400

    def test_empty_body_returns_400(self, base_url, auth_headers, tenant_id):
        """Empty JSON object body returns 400 (required categories missing).
        [BUG-R1] Server returns 500 (JSON parse error) instead of 400 VALIDATION_FAILED. MUST FAIL until fixed."""
        resp = requests.put(retention_url(base_url, tenant_id), json={}, headers=auth_headers)
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Atomicity
# ---------------------------------------------------------------------------

class TestPutAtomicity:

    def test_invalid_put_does_not_change_policy(self, base_url, auth_headers, tenant_id, current_policy):
        """A rejected PUT leaves the policy unchanged — no partial writes."""
        payload = _strip_server_fields(current_policy)
        cat_max = payload["templates"]["maxRetentionDays"]
        # Corrupt one modality to trigger a 400
        payload["templates"]["modalities"]["Face"] = cat_max + 100

        before = requests.get(retention_url(base_url, tenant_id), headers=auth_headers).json()
        resp = requests.put(retention_url(base_url, tenant_id), json=payload, headers=auth_headers)
        assert resp.status_code == 400
        after = requests.get(retention_url(base_url, tenant_id), headers=auth_headers).json()

        for cat in _CATEGORIES:
            assert before[cat]["maxRetentionDays"] == after[cat]["maxRetentionDays"], \
                f"{cat}.maxRetentionDays changed after a rejected PUT"
        assert before["saltLogsToRemovePii"] == after["saltLogsToRemovePii"]


# ---------------------------------------------------------------------------
# Error response shape
# ---------------------------------------------------------------------------

class TestPutErrorShape:

    def test_400_response_contains_error_field(self, base_url, auth_headers, tenant_id, current_policy):
        """400 response body contains an 'error' field."""
        payload = _strip_server_fields(current_policy)
        payload["templates"]["maxRetentionDays"] = 0
        body = requests.put(retention_url(base_url, tenant_id), json=payload, headers=auth_headers).json()
        assert "error" in body

    def test_400_response_contains_timestamp(self, base_url, auth_headers, tenant_id, current_policy):
        """400 response body contains a 'timestamp' field."""
        payload = _strip_server_fields(current_policy)
        payload["templates"]["maxRetentionDays"] = 0
        body = requests.put(retention_url(base_url, tenant_id), json=payload, headers=auth_headers).json()
        assert "timestamp" in body

    def test_400_response_contains_message(self, base_url, auth_headers, tenant_id, current_policy):
        """400 response body contains a 'message' field (required by the Error schema)."""
        payload = _strip_server_fields(current_policy)
        payload["templates"]["maxRetentionDays"] = 0
        body = requests.put(retention_url(base_url, tenant_id), json=payload, headers=auth_headers).json()
        assert "message" in body

    def test_400_response_contains_status(self, base_url, auth_headers, tenant_id, current_policy):
        """400 response body contains a 'status' field equal to 400 (required by the Error schema)."""
        payload = _strip_server_fields(current_policy)
        payload["templates"]["maxRetentionDays"] = 0
        body = requests.put(retention_url(base_url, tenant_id), json=payload, headers=auth_headers).json()
        assert body.get("status") == 400

    def test_validation_failed_includes_field_errors(self, base_url, auth_headers, tenant_id, current_policy):
        """A structural VALIDATION_FAILED response includes a per-field fieldErrors object.

        Per the spec's validationFailed example, structural failures populate fieldErrors
        (it is only omitted when null, i.e. for non-structural SETTINGS_INVALID errors)."""
        payload = _strip_server_fields(current_policy)
        payload["templates"]["maxRetentionDays"] = 0
        body = requests.put(retention_url(base_url, tenant_id), json=payload, headers=auth_headers).json()
        assert body.get("error") == "VALIDATION_FAILED"
        assert "fieldErrors" in body and isinstance(body["fieldErrors"], dict)


# ---------------------------------------------------------------------------
# Not found
# ---------------------------------------------------------------------------

class TestPutNotFound:

    def test_unknown_tenant_returns_404(self, base_url, auth_headers):
        """PUT for a well-formed but non-existent tenant UUID returns 404.

        A structurally valid body is sent so the failure is attributable to the unknown
        tenant rather than body validation."""
        from tests.retention.conftest import valid_policy
        fake_id = "00000000-0000-0000-0000-000000000000"
        resp = requests.put(
            retention_url(base_url, fake_id),
            json=valid_policy(),
            headers=auth_headers,
        )
        assert resp.status_code == 404
