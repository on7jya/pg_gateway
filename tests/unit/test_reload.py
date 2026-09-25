from __future__ import annotations

import os

import pytest
import yaml

from pg_gateway.config import Settings
from pg_gateway.config.reloader import ConfigReloader
from pg_gateway.main import create_app
from tests.conftest import CONFIG_PATH

TENANT_A = "11111111-1111-1111-1111-111111111111"
TENANT_B = "22222222-2222-2222-2222-222222222222"
DN_X = "CN=x,O=Acme,C=RU"
DN_Y = "CN=y,O=Acme,C=RU"


def _accounts_yaml(accounts: dict) -> str:
    return yaml.safe_dump({"accounts": accounts}, sort_keys=False)


def _one(dn: str, tenant: str) -> str:
    return _accounts_yaml({dn: {"tenant_id": tenant, "grants": {}}})


def _write(path, content: str, mtime: int) -> None:
    path.write_text(content, encoding="utf-8")
    os.utime(path, (mtime, mtime))


def test_poll_no_change_returns_false(tmp_path):
    accounts = tmp_path / "accounts.yaml"
    _write(accounts, _one(DN_X, TENANT_A), 1000)
    applied = []
    r = ConfigReloader(base_path=CONFIG_PATH, accounts_path=accounts, apply=applied.append)
    assert r.poll() is False
    assert applied == []


def test_poll_reloads_on_change(tmp_path):
    accounts = tmp_path / "accounts.yaml"
    _write(accounts, _one(DN_X, TENANT_A), 1000)
    applied = []
    r = ConfigReloader(base_path=CONFIG_PATH, accounts_path=accounts, apply=applied.append)
    _write(accounts, _one(DN_Y, TENANT_B), 2000)
    assert r.poll() is True
    assert len(applied) == 1
    assert DN_Y in applied[0].accounts


def test_poll_invalid_keeps_previous(tmp_path):
    accounts = tmp_path / "accounts.yaml"
    _write(accounts, _one(DN_X, TENANT_A), 1000)
    applied = []
    r = ConfigReloader(base_path=CONFIG_PATH, accounts_path=accounts, apply=applied.append)
    # Invalid: account missing tenant_id
    invalid = 'accounts:\n  "CN=x,O=Acme,C=RU":\n    grants: {}\n'
    _write(accounts, invalid, 2000)
    assert r.poll() is False
    assert applied == []


@pytest.mark.asyncio
async def test_app_hot_reload_updates_accounts(tmp_path):
    accounts = tmp_path / "accounts.yaml"
    _write(accounts, _one(DN_X, TENANT_A), 1000)

    settings = Settings(
        config_path=str(CONFIG_PATH),
        database_url="postgresql://x",
        accounts_config_path=str(accounts),
        reload_interval=3600,
    )
    app = create_app(settings=settings, connect_db=False)
    async with app.router.lifespan_context(app):
        assert app.state.account_tenants == {DN_X: TENANT_A}
        assert app.state.reloader is not None

        _write(accounts, _one(DN_Y, TENANT_B), 2000)

        assert app.state.reloader.poll() is True
        assert app.state.account_tenants == {DN_Y: TENANT_B}
        assert DN_Y in app.state.config.accounts
        assert DN_X not in app.state.config.accounts
