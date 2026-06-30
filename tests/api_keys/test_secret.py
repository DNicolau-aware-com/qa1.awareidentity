"""
GET /v3/tenants/{tenantId}/apiKeys/{id}/secret — fetch secret endpoint.

CRITICAL BUG (AWRNSS-386 violation):
  This endpoint returns the plaintext secret at any time after creation.
  Requirement: "API key secrets must never be displayed after initial creation."
  Actual: GET /{id}/secret returns {"secret": "<plaintext>"} — fully recoverable.

POST /v3/tenants/{tenantId}/apiKeys/{id}/rotate-credentials — rotate key.
  Returns a new plaintext secret in the `apiKey` field.
  Old secret is invalidated; new secret is set.
"""

import uuid
import requests
import pytest

from tests.api_keys.conftest import api_keys_url, valid_create_payload


class TestSecretEndpoint:

    def test_secret_endpoint_should_not_exist(self, base_url, tenant_id, mgmt_headers, created_key):
        """
        GET /{id}/secret must not expose the secret after creation.
        Expected: 404 (endpoint should not exist) or 405 (method not allowed).
        Actual: 200 with {'secret': '<plaintext>'} — critical security violation.
        """
        resp = requests.get(
            api_keys_url(base_url, tenant_id, created_key["id"], sub="secret"),
            headers=mgmt_headers,
        )
        assert resp.status_code in (404, 405), (
            f"Secret endpoint should not be reachable. Got {resp.status_code}: {resp.text[:200]}"
        )

    def test_secret_endpoint_currently_returns_200(self, base_url, tenant_id, mgmt_headers, created_key):
        """Documents the current (buggy) behavior — secret is retrievable post-creation."""
        resp = requests.get(
            api_keys_url(base_url, tenant_id, created_key["id"], sub="secret"),
            headers=mgmt_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "secret" in body, f"Expected 'secret' field in response, got: {list(body.keys())}"
        assert len(body["secret"]) > 20, "Secret looks too short to be real"

    def test_secret_endpoint_nonexistent_key_returns_404(self, base_url, tenant_id, mgmt_headers):
        resp = requests.get(
            api_keys_url(base_url, tenant_id, str(uuid.uuid4()), sub="secret"),
            headers=mgmt_headers,
        )
        assert resp.status_code == 404

    def test_secret_endpoint_requires_auth(self, base_url, tenant_id, auth_headers, created_key):
        """Secret endpoint must require bearer — not accessible with API key alone."""
        resp = requests.get(
            api_keys_url(base_url, tenant_id, created_key["id"], sub="secret"),
            headers=auth_headers,
        )
        assert resp.status_code == 401

    def test_secret_matches_original_api_key(self, base_url, tenant_id, mgmt_headers):
        """The secret returned by GET /secret must match the apiKey from creation."""
        resp = requests.post(
            api_keys_url(base_url, tenant_id),
            json=valid_create_payload(name=f"secret-match-{uuid.uuid4().hex[:6]}"),
            headers=mgmt_headers,
        )
        assert resp.status_code == 200
        key = resp.json()
        key_id = key["id"]
        original_secret = key.get("apiKey")

        secret_resp = requests.get(
            api_keys_url(base_url, tenant_id, key_id, sub="secret"),
            headers=mgmt_headers,
        )
        returned_secret = secret_resp.json().get("secret")
        requests.delete(api_keys_url(base_url, tenant_id, key_id), headers=mgmt_headers)

        assert original_secret == returned_secret, (
            f"Secret from GET /secret doesn't match creation response — "
            f"original: {original_secret!r}, returned: {returned_secret!r}"
        )


class TestRotateCredentials:

    def test_rotate_returns_200_with_new_secret(self, base_url, tenant_id, mgmt_headers, created_key):
        """POST /rotate-credentials returns a new secret in the apiKey field."""
        resp = requests.post(
            api_keys_url(base_url, tenant_id, created_key["id"], sub="rotate-credentials"),
            headers=mgmt_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        new_secret = body.get("apiKey")
        assert new_secret is not None, "rotate-credentials must return new secret in apiKey field"
        assert len(str(new_secret)) > 20

    def test_rotate_keeps_same_key_id(self, base_url, tenant_id, mgmt_headers, created_key):
        """Rotation creates a new secret but preserves the key ID."""
        original_id = created_key["id"]
        resp = requests.post(
            api_keys_url(base_url, tenant_id, original_id, sub="rotate-credentials"),
            headers=mgmt_headers,
        )
        assert resp.json().get("id") == original_id

    def test_rotate_changes_prefix_and_suffix(self, base_url, tenant_id, mgmt_headers, created_key):
        """New secret has different prefix/suffix than original."""
        original_prefix = created_key.get("keyPrefix")
        resp = requests.post(
            api_keys_url(base_url, tenant_id, created_key["id"], sub="rotate-credentials"),
            headers=mgmt_headers,
        )
        new_prefix = resp.json().get("keyPrefix")
        assert new_prefix != original_prefix, (
            "keyPrefix unchanged after rotation — new secret may be same as old"
        )

    def test_rotate_new_secret_different_from_original(self, base_url, tenant_id, mgmt_headers):
        """New secret after rotation must differ from original creation secret."""
        resp = requests.post(
            api_keys_url(base_url, tenant_id),
            json=valid_create_payload(name=f"rotate-diff-{uuid.uuid4().hex[:6]}"),
            headers=mgmt_headers,
        )
        key_id = resp.json()["id"]
        original_secret = resp.json().get("apiKey")

        rotate_resp = requests.post(
            api_keys_url(base_url, tenant_id, key_id, sub="rotate-credentials"),
            headers=mgmt_headers,
        )
        new_secret = rotate_resp.json().get("apiKey")
        requests.delete(api_keys_url(base_url, tenant_id, key_id), headers=mgmt_headers)

        assert original_secret != new_secret, "New secret after rotation must differ from original"

    def test_rotate_nonexistent_key_returns_404(self, base_url, tenant_id, mgmt_headers):
        resp = requests.post(
            api_keys_url(base_url, tenant_id, str(uuid.uuid4()), sub="rotate-credentials"),
            headers=mgmt_headers,
        )
        assert resp.status_code == 404

    def test_rotate_requires_auth(self, base_url, tenant_id, auth_headers, created_key):
        """rotate-credentials must require bearer — not accessible with API key alone."""
        resp = requests.post(
            api_keys_url(base_url, tenant_id, created_key["id"], sub="rotate-credentials"),
            headers=auth_headers,
        )
        assert resp.status_code == 401
