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
| `test_get.py` | 18 | GET happy path, shape, data integrity, not-found |
| `test_update.py` | 39 | PUT happy path, server-managed fields, business rules, validation, atomicity, error shape, not-found |
| `test_path_params.py` | 3 | Non-UUID tenantId path parameter validation |
| `test_edge_cases.py` | 19 | Numeric overflow, unsupported HTTP methods, category/modality consistency, `autoDeleteExpired` ignored-on-input, boolean coercion, modality value/key validation |

**Total: 87 tests** — last run (qa2, test02, 2026-07-01): **84 passed, 3 known-bug failures.**

## Running

```bash
# All retention tests
pytest tests/retention/ -v

# Single file
pytest tests/retention/test_update.py -v
```

> There is currently no marker/keyword split between passing and known-bug tests
> (`-k "not BUG"` is a no-op — "BUG" only appears in docstrings, which `-k` does not
> match). The 3 known-bug tests are listed individually under **Known Bugs** below.

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

## Known Bugs (found by this suite — 3 failing tests on qa2/test02, as of 2026-07-01)

| ID | Description | Expected | Actual | Affected tests |
|---|---|---|---|---|
| BUG-R6 | `saltLogsToRemovePii` silently coerces non-boolean JSON tokens instead of rejecting them | `400 VALIDATION_FAILED` | `200` — `0`→false, `"false"`→false (Jackson lenient coercion) | `test_salt_logs_integer_returns_400`, `test_salt_logs_string_returns_400` |
| BUG-R7 | Modality value `null` is silently ignored instead of rejected | `400 VALIDATION_FAILED` | `200` — the field is left unchanged, no error | `test_modality_value_null_returns_400` |

Arbitrary non-boolean strings (e.g. `"nope"`) are already correctly rejected for
`saltLogsToRemovePii` (`test_non_boolean_salt_logs_returns_400` passes) — BUG-R6 is
specifically about the tokens Jackson coerces (`0`/`1`/`"true"`/`"false"`).

### Previously tracked bugs — now fixed (verified 2026-07-01, qa2/test02)

BUG-R1 through BUG-R5 (invalid field type / empty body → 500, non-UUID tenantId →
500, `maxRetentionDays` > INT_MAX → 500, unsupported HTTP methods → 500) have all
been fixed server-side and now return the correct 400/405. See
`tests/AWRNSS_RETEST_REPORT.md` for the full retest evidence and the corresponding
Jira tickets (AWRNSS-455/457/458/459).

Two other tests that were flagged as bugs turned out to be **incorrect test
assumptions**, not server bugs — see "Spec notes" below before trusting old
assumptions about `autoDeleteExpired` or `saltLogsToRemovePii`'s required-ness.

## Error Codes

| Scenario | HTTP | `error` field |
|---|---|---|
| Required field missing / wrong type | 400 | `VALIDATION_FAILED` |
| Modality > category max, or category max > system ceiling | 400 | `SETTINGS_INVALID` |
| Unknown tenant | 404 | — |
| Invalid API key | 401 | — |
| AccountId mismatch | 403 | — |

## Spec notes

- **`saltLogsToRemovePii` IS required.** `DataRetentionPolicy.required` is
  `[templates, enrollmentImages, logs, saltLogsToRemovePii]` — a PUT body
  without it correctly returns 400 (see `test_missing_salt_logs_flag_returns_400`).
  An earlier version of this README/suite claimed the field was optional; that
  was a misreading of the spec, not a server bug.
- **`autoDeleteExpired` is read-only and ignored on PUT input.** Per spec,
  auto-delete is always enforced and cannot be disabled — the field is emitted
  as `true` on GET (bulk endpoint) and any value sent for it on PUT is silently
  ignored (no error, no effect). Tests must not assert that toggling it persists,
  and must not require it to be present or well-typed in a PUT body. See
  `TestAutoDeleteExpiredIgnoredOnInput` in `test_edge_cases.py` and the
  corresponding tests in `test_update.py`.
- **`systemMaxRetentionDays` is read-only.** Emitted on GET, ignored on PUT.
  Tests confirm a client-supplied value is not persisted.
- **`Error` requires `status` and `message`.** `timestamp`, `error`, and
  `fieldErrors` are optional; `fieldErrors` is omitted when null (present only
  on structural `VALIDATION_FAILED` errors).
