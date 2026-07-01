"""
GET /v3/tenants/{tenantId}/apiKeys — list API keys.

Response envelope: { content: [...], page, size, totalElements, totalPages, first, last }
Key fields: id, keyName, description, apiKey (null), keyPrefix, keySuffix,
            status, visibility, userId, tenantId, expiresAt, lastUsedAt, createdAt, updatedAt
"""

import requests
import pytest

from tests.api_keys.conftest import api_keys_url

REQUIRED_KEY_FIELDS = {
    "id", "keyName", "keyPrefix", "keySuffix", "status",
    "createdAt", "updatedAt",
}
REQUIRED_PAGINATION_FIELDS = {
    "content", "page", "size", "totalElements", "totalPages",
}


class TestListShape:

    def test_list_returns_200(self, base_url, tenant_id, mgmt_headers):
        resp = requests.get(api_keys_url(base_url, tenant_id), headers=mgmt_headers)
        assert resp.status_code == 200

    def test_list_has_pagination_envelope(self, base_url, tenant_id, mgmt_headers):
        body = requests.get(api_keys_url(base_url, tenant_id), headers=mgmt_headers).json()
        missing = REQUIRED_PAGINATION_FIELDS - set(body.keys())
        assert not missing, f"Missing pagination fields: {missing}"

    def test_content_is_a_list(self, base_url, tenant_id, mgmt_headers):
        body = requests.get(api_keys_url(base_url, tenant_id), headers=mgmt_headers).json()
        assert isinstance(body["content"], list)

    def test_each_key_has_required_fields(self, base_url, tenant_id, mgmt_headers, created_key):
        body = requests.get(api_keys_url(base_url, tenant_id), headers=mgmt_headers).json()
        assert len(body["content"]) > 0
        for key in body["content"]:
            missing = REQUIRED_KEY_FIELDS - set(key.keys())
            assert not missing, f"Key {key.get('id')} missing fields: {missing}"

    def test_secret_null_in_list(self, base_url, tenant_id, mgmt_headers, created_key):
        """apiKey field must be null in list — secret never exposed after creation."""
        body = requests.get(api_keys_url(base_url, tenant_id), headers=mgmt_headers).json()
        for key in body["content"]:
            assert key.get("apiKey") is None, (
                f"Key {key.get('id')} has non-null apiKey in list: {key.get('apiKey')!r}"
            )

    def test_masked_identifier_uses_prefix_and_suffix(self, base_url, tenant_id, mgmt_headers, created_key):
        """keyPrefix and keySuffix show partial key; neither is the full secret."""
        # Use GET /{id} — list may not contain fixture key if tenant has many keys (pagination)
        resp = requests.get(
            api_keys_url(base_url, tenant_id, created_key["id"]), headers=mgmt_headers
        )
        assert resp.status_code == 200
        key = resp.json()
        assert key.get("keyPrefix"), "keyPrefix must be present and non-empty"
        assert key.get("keySuffix"), "keySuffix must be present and non-empty"
        prefix_len = len(key["keyPrefix"])
        suffix_len = len(key["keySuffix"])
        assert prefix_len + suffix_len < 20, (
            f"prefix ({prefix_len}) + suffix ({suffix_len}) chars — looks unmasked"
        )


class TestListContent:

    def test_newly_created_key_appears_in_list(self, base_url, tenant_id, mgmt_headers, created_key):
        """Newly created key appears on the first page when sorted by createdAt,desc."""
        target_id = created_key["id"]
        body = requests.get(
            api_keys_url(base_url, tenant_id),
            params={"sort": "createdAt,desc", "size": 10},
            headers=mgmt_headers,
        ).json()
        ids = [k["id"] for k in body["content"]]
        assert target_id in ids, (
            f"Newly created key {target_id} not found in first page (sort=createdAt,desc)"
        )

    def test_new_key_has_active_status_in_list(self, base_url, tenant_id, mgmt_headers, created_key):
        """Verify status via GET /{id} — consistent regardless of pagination."""
        resp = requests.get(
            api_keys_url(base_url, tenant_id, created_key["id"]), headers=mgmt_headers
        )
        assert resp.json().get("status") == "ACTIVE"

    def test_never_used_key_has_null_last_used(self, base_url, tenant_id, mgmt_headers, created_key):
        """A freshly created key that has never authenticated must have lastUsedAt null."""
        # Use GET /{id} directly — list is paginated and fixture key may be on page > 0
        resp = requests.get(
            api_keys_url(base_url, tenant_id, created_key["id"]), headers=mgmt_headers
        )
        assert resp.status_code == 200
        assert resp.json().get("lastUsedAt") is None, (
            f"Fresh key should have null lastUsedAt, got: {resp.json().get('lastUsedAt')}"
        )

    def test_total_elements_matches_content_count_on_single_page(
        self, base_url, tenant_id, mgmt_headers
    ):
        body = requests.get(api_keys_url(base_url, tenant_id), headers=mgmt_headers).json()
        if body["totalPages"] == 1:
            assert body["totalElements"] == len(body["content"])


class TestListIsolation:

    def test_keys_from_other_tenant_not_returned(
        self, base_url, tenant_id, tenant_id_2, mgmt_headers, created_key
    ):
        """Keys created in tenant A must not appear in tenant B's list."""
        resp_b = requests.get(api_keys_url(base_url, tenant_id_2), headers=mgmt_headers)
        if resp_b.status_code == 200:
            ids_b = {k["id"] for k in resp_b.json().get("content", [])}
            assert created_key["id"] not in ids_b, (
                "Key from tenant A found in tenant B's list — cross-tenant leak"
            )
        else:
            assert resp_b.status_code in (403, 401)
