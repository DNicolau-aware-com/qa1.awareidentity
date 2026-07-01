# API Key Management — Test Suite

**Environment:** qa2 (`https://api.qa2.awareidentity.com`)  
**Last run:** 2026-07-01  
**Result: 142 passed · 8 failed (open bugs)**

---

## Authentication model

All tenant-scoped endpoints (`/v3/tenants/{id}/apiKeys/...`) require two layers:

| Header | Value |
|---|---|
| `Authorization` | `Bearer <Keycloak JWT>` — obtained via password grant from `auth.qa2.awareidentity.com` |
| `X-Aware-ApiKey` | Management API key (stored in `tests/.keycloak_creds` or env) |
| `X-Aware-AccountId` | `0001` |

Internal endpoints (`/v3/apiKeys/...`) have `security: []` — no application auth; Istio mesh-trust only.

Bearer tokens are auto-refreshed at the start of each session via `tests/conftest.py`. Credentials are read from `tests/.keycloak_creds` (gitignored).

---

## Test files

| File | Endpoint(s) | Tests | Pass | Fail |
|---|---|---|---|---|
| `test_auth.py` | All management endpoints — Istio/app auth | 9 | 9 | 0 |
| `test_create.py` | `POST /apiKeys` | 18 | 18 | 0 |
| `test_lifecycle.py` | `GET /{id}`, `PATCH`, `DELETE`, rotate | 16 | 16 | 0 |
| `test_list.py` | `GET /apiKeys` | 11 | 11 | 0 |
| `test_secret.py` | `GET /{id}/secret`, `POST /rotate-credentials` | 10 | 10 | 0 |
| `test_authentication.py` | Key authentication, lastUsedAt, tenant scope | 7 | 7 | 0 |
| `test_validation.py` | `/validate`, `/lookup`, `/lookupAndValidate` | 22 | 22 | 0 |
| `test_edge_cases.py` | All endpoints — edge cases and security | 57 | 49 | 8 |
| **Total** | | **150** | **142** | **8** |

---

## test_auth.py — Gateway and app-layer authentication

### TestGatewayAuth

| Test | Result |
|---|---|
| `test_post_create_no_auth_returns_401` | ✅ Pass |
| `test_get_single_no_auth_returns_401` | ✅ Pass |
| `test_delete_no_auth_returns_401` | ✅ Pass |
| `test_patch_no_auth_returns_401` | ✅ Pass |
| `test_malformed_bearer_returns_4xx` | ✅ Pass |
| `test_malformed_bearer_on_post_returns_4xx` | ✅ Pass |
| `test_api_key_only_no_bearer_returns_401` | ✅ Pass |

### TestAppAuth

| Test | Result |
|---|---|
| `test_bearer_only_no_apikey_returns_403` | ✅ Pass |
| `test_bearer_and_apikey_returns_200` | ✅ Pass |

---

## test_create.py — POST /v3/tenants/{tenantId}/apiKeys

### TestCreateHappyPath

| Test | Result |
|---|---|
| `test_create_returns_200` | ✅ Pass |
| `test_create_response_contains_secret_in_apikey_field` | ✅ Pass |
| `test_new_key_has_active_status` | ✅ Pass |
| `test_new_key_has_key_name` | ✅ Pass |
| `test_new_key_has_prefix_and_suffix` | ✅ Pass |
| `test_new_key_has_tenant_id` | ✅ Pass |
| `test_new_key_has_created_at` | ✅ Pass |
| `test_multiple_active_keys_allowed` | ✅ Pass |

### TestSecretOneTimeDisplay

| Test | Result |
|---|---|
| `test_secret_null_on_get_after_creation` | ✅ Pass |
| `test_secret_null_in_list_after_creation` | ✅ Pass |

### TestCreateValidation

| Test | Result |
|---|---|
| `test_missing_key_name_returns_4xx` | ✅ Pass |
| `test_empty_key_name_returns_4xx` | ✅ Pass |
| `test_whitespace_only_name_returns_4xx` | ✅ Pass |
| `test_missing_description_behavior` | ✅ Pass |
| `test_empty_body_returns_4xx` | ✅ Pass |
| `test_malformed_json_returns_4xx` | ✅ Pass |
| `test_visibility_personal_accepted` | ✅ Pass |
| `test_invalid_visibility_returns_4xx` | ✅ Pass |

---

## test_lifecycle.py — GET /{id} · PATCH · DELETE · Rotation

### TestDelete

| Test | Result |
|---|---|
| `test_delete_returns_204` | ✅ Pass |
| `test_delete_soft_deletes_key_to_inactive` | ✅ Pass |
| `test_delete_nonexistent_key_returns_404` | ✅ Pass |
| `test_double_delete_is_idempotent` | ✅ Pass |

### TestRevoke (PATCH)

| Test | Result |
|---|---|
| `test_revoke_changes_status_to_inactive` | ✅ Pass |
| `test_patch_returns_200` | ✅ Pass |
| `test_patch_nonexistent_key_returns_404` | ✅ Pass |
| `test_patch_invalid_status_value_returns_400` | ✅ Pass |

### TestRotation

| Test | Result |
|---|---|
| `test_two_active_keys_both_accessible` | ✅ Pass |
| `test_deleting_one_key_leaves_other_active` | ✅ Pass |
| `test_can_create_new_key_while_existing_is_active` | ✅ Pass |

### TestGetSingle

| Test | Result |
|---|---|
| `test_get_single_returns_200` | ✅ Pass |
| `test_get_single_secret_is_null` | ✅ Pass |
| `test_get_nonexistent_key_returns_404` | ✅ Pass |
| `test_get_key_from_wrong_tenant_returns_403_or_404` | ✅ Pass |

---

## test_list.py — GET /v3/tenants/{tenantId}/apiKeys

### TestListShape

| Test | Result |
|---|---|
| `test_list_returns_200` | ✅ Pass |
| `test_list_has_pagination_envelope` | ✅ Pass |
| `test_content_is_a_list` | ✅ Pass |
| `test_each_key_has_required_fields` | ✅ Pass |
| `test_secret_null_in_list` | ✅ Pass |
| `test_masked_identifier_uses_prefix_and_suffix` | ✅ Pass |

### TestListContent

| Test | Result |
|---|---|
| `test_newly_created_key_appears_in_list` | ✅ Pass |
| `test_new_key_has_active_status_in_list` | ✅ Pass |
| `test_never_used_key_has_null_last_used` | ✅ Pass |
| `test_total_elements_matches_content_count_on_single_page` | ✅ Pass |

### TestListIsolation

| Test | Result |
|---|---|
| `test_keys_from_other_tenant_not_returned` | ✅ Pass |

---

## test_secret.py — GET /{id}/secret · POST /rotate-credentials

### TestSecretEndpoint

| Test | Result |
|---|---|
| `test_secret_endpoint_returns_200_with_plaintext` | ✅ Pass |
| `test_secret_endpoint_nonexistent_key_returns_404` | ✅ Pass |
| `test_secret_endpoint_requires_auth` | ✅ Pass |
| `test_secret_matches_original_api_key` | ✅ Pass |

### TestRotateCredentials

| Test | Result |
|---|---|
| `test_rotate_returns_200_with_new_secret` | ✅ Pass |
| `test_rotate_keeps_same_key_id` | ✅ Pass |
| `test_rotate_changes_prefix_and_suffix` | ✅ Pass |
| `test_rotate_new_secret_different_from_original` | ✅ Pass |
| `test_rotate_nonexistent_key_returns_404` | ✅ Pass |
| `test_rotate_requires_auth` | ✅ Pass |

---

## test_authentication.py — Key authentication · lastUsedAt · tenant scope

### TestActiveKeyAuthentication

| Test | Result |
|---|---|
| `test_newly_issued_key_authenticates_collections_endpoint` | ✅ Pass |
| `test_inactive_key_is_rejected` | ✅ Pass |
| `test_unknown_key_is_rejected` | ✅ Pass |
| `test_inactive_and_unknown_key_return_same_status` | ✅ Pass |

### TestLastUsedTracking

| Test | Result |
|---|---|
| `test_last_used_updated_after_successful_auth` | ✅ Pass |
| `test_fresh_key_has_null_last_used` | ✅ Pass |

### TestTenantScope

| Test | Result |
|---|---|
| `test_key_cannot_access_different_tenant` | ✅ Pass |

---

## test_validation.py — Internal mesh endpoints

> These endpoints have `security: []` in the spec — unauthenticated by design, Istio mesh-trust only.

### TestValidate — GET /v3/apiKeys/validate

| Test | Result |
|---|---|
| `test_valid_active_key_returns_200` | ✅ Pass |
| `test_valid_key_returns_no_body` | ✅ Pass |
| `test_inactive_key_returns_401` | ✅ Pass |
| `test_unknown_key_returns_401` | ✅ Pass |
| `test_missing_api_key_header_returns_401` | ✅ Pass |
| `test_account_id_not_required` | ✅ Pass |
| `test_no_auth_returns_401` | ✅ Pass |
| `test_401_response_has_no_body` | ✅ Pass |

### TestLookup — GET /v3/apiKeys/{rawApiKey}/lookup

| Test | Result |
|---|---|
| `test_lookup_is_unauthenticated_by_design` | ✅ Pass |
| `test_lookup_with_valid_auth_returns_200` | ✅ Pass |
| `test_lookup_does_not_expose_secret` | ✅ Pass |
| `test_lookup_inactive_key_returns_401` | ✅ Pass |
| `test_lookup_unknown_key_returns_401_or_404` | ✅ Pass |
| `test_lookup_bearer_only_returns_403` | ✅ Pass |

### TestLookupAndValidate — GET /v3/apiKeys/{rawApiKey}/lookupAndValidate

| Test | Result |
|---|---|
| `test_valid_active_key_with_mgmt_headers_returns_200` | ✅ Pass |
| `test_response_does_not_expose_secret` | ✅ Pass |
| `test_inactive_key_returns_401` | ✅ Pass |
| `test_no_auth_returns_401` | ✅ Pass |
| `test_bearer_only_returns_403` | ✅ Pass |
| `test_unknown_key_returns_401_or_404` | ✅ Pass |

### TestCrossEndpointConsistency

| Test | Result |
|---|---|
| `test_internal_endpoints_all_reject_unknown_key` | ✅ Pass |
| `test_all_endpoints_reject_inactive_key_consistently` | ✅ Pass |

---

## test_edge_cases.py — Edge cases and security

### 1 · TestInactiveKeyAuthentication

| Test | Result |
|---|---|
| `test_inactive_key_cannot_authenticate` | ✅ Pass |

### 2 · TestCrossTenantKeyUsage

| Test | Result |
|---|---|
| `test_tenant_a_key_cannot_access_tenant_b` | ✅ Pass |

### 3 · TestSecretOnInactiveKey

| Test | Result |
|---|---|
| `test_secret_not_retrievable_after_soft_delete` | ✅ Pass |

### 4 · TestExpiresAt

| Test | Result |
|---|---|
| `test_expires_at_can_be_set_at_creation` | ✅ Pass |
| `test_expired_key_cannot_authenticate` | ✅ Pass |

### 5 · TestLongKeyName

| Test | Result |
|---|---|
| `test_very_long_key_name_returns_4xx` | ✅ Pass |
| `test_boundary_key_name_255_chars` | ✅ Pass |

### 6 · TestInjectionInKeyName

| Test | Result |
|---|---|
| `test_injection_payload_stored_safely[sql_injection]` | ✅ Pass |
| `test_injection_payload_stored_safely[xss_html]` | ✅ Pass |
| `test_injection_payload_stored_safely[ssti_template]` | ✅ Pass |
| `test_injection_payload_stored_safely[path_traversal]` | ✅ Pass |
| `test_injection_payload_stored_safely[null_byte]` | ✅ Pass |

### 7 · TestRotateOnInactiveKey

| Test | Result |
|---|---|
| `test_rotate_on_inactive_key_returns_4xx` | ✅ Pass |

### 8 · TestPatchOnInactiveKey

| Test | Result |
|---|---|
| `test_patch_on_inactive_key_returns_4xx` | ✅ Pass |

### 9 · TestInvalidPagination

| Test | Result | Note |
|---|---|---|
| `test_negative_page_returns_4xx_or_200` | ✅ Pass | |
| `test_zero_size_returns_4xx_or_200` | ✅ Pass | |
| `test_huge_size_returns_4xx_or_200` | ✅ Pass | |
| `test_non_numeric_page_returns_4xx` | ❌ Fail | **BUG** AWRNSS-483 — `page=abc` silently coerced to 0 |

### 10 · TestStatusTransitions

| Test | Result | Note |
|---|---|---|
| `test_patch_status_suspended` | ✅ Pass | SUSPENDED accepted; key correctly blocked from auth |
| `test_patch_provisioning_status_rejected[PENDING]` | ❌ Fail | **BUG** — PATCH to PENDING returns 200 |
| `test_patch_provisioning_status_rejected[FAILED]` | ❌ Fail | **BUG** — PATCH to FAILED returns 200 |

### 11 · TestClearExpiresAt

| Test | Result |
|---|---|
| `test_clear_expires_at_removes_expiry` | ✅ Pass |
| `test_clear_expires_at_on_key_without_expiry` | ✅ Pass |

### 12 · TestLongDescription

| Test | Result |
|---|---|
| `test_description_at_1024_chars_accepted` | ✅ Pass |
| `test_description_over_1024_chars_rejected` | ✅ Pass |

### 13 · TestUnknownFields

| Test | Result | Note |
|---|---|---|
| `test_unknown_field_in_create_returns_400` | ❌ Fail | **BUG** — unknown field silently accepted on POST |
| `test_unknown_field_in_patch_returns_400` | ✅ Pass | |
| `test_apikey_field_in_patch_returns_400` | ✅ Pass | |

### 14 · TestPersonalVisibility

| Test | Result | Note |
|---|---|---|
| `test_personal_key_not_visible_in_list_without_user_id` | ❌ Fail | **BUG** — PERSONAL keys visible without X-User-Id |
| `test_personal_key_visible_with_matching_user_id` | ✅ Pass | |
| `test_personal_key_not_visible_with_different_user_id` | ✅ Pass | |

### 15 · TestSortParam

| Test | Result | Note |
|---|---|---|
| `test_valid_sort_returns_200[createdAt,desc]` | ✅ Pass | |
| `test_valid_sort_returns_200[createdAt,asc]` | ✅ Pass | |
| `test_sort_by_key_name_returns_200` | ❌ Fail | **BUG** — `sort=keyName,asc` crashes with 500 |
| `test_unknown_sort_field_does_not_crash` | ❌ Fail | **BUG** — unknown sort crashes with 500 |
| `test_malformed_sort_does_not_crash` | ❌ Fail | **BUG** — malformed sort crashes with 500 |

### 16 · TestExpiresAtFormats

| Test | Result |
|---|---|
| `test_expires_at_with_timezone_offset_rejected_or_accepted` | ✅ Pass |
| `test_expires_at_invalid_format_returns_400` | ✅ Pass |
| `test_expires_at_far_future_accepted` | ✅ Pass |

### 17 · TestPatchExpiresAtInPast

| Test | Result |
|---|---|
| `test_patch_expires_at_to_past_makes_key_immediately_expired` | ✅ Pass |

### 18 · TestPatchBodyEdgeCases

| Test | Result |
|---|---|
| `test_patch_empty_body_returns_400` | ✅ Pass |
| `test_patch_clear_expires_at_false_does_not_clear_expiry` | ✅ Pass |
| `test_patch_expires_at_and_clear_expires_at_true_together` | ✅ Pass |

### 19 · TestRotationSecurity

| Test | Result |
|---|---|
| `test_old_secret_rejected_after_rotation` | ✅ Pass |

### 20 · TestAdditionalInputValidation

| Test | Result |
|---|---|
| `test_invalid_visibility_value_returns_400` | ✅ Pass |
| `test_keyname_whitespace_handling[whitespace_padded]` | ✅ Pass |
| `test_keyname_whitespace_handling[whitespace_only_single]` | ✅ Pass |
| `test_injection_in_description_stored_safely[sql_injection]` | ✅ Pass |
| `test_injection_in_description_stored_safely[xss_html]` | ✅ Pass |
| `test_injection_in_description_stored_safely[ssti_template]` | ✅ Pass |
| `test_malformed_api_key_header_short` | ✅ Pass |
| `test_malformed_api_key_header_very_long` | ✅ Pass |

### 21 · TestListPaginationEdgeCases

| Test | Result |
|---|---|
| `test_page_beyond_total_returns_empty_list` | ✅ Pass |
| `test_size_one_returns_single_result` | ✅ Pass |
| `test_multiple_sort_params_do_not_crash` | ✅ Pass |

### 22 · TestSecurityMisc

| Test | Result |
|---|---|
| `test_api_key_in_query_param_not_accepted` | ✅ Pass |
| `test_cross_tenant_patch_returns_403_or_404` | ✅ Pass |

---

## Open bugs (8 failing tests)

| Ticket | Test | Description | Severity |
|---|---|---|---|
| AWRNSS-483 | `test_non_numeric_page_returns_4xx` | `page=abc` silently coerced to 0 instead of 400 | Medium |
| Unfiled | `test_patch_provisioning_status_rejected[PENDING]` | PATCH to `PENDING` accepted with 200 | High |
| Unfiled | `test_patch_provisioning_status_rejected[FAILED]` | PATCH to `FAILED` accepted with 200 | High |
| Unfiled | `test_unknown_field_in_create_returns_400` | Unknown fields silently ignored on POST (spec: `additionalProperties: false`) | Medium |
| Unfiled | `test_personal_key_not_visible_in_list_without_user_id` | PERSONAL keys visible in list without `X-User-Id` header | High |
| Unfiled | `test_sort_by_key_name_returns_200` | `sort=keyName,asc` crashes server with 500 | Critical |
| Unfiled | `test_unknown_sort_field_does_not_crash` | Unknown sort field crashes server with 500 | High |
| Unfiled | `test_malformed_sort_does_not_crash` | Malformed sort value crashes server with 500 | High |

---

## Running the suite

```bash
# Full suite
python -m pytest tests/api_keys/ -v

# Single file
python -m pytest tests/api_keys/test_edge_cases.py -v

# Only open bugs (expected failures)
python -m pytest tests/api_keys/ -v -k "non_numeric_page or provisioning_status or unknown_field_in_create or personal_key_not_visible or sort"

# Skip known failures
python -m pytest tests/api_keys/ -v --ignore=tests/api_keys/test_edge_cases.py
```

Credentials are read automatically from `tests/.keycloak_creds`. Bearer tokens are refreshed at session start — no manual token paste required.
