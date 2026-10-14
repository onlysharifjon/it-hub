"""Release controls: public read, admin writes, legacy client gate, safe callbacks."""
import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text

from backend.models import AuditLog, UserRole
from .conftest import _create_user, _login


def _admin_headers(client, db):
    _create_user(db, "release_admin", "admin-test-password", UserRole.admin)
    return {"Authorization": f"Bearer {_login(client, 'release_admin', 'admin-test-password')}"}


def _payload(**changes):
    return {
        "maintenance_enabled": False,
        "maintenance_title": "Texnik xizmat davom etmoqda",
        "maintenance_message": "Ilova tez orada yana ishlaydi.",
        "min_supported_build": 1,
        "latest_build": 5,
        "app_store_url": "https://apps.apple.com/uz/app/minar-parents/id6820518218",
        **changes,
    }


def test_public_config_is_prelogin_and_not_cached(client):
    result = client.get("/parent/release-config")
    assert result.status_code == 200
    assert result.headers["cache-control"] == "no-store"
    assert result.json() == _payload(maintenance_message="Ilova ustida qisqa texnik ishlar olib borilmoqda. Birozdan so‘ng qayta urinib ko‘ring.")


def test_only_admin_can_change_config_and_change_is_audited(client, db):
    config = _payload(maintenance_enabled=True, maintenance_title="Bir soatlik texnik ko‘rik")
    assert client.get("/admin/parent-release-config").status_code == 401
    hunter = _create_user(db, "release_hunter", "hunter-test-password", UserRole.hunter)
    hunter_token = _login(client, hunter.username, "hunter-test-password")
    hunter_headers = {"Authorization": f"Bearer {hunter_token}"}
    assert client.get("/admin/parent-release-config", headers=hunter_headers).status_code == 403
    assert client.put("/admin/parent-release-config", headers=hunter_headers, json=config).status_code == 403

    admin_headers = _admin_headers(client, db)
    updated = client.put("/admin/parent-release-config", headers=admin_headers, json=config)
    assert updated.status_code == 200, updated.text
    assert updated.json()["maintenance_enabled"] is True
    assert updated.json()["updated_by_id"] is not None
    assert client.get("/parent/release-config").json()["maintenance_enabled"] is True
    assert db.query(AuditLog).filter(AuditLog.entity_type == "parent_release_config").count() == 1

    # Bir xil PUT qayta kelganda auditda sun'iy ikkinchi o'zgarish yozilmaydi.
    assert client.put("/admin/parent-release-config", headers=admin_headers, json=config).status_code == 200
    assert db.query(AuditLog).filter(AuditLog.entity_type == "parent_release_config").count() == 1


def test_validation_rejects_bad_build_and_non_apple_links(client, db):
    headers = _admin_headers(client, db)
    for bad in (
        _payload(min_supported_build=6, latest_build=5),
        _payload(min_supported_build=0),
        _payload(min_supported_build="6"),
        _payload(app_store_url="http://apps.apple.com/uz/app/id6820518218"),
        _payload(app_store_url="https://apps.apple.com.evil.example/uz/app/id6820518218"),
        _payload(app_store_url="https://apps.apple.com/uz/app/id123456789"),
        _payload(maintenance_title="   "),
    ):
        assert client.put("/admin/parent-release-config", headers=headers, json=bad).status_code == 422
    assert client.get("/parent/release-config").json()["min_supported_build"] == 1


def test_maintenance_stops_parent_and_legacy_otp_not_crm_or_callbacks(client, db):
    headers = _admin_headers(client, db)
    assert client.put("/admin/parent-release-config", headers=headers,
                      json=_payload(maintenance_enabled=True)).status_code == 200
    for path, method in (("/parent/auth/login", "post"), ("/parent/app-config", "get"),
                         ("/auth/phone/request-code", "post"), ("/auth/phone/resend-code", "post")):
        result = getattr(client, method)(path)
        assert result.status_code == 503, (path, result.text)
        assert result.json()["code"] == "maintenance"
        assert result.headers["cache-control"] == "no-store"
        assert result.headers["retry-after"] == "120"
        assert result.headers["x-request-id"] == result.json()["request_id"]

    assert client.get("/parent/release-config").status_code == 200
    assert client.get("/parent/privacy.html").status_code == 200
    assert client.delete("/parent/account").status_code == 401  # deletion stays available with auth
    assert client.get("/admin/parent-release-config", headers=headers).status_code == 200
    assert client.post("/payment-callbacks/payme", json={}).status_code != 503


def test_min_build_rejects_old_or_headerless_clients_before_maintenance(client, db):
    headers = _admin_headers(client, db)
    assert client.put("/admin/parent-release-config", headers=headers,
                      json=_payload(min_supported_build=6, latest_build=6, maintenance_enabled=True)).status_code == 200
    for client_headers in ({}, {"X-Minar-App-Build": "5"}, {"X-Minar-App-Build": "n/a"}):
        result = client.post("/parent/auth/login", headers=client_headers, json={})
        assert result.status_code == 426
        assert result.json()["code"] == "upgrade_required"
    # Build 6 endi maintenance xabarini ko'radi; 426 ustuvorligi tasdiqlandi.
    result = client.post("/parent/auth/login", headers={"X-Minar-App-Build": "6"}, json={})
    assert result.status_code == 503
    assert result.json()["code"] == "maintenance"


def test_migration_starts_with_access_open():
    migration_file = Path(__file__).parents[1] / "alembic/versions/20261013a_parent_release_config.py"
    spec = importlib.util.spec_from_file_location("parent_release_migration", migration_file)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        migration.op = Operations(MigrationContext.configure(connection))
        migration.upgrade()
        row = connection.execute(text(
            "SELECT maintenance_enabled, min_supported_build, latest_build, app_store_url "
            "FROM parent_release_config WHERE id = 1"
        )).one()
        assert bool(row.maintenance_enabled) is False
        assert row.min_supported_build == 1
        assert row.latest_build == 5
        assert row.app_store_url.endswith("/id6820518218")
        migration.downgrade()
        assert connection.execute(text(
            "SELECT name FROM sqlite_master WHERE name='parent_release_config'"
        )).first() is None
    engine.dispose()
