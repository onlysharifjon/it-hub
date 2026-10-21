"""A new Paycom sandbox cannot reuse CRM data or expose its test credential."""

import importlib.util
from pathlib import Path

import pytest


def test_provision_creates_private_sandbox_only(monkeypatch, tmp_path, capsys):
    script = Path(__file__).parents[2] / "deploy" / "provision_paycom_sandbox.py"
    spec = importlib.util.spec_from_file_location("paycom_provision", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    directory = tmp_path / "env"
    directory.mkdir(mode=0o700)
    monkeypatch.setattr(module, "ENV_PATH", directory / "paycom-sandbox.env")
    monkeypatch.setattr(module.os, "geteuid", lambda: 0)
    merchant = tmp_path / "merchant-id"
    key = tmp_path / "test-key"
    merchant.write_text("sandbox-merchant\n")
    key.write_text("sandbox%test&key\n")
    merchant.chmod(0o600)
    key.chmod(0o600)
    queries = []

    def fake_psql(_container, _user, sql):
        queries.append(sql)
        return "0|0" if sql.startswith("SELECT") else ""

    monkeypatch.setattr(module, "_psql", fake_psql)
    module.provision("postgres-container", "postgres", "db", merchant, key)

    env_text = module.ENV_PATH.read_text()
    assert module.ENV_PATH.stat().st_mode & 0o777 == 0o600
    assert "DATABASE_URL=postgresql://paycom_sandbox_role:" in env_text
    assert "@db:5432/paycom_sandbox" in env_text
    assert "PAYME_KEY=sandbox%test&key" in env_text
    assert "PAYCOM_SANDBOX_MODE=enabled" in env_text
    assert "PARENT_PAYMENTS_ENABLED=false" in env_text
    assert "CREATE ROLE paycom_sandbox_role" in queries[1]
    assert "CREATE DATABASE paycom_sandbox OWNER paycom_sandbox_role" in queries[2]
    assert "REVOKE CONNECT ON DATABASE paycom_sandbox FROM PUBLIC" in queries[3]
    assert "sandbox%test&key" not in capsys.readouterr().out

    with pytest.raises(module.ProvisionError, match="Refusing to overwrite"):
        module.provision("postgres-container", "postgres", "db", merchant, key)
