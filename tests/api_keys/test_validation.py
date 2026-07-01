"""
Internal / mesh-only API key validation endpoints.

  GET /v3/apiKeys/validate                       — OPA ext-authz: validate X-Aware-ApiKey header
  GET /v3/apiKeys/{rawApiKey}/lookup             — provider-gateway: resolve raw key to metadata
  GET /v3/apiKeys/{rawApiKey}/lookupAndValidate  — combined lookup + active/expiry check

All three endpoints have security: [] in the spec — exempt from OPA/AwareAuthInterceptor.
Network-level trust is enforced by Istio; only intra-mesh traffic should reach them.
Spec-defined response bodies:
  validate 200/401: no body defined
  lookup/lookupAndValidate 200: ApiKeyResponse; 401: no body defined
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

    def test_valid_key_returns_no_body(self, base_url, active_key):
        """Spec-defined: validate 200 has no response body (status-only signal for OPA)."""
        _, secret = active_key
        resp = requests.get(
            validate_url(base_url),
            headers={"X-Aware-ApiKey": secret},
        )
        assert resp.status_code == 200
        assert resp.text.strip() == "", (
            f"validate 200 should have no body per spec, got: {resp.text[:200]}"
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

    def test_account_id_not_required(self, base_url, active_key):
        """Spec-defined: validate only takes X-Aware-ApiKey; AccountId is not a parameter."""
        _, secret = active_key
        resp = requests.get(
            validate_url(base_url),
            headers={"X-Aware-ApiKey": secret},
        )
        assert resp.status_code == 200, (
            f"validate without AccountId should return 200 (AccountId not required per spec), "
            f"got {resp.status_code}"
        )

    def test_no_auth_returns_401(self, base_url):
        resp = requests.get(validate_url(base_url))
        assert resp.status_code == 401

    def test_401_response_has_no_body(self, base_url):
        """Spec-defined: validate 401 has no response body (status-only signal for OPA)."""
        resp = requests.get(
            validate_url(base_url),
            headers={"X-Aware-ApiKey": "0" * 64},
        )
        assert resp.status_code == 401
        assert resp.text.strip() == "", (
            f"validate 401 should have no body per spec, got: {resp.text[:200]}"
        )


# ---------------------------------------------------------------------------
# 2. GET /v3/apiKeys/{rawApiKey}/lookup
# ---------------------------------------------------------------------------

class TestLookup:

    def test_lookup_is_unauthenticated_by_design(self, base_url, active_key):
        """Spec-defined: lookup has security: [] — no auth required, Istio mesh-trust only."""
        _, secret = active_key
        resp = requests.get(lookup_url(base_url, secret))
        assert resp.status_code == 200, (
            f"lookup without auth should return 200 (unauthenticated by design per spec), "
            f"got {resp.status_code}"
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

    def test_lookup_inactive_key_returns_401(self, base_url, inactive_key, mgmt_headers):
        """Spec-defined: lookup returns 401 for keys that are unknown or not active."""
        _, secret = inactive_key
        resp = requests.get(lookup_url(base_url, secret), headers=mgmt_headers)
        assert resp.status_code == 401, (
            f"lookup on INACTIVE key returned {resp.status_code} — "
            f"expected 401 per spec. Body: {resp.text[:200]}"
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

    def test_internal_endpoints_all_reject_unknown_key(self, base_url):
        """All three internal endpoints must reject an unknown key with 401."""
        r_validate = requests.get(
            validate_url(base_url),
            headers={"X-Aware-ApiKey": "0" * 64},
        )
        r_lookup = requests.get(lookup_url(base_url, "0" * 64))
        r_lav = requests.get(lookup_and_validate_url(base_url, "0" * 64))

        assert r_validate.status_code == 401, f"validate: expected 401, got {r_validate.status_code}"
        assert r_lookup.status_code == 401, f"lookup: expected 401, got {r_lookup.status_code}"
        assert r_lav.status_code == 401, f"lookupAndValidate: expected 401, got {r_lav.status_code}"

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
