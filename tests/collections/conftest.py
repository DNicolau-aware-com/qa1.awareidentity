"""
Shared fixtures and helpers for biometric collections tests.
All test files under tests/collections/ inherit these automatically.
"""

import uuid
import requests
import pytest


def collection_url(base_url, tenant_id, collection_id=None):
    path = f"/v3/tenants/{tenant_id}/collections"
    if collection_id:
        path = f"{path}/{collection_id}"
    return f"{base_url}{path}"


def create_payload(name=None, **overrides):
    inner = {
        "name": name or f"test-collection-{uuid.uuid4().hex[:8]}",
        "storageType": "STANDARD",
        "createdBy": "test@aware.com",
    }
    inner.update(overrides)
    return {"biometricCollection": inner}


@pytest.fixture
def new_collection(base_url, auth_headers, tenant_id):
    """Create a fresh collection for a test and delete it on teardown."""
    resp = requests.post(collection_url(base_url, tenant_id), json=create_payload(), headers=auth_headers)
    assert resp.status_code == 201, f"Fixture setup failed: {resp.status_code} {resp.text}"
    c = resp.json()["biometricCollection"]
    yield c
    requests.delete(collection_url(base_url, tenant_id, c["id"]), headers=auth_headers)
