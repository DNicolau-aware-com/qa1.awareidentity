import base64
import json
import os
from datetime import datetime, timezone

import pytest
import requests as _requests_module

BASE_URL = os.getenv("AWARE_BASE_URL", "https://api.qa2.awareidentity.com")
API_KEY = os.getenv("AWARE_API_KEY", "b6b951000c48039fba9f48246c66fd075b5bc2951c78a9c8e88103424c119117")
API_KEY_2 = os.getenv("AWARE_API_KEY_2", "9977e1c12a625f536e2cae3da4678ae99b6d837a0f93ea34deffcc4463fad6fb")  # test02 tenant
ACCOUNT_ID = os.getenv("AWARE_ACCOUNT_ID", "0001")
LIVENESS_POLICY = os.getenv("AWARE_LIVENESS_POLICY", "Face Liveness")
COMPARE_POLICY = os.getenv("AWARE_COMPARE_POLICY", "Face · 1:1 Verification")
TEST_IMAGE_PATH = os.getenv("AWARE_TEST_IMAGE_PATH", "")
SPOOF_IMAGE_PATH = os.getenv("AWARE_SPOOF_IMAGE_PATH", "")
TENANT_ID = os.getenv("AWARE_TENANT_ID", "b3b8c292-2305-4e06-85c6-71fbb0519255")    # test01 (TENANT)
TENANT_ID_2 = os.getenv("AWARE_TENANT_ID_2", "57bf3cfb-09c7-4dc5-8d33-68423e269bba")  # test02 (TENANT)
ACCOUNT_ID_2 = os.getenv("AWARE_ACCOUNT_ID_2", "0001")

# ---------------------------------------------------------------------------
# Keycloak/OIDC bearer token for endpoints behind the Istio JWT filter
# (data-retention-policy, security-settings).
#
# Three ways to supply it, checked in order:
#   1. A ready token  — env AWARE_BEARER_TOKEN, or a gitignored tests/.bearer_token file.
#   2. User creds      — env AWARE_USERNAME + AWARE_PASSWORD (password grant).
#   3. A creds file    — gitignored tests/.keycloak_creds with KEY=VALUE lines:
#                          USERNAME=...  PASSWORD=...  (optional CLIENT_ID, CLIENT_SECRET)
#
# Nothing has to be pasted into a chat transcript — create the files yourself.
# ---------------------------------------------------------------------------
_TOKEN_FILE = os.path.join(os.path.dirname(__file__), ".bearer_token")
_CREDS_FILE = os.path.join(os.path.dirname(__file__), ".keycloak_creds")

KEYCLOAK_URL = os.getenv("AWARE_KEYCLOAK_URL", "https://auth.qa2.awareidentity.com")
KEYCLOAK_REALM = os.getenv("AWARE_KEYCLOAK_REALM", "test02")
KEYCLOAK_CLIENT_ID = os.getenv("AWARE_KEYCLOAK_CLIENT_ID", "awareness-portal-service")
KEYCLOAK_CLIENT_SECRET = os.getenv("AWARE_KEYCLOAK_CLIENT_SECRET", "")
AWARE_USERNAME = os.getenv("AWARE_USERNAME", "")
AWARE_PASSWORD = os.getenv("AWARE_PASSWORD", "")


def _read_creds_file():
    """Parse tests/.keycloak_creds (KEY=VALUE lines) into a dict; {} if absent."""
    if not os.path.exists(_CREDS_FILE):
        return {}
    creds = {}
    with open(_CREDS_FILE, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            creds[k.strip().upper()] = v.strip()
    return creds


def _static_bearer_token():
    tok = os.getenv("AWARE_BEARER_TOKEN", "").strip()
    if tok:
        return tok
    if os.path.exists(_TOKEN_FILE):
        with open(_TOKEN_FILE, "r", encoding="utf-8") as fh:
            return fh.read().strip()
    return ""


def _fetch_bearer_token():
    """Return a valid Keycloak access token for the current session.

    Priority:
      1. If credentials are available (env vars or .keycloak_creds), always mint
         a fresh token so expired-token failures never happen mid-suite.
      2. If only a static token is available (AWARE_BEARER_TOKEN / .bearer_token),
         use it as-is — the caller will skip/fail if it turns out to be expired.
    """
    creds = _read_creds_file()
    username = AWARE_USERNAME or creds.get("USERNAME", "")
    password = AWARE_PASSWORD or creds.get("PASSWORD", "")
    client_secret = creds.get("CLIENT_SECRET", KEYCLOAK_CLIENT_SECRET)

    if (username and password) or client_secret:
        client_id = creds.get("CLIENT_ID", KEYCLOAK_CLIENT_ID)
        realm = creds.get("REALM", KEYCLOAK_REALM)
        url = f"{KEYCLOAK_URL}/realms/{realm}/protocol/openid-connect/token"

        if username and password:
            data = {
                "grant_type": "password",
                "client_id": client_id,
                "username": username,
                "password": password,
                "scope": "openid",
            }
            if client_secret:
                data["client_secret"] = client_secret
        else:
            data = {
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
            }

        resp = _requests_module.post(url, data=data, timeout=20)
        if resp.status_code != 200:
            raise RuntimeError(
                f"Keycloak token request failed ({resp.status_code}): {resp.text[:300]}"
            )
        return resp.json()["access_token"]

    # No credentials — fall back to a static token (env var or .bearer_token file).
    return _static_bearer_token()

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
def mismatched_account_headers():
    """Valid API key paired with an AccountId that does not belong to it → 403."""
    return {
        "X-Aware-ApiKey": API_KEY,
        "X-Aware-AccountId": "9999",
        "Content-Type": "application/json",
    }


@pytest.fixture(scope="session")
def second_api_key():
    return API_KEY_2


@pytest.fixture(scope="session")
def bearer_token():
    """Keycloak/OIDC bearer token for JWT-gated endpoints, minted once per session.

    Resolves a ready token (AWARE_BEARER_TOKEN / tests/.bearer_token) or, failing
    that, performs a Keycloak password grant from AWARE_USERNAME+AWARE_PASSWORD or
    tests/.keycloak_creds. Skips the test if no credentials are configured."""
    token = _fetch_bearer_token()
    if not token:
        pytest.skip(
            "No bearer token/credentials. Provide one of: AWARE_BEARER_TOKEN, "
            "tests/.bearer_token, AWARE_USERNAME+AWARE_PASSWORD, or tests/.keycloak_creds "
            "to run JWT-gated endpoints (data-retention-policy, security-settings)."
        )
    return token


@pytest.fixture(scope="session")
def bearer_headers(bearer_token):
    """Authorization: Bearer headers for endpoints behind the Istio JWT filter."""
    return {
        "Authorization": f"Bearer {bearer_token}",
        "Content-Type": "application/json",
    }


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
