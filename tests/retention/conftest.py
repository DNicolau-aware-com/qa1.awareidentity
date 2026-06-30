"""
Shared fixtures and helpers for data retention policy tests.
All test files under tests/retention/ inherit these automatically.

AUTH MODEL (discovered against qa2):
  These endpoints sit behind a TWO-LAYER auth scheme, unlike the rest of v3:
    1. Gateway (Istio): a Keycloak bearer JWT in `Authorization`.
         missing      -> 401 "Missing or invalid Authorization header"
         malformed    -> 400 "Cannot derive JWKS URL ..."
    2. App: the `X-Aware-ApiKey` (+ `X-Aware-AccountId`) headers.
         missing/bad  -> 403
         valid        -> 200
  Both layers must pass. The token is minted from Keycloak (see root conftest
  `bearer_token`). The suite runs against the test02 tenant/realm, whose API key
  and bearer realm line up.

  NOTE: with a valid bearer present, the app does NOT reject a mismatched
  X-Aware-AccountId (account 9999 still returns 200) — so there is no 403
  account-mismatch case for these endpoints.
"""
import copy
import requests
import pytest


# ---------------------------------------------------------------------------
# Auth/tenant overrides — shadow the root fixtures for everything under
# tests/retention/. The retention endpoints need bearer + API key together,
# and are exercised against the test02 tenant (matching the bearer's realm).
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def tenant_id(tenant_id_2):
    """Retention endpoints are JWT-gated per realm; test against test02."""
    return tenant_id_2


@pytest.fixture(scope="session")
def auth_headers(auth_headers_2, bearer_token):
    """Combined two-layer auth: test02 API key/account + Keycloak bearer JWT."""
    return {**auth_headers_2, "Authorization": f"Bearer {bearer_token}"}


def retention_url(base_url, tenant_id):
    return f"{base_url}/v3/tenants/{tenant_id}/data-retention-policy"


def valid_policy(
    templates_max=30,
    enrollment_max=7,
    logs_max=1,
    templates_auto_delete=True,
    enrollment_auto_delete=True,
    logs_auto_delete=True,
    salt_logs=False,
):
    """Return a structurally valid retention policy with conservative values that should
    fit within any environment's system ceilings.  Use this only in auth / path-param
    tests where the payload must look valid but the server will reject on auth before
    reaching business-rule validation.  For any test that actually hits 200, base the
    payload on the `current_policy` fixture instead."""
    return {
        "templates": {
            "maxRetentionDays": templates_max,
            "autoDeleteExpired": templates_auto_delete,
            "modalities": {
                "Face": templates_max,
                "Voice": templates_max,
                "Iris": templates_max,
                "Fingerprint": templates_max,
            },
        },
        "enrollmentImages": {
            "maxRetentionDays": enrollment_max,
            "autoDeleteExpired": enrollment_auto_delete,
            "modalities": {
                "Face": enrollment_max,
                "Voice": enrollment_max,
                "Iris": enrollment_max,
                "Fingerprint": enrollment_max,
            },
        },
        "logs": {
            "maxRetentionDays": logs_max,
            "autoDeleteExpired": logs_auto_delete,
            "modalities": {
                "Face": logs_max,
                "Voice": logs_max,
                "Iris": logs_max,
                "Fingerprint": logs_max,
            },
        },
        "saltLogsToRemovePii": salt_logs,
    }


@pytest.fixture
def current_policy(base_url, auth_headers, tenant_id):
    """Snapshot the tenant's current retention policy and restore it after the test.

    Yields a deep copy of the live policy so tests can mutate it freely.
    The teardown always restores from the original snapshot, regardless of what
    the test does to the yielded object.
    """
    resp = requests.get(retention_url(base_url, tenant_id), headers=auth_headers)
    assert resp.status_code == 200, f"Fixture GET failed: {resp.status_code} {resp.text}"
    snapshot = resp.json()
    yield copy.deepcopy(snapshot)
    # Restore: strip the read-only systemMaxRetentionDays before PUT
    restore = {k: v for k, v in snapshot.items() if k != "systemMaxRetentionDays"}
    requests.put(retention_url(base_url, tenant_id), json=restore, headers=auth_headers)


@pytest.fixture(scope="session")
def system_ceilings(base_url, auth_headers, tenant_id):
    """Fetch systemMaxRetentionDays once per session for boundary-value tests."""
    resp = requests.get(retention_url(base_url, tenant_id), headers=auth_headers)
    assert resp.status_code == 200, f"System ceilings fetch failed: {resp.status_code} {resp.text}"
    ceilings = resp.json().get("systemMaxRetentionDays", {})
    assert ceilings, "systemMaxRetentionDays missing from GET response"
    return ceilings
