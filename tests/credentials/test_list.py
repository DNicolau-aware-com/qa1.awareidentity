"""
Tests for GET /v3/tenants/{tenantId}/collections/{collectionId}/credentials  (list all, no userId filter)

Covers: pagination defaults, size cap, status filter, soft-delete exclusion, imageData absence,
        userId filter (exact match on externalUserId, list response, no imageData).
"""

import uuid
import requests

from tests.credentials.conftest import credential_url, collection_url, create_collection_payload, create_credential_payload, _DUMMY_IMAGE_B64


class TestListHappyPath:

    def test_returns_200(self, base_url, auth_headers, tenant_id, collection_id):
        """GET list with no filters returns 200."""
        resp = requests.get(credential_url(base_url, tenant_id, collection_id), headers=auth_headers)
        assert resp.status_code == 200

    def test_response_shape(self, base_url, auth_headers, tenant_id, collection_id):
        """Response contains biometricCredentials list and pagination fields."""
        resp = requests.get(credential_url(base_url, tenant_id, collection_id), headers=auth_headers)
        body = resp.json()
        for field in ("biometricCredentials", "page", "size", "totalElements", "totalPages"):
            assert field in body, f"Missing pagination field: {field}"
        assert isinstance(body["biometricCredentials"], list)

    def test_default_pagination(self, base_url, auth_headers, tenant_id, collection_id):
        """Default pagination is page=0, size=25."""
        resp = requests.get(credential_url(base_url, tenant_id, collection_id), headers=auth_headers)
        body = resp.json()
        assert body["page"] == 0
        assert body["size"] == 25

    def test_response_content_type_is_json(self, base_url, auth_headers, tenant_id, collection_id):
        """Response Content-Type is application/json."""
        resp = requests.get(credential_url(base_url, tenant_id, collection_id), headers=auth_headers)
        assert "application/json" in resp.headers.get("Content-Type", "")

    def test_created_credential_appears_in_list(self, base_url, auth_headers, tenant_id, collection_id, new_credential):
        """A newly created credential appears in the list."""
        resp = requests.get(credential_url(base_url, tenant_id, collection_id), headers=auth_headers)
        ids = [c["id"] for c in resp.json()["biometricCredentials"]]
        assert new_credential["id"] in ids

    def test_image_data_not_in_list_items(self, base_url, auth_headers, tenant_id, collection_id, new_credential):
        """List endpoint does not include imageData in entry objects (imageData is GET-by-ID / GET-entry only)."""
        resp = requests.get(credential_url(base_url, tenant_id, collection_id), headers=auth_headers)
        for cred in resp.json().get("biometricCredentials", []):
            for entries in cred.get("biometrics", {}).values():
                for entry in entries:
                    assert "imageData" not in entry, f"imageData must not appear in list response entries"


class TestListPagination:

    def test_size_param_limits_results(self, base_url, auth_headers, tenant_id, collection_id):
        """size=1 returns at most 1 result."""
        resp = requests.get(
            credential_url(base_url, tenant_id, collection_id),
            params={"size": 1},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert len(resp.json()["biometricCredentials"]) <= 1

    def test_size_over_100_is_capped(self, base_url, auth_headers, tenant_id, collection_id):
        """size values above 100 are silently capped to 100 (spec: max 100)."""
        resp = requests.get(
            credential_url(base_url, tenant_id, collection_id),
            params={"size": 999},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["size"] <= 100

    def test_non_integer_page_returns_400(self, base_url, auth_headers, tenant_id, collection_id):
        """page=abc must return 400 VALIDATION_FAILED — page is typed int; a string cannot be converted.
        [BUG] Currently returns 500 'Failed to convert value of type java.lang.String to required type int'
        (MethodArgumentTypeMismatchException unhandled) — MUST FAIL until fixed."""
        resp = requests.get(
            credential_url(base_url, tenant_id, collection_id),
            params={"page": "abc"},
            headers=auth_headers,
        )
        assert resp.status_code == 400

    def test_size_zero_returns_400(self, base_url, auth_headers, tenant_id, collection_id):
        """size=0 must return 400 — zero-item pages are not valid.
        [BUG] Currently returns 500 'Page size must not be less than one' — MUST FAIL until fixed."""
        resp = requests.get(
            credential_url(base_url, tenant_id, collection_id),
            params={"size": 0},
            headers=auth_headers,
        )
        assert resp.status_code == 400

    def test_negative_size_returns_400(self, base_url, auth_headers, tenant_id, collection_id):
        """size=-1 must return 400 — negative page size is not valid.
        [BUG] Currently returns 500 'Page size must not be less than one' — MUST FAIL until fixed."""
        resp = requests.get(
            credential_url(base_url, tenant_id, collection_id),
            params={"size": -1},
            headers=auth_headers,
        )
        assert resp.status_code == 400

    def test_negative_page_returns_400(self, base_url, auth_headers, tenant_id, collection_id):
        """page=-1 must return 400 — negative page index is invalid.
        [BUG] Currently returns 500 'Page index must not be less than zero' — MUST FAIL until fixed."""
        resp = requests.get(
            credential_url(base_url, tenant_id, collection_id),
            params={"page": -1},
            headers=auth_headers,
        )
        assert resp.status_code == 400

    def test_page_param_is_zero_based(self, base_url, auth_headers, tenant_id, collection_id):
        """page=0 is the first page (zero-based indexing)."""
        resp = requests.get(
            credential_url(base_url, tenant_id, collection_id),
            params={"page": 0},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["page"] == 0

    def test_page_beyond_last_returns_empty(self, base_url, auth_headers, tenant_id, collection_id):
        """Requesting a page beyond the last returns an empty list, not an error."""
        resp = requests.get(
            credential_url(base_url, tenant_id, collection_id),
            params={"page": 99999},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["biometricCredentials"] == []

    def test_total_pages_matches_total_elements(self, base_url, auth_headers, tenant_id, collection_id, new_credential):
        """totalPages = ceil(totalElements / size)."""
        resp = requests.get(
            credential_url(base_url, tenant_id, collection_id),
            params={"size": 1},
            headers=auth_headers,
        )
        body = resp.json()
        import math
        expected = math.ceil(body["totalElements"] / 1) if body["totalElements"] > 0 else 1
        assert body["totalPages"] == expected

    def test_size_in_response_matches_request(self, base_url, auth_headers, tenant_id, collection_id):
        """size field in response reflects the requested page size."""
        resp = requests.get(
            credential_url(base_url, tenant_id, collection_id),
            params={"size": 5},
            headers=auth_headers,
        )
        assert resp.json()["size"] == 5


class TestListFilters:

    def test_status_active_filter(self, base_url, auth_headers, tenant_id, collection_id, new_credential):
        """status=ACTIVE filter returns only ACTIVE credentials."""
        resp = requests.get(
            credential_url(base_url, tenant_id, collection_id),
            params={"status": "ACTIVE"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        for cred in resp.json().get("biometricCredentials", []):
            assert cred["status"] == "ACTIVE"
        ids = [c["id"] for c in resp.json()["biometricCredentials"]]
        assert new_credential["id"] in ids

    def test_modality_filter_contract(self, base_url, auth_headers, tenant_id, collection_id):
        """modality=FACE returns 200 and every returned credential has a 'face' modality.
        (Filter value is upper-case per spec; biometrics map keys are lower-case.)"""
        resp = requests.get(
            credential_url(base_url, tenant_id, collection_id),
            params={"modality": "FACE"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        for cred in resp.json().get("biometricCredentials", []):
            assert "face" in cred.get("biometrics", {}), "modality filter returned a credential without a face entry"

    def test_soft_deleted_excluded_from_list(self, base_url, auth_headers, tenant_id, collection_id):
        """Soft-deleted credentials are not returned in list results."""
        resp = requests.post(
            credential_url(base_url, tenant_id, collection_id),
            json=create_credential_payload(),
            headers=auth_headers,
        )
        assert resp.status_code == 201
        cred = resp.json()["biometricCredential"]
        requests.delete(credential_url(base_url, tenant_id, collection_id, cred["id"]), headers=auth_headers)

        list_resp = requests.get(credential_url(base_url, tenant_id, collection_id), headers=auth_headers)
        ids = [c["id"] for c in list_resp.json()["biometricCredentials"]]
        assert cred["id"] not in ids

    def test_status_inactive_filter(self, base_url, auth_headers, tenant_id, collection_id):
        """status=INACTIVE filter returns only INACTIVE credentials (none in this collection → empty list)."""
        resp = requests.get(
            credential_url(base_url, tenant_id, collection_id),
            params={"status": "INACTIVE"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        for cred in resp.json().get("biometricCredentials", []):
            assert cred["status"] == "INACTIVE"

    def test_unknown_collection_returns_404(self, base_url, auth_headers, tenant_id):
        """GET list with a valid but unknown collectionId returns 404."""
        resp = requests.get(
            credential_url(base_url, tenant_id, str(uuid.uuid4())),
            headers=auth_headers,
        )
        assert resp.status_code == 404

    def test_soft_deleted_collection_returns_404(self, base_url, auth_headers, tenant_id):
        """GET credentials list on a soft-deleted collection returns 404."""
        coll_resp = requests.post(
            collection_url(base_url, tenant_id),
            json=create_collection_payload(),
            headers=auth_headers,
        )
        assert coll_resp.status_code == 201
        temp_coll_id = coll_resp.json()["biometricCollection"]["id"]
        requests.delete(collection_url(base_url, tenant_id, temp_coll_id), headers=auth_headers)

        resp = requests.get(credential_url(base_url, tenant_id, temp_coll_id), headers=auth_headers)
        assert resp.status_code == 404

    def test_user_id_filter_ignores_other_params(self, base_url, auth_headers, tenant_id, collection_id, new_credential):
        """When ?userId= is present, other filters (modality, status) are ignored per spec.
        The credential is returned even when status=INACTIVE is also supplied."""
        resp = requests.get(
            credential_url(base_url, tenant_id, collection_id),
            params={
                "userId": new_credential["externalUserId"],
                "modality": "FACE",
                "status": "INACTIVE",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200
        ids = [c["id"] for c in resp.json().get("biometricCredentials", [])]
        assert new_credential["id"] in ids

    def test_no_duplicate_ids_across_pages(self, base_url, auth_headers, tenant_id, collection_id):
        """Credentials do not appear on multiple pages."""
        prefix = f"pg-test-{uuid.uuid4().hex[:8]}"
        created = []
        try:
            for i in range(3):
                r = requests.post(
                    credential_url(base_url, tenant_id, collection_id),
                    json=create_credential_payload(f"{prefix}-{i}"),
                    headers=auth_headers,
                )
                assert r.status_code == 201
                created.append(r.json()["biometricCredential"]["id"])

            p0 = requests.get(
                credential_url(base_url, tenant_id, collection_id),
                params={"size": 2, "page": 0},
                headers=auth_headers,
            )
            p1 = requests.get(
                credential_url(base_url, tenant_id, collection_id),
                params={"size": 2, "page": 1},
                headers=auth_headers,
            )
            ids_p0 = {c["id"] for c in p0.json()["biometricCredentials"]}
            ids_p1 = {c["id"] for c in p1.json()["biometricCredentials"]}
            assert not ids_p0 & ids_p1, f"Duplicate IDs across pages: {ids_p0 & ids_p1}"
        finally:
            for cid in created:
                requests.delete(credential_url(base_url, tenant_id, collection_id, cid), headers=auth_headers)


class TestListUserIdFilter:
    """
    ?userId= as a list filter on GET /credentials.
    Spec: exact match on external_user_id; returns paginated list envelope; imageData absent.
    This is distinct from GET ?userId= as a single-credential lookup (tested in test_get.py::TestGetByUserId).
    """

    def test_user_id_filter_returns_only_matching_credential(
        self, base_url, auth_headers, tenant_id, collection_id
    ):
        """?userId= returns the matching credential and excludes all others in the collection."""
        user_a = f"filter-a-{uuid.uuid4().hex[:8]}"
        user_b = f"filter-b-{uuid.uuid4().hex[:8]}"
        resp_a = requests.post(
            credential_url(base_url, tenant_id, collection_id),
            json=create_credential_payload(user_a),
            headers=auth_headers,
        )
        resp_b = requests.post(
            credential_url(base_url, tenant_id, collection_id),
            json=create_credential_payload(user_b),
            headers=auth_headers,
        )
        assert resp_a.status_code == 201
        assert resp_b.status_code == 201
        cred_a_id = resp_a.json()["biometricCredential"]["id"]
        cred_b_id = resp_b.json()["biometricCredential"]["id"]
        try:
            resp = requests.get(
                credential_url(base_url, tenant_id, collection_id),
                params={"userId": user_a},
                headers=auth_headers,
            )
            assert resp.status_code == 200
            ids = [c["id"] for c in resp.json()["biometricCredentials"]]
            assert cred_a_id in ids
            assert cred_b_id not in ids
        finally:
            requests.delete(credential_url(base_url, tenant_id, collection_id, cred_a_id), headers=auth_headers)
            requests.delete(credential_url(base_url, tenant_id, collection_id, cred_b_id), headers=auth_headers)

    def test_user_id_filter_returns_paginated_envelope(
        self, base_url, auth_headers, tenant_id, collection_id, new_credential
    ):
        """?userId= response is a paginated list envelope, not a single-object response."""
        resp = requests.get(
            credential_url(base_url, tenant_id, collection_id),
            params={"userId": new_credential["externalUserId"]},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        for field in ("biometricCredentials", "page", "size", "totalElements", "totalPages"):
            assert field in body, f"Missing pagination field: {field}"
        assert isinstance(body["biometricCredentials"], list)

    def test_user_id_filter_includes_image_data(
        self, base_url, auth_headers, tenant_id, collection_id
    ):
        """Spec: imageData is populated on GET-by-userId. A credential with a face entry must
        return imageData in that entry when fetched via ?userId=."""
        user_id = f"img-list-{uuid.uuid4().hex[:8]}"
        resp = requests.post(
            credential_url(base_url, tenant_id, collection_id),
            json={"biometricCredential": {
                "externalUserId": user_id,
                "biometrics": {"face": [{"data": _DUMMY_IMAGE_B64, "labels": ["front"]}]},
            }},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        cred_id = resp.json()["biometricCredential"]["id"]
        try:
            list_resp = requests.get(
                credential_url(base_url, tenant_id, collection_id),
                params={"userId": user_id},
                headers=auth_headers,
            )
            assert list_resp.status_code == 200
            creds = list_resp.json().get("biometricCredentials", [])
            entries = [e for c in creds for e in c.get("biometrics", {}).get("face", [])]
            assert entries, "Expected at least one face entry in ?userId= response"
            for entry in entries:
                assert "imageData" in entry and entry["imageData"], "imageData must be populated on GET ?userId="
        finally:
            requests.delete(credential_url(base_url, tenant_id, collection_id, cred_id), headers=auth_headers)

    def test_user_id_filter_is_exact_match(
        self, base_url, auth_headers, tenant_id, collection_id
    ):
        """?userId= is an exact match — a prefix of an enrolled userId must return no results."""
        user_id = f"exactmatch-{uuid.uuid4().hex[:8]}"
        resp_create = requests.post(
            credential_url(base_url, tenant_id, collection_id),
            json=create_credential_payload(user_id),
            headers=auth_headers,
        )
        assert resp_create.status_code == 201
        cred_id = resp_create.json()["biometricCredential"]["id"]
        try:
            partial = user_id[: len(user_id) // 2]
            resp = requests.get(
                credential_url(base_url, tenant_id, collection_id),
                params={"userId": partial},
                headers=auth_headers,
            )
            assert resp.status_code in (200, 404), f"Expected 200 (empty) or 404 for non-matching userId, got {resp.status_code}"
            if resp.status_code == 200:
                ids = [c["id"] for c in resp.json()["biometricCredentials"]]
                assert cred_id not in ids, "Partial userId should not match — filter must be exact"
        finally:
            requests.delete(credential_url(base_url, tenant_id, collection_id, cred_id), headers=auth_headers)

    def test_user_id_filter_nonexistent_returns_404(
        self, base_url, auth_headers, tenant_id, collection_id
    ):
        """?userId= for an unknown externalUserId returns 404.
        The endpoint treats ?userId= as a single-credential lookup (same semantics as
        GET .../credentials/{id}), so a miss returns 404 rather than 200 with an empty list.
        Spec ambiguity: the list filter contract would imply 200 + empty results, but the
        observed and consistent behaviour is 404."""
        resp = requests.get(
            credential_url(base_url, tenant_id, collection_id),
            params={"userId": f"ghost-{uuid.uuid4().hex[:12]}"},
            headers=auth_headers,
        )
        assert resp.status_code == 404


class TestListItemShape:
    """Each item in the list response must satisfy the BiometricCredential schema:
    all required fields present, status enum valid, timestamps are integers,
    and optional fields (updatedBy, correlationId) are omitted entirely when null."""

    def test_required_fields_present_on_list_items(self, base_url, auth_headers, tenant_id, collection_id, new_credential):
        """Every credential in the list contains all spec-required fields."""
        resp = requests.get(credential_url(base_url, tenant_id, collection_id), headers=auth_headers)
        assert resp.status_code == 200
        for cred in resp.json()["biometricCredentials"]:
            for field in ("id", "collectionId", "externalUserId", "status", "biometrics", "createdBy", "createdAt", "updatedAt"):
                assert field in cred, f"Missing required field '{field}' in list item {cred.get('id')}"

    def test_status_enum_valid_on_list_items(self, base_url, auth_headers, tenant_id, collection_id, new_credential):
        """status on every list item is ACTIVE or INACTIVE — no other values are valid."""
        resp = requests.get(credential_url(base_url, tenant_id, collection_id), headers=auth_headers)
        assert resp.status_code == 200
        for cred in resp.json()["biometricCredentials"]:
            assert cred["status"] in ("ACTIVE", "INACTIVE"), \
                f"Invalid status '{cred['status']}' on credential {cred.get('id')}"

    def test_timestamps_are_integer_epoch_ms_on_list_items(self, base_url, auth_headers, tenant_id, collection_id, new_credential):
        """createdAt and updatedAt are positive integers (Unix epoch ms) on list items."""
        resp = requests.get(credential_url(base_url, tenant_id, collection_id), headers=auth_headers)
        assert resp.status_code == 200
        for cred in resp.json()["biometricCredentials"]:
            assert isinstance(cred["createdAt"], int) and cred["createdAt"] > 0, \
                f"createdAt must be a positive integer, got {cred['createdAt']}"
            assert isinstance(cred["updatedAt"], int) and cred["updatedAt"] > 0, \
                f"updatedAt must be a positive integer, got {cred['updatedAt']}"

    def test_updated_by_omitted_when_null(self, base_url, auth_headers, tenant_id, collection_id):
        """Spec: updatedBy is 'Omitted when null' — the key must be absent, not present as null."""
        user_id = f"omit-upd-{uuid.uuid4().hex[:8]}"
        resp = requests.post(
            credential_url(base_url, tenant_id, collection_id),
            json=create_credential_payload(user_id),
            headers=auth_headers,
        )
        assert resp.status_code == 201
        cred_id = resp.json()["biometricCredential"]["id"]
        try:
            list_resp = requests.get(credential_url(base_url, tenant_id, collection_id), headers=auth_headers)
            items = [c for c in list_resp.json()["biometricCredentials"] if c["id"] == cred_id]
            assert items, "Created credential not found in list"
            assert "updatedBy" not in items[0], \
                f"updatedBy must be absent (not null) when never patched, got {items[0].get('updatedBy')!r}"
        finally:
            requests.delete(credential_url(base_url, tenant_id, collection_id, cred_id), headers=auth_headers)

    def test_correlation_id_omitted_when_null(self, base_url, auth_headers, tenant_id, collection_id):
        """Spec: correlationId is 'Omitted when null' — the key must be absent, not present as null."""
        user_id = f"omit-corr-{uuid.uuid4().hex[:8]}"
        resp = requests.post(
            credential_url(base_url, tenant_id, collection_id),
            json=create_credential_payload(user_id),
            headers=auth_headers,
        )
        assert resp.status_code == 201
        cred_id = resp.json()["biometricCredential"]["id"]
        try:
            list_resp = requests.get(credential_url(base_url, tenant_id, collection_id), headers=auth_headers)
            items = [c for c in list_resp.json()["biometricCredentials"] if c["id"] == cred_id]
            assert items, "Created credential not found in list"
            assert "correlationId" not in items[0], \
                f"correlationId must be absent (not null) when unset, got {items[0].get('correlationId')!r}"
        finally:
            requests.delete(credential_url(base_url, tenant_id, collection_id, cred_id), headers=auth_headers)
