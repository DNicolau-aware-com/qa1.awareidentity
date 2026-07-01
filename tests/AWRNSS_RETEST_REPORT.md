# AWRNSS Ticket Retest Report

**Environment:** `https://api.qa2.awareidentity.com`
**Tenant (test02):** `57bf3cfb-09c7-4dc5-8d33-68423e269bba`
**Date:** 2026-07-01
**Suites involved:** `tests/retention/` (87 tests), `tests/tenant_preferences/` (128 tests, incl. new `test_security_settings_bulk.py` added 2026-07-01 covering the bulk `GET/PUT /v3/tenants/{tenantId}/security-settings` endpoint — 23 tests, all passing)

Retest pass of all "Ready For QA" / "In Progress" AWRNSS tickets against qa2, cross-checked
against `tenantpref-external.openapi.yaml` and `tenantpref-internal.openapi.yaml`. Two tickets
initially assumed broken (autoDeleteExpired non-persistence, missing-saltLogsToRemovePii) turned
out to be spec-compliant, not bugs — see "Corrections" below before trusting old assumptions in
either test suite.

---

## Ticket status

### Still open — bug reproduces on qa2

| Ticket | Summary | Evidence |
|---|---|---|
| **AWRNSS-468** | API key does not enforce tenant scope | test02's API key + `X-Aware-AccountId` successfully read test01's preferences by substituting test01's `tenantId` in the URL path. `GET /v3/tenants/{test01_id}/preferences` → 200 with test01's rows, using test02's key. |
| **AWRNSS-467** | POST `/preferences/{key}/{subKey}` accepts unbounded value length | 201 at 5,000 / 50,000 / 1,000,000-char values, no cap. `tests/tenant_preferences/test_preferences.py::TestValueValidation::test_oversized_value_returns_400` |
| **AWRNSS-460** | PUT data-retention-policy silently accepts invalid modality inputs | Narrower than filed: modality **key** validation (null byte, newline) and non-numeric/empty-string **values** are now correctly rejected (400). Only `modalities.<mod> = null` still returns 200 (silently ignored) instead of 400. `tests/retention/test_edge_cases.py::TestModalityValueValidation::test_modality_value_null_returns_400` |

### Fixed — safe to close

| Ticket | Summary | Confirmed |
|---|---|---|
| AWRNSS-469 | POST subKey with `/` or HTML chars → 500 | Now 400 for all 6 repro cases (slash, `<script>`, space, dot, unicode, SQLi string) |
| AWRNSS-466 | POST accepts invalid JSON when valueType=JSON | Now 400 |
| AWRNSS-465 | Bulk upsert duplicate subKey → duplicated response | No longer duplicates |
| AWRNSS-463 | PUT /security-settings → 500 for invalid inputs | Now 400 across missing field, string/float type, unknown field, empty body, null body |
| AWRNSS-462 | PUT /security-settings silently coerces wrong types | String/float now correctly rejected with 400 |
| AWRNSS-461 | sessionTimeoutMinutes / passwordResetLinkLifetimeMinutes enum not validated | Enum `{15,30,60,120}` / `{15,30,60,120,1440}` now enforced on both the bulk endpoint and the individual accessors |
| AWRNSS-459 | Unsupported HTTP methods → 500 | Now 405 with `Allow` header (POST/DELETE/PATCH tested) |
| AWRNSS-458 | maxRetentionDays > INT_MAX → 500 | Now 400 |
| AWRNSS-457 | Non-UUID tenantId → 500 | Now 400 |
| AWRNSS-456 | Missing saltLogsToRemovePii → 500 | Now 400 — correct per spec, see Corrections |
| AWRNSS-455 | Invalid PUT body (bad types, empty body) → 500 | Now 400 |

### Cannot verify

| Ticket | Summary | Why |
|---|---|---|
| AWRNSS-454 | Data Management page fails (500) for tenants created before retention seeding | Requires a tenant provisioned before the seeding logic existed; test01/test02 are both already seeded. Needs either a legacy tenant or a DB-level repro to confirm. |

---

## Corrections made to prior test-suite assumptions

Two "bugs" the test suite asserted turned out to be **spec-compliant behavior**, discovered by
re-reading `tenantpref-external.openapi.yaml` / `tenantpref-internal.openapi.yaml` closely:

1. **`autoDeleteExpired` is `readOnly: true` and explicitly "ignored on PUT input"** (auto-delete
   is always enforced, cannot be disabled). Tests that expected a PUT toggle of this field to
   persist, or expected omitting/mistyping it to return 400, were wrong. Fixed in
   `tests/retention/test_update.py` (`test_auto_delete_for_templates_ignored_on_put`,
   `test_missing_auto_delete_in_category_is_accepted`, `test_non_boolean_auto_delete_is_ignored`),
   `tests/retention/test_edge_cases.py` (new `TestAutoDeleteExpiredIgnoredOnInput`, replacing 4
   wrong cases in `TestBooleanCoercion`), and `tests/tenant_preferences/test_retention_accessors.py`
   (`test_put_ignores_auto_delete_expired_input`, `test_missing_auto_delete_is_accepted`).

2. **`saltLogsToRemovePii` IS in `DataRetentionPolicy.required`** (`[templates, enrollmentImages,
   logs, saltLogsToRemovePii]`), contradicting older suite notes that called it optional. Omitting
   it correctly returns 400. Fixed in `test_update.py::test_missing_salt_logs_flag_returns_400`.

3. **`passwordResetLinkLifetimeMinutes` is a 5-value enum** (`15, 30, 60, 120, 1440`), not a
   continuous 1–1440 range. Tests that treated `1` and `720` as valid were wrong — both correctly
   return 400. Fixed in `tests/tenant_preferences/test_security_accessors.py`.

---

## New defects found (not yet filed)

### DEFECT-A — `saltLogsToRemovePii` silently coerces non-boolean JSON values

**Endpoints:** `PUT /v3/tenants/{tenantId}/data-retention-policy` (bulk),
`PUT /v3/tenants/{tenantId}/data-retention-policy/saltLogsToRemovePii` (individual accessor)

**Expected:** `type: boolean` per spec → non-boolean JSON (int/string) returns 400 VALIDATION_FAILED.
**Actual:** 200, with Jackson lenient coercion: `0`→false, `1`→true, `"false"`→false, `"true"`→true.
Arbitrary non-boolean strings (e.g. `"nope"`) are still correctly rejected — the gap is specifically
the coercible tokens.

**Regression tests:** `tests/retention/test_edge_cases.py::TestBooleanCoercion` (bulk),
`tests/tenant_preferences/test_retention_accessors.py::TestSaltLogsAccessor::test_put_salt_logs_non_boolean_returns_400`
(accessor) — both currently fail against this.

### DEFECT-B — Individual retention-category accessor GET returns `autoDeleteExpired: null`

**Endpoint:** `GET /v3/tenants/{tenantId}/data-retention-policy/{templates|enrollmentImages|logs}`

**Expected:** Per spec, "Always true" — every GET should show `true`.
**Actual:** GET on all three individual accessors returns `autoDeleteExpired: null`. The bulk
endpoint (`GET /v3/tenants/{tenantId}/data-retention-policy`) correctly returns `true` for the same
tenant/categories — the bug is isolated to the individual accessors' GET path. (PUT responses on
the same accessors correctly show `true`.)

**Regression test:** `tests/tenant_preferences/test_retention_accessors.py::TestGetRetentionCategory::test_auto_delete_expired_is_boolean`
— currently fails against this.

### DEFECT-C — `session_timeout_minutes` / `password_reset_link_lifetime` individual accessors silently coerce numeric strings and decimals

**Endpoints:** `PUT /v3/tenants/{tenantId}/security-settings/session_timeout_minutes`,
`PUT /v3/tenants/{tenantId}/security-settings/password_reset_link_lifetime`

**Expected:** Per spec, "Must be a whole number — a decimal, string, boolean, or out-of-range
value returns 400 VALIDATION_FAILED."
**Actual:** `200` for a numeric string matching a valid enum value (`"30"`→30) and for a decimal
(`30.5`→30, silently truncated) — on **both** accessors. Boolean, `null`, array, and huge-number
inputs are all correctly rejected (400) on both. The **bulk** endpoint (`PUT
/v3/tenants/{tenantId}/security-settings`) correctly rejects numeric strings and decimals for both
fields — the gap is isolated to the individual accessors.

**Evidence:**
```
PUT .../security-settings/session_timeout_minutes   body: "30"    -> 200, body: 30
PUT .../security-settings/session_timeout_minutes   body: 30.5    -> 200, body: 30
PUT .../security-settings/password_reset_link_lifetime  body: "60" -> 200, body: 60
PUT .../security-settings/password_reset_link_lifetime  body: 60.5 -> 200, body: 60

For comparison, same inputs on the bulk endpoint:
PUT .../security-settings {"sessionTimeoutMinutes": "30", ...}  -> 400 VALIDATION_FAILED
PUT .../security-settings {"sessionTimeoutMinutes": 30.0, ...}  -> 400 VALIDATION_FAILED
```

**Regression tests:** `tests/tenant_preferences/test_security_accessors.py::TestAccessorTypeCoercion::test_numeric_string_returns_400`,
`::test_decimal_returns_400` (both parametrized over both fields) — currently fail against this.

**Related documentation bug (not a server bug):** manually reproduced via Postman
(`PUT .../security-settings/password_reset_link_lifetime`, body `"30"` → `200 OK`, body `30`),
which surfaced that the team's Postman collection documents the wrong "Example Value" for this
endpoint — it shows the **bulk** `SecuritySettings` object shape
(`{"sessionTimeoutMinutes": 60, "passwordResetLinkLifetimeMinutes": 1440}`) instead of a bare
integer, which is what this individual accessor actually takes. Confirmed the real contract is a
bare integer: sending the documented object shape to this endpoint returns `400`
(`"Request body could not be parsed: malformed or invalid JSON"`). Locked in by
`test_security_accessors.py::TestUpdatePasswordResetLifetime::test_put_bulk_object_shape_returns_400`
so that if this is ever "fixed" by changing the endpoint to match the wrong doc instead of fixing
the doc, the regression is caught. The collection example itself should be corrected separately
(outside this test suite's scope).

---

## Suite pass rates after corrections

| Suite | Passed | Failed | Failing tests map to |
|---|---|---|---|
| `tests/retention/` | 84 | 3 | AWRNSS-460 (modality null) ×1, DEFECT-A ×2 |
| `tests/tenant_preferences/test_preferences.py` | 51 | 3 | AWRNSS-467 ×3 |
| `tests/tenant_preferences/test_retention_accessors.py` | 49 | 2 | DEFECT-A ×1, DEFECT-B ×1 |
| `tests/tenant_preferences/test_security_accessors.py` | 41 | 4 | DEFECT-C ×4 |
| `tests/tenant_preferences/test_security_settings_bulk.py` | 23 | 0 | — |
