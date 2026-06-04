import base64
import os

import pytest

BASE_URL = os.getenv("AWARE_BASE_URL", "https://api.qa1.awareidentity.com")
API_KEY = os.getenv("AWARE_API_KEY", "")
ACCOUNT_ID = os.getenv("AWARE_ACCOUNT_ID", "0001")
LIVENESS_POLICY = os.getenv("AWARE_LIVENESS_POLICY", "Face Liveness")
COMPARE_POLICY = os.getenv("AWARE_COMPARE_POLICY", "Face · 1:1 Verification")
TEST_IMAGE_PATH = os.getenv("AWARE_TEST_IMAGE_PATH", "")
SECOND_IMAGE_PATH = os.getenv("AWARE_SECOND_IMAGE_PATH", "")
SPOOF_IMAGE_PATH = os.getenv("AWARE_SPOOF_IMAGE_PATH", "")

# Minimal 1×1 gray-pixel JPEG — satisfies structural validation but is not a face.
# Only use this for tests that expect non-200 responses (validation/auth/policy errors).
_MINIMAL_JPEG_B64 = (
    "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkS"
    "Ew8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/wAARCAAB"
    "AAEDASIAAhEBAxEB/8QAFAABAAAAAAAAAAAAAAAAAAAACf/EABQQAQAAAAAAAAAAAA"
    "AAAAAAAD/xAAUAQEAAAAAAAAAAAAAAAAAAAAA/8QAFBEBAAAAAAAAAAAAAAAAAAAAAP/"
    "aAAwDAQACEQMRAD8AJQAB/9k="
)


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
def minimal_image_b64():
    return _MINIMAL_JPEG_B64


@pytest.fixture(scope="session")
def face_image_b64():
    if not TEST_IMAGE_PATH:
        pytest.skip("Set AWARE_TEST_IMAGE_PATH to a face photo to run happy-path tests")
    with open(TEST_IMAGE_PATH, "rb") as fh:
        return base64.b64encode(fh.read()).decode()


@pytest.fixture(scope="session")
def second_image_b64():
    if not SECOND_IMAGE_PATH:
        pytest.skip("Set AWARE_SECOND_IMAGE_PATH to a second face photo to run this test")
    with open(SECOND_IMAGE_PATH, "rb") as fh:
        return base64.b64encode(fh.read()).decode()


@pytest.fixture(scope="session")
def spoof_image_b64():
    if not SPOOF_IMAGE_PATH:
        pytest.skip("Set AWARE_SPOOF_IMAGE_PATH to a spoof image to run this test")
    with open(SPOOF_IMAGE_PATH, "rb") as fh:
        return base64.b64encode(fh.read()).decode()
