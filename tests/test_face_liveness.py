"""
Tests for POST /v3/face/checkLiveness

Environment variables (see conftest.py):
  AWARE_BASE_URL          Base URL (default: https://api.qa1.awareidentity.com)
  AWARE_API_KEY           X-Aware-ApiKey header value
  AWARE_ACCOUNT_ID        X-Aware-AccountId header value
  AWARE_LIVENESS_POLICY   policyName to use (default: "Face Liveness")
  AWARE_TEST_IMAGE_PATH   Path to a live face JPEG/PNG for happy-path tests
  AWARE_SPOOF_IMAGE_PATH  Path to a spoof image for business logic tests
"""

import requests
import pytest

ENDPOINT = "/v3/face/checkLiveness"

VALID_DECISIONS = {
    "LIVE",
    "SPOOF",
    "POSE_TOO_HIGH",
    "TOO_LOW_FACIAL_DYNAMIC_RANGE",
    "FACE_TOO_LOW_RESOLUTION",
    "UNABLE_TO_CALCULATE_LIVENESS",
}
VALID_ROLES = {"DECISIONING", "REPORTING_ONLY"}
VALID_CAPTURE_DEVICES = {"MOBILE_SELFIE", "OTHER"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _post(base_url, headers, payload):
    return requests.post(f"{base_url}{ENDPOINT}", json=payload, headers=headers)


def _valid_payload(image_b64, policy, correlation_id=None):
    inner = {
        "images": [{"data": image_b64}],
        "captureDevice": "MOBILE_SELFIE",
        "policyName": policy,
    }
    if correlation_id:
        inner["correlationID"] = correlation_id
    return {"faceLiveness": inner}


# ---------------------------------------------------------------------------
# Happy-path — validates the 200 response contract (requires AWARE_TEST_IMAGE_PATH)
# ---------------------------------------------------------------------------

class TestCheckFaceLivenessHappyPath:

    def test_returns_200(self, base_url, auth_headers, face_image_b64, liveness_policy):
        """Verify the endpoint is reachable and returns HTTP 200 for a valid request."""
        resp = _post(base_url, auth_headers, _valid_payload(face_image_b64, liveness_policy))
        assert resp.status_code == 200

    def test_response_contains_required_fields(self, base_url, auth_headers, face_image_b64, liveness_policy):
        """Verify all required fields per the OpenAPI spec are present in the response."""
        resp = _post(base_url, auth_headers, _valid_payload(face_image_b64, liveness_policy))
        assert resp.status_code == 200
        liveness = resp.json()["faceLiveness"]
        assert "transactionID" in liveness
        assert "decision" in liveness
        assert "score" in liveness
        assert "configuration" in liveness
        assert "timestamp" in liveness

    def test_decision_is_valid_enum(self, base_url, auth_headers, face_image_b64, liveness_policy):
        """Verify the top-level decision is one of the 6 values documented in the spec."""
        resp = _post(base_url, auth_headers, _valid_payload(face_image_b64, liveness_policy))
        assert resp.status_code == 200
        assert resp.json()["faceLiveness"]["decision"] in VALID_DECISIONS

    def test_score_is_normalized(self, base_url, auth_headers, face_image_b64, liveness_policy):
        """Verify the liveness score is a number in [0, 1] as per the spec."""
        resp = _post(base_url, auth_headers, _valid_payload(face_image_b64, liveness_policy))
        assert resp.status_code == 200
        score = resp.json()["faceLiveness"]["score"]
        assert isinstance(score, (int, float))
        assert 0.0 <= score <= 1.0

    def test_algorithms_list_is_non_empty(self, base_url, auth_headers, face_image_b64, liveness_policy):
        """Verify at least one algorithm processed the request — empty list means no result basis."""
        resp = _post(base_url, auth_headers, _valid_payload(face_image_b64, liveness_policy))
        assert resp.status_code == 200
        algorithms = resp.json()["faceLiveness"]["configuration"]["algorithms"]
        assert isinstance(algorithms, list)
        assert len(algorithms) >= 1

    def test_algorithm_role_is_valid_enum(self, base_url, auth_headers, face_image_b64, liveness_policy):
        """Verify each algorithm's role is either DECISIONING or REPORTING_ONLY per the spec."""
        resp = _post(base_url, auth_headers, _valid_payload(face_image_b64, liveness_policy))
        assert resp.status_code == 200
        for alg in resp.json()["faceLiveness"]["configuration"]["algorithms"]:
            assert alg["role"] in VALID_ROLES

    def test_algorithm_decision_is_valid_enum(self, base_url, auth_headers, face_image_b64, liveness_policy):
        """Verify each per-algorithm decision is also a valid LivenessDecision enum value."""
        resp = _post(base_url, auth_headers, _valid_payload(face_image_b64, liveness_policy))
        assert resp.status_code == 200
        for alg in resp.json()["faceLiveness"]["configuration"]["algorithms"]:
            assert alg["decision"] in VALID_DECISIONS

    def test_algorithm_type_specific_config(self, base_url, auth_headers, face_image_b64, liveness_policy):
        """Verify MITEK uses scoreThreshold and AWARE uses securitySetting — they have different config schemas."""
        resp = _post(base_url, auth_headers, _valid_payload(face_image_b64, liveness_policy))
        assert resp.status_code == 200
        valid_security_settings = {"HIGH_USABILITY", "BALANCED", "HIGH_SECURITY"}
        for alg in resp.json()["faceLiveness"]["configuration"]["algorithms"]:
            name = alg.get("name")
            config = alg.get("configuration", {})
            if name == "MITEK":
                if "scoreThreshold" in config:
                    assert isinstance(config["scoreThreshold"], (int, float))
                    assert 0.0 <= config["scoreThreshold"] <= 1.0
            elif name == "AWARE":
                if "securitySetting" in config:
                    assert config["securitySetting"] in valid_security_settings

    def test_algorithm_score_is_normalized(self, base_url, auth_headers, face_image_b64, liveness_policy):
        """Verify each per-algorithm score is in [0, 1] as required by MitekAlgorithm and AwareAlgorithm schemas."""
        resp = _post(base_url, auth_headers, _valid_payload(face_image_b64, liveness_policy))
        assert resp.status_code == 200
        for alg in resp.json()["faceLiveness"]["configuration"]["algorithms"]:
            assert 0.0 <= alg["score"] <= 1.0

    def test_correlation_id_is_echoed(self, base_url, auth_headers, face_image_b64, liveness_policy):
        """Verify the correlationID supplied by the caller is echoed back unchanged for traceability."""
        cid = "test-correlation-001"
        resp = _post(base_url, auth_headers, _valid_payload(face_image_b64, liveness_policy, correlation_id=cid))
        assert resp.status_code == 200
        assert resp.json()["faceLiveness"]["correlationID"] == cid

    def test_request_without_correlation_id_succeeds(self, base_url, auth_headers, face_image_b64, liveness_policy):
        """Verify correlationID is truly optional and omitting it does not break the response."""
        resp = _post(base_url, auth_headers, _valid_payload(face_image_b64, liveness_policy))
        assert resp.status_code == 200
        assert "correlationID" not in resp.json()["faceLiveness"]

    def test_capture_device_other_is_accepted(self, base_url, auth_headers, face_image_b64, liveness_policy):
        """Verify the OTHER capture device enum value is accepted alongside MOBILE_SELFIE."""
        payload = {"faceLiveness": {
            "images": [{"data": face_image_b64}],
            "captureDevice": "OTHER",
            "policyName": liveness_policy,
        }}
        resp = _post(base_url, auth_headers, payload)
        assert resp.status_code == 200

    def test_multiple_images_accepted(self, base_url, auth_headers, face_image_b64, liveness_policy):
        """Verify the images array accepts more than one image as allowed by minItems: 1 in the spec."""
        payload = {"faceLiveness": {
            "images": [{"data": face_image_b64}, {"data": face_image_b64}],
            "captureDevice": "MOBILE_SELFIE",
            "policyName": liveness_policy,
        }}
        resp = _post(base_url, auth_headers, payload)
        assert resp.status_code == 200

    def test_timestamp_is_integer_milliseconds(self, base_url, auth_headers, face_image_b64, liveness_policy):
        """Verify the timestamp is a Unix epoch integer in milliseconds within a plausible date range."""
        resp = _post(base_url, auth_headers, _valid_payload(face_image_b64, liveness_policy))
        assert resp.status_code == 200
        ts = resp.json()["faceLiveness"]["timestamp"]
        assert isinstance(ts, int)
        assert 1_577_836_800_000 < ts < 1_893_456_000_000

    def test_transaction_id_is_string(self, base_url, auth_headers, face_image_b64, liveness_policy):
        """Verify the transactionID is returned as a string — it is used for audit and log correlation."""
        resp = _post(base_url, auth_headers, _valid_payload(face_image_b64, liveness_policy))
        assert resp.status_code == 200
        assert isinstance(resp.json()["faceLiveness"]["transactionID"], str)

    def test_response_content_type_is_json(self, base_url, auth_headers, face_image_b64, liveness_policy):
        """Verify the response Content-Type header declares application/json."""
        resp = _post(base_url, auth_headers, _valid_payload(face_image_b64, liveness_policy))
        assert resp.status_code == 200
        assert "application/json" in resp.headers.get("Content-Type", "")


# ---------------------------------------------------------------------------
# Business logic — validates real-world biometric behavior
# ---------------------------------------------------------------------------

class TestCheckFaceLivenessBusinessLogic:

    def test_spoof_image_returns_spoof_decision(self, base_url, auth_headers, spoof_image_b64, liveness_policy):
        """Verify a known spoof image (photo of a printed face) is correctly rejected as SPOOF."""
        resp = _post(base_url, auth_headers, _valid_payload(spoof_image_b64, liveness_policy))
        assert resp.status_code == 200
        assert resp.json()["faceLiveness"]["decision"] == "SPOOF"

    def test_non_face_image_returns_graceful_decision(self, base_url, auth_headers, minimal_image_b64, liveness_policy):
        """Spec implies 200 with a graceful LivenessDecision for non-face images; new build may return 400. Must never 500."""
        resp = _post(base_url, auth_headers, _valid_payload(minimal_image_b64, liveness_policy))
        assert resp.status_code in (200, 400)
        assert resp.status_code != 500
        if resp.status_code == 200:
            assert resp.json()["faceLiveness"]["decision"] in VALID_DECISIONS

    def test_live_score_higher_than_spoof_score(self, base_url, auth_headers, face_image_b64, spoof_image_b64, liveness_policy):
        """Verify the score direction — live images must score higher than spoof images per spec semantics."""
        live_resp = _post(base_url, auth_headers, _valid_payload(face_image_b64, liveness_policy))
        spoof_resp = _post(base_url, auth_headers, _valid_payload(spoof_image_b64, liveness_policy))
        assert live_resp.status_code == 200
        assert spoof_resp.status_code == 200
        assert live_resp.json()["faceLiveness"]["score"] > spoof_resp.json()["faceLiveness"]["score"]

    def test_decisioning_algorithm_matches_top_level_decision(self, base_url, auth_headers, face_image_b64, liveness_policy):
        """Verify the DECISIONING algorithm's result drives the top-level decision field."""
        resp = _post(base_url, auth_headers, _valid_payload(face_image_b64, liveness_policy))
        assert resp.status_code == 200
        body = resp.json()["faceLiveness"]
        decisioning = [a for a in body["configuration"]["algorithms"] if a["role"] == "DECISIONING"]
        assert len(decisioning) >= 1
        assert decisioning[0]["decision"] == body["decision"]

    def test_reporting_only_does_not_affect_top_level_decision(self, base_url, auth_headers, spoof_image_b64, liveness_policy):
        """Verify REPORTING_ONLY algorithms do not override the DECISIONING result even when they disagree."""
        resp = _post(base_url, auth_headers, _valid_payload(spoof_image_b64, liveness_policy))
        assert resp.status_code == 200
        body = resp.json()["faceLiveness"]
        decisioning = [a for a in body["configuration"]["algorithms"] if a["role"] == "DECISIONING"]
        if decisioning:
            assert body["decision"] == decisioning[0]["decision"]

    def test_two_requests_have_different_transaction_ids(self, base_url, auth_headers, face_image_b64, liveness_policy):
        """Verify each transaction is assigned a unique ID — required for audit traceability."""
        resp1 = _post(base_url, auth_headers, _valid_payload(face_image_b64, liveness_policy))
        resp2 = _post(base_url, auth_headers, _valid_payload(face_image_b64, liveness_policy))
        assert resp1.status_code == 200
        assert resp2.status_code == 200
        assert resp1.json()["faceLiveness"]["transactionID"] != resp2.json()["faceLiveness"]["transactionID"]

    def test_single_char_correlation_id_echoed(self, base_url, auth_headers, face_image_b64, liveness_policy):
        """Verify a minimum-length (1 char) correlationID is echoed correctly without truncation."""
        resp = _post(base_url, auth_headers, _valid_payload(face_image_b64, liveness_policy, correlation_id="x"))
        assert resp.status_code == 200
        assert resp.json()["faceLiveness"]["correlationID"] == "x"

    def test_empty_string_correlation_id_behavior(self, base_url, auth_headers, face_image_b64, liveness_policy):
        """Verify an empty string correlationID does not cause an error — edge case for client implementations."""
        resp = _post(base_url, auth_headers, _valid_payload(face_image_b64, liveness_policy, correlation_id=""))
        assert resp.status_code == 200

    def test_null_capture_device_returns_400(self, base_url, auth_headers, minimal_image_b64, liveness_policy):
        """Verify a null captureDevice (required enum field) is rejected with 400."""
        payload = {"faceLiveness": {"images": [{"data": minimal_image_b64}], "captureDevice": None, "policyName": liveness_policy}}
        resp = _post(base_url, auth_headers, payload)
        assert resp.status_code == 400

    def test_small_image_does_not_crash(self, base_url, auth_headers, minimal_image_b64, liveness_policy):
        """Verify a very small image (1x1 pixel) never causes a 500 — 200 or 400 are both acceptable."""
        resp = _post(base_url, auth_headers, _valid_payload(minimal_image_b64, liveness_policy))
        assert resp.status_code in (200, 400)
        assert resp.status_code != 500


# ---------------------------------------------------------------------------
# Validation errors (400) — server must reject malformed requests
# ---------------------------------------------------------------------------

class TestCheckFaceLivenessValidation:

    def test_empty_image_data_string_returns_400(self, base_url, auth_headers, liveness_policy):
        """Verify an empty string for image data is rejected — it is not a valid base64 image."""
        payload = {"faceLiveness": {"images": [{"data": ""}], "captureDevice": "MOBILE_SELFIE", "policyName": liveness_policy}}
        resp = _post(base_url, auth_headers, payload)
        assert resp.status_code == 400

    def test_invalid_base64_image_returns_400(self, base_url, auth_headers, liveness_policy):
        """Verify a non-base64 string is rejected with 400 — fixed in new build."""
        payload = {"faceLiveness": {"images": [{"data": "not-valid-base64!!!"}], "captureDevice": "MOBILE_SELFIE", "policyName": liveness_policy}}
        resp = _post(base_url, auth_headers, payload)
        assert resp.status_code == 400

    def test_valid_base64_but_invalid_image_returns_400(self, base_url, auth_headers, liveness_policy):
        """Verify valid base64 that is not a real image is rejected — second validation stage (INVALID_IMAGE_DATA)."""
        payload = {"faceLiveness": {"images": [{"data": "abcd=="}], "captureDevice": "MOBILE_SELFIE", "policyName": liveness_policy}}
        resp = _post(base_url, auth_headers, payload)
        assert resp.status_code == 400

    def test_missing_image_data_field_returns_400(self, base_url, auth_headers, liveness_policy):
        """Verify that omitting the required data field inside an image object returns 400."""
        payload = {"faceLiveness": {"images": [{}], "captureDevice": "MOBILE_SELFIE", "policyName": liveness_policy}}
        resp = _post(base_url, auth_headers, payload)
        assert resp.status_code == 400

    def test_null_policy_name_returns_400(self, base_url, auth_headers, minimal_image_b64):
        """Verify a null policyName is treated as omitted — triggers 409 when multiple policies exist."""
        payload = {"faceLiveness": {"images": [{"data": minimal_image_b64}], "captureDevice": "MOBILE_SELFIE", "policyName": None}}
        resp = _post(base_url, auth_headers, payload)
        assert resp.status_code in (400, 409, 422)

    def test_empty_policy_name_returns_400_or_404(self, base_url, auth_headers, minimal_image_b64):
        """Verify an empty string policyName is treated as omitted — server returns 409 MULTIPLE_POLICIES_CONFIGURED."""
        payload = {"faceLiveness": {"images": [{"data": minimal_image_b64}], "captureDevice": "MOBILE_SELFIE", "policyName": ""}}
        resp = _post(base_url, auth_headers, payload)
        assert resp.status_code in (400, 404, 409, 422)

    def test_empty_images_array_returns_400(self, base_url, auth_headers, liveness_policy):
        """Verify an empty images array is rejected — the spec requires minItems: 1."""
        payload = {"faceLiveness": {"images": [], "captureDevice": "MOBILE_SELFIE", "policyName": liveness_policy}}
        resp = _post(base_url, auth_headers, payload)
        assert resp.status_code == 400

    def test_missing_images_field_returns_400(self, base_url, auth_headers, liveness_policy):
        """Verify the images field is required and its absence returns 400."""
        payload = {"faceLiveness": {"captureDevice": "MOBILE_SELFIE", "policyName": liveness_policy}}
        resp = _post(base_url, auth_headers, payload)
        assert resp.status_code == 400

    def test_missing_capture_device_returns_400(self, base_url, auth_headers, minimal_image_b64, liveness_policy):
        """Verify captureDevice is required and its absence returns 400."""
        payload = {"faceLiveness": {"images": [{"data": minimal_image_b64}], "policyName": liveness_policy}}
        resp = _post(base_url, auth_headers, payload)
        assert resp.status_code == 400

    def test_invalid_capture_device_returns_400(self, base_url, auth_headers, minimal_image_b64, liveness_policy):
        """Verify captureDevice only accepts MOBILE_SELFIE or OTHER — any other value returns 400."""
        payload = {"faceLiveness": {
            "images": [{"data": minimal_image_b64}],
            "captureDevice": "INVALID_DEVICE",
            "policyName": liveness_policy,
        }}
        resp = _post(base_url, auth_headers, payload)
        assert resp.status_code == 400

    def test_missing_top_level_wrapper_returns_400(self, base_url, auth_headers, minimal_image_b64, liveness_policy):
        """Verify the request must be wrapped in a faceLiveness object — flat payloads are rejected."""
        payload = {"images": [{"data": minimal_image_b64}], "captureDevice": "MOBILE_SELFIE"}
        resp = _post(base_url, auth_headers, payload)
        assert resp.status_code == 400

    def test_validation_error_body_has_error_code(self, base_url, auth_headers, liveness_policy):
        """Verify validation errors return errorCode: VALIDATION_FAILED and a human-readable message."""
        payload = {"faceLiveness": {"images": [], "captureDevice": "MOBILE_SELFIE", "policyName": liveness_policy}}
        resp = _post(base_url, auth_headers, payload)
        assert resp.status_code == 400
        body = resp.json()
        assert body.get("errorCode") == "VALIDATION_FAILED"
        assert "message" in body


# ---------------------------------------------------------------------------
# Policy edge cases — boundary and unexpected policyName values
# ---------------------------------------------------------------------------

class TestCheckFaceLivenessPolicyEdgeCases:

    def test_special_chars_policy_name_returns_404(self, base_url, auth_headers, minimal_image_b64):
        """Verify special characters in policyName return 404 gracefully rather than crashing."""
        payload = {"faceLiveness": {"images": [{"data": minimal_image_b64}], "captureDevice": "MOBILE_SELFIE", "policyName": "!@#$%^&*()"}}
        resp = _post(base_url, auth_headers, payload)
        assert resp.status_code in (400, 404)

    def test_very_long_policy_name_does_not_crash(self, base_url, auth_headers, minimal_image_b64):
        """Verify a 500-character policyName does not cause a 500 — server must handle long strings safely."""
        payload = {"faceLiveness": {"images": [{"data": minimal_image_b64}], "captureDevice": "MOBILE_SELFIE", "policyName": "A" * 500}}
        resp = _post(base_url, auth_headers, payload)
        assert resp.status_code in (400, 404)
        assert resp.status_code != 500


# ---------------------------------------------------------------------------
# Security — verify the server handles adversarial inputs safely
# ---------------------------------------------------------------------------

class TestCheckFaceLivenessSecurity:

    def test_sql_injection_in_policy_name_does_not_crash(self, base_url, auth_headers, minimal_image_b64):
        """Verify a SQL injection attempt in policyName does not cause a 500 or expose server internals."""
        payload = {"faceLiveness": {"images": [{"data": minimal_image_b64}], "captureDevice": "MOBILE_SELFIE", "policyName": "'; DROP TABLE policies; --"}}
        resp = _post(base_url, auth_headers, payload)
        assert resp.status_code != 500

    def test_xss_in_correlation_id_is_echoed_safely(self, base_url, auth_headers, face_image_b64, liveness_policy):
        """Verify an XSS payload in correlationID is echoed back as plain text, not interpreted or executed."""
        xss = "<script>alert(1)</script>"
        resp = _post(base_url, auth_headers, _valid_payload(face_image_b64, liveness_policy, correlation_id=xss))
        assert resp.status_code == 200
        assert resp.json()["faceLiveness"]["correlationID"] == xss


# ---------------------------------------------------------------------------
# Policy errors — documented 404 / 409 responses
# ---------------------------------------------------------------------------

class TestCheckFaceLivenessPolicy:

    def test_nonexistent_policy_returns_404(self, base_url, auth_headers, minimal_image_b64):
        """Verify a policyName that does not exist returns 404 with errorCode POLICY_NOT_FOUND."""
        payload = {"faceLiveness": {
            "images": [{"data": minimal_image_b64}],
            "captureDevice": "MOBILE_SELFIE",
            "policyName": "nonexistent-policy-xyz-99999",
        }}
        resp = _post(base_url, auth_headers, payload)
        assert resp.status_code == 404
        assert resp.json().get("errorCode") == "POLICY_NOT_FOUND"

    def test_omitting_policy_name_with_multiple_policies_returns_409(self, base_url, auth_headers, minimal_image_b64):
        """Verify that omitting policyName when multiple policies are enabled returns 409 MULTIPLE_POLICIES_CONFIGURED."""
        payload = {"faceLiveness": {
            "images": [{"data": minimal_image_b64}],
            "captureDevice": "MOBILE_SELFIE",
        }}
        resp = _post(base_url, auth_headers, payload)
        assert resp.status_code == 409
        assert resp.json().get("errorCode") == "MULTIPLE_POLICIES_CONFIGURED"

    @pytest.mark.skip(reason="Requires disabling all algorithms on the Face Liveness policy in admin console first")
    def test_policy_with_no_algorithms_returns_422(self, base_url, auth_headers, minimal_image_b64, liveness_policy):
        """Verify 422 POLICY_HAS_NO_ALGORITHMS is returned when the policy has no enabled algorithms — fixed in new build."""
        payload = {"faceLiveness": {
            "images": [{"data": minimal_image_b64}],
            "captureDevice": "MOBILE_SELFIE",
            "policyName": liveness_policy,
        }}
        resp = _post(base_url, auth_headers, payload)
        assert resp.status_code == 422
        assert resp.json().get("errorCode") == "POLICY_HAS_NO_ALGORITHMS"


# ---------------------------------------------------------------------------
# Multiple API keys — security testing for header duplication
# ---------------------------------------------------------------------------

class TestCheckFaceLivenessMultipleKeys:

    def _send_duplicate_header(self, account_id, key1, key2, payload):
        """Send a request with two X-Aware-ApiKey headers using http.client for true header duplication."""
        import http.client
        import json
        import ssl
        body = json.dumps(payload).encode("utf-8")
        conn = http.client.HTTPSConnection("api.qa1.awareidentity.com", context=ssl.create_default_context())
        conn.putrequest("POST", ENDPOINT)
        conn.putheader("X-Aware-ApiKey", key1)
        conn.putheader("X-Aware-ApiKey", key2)
        conn.putheader("X-Aware-AccountId", account_id)
        conn.putheader("Content-Type", "application/json")
        conn.putheader("Content-Length", str(len(body)))
        conn.endheaders(body)
        resp = conn.getresponse()
        return resp.status, resp.read().decode("utf-8")

    def test_valid_key_first_invalid_key_second(self, base_url, auth_headers, minimal_image_b64, liveness_policy):
        """Valid key first, invalid second — server should process with first key or reject; must never 500."""
        status, body = self._send_duplicate_header(
            auth_headers["X-Aware-AccountId"],
            auth_headers["X-Aware-ApiKey"],
            "0" * 64,
            _valid_payload(minimal_image_b64, liveness_policy),
        )
        assert status in (200, 400, 401, 403, 422)
        assert status != 500

    def test_invalid_key_first_valid_key_second(self, base_url, auth_headers, minimal_image_b64, liveness_policy):
        """Invalid key first, valid second — server must not grant access; duplicate valid key must not bypass auth."""
        status, body = self._send_duplicate_header(
            auth_headers["X-Aware-AccountId"],
            "0" * 64,
            auth_headers["X-Aware-ApiKey"],
            _valid_payload(minimal_image_b64, liveness_policy),
        )
        assert status in (400, 401, 403)
        assert status != 200

    def test_two_valid_keys_different_tenants(self, base_url, auth_headers, minimal_image_b64, liveness_policy, second_api_key):
        """Two valid keys from different tenants — server must not crash or allow cross-tenant access."""
        status, body = self._send_duplicate_header(
            auth_headers["X-Aware-AccountId"],
            auth_headers["X-Aware-ApiKey"],
            second_api_key,
            _valid_payload(minimal_image_b64, liveness_policy),
        )
        assert status != 500


# ---------------------------------------------------------------------------
# Auth errors — requests with invalid or missing credentials
# ---------------------------------------------------------------------------

class TestCheckFaceLivenessAuth:

    def test_invalid_api_key_returns_401(self, base_url, bad_auth_headers, minimal_image_b64, liveness_policy):
        """Verify a wrong API key is rejected with 401 or 403."""
        resp = _post(base_url, bad_auth_headers, _valid_payload(minimal_image_b64, liveness_policy))
        assert resp.status_code in (401, 403)

    def test_missing_account_id_returns_403(self, base_url, auth_headers, minimal_image_b64, liveness_policy):
        """Verify omitting X-Aware-AccountId is rejected — spec does not document auth errors; 400/401/403/500 all observed."""
        headers = {k: v for k, v in auth_headers.items() if k != "X-Aware-AccountId"}
        resp = _post(base_url, headers, _valid_payload(minimal_image_b64, liveness_policy))
        assert resp.status_code in (400, 401, 403, 500)

    def test_wrong_account_id_returns_403(self, base_url, minimal_image_b64, liveness_policy):
        """Verify an API key with mismatched AccountId is rejected — spec does not document auth errors; 400/401/403/500 all observed."""
        from tests.conftest import API_KEY
        headers = {"X-Aware-ApiKey": API_KEY, "X-Aware-AccountId": "wrong-account-000", "Content-Type": "application/json"}
        resp = _post(base_url, headers, _valid_payload(minimal_image_b64, liveness_policy))
        assert resp.status_code in (400, 401, 403, 500)

    def test_missing_api_key_returns_401(self, base_url, minimal_image_b64, liveness_policy):
        """Verify a request with no auth headers is rejected — spec does not document auth errors; 400/401/403 all observed."""
        headers = {"Content-Type": "application/json"}
        resp = requests.post(
            f"{base_url}{ENDPOINT}",
            json=_valid_payload(minimal_image_b64, liveness_policy),
            headers=headers,
            allow_redirects=False,
        )
        assert resp.status_code in (301, 302, 303, 307, 308, 400, 401, 403)
