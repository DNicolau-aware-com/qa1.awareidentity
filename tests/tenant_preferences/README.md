# Tenant Preferences API Tests (Internal)

Integration tests for the **Aware Tenant Service — Tenant Preferences API (Internal)**.

**Spec:** `tenantpref-internal.openapi.yaml`

> These endpoints are **internal to tenant-service** — not proxied by the
> awareness-portal BFF and not reachable by the portal frontend. Auth is
> API-key only (`X-Aware-ApiKey` + `X-Aware-AccountId`); no Keycloak bearer
> JWT required (unlike the external retention/security-settings endpoints).

---

## Endpoint groups

### Generic preferences — low-level CRUD over `tenant_pref` table

| Method | Path | Description |
|---|---|---|
| GET | `/v3/tenants/{tenantId}/preferences` | List all preference rows |
| GET | `/v3/tenants/{tenantId}/preferences/{key}` | List all rows in a settings group |
| PUT | `/v3/tenants/{tenantId}/preferences/{key}` | Bulk upsert a whole group |
| GET | `/v3/tenants/{tenantId}/preferences/{key}/{subKey}` | Get one preference row |
| POST | `/v3/tenants/{tenantId}/preferences/{key}/{subKey}` | Create one row (409 if exists) |
| PUT | `/v3/tenants/{tenantId}/preferences/{key}/{subKey}` | Upsert one row |
| DELETE | `/v3/tenants/{tenantId}/preferences/{key}/{subKey}` | Delete one row |

### Data retention — individual category accessors

| Method | Path | Description |
|---|---|---|
| GET/PUT | `/v3/tenants/{tenantId}/data-retention-policy/templates` | Templates category |
| GET/PUT | `/v3/tenants/{tenantId}/data-retention-policy/enrollmentImages` | Enrollment images category |
| GET/PUT | `/v3/tenants/{tenantId}/data-retention-policy/logs` | Transaction logs category |
| GET/PUT | `/v3/tenants/{tenantId}/data-retention-policy/saltLogsToRemovePii` | PII salt flag |

### Security settings — individual field accessors

| Method | Path | Description |
|---|---|---|
| GET/PUT | `/v3/tenants/{tenantId}/security-settings/session_timeout_minutes` | Session timeout |
| GET/PUT | `/v3/tenants/{tenantId}/security-settings/password_reset_link_lifetime` | Password reset link lifetime |

### Security settings — bulk (external)

| Method | Path | Description |
|---|---|---|
| GET/PUT | `/v3/tenants/{tenantId}/security-settings` | Both fields together |

> This endpoint is part of the **external** API (`tenantpref-external.openapi.yaml`,
> proxied by the awareness-portal BFF), unlike everything else in this directory.
> It's tested here (`test_security_settings_bulk.py`) rather than in its own
> directory because it shares the test02 tenant/auth fixtures already set up in
> this `conftest.py` — mirrors how `tests/retention/` covers the external bulk
> `data-retention-policy` endpoint on its own.

---

## Key concepts

- Each preference row holds **one value** addressed by `(key, subKey)`.
  A settings group is all rows sharing the same `key`.
- `value` is always stored as **text** (`STRING`); `valueType` (`STRING`,
  `INTEGER`, `BOOLEAN`, `JSON`) tells consumers how to interpret it.
- **Presence invariant**: every typed-layer field is seeded at tenant
  creation. A missing row is an integrity error (500), not a 404 with a
  default — this is by design.
- `POST` creates and returns **409** if the `(key, subKey)` already exists.
  `PUT` on a subKey is an upsert (create-or-update, always 200/201).

## Error codes

| Code | HTTP | When |
|---|---|---|
| `VALIDATION_FAILED` | 400 | Missing/invalid request fields |
| `SETTINGS_INVALID` | 400 | Business rule failed (modality > category max, etc.) |
| `NOT_FOUND` | 404 | Preference row not found |
| `CONFLICT` | 409 | subKey already exists (POST only) |

## Known Bugs

| ID | Description | Expected | Actual | Affected tests |
|---|---|---|---|---|
| BUG-S1 | `session_timeout_minutes` and `password_reset_link_lifetime` **individual accessors** silently coerce numeric strings and decimals instead of rejecting them | `400 VALIDATION_FAILED` | `200` — `"30"`→30, `30.5`→30. The **bulk** `security-settings` endpoint gets this right (400) for the same inputs. | `TestAccessorTypeCoercion::test_numeric_string_returns_400`, `::test_decimal_returns_400` (both fields) in `test_security_accessors.py` |
| — | `saltLogsToRemovePii` silently coerces non-boolean JSON tokens (`0`/`1`/`"true"`/`"false"`) | `400 VALIDATION_FAILED` | `200` | `test_retention_accessors.py::TestSaltLogsAccessor::test_put_salt_logs_non_boolean_returns_400` — see `tests/retention/README.md` BUG-R6 (same root cause, also present on the bulk endpoint) |
| — | Individual retention-category accessor `GET` returns `autoDeleteExpired: null` instead of `true` | `true` | `null` | `test_retention_accessors.py::TestGetRetentionCategory::test_auto_delete_expired_is_boolean` |
| AWRNSS-467 | `POST /preferences/{key}/{subKey}` accepts unbounded value length | `400` past some max | `201` at 5k/50k/1M chars | `test_preferences.py::TestValueValidation::test_oversized_value_returns_400` |

Full evidence and Jira ticket cross-reference for all of these: `tests/AWRNSS_RETEST_REPORT.md`.
Full test-case list and results for the security-settings suites specifically:
`SECURITY_SETTINGS_REPORT.md`.

## Structure

| File | Description |
|---|---|
| `tenantpref-internal.openapi.yaml` | Full OpenAPI 3.0.3 spec for this API |
| `conftest.py` | Fixtures: auth headers, tenant ID, URL builders |
| `test_preferences.py` | Generic preferences CRUD tests |
| `test_retention_accessors.py` | Per-category retention accessor tests |
| `test_security_accessors.py` | Security settings field accessor tests |
| `test_security_settings_bulk.py` | Bulk security-settings (external) tests — both fields together |

## Running

```bash
# All tenant preference tests
pytest tests/tenant_preferences/ -v

# Single file
pytest tests/tenant_preferences/test_preferences.py -v
```
