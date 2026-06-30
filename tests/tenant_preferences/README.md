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

## Structure

| File | Description |
|---|---|
| `tenantpref-internal.openapi.yaml` | Full OpenAPI 3.0.3 spec for this API |
| `conftest.py` | Fixtures: auth headers, tenant ID, URL builders |
| `test_preferences.py` | Generic preferences CRUD tests |
| `test_retention_accessors.py` | Per-category retention accessor tests |
| `test_security_accessors.py` | Security settings field accessor tests |

## Running

```bash
# All tenant preference tests
pytest tests/tenant_preferences/ -v

# Single file
pytest tests/tenant_preferences/test_preferences.py -v
```
