"""Unit tests for FastAPI server configuration, loopback enforcement, and health endpoint."""

import pytest
from fastapi.testclient import TestClient

from magang_log.server.app import create_app
from magang_log.server.config import ServerConfig


def test_server_config_defaults() -> None:
    config = ServerConfig()
    assert config.host == "127.0.0.1"
    assert config.port == 8000


def test_server_config_allows_loopback() -> None:
    cfg1 = ServerConfig(host="127.0.0.1", port=8080)
    assert cfg1.host == "127.0.0.1"
    assert cfg1.port == 8080

    cfg2 = ServerConfig(host="localhost", port=9000)
    assert cfg2.host == "localhost"


def test_server_config_rejects_non_loopback() -> None:
    non_loopback_hosts = [
        "0.0.0.0",
        "192.168.1.50",
        "10.0.0.1",
        "example.com",
        "172.16.0.1",
    ]
    for host in non_loopback_hosts:
        with pytest.raises(ValueError, match="loopback"):
            ServerConfig(host=host)


def test_create_app_openapi_docs_enabled() -> None:
    app = create_app()
    assert app.docs_url == "/docs"
    assert app.redoc_url == "/redoc"


def test_api_health_endpoint() -> None:
    app = create_app()
    client = TestClient(app)
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_openapi_spec_includes_health_route() -> None:
    app = create_app()
    client = TestClient(app)
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert "/api/health" in schema["paths"]
