"""
Cross-tenant isolation tests for /v3/tenants/{tenantId}/collections.

Requires two independent tenants to be configured:
  AWARE_TENANT_ID       — primary tenant (auth_headers / tenant_id)
  AWARE_TENANT_ID_2     — secondary tenant (auth_headers_2 / tenant_id_2)
  AWARE_ACCOUNT_ID_2    — account ID for the secondary tenant

Both pairs of tests skip automatically when those env vars are absent.
"""

import uuid
import requests

from tests.collections.conftest import collection_url, create_payload


class TestCrossTenantRead:

    def test_collection_from_tenant_a_not_readable_by_tenant_b(
        self, base_url, auth_headers, tenant_id, auth_headers_2, tenant_id_2, new_collection
    ):
        """GET tenant A's collection via tenant B's URL returns 403 or 404."""
        resp = requests.get(
            collection_url(base_url, tenant_id_2, new_collection["id"]),
            headers=auth_headers_2,
        )
        assert resp.status_code in (403, 404)

    def test_tenant_b_credentials_cannot_list_tenant_a_collections(
        self, base_url, auth_headers_2, tenant_id
    ):
        """[BUG-10] GET tenant A's list URL with tenant B's API key must return 403.

        Currently returns 200 and exposes ALL of tenant A's collections — the API does
        not validate that the API key belongs to the tenant in the URL path.
        Confirmed with multiple tenants (dantest01, testtest1): any valid API key can
        read any other tenant's collections by substituting the target tenantId in the URL.
        This is a cross-tenant data leak / security vulnerability.
        MUST FAIL until tenant-to-API-key binding is enforced on the list endpoint."""
        resp = requests.get(collection_url(base_url, tenant_id), headers=auth_headers_2)
        assert resp.status_code in (401, 403, 404)


class TestCrossTenantWrite:

    def test_collection_from_tenant_a_not_patchable_by_tenant_b(
        self, base_url, auth_headers_2, tenant_id_2, new_collection, tenant_id
    ):
        """PATCH tenant A's collection ID via tenant B's URL returns 403 or 404."""
        payload = {"biometricCollection": {"updatedBy": "attacker@example.com"}}
        resp = requests.patch(
            collection_url(base_url, tenant_id_2, new_collection["id"]),
            json=payload,
            headers=auth_headers_2,
        )
        assert resp.status_code in (403, 404)

    def test_collection_from_tenant_a_not_deletable_by_tenant_b(
        self, base_url, auth_headers_2, tenant_id_2, new_collection
    ):
        """DELETE tenant A's collection ID via tenant B's URL returns 403 or 404."""
        resp = requests.delete(
            collection_url(base_url, tenant_id_2, new_collection["id"]),
            headers=auth_headers_2,
        )
        assert resp.status_code in (403, 404)


class TestCrossTenantNameUniqueness:

    def test_same_name_allowed_across_different_tenants(
        self, base_url, auth_headers, tenant_id, auth_headers_2, tenant_id_2
    ):
        """Creating a collection with the same name under two tenants both succeed."""
        name = f"shared-name-{uuid.uuid4().hex[:8]}"
        r1 = requests.post(collection_url(base_url, tenant_id),
                           json=create_payload(name=name), headers=auth_headers)
        r2 = requests.post(collection_url(base_url, tenant_id_2),
                           json=create_payload(name=name), headers=auth_headers_2)
        try:
            assert r1.status_code == 201, f"Tenant A create failed: {r1.text}"
            if r2.status_code in (403, 404):
                import pytest as _pytest
                _pytest.skip(f"Tenant B not accessible with current credentials ({r2.status_code}): {r2.text}")
            assert r2.status_code == 201, f"Tenant B create failed (expected no cross-tenant conflict): {r2.text}"
        finally:
            if r1.status_code == 201:
                requests.delete(
                    collection_url(base_url, tenant_id, r1.json()["biometricCollection"]["id"]),
                    headers=auth_headers,
                )
            if r2.status_code == 201:
                requests.delete(
                    collection_url(base_url, tenant_id_2, r2.json()["biometricCollection"]["id"]),
                    headers=auth_headers_2,
                )
