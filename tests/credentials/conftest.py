"""
Shared fixtures and helpers for biometric credentials tests.
"""

import uuid
import requests
import pytest

# Minimal 1×1 PNG in base64 — used as dummy image data for entry tests.
# If the server validates biometric image content, entry tests will skip.
_DUMMY_IMAGE_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk"
    "+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


def credential_url(base_url, tenant_id, collection_id, credential_id=None):
    path = f"/v3/tenants/{tenant_id}/collections/{collection_id}/credentials"
    if credential_id:
        path = f"{path}/{credential_id}"
    return f"{base_url}{path}"


def entry_url(base_url, tenant_id, collection_id, credential_id, entry_id=None):
    path = (
        f"/v3/tenants/{tenant_id}/collections/{collection_id}"
        f"/credentials/{credential_id}/credentialentries"
    )
    if entry_id:
        path = f"{path}/{entry_id}"
    return f"{base_url}{path}"


def collection_url(base_url, tenant_id, collection_id=None):
    path = f"/v3/tenants/{tenant_id}/collections"
    if collection_id:
        path = f"{path}/{collection_id}"
    return f"{base_url}{path}"


def create_collection_payload(name=None):
    return {
        "biometricCollection": {
            "name": name or f"test-coll-{uuid.uuid4().hex[:8]}",
            "storageType": "STANDARD",
            "createdBy": "test@aware.com",
        }
    }


def create_credential_payload(external_user_id=None, **overrides):
    """Minimal valid credential payload. createdBy is optional per spec."""
    inner = {
        "externalUserId": external_user_id or f"user-{uuid.uuid4().hex[:8]}",
        "biometrics": {},
    }
    inner.update(overrides)
    return {"biometricCredential": inner}


@pytest.fixture(scope="module")
def collection_id(base_url, auth_headers, tenant_id):
    """Create a collection for the module and delete it on teardown."""
    resp = requests.post(
        collection_url(base_url, tenant_id),
        json=create_collection_payload(),
        headers=auth_headers,
    )
    assert resp.status_code == 201, f"Collection fixture setup failed: {resp.status_code} {resp.text}"
    cid = resp.json()["biometricCollection"]["id"]
    yield cid
    requests.delete(collection_url(base_url, tenant_id, cid), headers=auth_headers)


@pytest.fixture
def new_credential(base_url, auth_headers, tenant_id, collection_id):
    """Create a fresh credential and delete it on teardown."""
    resp = requests.post(
        credential_url(base_url, tenant_id, collection_id),
        json=create_credential_payload(),
        headers=auth_headers,
    )
    assert resp.status_code == 201, f"Credential fixture setup failed: {resp.status_code} {resp.text}"
    cred = resp.json()["biometricCredential"]
    yield cred
    requests.delete(credential_url(base_url, tenant_id, collection_id, cred["id"]), headers=auth_headers)
