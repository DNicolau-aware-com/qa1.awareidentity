"""
Shared fixtures and helpers for API Key Management tests (AWRNSS-423).

ENDPOINT MAP (confirmed against qa2):
  GET    /v3/tenants/{tenantId}/apiKeys              — list (paginated, envelope: content[])
  POST   /v3/tenants/{tenantId}/apiKeys              — create (returns apiKey secret once, HTTP 200)
  GET    /v3/tenants/{tenantId}/apiKeys/{id}         — get single
  PATCH  /v3/tenants/{tenantId}/apiKeys/{id}         — update (field: keyStatus) [BUG: no effect]
  DELETE /v3/tenants/{tenantId}/apiKeys/{id}         — soft-delete → status INACTIVE (HTTP 204)
  POST   /v3/tenants/{tenantId}/apiKeys/{id}/rotate-credentials — new secret, same ID
  GET    /v3/tenants/{tenantId}/apiKeys/{id}/secret  — returns {"secret": "..."} [BUG: violates one-time display]

AUTH MODEL: Bearer JWT + X-Aware-ApiKey + X-Aware-AccountId (all three required)
  Missing bearer   -> 401
  Malformed bearer -> 403
  Bearer only      -> 403 (app layer also needs API key)
  All three valid  -> 200

RESPONSE FIELDS (flat, no wrapper envelope):
  id, keyName, description, apiKey (secret—only on create/rotate), keyPrefix, keySuffix,
  status (ACTIVE / INACTIVE), visibility (PERSONAL / ORGANIZATION),
  userId, tenantId, expiresAt, lastUsedAt, createdAt, updatedAt
"""

import uuid
import pytest
import requests


# ---------------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------------

def api_keys_url(base_url, tenant_id, key_id=None, sub=None):
    path = f"/v3/tenants/{tenant_id}/apiKeys"
    if key_id:
        path = f"{path}/{key_id}"
    if sub:
        path = f"{path}/{sub}"
    return f"{base_url}{path}"


def valid_create_payload(name=None, description=None, visibility="ORGANIZATION"):
    return {
        "keyName": name or f"test-key-{uuid.uuid4().hex[:8]}",
        "description": description or "Created by automated test suite",
        "visibility": visibility,
    }


# ---------------------------------------------------------------------------
# Auth fixtures — bearer + API key (two-layer, same as retention)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def mgmt_headers(bearer_token, auth_headers):
    """Combined auth: Keycloak bearer JWT + X-Aware-ApiKey + X-Aware-AccountId."""
    return {
        **auth_headers,
        "Authorization": f"Bearer {bearer_token}",
    }


# ---------------------------------------------------------------------------
# Key lifecycle fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def created_key(base_url, tenant_id, mgmt_headers):
    """Create a fresh API key and soft-delete it on teardown."""
    resp = requests.post(
        api_keys_url(base_url, tenant_id),
        json=valid_create_payload(),
        headers=mgmt_headers,
    )
    assert resp.status_code == 200, f"API key fixture create failed: {resp.status_code} {resp.text}"
    key = resp.json()
    yield key
    key_id = key.get("id")
    if key_id:
        requests.delete(api_keys_url(base_url, tenant_id, key_id), headers=mgmt_headers)


@pytest.fixture
def two_active_keys(base_url, tenant_id, mgmt_headers):
    """Create two API keys and soft-delete both on teardown."""
    keys = []
    for i in range(2):
        resp = requests.post(
            api_keys_url(base_url, tenant_id),
            json=valid_create_payload(name=f"rotation-test-{i}-{uuid.uuid4().hex[:6]}"),
            headers=mgmt_headers,
        )
        assert resp.status_code == 200, f"Key {i} create failed: {resp.status_code} {resp.text}"
        keys.append(resp.json())
    yield keys
    for k in keys:
        kid = k.get("id")
        if kid:
            requests.delete(api_keys_url(base_url, tenant_id, kid), headers=mgmt_headers)
