from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.cors import configure_cors, is_origin_allowed


def test_cors_allows_only_configured_frontend_origins():
    app = FastAPI()
    configure_cors(app, "https://asha-demo.pages.dev, https://preview.pages.dev/")

    @app.get("/api/health")
    def health():
        return {"ok": True}

    client = TestClient(app)
    allowed = client.get("/api/health", headers={"Origin": "https://asha-demo.pages.dev"})
    denied = client.get("/api/health", headers={"Origin": "https://untrusted.example"})

    assert allowed.headers["access-control-allow-origin"] == "https://asha-demo.pages.dev"
    assert "access-control-allow-origin" not in denied.headers


def test_websocket_origin_uses_the_same_allowlist():
    allowed = "https://asha-demo.pages.dev, https://preview.pages.dev/"

    assert is_origin_allowed(allowed, "https://asha-demo.pages.dev")
    assert is_origin_allowed(allowed, "https://preview.pages.dev/")
    assert not is_origin_allowed(allowed, "https://untrusted.example")
    assert not is_origin_allowed(allowed, None)
    assert is_origin_allowed("", None)
