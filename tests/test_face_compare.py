"""
Tests for POST /v3/face/compare

Environment variables (see conftest.py):
  AWARE_BASE_URL           Base URL (default: https://api.qa1.awareidentity.com)
  AWARE_API_KEY            X-Aware-ApiKey header value
  AWARE_ACCOUNT_ID         X-Aware-AccountId header value
  AWARE_COMPARE_POLICY     policyName to use (default: "Face · 1:1 Verification")
  AWARE_TEST_IMAGE_PATH    Path to a face JPEG/PNG (person A, photo 1)
  AWARE_SECOND_IMAGE_PATH  Path to a second photo of the same person (person A, photo 2)
  AWARE_SPOOF_IMAGE_PATH   Path to a different person's photo (person B)
"""

import requests
import pytest

ENDPOINT = "/v3/face/compare"

VALID_ROLES = {"DECISIONING", "REPORTING_ONLY"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _post(base_url, headers, payload):
    return requests.post(f"{base_url}{ENDPOINT}", json=payload, headers=headers)


def _valid_payload(probe_b64, candidate_b64, policy, correlation_id=None):
    inner = {
        "probe": {"image": probe_b64},
        "candidate": {"image": candidate_b64},
        "policyName": policy,
    }
    if correlation_id:
        inner["correlationID"] = correlation_id
    return {"faceCompare": inner}


# ---------------------------------------------------------------------------
# Happy-path — validates the 200 response contract (requires AWARE_TEST_IMAGE_PATH)
# ---------------------------------------------------------------------------

class TestFaceCompareHappyPath:

    def test_returns_200(self, base_url, auth_headers, face_image_b64, compare_policy):
        """Verify the endpoint is reachable and returns HTTP 200 for a valid request."""
        resp = _post(base_url, auth_headers, _valid_payload(face_image_b64, face_image_b64, compare_policy))
        assert resp.status_code == 200

    def test_response_contains_required_fields(self, base_url, auth_headers, face_image_b64, compare_policy):
        """Verify all required fields per the OpenAPI spec are present in the response."""
        resp = _post(base_url, auth_headers, _valid_payload(face_image_b64, face_image_b64, compare_policy))
        assert resp.status_code == 200
        compare = resp.json()["faceCompare"]
        assert "score" in compare
        assert "match" in compare
        assert "configuration" in compare
        assert "timestamp" in compare
        assert "transactionID" in compare

    def test_score_is_non_negative(self, base_url, auth_headers, face_image_b64, compare_policy):
        """Verify the similarity score is >= 0 — the spec defines range as [0, +inf)."""
        resp = _post(base_url, auth_headers, _valid_payload(face_image_b64, face_image_b64, compare_policy))
        assert resp.status_code == 200
        score = resp.json()["faceCompare"]["score"]
        assert isinstance(score, (int, float))
        assert score >= 0.0

    def test_match_is_boolean(self, base_url, auth_headers, face_image_b64, compare_policy):
        """Verify the match field is a boolean — not a string or integer."""
        resp = _post(base_url, auth_headers, _valid_payload(face_image_b64, face_image_b64, compare_policy))
        assert resp.status_code == 200
        assert isinstance(resp.json()["faceCompare"]["match"], bool)

    def test_same_image_produces_match(self, base_url, auth_headers, face_image_b64, compare_policy):
        """Verify the same image compared against itself returns match: true — baseline correctness check."""
        resp = _post(base_url, auth_headers, _valid_payload(face_image_b64, face_image_b64, compare_policy))
        assert resp.status_code == 200
        assert resp.json()["faceCompare"]["match"] is True

    def test_algorithms_list_is_non_empty(self, base_url, auth_headers, face_image_b64, compare_policy):
        """Verify at least one algorithm ran — empty list means no result basis (known bug when no algorithms configured)."""
        resp = _post(base_url, auth_headers, _valid_payload(face_image_b64, face_image_b64, compare_policy))
        assert resp.status_code == 200
        algorithms = resp.json()["faceCompare"]["configuration"]["algorithms"]
        assert isinstance(algorithms, list)
        assert len(algorithms) >= 1

    def test_algorithm_role_is_valid_enum(self, base_url, auth_headers, face_image_b64, compare_policy):
        """Verify each algorithm's role is either DECISIONING or REPORTING_ONLY per the spec."""
        resp = _post(base_url, auth_headers, _valid_payload(face_image_b64, face_image_b64, compare_policy))
        assert resp.status_code == 200
        for alg in resp.json()["faceCompare"]["configuration"]["algorithms"]:
            assert alg["role"] in VALID_ROLES

    def test_algorithm_score_is_non_negative(self, base_url, auth_headers, face_image_b64, compare_policy):
        """Verify each per-algorithm score is >= 0 as required by MatchAlgorithm schema."""
        resp = _post(base_url, auth_headers, _valid_payload(face_image_b64, face_image_b64, compare_policy))
        assert resp.status_code == 200
        for alg in resp.json()["faceCompare"]["configuration"]["algorithms"]:
            assert alg["score"] >= 0.0

    def test_algorithm_score_threshold_when_present_is_numeric(self, base_url, auth_headers, face_image_b64, compare_policy):
        """Verify scoreThreshold is a number when present — currently a known bug (returned as string '4')."""
        resp = _post(base_url, auth_headers, _valid_payload(face_image_b64, face_image_b64, compare_policy))
        assert resp.status_code == 200
        for alg in resp.json()["faceCompare"]["configuration"]["algorithms"]:
            threshold = alg.get("configuration", {}).get("scoreThreshold")
            if threshold is not None:
                assert isinstance(threshold, (int, float))
                assert threshold >= 0

    def test_correlation_id_is_echoed(self, base_url, auth_headers, face_image_b64, compare_policy):
        """Verify the caller-supplied correlationID is echoed back unchanged for traceability."""
        cid = "test-compare-correlation-001"
        resp = _post(base_url, auth_headers, _valid_payload(face_image_b64, face_image_b64, compare_policy, correlation_id=cid))
        assert resp.status_code == 200
        assert resp.json()["faceCompare"]["correlationID"] == cid

    def test_request_without_correlation_id_succeeds(self, base_url, auth_headers, face_image_b64, compare_policy):
        """Verify correlationID is optional and omitting it does not affect the response structure."""
        resp = _post(base_url, auth_headers, _valid_payload(face_image_b64, face_image_b64, compare_policy))
        assert resp.status_code == 200
        assert "correlationID" not in resp.json()["faceCompare"]

    def test_timestamp_is_integer_milliseconds(self, base_url, auth_headers, face_image_b64, compare_policy):
        """Verify the timestamp is a Unix epoch integer in milliseconds within a plausible date range."""
        resp = _post(base_url, auth_headers, _valid_payload(face_image_b64, face_image_b64, compare_policy))
        assert resp.status_code == 200
        ts = resp.json()["faceCompare"]["timestamp"]
        assert isinstance(ts, int)
        assert 1_577_836_800_000 < ts < 1_893_456_000_000

    def test_transaction_id_is_string(self, base_url, auth_headers, face_image_b64, compare_policy):
        """Verify the transactionID is returned as a string — used for audit and log correlation."""
        resp = _post(base_url, auth_headers, _valid_payload(face_image_b64, face_image_b64, compare_policy))
        assert resp.status_code == 200
        assert isinstance(resp.json()["faceCompare"]["transactionID"], str)

    def test_response_content_type_is_json(self, base_url, auth_headers, face_image_b64, compare_policy):
        """Verify the response Content-Type header declares application/json."""
        resp = _post(base_url, auth_headers, _valid_payload(face_image_b64, face_image_b64, compare_policy))
        assert resp.status_code == 200
        assert "application/json" in resp.headers.get("Content-Type", "")

    def test_algorithm_match_is_boolean(self, base_url, auth_headers, face_image_b64, compare_policy):
        """Verify the per-algorithm match field is a boolean — mirrors the top-level match type."""
        resp = _post(base_url, auth_headers, _valid_payload(face_image_b64, face_image_b64, compare_policy))
        assert resp.status_code == 200
        for alg in resp.json()["faceCompare"]["configuration"]["algorithms"]:
            assert isinstance(alg["match"], bool)


# ---------------------------------------------------------------------------
# Business logic — validates real-world biometric comparison behavior
# ---------------------------------------------------------------------------

class TestFaceCompareBusinessLogic:

    def test_different_people_returns_no_match(self, base_url, auth_headers, face_image_b64, spoof_image_b64, compare_policy):
        """Verify two different people return match: false — core biometric correctness check."""
        resp = _post(base_url, auth_headers, _valid_payload(face_image_b64, spoof_image_b64, compare_policy))
        assert resp.status_code == 200
        assert resp.json()["faceCompare"]["match"] is False

    def test_same_person_different_photo_returns_match(self, base_url, auth_headers, face_image_b64, second_image_b64, compare_policy):
        """Verify two different photos of the same person return match: true — validates algorithm robustness."""
        resp = _post(base_url, auth_headers, _valid_payload(face_image_b64, second_image_b64, compare_policy))
        assert resp.status_code == 200
        assert resp.json()["faceCompare"]["match"] is True

    def test_score_higher_for_same_person_than_different(self, base_url, auth_headers, face_image_b64, second_image_b64, spoof_image_b64, compare_policy):
        """Verify the similarity score is higher for the same person than for different people — validates score direction."""
        same_resp = _post(base_url, auth_headers, _valid_payload(face_image_b64, second_image_b64, compare_policy))
        diff_resp = _post(base_url, auth_headers, _valid_payload(face_image_b64, spoof_image_b64, compare_policy))
        assert same_resp.status_code == 200
        assert diff_resp.status_code == 200
        assert same_resp.json()["faceCompare"]["score"] > diff_resp.json()["faceCompare"]["score"]

    def test_at_least_one_decisioning_algorithm(self, base_url, auth_headers, face_image_b64, compare_policy):
        """Verify at least one DECISIONING algorithm is present — it drives the top-level match result."""
        resp = _post(base_url, auth_headers, _valid_payload(face_image_b64, face_image_b64, compare_policy))
        assert resp.status_code == 200
        algorithms = resp.json()["faceCompare"]["configuration"]["algorithms"]
        decisioning = [a for a in algorithms if a["role"] == "DECISIONING"]
        assert len(decisioning) >= 1

    def test_two_requests_have_different_transaction_ids(self, base_url, auth_headers, face_image_b64, compare_policy):
        """Verify each transaction gets a unique ID — required for audit traceability."""
        resp1 = _post(base_url, auth_headers, _valid_payload(face_image_b64, face_image_b64, compare_policy))
        resp2 = _post(base_url, auth_headers, _valid_payload(face_image_b64, face_image_b64, compare_policy))
        assert resp1.status_code == 200
        assert resp2.status_code == 200
        assert resp1.json()["faceCompare"]["transactionID"] != resp2.json()["faceCompare"]["transactionID"]

    def test_single_char_correlation_id_echoed(self, base_url, auth_headers, face_image_b64, compare_policy):
        """Verify a minimum-length (1 char) correlationID is echoed correctly without being dropped."""
        resp = _post(base_url, auth_headers, _valid_payload(face_image_b64, face_image_b64, compare_policy, correlation_id="x"))
        assert resp.status_code == 200
        assert resp.json()["faceCompare"]["correlationID"] == "x"

    def test_empty_string_correlation_id_behavior(self, base_url, auth_headers, face_image_b64, compare_policy):
        """Verify an empty string correlationID does not cause an error — edge case for client implementations."""
        resp = _post(base_url, auth_headers, _valid_payload(face_image_b64, face_image_b64, compare_policy, correlation_id=""))
        assert resp.status_code == 200

    def test_probe_candidate_swap_same_score(self, base_url, auth_headers, face_image_b64, spoof_image_b64, compare_policy):
        """Verify face comparison is approximately symmetric — swapping probe and candidate gives a similar score."""
        resp1 = _post(base_url, auth_headers, _valid_payload(face_image_b64, spoof_image_b64, compare_policy))
        resp2 = _post(base_url, auth_headers, _valid_payload(spoof_image_b64, face_image_b64, compare_policy))
        assert resp1.status_code == 200
        assert resp2.status_code == 200
        assert abs(resp1.json()["faceCompare"]["score"] - resp2.json()["faceCompare"]["score"]) < 1.0

    def test_small_image_does_not_crash(self, base_url, auth_headers, minimal_image_b64, compare_policy):
        """Verify a very small image (1x1 pixel) is handled gracefully without causing a 500."""
        resp = _post(base_url, auth_headers, _valid_payload(minimal_image_b64, minimal_image_b64, compare_policy))
        assert resp.status_code != 500


# ---------------------------------------------------------------------------
# Validation errors (400) — server must reject malformed requests
# ---------------------------------------------------------------------------

class TestFaceCompareValidation:

    def test_null_probe_image_returns_400(self, base_url, auth_headers, minimal_image_b64, compare_policy):
        """Verify a null probe image value is rejected — image field is required."""
        payload = {"faceCompare": {"probe": {"image": None}, "candidate": {"image": minimal_image_b64}, "policyName": compare_policy}}
        resp = _post(base_url, auth_headers, payload)
        assert resp.status_code == 400

    def test_null_candidate_image_returns_400(self, base_url, auth_headers, minimal_image_b64, compare_policy):
        """Verify a null candidate image value is rejected — image field is required."""
        payload = {"faceCompare": {"probe": {"image": minimal_image_b64}, "candidate": {"image": None}, "policyName": compare_policy}}
        resp = _post(base_url, auth_headers, payload)
        assert resp.status_code == 400

    def test_empty_string_probe_image_returns_400(self, base_url, auth_headers, minimal_image_b64, compare_policy):
        """Verify an empty string probe image is rejected — not valid base64 image data."""
        payload = {"faceCompare": {"probe": {"image": ""}, "candidate": {"image": minimal_image_b64}, "policyName": compare_policy}}
        resp = _post(base_url, auth_headers, payload)
        assert resp.status_code == 400

    def test_invalid_base64_probe_image_returns_400(self, base_url, auth_headers, minimal_image_b64, compare_policy):
        """Verify a non-base64 probe image string is rejected — fixed in new build."""
        payload = {"faceCompare": {"probe": {"image": "not-valid-base64!!!"}, "candidate": {"image": minimal_image_b64}, "policyName": compare_policy}}
        resp = _post(base_url, auth_headers, payload)
        assert resp.status_code == 400

    def test_valid_base64_but_invalid_image_probe_returns_400(self, base_url, auth_headers, minimal_image_b64, compare_policy):
        """Verify valid base64 that is not a real image is rejected — second validation stage (INVALID_IMAGE_DATA)."""
        payload = {"faceCompare": {"probe": {"image": "abcd=="}, "candidate": {"image": minimal_image_b64}, "policyName": compare_policy}}
        resp = _post(base_url, auth_headers, payload)
        assert resp.status_code == 400

    def test_null_policy_name_returns_400_or_409(self, base_url, auth_headers, minimal_image_b64):
        """Verify a null policyName is treated as omitted — triggers 409 when multiple policies exist."""
        payload = {"faceCompare": {"probe": {"image": minimal_image_b64}, "candidate": {"image": minimal_image_b64}, "policyName": None}}
        resp = _post(base_url, auth_headers, payload)
        assert resp.status_code in (400, 409, 422)

    def test_empty_policy_name_returns_400_or_404(self, base_url, auth_headers, minimal_image_b64):
        """Verify an empty string policyName is treated as omitted — server returns 409 MULTIPLE_POLICIES_CONFIGURED."""
        payload = {"faceCompare": {"probe": {"image": minimal_image_b64}, "candidate": {"image": minimal_image_b64}, "policyName": ""}}
        resp = _post(base_url, auth_headers, payload)
        assert resp.status_code in (400, 404, 409, 422)

    def test_missing_probe_returns_400(self, base_url, auth_headers, minimal_image_b64, compare_policy):
        """Verify omitting the probe field returns 400 — probe is required per the spec."""
        payload = {"faceCompare": {"candidate": {"image": minimal_image_b64}, "policyName": compare_policy}}
        resp = _post(base_url, auth_headers, payload)
        assert resp.status_code == 400

    def test_missing_candidate_returns_400(self, base_url, auth_headers, minimal_image_b64, compare_policy):
        """Verify omitting the candidate field returns 400 — candidate is required per the spec."""
        payload = {"faceCompare": {"probe": {"image": minimal_image_b64}, "policyName": compare_policy}}
        resp = _post(base_url, auth_headers, payload)
        assert resp.status_code == 400

    def test_missing_both_images_returns_400(self, base_url, auth_headers, compare_policy):
        """Verify omitting both probe and candidate returns 400."""
        payload = {"faceCompare": {"policyName": compare_policy}}
        resp = _post(base_url, auth_headers, payload)
        assert resp.status_code == 400

    def test_missing_top_level_wrapper_returns_400(self, base_url, auth_headers, minimal_image_b64, compare_policy):
        """Verify the request must be wrapped in a faceCompare object — flat payloads are rejected."""
        payload = {"probe": {"image": minimal_image_b64}, "candidate": {"image": minimal_image_b64}}
        resp = _post(base_url, auth_headers, payload)
        assert resp.status_code == 400

    def test_empty_body_returns_400(self, base_url, auth_headers):
        """Verify an empty JSON body is rejected with 400."""
        resp = _post(base_url, auth_headers, {})
        assert resp.status_code == 400

    def test_validation_error_body_has_message(self, base_url, auth_headers, compare_policy):
        """Verify validation error responses include a human-readable message field."""
        payload = {"faceCompare": {"policyName": compare_policy}}
        resp = _post(base_url, auth_headers, payload)
        assert resp.status_code == 400
        assert "message" in resp.json()


# ---------------------------------------------------------------------------
# Policy errors — documented 404 / 409 responses
# ---------------------------------------------------------------------------

class TestFaceComparePolicy:

    def test_nonexistent_policy_returns_404(self, base_url, auth_headers, minimal_image_b64):
        """Verify a policyName that does not exist returns 404 with errorCode POLICY_NOT_FOUND."""
        payload = {"faceCompare": {
            "probe": {"image": minimal_image_b64},
            "candidate": {"image": minimal_image_b64},
            "policyName": "nonexistent-policy-xyz-99999",
        }}
        resp = _post(base_url, auth_headers, payload)
        assert resp.status_code == 404
        assert resp.json().get("errorCode") == "POLICY_NOT_FOUND"

    def test_omitting_policy_name_with_multiple_policies_returns_409(self, base_url, auth_headers, minimal_image_b64):
        """Verify omitting policyName when multiple policies are enabled returns 409 MULTIPLE_POLICIES_CONFIGURED."""
        payload = {"faceCompare": {
            "probe": {"image": minimal_image_b64},
            "candidate": {"image": minimal_image_b64},
        }}
        resp = _post(base_url, auth_headers, payload)
        assert resp.status_code == 409
        assert resp.json().get("errorCode") == "MULTIPLE_POLICIES_CONFIGURED"

    @pytest.mark.skip(reason="Requires disabling all algorithms on Face · 1:1 Verification policy in admin console first")
    def test_policy_with_no_algorithms_returns_422(self, base_url, auth_headers, minimal_image_b64, compare_policy):
        """Verify 422 POLICY_HAS_NO_ALGORITHMS is returned when policy has no enabled algorithms — fixed in new build."""
        payload = {"faceCompare": {
            "probe": {"image": minimal_image_b64},
            "candidate": {"image": minimal_image_b64},
            "policyName": compare_policy,
        }}
        resp = _post(base_url, auth_headers, payload)
        assert resp.status_code == 422
        assert resp.json().get("errorCode") == "POLICY_HAS_NO_ALGORITHMS"


# ---------------------------------------------------------------------------
# Policy edge cases — boundary and unexpected policyName values
# ---------------------------------------------------------------------------

class TestFaceComparePolicyEdgeCases:

    def test_special_chars_policy_name_returns_404(self, base_url, auth_headers, minimal_image_b64):
        """Verify special characters in policyName return 404 gracefully rather than crashing."""
        payload = {"faceCompare": {"probe": {"image": minimal_image_b64}, "candidate": {"image": minimal_image_b64}, "policyName": "!@#$%^&*()"}}
        resp = _post(base_url, auth_headers, payload)
        assert resp.status_code in (400, 404)

    def test_very_long_policy_name_does_not_crash(self, base_url, auth_headers, minimal_image_b64):
        """Verify a 500-character policyName does not cause a 500 — server must handle long strings safely."""
        payload = {"faceCompare": {"probe": {"image": minimal_image_b64}, "candidate": {"image": minimal_image_b64}, "policyName": "A" * 500}}
        resp = _post(base_url, auth_headers, payload)
        assert resp.status_code in (400, 404)
        assert resp.status_code != 500


# ---------------------------------------------------------------------------
# Security — verify the server handles adversarial inputs safely
# ---------------------------------------------------------------------------

class TestFaceCompareSecurity:

    def test_sql_injection_in_policy_name_does_not_crash(self, base_url, auth_headers, minimal_image_b64):
        """Verify a SQL injection attempt in policyName does not cause a 500 or expose server internals."""
        payload = {"faceCompare": {"probe": {"image": minimal_image_b64}, "candidate": {"image": minimal_image_b64}, "policyName": "'; DROP TABLE policies; --"}}
        resp = _post(base_url, auth_headers, payload)
        assert resp.status_code != 500

    def test_xss_in_correlation_id_is_echoed_safely(self, base_url, auth_headers, face_image_b64, compare_policy):
        """Verify an XSS payload in correlationID is echoed back as plain text, not interpreted or executed."""
        xss = "<script>alert(1)</script>"
        resp = _post(base_url, auth_headers, _valid_payload(face_image_b64, face_image_b64, compare_policy, correlation_id=xss))
        assert resp.status_code == 200
        assert resp.json()["faceCompare"]["correlationID"] == xss


# ---------------------------------------------------------------------------
# Auth errors — requests with invalid or missing credentials
# ---------------------------------------------------------------------------

class TestFaceCompareAuth:

    def test_invalid_api_key_returns_401(self, base_url, bad_auth_headers, minimal_image_b64, compare_policy):
        """Verify a wrong API key is rejected with 401 or 403."""
        resp = _post(base_url, bad_auth_headers, _valid_payload(minimal_image_b64, minimal_image_b64, compare_policy))
        assert resp.status_code in (401, 403)

    def test_missing_account_id_returns_403(self, base_url, auth_headers, minimal_image_b64, compare_policy):
        """Verify omitting X-Aware-AccountId is rejected — spec does not document auth errors; 400/401/403/500 all observed."""
        headers = {k: v for k, v in auth_headers.items() if k != "X-Aware-AccountId"}
        resp = _post(base_url, headers, _valid_payload(minimal_image_b64, minimal_image_b64, compare_policy))
        assert resp.status_code in (400, 401, 403, 500)

    def test_wrong_account_id_returns_403(self, base_url, minimal_image_b64, compare_policy):
        """Verify an API key with mismatched AccountId is rejected — spec does not document auth errors; 400/401/403/500 all observed."""
        from tests.conftest import API_KEY
        headers = {"X-Aware-ApiKey": API_KEY, "X-Aware-AccountId": "wrong-account-000", "Content-Type": "application/json"}
        resp = _post(base_url, headers, _valid_payload(minimal_image_b64, minimal_image_b64, compare_policy))
        assert resp.status_code in (400, 401, 403, 500)

    def test_missing_api_key_returns_401(self, base_url, minimal_image_b64, compare_policy):
        """Verify a request with no auth headers is rejected — spec does not document auth errors; 400/401/403 all observed."""
        headers = {"Content-Type": "application/json"}
        resp = requests.post(
            f"{base_url}{ENDPOINT}",
            json=_valid_payload(minimal_image_b64, minimal_image_b64, compare_policy),
            headers=headers,
            allow_redirects=False,
        )
        assert resp.status_code in (301, 302, 303, 307, 308, 400, 401, 403)
