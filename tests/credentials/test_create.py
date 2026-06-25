"""
Tests for POST /v3/tenants/{tenantId}/collections/{collectionId}/credentials
"""

import uuid
import datetime
import requests

from tests.credentials.conftest import credential_url, create_credential_payload, _DUMMY_IMAGE_B64


class TestCreateHappyPath:

    def test_returns_201(self, base_url, auth_headers, tenant_id, collection_id, new_credential):
        """POST returns 201 Created."""
        assert new_credential["id"] is not None

    def test_response_wrapped_in_envelope(self, base_url, auth_headers, tenant_id, collection_id):
        """Response is wrapped in biometricCredential envelope."""
        resp = requests.post(
            credential_url(base_url, tenant_id, collection_id),
            json=create_credential_payload(),
            headers=auth_headers,
        )
        assert resp.status_code == 201
        assert "biometricCredential" in resp.json()
        requests.delete(
            credential_url(base_url, tenant_id, collection_id, resp.json()["biometricCredential"]["id"]),
            headers=auth_headers,
        )

    def test_response_contains_required_fields(self, base_url, auth_headers, tenant_id, collection_id, new_credential):
        """Response contains id, collectionId, externalUserId, status, biometrics, createdAt, updatedAt."""
        for field in ("id", "collectionId", "externalUserId", "status", "biometrics", "createdBy", "createdAt", "updatedAt"):
            assert field in new_credential, f"Missing field: {field}"

    def test_id_is_uuid(self, base_url, auth_headers, tenant_id, collection_id, new_credential):
        """id is a valid UUID."""
        uuid.UUID(new_credential["id"])

    def test_collection_id_matches_path(self, base_url, auth_headers, tenant_id, collection_id, new_credential):
        """collectionId in response matches the collectionId in the URL path."""
        assert new_credential["collectionId"] == collection_id

    def test_external_user_id_is_stored(self, base_url, auth_headers, tenant_id, collection_id, new_credential):
        """externalUserId in response matches what was supplied in the request."""
        assert new_credential["externalUserId"] is not None

    def test_status_is_active_on_creation(self, base_url, auth_headers, tenant_id, collection_id, new_credential):
        """status defaults to ACTIVE on creation."""
        assert new_credential["status"] == "ACTIVE"

    def test_biometrics_is_dict(self, base_url, auth_headers, tenant_id, collection_id, new_credential):
        """biometrics is a dict (modality → entries), not a list."""
        assert isinstance(new_credential["biometrics"], dict)

    def test_data_not_echoed_in_response(self, base_url, auth_headers, tenant_id, collection_id):
        """data field is write-only: entries in POST response must not contain 'data'."""
        resp = requests.post(
            credential_url(base_url, tenant_id, collection_id),
            json=create_credential_payload(),
            headers=auth_headers,
        )
        assert resp.status_code == 201
        cred = resp.json()["biometricCredential"]
        for entries in cred.get("biometrics", {}).values():
            for entry in entries:
                assert "data" not in entry
        requests.delete(credential_url(base_url, tenant_id, collection_id, cred["id"]), headers=auth_headers)

    def test_timestamps_are_integer_milliseconds(self, base_url, auth_headers, tenant_id, collection_id, new_credential):
        """createdAt and updatedAt are positive integers (epoch ms)."""
        assert isinstance(new_credential["createdAt"], int) and new_credential["createdAt"] > 0
        assert isinstance(new_credential["updatedAt"], int) and new_credential["updatedAt"] > 0

    def test_response_content_type_is_json(self, base_url, auth_headers, tenant_id, collection_id):
        """Response Content-Type is application/json."""
        resp = requests.post(
            credential_url(base_url, tenant_id, collection_id),
            json=create_credential_payload(),
            headers=auth_headers,
        )
        assert resp.status_code == 201
        assert "application/json" in resp.headers.get("Content-Type", "")
        requests.delete(
            credential_url(base_url, tenant_id, collection_id, resp.json()["biometricCredential"]["id"]),
            headers=auth_headers,
        )

    def test_created_by_is_optional(self, base_url, auth_headers, tenant_id, collection_id):
        """POST without createdBy succeeds — createdBy is optional per spec."""
        payload = {"biometricCredential": {"externalUserId": f"user-{uuid.uuid4().hex[:8]}", "biometrics": {}}}
        resp = requests.post(credential_url(base_url, tenant_id, collection_id), json=payload, headers=auth_headers)
        assert resp.status_code == 201
        requests.delete(
            credential_url(base_url, tenant_id, collection_id, resp.json()["biometricCredential"]["id"]),
            headers=auth_headers,
        )


class TestCreateCorrelationId:

    def test_correlation_id_is_echoed(self, base_url, auth_headers, tenant_id, collection_id):
        """correlationId supplied on POST is echoed back in the response."""
        corr = f"corr-{uuid.uuid4().hex[:8]}"
        payload = create_credential_payload(correlationId=corr)
        resp = requests.post(credential_url(base_url, tenant_id, collection_id), json=payload, headers=auth_headers)
        assert resp.status_code == 201
        cred = resp.json()["biometricCredential"]
        try:
            assert cred.get("correlationId") == corr
        finally:
            requests.delete(credential_url(base_url, tenant_id, collection_id, cred["id"]), headers=auth_headers)

    def test_correlation_id_omitted_when_not_supplied(self, base_url, auth_headers, tenant_id, collection_id):
        """correlationId is omitted from the response when not supplied (spec: omitted when null)."""
        payload = {"biometricCredential": {"externalUserId": f"user-{uuid.uuid4().hex[:8]}", "biometrics": {}}}
        resp = requests.post(credential_url(base_url, tenant_id, collection_id), json=payload, headers=auth_headers)
        assert resp.status_code == 201
        cred = resp.json()["biometricCredential"]
        try:
            assert "correlationId" not in cred, \
                f"correlationId must be absent when not supplied, got {cred.get('correlationId')!r}"
        finally:
            requests.delete(credential_url(base_url, tenant_id, collection_id, cred["id"]), headers=auth_headers)

    def test_correlation_id_null_omitted_from_response(self, base_url, auth_headers, tenant_id, collection_id):
        """Explicitly supplying correlationId:null is treated as absent — field omitted from response."""
        payload = {"biometricCredential": {
            "externalUserId": f"user-{uuid.uuid4().hex[:8]}",
            "biometrics": {},
            "correlationId": None,
        }}
        resp = requests.post(credential_url(base_url, tenant_id, collection_id), json=payload, headers=auth_headers)
        assert resp.status_code == 201
        cred = resp.json()["biometricCredential"]
        try:
            assert "correlationId" not in cred, \
                f"correlationId must be absent when explicitly null, got {cred.get('correlationId')!r}"
        finally:
            requests.delete(credential_url(base_url, tenant_id, collection_id, cred["id"]), headers=auth_headers)


class TestCreateCreatedByValidation:
    """createdBy must be a plain name or email (PATTERN_NAME_OR_EMAIL) if supplied."""

    def test_plain_name_accepted(self, base_url, auth_headers, tenant_id, collection_id):
        """A plain name in createdBy is accepted."""
        payload = create_credential_payload(createdBy="Jane Doe")
        resp = requests.post(credential_url(base_url, tenant_id, collection_id), json=payload, headers=auth_headers)
        assert resp.status_code == 201
        requests.delete(
            credential_url(base_url, tenant_id, collection_id, resp.json()["biometricCredential"]["id"]),
            headers=auth_headers,
        )

    def test_xss_in_created_by_returns_400(self, base_url, auth_headers, tenant_id, collection_id):
        """An XSS payload in createdBy is rejected with 400."""
        payload = create_credential_payload(createdBy="<script>alert(1)</script>")
        resp = requests.post(credential_url(base_url, tenant_id, collection_id), json=payload, headers=auth_headers)
        assert resp.status_code == 400

    def test_symbols_in_created_by_returns_400(self, base_url, auth_headers, tenant_id, collection_id):
        """Disallowed symbols in createdBy are rejected with 400."""
        payload = create_credential_payload(createdBy="robert');DROP TABLE--")
        resp = requests.post(credential_url(base_url, tenant_id, collection_id), json=payload, headers=auth_headers)
        assert resp.status_code == 400

    # ------------------------------------------------------------------
    # Blank / control-character createdBy → 400
    # [BUG TICKET 4] Values below currently return 201 — MUST FAIL until fixed.
    # ------------------------------------------------------------------

    def test_blank_created_by_returns_400(self, base_url, auth_headers, tenant_id, collection_id):
        """[BUG TICKET 4] Empty string createdBy must fail PATTERN_NAME_OR_EMAIL validation."""
        payload = create_credential_payload(createdBy="")
        resp = requests.post(credential_url(base_url, tenant_id, collection_id), json=payload, headers=auth_headers)
        if resp.status_code == 201:
            requests.delete(
                credential_url(base_url, tenant_id, collection_id, resp.json()["biometricCredential"]["id"]),
                headers=auth_headers,
            )
        assert resp.status_code == 400

    def test_whitespace_created_by_returns_400(self, base_url, auth_headers, tenant_id, collection_id):
        """[BUG TICKET 4] Whitespace-only createdBy must fail PATTERN_NAME_OR_EMAIL validation."""
        payload = create_credential_payload(createdBy="   ")
        resp = requests.post(credential_url(base_url, tenant_id, collection_id), json=payload, headers=auth_headers)
        if resp.status_code == 201:
            requests.delete(
                credential_url(base_url, tenant_id, collection_id, resp.json()["biometricCredential"]["id"]),
                headers=auth_headers,
            )
        assert resp.status_code == 400

    def test_newline_in_created_by_returns_400(self, base_url, auth_headers, tenant_id, collection_id):
        """[BUG TICKET 4] Newline character in createdBy must fail PATTERN_NAME_OR_EMAIL validation."""
        payload = create_credential_payload(createdBy="user\nname")
        resp = requests.post(credential_url(base_url, tenant_id, collection_id), json=payload, headers=auth_headers)
        if resp.status_code == 201:
            requests.delete(
                credential_url(base_url, tenant_id, collection_id, resp.json()["biometricCredential"]["id"]),
                headers=auth_headers,
            )
        assert resp.status_code == 400

    def test_tab_in_created_by_returns_400(self, base_url, auth_headers, tenant_id, collection_id):
        """[BUG TICKET 4] Tab character in createdBy must fail PATTERN_NAME_OR_EMAIL validation."""
        payload = create_credential_payload(createdBy="user\tname")
        resp = requests.post(credential_url(base_url, tenant_id, collection_id), json=payload, headers=auth_headers)
        if resp.status_code == 201:
            requests.delete(
                credential_url(base_url, tenant_id, collection_id, resp.json()["biometricCredential"]["id"]),
                headers=auth_headers,
            )
        assert resp.status_code == 400


class TestCreateConflict:

    def test_duplicate_external_user_id_returns_409(self, base_url, auth_headers, tenant_id, collection_id):
        """POST with an externalUserId that already exists in the collection returns 409 CONFLICT."""
        user_id = f"dup-{uuid.uuid4().hex[:8]}"
        resp1 = requests.post(
            credential_url(base_url, tenant_id, collection_id),
            json=create_credential_payload(user_id),
            headers=auth_headers,
        )
        assert resp1.status_code == 201
        cid = resp1.json()["biometricCredential"]["id"]
        try:
            resp2 = requests.post(
                credential_url(base_url, tenant_id, collection_id),
                json=create_credential_payload(user_id),
                headers=auth_headers,
            )
            assert resp2.status_code == 409
        finally:
            requests.delete(credential_url(base_url, tenant_id, collection_id, cid), headers=auth_headers)


class TestCreateValidation:

    def test_missing_envelope_returns_400(self, base_url, auth_headers, tenant_id, collection_id):
        """POST without biometricCredential wrapper returns 400."""
        resp = requests.post(
            credential_url(base_url, tenant_id, collection_id),
            json={"externalUserId": "user-x"},
            headers=auth_headers,
        )
        assert resp.status_code == 400

    def test_empty_body_returns_400(self, base_url, auth_headers, tenant_id, collection_id):
        """POST with empty body returns 400."""
        resp = requests.post(
            credential_url(base_url, tenant_id, collection_id),
            json={},
            headers=auth_headers,
        )
        assert resp.status_code == 400

    def test_missing_external_user_id_returns_400(self, base_url, auth_headers, tenant_id, collection_id):
        """POST without externalUserId returns 400 VALIDATION_FAILED.
        """
        payload = {"biometricCredential": {"biometrics": {}}}
        resp = requests.post(credential_url(base_url, tenant_id, collection_id), json=payload, headers=auth_headers)
        assert resp.status_code == 400
        assert resp.json().get("error") == "VALIDATION_FAILED"

    def test_empty_external_user_id_returns_400(self, base_url, auth_headers, tenant_id, collection_id):
        """POST with empty string externalUserId returns 400."""
        payload = {"biometricCredential": {"externalUserId": "", "biometrics": {}}}
        resp = requests.post(credential_url(base_url, tenant_id, collection_id), json=payload, headers=auth_headers)
        assert resp.status_code == 400

    def test_missing_biometrics_returns_400(self, base_url, auth_headers, tenant_id, collection_id):
        """POST without biometrics returns 400 — biometrics is required per spec."""
        payload = {"biometricCredential": {"externalUserId": f"user-{uuid.uuid4().hex[:8]}"}}
        resp = requests.post(credential_url(base_url, tenant_id, collection_id), json=payload, headers=auth_headers)
        assert resp.status_code == 400

    def test_empty_biometrics_map_returns_400(self, base_url, auth_headers, tenant_id, collection_id):
        """POST with an empty biometrics map returns 400 VALIDATION_FAILED.
        Spec: 'At least one modality key with at least one entry is required.'
        [BUG] Live API currently accepts {} and returns 201 — MUST FAIL until fixed."""
        payload = {"biometricCredential": {"externalUserId": f"user-{uuid.uuid4().hex[:8]}", "biometrics": {}}}
        resp = requests.post(credential_url(base_url, tenant_id, collection_id), json=payload, headers=auth_headers)
        # Clean up if the (buggy) API created the credential anyway.
        if resp.status_code == 201:
            requests.delete(
                credential_url(base_url, tenant_id, collection_id, resp.json()["biometricCredential"]["id"]),
                headers=auth_headers,
            )
        assert resp.status_code == 400

    def test_empty_modality_array_returns_400(self, base_url, auth_headers, tenant_id, collection_id):
        """Spec: biometrics modality arrays have minItems 1 — an empty array must return 400.
        [BUG] Server may accept this silently — MUST FAIL until validation is enforced."""
        payload = {"biometricCredential": {
            "externalUserId": f"user-{uuid.uuid4().hex[:8]}",
            "biometrics": {"face": []},
        }}
        resp = requests.post(credential_url(base_url, tenant_id, collection_id), json=payload, headers=auth_headers)
        if resp.status_code == 201:
            requests.delete(
                credential_url(base_url, tenant_id, collection_id, resp.json()["biometricCredential"]["id"]),
                headers=auth_headers,
            )
        assert resp.status_code == 400

    def test_missing_data_in_biometrics_entry_returns_400(self, base_url, auth_headers, tenant_id, collection_id):
        """Spec: BiometricCredentialEntryRequest.data is required ('*'). Entry without data must return 400."""
        payload = {"biometricCredential": {
            "externalUserId": f"user-{uuid.uuid4().hex[:8]}",
            "biometrics": {"face": [{"labels": ["front"]}]},
        }}
        resp = requests.post(credential_url(base_url, tenant_id, collection_id), json=payload, headers=auth_headers)
        if resp.status_code == 201:
            requests.delete(
                credential_url(base_url, tenant_id, collection_id, resp.json()["biometricCredential"]["id"]),
                headers=auth_headers,
            )
        assert resp.status_code == 400
        assert resp.json().get("error") == "VALIDATION_FAILED"

    def test_validation_error_includes_field_errors(self, base_url, auth_headers, tenant_id, collection_id):
        """400 VALIDATION_FAILED body includes a fieldErrors map.
        """
        payload = {"biometricCredential": {}}
        resp = requests.post(credential_url(base_url, tenant_id, collection_id), json=payload, headers=auth_headers)
        assert resp.status_code == 400
        body = resp.json()
        assert body.get("error") == "VALIDATION_FAILED"
        assert "fieldErrors" in body


class TestCreateExternalUserId:

    def test_special_chars_in_external_user_id_accepted(self, base_url, auth_headers, tenant_id, collection_id):
        """externalUserId is an opaque identifier — spaces and symbols are accepted (no format constraint)."""
        payload = {"biometricCredential": {
            "externalUserId": "user with spaces & symbols!",
            "biometrics": {},
        }}
        resp = requests.post(credential_url(base_url, tenant_id, collection_id), json=payload, headers=auth_headers)
        assert resp.status_code == 201
        requests.delete(
            credential_url(base_url, tenant_id, collection_id, resp.json()["biometricCredential"]["id"]),
            headers=auth_headers,
        )

    def test_long_external_user_id_accepted(self, base_url, auth_headers, tenant_id, collection_id):
        """A 500-character externalUserId is accepted — no length limit is enforced."""
        long_id = f"u-{'x' * 498}"
        payload = {"biometricCredential": {"externalUserId": long_id, "biometrics": {}}}
        resp = requests.post(credential_url(base_url, tenant_id, collection_id), json=payload, headers=auth_headers)
        assert resp.status_code == 201
        assert resp.json()["biometricCredential"]["externalUserId"] == long_id
        requests.delete(
            credential_url(base_url, tenant_id, collection_id, resp.json()["biometricCredential"]["id"]),
            headers=auth_headers,
        )


class TestCreateNotFound:

    def test_nonexistent_collection_returns_404(self, base_url, auth_headers, tenant_id):
        """POST to a non-existent collectionId returns 404 NOT_FOUND.
        """
        resp = requests.post(
            credential_url(base_url, tenant_id, str(uuid.uuid4())),
            json=create_credential_payload(),
            headers=auth_headers,
        )
        assert resp.status_code == 404
        assert resp.json().get("error") == "NOT_FOUND"

    def test_nonexistent_tenant_returns_403_or_404(self, base_url, auth_headers, collection_id):
        """POST to a non-existent tenantId returns 403 or 404."""
        resp = requests.post(
            credential_url(base_url, str(uuid.uuid4()), collection_id),
            json=create_credential_payload(),
            headers=auth_headers,
        )
        assert resp.status_code in (403, 404)


class TestCreateServerManagedFields:
    """Client-supplied server-managed fields must be ignored on POST."""

    _FAKE_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    _FAKE_TS = 1000000000000

    def _post_with_server_fields(self, base_url, auth_headers, tenant_id, collection_id):
        payload = {"biometricCredential": {
            "externalUserId": f"user-{uuid.uuid4().hex[:8]}",
            "biometrics": {},
            "id": self._FAKE_ID,
            "createdAt": self._FAKE_TS,
            "updatedAt": self._FAKE_TS,
            "updatedBy": "attacker@evil.com",
        }}
        resp = requests.post(credential_url(base_url, tenant_id, collection_id), json=payload, headers=auth_headers)
        assert resp.status_code == 201, f"Setup failed: {resp.text}"
        return resp.json()["biometricCredential"]

    def test_client_id_is_ignored(self, base_url, auth_headers, tenant_id, collection_id):
        """Client-supplied id is ignored — the server generates a new UUID."""
        c = self._post_with_server_fields(base_url, auth_headers, tenant_id, collection_id)
        try:
            assert c["id"] != self._FAKE_ID
            uuid.UUID(c["id"])
        finally:
            requests.delete(credential_url(base_url, tenant_id, collection_id, c["id"]), headers=auth_headers)

    def test_client_created_at_is_ignored(self, base_url, auth_headers, tenant_id, collection_id):
        """Client-supplied createdAt is ignored — the server sets it to now."""
        c = self._post_with_server_fields(base_url, auth_headers, tenant_id, collection_id)
        try:
            assert c["createdAt"] != self._FAKE_TS
            assert c["createdAt"] > self._FAKE_TS
        finally:
            requests.delete(credential_url(base_url, tenant_id, collection_id, c["id"]), headers=auth_headers)

    def test_client_updated_by_is_ignored_on_create(self, base_url, auth_headers, tenant_id, collection_id):
        """Client-supplied updatedBy is ignored on create."""
        c = self._post_with_server_fields(base_url, auth_headers, tenant_id, collection_id)
        try:
            assert c.get("updatedBy") != "attacker@evil.com"
        finally:
            requests.delete(credential_url(base_url, tenant_id, collection_id, c["id"]), headers=auth_headers)


class TestCreateMalformedBody:
    """
    [BUG TICKET 1] Malformed/invalid request bodies currently return 500.
    Spring exception handlers for HttpMessageNotReadableException and
    HttpMediaTypeNotSupportedException are not mapped — exceptions bubble up as 500.
    All cases below must fail until those handlers are added.
    """

    def test_envelope_as_array_returns_400(self, base_url, auth_headers, tenant_id, collection_id):
        """biometricCredential value is an array instead of an object — must return 400, not 500."""
        resp = requests.post(
            credential_url(base_url, tenant_id, collection_id),
            json={"biometricCredential": [{"externalUserId": "x"}]},
            headers=auth_headers,
        )
        assert resp.status_code == 400

    def test_malformed_json_returns_400(self, base_url, auth_headers, tenant_id, collection_id):
        """Syntactically invalid JSON body must return 400, not 500."""
        headers = {**auth_headers, "Content-Type": "application/json"}
        resp = requests.post(
            credential_url(base_url, tenant_id, collection_id),
            data="{not valid json",
            headers=headers,
        )
        assert resp.status_code == 400

    def test_wrong_content_type_returns_415(self, base_url, auth_headers, tenant_id, collection_id):
        """text/plain Content-Type must return 415 Unsupported Media Type, not 500."""
        headers = {**auth_headers, "Content-Type": "text/plain"}
        resp = requests.post(
            credential_url(base_url, tenant_id, collection_id),
            data="some text",
            headers=headers,
        )
        assert resp.status_code == 415

    def test_empty_body_returns_400(self, base_url, auth_headers, tenant_id, collection_id):
        """Completely empty HTTP body must return 400, not 500.
        Distinct from TestCreateValidation.test_empty_body_returns_400 which sends a valid JSON
        empty object {}; this sends zero bytes with Content-Type: application/json."""
        headers = {**auth_headers, "Content-Type": "application/json"}
        resp = requests.post(
            credential_url(base_url, tenant_id, collection_id),
            data=b"",
            headers=headers,
        )
        assert resp.status_code == 400


class TestCreateModalityEntryLimit:
    """Spec: each modality array in the POST body must contain no more than 5 entries."""

    def test_six_face_entries_returns_400(self, base_url, auth_headers, tenant_id, collection_id):
        """POST with 6 face entries exceeds the per-modality limit — must return 400 MODALITY_ENTRY_LIMIT_EXCEEDED."""
        entries = [{"labels": [f"sample-{i}"], "data": _DUMMY_IMAGE_B64} for i in range(6)]
        payload = {
            "biometricCredential": {
                "externalUserId": f"user-{uuid.uuid4().hex[:8]}",
                "biometrics": {"face": entries},
            }
        }
        resp = requests.post(credential_url(base_url, tenant_id, collection_id), json=payload, headers=auth_headers)
        if resp.status_code == 201:
            requests.delete(
                credential_url(base_url, tenant_id, collection_id, resp.json()["biometricCredential"]["id"]),
                headers=auth_headers,
            )
        assert resp.status_code == 400
        assert resp.json().get("error") == "MODALITY_ENTRY_LIMIT_EXCEEDED"

    def test_five_face_entries_is_accepted(self, base_url, auth_headers, tenant_id, collection_id):
        """POST with exactly 5 face entries is at the limit and must succeed."""
        entries = [{"labels": [f"sample-{i}"], "data": _DUMMY_IMAGE_B64} for i in range(5)]
        payload = {
            "biometricCredential": {
                "externalUserId": f"user-{uuid.uuid4().hex[:8]}",
                "biometrics": {"face": entries},
            }
        }
        resp = requests.post(credential_url(base_url, tenant_id, collection_id), json=payload, headers=auth_headers)
        if resp.status_code == 201:
            requests.delete(
                credential_url(base_url, tenant_id, collection_id, resp.json()["biometricCredential"]["id"]),
                headers=auth_headers,
            )
        assert resp.status_code == 201


class TestErrorResponseShape:
    """Error responses must include a timestamp field formatted as ISO-8601."""

    def test_error_response_includes_timestamp(self, base_url, auth_headers, tenant_id, collection_id):
        """A 400 error response must contain a 'timestamp' field."""
        payload = {"biometricCredential": {"biometrics": {}}}  # missing externalUserId → 400
        resp = requests.post(credential_url(base_url, tenant_id, collection_id), json=payload, headers=auth_headers)
        assert resp.status_code == 400
        assert "timestamp" in resp.json(), "Error response missing 'timestamp' field"

    def test_error_timestamp_is_iso8601(self, base_url, auth_headers, tenant_id, collection_id):
        """The 'timestamp' field in an error response must be a valid ISO-8601 string."""
        payload = {"biometricCredential": {"biometrics": {}}}
        resp = requests.post(credential_url(base_url, tenant_id, collection_id), json=payload, headers=auth_headers)
        assert resp.status_code == 400
        ts = resp.json().get("timestamp")
        assert ts is not None
        try:
            datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            raise AssertionError(f"timestamp is not valid ISO-8601: {ts!r}")


class TestCreateCreatedByDefault:
    """Spec: createdBy is optional — when omitted the server falls back to 'system'."""

    def test_created_by_defaults_to_system_when_omitted(self, base_url, auth_headers, tenant_id, collection_id):
        """Omitting createdBy results in createdBy='system' in the stored credential."""
        payload = {"biometricCredential": {"externalUserId": f"user-{uuid.uuid4().hex[:8]}", "biometrics": {}}}
        resp = requests.post(credential_url(base_url, tenant_id, collection_id), json=payload, headers=auth_headers)
        assert resp.status_code == 201
        cred = resp.json()["biometricCredential"]
        try:
            assert cred.get("createdBy") == "system"
        finally:
            requests.delete(credential_url(base_url, tenant_id, collection_id, cred["id"]), headers=auth_headers)
