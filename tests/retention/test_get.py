"""
Tests for GET /v3/tenants/{tenantId}/data-retention-policy

The endpoint returns the full policy plus systemMaxRetentionDays (read-only,
recomputed from configuration on every read).  Every field is seeded at tenant
creation, so a missing row is an integrity error (500), never silently defaulted.
"""

import requests

from tests.retention.conftest import retention_url

_CATEGORIES = ("templates", "enrollmentImages", "logs")


class TestGetHappyPath:

    def test_returns_200(self, base_url, auth_headers, tenant_id):
        """GET returns 200 for a valid tenant."""
        resp = requests.get(retention_url(base_url, tenant_id), headers=auth_headers)
        assert resp.status_code == 200

    def test_response_content_type_is_json(self, base_url, auth_headers, tenant_id):
        """Response Content-Type is application/json."""
        resp = requests.get(retention_url(base_url, tenant_id), headers=auth_headers)
        assert "application/json" in resp.headers.get("Content-Type", "")

    def test_response_contains_all_three_categories(self, base_url, auth_headers, tenant_id):
        """Response contains templates, enrollmentImages, and logs."""
        body = requests.get(retention_url(base_url, tenant_id), headers=auth_headers).json()
        for cat in _CATEGORIES:
            assert cat in body, f"Missing category: {cat}"

    def test_response_contains_system_max_retention_days(self, base_url, auth_headers, tenant_id):
        """Response includes systemMaxRetentionDays (server-computed ceiling per category)."""
        body = requests.get(retention_url(base_url, tenant_id), headers=auth_headers).json()
        assert "systemMaxRetentionDays" in body

    def test_response_contains_salt_logs_flag(self, base_url, auth_headers, tenant_id):
        """Response includes saltLogsToRemovePii flag."""
        body = requests.get(retention_url(base_url, tenant_id), headers=auth_headers).json()
        assert "saltLogsToRemovePii" in body


class TestGetShape:
    """Verify the structure and types of every field in the GET response."""

    def test_each_category_has_required_fields(self, base_url, auth_headers, tenant_id):
        """Each data category contains maxRetentionDays, autoDeleteExpired, and modalities."""
        body = requests.get(retention_url(base_url, tenant_id), headers=auth_headers).json()
        for cat in _CATEGORIES:
            c = body[cat]
            assert "maxRetentionDays" in c, f"{cat}: missing maxRetentionDays"
            assert "autoDeleteExpired" in c, f"{cat}: missing autoDeleteExpired"
            assert "modalities" in c, f"{cat}: missing modalities"

    def test_max_retention_days_is_positive_integer(self, base_url, auth_headers, tenant_id):
        """maxRetentionDays is an integer ≥ 1 in every category."""
        body = requests.get(retention_url(base_url, tenant_id), headers=auth_headers).json()
        for cat in _CATEGORIES:
            val = body[cat]["maxRetentionDays"]
            assert isinstance(val, int) and val >= 1, \
                f"{cat}.maxRetentionDays must be integer ≥ 1, got {val!r}"

    def test_auto_delete_expired_is_boolean(self, base_url, auth_headers, tenant_id):
        """autoDeleteExpired is a boolean in every category."""
        body = requests.get(retention_url(base_url, tenant_id), headers=auth_headers).json()
        for cat in _CATEGORIES:
            val = body[cat]["autoDeleteExpired"]
            assert isinstance(val, bool), \
                f"{cat}.autoDeleteExpired must be boolean, got {type(val).__name__}"

    def test_modalities_are_non_negative_integers(self, base_url, auth_headers, tenant_id):
        """Every modality value is an integer in the range [0, category max]."""
        body = requests.get(retention_url(base_url, tenant_id), headers=auth_headers).json()
        for cat in _CATEGORIES:
            for mod, days in body[cat]["modalities"].items():
                assert isinstance(days, int) and days >= 0, \
                    f"{cat}.modalities.{mod} must be integer ≥ 0, got {days!r}"

    def test_modalities_is_a_non_empty_object(self, base_url, auth_headers, tenant_id):
        """modalities is a non-empty dict in every category."""
        body = requests.get(retention_url(base_url, tenant_id), headers=auth_headers).json()
        for cat in _CATEGORIES:
            mods = body[cat]["modalities"]
            assert isinstance(mods, dict) and len(mods) > 0, \
                f"{cat}.modalities must be a non-empty object"

    def test_system_max_retention_days_is_object(self, base_url, auth_headers, tenant_id):
        """systemMaxRetentionDays is a dict."""
        body = requests.get(retention_url(base_url, tenant_id), headers=auth_headers).json()
        assert isinstance(body["systemMaxRetentionDays"], dict)

    def test_system_max_retention_days_has_all_categories(self, base_url, auth_headers, tenant_id):
        """systemMaxRetentionDays contains an entry for every data category."""
        body = requests.get(retention_url(base_url, tenant_id), headers=auth_headers).json()
        ceilings = body["systemMaxRetentionDays"]
        for cat in _CATEGORIES:
            assert cat in ceilings, f"systemMaxRetentionDays missing category: {cat}"

    def test_system_max_values_are_positive_integers(self, base_url, auth_headers, tenant_id):
        """Each value in systemMaxRetentionDays is an integer ≥ 1."""
        body = requests.get(retention_url(base_url, tenant_id), headers=auth_headers).json()
        for cat, ceiling in body["systemMaxRetentionDays"].items():
            assert isinstance(ceiling, int) and ceiling >= 1, \
                f"systemMaxRetentionDays.{cat} must be integer ≥ 1, got {ceiling!r}"

    def test_salt_logs_to_remove_pii_is_boolean(self, base_url, auth_headers, tenant_id):
        """saltLogsToRemovePii is a boolean."""
        body = requests.get(retention_url(base_url, tenant_id), headers=auth_headers).json()
        assert isinstance(body["saltLogsToRemovePii"], bool)


class TestGetDataIntegrity:
    """Business-rule assertions on the GET response — values must be internally consistent."""

    def test_modality_values_do_not_exceed_category_max(self, base_url, auth_headers, tenant_id):
        """Every modality's days value is ≤ its category's maxRetentionDays."""
        body = requests.get(retention_url(base_url, tenant_id), headers=auth_headers).json()
        for cat in _CATEGORIES:
            cat_max = body[cat]["maxRetentionDays"]
            for mod, days in body[cat]["modalities"].items():
                assert days <= cat_max, \
                    f"{cat}.modalities.{mod} ({days}) exceeds category max ({cat_max})"

    def test_category_max_does_not_exceed_system_ceiling(self, base_url, auth_headers, tenant_id):
        """Every category's maxRetentionDays is ≤ its system ceiling."""
        body = requests.get(retention_url(base_url, tenant_id), headers=auth_headers).json()
        ceilings = body["systemMaxRetentionDays"]
        for cat in _CATEGORIES:
            cat_max = body[cat]["maxRetentionDays"]
            ceiling = ceilings.get(cat)
            if ceiling is not None:
                assert cat_max <= ceiling, \
                    f"{cat}.maxRetentionDays ({cat_max}) exceeds system ceiling ({ceiling})"

    def test_get_is_idempotent(self, base_url, auth_headers, tenant_id):
        """Two consecutive GETs return the same policy values (no side effects on read)."""
        r1 = requests.get(retention_url(base_url, tenant_id), headers=auth_headers).json()
        r2 = requests.get(retention_url(base_url, tenant_id), headers=auth_headers).json()
        for cat in _CATEGORIES:
            assert r1[cat]["maxRetentionDays"] == r2[cat]["maxRetentionDays"], \
                f"{cat}.maxRetentionDays changed between consecutive reads"
            assert r1[cat]["autoDeleteExpired"] == r2[cat]["autoDeleteExpired"]
        assert r1["saltLogsToRemovePii"] == r2["saltLogsToRemovePii"]


class TestGetNotFound:

    def test_unknown_tenant_returns_404(self, base_url, auth_headers):
        """GET for a well-formed but non-existent tenant UUID returns 404."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        resp = requests.get(retention_url(base_url, fake_id), headers=auth_headers)
        assert resp.status_code == 404
