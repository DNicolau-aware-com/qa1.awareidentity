import base64
import json
import os
from datetime import datetime, timezone

import pytest
import requests as _requests_module

BASE_URL = os.getenv("AWARE_BASE_URL", "https://api.qa1.awareidentity.com")
API_KEY = os.getenv("AWARE_API_KEY", "8012ca2705773d1077f2b74c148434b201179a1e5cb7431b44e89728ac39bc0f")
API_KEY_2 = os.getenv("AWARE_API_KEY_2", "f4847344231fd62e1858fc47b4297520b4c1d0d551671ff7fb29c37406c689e7")  # testtest1 tenant
ACCOUNT_ID = os.getenv("AWARE_ACCOUNT_ID", "0001")
LIVENESS_POLICY = os.getenv("AWARE_LIVENESS_POLICY", "Face Liveness")
COMPARE_POLICY = os.getenv("AWARE_COMPARE_POLICY", "Face · 1:1 Verification")
TEST_IMAGE_PATH = os.getenv("AWARE_TEST_IMAGE_PATH", "")
SPOOF_IMAGE_PATH = os.getenv("AWARE_SPOOF_IMAGE_PATH", "")
TENANT_ID = os.getenv("AWARE_TENANT_ID", "3d95a209-5011-446c-bf7f-34217e7a31f6")    # test01 (TENANT)
TENANT_ID_2 = os.getenv("AWARE_TENANT_ID_2", "efd53128-7c95-47c3-bf7b-2f86d00848f0")  # testtest1 (TENANT)
ACCOUNT_ID_2 = os.getenv("AWARE_ACCOUNT_ID_2", "0001")

# Minimal 1×1 gray-pixel JPEG — satisfies structural validation but is not a face.
# Only use this for tests that expect non-200 responses (validation/auth/policy errors).
_MINIMAL_JPEG_B64 = (
    "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkS"
    "Ew8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/wAARCAAB"
    "AAEDASIAAhEBAxEB/8QAFAABAAAAAAAAAAAAAAAAAAAACf/EABQQAQAAAAAAAAAAAA"
    "AAAAAAAD/xAAUAQEAAAAAAAAAAAAAAAAAAAAA/8QAFBEBAAAAAAAAAAAAAAAAAAAAAP/"
    "aAAwDAQACEQMRAD8AJQAB/9k="
)

# Session-level transaction log — populated by capture_transaction_ids fixture
_transaction_log = []


# ---------------------------------------------------------------------------
# Transaction ID capture — intercepts every requests.post call and logs
# the transactionID, test name, endpoint, decision and timestamp
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def capture_transaction_ids(request, monkeypatch):
    """Wrap requests.post to capture transactionID from every API response."""
    test_name = request.node.nodeid
    original_post = _requests_module.post

    def _intercepted(url, *args, **kwargs):
        response = original_post(url, *args, **kwargs)
        try:
            body = response.json()
            data = body.get("faceLiveness") or body.get("faceCompare") or {}
            tid = data.get("transactionID")
            if tid:
                decision = data.get("decision")
                if decision is None and "match" in data:
                    decision = f"match={data['match']}"
                _transaction_log.append({
                    "test":          test_name,
                    "transactionID": tid,
                    "endpoint":      url.split(".com")[-1],
                    "decision":      decision,
                    "score":         data.get("score"),
                    "timestamp":     datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                })
        except Exception:
            pass
        return response

    monkeypatch.setattr(_requests_module, "post", _intercepted)
    yield


@pytest.fixture(scope="session", autouse=True)
def write_transaction_log():
    """Write transaction_log.json at the end of the session."""
    yield
    if _transaction_log:
        log_path = os.path.join(os.path.dirname(__file__), "..", "transaction_log.json")
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(_transaction_log, f, indent=2, ensure_ascii=False)
        print(f"\nTransaction log saved -> transaction_log.json ({len(_transaction_log)} entries)")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def base_url():
    return BASE_URL


@pytest.fixture(scope="session")
def liveness_policy():
    return LIVENESS_POLICY


@pytest.fixture(scope="session")
def compare_policy():
    return COMPARE_POLICY


@pytest.fixture(scope="session")
def auth_headers():
    return {
        "X-Aware-ApiKey": API_KEY,
        "X-Aware-AccountId": ACCOUNT_ID,
        "Content-Type": "application/json",
    }


@pytest.fixture(scope="session")
def bad_auth_headers():
    return {
        "X-Aware-ApiKey": "0" * 64,
        "X-Aware-AccountId": ACCOUNT_ID,
        "Content-Type": "application/json",
    }


@pytest.fixture(scope="session")
def second_api_key():
    return API_KEY_2


@pytest.fixture(scope="session")
def minimal_image_b64():
    return _MINIMAL_JPEG_B64


@pytest.fixture(scope="session")
def tenant_id():
    if not TENANT_ID:
        pytest.skip("Set AWARE_TENANT_ID to a tenant UUID to run collections tests")
    return TENANT_ID


@pytest.fixture(scope="session")
def tenant_id_2():
    if not TENANT_ID_2:
        pytest.skip("Set AWARE_TENANT_ID_2 to a second tenant UUID to run isolation tests")
    return TENANT_ID_2


@pytest.fixture(scope="session")
def auth_headers_2():
    if not ACCOUNT_ID_2:
        pytest.skip("Set AWARE_ACCOUNT_ID_2 (and optionally AWARE_API_KEY_2) to run cross-tenant isolation tests")
    return {
        "X-Aware-ApiKey": API_KEY_2,
        "X-Aware-AccountId": ACCOUNT_ID_2,
        "Content-Type": "application/json",
    }


@pytest.fixture(scope="session")
def face_image_b64():
    if not TEST_IMAGE_PATH:
        pytest.skip("Set AWARE_TEST_IMAGE_PATH to a face photo to run happy-path tests")
    with open(TEST_IMAGE_PATH, "rb") as fh:
        return base64.b64encode(fh.read()).decode()


@pytest.fixture(scope="session")
def spoof_image_b64():
    if not SPOOF_IMAGE_PATH:
        pytest.skip("Set AWARE_SPOOF_IMAGE_PATH to a spoof image to run this test")
    with open(SPOOF_IMAGE_PATH, "rb") as fh:
        return base64.b64encode(fh.read()).decode()
