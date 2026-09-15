"""Export OpenAPI schema to openapi.yaml without requiring a live DB connection."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

from pg_gateway.config import Settings, load_config
from pg_gateway.main import create_app


def export_openapi(output: Path | None = None) -> Path:
    settings = Settings.from_env()
    config_path = Path(settings.config_path)
    if not config_path.exists():
        config_path = Path(__file__).resolve().parents[2] / "config" / "config.yaml"
    config = load_config(config_path)
    # Do not connect to DB for schema export
    app = create_app(config=config, settings=settings, connect_db=False)
    schema = app.openapi()
    # Ensure OpenAPI 3.1
    schema["openapi"] = "3.1.0"
    out = output or Path(__file__).resolve().parents[2] / "openapi.yaml"
    out.write_text(
        yaml.safe_dump(schema, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    # also write json sibling for convenience
    json_path = out.with_suffix(".json")
    json_path.write_text(json.dumps(schema, indent=2), encoding="utf-8")
    return out


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    path = export_openapi(out)
    print(f"Wrote {path}")


if __name__ == "__main__":
    main()
