# Aware Face API — Test Suite

Automated pytest suite for the **Aware Face Liveness API v3.0.0**, covering:
- `POST /v3/face/checkLiveness`
- `POST /v3/face/compare`

Jira ticket: **AWRNSS-355** | Parent: **AWRNSS-341 Core APIs**

---

## Prerequisites

```
pip install -r requirements.txt
```

---

## Configuration

All settings are controlled via environment variables. Defaults point to QA1 with the `dantest01` tenant.

| Variable | Default | Description |
|----------|---------|-------------|
| `AWARE_BASE_URL` | `https://api.qa1.awareidentity.com` | API base URL |
| `AWARE_API_KEY` | *(set in conftest)* | `X-Aware-ApiKey` header |
| `AWARE_ACCOUNT_ID` | `0001` | `X-Aware-AccountId` header |
| `AWARE_LIVENESS_POLICY` | `Face Liveness` | Liveness policy name |
| `AWARE_COMPARE_POLICY` | `Face · 1:1 Verification` | Compare policy name |
| `AWARE_TEST_IMAGE_PATH` | *(set in conftest)* | Live face image (person A, photo 1) |
| `AWARE_SECOND_IMAGE_PATH` | *(set in conftest)* | Second photo of same person (person A, photo 2) |
| `AWARE_SPOOF_IMAGE_PATH` | *(set in conftest)* | Different person's photo (person B) |

---

## Running the tests

```powershell
# Full suite
python -m pytest tests/ -v

# Liveness only
python -m pytest tests/test_face_liveness.py -v

# Compare only
python -m pytest tests/test_face_compare.py -v

# Specific class
python -m pytest tests/test_face_liveness.py::TestCheckFaceLivenessBusinessLogic -v
```

---

## Test structure

### `test_face_liveness.py`

| Class | Description |
|-------|-------------|
| `TestCheckFaceLivenessHappyPath` | 200 response contract — required fields, enums, score ranges, timestamps |
| `TestCheckFaceLivenessBusinessLogic` | Biometric behavior — spoof detection, score direction, algorithm roles, transaction uniqueness |
| `TestCheckFaceLivenessValidation` | 400 errors — missing/invalid fields, empty arrays, wrong enums |
| `TestCheckFaceLivenessPolicyEdgeCases` | Policy name edge cases — special chars, very long strings |
| `TestCheckFaceLivenessSecurity` | Adversarial inputs — SQL injection, XSS in correlationID |
| `TestCheckFaceLivenessPolicy` | 404 / 409 policy errors — missing policy, multiple policies |
| `TestCheckFaceLivenessAuth` | Auth failures — invalid key, missing headers, wrong account |

### `test_face_compare.py`

| Class | Description |
|-------|-------------|
| `TestFaceCompareHappyPath` | 200 response contract — required fields, score, match, algorithms |
| `TestFaceCompareBusinessLogic` | Biometric behavior — same/different person, score direction, symmetry, transaction uniqueness |
| `TestFaceCompareValidation` | 400 errors — null/empty images, missing probe/candidate, bad base64 |
| `TestFaceComparePolicyEdgeCases` | Policy name edge cases — special chars, very long strings |
| `TestFaceCompareSecurity` | Adversarial inputs — SQL injection, XSS in correlationID |
| `TestFaceComparePolicy` | 404 / 409 policy errors |
| `TestFaceCompareAuth` | Auth failures — invalid key, missing headers, wrong account |

---

## Known failing tests (open bugs)

| Test | Expected | Actual | Jira |
|------|----------|--------|------|
| `test_invalid_base64_image_returns_400` | `400` | `200` — server processes invalid base64 | Open |
| `test_algorithm_score_threshold_when_present_is_numeric` | `number` | `"4"` (string) | Open |
| `test_missing_api_key_returns_401` | `401/403` | `500` | Open |
| `test_missing_account_id_returns_403` | `401/403` | `500` | Open |
| `test_wrong_account_id_returns_403` | `401/403` | `500` | Open |

---

## OpenAPI spec

`face.openapi 1.yaml` — Aware Face Liveness API v3.0.0
