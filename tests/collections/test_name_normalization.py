"""
Tests for name normalization behavior: case sensitivity and whitespace handling.

Observed API behavior (confirmed via live probe):
  - Uniqueness constraint is CASE-SENSITIVE: "Demo", "demo", "DEMO" each create without conflict.
  - The list name filter is CASE-INSENSITIVE: searching "demo" finds "Demo".
  - Whitespace is NOT trimmed: " Demo" and "Demo " are stored verbatim and treated as distinct names.

Known bugs tracked here:
  [BUG-8] Leading/trailing whitespace is not stripped — invisible duplicates are possible.
          Tests marked [BUG-8] MUST FAIL until the bug is resolved.
  [BUG-9] Uniqueness is case-sensitive but the search filter is case-insensitive.
          A user can create "Demo" and "demo" as separate collections even though the filter
          cannot distinguish them. Tests marked [BUG-9] MUST FAIL until the bug is resolved.
"""

import uuid
import requests
import pytest

from tests.collections.conftest import collection_url, create_payload


def _make_suffix():
    return uuid.uuid4().hex[:10]


class TestNameCaseSensitivity:
    """Case sensitivity in uniqueness constraint vs. search filter."""

    def test_case_variants_create_distinct_collections(self, base_url, auth_headers, tenant_id):
        """Documents current behavior: 'Demo', 'demo', 'DEMO' are all accepted (case-sensitive uniqueness)."""
        suffix = _make_suffix()
        created = []
        try:
            for variant in (f"CaseTest-{suffix}", f"casetest-{suffix}", f"CASETEST-{suffix}"):
                r = requests.post(
                    collection_url(base_url, tenant_id),
                    json=create_payload(name=variant),
                    headers=auth_headers,
                )
                assert r.status_code == 201, f"Expected 201 for {repr(variant)}, got {r.status_code}"
                created.append(r.json()["biometricCollection"]["id"])
            assert len(set(created)) == 3, "All three case variants must have different IDs"
        finally:
            for cid in created:
                requests.delete(collection_url(base_url, tenant_id, cid), headers=auth_headers)

    def test_different_case_variants_have_distinct_ids(self, base_url, auth_headers, tenant_id):
        """'Demo' and 'demo' are stored as separate collections with different IDs."""
        suffix = _make_suffix()
        ids = []
        try:
            for variant in (f"NCase-{suffix}", f"ncase-{suffix}"):
                r = requests.post(
                    collection_url(base_url, tenant_id),
                    json=create_payload(name=variant),
                    headers=auth_headers,
                )
                assert r.status_code == 201
                ids.append(r.json()["biometricCollection"]["id"])
            assert ids[0] != ids[1]
        finally:
            for cid in ids:
                requests.delete(collection_url(base_url, tenant_id, cid), headers=auth_headers)

    def test_filter_is_case_insensitive(self, base_url, auth_headers, tenant_id):
        """The name filter finds a collection regardless of search term casing (case-insensitive LIKE)."""
        suffix = _make_suffix()
        r = requests.post(
            collection_url(base_url, tenant_id),
            json=create_payload(name=f"FilterCase-{suffix}"),
            headers=auth_headers,
        )
        assert r.status_code == 201
        cid = r.json()["biometricCollection"]["id"]
        try:
            resp = requests.get(
                collection_url(base_url, tenant_id),
                params={"name": f"filtercase-{suffix}"},
                headers=auth_headers,
            )
            assert resp.status_code == 200
            ids = [c["id"] for c in resp.json()["biometricCollections"]]
            assert cid in ids, "Case-insensitive filter must find a collection created with different casing"
        finally:
            requests.delete(collection_url(base_url, tenant_id, cid), headers=auth_headers)

    def test_lowercase_after_mixed_case_returns_409(self, base_url, auth_headers, tenant_id):
        """[BUG-9] Creating 'demo' after 'Demo' must return 409 CONFLICT (case-insensitive uniqueness).

        Currently returns 201 because uniqueness is case-sensitive. This contradicts the
        case-insensitive filter: users cannot rely on search to detect duplicates before creating.
        MUST FAIL until the API enforces case-insensitive name uniqueness."""
        suffix = _make_suffix()
        first_id = None
        second_id = None
        try:
            r1 = requests.post(
                collection_url(base_url, tenant_id),
                json=create_payload(name=f"CIConflict-{suffix}"),
                headers=auth_headers,
            )
            assert r1.status_code == 201
            first_id = r1.json()["biometricCollection"]["id"]

            r2 = requests.post(
                collection_url(base_url, tenant_id),
                json=create_payload(name=f"ciconflict-{suffix}"),
                headers=auth_headers,
            )
            if r2.status_code == 201:
                second_id = r2.json()["biometricCollection"]["id"]
            assert r2.status_code == 409, (
                f"Expected 409 CONFLICT for lowercase duplicate, got {r2.status_code}. "
                "BUG-9: uniqueness is case-sensitive but filter is case-insensitive."
            )
        finally:
            for cid in (first_id, second_id):
                if cid:
                    requests.delete(collection_url(base_url, tenant_id, cid), headers=auth_headers)


class TestNameWhitespaceTrimming:
    """Whitespace handling on create and search."""

    def test_leading_whitespace_creates_separate_collection(self, base_url, auth_headers, tenant_id):
        """[BUG-8] Creating ' Demo' after 'Demo' must return 409 — leading whitespace should be trimmed.

        Currently returns 201 and stores the name verbatim with the leading space.
        This allows invisible duplicates that look identical in any UI.
        MUST FAIL until the API trims leading/trailing whitespace on create."""
        suffix = _make_suffix()
        first_id = None
        second_id = None
        try:
            r1 = requests.post(
                collection_url(base_url, tenant_id),
                json=create_payload(name=f"WSTest-{suffix}"),
                headers=auth_headers,
            )
            assert r1.status_code == 201
            first_id = r1.json()["biometricCollection"]["id"]

            r2 = requests.post(
                collection_url(base_url, tenant_id),
                json=create_payload(name=f" WSTest-{suffix}"),  # leading space
                headers=auth_headers,
            )
            if r2.status_code == 201:
                second_id = r2.json()["biometricCollection"]["id"]
            assert r2.status_code == 409, (
                f"Expected 409 CONFLICT — leading whitespace should be stripped. Got {r2.status_code}. BUG-8."
            )
        finally:
            for cid in (first_id, second_id):
                if cid:
                    requests.delete(collection_url(base_url, tenant_id, cid), headers=auth_headers)

    def test_trailing_whitespace_creates_separate_collection(self, base_url, auth_headers, tenant_id):
        """[BUG-8] Creating 'Demo ' after 'Demo' must return 409 — trailing whitespace should be trimmed.

        Currently returns 201 and stores the trailing space verbatim. MUST FAIL until fixed."""
        suffix = _make_suffix()
        first_id = None
        second_id = None
        try:
            r1 = requests.post(
                collection_url(base_url, tenant_id),
                json=create_payload(name=f"TWS-{suffix}"),
                headers=auth_headers,
            )
            assert r1.status_code == 201
            first_id = r1.json()["biometricCollection"]["id"]

            r2 = requests.post(
                collection_url(base_url, tenant_id),
                json=create_payload(name=f"TWS-{suffix} "),  # trailing space
                headers=auth_headers,
            )
            if r2.status_code == 201:
                second_id = r2.json()["biometricCollection"]["id"]
            assert r2.status_code == 409, (
                f"Expected 409 CONFLICT — trailing whitespace should be stripped. Got {r2.status_code}. BUG-8."
            )
        finally:
            for cid in (first_id, second_id):
                if cid:
                    requests.delete(collection_url(base_url, tenant_id, cid), headers=auth_headers)

    def test_both_sides_whitespace_creates_separate_collection(self, base_url, auth_headers, tenant_id):
        """[BUG-8] Creating ' Demo ' after 'Demo' must return 409 — both-sides whitespace should be trimmed.

        Currently returns 201. MUST FAIL until fixed."""
        suffix = _make_suffix()
        first_id = None
        second_id = None
        try:
            r1 = requests.post(
                collection_url(base_url, tenant_id),
                json=create_payload(name=f"BSWS-{suffix}"),
                headers=auth_headers,
            )
            assert r1.status_code == 201
            first_id = r1.json()["biometricCollection"]["id"]

            r2 = requests.post(
                collection_url(base_url, tenant_id),
                json=create_payload(name=f" BSWS-{suffix} "),  # space on both sides
                headers=auth_headers,
            )
            if r2.status_code == 201:
                second_id = r2.json()["biometricCollection"]["id"]
            assert r2.status_code == 409, (
                f"Expected 409 CONFLICT — surrounding whitespace should be stripped. Got {r2.status_code}. BUG-8."
            )
        finally:
            for cid in (first_id, second_id):
                if cid:
                    requests.delete(collection_url(base_url, tenant_id, cid), headers=auth_headers)

    def test_whitespace_name_is_stored_verbatim(self, base_url, auth_headers, tenant_id):
        """Documents current behavior: the stored name includes leading/trailing whitespace unchanged."""
        suffix = _make_suffix()
        padded_name = f" WSVerbatim-{suffix} "
        r = requests.post(
            collection_url(base_url, tenant_id),
            json=create_payload(name=padded_name),
            headers=auth_headers,
        )
        assert r.status_code == 201
        cid = r.json()["biometricCollection"]["id"]
        try:
            stored = r.json()["biometricCollection"]["name"]
            assert stored == padded_name, (
                f"Stored name {repr(stored)} should equal sent name {repr(padded_name)} "
                "(currently API stores verbatim — no trimming occurs)"
            )
        finally:
            requests.delete(collection_url(base_url, tenant_id, cid), headers=auth_headers)

    def test_filter_substring_finds_whitespace_padded_name(self, base_url, auth_headers, tenant_id):
        """Filter with the core name (no spaces) still finds a collection stored with surrounding spaces,
        because the filter is a CONTAINS (substring) match."""
        suffix = _make_suffix()
        core = f"SubFind-{suffix}"
        r = requests.post(
            collection_url(base_url, tenant_id),
            json=create_payload(name=f" {core} "),
            headers=auth_headers,
        )
        assert r.status_code == 201
        cid = r.json()["biometricCollection"]["id"]
        try:
            resp = requests.get(
                collection_url(base_url, tenant_id),
                params={"name": core},
                headers=auth_headers,
            )
            assert resp.status_code == 200
            ids = [c["id"] for c in resp.json()["biometricCollections"]]
            assert cid in ids, (
                "Filter must find a whitespace-padded collection when searching for the core name substring"
            )
        finally:
            requests.delete(collection_url(base_url, tenant_id, cid), headers=auth_headers)
