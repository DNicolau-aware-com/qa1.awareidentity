"""
Edge-case / robustness tests for /v3/tenants/{tenantId}/data-retention-policy.

These go beyond happy-path and structural validation to probe boundary and
adversarial inputs. Bugs found here are marked [BUG-R*] and assert the correct
(spec-conformant) behavior, so they FAIL until the server is fixed.
"""

import requests

from tests.retention.conftest import retention_url, valid_policy

_INT_MAX = 2147483647


def _strip(policy):
    return {k: v for k, v in policy.items() if k != "systemMaxRetentionDays"}


class TestNumericOverflow:
    """maxRetentionDays is a Java int; values past Integer.MAX_VALUE must be
    rejected with 400, not crash deserialization with 500.

    [BUG-R4] Any maxRetentionDays > 2147483647 returns 500
    "JSON parse error: Numeric value (...) out of range of int" — Jackson rejects
    it before validation and the error is not mapped to 400. (INT_MAX exactly is
    handled correctly: 400 SETTINGS_INVALID for exceeding the system ceiling.)
    MUST FAIL until numeric overflow is mapped to 400 VALIDATION_FAILED.
    """

    def test_max_retention_days_int_max_plus_one_returns_400(
        self, base_url, auth_headers, tenant_id, current_policy
    ):
        """maxRetentionDays = INT_MAX + 1 → 400 (not 500). [BUG-R4]"""
        payload = _strip(current_policy)
        payload["logs"]["maxRetentionDays"] = _INT_MAX + 1
        for mod in payload["logs"]["modalities"]:
            payload["logs"]["modalities"][mod] = 0
        resp = requests.put(retention_url(base_url, tenant_id), json=payload, headers=auth_headers)
        assert resp.status_code == 400

    def test_max_retention_days_long_overflow_returns_400(
        self, base_url, auth_headers, tenant_id, current_policy
    ):
        """maxRetentionDays = a value beyond Long range → 400 (not 500). [BUG-R4]"""
        payload = _strip(current_policy)
        payload["logs"]["maxRetentionDays"] = 9999999999999999999
        for mod in payload["logs"]["modalities"]:
            payload["logs"]["modalities"][mod] = 0
        resp = requests.put(retention_url(base_url, tenant_id), json=payload, headers=auth_headers)
        assert resp.status_code == 400

    def test_max_retention_days_int_max_is_handled(
        self, base_url, auth_headers, tenant_id, current_policy
    ):
        """Control case: maxRetentionDays = INT_MAX exactly is handled cleanly
        (400 SETTINGS_INVALID for exceeding the system ceiling — never 500)."""
        payload = _strip(current_policy)
        payload["logs"]["maxRetentionDays"] = _INT_MAX
        for mod in payload["logs"]["modalities"]:
            payload["logs"]["modalities"][mod] = 0
        resp = requests.put(retention_url(base_url, tenant_id), json=payload, headers=auth_headers)
        assert resp.status_code == 400
        assert resp.json().get("error") == "SETTINGS_INVALID"


class TestUnsupportedMethods:
    """Only GET and PUT are defined on this resource. POST, DELETE, and other
    methods must return 405 Method Not Allowed with an Allow header listing the
    supported methods (RFC 9110 §15.5.6).

    [BUG-R5] POST and DELETE return 500 — HttpRequestMethodNotSupportedException
    is not mapped to 405. The server knows the method but does not support it on
    this route; 500 is incorrect per RFC 9110.
    MUST FAIL until the exception is mapped to 405.
    """

    def test_post_method_returns_405(self, base_url, auth_headers, tenant_id):
        """POST to a GET/PUT-only resource → 405 (not 500). [BUG-R5]"""
        resp = requests.post(
            retention_url(base_url, tenant_id),
            json=valid_policy(),
            headers=auth_headers,
        )
        assert resp.status_code == 405

    def test_delete_method_returns_405(self, base_url, auth_headers, tenant_id):
        """DELETE to a GET/PUT-only resource → 405 (not 500). [BUG-R5]"""
        resp = requests.delete(
            retention_url(base_url, tenant_id),
            headers=auth_headers,
        )
        assert resp.status_code == 405

    def test_post_response_includes_allow_header(self, base_url, auth_headers, tenant_id):
        """405 response MUST include an Allow header listing supported methods
        (RFC 9110 §15.5.6). [BUG-R5]"""
        resp = requests.post(
            retention_url(base_url, tenant_id),
            json=valid_policy(),
            headers=auth_headers,
        )
        assert resp.status_code == 405
        allow = resp.headers.get("Allow", "")
        assert "GET" in allow
        assert "PUT" in allow

    def test_patch_method_returns_405(self, base_url, auth_headers, tenant_id):
        """PATCH to a GET/PUT-only resource → 405 (not 500). [BUG-R5]"""
        resp = requests.patch(
            retention_url(base_url, tenant_id),
            json={},
            headers=auth_headers,
        )
        assert resp.status_code == 405


class TestCategoryMaxConsistency:
    """Lowering maxRetentionDays must be consistent with modality values in the
    same PUT request — the server validates the final state, not the delta.

    If any modality value exceeds the new category max the whole request must
    fail with 400 SETTINGS_INVALID. The only way to lower the ceiling is to
    lower the affected modality values in the same payload.
    """

    def test_lowering_category_max_below_modality_values_returns_400(
        self, base_url, auth_headers, tenant_id, current_policy, system_ceilings
    ):
        """Lower templates.maxRetentionDays to half the ceiling while keeping
        modality values at the ceiling → 400 SETTINGS_INVALID."""
        payload = _strip(current_policy)
        ceiling = system_ceilings["templates"]
        new_max = ceiling // 2
        payload["templates"]["maxRetentionDays"] = new_max
        # leave modalities at ceiling — now they exceed new_max
        for mod in payload["templates"]["modalities"]:
            payload["templates"]["modalities"][mod] = ceiling
        resp = requests.put(retention_url(base_url, tenant_id), json=payload, headers=auth_headers)
        assert resp.status_code == 400
        assert resp.json().get("error") == "SETTINGS_INVALID"

    def test_lowering_category_max_and_modalities_together_returns_200(
        self, base_url, auth_headers, tenant_id, current_policy, system_ceilings
    ):
        """Lower templates.maxRetentionDays AND all modality values together
        in one PUT → 200 OK (consistent final state)."""
        payload = _strip(current_policy)
        ceiling = system_ceilings["templates"]
        new_max = ceiling // 2
        payload["templates"]["maxRetentionDays"] = new_max
        for mod in payload["templates"]["modalities"]:
            payload["templates"]["modalities"][mod] = new_max
        resp = requests.put(retention_url(base_url, tenant_id), json=payload, headers=auth_headers)
        assert resp.status_code == 200

    def test_lowering_category_max_with_some_modalities_above_returns_400(
        self, base_url, auth_headers, tenant_id, current_policy, system_ceilings
    ):
        """Even one modality above the new category max fails the whole request."""
        payload = _strip(current_policy)
        ceiling = system_ceilings["templates"]
        new_max = ceiling // 2
        payload["templates"]["maxRetentionDays"] = new_max
        mods = list(payload["templates"]["modalities"].keys())
        # set all modalities within range except the first one
        for mod in mods:
            payload["templates"]["modalities"][mod] = new_max
        if mods:
            payload["templates"]["modalities"][mods[0]] = new_max + 1
        resp = requests.put(retention_url(base_url, tenant_id), json=payload, headers=auth_headers)
        assert resp.status_code == 400
        assert resp.json().get("error") == "SETTINGS_INVALID"


class TestBooleanCoercion:
    """Boolean fields (autoDeleteExpired, saltLogsToRemovePii) must reject
    non-boolean JSON tokens — integers and strings must not be silently coerced.

    Currently Jackson coerces 0→false, 1→true, "true"→true, "false"→false
    and returns 200. All cases below MUST FAIL until strict boolean
    deserialization is enforced (400 VALIDATION_FAILED expected).
    """

    def test_auto_delete_integer_zero_returns_400(
        self, base_url, auth_headers, tenant_id, current_policy
    ):
        """autoDeleteExpired = 0 (int) → 400, not 200 with silent coercion to false."""
        payload = _strip(current_policy)
        payload["logs"]["autoDeleteExpired"] = 0
        resp = requests.put(retention_url(base_url, tenant_id), json=payload, headers=auth_headers)
        assert resp.status_code == 400

    def test_auto_delete_integer_one_returns_400(
        self, base_url, auth_headers, tenant_id, current_policy
    ):
        """autoDeleteExpired = 1 (int) → 400, not 200 with silent coercion to true."""
        payload = _strip(current_policy)
        payload["logs"]["autoDeleteExpired"] = 1
        resp = requests.put(retention_url(base_url, tenant_id), json=payload, headers=auth_headers)
        assert resp.status_code == 400

    def test_auto_delete_string_true_returns_400(
        self, base_url, auth_headers, tenant_id, current_policy
    ):
        """autoDeleteExpired = "true" (string) → 400, not 200 with silent coercion."""
        payload = _strip(current_policy)
        payload["logs"]["autoDeleteExpired"] = "true"
        resp = requests.put(retention_url(base_url, tenant_id), json=payload, headers=auth_headers)
        assert resp.status_code == 400

    def test_auto_delete_string_false_returns_400(
        self, base_url, auth_headers, tenant_id, current_policy
    ):
        """autoDeleteExpired = "false" (string) → 400, not 200 with silent coercion."""
        payload = _strip(current_policy)
        payload["logs"]["autoDeleteExpired"] = "false"
        resp = requests.put(retention_url(base_url, tenant_id), json=payload, headers=auth_headers)
        assert resp.status_code == 400

    def test_salt_logs_integer_returns_400(
        self, base_url, auth_headers, tenant_id, current_policy
    ):
        """saltLogsToRemovePii = 0 (int) → 400, not 200 with silent coercion."""
        payload = _strip(current_policy)
        payload["saltLogsToRemovePii"] = 0
        resp = requests.put(retention_url(base_url, tenant_id), json=payload, headers=auth_headers)
        assert resp.status_code == 400

    def test_salt_logs_string_returns_400(
        self, base_url, auth_headers, tenant_id, current_policy
    ):
        """saltLogsToRemovePii = "false" (string) → 400, not 200 with silent coercion."""
        payload = _strip(current_policy)
        payload["saltLogsToRemovePii"] = "false"
        resp = requests.put(retention_url(base_url, tenant_id), json=payload, headers=auth_headers)
        assert resp.status_code == 400


class TestModalityValueValidation:
    """Modality values must be non-negative integers. null, empty string, and
    string numbers must be rejected. A null value currently returns 200 but
    silently keeps the previous value — misleading and incorrect.

    All cases below MUST FAIL until strict value validation is enforced.
    """

    def test_modality_value_null_returns_400(
        self, base_url, auth_headers, tenant_id, current_policy
    ):
        """Modality value = null → 400 (not 200 with silent ignore of the update)."""
        payload = _strip(current_policy)
        payload["logs"]["modalities"]["Face"] = None
        resp = requests.put(retention_url(base_url, tenant_id), json=payload, headers=auth_headers)
        assert resp.status_code == 400

    def test_modality_value_string_number_returns_400(
        self, base_url, auth_headers, tenant_id, current_policy
    ):
        """Modality value = "30" (string) → 400, not 200 with silent coercion to int."""
        payload = _strip(current_policy)
        payload["logs"]["modalities"]["Face"] = "30"
        resp = requests.put(retention_url(base_url, tenant_id), json=payload, headers=auth_headers)
        assert resp.status_code == 400

    def test_modality_value_empty_string_returns_400(
        self, base_url, auth_headers, tenant_id, current_policy
    ):
        """Modality value = "" (empty string) → 400."""
        payload = _strip(current_policy)
        payload["logs"]["modalities"]["Face"] = ""
        resp = requests.put(retention_url(base_url, tenant_id), json=payload, headers=auth_headers)
        assert resp.status_code == 400


class TestModalityKeyValidation:
    """Modality keys must contain only safe printable characters. Control
    characters (null byte, newline) are currently accepted and stored verbatim.

    All cases below MUST FAIL until modality key validation is enforced.
    """

    def test_modality_key_null_byte_returns_400(
        self, base_url, auth_headers, tenant_id, current_policy
    ):
        """Modality key with null byte \\x00 → 400 (control character rejected)."""
        payload = _strip(current_policy)
        payload["logs"]["modalities"]["Face\x00Null"] = 1
        resp = requests.put(retention_url(base_url, tenant_id), json=payload, headers=auth_headers)
        assert resp.status_code == 400

    def test_modality_key_newline_returns_400(
        self, base_url, auth_headers, tenant_id, current_policy
    ):
        """Modality key with newline \\n → 400 (control character rejected)."""
        payload = _strip(current_policy)
        payload["logs"]["modalities"]["Face\nNewline"] = 1
        resp = requests.put(retention_url(base_url, tenant_id), json=payload, headers=auth_headers)
        assert resp.status_code == 400
