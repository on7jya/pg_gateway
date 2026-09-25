from __future__ import annotations

import yaml

from pg_gateway.export_openapi import export_openapi
from tests.conftest import ACCOUNTS_PATH, CONFIG_PATH


def test_export_openapi_writes_yaml_and_json(tmp_path, monkeypatch):
    monkeypatch.setenv("CONFIG_PATH", str(CONFIG_PATH))
    monkeypatch.setenv("ACCOUNTS_CONFIG_PATH", str(ACCOUNTS_PATH))
    out = tmp_path / "openapi.yaml"

    path = export_openapi(out)

    assert path == out
    assert out.exists()
    json_path = out.with_suffix(".json")
    assert json_path.exists()

    schema = yaml.safe_load(out.read_text())
    assert schema["openapi"] == "3.1.0"
    assert "/api/v1/users" in schema["paths"]
    assert "ClientCertDN" in schema["components"]["securitySchemes"]
