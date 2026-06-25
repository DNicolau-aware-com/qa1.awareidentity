"""
Tests for GET /v3/tenants/{tenantId}/collections  (list / search / pagination)
"""

import uuid
import requests

from tests.collections.conftest import collection_url, create_payload


class TestListHappyPath:

    def test_returns_200(self, base_url, auth_headers, tenant_id):
        """GET list returns 200."""
        resp = requests.get(collection_url(base_url, tenant_id), headers=auth_headers)
        assert resp.status_code == 200

    def test_response_shape(self, base_url, auth_headers, tenant_id):
        """Response contains all pagination fields and a list."""
        resp = requests.get(collection_url(base_url, tenant_id), headers=auth_headers)
        body = resp.json()
        for field in ("biometricCollections", "page", "size", "totalElements", "totalPages"):
            assert field in body
        assert isinstance(body["biometricCollections"], list)

    def test_default_pagination(self, base_url, auth_headers, tenant_id):
        """Default pagination is page=0, size=25."""
        resp = requests.get(collection_url(base_url, tenant_id), headers=auth_headers)
        body = resp.json()
        assert body["page"] == 0
        assert body["size"] == 25

    def test_response_content_type_is_json(self, base_url, auth_headers, tenant_id):
        """Response Content-Type is application/json."""
        resp = requests.get(collection_url(base_url, tenant_id), headers=auth_headers)
        assert "application/json" in resp.headers.get("Content-Type", "")

    def test_created_collection_appears_in_list(self, base_url, auth_headers, tenant_id, new_collection):
        """A newly created collection appears in the list."""
        resp = requests.get(collection_url(base_url, tenant_id), params={"name": new_collection["name"]}, headers=auth_headers)
        ids = [c["id"] for c in resp.json()["biometricCollections"]]
        assert new_collection["id"] in ids


class TestListFilters:

    def test_name_filter_returns_matching(self, base_url, auth_headers, tenant_id, new_collection):
        """name filter returns collections whose name contains the substring."""
        resp = requests.get(collection_url(base_url, tenant_id),
                            params={"name": new_collection["name"]}, headers=auth_headers)
        assert resp.status_code == 200
        ids = [c["id"] for c in resp.json()["biometricCollections"]]
        assert new_collection["id"] in ids

    def test_name_filter_is_case_insensitive(self, base_url, auth_headers, tenant_id, new_collection):
        """name filter is case-insensitive."""
        resp = requests.get(collection_url(base_url, tenant_id),
                            params={"name": new_collection["name"].upper()}, headers=auth_headers)
        assert resp.status_code == 200
        ids = [c["id"] for c in resp.json()["biometricCollections"]]
        assert new_collection["id"] in ids

    def test_name_filter_no_match_returns_empty(self, base_url, auth_headers, tenant_id):
        """name filter with no matches returns empty list and totalElements=0."""
        resp = requests.get(collection_url(base_url, tenant_id),
                            params={"name": f"zzznomatch-{uuid.uuid4().hex}"}, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["biometricCollections"] == []
        assert resp.json()["totalElements"] == 0

    def test_storage_type_filter(self, base_url, auth_headers, tenant_id, new_collection):
        """storageType filter returns only collections with that storage type."""
        resp = requests.get(collection_url(base_url, tenant_id),
                            params={"storageType": "STANDARD"}, headers=auth_headers)
        assert resp.status_code == 200
        for c in resp.json()["biometricCollections"]:
            assert c["storageType"] == "STANDARD"

    def test_dedup_enabled_filter(self, base_url, auth_headers, tenant_id):
        """dedupEnabled=true filter returns only collections with dedupEnabled=true."""
        create_resp = requests.post(collection_url(base_url, tenant_id),
                                    json=create_payload(dedupEnabled=True), headers=auth_headers)
        assert create_resp.status_code == 201
        c = create_resp.json()["biometricCollection"]
        try:
            resp = requests.get(collection_url(base_url, tenant_id),
                                params={"dedupEnabled": "true"}, headers=auth_headers)
            assert resp.status_code == 200
            for item in resp.json()["biometricCollections"]:
                assert item["dedupEnabled"] is True
        finally:
            requests.delete(collection_url(base_url, tenant_id, c["id"]), headers=auth_headers)

    def test_dedup_disabled_filter(self, base_url, auth_headers, tenant_id):
        """dedupEnabled=false filter returns only collections with dedupEnabled=false."""
        create_resp = requests.post(collection_url(base_url, tenant_id),
                                    json=create_payload(dedupEnabled=False), headers=auth_headers)
        assert create_resp.status_code == 201
        c = create_resp.json()["biometricCollection"]
        try:
            resp = requests.get(collection_url(base_url, tenant_id),
                                params={"dedupEnabled": "false"}, headers=auth_headers)
            assert resp.status_code == 200
            ids = [item["id"] for item in resp.json()["biometricCollections"]]
            assert c["id"] in ids, "Collection with dedupEnabled=false must appear in dedupEnabled=false filter results"
            for item in resp.json()["biometricCollections"]:
                assert item["dedupEnabled"] is False
        finally:
            requests.delete(collection_url(base_url, tenant_id, c["id"]), headers=auth_headers)

    def test_soft_deleted_excluded_from_list(self, base_url, auth_headers, tenant_id):
        """Soft-deleted collections are not returned in list results."""
        create_resp = requests.post(collection_url(base_url, tenant_id), json=create_payload(), headers=auth_headers)
        assert create_resp.status_code == 201
        c = create_resp.json()["biometricCollection"]
        requests.delete(collection_url(base_url, tenant_id, c["id"]), headers=auth_headers)

        resp = requests.get(collection_url(base_url, tenant_id), params={"name": c["name"]}, headers=auth_headers)
        ids = [x["id"] for x in resp.json()["biometricCollections"]]
        assert c["id"] not in ids


class TestListPagination:

    def test_size_param_limits_results(self, base_url, auth_headers, tenant_id):
        """size=1 returns at most 1 result."""
        resp = requests.get(collection_url(base_url, tenant_id), params={"size": 1}, headers=auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()["biometricCollections"]) <= 1

    def test_size_over_100_is_capped(self, base_url, auth_headers, tenant_id):
        """size values above 100 are silently capped to 100 (spec: max 100)."""
        resp = requests.get(collection_url(base_url, tenant_id), params={"size": 999}, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["size"] <= 100

    def test_page_param_is_zero_based(self, base_url, auth_headers, tenant_id):
        """page=0 is the first page (zero-based)."""
        resp = requests.get(collection_url(base_url, tenant_id), params={"page": 0}, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["page"] == 0

    def test_page_beyond_last_returns_empty_list(self, base_url, auth_headers, tenant_id):
        """Requesting a page number beyond the last returns empty list, not an error."""
        resp = requests.get(collection_url(base_url, tenant_id), params={"page": 99999}, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["biometricCollections"] == []

    def test_total_elements_reflects_created_collection(self, base_url, auth_headers, tenant_id, new_collection):
        """totalElements for a name-filtered search is at least 1 after creation."""
        resp = requests.get(collection_url(base_url, tenant_id),
                            params={"name": new_collection["name"]}, headers=auth_headers)
        assert resp.json()["totalElements"] >= 1

    def test_size_zero_returns_400(self, base_url, auth_headers, tenant_id):
        """[BUG-4] size=0 must return 400. Currently returns 500 — Spring's IllegalArgumentException
        is unhandled and surfaces as an Internal Server Error. MUST FAIL until fixed."""
        resp = requests.get(collection_url(base_url, tenant_id), params={"size": 0}, headers=auth_headers)
        assert resp.status_code == 400

    def test_negative_page_returns_400(self, base_url, auth_headers, tenant_id):
        """[BUG-5] page=-1 must return 400. Currently returns 500 with message
        'Page index must not be less than zero' — Spring's IllegalArgumentException is unhandled.
        MUST FAIL until fixed."""
        resp = requests.get(collection_url(base_url, tenant_id), params={"page": -1}, headers=auth_headers)
        assert resp.status_code == 400


class TestListPaginationBehavior:
    """Real pagination: create known collections, walk pages, assert correctness."""

    def test_no_duplicate_ids_across_pages(self, base_url, auth_headers, tenant_id):
        """Create 3 collections, fetch size=2 pages 0 and 1, assert no ID appears on both pages."""
        prefix = f"pag-test-{uuid.uuid4().hex[:8]}"
        created_ids = []
        try:
            for i in range(3):
                r = requests.post(
                    collection_url(base_url, tenant_id),
                    json=create_payload(name=f"{prefix}-{i + 1}"),
                    headers=auth_headers,
                )
                assert r.status_code == 201, f"setup failed: {r.text}"
                created_ids.append(r.json()["biometricCollection"]["id"])

            params_base = {"name": prefix, "size": 2}
            p0 = requests.get(collection_url(base_url, tenant_id),
                               params={**params_base, "page": 0}, headers=auth_headers)
            p1 = requests.get(collection_url(base_url, tenant_id),
                               params={**params_base, "page": 1}, headers=auth_headers)
            assert p0.status_code == 200
            assert p1.status_code == 200

            ids_p0 = {c["id"] for c in p0.json()["biometricCollections"]}
            ids_p1 = {c["id"] for c in p1.json()["biometricCollections"]}

            assert not ids_p0 & ids_p1, f"Duplicate IDs across pages: {ids_p0 & ids_p1}"
            assert len(p0.json()["biometricCollections"]) == 2
            assert len(p1.json()["biometricCollections"]) == 1
            assert p0.json()["totalElements"] == 3
            assert p0.json()["totalElements"] == p1.json()["totalElements"]
            assert p0.json()["totalPages"] == 2
            assert ids_p0 | ids_p1 == set(created_ids)
        finally:
            for cid in created_ids:
                requests.delete(collection_url(base_url, tenant_id, cid), headers=auth_headers)


class TestListFilterCombined:

    def test_name_and_storage_type_combined(self, base_url, auth_headers, tenant_id, new_collection):
        """Combining name and storageType filters returns only matching collections."""
        resp = requests.get(collection_url(base_url, tenant_id),
                            params={"name": new_collection["name"], "storageType": "STANDARD"},
                            headers=auth_headers)
        assert resp.status_code == 200
        items = resp.json()["biometricCollections"]
        assert new_collection["id"] in [c["id"] for c in items]
        for c in items:
            assert c["storageType"] == "STANDARD"

    def test_name_and_dedup_combined_no_match(self, base_url, auth_headers, tenant_id, new_collection):
        """name filter + dedupEnabled=true returns empty when the named collection has dedupEnabled=false."""
        assert new_collection["dedupEnabled"] is False
        resp = requests.get(collection_url(base_url, tenant_id),
                            params={"name": new_collection["name"], "dedupEnabled": "true"},
                            headers=auth_headers)
        assert resp.status_code == 200
        ids = [c["id"] for c in resp.json()["biometricCollections"]]
        assert new_collection["id"] not in ids

    def test_list_ordering_is_stable(self, base_url, auth_headers, tenant_id):
        """Two identical list requests return results in the same order."""
        r1 = requests.get(collection_url(base_url, tenant_id), params={"size": 10}, headers=auth_headers)
        r2 = requests.get(collection_url(base_url, tenant_id), params={"size": 10}, headers=auth_headers)
        assert r1.status_code == 200
        ids1 = [c["id"] for c in r1.json()["biometricCollections"]]
        ids2 = [c["id"] for c in r2.json()["biometricCollections"]]
        assert ids1 == ids2
