# Collections API — Integration Test Suite

Integration tests for `GET|POST|PATCH|DELETE /v3/tenants/{tenantId}/collections[/{collectionId}]`

Run against the QA1 environment. All tests hit a live API — no mocks.

---

## Running the tests

```bash
pytest tests/collections/ -v
```

Filter to a single file:
```bash
pytest tests/collections/test_create.py -v
```

Filter to passing tests only (skip known bugs):
```bash
pytest tests/collections/ -v -k "not (BUG)"
```

---

## Test files

### `conftest.py`
Shared fixtures and helpers used by every test file in this directory.

| Helper / Fixture | What it does |
|---|---|
| `collection_url(base_url, tenant_id, id?)` | Builds the full endpoint URL |
| `create_payload(name?, **overrides)` | Returns a valid `POST` body with a random name |
| `new_collection` fixture | Creates a fresh collection before the test, deletes it on teardown |

---

### `test_auth.py` — Authentication and authorization

Tests that the API enforces `X-Aware-ApiKey` and `X-Aware-AccountId` headers correctly.

| Test | What it checks |
|---|---|
| `test_invalid_api_key_returns_403` | Wrong API key → 403 on GET list |
| `test_invalid_api_key_on_post_returns_403` | Wrong API key → 403 on POST |
| `test_invalid_api_key_on_get_by_id_returns_403` | Wrong API key → 403 on GET by ID |
| `test_invalid_api_key_on_patch_returns_403` | Wrong API key → 403 on PATCH |
| `test_invalid_api_key_on_delete_returns_403` | Wrong API key → 403 on DELETE |
| `test_missing_api_key_returns_401` | **[BUG-1]** No API key header → should be 401, currently 500 |
| `test_missing_account_id_on_get_list_returns_403` | **[BUG-1]** No AccountId header → should be 403, currently 500 |
| `test_missing_account_id_on_post_returns_403` | **[BUG-1]** No AccountId header → should be 403, currently 500 |
| `test_missing_account_id_on_get_by_id_returns_403` | **[BUG-1]** No AccountId header → should be 403, currently 500 |
| `test_missing_account_id_on_patch_returns_403` | **[BUG-1]** No AccountId header → should be 403, currently 500 |
| `test_missing_account_id_on_delete_returns_403` | **[BUG-1]** No AccountId header → should be 403, currently 500 |

---

### `test_create.py` — POST /collections

Tests for creating biometric collections.

**TestCreateHappyPath** — valid requests succeed correctly

| Test | What it checks |
|---|---|
| `test_returns_201` | Successful POST returns 201 Created |
| `test_response_wrapped_in_envelope` | Response body has `biometricCollection` wrapper |
| `test_response_contains_required_fields` | All spec-required fields present in response |
| `test_id_is_uuid` | The returned `id` is a valid UUID |
| `test_storage_type_is_standard` | `storageType` echoed back correctly |
| `test_tenant_id_matches_path` | `tenantId` in response matches the URL path |
| `test_dedup_enabled_defaults_to_false` | `dedupEnabled` is `false` when not provided |
| `test_dedup_enabled_true_when_supplied` | `dedupEnabled` is `true` when explicitly set |
| `test_timestamps_are_integer_milliseconds` | `createdAt` and `updatedAt` are positive integers (epoch ms) |
| `test_description_omitted_when_not_supplied` | `description` field is absent when not sent |
| `test_description_present_when_supplied` | `description` is returned when provided |
| `test_response_content_type_is_json` | Response `Content-Type` is `application/json` |

**TestCreateValidation** — missing or invalid fields are rejected

| Test | What it checks |
|---|---|
| `test_missing_envelope_returns_400` | Request without `biometricCollection` wrapper → 400 |
| `test_empty_body_returns_400` | Empty JSON object `{}` → 400 |
| `test_missing_name_returns_400` | **[BUG-3]** No `name` → 400 with `errorCode: VALIDATION_FAILED` (field name is `error` not `errorCode`) |
| `test_blank_name_returns_400` | **[BUG-3]** Whitespace-only name → 400 with `errorCode: VALIDATION_FAILED` |
| `test_missing_storage_type_returns_400` | **[BUG-3]** No `storageType` → 400 with `errorCode: VALIDATION_FAILED` |
| `test_invalid_storage_type_returns_400` | Unknown `storageType` value → 400 |
| `test_missing_created_by_returns_400` | **[BUG-3]** No `createdBy` → 400 with `errorCode: VALIDATION_FAILED` |
| `test_empty_name_returns_400` | Empty string name → 400 |
| `test_empty_created_by_returns_400` | Empty string `createdBy` → 400 |
| `test_validation_error_includes_field_errors` | **[BUG-3]** 400 body must have `errorCode` and `fieldErrors` |

**TestCreateNameBoundaries** — edge cases for name length and character set

| Test | What it checks |
|---|---|
| `test_name_at_255_chars_is_accepted` | 255-character name is accepted |
| `test_very_long_name_is_accepted_or_rejected` | 300-character name returns 201 or 400 — not 500 |
| `test_unicode_name_is_accepted` | Unicode (accents, CJK) in name is stored and returned correctly |
| `test_long_description_is_accepted` | 1000-character description is stored correctly |

**TestCreateServerManagedFields** — client cannot inject server-owned fields

| Test | What it checks |
|---|---|
| `test_client_id_is_ignored` | Client-supplied `id` is discarded — the server generates a new UUID |
| `test_client_tenant_id_is_ignored` | Client-supplied `tenantId` is discarded — value comes from the URL path |
| `test_client_created_at_is_ignored` | Client-supplied `createdAt` is discarded — server sets it to now |
| `test_client_updated_at_is_ignored` | Client-supplied `updatedAt` is discarded — server sets it to now |
| `test_client_updated_by_is_ignored_on_create` | Client-supplied `updatedBy` is discarded — field is absent on a fresh collection |

**TestCreateConflict** — duplicate name handling

| Test | What it checks |
|---|---|
| `test_duplicate_name_returns_409` | **[BUG-3]** Same name in same tenant → 409 with `errorCode: CONFLICT` |

---

### `test_get.py` — GET /collections/{collectionId}

Tests for retrieving a single collection by ID.

**TestGetByIdHappyPath** — successful retrieval

| Test | What it checks |
|---|---|
| `test_returns_200` | GET by ID returns 200 |
| `test_response_contains_required_fields` | All required fields present |
| `test_response_wrapped_in_envelope` | Response has `biometricCollection` wrapper |
| `test_returned_id_matches_requested_id` | The returned `id` matches the requested one |
| `test_timestamps_are_integer_milliseconds` | Timestamps are positive integers |
| `test_response_content_type_is_json` | Content-Type is `application/json` |

**TestGetByIdDataIntegrity** — data matches what was created

| Test | What it checks |
|---|---|
| `test_fields_match_create_payload` | `name`, `storageType`, `createdBy` match the POST payload |
| `test_tenant_id_matches_path` | `tenantId` matches the URL |

**TestGetByIdNotFound** — missing or deleted resources

| Test | What it checks |
|---|---|
| `test_nonexistent_id_returns_404` | **[BUG-3]** Random UUID → 404 with `errorCode: NOT_FOUND` |
| `test_soft_deleted_collection_returns_404` | **[BUG-3]** Deleted collection → 404 with `errorCode: NOT_FOUND` |

---

### `test_update.py` — PATCH /collections/{collectionId}

Tests for partially updating a collection.

**TestUpdateHappyPath** — fields update correctly

| Test | What it checks |
|---|---|
| `test_returns_200` | PATCH returns 200 |
| `test_name_is_updated` | New name reflected in response |
| `test_description_is_updated` | New description reflected in response |
| `test_dedup_enabled_is_updated` | `dedupEnabled` toggle persists |
| `test_updated_by_is_set` | `updatedBy` reflected in response |
| `test_updated_at_advances` | `updatedAt` is >= `createdAt` after PATCH |
| `test_created_by_unchanged_after_patch` | `createdBy` is never overwritten |
| `test_created_at_unchanged_after_patch` | `createdAt` is never overwritten |
| `test_response_wrapped_in_envelope` | Response has `biometricCollection` wrapper |
| `test_patch_persists_via_get` | Changes visible in a subsequent GET |
| `test_rename_to_own_name_returns_200` | Patching with the same name is not a conflict |
| `test_empty_inner_object_is_accepted` | Empty `biometricCollection: {}` is a no-op |
| `test_description_null_is_handled_gracefully` | `description: null` does not crash the API |

**TestUpdateClientSuppliedImmutableFields** — server-owned fields cannot be overwritten via PATCH

| Test | What it checks |
|---|---|
| `test_id_cannot_be_changed_via_patch` | Client-supplied `id` in PATCH is ignored — GET returns the original id |
| `test_tenant_id_cannot_be_changed_via_patch` | Client-supplied `tenantId` in PATCH is ignored — GET returns the URL's tenantId |
| `test_created_by_cannot_be_changed_via_patch` | Client-supplied `createdBy` in PATCH is ignored — GET returns the original createdBy |
| `test_created_at_cannot_be_changed_via_patch` | Client-supplied `createdAt` in PATCH is ignored — GET returns the original timestamp |
| `test_all_immutable_fields_ignored_together` | All four fields sent together in one PATCH are all ignored — single GET confirms all four unchanged |

**TestUpdateImmutability** — fields that cannot be changed

| Test | What it checks |
|---|---|
| `test_storage_type_returns_400` | **[BUG-3]** Changing `storageType` (valid value) → 400 STORAGE_TYPE_IMMUTABLE |
| `test_storage_type_error_message` | Error message mentions `storageType` |
| `test_invalid_storage_type_value_returns_400` | **[BUG-3]** `storageType: "PREMIUM"` (invalid enum) → 400 STORAGE_TYPE_IMMUTABLE; immutability checked before enum validation |
| `test_null_storage_type_returns_400` | **[BUG-11]** `storageType: null` → 400 STORAGE_TYPE_IMMUTABLE; currently returns 200 (null treated as absent) |

**TestUpdateConflict** — name uniqueness on rename

| Test | What it checks |
|---|---|
| `test_rename_to_existing_name_returns_409` | **[BUG-3]** Renaming to a taken name → 409 with `errorCode: CONFLICT` |

**TestUpdateValidation** — invalid inputs

| Test | What it checks |
|---|---|
| `test_missing_envelope_returns_400` | No `biometricCollection` wrapper → 400 |
| `test_empty_name_returns_400` | Empty string name → 400 or 409 |
| `test_whitespace_name_returns_400` | Whitespace-only name → 400 or 409 |
| `test_updated_by_accepts_email_format` | Email-format `updatedBy` is accepted |

**TestUpdateNotFound**

| Test | What it checks |
|---|---|
| `test_nonexistent_id_returns_404` | **[BUG-3]** Random UUID → 404 with `errorCode: NOT_FOUND` |

---

### `test_delete.py` — DELETE /collections/{collectionId}

Tests for soft-deleting a collection.

**TestDeleteHappyPath**

| Test | What it checks |
|---|---|
| `test_returns_204` | DELETE returns 204 No Content |
| `test_response_has_no_body` | Response body is empty |
| `test_delete_decrements_total_elements` | `totalElements` decreases by 1 after deletion |

**TestDeleteSoftDelete** — verifies soft-delete behavior

| Test | What it checks |
|---|---|
| `test_deleted_collection_get_returns_404` | **[BUG-3]** GET after delete → 404 with `errorCode: NOT_FOUND` |
| `test_deleted_collection_excluded_from_list` | Deleted collection absent from list results |
| `test_deleted_collection_patch_returns_404` | PATCH after delete → 404 |

**TestDeleteNotFound**

| Test | What it checks |
|---|---|
| `test_nonexistent_id_returns_404` | **[BUG-3]** Random UUID → 404 with `errorCode: NOT_FOUND` |
| `test_already_deleted_returns_404` | Deleting the same ID twice → 404 on second call |
| `test_non_uuid_id_returns_400_or_404` | **[BUG-2]** Non-UUID ID → should be 400/404, currently 500 |

---

### `test_list.py` — GET /collections (list, filter, paginate)

**TestListHappyPath**

| Test | What it checks |
|---|---|
| `test_returns_200` | List endpoint returns 200 |
| `test_response_shape` | Response has `biometricCollections`, `page`, `size`, `totalElements`, `totalPages` |
| `test_default_pagination` | Default is `page=0`, `size=25` |
| `test_response_content_type_is_json` | Content-Type is `application/json` |
| `test_created_collection_appears_in_list` | Newly created collection visible in list |

**TestListFilters**

| Test | What it checks |
|---|---|
| `test_name_filter_returns_matching` | `?name=x` returns collections whose name contains `x` |
| `test_name_filter_is_case_insensitive` | `?name=DEMO` finds a collection named `demo` |
| `test_name_filter_no_match_returns_empty` | Non-matching name returns empty list and `totalElements=0` |
| `test_storage_type_filter` | `?storageType=STANDARD` returns only STANDARD collections |
| `test_dedup_enabled_filter` | `?dedupEnabled=true` returns only collections with `dedupEnabled=true` |
| `test_dedup_disabled_filter` | `?dedupEnabled=false` returns only collections with `dedupEnabled=false` |
| `test_soft_deleted_excluded_from_list` | Soft-deleted collections do not appear in list results |

**TestListPagination**

| Test | What it checks |
|---|---|
| `test_size_param_limits_results` | `?size=1` returns at most 1 result |
| `test_size_over_100_is_capped` | `?size=999` is silently capped to 100 |
| `test_page_param_is_zero_based` | `?page=0` is the first page |
| `test_page_beyond_last_returns_empty_list` | `?page=99999` returns empty list, not an error |
| `test_total_elements_reflects_created_collection` | `totalElements` is at least 1 after creating a collection |
| `test_size_zero_returns_400` | **[BUG-4]** `?size=0` → should be 400, currently 500 |
| `test_negative_page_returns_400` | **[BUG-5]** `?page=-1` → should be 400, currently 500 |

**TestListPaginationBehavior** — real multi-page traversal

| Test | What it checks |
|---|---|
| `test_no_duplicate_ids_across_pages` | Creates 3 collections, fetches page 0 and page 1 at `size=2`, asserts no ID appears on both pages, `totalElements=3`, `totalPages=2`, and the union of both pages equals exactly the 3 created IDs |

**TestListFilterCombined**

| Test | What it checks |
|---|---|
| `test_name_and_storage_type_combined` | `?name=x&storageType=STANDARD` only returns matching collections |
| `test_name_and_dedup_combined_no_match` | `?name=x&dedupEnabled=true` returns empty when the named collection has `dedupEnabled=false` |
| `test_list_ordering_is_stable` | Two identical requests return results in the same order |

---

### `test_isolation.py` — Cross-tenant data isolation

Tests that tenant A's data is invisible and inaccessible to tenant B.

| Test | What it checks |
|---|---|
| `test_collection_from_tenant_a_not_readable_by_tenant_b` | GET with tenant B credentials on tenant A's collection ID → 403/404 |
| `test_tenant_b_credentials_cannot_list_tenant_a_collections` | GET list with tenant B credentials on tenant A's URL → 403 or empty list |
| `test_collection_from_tenant_a_not_patchable_by_tenant_b` | PATCH with tenant B credentials on tenant A's collection → 403/404 |
| `test_collection_from_tenant_a_not_deletable_by_tenant_b` | DELETE with tenant B credentials on tenant A's collection → 403/404 |
| `test_same_name_allowed_across_different_tenants` | The same collection name can be created in two different tenants (name uniqueness is per-tenant) |

> Requires `AWARE_TENANT_ID_2` (`efd53128-7c95-47c3-bf7b-2f86d00848f0` — testtest1) and `AWARE_API_KEY_2` environment variables. Tests are skipped if not set.

---

### `test_path_params.py` — Malformed path parameters

**TestNonUuidCollectionId**

| Test | What it checks |
|---|---|
| `test_get_non_uuid_id_returns_400_or_404` | **[BUG-2]** `GET .../not-a-uuid` → should be 400/404, currently 500 |
| `test_patch_non_uuid_id_returns_400_or_404` | **[BUG-2]** `PATCH .../not-a-uuid` → should be 400/404, currently 500 |
| `test_delete_non_uuid_id_returns_400_or_404` | **[BUG-2]** `DELETE .../not-a-uuid` → should be 400/404, currently 500 |

**TestNonExistentTenantId**

| Test | What it checks |
|---|---|
| `test_get_list_unknown_tenant_returns_empty_or_error` | GET list with unknown tenantId → 200 (empty) or 403/404 |
| `test_post_unknown_tenant_does_not_create` | POST to unknown tenantId → 403/404; service verifies tenant exists before creating |
| `test_get_by_id_unknown_tenant_not_200` | GET by ID with unknown tenantId → not a resource leak |

---

### `test_request_body.py` — Malformed request bodies

**TestPostRequestBody**

| Test | What it checks |
|---|---|
| `test_null_envelope_returns_400` | `biometricCollection: null` → 400 (working correctly) |
| `test_malformed_json_returns_400` | **[BUG-7]** `{not valid json` body → should be 400, currently 500 |
| `test_text_plain_content_type_returns_415` | **[BUG-7]** `Content-Type: text/plain` → should be 415, currently 500 |
| `test_empty_raw_body_returns_400` | **[BUG-7]** Empty raw body → should be 400, currently 500 |

**TestPatchRequestBody**

| Test | What it checks |
|---|---|
| `test_null_envelope_returns_400` | `biometricCollection: null` → 400 (working correctly) |
| `test_malformed_json_returns_400` | **[BUG-7]** Malformed JSON → should be 400, currently 500 |
| `test_text_plain_content_type_returns_415` | **[BUG-7]** Wrong Content-Type → should be 415, currently 500 |
| `test_empty_raw_body_returns_400` | **[BUG-7]** Empty raw body → should be 400, currently 500 |

---

### `test_name_normalization.py` — Name case and whitespace handling

**TestNameCaseSensitivity**

| Test | What it checks |
|---|---|
| `test_case_variants_create_distinct_collections` | Documents that `"Demo"`, `"demo"`, `"DEMO"` are currently accepted as distinct names (case-sensitive uniqueness) |
| `test_different_case_variants_have_distinct_ids` | Confirms case variants have different IDs |
| `test_filter_is_case_insensitive` | `?name=DEMO` finds a collection named `demo` (filter is case-insensitive) |
| `test_lowercase_after_mixed_case_returns_409` | **[BUG-9]** `"demo"` after `"Demo"` → should be 409 (case-insensitive uniqueness); currently 201 — contradicts the case-insensitive filter |

**TestNameWhitespaceTrimming**

| Test | What it checks |
|---|---|
| `test_leading_whitespace_creates_separate_collection` | **[BUG-8]** `" Demo"` after `"Demo"` → should be 409; currently 201 (names not trimmed) |
| `test_trailing_whitespace_creates_separate_collection` | **[BUG-8]** `"Demo "` after `"Demo"` → should be 409; currently 201 |
| `test_both_sides_whitespace_creates_separate_collection` | **[BUG-8]** `" Demo "` after `"Demo"` → should be 409; currently 201 |
| `test_whitespace_name_is_stored_verbatim` | Documents that names including whitespace are stored exactly as sent |
| `test_filter_substring_finds_whitespace_padded_name` | Filter still finds a padded name via substring match |

---

## Known bugs (failing tests)

| Bug | Description | Tests failing | Root cause |
|---|---|---|---|
| BUG-1 | Missing required headers crash with 500 instead of 401/403 | 6 | `MissingRequestHeaderException` unhandled in Spring |
| BUG-2 | Non-UUID collectionId crashes with 500 instead of 400/404 | 4 | `MethodArgumentTypeMismatchException` unhandled |
| BUG-3 | Error response field is `"error"` instead of `"errorCode"` per spec | 13 | Response DTO uses wrong field name |
| BUG-4 | `?size=0` crashes with 500 instead of 400 | 1 | `IllegalArgumentException` from Spring Data unhandled |
| BUG-5 | `?page=-1` crashes with 500 instead of 400 | 1 | `IllegalArgumentException` from Spring Data unhandled |
| BUG-7 | Malformed body / wrong Content-Type crashes with 500 instead of 400/415 | 6 | `HttpMessageNotReadableException` / `HttpMediaTypeNotSupportedException` unhandled |
| BUG-8 | Leading/trailing whitespace in names not trimmed — invisible duplicates allowed | 3 | No `@NotBlank` trim or service-layer normalization |
| BUG-9 | Name uniqueness is case-sensitive but list filter is case-insensitive | 1 | DB unique constraint is case-sensitive; inconsistent with filter behavior |

> **Note:** Bug-3 is the highest-impact fix — it will turn 13 failing tests green immediately upon correcting the response field name from `"error"` to `"errorCode"`.
> BUG-4 and BUG-5 share the same root cause as BUG-1/BUG-2 (missing global exception handler in Spring) and can likely be fixed together.
