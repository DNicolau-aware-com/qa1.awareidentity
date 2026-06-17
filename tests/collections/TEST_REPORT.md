# Collections API — Test Report

**Date:** 2026-06-16
**Environment:** QA1 — https://api.qa1.awareidentity.com
**Tenant A (primary):** test01 (`3d95a209-5011-446c-bf7f-34217e7a31f6`)
**Tenant B (isolation):** testtest1 (`efd53128-7c95-47c3-bf7b-2f86d00848f0`)

---

## Summary

| | Count |
|---|---|
| Total tests | 141 |
| Passed | 102 |
| Failed | 38 |
| Skipped | 1 |

> All 38 failures are **intentional bug trackers**. They assert the correct expected behavior and will pass automatically once the underlying bug is fixed. 

---

## Results by file

| File | Passed | Failed | Skipped |
|---|---|---|---|
| `test_auth.py` | 5 | 6 | 0 |
| `test_create.py` | 21 | 6 | 0 |
| `test_delete.py` | 5 | 3 | 0 |
| `test_get.py` | 8 | 2 | 0 |
| `test_isolation.py` | 3 | 1 | 1 |
| `test_list.py` | 16 | 2 | 0 |
| `test_name_normalization.py` | 5 | 4 | 0 |
| `test_path_params.py` | 3 | 3 | 0 |
| `test_request_body.py` | 2 | 6 | 0 |
| `test_update.py` | 34 | 5 | 0 |
| **Total** | **102** | **38** | **1** |

---

## Bug tracker: failures grouped by bug

### BUG-1 — Missing required headers return 500 instead of 401/403
**6 tests failing** | Endpoints: all 5 (GET list, POST, GET by ID, PATCH, DELETE)

When `X-Aware-ApiKey` or `X-Aware-AccountId` is absent, Spring's `MissingRequestHeaderException` is unhandled and surfaces as 500 Internal Server Error. Expected: 401 (missing API key) or 403 (missing AccountId).

| Failing test |
|---|
| `test_auth.py::test_missing_api_key_returns_401` |
| `test_auth.py::test_missing_account_id_on_get_list_returns_403` |
| `test_auth.py::test_missing_account_id_on_post_returns_403` |
| `test_auth.py::test_missing_account_id_on_get_by_id_returns_403` |
| `test_auth.py::test_missing_account_id_on_patch_returns_403` |
| `test_auth.py::test_missing_account_id_on_delete_returns_403` |

**Reproduce:**
```
GET /v3/tenants/{tenantId}/collections
X-Aware-ApiKey: <valid key>
# X-Aware-AccountId omitted

→ 500 Internal Server Error
  "Required request header X-Aware-AccountId for method parameter type String is not present"
```

---

### BUG-2 — Non-UUID collectionId crashes with 500 instead of 400/404
**4 tests failing** | Endpoints: GET by ID, PATCH, DELETE

When a non-UUID value (e.g. `"not-a-uuid"`) is passed as `{collectionId}`, Spring's `MethodArgumentTypeMismatchException` is unhandled and surfaces as 500. Expected: 400 (bad format) or 404.

| Failing test |
|---|
| `test_path_params.py::test_get_non_uuid_id_returns_400_or_404` |
| `test_path_params.py::test_patch_non_uuid_id_returns_400_or_404` |
| `test_path_params.py::test_delete_non_uuid_id_returns_400_or_404` |
| `test_delete.py::test_non_uuid_id_returns_400_or_404` |

**Reproduce:**
```
GET /v3/tenants/{tenantId}/collections/not-a-uuid

→ 500 Internal Server Error
```

---

### BUG-3 — Error response field is `"error"` instead of `"errorCode"` per spec
**13 tests failing** | Endpoints: all

The API spec defines the error response field as `errorCode`. The API returns `error`. Every test that asserts `.get("errorCode")` fails because the field does not exist under that name.

**Highest-impact fix** — correcting the response field name will turn 13 tests green at once.

| Failing test | Expected errorCode value |
|---|---|
| `test_create.py::test_missing_name_returns_400` | `VALIDATION_FAILED` |
| `test_create.py::test_blank_name_returns_400` | `VALIDATION_FAILED` |
| `test_create.py::test_missing_storage_type_returns_400` | `VALIDATION_FAILED` |
| `test_create.py::test_missing_created_by_returns_400` | `VALIDATION_FAILED` |
| `test_create.py::test_validation_error_includes_field_errors` | `VALIDATION_FAILED` |
| `test_create.py::test_duplicate_name_returns_409` | `CONFLICT` |
| `test_delete.py::test_deleted_collection_get_returns_404` | `NOT_FOUND` |
| `test_delete.py::test_nonexistent_id_returns_404` | `NOT_FOUND` |
| `test_get.py::test_nonexistent_id_returns_404` | `NOT_FOUND` |
| `test_get.py::test_soft_deleted_collection_returns_404` | `NOT_FOUND` |
| `test_update.py::test_storage_type_returns_400` | `STORAGE_TYPE_IMMUTABLE` |
| `test_update.py::test_invalid_storage_type_value_returns_400` | `STORAGE_TYPE_IMMUTABLE` |
| `test_update.py::test_rename_to_existing_name_returns_409` | `CONFLICT` |
| `test_update.py::test_nonexistent_id_returns_404` | `NOT_FOUND` |

**Reproduce:**
```
POST /v3/tenants/{tenantId}/collections
{ "biometricCollection": { "storageType": "STANDARD", "createdBy": "x" } }

→ 400
{
  "error": "VALIDATION_FAILED",   ← spec says this should be "errorCode"
  "fieldErrors": { ... },
  ...
}
```

---

### BUG-4 — `?size=0` crashes with 500 instead of 400
**1 test failing** | Endpoint: GET /collections

Spring Data's `PageRequest` throws `IllegalArgumentException("Page size must not be less than one")` which is unhandled.

| Failing test |
|---|
| `test_list.py::test_size_zero_returns_400` |

**Reproduce:**
```
GET /v3/tenants/{tenantId}/collections?size=0

→ 500 Internal Server Error
```

---

### BUG-5 — `?page=-1` crashes with 500 instead of 400
**1 test failing** | Endpoint: GET /collections

Spring Data's `PageRequest` throws `IllegalArgumentException("Page index must not be less than zero")` which is unhandled.

| Failing test |
|---|
| `test_list.py::test_negative_page_returns_400` |

**Reproduce:**
```
GET /v3/tenants/{tenantId}/collections?page=-1

→ 500 Internal Server Error
  "Page index must not be less than zero"
```

> BUG-4 and BUG-5 share the same root cause as BUG-1 and BUG-2 — a missing global `@ExceptionHandler` for `IllegalArgumentException` and `MethodArgumentTypeMismatchException`. All four can likely be fixed in a single change.

---

### BUG-7 — Malformed request body / wrong Content-Type crashes with 500
**6 tests failing** | Endpoints: POST, PATCH

Spring's `HttpMessageNotReadableException` (malformed JSON, empty body) and `HttpMediaTypeNotSupportedException` (wrong Content-Type) are unhandled.

| Failing test | Scenario | Expected | Actual |
|---|---|---|---|
| `test_request_body.py::TestPostRequestBody::test_malformed_json_returns_400` | `{not valid json` | 400 | 500 |
| `test_request_body.py::TestPostRequestBody::test_text_plain_content_type_returns_415` | `Content-Type: text/plain` | 415 | 500 |
| `test_request_body.py::TestPostRequestBody::test_empty_raw_body_returns_400` | Empty raw body | 400 | 500 |
| `test_request_body.py::TestPatchRequestBody::test_malformed_json_returns_400` | `{not valid json` | 400 | 500 |
| `test_request_body.py::TestPatchRequestBody::test_text_plain_content_type_returns_415` | `Content-Type: text/plain` | 415 | 500 |
| `test_request_body.py::TestPatchRequestBody::test_empty_raw_body_returns_400` | Empty raw body | 400 | 500 |

**Reproduce (malformed JSON):**
```
POST /v3/tenants/{tenantId}/collections
Content-Type: application/json
Body: {not valid json

→ 500 Internal Server Error
```

---

### BUG-8 — Leading/trailing whitespace in names is not trimmed
**3 tests failing** | Endpoints: POST

Names are stored verbatim. `"Demo"` and `" Demo "` are treated as distinct names and both return 201. This allows invisible duplicates that appear identical in any UI.

| Failing test |
|---|
| `test_name_normalization.py::test_leading_whitespace_creates_separate_collection` |
| `test_name_normalization.py::test_trailing_whitespace_creates_separate_collection` |
| `test_name_normalization.py::test_both_sides_whitespace_creates_separate_collection` |

**Reproduce:**
```
POST → { "name": "Demo" }       → 201, id: aaa
POST → { "name": " Demo " }     → 201, id: bbb  (should be 409)
POST → { "name": "Demo " }      → 201, id: ccc  (should be 409)
```

---

### BUG-9 — Name uniqueness is case-sensitive but list filter is case-insensitive
**1 test failing** | Endpoints: POST, GET /collections

`"Demo"` and `"demo"` are accepted as separate collections (case-sensitive uniqueness constraint), but `GET /collections?name=demo` returns both (case-insensitive filter). The behaviors are inconsistent: a user cannot use the search filter to reliably detect whether a name is already taken.

| Failing test |
|---|
| `test_name_normalization.py::test_lowercase_after_mixed_case_returns_409` |

**Reproduce:**
```
POST → { "name": "Demo" }   → 201
POST → { "name": "demo" }   → 201  (should be 409 if uniqueness matches filter behavior)

GET ?name=Demo → returns both "Demo" and "demo"
```


---

### BUG-10 — CRITICAL: Cross-tenant data leak on the Collections list endpoint
**1 test failing** | Endpoint: GET /collections
**Severity:** Critical — Security vulnerability

The Collections list endpoint does not validate that the `X-Aware-ApiKey` header belongs to the tenant identified by `{tenantId}` in the URL path. Any authenticated API key from any tenant can retrieve the full collection list of any other tenant by substituting that tenant's ID in the URL. The API returns 200 with all of the target tenant's data — no 403 is raised.

GET by ID, PATCH, and DELETE do **not** have this problem — they correctly return 403/404. The leak is isolated to the list endpoint.

| Failing test |
|---|
| `test_isolation.py::test_tenant_b_credentials_cannot_list_tenant_a_collections` |

**Steps to reproduce:**

1. Obtain a valid API key for **Tenant B** (any active tenant).
2. Obtain the tenant ID of **Tenant A** (a completely different tenant).
3. Send the following request using Tenant B's API key in the headers, but Tenant A's ID in the URL:

```
GET https://api.qa1.awareidentity.com/v3/tenants/{tenantA-id}/collections
X-Aware-ApiKey: {tenantB-apikey}
X-Aware-AccountId: 0001
```

**Concrete example (QA1):**

```
GET https://api.qa1.awareidentity.com/v3/tenants/3d95a209-5011-446c-bf7f-34217e7a31f6/collections
X-Aware-ApiKey: f4847344231fd62e1858fc47b4297520b4c1d0d551671ff7fb29c37406c689e7
X-Aware-AccountId: 0001
```

*(API key belongs to `testtest1` / `efd53128-7c95-47c3-bf7b-2f86d00848f0`. The URL tenantId belongs to `test01`.)*

**Expected result:**
```json
HTTP 403 Forbidden
{
  "status": 403,
  "errorCode": "FORBIDDEN",
  "message": "Access denied"
}
```

**Actual result:**
```json
HTTP 200 OK
{
  "page": 0,
  "size": 25,
  "totalElements": 36,
  "totalPages": 2,
  "biometricCollections": [
    {
      "id": "...",
      "tenantId": "3d95a209-5011-446c-bf7f-34217e7a31f6",
      "name": "boston",
      "storageType": "STANDARD",
      ...
    },
    ...
  ]
}
```

All 36 collections belong to `test01`. Tenant B has full read access to Tenant A's data.

**Scope — confirmed with two independent Tenant B accounts:**

| Tenant B | Tenant B ID | Result against test01 |
|---|---|---|
| testtest1 | `efd53128-7c95-47c3-bf7b-2f86d00848f0` | 200 — 36 collections leaked |
| dantest01 | `ec79d440-3ba7-4abc-b00e-38141ff52b9b` | 200 — 36 collections leaked |

The vulnerability is systemic — not specific to a single tenant pair.

**Endpoint comparison — which endpoints are affected:**

| Endpoint | Tenant B result | Correctly isolated? |
|---|---|---|
| `GET /collections` | **200 — data leaked** | No |
| `GET /collections/{id}` | 403 / 404 | Yes |
| `PATCH /collections/{id}` | 403 / 404 | Yes |
| `DELETE /collections/{id}` | 403 / 404 | Yes |



### BUG-11 — `storageType: null` accepted silently instead of returning 400
**1 test failing** | Endpoint: PATCH /collections/{id}

When `storageType` is set to `null` in a PATCH body, the API returns 200 and ignores the field. The spec says storageType is immutable — any PATCH body containing the key (even with a null value) must return 400 STORAGE_TYPE_IMMUTABLE. The current behavior means a client can "clear" or probe storageType without being told it's off-limits.

| Failing test |
|---|
| `test_update.py::test_null_storage_type_returns_400` |

**Reproduce:**
```
PATCH /v3/tenants/{tenantId}/collections/{id}
{ "biometricCollection": { "storageType": null } }

→ 200 OK   (expected: 400 STORAGE_TYPE_IMMUTABLE)
```

> Contrast: `storageType: "STANDARD"` and `storageType: "PREMIUM"` both return 400 STORAGE_TYPE_IMMUTABLE correctly. Only `null` slips through.

---

## What is passing (102 tests)

- Full happy-path coverage for POST, GET by ID, PATCH, DELETE, and GET list
- Server-managed fields on create (`id`, `tenantId`, `createdAt`, `updatedAt`, `updatedBy`) are all ignored — client cannot inject them
- Immutable fields on PATCH (`id`, `tenantId`, `createdBy`, `createdAt`) are all ignored — GET after PATCH confirms original values unchanged
- All validation rejections (missing fields, invalid values, wrong envelope)
- Soft-delete behavior (excluded from list, GET/PATCH return 404)
- Pagination: default values, `size` cap at 100, zero-based `page`, empty page beyond last, real multi-page traversal with no duplicate IDs
- All filter combinations: `name` (substring, case-insensitive), `storageType`, `dedupEnabled=true`, `dedupEnabled=false`, combined filters
- Cross-tenant isolation: GET by ID, PATCH, DELETE correctly blocked across tenants (list endpoint leaks — see BUG-10)
- Name boundaries: 255-char name, Unicode, long description
- Response shape: envelope, Content-Type, all required fields, timestamp format
- Auth: invalid API key rejected with 403 on all 5 endpoints
- Path params: unknown tenantId returns empty or 403/404

---

