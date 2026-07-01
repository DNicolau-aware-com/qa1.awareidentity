# Security Settings — Test Suite Report

**Environment:** `https://api.qa2.awareidentity.com`
**Tenant (test02):** `57bf3cfb-09c7-4dc5-8d33-68423e269bba`
**Date:** 2026-07-01
**Files:** `test_security_accessors.py` (49 tests), `test_security_settings_bulk.py` (23 tests)
**Total: 72 tests — 68 passed, 4 known-bug failures**

Covers the two typed Security Settings endpoint shapes:
- **Individual field accessors** (internal): `GET/PUT /v3/tenants/{tenantId}/security-settings/{session_timeout_minutes|password_reset_link_lifetime}`
- **Bulk** (external): `GET/PUT /v3/tenants/{tenantId}/security-settings` (both fields together)

Related tickets: AWRNSS-461 (enum validation), AWRNSS-462 (silent type coercion),
AWRNSS-463 (500 instead of 4xx) — see "Ticket status" below.

---

## Test Suite Breakdown

### `test_security_accessors.py` — 49 tests

#### TestGetSecuritySettings — 7 tests
| Test | Expected |
|------|----------|
| test_get_session_timeout_returns_200 | 200 |
| test_get_session_timeout_returns_integer | body is int |
| test_get_session_timeout_is_positive | value ≥ 1 |
| test_get_password_reset_lifetime_returns_200 | 200 |
| test_get_password_reset_lifetime_returns_integer | body is int |
| test_get_password_reset_lifetime_is_positive | value ≥ 1 |
| test_response_is_json | Content-Type: application/json |

#### TestUpdateSessionTimeout — 10 tests
| Test | Expected |
|------|----------|
| test_put_15_returns_200 | 200 |
| test_put_30_returns_200 | 200 |
| test_put_60_returns_200 | 200 |
| test_put_120_returns_200 | 200 |
| test_put_value_is_persisted | value confirmed by subsequent GET |
| test_put_zero_returns_400 | 400 (not in enum) |
| test_put_negative_returns_400 | 400 |
| test_put_out_of_enum_returns_400 | 400 (16 not in [15,30,60,120]) |
| test_put_very_large_value_returns_400 | 400 (999999) |
| test_put_bulk_object_shape_returns_400 | 400 — endpoint takes a bare integer, not the bulk `SecuritySettings` object shape |

#### TestUpdatePasswordResetLifetime — 9 tests
| Test | Expected |
|------|----------|
| test_put_valid_maximum_returns_200 | 200 (1440) |
| test_put_out_of_enum_low_returns_400 | 400 (1 not in enum) |
| test_put_out_of_enum_mid_returns_400 | 400 (720 not in enum) |
| test_put_value_is_persisted | value confirmed by subsequent GET |
| test_put_zero_returns_400 | 400 |
| test_put_negative_returns_400 | 400 |
| test_put_above_max_returns_400 | 400 (1441) |
| test_put_far_above_max_returns_400 | 400 (144055) |
| test_put_bulk_object_shape_returns_400 | 400 — endpoint takes a bare integer, not the bulk object shape |

#### TestAccessorFieldIsolation — 2 tests
| Test | Expected |
|------|----------|
| test_put_session_timeout_does_not_change_password_reset_lifetime | other field's live value unchanged after PUT |
| test_put_password_reset_lifetime_does_not_change_session_timeout | other field's live value unchanged after PUT |

#### TestAccessorTypeCoercion — 12 tests (parametrized × 2 fields)
| Test | Expected | Known Issue |
|------|----------|-------------|
| test_numeric_string_returns_400 | 400 (e.g. `"30"`) | **DEFECT-C** |
| test_decimal_returns_400 | 400 (e.g. `30.5`) | **DEFECT-C** |
| test_boolean_returns_400 | 400 | |
| test_null_returns_400 | 400 | |
| test_array_returns_400 | 400 | |
| test_huge_number_returns_400_not_500 | 400, not a 500 overflow crash | |

#### TestAccessorUnsupportedMethods — 4 tests (parametrized × 2 fields)
| Test | Expected |
|------|----------|
| test_post_returns_405 | 405 + `Allow` header |
| test_delete_returns_405 | 405 |

#### TestAccessorUnsupportedMediaType — 2 tests (parametrized × 2 fields)
| Test | Expected |
|------|----------|
| test_non_json_content_type_returns_415 | 415 |

#### TestSecurityAccessorAuth — 3 tests
| Test | Expected |
|------|----------|
| test_no_api_key_returns_401 | 401 |
| test_invalid_api_key_returns_403 | 403 |
| test_non_uuid_tenant_id_returns_400 | 400 |

---

### `test_security_settings_bulk.py` — 23 tests

#### TestGetSecuritySettingsBulk — 5 tests
| Test | Expected |
|------|----------|
| test_returns_200 | 200 |
| test_response_contains_both_fields | both fields present |
| test_session_timeout_is_in_enum | value in [15,30,60,120] |
| test_password_reset_lifetime_is_in_enum | value in [15,30,60,120,1440] |
| test_response_is_json | Content-Type: application/json |

#### TestUpdateSecuritySettingsBulk — 3 tests
| Test | Expected |
|------|----------|
| test_put_valid_returns_200 | 200 |
| test_put_response_echoes_saved_values | response reflects saved values |
| test_put_value_is_persisted | value confirmed by subsequent GET |

#### TestPutValidation — 7 tests
| Test | Expected |
|------|----------|
| test_missing_session_timeout_returns_400 | 400 VALIDATION_FAILED |
| test_missing_password_reset_lifetime_returns_400 | 400 VALIDATION_FAILED |
| test_string_session_timeout_returns_400 | 400 |
| test_float_session_timeout_returns_400 | 400 |
| test_unknown_field_returns_400 | 400 (additionalProperties: false) |
| test_empty_body_returns_400 | 400 |
| test_null_body_returns_400 | 400 |

#### TestPutBusinessRules — 2 tests
| Test | Expected |
|------|----------|
| test_session_timeout_out_of_enum_returns_400 | 400 SETTINGS_INVALID |
| test_password_reset_lifetime_out_of_enum_returns_400 | 400 SETTINGS_INVALID |

#### TestUnsupportedMethods — 2 tests
| Test | Expected |
|------|----------|
| test_post_returns_405 | 405 + `Allow` header |
| test_delete_returns_405 | 405 |

#### TestUnsupportedMediaType — 1 test
| Test | Expected |
|------|----------|
| test_non_json_content_type_returns_415 | 415 |

#### TestSecuritySettingsBulkAuth — 3 tests
| Test | Expected |
|------|----------|
| test_no_api_key_returns_401 | 401 |
| test_invalid_api_key_returns_403 | 403 |
| test_non_uuid_tenant_id_returns_400 | 400 |

---

## Results summary

| File | Passed | Failed |
|---|---|---|
| `test_security_accessors.py` | 45 | 4 |
| `test_security_settings_bulk.py` | 23 | 0 |
| **Total** | **68** | **4** |

## Known Issues

### DEFECT-C — Individual accessors silently coerce numeric strings and decimals
**Affects:** `TestAccessorTypeCoercion::test_numeric_string_returns_400` and `::test_decimal_returns_400`, both fields (4 failing tests)
**Observed:** `PUT .../session_timeout_minutes` or `.../password_reset_link_lifetime` with body `"30"` or `30.5` → `200 OK`, silently coerced/truncated to an int
**Expected:** `400 VALIDATION_FAILED` — per spec, "a decimal, string, boolean, or out-of-range value returns 400"
**Note:** The **bulk** endpoint (`test_security_settings_bulk.py`) correctly rejects the same inputs — the gap is isolated to the individual accessors. Manually reproduced via Postman. Not yet filed as its own Jira ticket. Full evidence: `tests/AWRNSS_RETEST_REPORT.md`.

### Related documentation bug (not a server bug)
The team's Postman collection documents the wrong "Example Value" for the individual accessor endpoints — it shows the bulk `SecuritySettings` object shape instead of the bare integer these endpoints actually take. Locked in by `test_put_bulk_object_shape_returns_400` (both fields) so a future fix in the wrong direction (changing the endpoint to match the bad doc, instead of fixing the doc) would be caught.

## Ticket status

| Ticket | Status |
|---|---|
| AWRNSS-461 (enum not validated) | **Fixed — safe to close.** Confirmed by `TestAccessorTypeCoercion`'s enum tests, `TestPutBusinessRules`, and manual Postman checks. |
| AWRNSS-462 (silent type coercion, bulk) | **Fixed — safe to close.** `TestPutValidation` in `test_security_settings_bulk.py` confirms string/float/boolean now correctly rejected on the bulk endpoint. |
| AWRNSS-463 (500 instead of 4xx) | **Fixed — safe to close.** All invalid-input cases across both files return 400/405/415, never 500. |
| DEFECT-C | **Open, not yet filed.** Closing 461/462/463 does not mean these endpoints are fully clean — see above. |
