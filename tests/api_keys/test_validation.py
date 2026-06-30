"""
Public / gateway-facing API key validation endpoints.

  GET /v3/apiKeys/validate               — validate key passed via X-Aware-ApiKey header
  GET /v3/apiKeys/{rawApiKey}/lookup     — resolve raw key to key object (no auth required?)
  GET /v3/apiKeys/{rawApiKey}/lookupAndValidate — resolve + validate (bearer required)
"""

import uuid
import requests
import pytest

BASE_VALIDATE = "/v3/apiKeys/validate"


def validate_url(base_url):
    return f"{base_url}{BASE_VALIDATE}"


def lookup_url(base_url, raw_key):
    return f"{base_url}/v3/apiKeys/{raw_key}/lookup"


def lookup_and_validate_url(base_url, raw_key):
    return f"{base_url}/v3/apiKeys/{raw_key}/lookupAndValidate"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def active_key(base_url, tenant_id, mgmt_headers):
    """Create a fresh ACTIVE key; yield (key_obj, secret); cleanup after test."""
    from tests.api_keys.conftest import api_keys_url, valid_create_payload
    resp = requests.post(
        api_keys_url(base_url, tenant_id),
        json=valid_create_payload(name=f"val-{uuid.uuid4().hex[:8]}"),
        headers=mgmt_headers,
    )
    assert resp.status_code == 200
    key = resp.json()
    secret = key["apiKey"]
    yield key, secret
    requests.delete(api_keys_url(base_url, tenant_id, key["id"]), headers=mgmt_headers)


@pytest.fixture
def inactive_key(base_url, tenant_id, mgmt_headers):
    """Create a key then soft-delete it; yield (key_obj, secret)."""
    from tests.api_keys.conftest import api_keys_url, valid_create_payload
    resp = requests.post(
        api_keys_url(base_url, tenant_id),
        json=valid_create_payload(name=f"val-inactive-{uuid.uuid4().hex[:6]}"),
        headers=mgmt_headers,
    )
    assert resp.status_code == 200
    key = resp.json()
    secret = key["apiKey"]
    requests.delete(api_keys_url(base_url, tenant_id, key["id"]), headers=mgmt_headers)
    yield key, secret


# ---------------------------------------------------------------------------
# 1. GET /v3/apiKeys/validate
# ---------------------------------------------------------------------------

class TestValidate:

    def test_valid_active_key_returns_200(self, base_url, active_key):
        _, secret = active_key
        resp = requests.get(
            validate_url(base_url),
            headers={"X-Aware-ApiKey": secret, "X-Aware-AccountId": "0001"},
        )
        assert resp.status_code == 200, f"Expected 200 for valid key, got {resp.status_code}"

    def test_valid_key_returns_json_body(self, base_url, active_key):
        """200 response must include a structured JSON body, not empty string."""
        _, secret = active_key
        resp = requests.get(
            validate_url(base_url),
            headers={"X-Aware-ApiKey": secret, "X-Aware-AccountId": "0001"},
        )
        assert resp.status_code == 200
        assert resp.text.strip() != "", (
            "validate returned 200 with empty body — must return structured JSON"
        )
        body = resp.json()
        assert isinstance(body, dict), f"Expected JSON object, got: {resp.text[:200]}"

    def test_valid_key_response_has_content_type(self, base_url, active_key):
        """200 response must include Content-Type: application/json."""
        _, secret = active_key
        resp = requests.get(
            validate_url(base_url),
            headers={"X-Aware-ApiKey": secret, "X-Aware-AccountId": "0001"},
        )
        assert resp.status_code == 200
        ct = resp.headers.get("Content-Type", "")
        assert "application/json" in ct, (
            f"Missing Content-Type header on 200 response — got: '{ct}'"
        )

    def test_inactive_key_returns_401(self, base_url, inactive_key):
        """Soft-deleted (INACTIVE) key must be rejected by validate."""
        _, secret = inactive_key
        resp = requests.get(
            validate_url(base_url),
            headers={"X-Aware-ApiKey": secret, "X-Aware-AccountId": "0001"},
        )
        assert resp.status_code == 401, (
            f"INACTIVE key returned {resp.status_code} on validate — expected 401"
        )

    def test_unknown_key_returns_401(self, base_url):
        resp = requests.get(
            validate_url(base_url),
            headers={"X-Aware-ApiKey": "0" * 64, "X-Aware-AccountId": "0001"},
        )
        assert resp.status_code == 401

    def test_missing_api_key_header_returns_401(self, base_url):
        resp = requests.get(validate_url(base_url), headers={"X-Aware-AccountId": "0001"})
        assert resp.status_code == 401

    def test_missing_account_id_returns_401(self, base_url, active_key):
        _, secret = active_key
        resp = requests.get(
            validate_url(base_url),
            headers={"X-Aware-ApiKey": secret},
        )
        assert resp.status_code in (401, 403)

    def test_no_auth_returns_401(self, base_url):
        resp = requests.get(validate_url(base_url))
        assert resp.status_code == 401

    def test_401_response_has_error_body(self, base_url):
        """401 must include a structured error body, not empty string."""
        resp = requests.get(
            validate_url(base_url),
            headers={"X-Aware-ApiKey": "0" * 64, "X-Aware-AccountId": "0001"},
        )
        assert resp.status_code == 401
        assert resp.text.strip() != "", (
            "validate returned 401 with empty body — must include error message"
        )
        body = resp.json()
        assert "error" in body or "message" in body, (
            f"401 body has no error/message field: {body}"
        )


# ---------------------------------------------------------------------------
# 2. GET /v3/apiKeys/{rawApiKey}/lookup
# ---------------------------------------------------------------------------

class TestLookup:

    def test_lookup_requires_authentication(self, base_url, active_key):
        """
        CRITICAL BUG: lookup must require authentication.
        Currently returns 200 with full key metadata when called with no headers.
        Anyone who intercepts a raw API key can resolve the full key object
        (keyName, description, tenantId, status) without any credentials.
        """
        _, secret = active_key
        resp = requests.get(lookup_url(base_url, secret))
        assert resp.status_code in (401, 403), (
            f"lookup returned {resp.status_code} with NO auth — "
            f"full key metadata exposed without credentials: {resp.text[:300]}"
        )

    def test_lookup_with_valid_auth_returns_200(self, base_url, active_key, mgmt_headers):
        """lookup with valid management credentials returns key object."""
        _, secret = active_key
        resp = requests.get(lookup_url(base_url, secret), headers=mgmt_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body.get("status") == "ACTIVE"

    def test_lookup_does_not_expose_secret(self, base_url, active_key, mgmt_headers):
        """apiKey field must be null in lookup response."""
        _, secret = active_key
        resp = requests.get(lookup_url(base_url, secret), headers=mgmt_headers)
        assert resp.status_code == 200
        assert resp.json().get("apiKey") is None

    def test_lookup_inactive_key_returns_404(self, base_url, inactive_key, mgmt_headers):
        """
        BUG: lookup on INACTIVE key returns 200 — should return 404.
        A soft-deleted key must not be resolvable.
        """
        _, secret = inactive_key
        resp = requests.get(lookup_url(base_url, secret), headers=mgmt_headers)
        assert resp.status_code == 404, (
            f"lookup on INACTIVE key returned {resp.status_code} — "
            f"expected 404. Body: {resp.text[:200]}"
        )

    def test_lookup_unknown_key_returns_401_or_404(self, base_url, mgmt_headers):
        resp = requests.get(lookup_url(base_url, "0" * 64), headers=mgmt_headers)
        assert resp.status_code in (401, 404)

    def test_lookup_bearer_only_returns_403(self, base_url, active_key, bearer_headers):
        """bearer-only (no X-Aware-ApiKey) must be rejected."""
        _, secret = active_key
        resp = requests.get(lookup_url(base_url, secret), headers=bearer_headers)
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# 3. GET /v3/apiKeys/{rawApiKey}/lookupAndValidate
# ---------------------------------------------------------------------------

class TestLookupAndValidate:

    def test_valid_active_key_with_mgmt_headers_returns_200(
        self, base_url, active_key, mgmt_headers
    ):
        _, secret = active_key
        resp = requests.get(lookup_and_validate_url(base_url, secret), headers=mgmt_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body.get("status") == "ACTIVE"

    def test_response_does_not_expose_secret(self, base_url, active_key, mgmt_headers):
        _, secret = active_key
        resp = requests.get(lookup_and_validate_url(base_url, secret), headers=mgmt_headers)
        assert resp.status_code == 200
        assert resp.json().get("apiKey") is None

    def test_inactive_key_returns_401(self, base_url, inactive_key, mgmt_headers):
        """INACTIVE key must be rejected by lookupAndValidate."""
        _, secret = inactive_key
        resp = requests.get(lookup_and_validate_url(base_url, secret), headers=mgmt_headers)
        assert resp.status_code in (401, 404), (
            f"INACTIVE key returned {resp.status_code} on lookupAndValidate — "
            "deleted keys must be rejected"
        )

    def test_no_auth_returns_401(self, base_url, active_key):
        _, secret = active_key
        resp = requests.get(lookup_and_validate_url(base_url, secret))
        assert resp.status_code == 401

    def test_bearer_only_returns_403(self, base_url, active_key, bearer_headers):
        _, secret = active_key
        resp = requests.get(lookup_and_validate_url(base_url, secret), headers=bearer_headers)
        assert resp.status_code == 403

    def test_unknown_key_returns_401_or_404(self, base_url, mgmt_headers):
        resp = requests.get(lookup_and_validate_url(base_url, "0" * 64), headers=mgmt_headers)
        assert resp.status_code in (401, 404)


# ---------------------------------------------------------------------------
# 4. Cross-endpoint consistency
# ---------------------------------------------------------------------------

class TestCrossEndpointConsistency:

    def test_error_format_consistent_across_endpoints(self, base_url):
        """
        BUG: 401 error format is inconsistent across the three endpoints.
        validate/lookup return empty body; lookupAndValidate returns JSON error object.
        All must return the same structured error format.
        """
        r_validate = requests.get(
            validate_url(base_url),
            headers={"X-Aware-ApiKey": "0" * 64, "X-Aware-AccountId": "0001"},
        )
        r_lookup = requests.get(lookup_url(base_url, "0" * 64))
        r_lav = requests.get(lookup_and_validate_url(base_url, "0" * 64))

        validate_has_body = r_validate.text.strip() != ""
        lookup_has_body = r_lookup.text.strip() != ""
        lav_has_body = r_lav.text.strip() != ""

        assert validate_has_body == lookup_has_body == lav_has_body, (
            f"Inconsistent 401 error bodies across endpoints:\n"
            f"  validate body: '{r_validate.text[:100]}'\n"
            f"  lookup body:   '{r_lookup.text[:100]}'\n"
            f"  lav body:      '{r_lav.text[:100]}'"
        )

    def test_all_endpoints_reject_inactive_key_consistently(
        self, base_url, inactive_key, mgmt_headers
    ):
        """
        All three endpoints must consistently reject an INACTIVE key.
        Currently lookup returns 200 for INACTIVE keys while validate/lookupAndValidate reject them.
        """
        _, secret = inactive_key

        r_validate = requests.get(
            validate_url(base_url),
            headers={"X-Aware-ApiKey": secret, "X-Aware-AccountId": "0001"},
        )
        r_lookup = requests.get(lookup_url(base_url, secret), headers=mgmt_headers)
        r_lav = requests.get(lookup_and_validate_url(base_url, secret), headers=mgmt_headers)

        validate_ok = r_validate.status_code in (401, 403, 404)
        lookup_ok = r_lookup.status_code in (401, 403, 404)
        lav_ok = r_lav.status_code in (401, 403, 404)

        assert validate_ok and lookup_ok and lav_ok, (
            f"Inconsistent INACTIVE key handling:\n"
            f"  validate -> {r_validate.status_code}\n"
            f"  lookup   -> {r_lookup.status_code}\n"
            f"  lav      -> {r_lav.status_code}"
        )
