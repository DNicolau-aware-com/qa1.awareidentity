"""
Tests for invalid request body and Content-Type on POST and PATCH endpoints.

Known bug [BUG-7]: Malformed JSON, wrong Content-Type, and empty raw body
return 500 instead of 400/415. Spring exceptions HttpMessageNotReadableException
and HttpMediaTypeNotSupportedException have no registered @ExceptionHandler.
Tests marked [BUG-7] MUST FAIL until the bug is resolved.
"""

import uuid
import requests

from tests.collections.conftest import collection_url, create_payload

_FAKE_ID = str(uuid.uuid4())


class TestPostRequestBody:

    def test_null_envelope_returns_400(self, base_url, auth_headers, tenant_id):
        """POST with biometricCollection: null returns 400 VALIDATION_FAILED (working correctly)."""
        resp = requests.post(collection_url(base_url, tenant_id),
                             json={"biometricCollection": None},
                             headers=auth_headers)
        assert resp.status_code == 400

    def test_malformed_json_returns_400(self, base_url, auth_headers, tenant_id):
        """[BUG-7] POST with malformed JSON must return 400.
        Currently returns 500: HttpMessageNotReadableException is unhandled."""
        resp = requests.post(collection_url(base_url, tenant_id),
                             data="{not valid json",
                             headers=auth_headers)
        assert resp.status_code == 400

    def test_text_plain_content_type_returns_415(self, base_url, auth_headers, tenant_id):
        """[BUG-7] POST with Content-Type text/plain must return 415 Unsupported Media Type.
        Currently returns 500: HttpMediaTypeNotSupportedException is unhandled."""
        headers = {**auth_headers, "Content-Type": "text/plain"}
        resp = requests.post(collection_url(base_url, tenant_id),
                             data="some text",
                             headers=headers)
        assert resp.status_code == 415

    def test_empty_raw_body_returns_400(self, base_url, auth_headers, tenant_id):
        """[BUG-7] POST with an empty raw body must return 400.
        Currently returns 500: HttpMessageNotReadableException is unhandled."""
        resp = requests.post(collection_url(base_url, tenant_id),
                             data="",
                             headers=auth_headers)
        assert resp.status_code == 400


class TestPatchRequestBody:

    def test_null_envelope_returns_400(self, base_url, auth_headers, tenant_id):
        """PATCH with biometricCollection: null returns 400 VALIDATION_FAILED (working correctly)."""
        resp = requests.patch(collection_url(base_url, tenant_id, _FAKE_ID),
                              json={"biometricCollection": None},
                              headers=auth_headers)
        assert resp.status_code == 400

    def test_malformed_json_returns_400(self, base_url, auth_headers, tenant_id):
        """[BUG-7] PATCH with malformed JSON must return 400.
        Currently returns 500: HttpMessageNotReadableException is unhandled."""
        resp = requests.patch(collection_url(base_url, tenant_id, _FAKE_ID),
                              data="{not valid json",
                              headers=auth_headers)
        assert resp.status_code == 400

    def test_text_plain_content_type_returns_415(self, base_url, auth_headers, tenant_id):
        """[BUG-7] PATCH with Content-Type text/plain must return 415 Unsupported Media Type.
        Currently returns 500: HttpMediaTypeNotSupportedException is unhandled."""
        headers = {**auth_headers, "Content-Type": "text/plain"}
        resp = requests.patch(collection_url(base_url, tenant_id, _FAKE_ID),
                              data="some text",
                              headers=headers)
        assert resp.status_code == 415

    def test_empty_raw_body_returns_400(self, base_url, auth_headers, tenant_id):
        """[BUG-7] PATCH with an empty raw body must return 400.
        Currently returns 500: HttpMessageNotReadableException is unhandled."""
        resp = requests.patch(collection_url(base_url, tenant_id, _FAKE_ID),
                              data="",
                              headers=auth_headers)
        assert resp.status_code == 400
