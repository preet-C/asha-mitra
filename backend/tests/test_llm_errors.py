import httpx
import pytest

from app.brain.llm import _post_with_retry


def test_provider_error_does_not_copy_response_body_or_api_key_into_message(monkeypatch):
    request = httpx.Request("POST", "https://example.test/?key=private-test-key")
    response = httpx.Response(
        401,
        text="provider response that must not be copied",
        request=request,
    )

    def fail_request(*_args, **_kwargs):
        raise httpx.HTTPStatusError("unauthorized", request=request, response=response)

    monkeypatch.setattr("app.brain.llm.httpx.post", fail_request)
    with pytest.raises(ValueError) as error:
        _post_with_retry("https://example.test/", {}, lambda value: value)

    message = str(error.value)
    assert "HTTP 401" in message
    assert "provider response" not in message
    assert "private-test-key" not in message
