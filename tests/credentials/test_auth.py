"""
Auth tests for all /v3/tenants/{tenantId}/collections/{collectionId}/credentials endpoints.

Per spec:
  - Invalid/unknown API key                          → 401 UNAUTHORIZED
  - Missing X-Aware-ApiKey or X-Aware-AccountId     → 401 UNAUTHORIZED
  - API key valid but X-Aware-AccountId mismatch    → 403 FORBIDDEN
  - 401 responses must include WWW-Authenticate: ApiKey realm="aware"
"""

import uuid
import requests

from tests.credentials.conftest import credential_url


class TestCredentialsAuth:

    # ------------------------------------------------------------------
    # Invalid API key → 401
    # [BUG] Currently returns 403 instead of 401 — MUST FAIL until fixed.
    # ------------------------------------------------------------------

    def test_invalid_api_key_on_post_returns_401(self, base_url, tenant_id, collection_id):
        """Invalid API key returns 401 on POST."""
        headers = {"X-Aware-ApiKey": "0" * 64, "X-Aware-AccountId": "0001", "Content-Type": "application/json"}
        payload = {"biometricCredential": {"externalUserId": "user-x", "biometrics": {}}}
        resp = requests.post(credential_url(base_url, tenant_id, collection_id), json=payload, headers=headers)
        assert resp.status_code == 401
        assert resp.json().get("error") == "UNAUTHORIZED"

    def test_invalid_api_key_on_get_by_id_returns_401(self, base_url, tenant_id, collection_id):
        """Invalid API key returns 401 on GET by credentialId."""
        headers = {"X-Aware-ApiKey": "0" * 64, "X-Aware-AccountId": "0001", "Content-Type": "application/json"}
        resp = requests.get(credential_url(base_url, tenant_id, collection_id, str(uuid.uuid4())), headers=headers)
        assert resp.status_code == 401
        assert resp.json().get("error") == "UNAUTHORIZED"

    def test_invalid_api_key_on_get_list_returns_401(self, base_url, tenant_id, collection_id):
        """Invalid API key returns 401 on GET list."""
        headers = {"X-Aware-ApiKey": "0" * 64, "X-Aware-AccountId": "0001", "Content-Type": "application/json"}
        resp = requests.get(credential_url(base_url, tenant_id, collection_id), headers=headers)
        assert resp.status_code == 401
        assert resp.json().get("error") == "UNAUTHORIZED"

    def test_invalid_api_key_on_get_by_external_user_id_returns_401(self, base_url, tenant_id, collection_id):
        """Invalid API key returns 401 on GET ?externalUserId=."""
        headers = {"X-Aware-ApiKey": "0" * 64, "X-Aware-AccountId": "0001", "Content-Type": "application/json"}
        resp = requests.get(
            credential_url(base_url, tenant_id, collection_id),
            params={"externalUserId": "user-x"},
            headers=headers,
        )
        assert resp.status_code == 401
        assert resp.json().get("error") == "UNAUTHORIZED"

    def test_invalid_api_key_on_patch_by_id_returns_401(self, base_url, tenant_id, collection_id):
        """Invalid API key returns 401 on PATCH by credentialId."""
        headers = {"X-Aware-ApiKey": "0" * 64, "X-Aware-AccountId": "0001", "Content-Type": "application/json"}
        payload = {"biometricCredential": {"updatedBy": "x"}}
        resp = requests.patch(
            credential_url(base_url, tenant_id, collection_id, str(uuid.uuid4())),
            json=payload,
            headers=headers,
        )
        assert resp.status_code == 401
        assert resp.json().get("error") == "UNAUTHORIZED"

    def test_invalid_api_key_on_patch_by_external_user_id_returns_401(self, base_url, tenant_id, collection_id):
        """Invalid API key returns 401 on PATCH ?externalUserId=."""
        headers = {"X-Aware-ApiKey": "0" * 64, "X-Aware-AccountId": "0001", "Content-Type": "application/json"}
        payload = {"biometricCredential": {"updatedBy": "x"}}
        resp = requests.patch(
            credential_url(base_url, tenant_id, collection_id),
            params={"externalUserId": "user-x"},
            json=payload,
            headers=headers,
        )
        assert resp.status_code == 401
        assert resp.json().get("error") == "UNAUTHORIZED"

    def test_invalid_api_key_on_delete_by_id_returns_401(self, base_url, tenant_id, collection_id):
        """Invalid API key returns 401 on DELETE by credentialId."""
        headers = {"X-Aware-ApiKey": "0" * 64, "X-Aware-AccountId": "0001", "Content-Type": "application/json"}
        resp = requests.delete(
            credential_url(base_url, tenant_id, collection_id, str(uuid.uuid4())),
            headers=headers,
        )
        assert resp.status_code == 401
        assert resp.json().get("error") == "UNAUTHORIZED"

    def test_invalid_api_key_on_delete_by_external_user_id_returns_401(self, base_url, tenant_id, collection_id):
        """Invalid API key returns 401 on DELETE ?externalUserId=."""
        headers = {"X-Aware-ApiKey": "0" * 64, "X-Aware-AccountId": "0001", "Content-Type": "application/json"}
        resp = requests.delete(
            credential_url(base_url, tenant_id, collection_id),
            params={"externalUserId": "user-x"},
            headers=headers,
        )
        assert resp.status_code == 401
        assert resp.json().get("error") == "UNAUTHORIZED"

    # ------------------------------------------------------------------
    # Missing X-Aware-ApiKey → 401
    # [BUG] Currently returns 500 (MissingRequestHeaderException unhandled) — MUST FAIL until fixed.
    # ------------------------------------------------------------------

    def test_missing_api_key_on_get_list_returns_401(self, base_url, tenant_id, collection_id):
        """Missing X-Aware-ApiKey must return 401 on GET list."""
        headers = {"X-Aware-AccountId": "0001", "Content-Type": "application/json"}
        resp = requests.get(credential_url(base_url, tenant_id, collection_id), headers=headers)
        assert resp.status_code == 401
        assert resp.json().get("error") == "UNAUTHORIZED"

    def test_missing_api_key_on_post_returns_401(self, base_url, tenant_id, collection_id):
        """Missing X-Aware-ApiKey must return 401 on POST."""
        headers = {"X-Aware-AccountId": "0001", "Content-Type": "application/json"}
        payload = {"biometricCredential": {"externalUserId": "user-x", "biometrics": {}}}
        resp = requests.post(credential_url(base_url, tenant_id, collection_id), json=payload, headers=headers)
        assert resp.status_code == 401
        assert resp.json().get("error") == "UNAUTHORIZED"

    # ------------------------------------------------------------------
    # Missing X-Aware-AccountId → 401
    # [BUG] Currently returns 500 (MissingRequestHeaderException unhandled) — MUST FAIL until fixed.
    # ------------------------------------------------------------------

    def test_missing_account_id_on_post_returns_401(self, base_url, auth_headers, tenant_id, collection_id):
        """Missing X-Aware-AccountId must return 401 on POST."""
        headers = {k: v for k, v in auth_headers.items() if k != "X-Aware-AccountId"}
        payload = {"biometricCredential": {"externalUserId": "user-x", "biometrics": {}}}
        resp = requests.post(credential_url(base_url, tenant_id, collection_id), json=payload, headers=headers)
        assert resp.status_code == 401
        assert resp.json().get("error") == "UNAUTHORIZED"

    def test_missing_account_id_on_get_list_returns_401(self, base_url, auth_headers, tenant_id, collection_id):
        """Missing X-Aware-AccountId must return 401 on GET list."""
        headers = {k: v for k, v in auth_headers.items() if k != "X-Aware-AccountId"}
        resp = requests.get(credential_url(base_url, tenant_id, collection_id), headers=headers)
        assert resp.status_code == 401
        assert resp.json().get("error") == "UNAUTHORIZED"

    def test_missing_account_id_on_get_by_id_returns_401(self, base_url, auth_headers, tenant_id, collection_id):
        """Missing X-Aware-AccountId must return 401 on GET by credentialId."""
        headers = {k: v for k, v in auth_headers.items() if k != "X-Aware-AccountId"}
        resp = requests.get(
            credential_url(base_url, tenant_id, collection_id, str(uuid.uuid4())),
            headers=headers,
        )
        assert resp.status_code == 401
        assert resp.json().get("error") == "UNAUTHORIZED"

    def test_missing_account_id_on_patch_returns_401(self, base_url, auth_headers, tenant_id, collection_id):
        """Missing X-Aware-AccountId must return 401 on PATCH."""
        headers = {k: v for k, v in auth_headers.items() if k != "X-Aware-AccountId"}
        payload = {"biometricCredential": {"updatedBy": "x"}}
        resp = requests.patch(
            credential_url(base_url, tenant_id, collection_id, str(uuid.uuid4())),
            json=payload,
            headers=headers,
        )
        assert resp.status_code == 401
        assert resp.json().get("error") == "UNAUTHORIZED"

    def test_missing_account_id_on_delete_returns_401(self, base_url, auth_headers, tenant_id, collection_id):
        """Missing X-Aware-AccountId must return 401 on DELETE."""
        headers = {k: v for k, v in auth_headers.items() if k != "X-Aware-AccountId"}
        resp = requests.delete(
            credential_url(base_url, tenant_id, collection_id, str(uuid.uuid4())),
            headers=headers,
        )
        assert resp.status_code == 401
        assert resp.json().get("error") == "UNAUTHORIZED"


class TestCredentialsForbidden:
    """Valid API key paired with a mismatched X-Aware-AccountId must return 403 on every method."""

    def test_account_mismatch_on_post_returns_403(
        self, base_url, mismatched_account_headers, tenant_id, collection_id
    ):
        payload = {"biometricCredential": {"externalUserId": "user-x", "biometrics": {}}}
        resp = requests.post(
            credential_url(base_url, tenant_id, collection_id),
            json=payload,
            headers=mismatched_account_headers,
        )
        assert resp.status_code == 403
        assert resp.json().get("error") == "FORBIDDEN"

    def test_account_mismatch_on_get_list_returns_403(
        self, base_url, mismatched_account_headers, tenant_id, collection_id
    ):
        resp = requests.get(
            credential_url(base_url, tenant_id, collection_id),
            headers=mismatched_account_headers,
        )
        assert resp.status_code == 403
        assert resp.json().get("error") == "FORBIDDEN"

    def test_account_mismatch_on_get_by_id_returns_403(
        self, base_url, mismatched_account_headers, tenant_id, collection_id
    ):
        resp = requests.get(
            credential_url(base_url, tenant_id, collection_id, str(uuid.uuid4())),
            headers=mismatched_account_headers,
        )
        assert resp.status_code == 403
        assert resp.json().get("error") == "FORBIDDEN"

    def test_account_mismatch_on_get_by_user_id_returns_403(
        self, base_url, mismatched_account_headers, tenant_id, collection_id
    ):
        resp = requests.get(
            credential_url(base_url, tenant_id, collection_id),
            params={"userId": "user-x"},
            headers=mismatched_account_headers,
        )
        assert resp.status_code == 403
        assert resp.json().get("error") == "FORBIDDEN"

    def test_account_mismatch_on_patch_by_id_returns_403(
        self, base_url, mismatched_account_headers, tenant_id, collection_id
    ):
        payload = {"biometricCredential": {"updatedBy": "x"}}
        resp = requests.patch(
            credential_url(base_url, tenant_id, collection_id, str(uuid.uuid4())),
            json=payload,
            headers=mismatched_account_headers,
        )
        assert resp.status_code == 403
        assert resp.json().get("error") == "FORBIDDEN"

    def test_account_mismatch_on_patch_by_user_id_returns_403(
        self, base_url, mismatched_account_headers, tenant_id, collection_id
    ):
        payload = {"biometricCredential": {"updatedBy": "x"}}
        resp = requests.patch(
            credential_url(base_url, tenant_id, collection_id),
            params={"userId": "user-x"},
            json=payload,
            headers=mismatched_account_headers,
        )
        assert resp.status_code == 403
        assert resp.json().get("error") == "FORBIDDEN"

    def test_account_mismatch_on_delete_by_id_returns_403(
        self, base_url, mismatched_account_headers, tenant_id, collection_id
    ):
        resp = requests.delete(
            credential_url(base_url, tenant_id, collection_id, str(uuid.uuid4())),
            headers=mismatched_account_headers,
        )
        assert resp.status_code == 403
        assert resp.json().get("error") == "FORBIDDEN"

    def test_account_mismatch_on_delete_by_user_id_returns_403(
        self, base_url, mismatched_account_headers, tenant_id, collection_id
    ):
        resp = requests.delete(
            credential_url(base_url, tenant_id, collection_id),
            params={"userId": "user-x"},
            headers=mismatched_account_headers,
        )
        assert resp.status_code == 403
        assert resp.json().get("error") == "FORBIDDEN"


class TestCredentialsWwwAuthenticate:
    """401 responses must include WWW-Authenticate: ApiKey realm="aware"."""

    def test_invalid_api_key_returns_www_authenticate_header(
        self, base_url, bad_auth_headers, tenant_id, collection_id
    ):
        resp = requests.get(credential_url(base_url, tenant_id, collection_id), headers=bad_auth_headers)
        assert resp.status_code == 401
        assert resp.json().get("error") == "UNAUTHORIZED"
        assert resp.headers.get("WWW-Authenticate") == 'ApiKey realm="aware"'

    def test_missing_api_key_returns_www_authenticate_header(
        self, base_url, auth_headers, tenant_id, collection_id
    ):
        headers = {k: v for k, v in auth_headers.items() if k != "X-Aware-ApiKey"}
        resp = requests.get(credential_url(base_url, tenant_id, collection_id), headers=headers)
        assert resp.status_code == 401
        assert resp.json().get("error") == "UNAUTHORIZED"
        assert resp.headers.get("WWW-Authenticate") == 'ApiKey realm="aware"'

    def test_missing_account_id_returns_www_authenticate_header(
        self, base_url, auth_headers, tenant_id, collection_id
    ):
        headers = {k: v for k, v in auth_headers.items() if k != "X-Aware-AccountId"}
        resp = requests.get(credential_url(base_url, tenant_id, collection_id), headers=headers)
        assert resp.status_code == 401
        assert resp.json().get("error") == "UNAUTHORIZED"
        assert resp.headers.get("WWW-Authenticate") == 'ApiKey realm="aware"'
