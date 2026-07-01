"""
Fixtures and URL builders for the Tenant Preferences (Internal) API.

Auth: API-key only — no Keycloak bearer JWT required (unlike the external
retention/security-settings endpoints). Uses test02 tenant throughout.
"""

import pytest
import requests


# ---------------------------------------------------------------------------
# URL builders
# ---------------------------------------------------------------------------

def preferences_url(base_url, tenant_id, key=None, sub_key=None):
    url = f"{base_url}/v3/tenants/{tenant_id}/preferences"
    if key:
        url += f"/{key}"
    if sub_key:
        url += f"/{sub_key}"
    return url


def retention_accessor_url(base_url, tenant_id, category):
    return f"{base_url}/v3/tenants/{tenant_id}/data-retention-policy/{category}"


def security_accessor_url(base_url, tenant_id, field):
    return f"{base_url}/v3/tenants/{tenant_id}/security-settings/{field}"


def security_settings_url(base_url, tenant_id):
    return f"{base_url}/v3/tenants/{tenant_id}/security-settings"


# ---------------------------------------------------------------------------
# Tenant / auth overrides — use test02 (seeded tenant)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def tenant_id(tenant_id_2):
    """Internal API tests run against test02 (seeded tenant)."""
    return tenant_id_2


@pytest.fixture(scope="session")
def auth_headers(auth_headers_2, bearer_token):
    """Internal API requires both API key AND bearer JWT (same as external endpoints).
    NOTE: spec states API-key only — the two-layer auth requirement is a spec gap."""
    return {**auth_headers_2, "Authorization": f"Bearer {bearer_token}"}


# ---------------------------------------------------------------------------
# Preference lifecycle helpers
# ---------------------------------------------------------------------------

_TEST_KEY = "test_suite"
_TEST_SUB_KEY = "test_value"


@pytest.fixture
def created_preference(base_url, auth_headers, tenant_id):
    """Create a disposable preference row before the test; delete it after.

    Uses key=test_suite / subKey=test_value so it never conflicts with
    seeded production preferences (security_settings, data_retention_policy).
    """
    url = preferences_url(base_url, tenant_id, _TEST_KEY, _TEST_SUB_KEY)
    requests.delete(url, headers=auth_headers, timeout=10)
    r = requests.post(
        url,
        json={"value": "initial_value", "valueType": "STRING"},
        headers=auth_headers,
        timeout=10,
    )
    assert r.status_code == 201, f"Test setup failed: {r.status_code} {r.text}"
    yield r.json()
    requests.delete(url, headers=auth_headers, timeout=10)


@pytest.fixture(scope="session")
def current_session_timeout(base_url, auth_headers, tenant_id):
    """Snapshot the session timeout before the session; restore after."""
    url = security_accessor_url(base_url, tenant_id, "session_timeout_minutes")
    snap = requests.get(url, headers=auth_headers, timeout=10).json()
    yield snap
    requests.put(url, json=snap, headers=auth_headers, timeout=10)


@pytest.fixture(scope="session")
def current_password_reset_lifetime(base_url, auth_headers, tenant_id):
    """Snapshot the password reset lifetime before the session; restore after."""
    url = security_accessor_url(base_url, tenant_id, "password_reset_link_lifetime")
    snap = requests.get(url, headers=auth_headers, timeout=10).json()
    yield snap
    requests.put(url, json=snap, headers=auth_headers, timeout=10)


@pytest.fixture
def current_retention_category(base_url, auth_headers, tenant_id):
    """Snapshot+restore templates retention for tests that modify it."""
    url = retention_accessor_url(base_url, tenant_id, "templates")
    snap = requests.get(url, headers=auth_headers, timeout=10).json()
    yield snap
    requests.put(url, json=snap, headers=auth_headers, timeout=10)


@pytest.fixture
def current_security_settings(base_url, auth_headers, tenant_id):
    """Snapshot+restore the bulk security-settings object for tests that modify it."""
    url = security_settings_url(base_url, tenant_id)
    snap = requests.get(url, headers=auth_headers, timeout=10).json()
    yield snap
    requests.put(url, json=snap, headers=auth_headers, timeout=10)
