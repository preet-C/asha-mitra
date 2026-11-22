"""Small CORS setup for the hosted frontend/backend split."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


def _parse_origins(origins: str) -> list[str]:
    return [
        origin.strip().rstrip("/")
        for origin in origins.split(",")
        if origin.strip()
    ]


def configure_cors(app: FastAPI, origins: str) -> None:
    """Allow browser API calls only from explicitly listed frontend origins."""
    allowed_origins = _parse_origins(origins)
    if not allowed_origins:
        return

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_methods=["GET"],
        allow_headers=["*"],
        allow_credentials=False,
    )


def is_origin_allowed(origins: str, origin: str | None) -> bool:
    """Check browser WebSocket origins against the same production allowlist."""
    allowed_origins = _parse_origins(origins)
    if not allowed_origins:
        return True
    return bool(origin and origin.rstrip("/") in allowed_origins)
