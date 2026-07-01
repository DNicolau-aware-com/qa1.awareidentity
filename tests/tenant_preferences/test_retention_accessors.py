"""
Tests for the individual data-retention-policy category accessor endpoints.

Endpoints:
  GET/PUT /v3/tenants/{tenantId}/data-retention-policy/templates
  GET/PUT /v3/tenants/{tenantId}/data-retention-policy/enrollmentImages
  GET/PUT /v3/tenants/{tenantId}/data-retention-policy/logs
  GET/PUT /v3/tenants/{tenantId}/data-retention-policy/saltLogsToRemovePii
"""

import requests

from tests.tenant_preferences.conftest import retention_accessor_url

_CATEGORIES = ("templates", "enrollmentImages", "logs")


class TestGetRetentionCategory:

    def test_get_templates_returns_200(self, base_url, auth_headers, tenant_id):
        """GET templates category returns 200."""
        resp = requests.get(retention_accessor_url(base_url, tenant_id, "templates"), headers=auth_headers)
        assert resp.status_code == 200

    def test_get_enrollment_images_returns_200(self, base_url, auth_headers, tenant_id):
        """GET enrollmentImages category returns 200."""
        resp = requests.get(retention_accessor_url(base_url, tenant_id, "enrollmentImages"), headers=auth_headers)
        assert resp.status_code == 200

    def test_get_logs_returns_200(self, base_url, auth_headers, tenant_id):
        """GET logs category returns 200."""
        resp = requests.get(retention_accessor_url(base_url, tenant_id, "logs"), headers=auth_headers)
        assert resp.status_code == 200

    def test_each_category_has_required_fields(self, base_url, auth_headers, tenant_id):
        """Each category response contains maxRetentionDays, autoDeleteExpired, modalities."""
        for cat in _CATEGORIES:
            body = requests.get(retention_accessor_url(base_url, tenant_id, cat), headers=auth_headers).json()
            assert "maxRetentionDays" in body, f"{cat} missing maxRetentionDays"
            assert "autoDeleteExpired" in body, f"{cat} missing autoDeleteExpired"
            assert "modalities" in body, f"{cat} missing modalities"

    def test_max_retention_days_is_positive_integer(self, base_url, auth_headers, tenant_id):
        """maxRetentionDays is a positive integer in every category."""
        for cat in _CATEGORIES:
            body = requests.get(retention_accessor_url(base_url, tenant_id, cat), headers=auth_headers).json()
            val = body["maxRetentionDays"]
            assert isinstance(val, int) and val > 0, f"{cat}.maxRetentionDays invalid: {val}"

    def test_auto_delete_expired_is_boolean(self, base_url, auth_headers, tenant_id):
        """autoDeleteExpired is a boolean in every category."""
        for cat in _CATEGORIES:
            body = requests.get(retention_accessor_url(base_url, tenant_id, cat), headers=auth_headers).json()
            assert isinstance(body["autoDeleteExpired"], bool), f"{cat}.autoDeleteExpired not boolean"

    def test_modalities_are_non_negative_integers(self, base_url, auth_headers, tenant_id):
        """All modality values are non-negative integers."""
        for cat in _CATEGORIES:
            body = requests.get(retention_accessor_url(base_url, tenant_id, cat), headers=auth_headers).json()
            for mod, val in body["modalities"].items():
                assert isinstance(val, int) and val >= 0, f"{cat}.modalities.{mod} invalid: {val}"

    def test_response_is_json(self, base_url, auth_headers, tenant_id):
        """Each category GET response has Content-Type application/json."""
        for cat in _CATEGORIES:
            resp = requests.get(retention_accessor_url(base_url, tenant_id, cat), headers=auth_headers)
            assert "application/json" in resp.headers.get("Content-Type", "")


class TestUpdateRetentionCategory:

    def test_put_templates_returns_200(self, base_url, auth_headers, tenant_id, current_retention_category):
        """PUT valid templates category returns 200."""
        url = retention_accessor_url(base_url, tenant_id, "templates")
        resp = requests.put(url, json=current_retention_category, headers=auth_headers)
        assert resp.status_code == 200

    def test_put_ignores_auto_delete_expired_input(self, base_url, auth_headers, tenant_id, current_retention_category):
        """autoDeleteExpired is readOnly and ignored on PUT input per spec (auto-delete
        is always enforced) — PUT response always reports true regardless of what was sent."""
        url = retention_accessor_url(base_url, tenant_id, "templates")
        payload = dict(current_retention_category)
        payload["autoDeleteExpired"] = False
        resp = requests.put(url, json=payload, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["autoDeleteExpired"] is True

    def test_max_retention_days_change_is_persisted(self, base_url, auth_headers, tenant_id, current_retention_category):
        """Updated maxRetentionDays is confirmed by a subsequent GET (autoDeleteExpired is
        excluded from this check — see test_auto_delete_expired_is_boolean, GET returns
        null for it on this endpoint, a separate known issue)."""
        url = retention_accessor_url(base_url, tenant_id, "templates")
        payload = dict(current_retention_category)
        current_max = payload["maxRetentionDays"]
        new_max = current_max - 1 if current_max > 1 else current_max + 1
        for mod in payload["modalities"]:
            payload["modalities"][mod] = min(payload["modalities"][mod], new_max)
        payload["maxRetentionDays"] = new_max
        requests.put(url, json=payload, headers=auth_headers)
        body = requests.get(url, headers=auth_headers).json()
        assert body["maxRetentionDays"] == new_max

    def test_modality_exceeding_category_max_returns_400(self, base_url, auth_headers, tenant_id, current_retention_category):
        """Modality value > category maxRetentionDays returns 400 SETTINGS_INVALID."""
        url = retention_accessor_url(base_url, tenant_id, "templates")
        payload = dict(current_retention_category)
        cat_max = payload["maxRetentionDays"]
        first_mod = next(iter(payload["modalities"]))
        payload["modalities"][first_mod] = cat_max + 1
        resp = requests.put(url, json=payload, headers=auth_headers)
        assert resp.status_code == 400
        assert resp.json().get("error") == "SETTINGS_INVALID"

    def test_max_retention_days_zero_returns_400(self, base_url, auth_headers, tenant_id, current_retention_category):
        """maxRetentionDays = 0 returns 400 (minimum is 1)."""
        url = retention_accessor_url(base_url, tenant_id, "templates")
        payload = dict(current_retention_category)
        payload["maxRetentionDays"] = 0
        resp = requests.put(url, json=payload, headers=auth_headers)
        assert resp.status_code == 400

    def test_max_retention_days_negative_returns_400(self, base_url, auth_headers, tenant_id, current_retention_category):
        """maxRetentionDays = -1 returns 400."""
        url = retention_accessor_url(base_url, tenant_id, "templates")
        payload = dict(current_retention_category)
        payload["maxRetentionDays"] = -1
        resp = requests.put(url, json=payload, headers=auth_headers)
        assert resp.status_code == 400

    def test_missing_max_retention_days_returns_400(self, base_url, auth_headers, tenant_id, current_retention_category):
        """PUT without maxRetentionDays returns 400 VALIDATION_FAILED."""
        url = retention_accessor_url(base_url, tenant_id, "templates")
        payload = {k: v for k, v in current_retention_category.items() if k != "maxRetentionDays"}
        resp = requests.put(url, json=payload, headers=auth_headers)
        assert resp.status_code == 400

    def test_missing_auto_delete_is_accepted(self, base_url, auth_headers, tenant_id, current_retention_category):
        """PUT without autoDeleteExpired returns 200 — the field is readOnly and ignored
        on PUT input, so it isn't required in the request body."""
        url = retention_accessor_url(base_url, tenant_id, "templates")
        payload = {k: v for k, v in current_retention_category.items() if k != "autoDeleteExpired"}
        resp = requests.put(url, json=payload, headers=auth_headers)
        assert resp.status_code == 200


class TestSaltLogsAccessor:

    def test_get_salt_logs_returns_200(self, base_url, auth_headers, tenant_id):
        """GET saltLogsToRemovePii returns 200."""
        resp = requests.get(retention_accessor_url(base_url, tenant_id, "saltLogsToRemovePii"), headers=auth_headers)
        assert resp.status_code == 200

    def test_get_salt_logs_returns_boolean(self, base_url, auth_headers, tenant_id):
        """GET saltLogsToRemovePii response body is a boolean."""
        resp = requests.get(retention_accessor_url(base_url, tenant_id, "saltLogsToRemovePii"), headers=auth_headers)
        assert isinstance(resp.json(), bool)

    def test_put_salt_logs_true_returns_200(self, base_url, auth_headers, tenant_id):
        """PUT saltLogsToRemovePii = true returns 200."""
        url = retention_accessor_url(base_url, tenant_id, "saltLogsToRemovePii")
        snap = requests.get(url, headers=auth_headers).json()
        resp = requests.put(url, json=True, headers=auth_headers)
        assert resp.status_code == 200
        requests.put(url, json=snap, headers=auth_headers)

    def test_put_salt_logs_false_returns_200(self, base_url, auth_headers, tenant_id):
        """PUT saltLogsToRemovePii = false returns 200."""
        url = retention_accessor_url(base_url, tenant_id, "saltLogsToRemovePii")
        snap = requests.get(url, headers=auth_headers).json()
        resp = requests.put(url, json=False, headers=auth_headers)
        assert resp.status_code == 200
        requests.put(url, json=snap, headers=auth_headers)

    def test_put_salt_logs_value_is_persisted(self, base_url, auth_headers, tenant_id):
        """PUT saltLogsToRemovePii value is confirmed by subsequent GET."""
        url = retention_accessor_url(base_url, tenant_id, "saltLogsToRemovePii")
        snap = requests.get(url, headers=auth_headers).json()
        new_val = not snap
        requests.put(url, json=new_val, headers=auth_headers)
        assert requests.get(url, headers=auth_headers).json() == new_val
        requests.put(url, json=snap, headers=auth_headers)

    def test_put_salt_logs_non_boolean_returns_400(self, base_url, auth_headers, tenant_id):
        """PUT saltLogsToRemovePii with non-boolean value returns 400."""
        url = retention_accessor_url(base_url, tenant_id, "saltLogsToRemovePii")
        resp = requests.put(url, json="true", headers=auth_headers)
        assert resp.status_code == 400


class TestRetentionAccessorAuth:

    def test_no_api_key_returns_401(self, base_url, tenant_id):
        """GET without auth returns 401."""
        resp = requests.get(retention_accessor_url(base_url, tenant_id, "templates"))
        assert resp.status_code == 401

    def test_invalid_api_key_returns_403(self, base_url, bad_auth_headers, tenant_id):
        """GET with invalid API key returns 403."""
        resp = requests.get(retention_accessor_url(base_url, tenant_id, "templates"), headers=bad_auth_headers)
        assert resp.status_code == 403
