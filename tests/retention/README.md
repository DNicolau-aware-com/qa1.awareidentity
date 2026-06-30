# Data Retention Policy Tests

Integration tests for `GET /v3/tenants/{tenantId}/data-retention-policy` and
`PUT /v3/tenants/{tenantId}/data-retention-policy`.

**Story:** AWRNSS-316 — *MVP: Tenant Level Retention Policies*
**Supporting work:** *Generic Job Framework for Data Retention Policy* (job
definition / scheduling / execution + ShedLock-based multi-node deletion engine).

## Requirements (AWRNSS-316)

Tenant administrators configure tenant-wide lifecycle policies from the
**Administration → Data Management** page. Each data category has a retention
period (in days) and an auto-delete toggle that controls whether expired data is
removed once it passes the retention window.

### Data categories

The MVP story groups data into business categories; the API contract exposes
them at a finer grain. The mapping the tests assume:

| AWRNSS-316 category | API field(s) | Notes |
|---|---|---|
| Biometric Data | `templates` + `enrollmentImages` | enrolled templates + source enrollment images |
| Log Data | `logs` | verification / liveness transaction logs + captured images |
| Billing Data | _(not in API yet)_ | min 365 days; out of MVP UI scope, pending Product (Sarah) |

### Business rules

| Rule | Value | Where tested |
|---|---|---|
| Minimum retention period | **1 day** (when the customer changes config) | `test_max_retention_days_of_zero_returns_400`, `test_negative_max_retention_days_returns_400` |
| Maximum retention period | **1095 days** (≈3 years) | bounded dynamically via `system_ceilings` — see discrepancy note below |
| Default — Biometric Data | 180 days | seeded by backend at tenant creation (not asserted; values vary by env) |
| Default — Log Data | 90 days | seeded by backend at tenant creation |
| Authorization | Tenant Administrator only | `test_auth.py` (401/403) |
| Audit logging | retention changes + deletion actions logged | backend/async — out of scope for this API test suite |
| Auto-delete | expired data removed by the Job Framework when toggle is on | deletion engine — out of scope for this API test suite |

> **Spec ⇄ story discrepancy (flagged):** AWRNSS-316 states a single flat
> maximum of **1095 days** for all categories, but the OpenAPI contract exposes a
> per-category `systemMaxRetentionDays` (example values 365/90/30) and the tests
> bound against *that* value. The tests therefore enforce the API contract, not
> the flat 1095 figure. If 1095 is the intended ceiling, the API examples and/or
> the story need to be reconciled. The per-modality limits in the API contract
> also have no counterpart in the MVP UI story.

### Out of scope for these tests

Deletion/anonymization engine execution, audit-log assertions, the Job Framework
(scheduling, `JOB_DEFINITION`/`JOB_SCHEDULE`, ShedLock distributed locking),
log-retention *enforcement*, billing-data retention, and legal-hold workflows.
This suite validates only the read/update API contract, validation, authorization,
and error behavior.

## Structure

| File | Tests | Description |
|---|---|---|
| `conftest.py` | — | Auth/tenant overrides, URL builder, `valid_policy()` helper, `current_policy` and `system_ceilings` fixtures |
| `test_auth.py` | 8 | Two-layer auth: gateway JWT (401/400) + app API-key (403/200) |
| `test_get.py` | 19 | GET happy path, shape, data integrity, not-found |
| `test_update.py` | 38 | PUT happy path, server-managed fields, business rules, validation, atomicity, error shape, not-found |
| `test_path_params.py` | 3 | Non-UUID tenantId path parameter validation |
| `test_edge_cases.py` | 21 | Numeric overflow, unsupported HTTP methods, category/modality consistency, boolean coercion, modality value/key validation |

**Total: 89 tests** — last run (qa2, test02): **63 passed, 26 known-bug failures**.

## Running

```bash
# All retention tests
pytest tests/retention/ -v

# Single file
pytest tests/retention/test_update.py -v

# Only tests expected to pass (skip known-bug tests)
pytest tests/retention/ -v -k "not BUG"
```

## Fixtures

### `current_policy` (function-scoped)
Used by every PUT test that actually modifies the policy.  Snapshots the live
policy before the test runs and restores it in teardown — regardless of whether
the test passes or fails.  Always strip `systemMaxRetentionDays` before using
the yielded dict as a PUT body (the fixture provides a deep copy, not a
ready-made payload).

```python
def test_example(self, base_url, auth_headers, tenant_id, current_policy):
    payload = {k: v for k, v in current_policy.items() if k != "systemMaxRetentionDays"}
    payload["saltLogsToRemovePii"] = True
    resp = requests.put(retention_url(base_url, tenant_id), json=payload, headers=auth_headers)
    assert resp.status_code == 200
```

### `system_ceilings` (session-scoped)
Fetches `systemMaxRetentionDays` once per session.  Use this in any boundary
test that needs to send `ceiling + 1` to trigger a `SETTINGS_INVALID` error,
so tests stay correct across environments with different configurations.

### `valid_policy()` helper
Returns a hard-coded structurally valid payload with conservative values
(templates=30d, enrollmentImages=7d, logs=1d).  Safe for auth and path-param
tests where the server rejects the request before reaching business logic.
**Do not use in tests that expect 200** — values may violate environment-specific
system ceilings; use `current_policy` instead.

## Authentication (two-layer)

Unlike the rest of the v3 API (API-key only), these endpoints require **both**:

1. **Gateway (Istio) — a Keycloak bearer JWT** in `Authorization`.
   - missing → `401 "Missing or invalid Authorization header"`
   - malformed / non-Keycloak issuer → `400 "Cannot derive JWKS URL ..."`
2. **App — the `X-Aware-ApiKey` (+ `X-Aware-AccountId`) headers**, checked only
   after a valid bearer passes the gateway.
   - missing / invalid key → `403`
   - valid → `200`
   - (a mismatched `X-Aware-AccountId` is **not** rejected here — `9999` still 200)

### Getting the token

The `bearer_token` fixture (root `conftest.py`) mints a token automatically.
Provide credentials via a gitignored `tests/.keycloak_creds` file:

```
# client-credentials flow (service account):
REALM=test02
CLIENT_ID=awareness-portal-service
CLIENT_SECRET=<b2b client secret>

# OR password flow (real user; comment out CLIENT_SECRET):
# CLIENT_ID=admin-cli
# USERNAME=<admin email>
# PASSWORD=<password>
```

Token endpoint: `https://auth.qa2.awareidentity.com/realms/{REALM}/protocol/openid-connect/token`.
A one-shot token can also be dropped into `tests/.bearer_token`, or supplied via
`AWARE_BEARER_TOKEN`. The suite runs against the **test02** tenant so the API key
(`API_KEY_2`) and the bearer's realm line up.

## Known Bugs (found by this suite — 9 failing tests on qa2/test02)

| ID | Description | Expected | Actual | Affected tests |
|---|---|---|---|---|
| BUG-R1 | Invalid field **type** in PUT body, or empty body, throws instead of validating | `400 VALIDATION_FAILED` | `500` (Jackson JSON parse error) | `test_string_max_retention_days_returns_400`, `test_string_modality_value_returns_400`, `test_non_boolean_auto_delete_returns_400`, `test_non_boolean_salt_logs_returns_400`, `test_empty_body_returns_400` |
| BUG-R2 | Omitting `saltLogsToRemovePii` (optional per spec) is rejected | `200` | `500` (JSON parse error) | `test_missing_salt_logs_flag_is_accepted` |
| BUG-R3 | Non-UUID `tenantId` path param not validated | `400` | `500` (Internal Server Error) | All 3 tests in `test_path_params.py` |
| BUG-R4 | `maxRetentionDays` > `Integer.MAX_VALUE` (2147483647) triggers Jackson numeric range error instead of 400 | `400 VALIDATION_FAILED` | `500` "JSON parse error: Numeric value (...) out of range of int" | `test_max_retention_days_int_max_plus_one_returns_400`, `test_max_retention_days_long_overflow_returns_400` |
| BUG-R5 | POST and DELETE return 500; unsupported methods must return 405 with `Allow` header (RFC 9110 §15.5.6) | `405 Method Not Allowed` + `Allow: GET, PUT` | `500` (HttpRequestMethodNotSupportedException unmapped) | `test_post_method_returns_405`, `test_delete_method_returns_405`, `test_post_response_includes_allow_header` |

**BUG-R1** is the highest-impact: any client sending a wrong-typed value gets an
opaque 500 instead of a field-level 400, and the documented `VALIDATION_FAILED`
error shape is never produced for type errors. **BUG-R2** needs a spec↔impl
decision: either the impl should accept the missing flag (200) or the spec should
mark it required (then a clean 400 is expected, still not 500).

## Error Codes

| Scenario | HTTP | `error` field |
|---|---|---|
| Required field missing / wrong type | 400 | `VALIDATION_FAILED` |
| Modality > category max, or category max > system ceiling | 400 | `SETTINGS_INVALID` |
| Unknown tenant | 404 | — |
| Invalid API key | 401 | — |
| AccountId mismatch | 403 | — |

## Spec notes

- **`saltLogsToRemovePii` is optional.** `DataRetentionPolicy.required` is
  `[templates, enrollmentImages, logs]` only — a PUT body without
  `saltLogsToRemovePii` is structurally valid (see
  `test_missing_salt_logs_flag_is_accepted`).
- **`systemMaxRetentionDays` is read-only.** Emitted on GET, ignored on PUT.
  Tests confirm a client-supplied value is not persisted.
- **`Error` requires `status` and `message`.** `timestamp`, `error`, and
  `fieldErrors` are optional; `fieldErrors` is omitted when null (present only
  on structural `VALIDATION_FAILED` errors).
