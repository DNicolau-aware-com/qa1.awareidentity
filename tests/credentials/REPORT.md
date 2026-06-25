# Biometric Credentials API — Test Suite Report

**Environment:** `https://api.qa2.awareidentity.com`  
**Tenant:** `b3b8c292-2305-4e06-85c6-71fbb0519255`  
**Total tests:** 229  
**Known bugs (tests expected to fail):** 16

---

## Test Suite Breakdown

### `test_auth.py` — 26 tests

#### TestCredentialsAuth
| Test | Expected | Known Issue |
|------|----------|-------------|
| test_invalid_api_key_on_post_returns_401 | 401 UNAUTHORIZED | BUG-1 |
| test_invalid_api_key_on_get_by_id_returns_401 | 401 UNAUTHORIZED | BUG-1 |
| test_invalid_api_key_on_get_list_returns_401 | 401 UNAUTHORIZED | BUG-1 |
| test_invalid_api_key_on_get_by_external_user_id_returns_401 | 401 UNAUTHORIZED | BUG-1 |
| test_invalid_api_key_on_patch_by_id_returns_401 | 401 UNAUTHORIZED | BUG-1 |
| test_invalid_api_key_on_patch_by_external_user_id_returns_401 | 401 UNAUTHORIZED | BUG-1 |
| test_invalid_api_key_on_delete_by_id_returns_401 | 401 UNAUTHORIZED | BUG-1 |
| test_invalid_api_key_on_delete_by_external_user_id_returns_401 | 401 UNAUTHORIZED | BUG-1 |
| test_missing_api_key_on_get_list_returns_401 | 401 UNAUTHORIZED | BUG-2 |
| test_missing_api_key_on_post_returns_401 | 401 UNAUTHORIZED | BUG-2 |
| test_missing_account_id_on_post_returns_401 | 401 UNAUTHORIZED | BUG-2 |
| test_missing_account_id_on_get_list_returns_401 | 401 UNAUTHORIZED | BUG-2 |
| test_missing_account_id_on_get_by_id_returns_401 | 401 UNAUTHORIZED | BUG-2 |
| test_missing_account_id_on_patch_returns_401 | 401 UNAUTHORIZED | BUG-2 |
| test_missing_account_id_on_delete_returns_401 | 401 UNAUTHORIZED | BUG-2 |

#### TestCredentialsForbidden
| Test | Expected |
|------|----------|
| test_account_mismatch_on_post_returns_403 | 403 FORBIDDEN |
| test_account_mismatch_on_get_list_returns_403 | 403 FORBIDDEN |
| test_account_mismatch_on_get_by_id_returns_403 | 403 FORBIDDEN |
| test_account_mismatch_on_get_by_user_id_returns_403 | 403 FORBIDDEN |
| test_account_mismatch_on_patch_by_id_returns_403 | 403 FORBIDDEN |
| test_account_mismatch_on_patch_by_user_id_returns_403 | 403 FORBIDDEN |
| test_account_mismatch_on_delete_by_id_returns_403 | 403 FORBIDDEN |
| test_account_mismatch_on_delete_by_user_id_returns_403 | 403 FORBIDDEN |

#### TestCredentialsWwwAuthenticate
| Test | Expected |
|------|----------|
| test_invalid_api_key_returns_www_authenticate_header | WWW-Authenticate header present |
| test_missing_api_key_returns_www_authenticate_header | WWW-Authenticate header present |
| test_missing_account_id_returns_www_authenticate_header | WWW-Authenticate header present |

---

### `test_create.py` — 48 tests

#### TestCreateHappyPath
| Test | Expected |
|------|----------|
| test_returns_201 | 201 Created |
| test_response_wrapped_in_envelope | `biometricCredential` key present |
| test_response_contains_required_fields | id, collectionId, externalUserId, status, biometrics, createdBy, createdAt, updatedAt |
| test_id_is_uuid | id is valid UUID |
| test_collection_id_matches_path | collectionId matches URL |
| test_external_user_id_is_stored | externalUserId echoed |
| test_status_is_active_on_creation | status == "ACTIVE" |
| test_biometrics_is_dict | biometrics is object |
| test_data_not_echoed_in_response | `data` absent from entry objects |
| test_timestamps_are_integer_milliseconds | createdAt, updatedAt > 0 integers |
| test_response_content_type_is_json | Content-Type: application/json |
| test_created_by_is_optional | POST without createdBy → 201 |

#### TestCreateCorrelationId
| Test | Expected |
|------|----------|
| test_correlation_id_is_echoed | correlationId in response matches request |
| test_correlation_id_omitted_when_not_supplied | `correlationId` key absent |
| test_correlation_id_null_omitted_from_response | `correlationId` key absent when null |

#### TestCreateCreatedByValidation
| Test | Expected | Known Issue |
|------|----------|-------------|
| test_plain_name_accepted | 201 | |
| test_xss_in_created_by_returns_400 | 400 | |
| test_symbols_in_created_by_returns_400 | 400 | |
| test_blank_created_by_returns_400 | 400 | BUG-3 |
| test_whitespace_created_by_returns_400 | 400 | BUG-3 |
| test_newline_in_created_by_returns_400 | 400 | BUG-3 |
| test_tab_in_created_by_returns_400 | 400 | BUG-3 |

#### TestCreateConflict
| Test | Expected |
|------|----------|
| test_duplicate_external_user_id_returns_409 | 409 CONFLICT |

#### TestCreateValidation
| Test | Expected | Known Issue |
|------|----------|-------------|
| test_missing_envelope_returns_400 | 400 | |
| test_empty_body_returns_400 | 400 | |
| test_missing_external_user_id_returns_400 | 400 VALIDATION_FAILED | |
| test_empty_external_user_id_returns_400 | 400 | |
| test_missing_biometrics_returns_400 | 400 | |
| test_empty_biometrics_map_returns_400 | 400 | BUG-4 |
| test_empty_modality_array_returns_400 | 400 | BUG-5 |
| test_missing_data_in_biometrics_entry_returns_400 | 400 VALIDATION_FAILED | |
| test_validation_error_includes_field_errors | 400 + `fieldErrors` body | |

#### TestCreateExternalUserId
| Test | Expected |
|------|----------|
| test_special_chars_in_external_user_id_accepted | 201 |
| test_long_external_user_id_accepted | 201, externalUserId stored verbatim |

#### TestCreateNotFound
| Test | Expected |
|------|----------|
| test_nonexistent_collection_returns_404 | 404 NOT_FOUND |
| test_nonexistent_tenant_returns_403_or_404 | 403 or 404 |

#### TestCreateServerManagedFields
| Test | Expected |
|------|----------|
| test_client_id_is_ignored | Server-generated UUID returned |
| test_client_created_at_is_ignored | Server timestamp returned |
| test_client_updated_by_is_ignored_on_create | updatedBy not set by client on create |

#### TestCreateMalformedBody
| Test | Expected |
|------|----------|
| test_envelope_as_array_returns_400 | 400 |
| test_malformed_json_returns_400 | 400 |
| test_wrong_content_type_returns_415 | 415 |
| test_empty_body_returns_400 | 400 |

#### TestCreateModalityEntryLimit
| Test | Expected |
|------|----------|
| test_six_face_entries_returns_400 | 400 MODALITY_ENTRY_LIMIT_EXCEEDED |
| test_five_face_entries_is_accepted | 201 |

#### TestErrorResponseShape
| Test | Expected |
|------|----------|
| test_error_response_includes_timestamp | `timestamp` key present in error body |
| test_error_timestamp_is_iso8601 | timestamp parses as ISO-8601 |

#### TestCreateCreatedByDefault
| Test | Expected |
|------|----------|
| test_created_by_defaults_to_system_when_omitted | createdBy == "system" |

---

### `test_get.py` — 27 tests

#### TestGetByIdHappyPath
| Test | Expected |
|------|----------|
| test_returns_200 | 200 |
| test_response_wrapped_in_envelope | `biometricCredential` key present |
| test_response_contains_required_fields | id, collectionId, externalUserId, status, biometrics, createdBy, createdAt, updatedAt |
| test_returned_id_matches_requested_id | id matches URL param |
| test_collection_id_matches_path | collectionId matches URL |
| test_timestamps_are_integer_milliseconds | createdAt, updatedAt > 0 integers |
| test_response_content_type_is_json | Content-Type: application/json |
| test_biometrics_is_dict | biometrics is object |
| test_entries_in_get_by_id_do_not_contain_raw_data | `data` absent |
| test_image_data_populated_in_get_by_id_entries | `imageData` present and non-empty in entries |

#### TestGetByIdShape
| Test | Expected |
|------|----------|
| test_status_enum_valid_on_get_by_id | status in ["ACTIVE", "INACTIVE"] |
| test_updated_by_omitted_when_null_on_get_by_id | `updatedBy` key absent |
| test_correlation_id_omitted_when_null_on_get_by_id | `correlationId` key absent |

#### TestGetByIdDataIntegrity
| Test | Expected |
|------|----------|
| test_external_user_id_matches_create_payload | externalUserId round-trips |
| test_created_by_matches_create_payload | createdBy round-trips |

#### TestGetByIdNotFound
| Test | Expected | Known Issue |
|------|----------|-------------|
| test_nonexistent_id_returns_404 | 404 NOT_FOUND | |
| test_nonexistent_collection_returns_404 | 404 | |
| test_credential_in_wrong_collection_returns_404 | 404 | |
| test_non_uuid_id_returns_400 | 400 VALIDATION_FAILED | BUG-6 |
| test_deleted_credential_returns_404 | 404 NOT_FOUND | |

#### TestGetByUserId
| Test | Expected |
|------|----------|
| test_returns_200_for_existing_user | 200 |
| test_response_contains_page_envelope_fields | biometricCredentials, page, size, totalElements |
| test_response_contains_matching_credential | credential id in list |
| test_unknown_user_id_returns_404 | 404 NOT_FOUND |
| test_credentials_filtered_by_user_id | only matching user returned |
| test_image_data_populated_in_entries | `imageData` present and non-empty |
| test_deleted_credential_returns_404_by_user_id | 404 |

---

### `test_list.py` — 32 tests

#### TestListHappyPath
| Test | Expected |
|------|----------|
| test_returns_200 | 200 |
| test_response_shape | biometricCredentials, page, size, totalElements, totalPages |
| test_default_pagination | page=0, size=25 |
| test_response_content_type_is_json | Content-Type: application/json |
| test_created_credential_appears_in_list | new credential id in list |
| test_image_data_not_in_list_items | `imageData` absent in entry objects |

#### TestListPagination
| Test | Expected | Known Issue |
|------|----------|-------------|
| test_size_param_limits_results | ≤ requested size returned | |
| test_size_over_100_is_capped | size capped at 100 | |
| test_size_zero_returns_400 | 400 | BUG-7 |
| test_negative_page_returns_400 | 400 | BUG-7 |
| test_page_param_is_zero_based | page=0 is first page | |
| test_page_beyond_last_returns_empty | 200, empty list | |
| test_total_pages_matches_total_elements | totalPages = ceil(total/size) | |
| test_size_in_response_matches_request | size echoed back | |

#### TestListFilters
| Test | Expected |
|------|----------|
| test_status_active_filter | only ACTIVE credentials |
| test_modality_filter_contract | only credentials with `face` modality |
| test_soft_deleted_excluded_from_list | deleted id absent |
| test_status_inactive_filter | only INACTIVE credentials |
| test_unknown_collection_returns_404 | 404 |
| test_soft_deleted_collection_returns_404 | 404 |
| test_user_id_filter_ignores_other_params | userId takes priority |
| test_no_duplicate_ids_across_pages | no id on two pages |

#### TestListUserIdFilter
| Test | Expected |
|------|----------|
| test_user_id_filter_returns_only_matching_credential | only matching credential |
| test_user_id_filter_returns_paginated_envelope | page envelope returned |
| test_user_id_filter_includes_image_data | `imageData` populated |
| test_user_id_filter_is_exact_match | partial match returns empty |
| test_user_id_filter_nonexistent_returns_empty_list | 200, empty list |

#### TestListItemShape
| Test | Expected |
|------|----------|
| test_required_fields_present_on_list_items | id, collectionId, externalUserId, status, biometrics, createdBy, createdAt, updatedAt |
| test_status_enum_valid_on_list_items | status in ["ACTIVE", "INACTIVE"] |
| test_timestamps_are_integer_epoch_ms_on_list_items | createdAt, updatedAt > 0 integers |
| test_updated_by_omitted_when_null | `updatedBy` key absent |
| test_correlation_id_omitted_when_null | `correlationId` key absent |

---

### `test_update.py` — 44 tests

#### TestUpdateByIdHappyPath
| Test | Expected |
|------|----------|
| test_returns_200 | 200 |
| test_response_wrapped_in_envelope | `biometricCredential` key present |
| test_updated_by_is_set | updatedBy echoed in response |
| test_updated_at_advances | updatedAt >= createdAt |
| test_created_by_unchanged_after_patch | createdBy not modified |
| test_created_at_unchanged_after_patch | createdAt not modified |
| test_patch_persists_via_get | change visible on subsequent GET |
| test_data_not_echoed_in_patch_response | `data` absent |
| test_image_data_not_in_patch_response | `imageData` absent |
| test_correlation_id_updated | correlationId replaced and echoed |
| test_updated_by_absent_on_new_credential | `updatedBy` key absent on fresh credential |

#### TestUpdateByIdImmutableFields
| Test | Expected |
|------|----------|
| test_id_cannot_be_changed_via_patch | id unchanged |
| test_created_by_cannot_be_changed_via_patch | createdBy unchanged |
| test_created_at_cannot_be_changed_via_patch | createdAt unchanged |
| test_status_cannot_be_changed_via_patch | status unchanged |
| test_external_user_id_cannot_be_changed_via_patch | externalUserId unchanged |

#### TestUpdateByIdNotFound
| Test | Expected |
|------|----------|
| test_nonexistent_id_returns_404 | 404 NOT_FOUND |
| test_deleted_credential_patch_returns_404 | 404 NOT_FOUND |

#### TestUpdateByIdValidation
| Test | Expected | Known Issue |
|------|----------|-------------|
| test_missing_envelope_returns_400 | 400 | |
| test_non_uuid_id_returns_400 | 400 VALIDATION_FAILED | BUG-6 |
| test_empty_biometrics_map_returns_400 | 400 | BUG-8 |
| test_invalid_base64_in_entry_data_returns_400 | 400 VALIDATION_FAILED | |
| test_modality_entry_limit_exceeded_returns_400 | 400 MODALITY_ENTRY_LIMIT_EXCEEDED | |
| test_modality_entry_limit_enforced_cumulatively_on_patch_by_id | 400 at 3+3, 200 at 3+2 | |
| test_empty_modality_array_returns_400 | 400 | BUG-5 |
| test_missing_data_in_biometrics_entry_returns_400 | 400 VALIDATION_FAILED | |
| test_credential_in_wrong_collection_returns_404 | 404 | |

#### TestUpdateByIdUpdatedByValidation
| Test | Expected | Known Issue |
|------|----------|-------------|
| test_plain_name_accepted | 200 | |
| test_xss_in_updated_by_returns_400 | 400 | |
| test_symbols_in_updated_by_returns_400 | 400 | |
| test_blank_updated_by_returns_400 | 400 | BUG-3 |
| test_whitespace_updated_by_returns_400 | 400 | BUG-3 |
| test_newline_in_updated_by_returns_400 | 400 | BUG-3 |

#### TestUpdateByIdShape
| Test | Expected |
|------|----------|
| test_required_fields_present_in_patch_response | id, collectionId, externalUserId, status, biometrics, createdBy, createdAt, updatedAt |
| test_status_enum_valid_in_patch_response | status in ["ACTIVE", "INACTIVE"] |
| test_updated_by_omitted_when_null_in_patch_response | `updatedBy` key absent |
| test_correlation_id_omitted_when_null_in_patch_response | `correlationId` key absent |

#### TestUpdateByUserIdUpsert
| Test | Expected | Known Issue |
|------|----------|-------------|
| test_existing_user_returns_200 | 200 | |
| test_new_user_creates_credential_returns_201 | 201 | BUG-9 |
| test_update_persists_via_get_by_user_id | change visible on GET ?userId= | |

#### TestUpdateByUserIdValidation
| Test | Expected | Known Issue |
|------|----------|-------------|
| test_empty_user_id_returns_400 | 400 VALIDATION_FAILED | BUG-10 |
| test_missing_user_id_param_returns_400 | 400 | BUG-11 |
| test_soft_deleted_user_id_returns_409 | 409 CONFLICT | |
| test_modality_entry_limit_enforced_cumulatively_on_patch_by_user_id | 400 MODALITY_ENTRY_LIMIT_EXCEEDED | |

---

### `test_delete.py` — 15 tests

#### TestDeleteByIdHappyPath
| Test | Expected |
|------|----------|
| test_returns_204 | 204 No Content |
| test_response_has_no_body | empty body |

#### TestDeleteByIdSoftDelete
| Test | Expected |
|------|----------|
| test_deleted_credential_get_returns_404 | 404 NOT_FOUND |
| test_deleted_credential_excluded_from_user_id_search | 404 NOT_FOUND |
| test_deleted_credential_patch_returns_404 | 404 NOT_FOUND |

#### TestDeleteByIdNotFound
| Test | Expected | Known Issue |
|------|----------|-------------|
| test_nonexistent_id_returns_404 | 404 NOT_FOUND | |
| test_already_deleted_returns_404 | 404 NOT_FOUND | |
| test_non_uuid_id_returns_400 | 400 VALIDATION_FAILED | BUG-6 |

#### TestDeleteByUserIdHappyPath
| Test | Expected |
|------|----------|
| test_returns_204 | 204 No Content |
| test_delete_by_user_id_removes_credential | subsequent GET ?userId= returns 404 |
| test_delete_by_user_id_does_not_affect_other_users | other user still accessible |

#### TestDeleteByUserIdNotFound
| Test | Expected |
|------|----------|
| test_unknown_user_id_returns_404 | 404 NOT_FOUND |

#### TestDeleteByIdWrongCollection
| Test | Expected |
|------|----------|
| test_credential_in_wrong_collection_returns_404 | 404 NOT_FOUND |

#### TestDeleteByUserIdValidation
| Test | Expected | Known Issue |
|------|----------|-------------|
| test_empty_user_id_returns_404 | 404 NOT_FOUND | |
| test_missing_user_id_param_does_not_crash | < 500 | BUG-12 |

---

### `test_credential_entries.py` — 31 tests

#### TestGetEntryNotFound
| Test | Expected | Known Issue |
|------|----------|-------------|
| test_entry_on_nonexistent_credential_returns_404 | 404 NOT_FOUND | |
| test_random_entry_id_on_real_credential_returns_404 | 404 NOT_FOUND | |
| test_non_uuid_entry_id_does_not_crash | < 500 | BUG-13 |
| test_nonexistent_entry_returns_404 | 404 NOT_FOUND | |

#### TestEntryPathOwnership
| Test | Expected |
|------|----------|
| test_get_entry_wrong_credential_returns_404 | 404 NOT_FOUND |
| test_patch_entry_wrong_credential_returns_404 | 404 NOT_FOUND |
| test_delete_entry_wrong_credential_returns_404_and_entry_survives | 404 + entry still accessible |

#### TestPatchEntryValidation
| Test | Expected | Known Issue |
|------|----------|-------------|
| test_missing_envelope_returns_400 | 400 | |
| test_random_entry_id_on_real_credential_returns_404 | 404 NOT_FOUND | |
| test_non_uuid_entry_id_does_not_crash | < 500 | BUG-13 |

#### TestGetEntryHappyPath
| Test | Expected |
|------|----------|
| test_returns_200 | 200 |
| test_response_content_type_is_json | Content-Type: application/json |
| test_response_contains_id | id == requested entryId |
| test_image_data_included_in_get_entry | `imageData` present |
| test_entry_timestamps_are_integer_epoch_ms | createdAt, updatedAt > 0 integers |
| test_labels_omitted_when_entry_has_no_labels | `labels` key absent |

#### TestPatchEntry
| Test | Expected |
|------|----------|
| test_patch_labels_returns_200 | 200 |
| test_patch_labels_persists | labels reflected in subsequent GET |
| test_patch_image_returns_new_entry_id | response id ≠ old entryId |
| test_patch_response_does_not_include_image_data | `imageData` absent |
| test_data_not_echoed_in_entry_patch_response | `data` absent |
| test_patch_nonexistent_entry_returns_404 | 404 NOT_FOUND |
| test_labels_only_retains_same_entry_id | response id == original entryId |
| test_data_and_labels_together_returns_new_id | new id returned, labels set |

#### TestDeleteEntry
| Test | Expected |
|------|----------|
| test_returns_204 | 204 No Content |
| test_deleted_entry_get_returns_404 | 404 NOT_FOUND |
| test_delete_entry_does_not_delete_credential | parent credential still 200 |
| test_delete_nonexistent_entry_returns_404 | 404 NOT_FOUND |

#### TestPatchEntryUpdatedBy
| Test | Expected |
|------|----------|
| test_updated_by_accepted_on_entry_patch | 200 |
| test_invalid_updated_by_in_entry_patch_returns_400 | 400 |

#### TestModalityEntryLimit
| Test | Expected |
|------|----------|
| test_sixth_entry_exceeds_limit | 400 MODALITY_ENTRY_LIMIT_EXCEEDED |

---

### `test_path_params.py` — 6 tests

#### TestNonUuidTenantId
| Test | Expected |
|------|----------|
| test_non_uuid_tenant_get_list_returns_400 | 400 |
| test_oversized_tenant_get_list_returns_400 | 400 |
| test_non_uuid_tenant_get_by_id_returns_400 | 400 |

#### TestNonUuidCollectionId
| Test | Expected |
|------|----------|
| test_non_uuid_collection_get_list_returns_400 | 400 |
| test_oversized_collection_get_list_returns_400 | 400 |
| test_non_uuid_collection_get_by_id_returns_400 | 400 |

---

## Known Issues

### BUG-1 — Invalid API key returns 403 instead of 401
**Affects:** All 8 `test_invalid_api_key_on_*_returns_401` tests  
**Observed:** Server returns `403 FORBIDDEN`  
**Expected:** `401 UNAUTHORIZED` with `WWW-Authenticate` header  
**Root cause:** Auth filter classifies invalid API key as a resource access denial rather than an authentication failure.

---

### BUG-2 — Missing auth headers return 500 instead of 401
**Affects:** 7 `test_missing_api_key_*` and `test_missing_account_id_*` tests  
**Observed:** Server returns `500` (`MissingRequestHeaderException` unhandled)  
**Expected:** `401 UNAUTHORIZED`  
**Root cause:** Spring exception handler for `MissingRequestHeaderException` is not mapped.

---

### BUG-3 — Blank / control-character `createdBy` / `updatedBy` not validated
**Affects:** 7 tests — `test_blank_created_by_returns_400`, `test_whitespace_created_by_returns_400`, `test_newline_in_created_by_returns_400`, `test_tab_in_created_by_returns_400`, `test_blank_updated_by_returns_400`, `test_whitespace_updated_by_returns_400`, `test_newline_in_updated_by_returns_400`  
**Observed:** Server accepts these values and returns 201/200  
**Expected:** `400 VALIDATION_FAILED` — `PATTERN_NAME_OR_EMAIL` regex must reject blank and control-character strings  
**Root cause:** Regex pattern only rejects disallowed symbols; does not enforce non-blank / no-control-chars.

---

### BUG-4 — Empty `biometrics` map `{}` accepted on POST and PATCH
**Affects:** `test_empty_biometrics_map_returns_400` (test_create.py and test_update.py)  
**Observed:** POST returns 201; PATCH returns 200 and advances `updatedAt` with no data change  
**Expected:** `400 VALIDATION_FAILED` — spec requires at least one modality key with at least one entry  
**Root cause:** `biometrics` map emptiness is not validated before persistence.

---

### BUG-5 — Empty modality array `{"face": []}` may be silently accepted
**Affects:** `test_empty_modality_array_returns_400` (test_create.py and test_update.py)  
**Observed:** Server may return 201/200  
**Expected:** `400 VALIDATION_FAILED` — spec declares `minItems: 1` per modality array  
**Root cause:** Same as BUG-4; per-modality array length not validated.

---

### BUG-6 — Non-UUID path variables return 500 instead of 400
**Affects:** `test_non_uuid_id_returns_400` in test_get.py, test_update.py, and test_delete.py  
**Observed:** Server returns `500`  
**Expected:** `400 VALIDATION_FAILED`  
**Root cause:** `MethodArgumentTypeMismatchException` for UUID path parameters is not mapped to a 400 error handler in Spring.

---

### BUG-7 — Invalid pagination parameters return 500 instead of 400
**Affects:** `test_size_zero_returns_400`, `test_negative_page_returns_400` (test_list.py)  
**Observed:** `500` with Spring internal exception message  
**Expected:** `400 VALIDATION_FAILED`  
**Root cause:** Spring's `ConstraintViolationException` / `IllegalArgumentException` for page/size parameters is not mapped to a 400 handler.

---

### BUG-8 — PATCH with `biometrics: {}` returns 200 and silently no-ops
**Affects:** `test_empty_biometrics_map_returns_400` (test_update.py)  
**Observed:** 200, `updatedAt` advances, no entries added  
**Expected:** `400 VALIDATION_FAILED`  
**Note:** Same root cause as BUG-4; listed separately because the behaviour on PATCH (silent no-op) is distinct from POST (creates an empty credential).

---

### BUG-9 — PATCH `?userId=` upsert always returns 200, never 201 on first create
**Affects:** `test_new_user_creates_credential_returns_201` (test_update.py)  
**Observed:** 200 for both create and update paths  
**Expected:** 201 on first call (credential created), 200 on subsequent calls (credential updated)  
**Root cause:** Upsert implementation does not differentiate insert vs update in the HTTP response code.

---

### BUG-10 — PATCH `?userId=` with empty string creates a blank-userId credential
**Affects:** `test_empty_user_id_returns_400` (test_update.py)  
**Observed:** 200, credential created with `externalUserId: ""`  
**Expected:** `400 VALIDATION_FAILED`  
**Impact:** The blank-userId slot is permanently occupied even after soft-delete; cannot be reclaimed.

---

### BUG-11 — PATCH `/credentials` without `?userId=` returns 500
**Affects:** `test_missing_user_id_param_returns_400` (test_update.py)  
**Observed:** `500` (`MissingServletRequestParameterException` unhandled)  
**Expected:** `400`  
**Root cause:** Missing required query parameter exception handler not mapped.

---

### BUG-12 — DELETE `/credentials` without `?userId=` returns 500
**Affects:** `test_missing_user_id_param_does_not_crash` (test_delete.py)  
**Observed:** `500` (`MissingServletRequestParameterException` unhandled)  
**Expected:** Any non-500 status code  
**Root cause:** Same as BUG-11.

---

### BUG-13 — Non-UUID `credentialEntryId` in path returns 500
**Affects:** `test_non_uuid_entry_id_does_not_crash` in TestGetEntryNotFound and TestPatchEntryValidation  
**Observed:** `500`  
**Expected:** `400 VALIDATION_FAILED`  
**Root cause:** Same as BUG-6; entry ID path variable not handled by the 400 error mapper.

---

## Error Response Contract

All error responses follow a consistent shape. Tests assert these fields are present and correctly typed:

```json
{
  "timestamp": "2024-01-15T10:30:00.000Z",
  "status": 404,
  "error": "NOT_FOUND",
  "message": "..."
}
```

> **Note:** The spec documentation describes this field as `errorCode`. The server correctly returns `"error"`. All tests use `"error"` — the spec documentation has a mistake.

---

## Response Schema Coverage

| Schema | Endpoint(s) | Fields verified |
|--------|-------------|-----------------|
| `BiometricCredentialEnvelope` | POST, GET by ID, PATCH by ID | All required + optional-omitted fields |
| `BiometricCredentialPageResponse` | GET list, GET/PATCH/DELETE ?userId= | Envelope fields, pagination, all credential fields |
| `BiometricCredentialEntryResponse` | GET entry, PATCH entry | id, imageData, labels omit-when-empty, createdAt, updatedAt |
| Error response | All 4xx | timestamp (ISO-8601), status, error, fieldErrors |
