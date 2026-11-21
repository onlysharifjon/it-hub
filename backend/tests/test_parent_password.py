"""Ota-ona parol bilan kirishi (iOS: +998XXXXXXXXX + parol) — admin create/reset, o'zi almashtirish,
sessiyalarni bekor qilish, review akkaunti migratsiyasi, OTP endpointlari saqlanganligi.

Hech qanday tashqi xizmatga murojaat yo'q: Telegram Gateway chaqirilmaydi, baza — conftest'dagi vaqtinchalik.
"""
from datetime import datetime, timedelta

import pytest
from jose import jwt

from backend import security
from backend.models import AuditLog, Parent, ParentChild, ParentRefreshToken, Student, UserRole
from .conftest import _create_user

PHONE = "+998901112233"
OLD = "Old-parent-pass-2026"
NEW = "Yangi-Parol-Juda-Uzun-77"


@pytest.fixture
def hunter_user(db):
    return _create_user(db, "hunter", "hunter123", UserRole.hunter)


def _staff(client):
    t = client.post("/auth/login", json={"username": "hunter", "password": "hunter123"}).json()["access_token"]
    return {"Authorization": f"Bearer {t}"}


def _mk_student(db, name="Alibek", phone="+998900000001"):
    s = Student(full_name=name, phone1=phone, is_active=True, created_at=datetime.utcnow())
    db.add(s); db.commit(); db.refresh(s)
    return s


def _mk_parent(db, phone=PHONE, password=OLD, username=None, children=()):
    p = Parent(full_name="Nodira", phone=phone, username=username or phone,
               hashed_password=security.hash_password(password), is_active=True, created_at=datetime.utcnow())
    db.add(p); db.flush()
    for c in children:
        db.add(ParentChild(parent_id=p.id, student_id=c.id))
    db.commit(); db.refresh(p)
    return p


def _login(client, username=PHONE, password=OLD):
    return client.post("/parent/auth/login", json={"username": username, "password": password})


def _bearer(tokens):
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def _change(client, h, current=OLD, new=NEW, **extra):
    return client.post("/parent/auth/change-password", headers=h,
                       json={"current_password": current, "new_password": new, **extra})


# ── Parol siyosati / generator ──────────────────────────────────────────────

def test_generated_password_is_strong_and_random():
    pw = {security.generate_parent_password() for _ in range(50)}
    assert len(pw) == 50
    for p in pw:
        assert len(p) == 20 and security.parent_password_problem(p) is None
        assert not set(p) & set("0O1lI")


@pytest.mark.parametrize("pw,ok", [
    ("a" * 14, False), ("abcde" * 3, True), ("x" * 15, False),          # 1 xil belgi — oddiy
    ("Abc1-" * 14 + "zz", True), ("Abc1-" * 14 + "zzz", False),          # 72 bayt — ruxsat, 73 — yo'q
    ("Пароль-кириллица-ok", True), ("Ж" * 20 + "abcde" * 7, False),      # baytlar hisoblanadi (Ж = 2 bayt)
    ("P@ss-word-64-chars-" * 3 + "abcdefg", True),                       # 64 belgi
    (" leading-space-pass", False), ("trailing-space-pass ", False),
    ("ctrl\x00char-password", False),
])
def test_password_policy(pw, ok):
    assert (security.parent_password_problem(pw) is None) is ok


# ── Admin: yaratish / reset ─────────────────────────────────────────────────

def test_admin_create_generates_name_last4_password_once(client, db, hunter_user):
    s = _mk_student(db)
    r = client.post("/parents", headers=_staff(client),
                    json={"full_name": "Nodira", "phone": "90 111 22 33", "student_ids": [s.id]})
    assert r.status_code == 201, r.text
    assert r.headers.get("cache-control") == "no-store"
    body = r.json()
    pw = body["generated_password"]
    assert pw == "Nodira2233"                       # ism + telefonning oxirgi 4 raqami
    # Telefon E.164 ko'rinishida saqlanadi — iOS aynan shuni yuboradi
    assert body["phone"] == PHONE and body["username"] == PHONE
    p = db.query(Parent).filter_by(id=body["id"]).one()
    assert p.hashed_password != pw and security.verify_password(pw, p.hashed_password)
    # Parol keyin hech qayerda ko'rinmaydi
    listing = client.get("/parents", headers=_staff(client))
    assert pw not in listing.text and "generated_password" not in listing.text
    assert _login(client, PHONE, pw).status_code == 200


def test_admin_password_policy_on_create_and_reset(client, db, hunter_user):
    h = _staff(client)
    # CRM API shartnomasi o'zgarmagan: qo'lda parol 6..128 belgi
    short = client.post("/parents", headers=h, json={"full_name": "A B", "phone": PHONE, "password": "12345"})
    assert short.status_code == 422
    too_long = client.post("/parents", headers=h, json={"full_name": "A B", "phone": PHONE, "password": "x" * 129})
    assert too_long.status_code == 422
    ok = client.post("/parents", headers=h, json={"full_name": "A B", "phone": PHONE, "password": "abc123"})
    assert ok.status_code == 201 and ok.json()["generated_password"] == "abc123"
    pid = ok.json()["id"]
    assert client.post(f"/parents/{pid}/reset-password", headers=h, json={"password": "12345"}).status_code == 422
    long64 = "Uzun-va-esda-qoladigan-parol-ibora-" + "x" * 29
    assert len(long64) == 64
    r = client.post(f"/parents/{pid}/reset-password", headers=h, json={"password": long64})
    assert r.status_code == 200 and r.headers.get("cache-control") == "no-store"
    assert _login(client, PHONE, long64).status_code == 200


def test_admin_gives_password_to_otp_created_parent(client, db, hunter_user):
    # Telegram OTP orqali yaratilgan ota-ona: tasodifiy (noma'lum) parol, login = telefon
    otp_parent = _mk_parent(db, password=security.generate_parent_password(40))
    h = _staff(client)
    dup = client.post("/parents", headers=h, json={"full_name": "Nodira", "phone": "+998 90 111-22-33"})
    assert dup.status_code == 409 and f"ID {otp_parent.id}" in dup.json()["detail"]
    assert db.query(Parent).count() == 1                                   # dublikat yaratilmadi

    r = client.post(f"/parents/{otp_parent.id}/reset-password", headers=h, json={})
    assert r.status_code == 200
    pw = r.json()["generated_password"]
    assert pw == "Nodira2233"
    assert _login(client, PHONE, pw).status_code == 200
    audit = db.query(AuditLog).filter_by(entity_type="parent", entity_id=otp_parent.id, action="reset_password").one()
    assert pw not in (audit.new_value or "") and pw not in (audit.old_value or "")


def test_admin_reset_revokes_every_session_immediately(client, db, hunter_user):
    p = _mk_parent(db)
    phone_a, phone_b = _login(client).json(), _login(client).json()
    r = client.post(f"/parents/{p.id}/reset-password", headers=_staff(client), json={})
    new_pw = r.json()["generated_password"]
    for dev in (phone_a, phone_b):
        assert client.get("/parent/profile", headers=_bearer(dev)).status_code == 401      # access ham
        ref = client.post("/parent/auth/refresh", json={"refresh_token": dev["refresh_token"]})
        assert ref.status_code == 401 and ref.json()["code"] == "invalid_token"
    assert _login(client).status_code == 401
    fresh = _login(client, password=new_pw)
    assert fresh.status_code == 200
    assert client.get("/parent/profile", headers=_bearer(fresh.json())).status_code == 200


# ── Ota-ona o'zi almashtiradi ───────────────────────────────────────────────

def test_change_password_success_rotates_sessions(client, db):
    p = _mk_parent(db)
    this_dev, other_dev = _login(client).json(), _login(client).json()
    r = _change(client, _bearer(this_dev))
    assert r.status_code == 200, r.text
    assert set(r.json()) == {"access_token", "refresh_token"}
    assert r.headers.get("cache-control") == "no-store"
    new_tokens = r.json()

    assert client.get("/parent/profile", headers=_bearer(this_dev)).status_code == 401
    assert client.get("/parent/profile", headers=_bearer(other_dev)).status_code == 401
    assert client.post("/parent/auth/refresh", json={"refresh_token": other_dev["refresh_token"]}).status_code == 401
    assert client.get("/parent/profile", headers=_bearer(new_tokens)).status_code == 200
    # Boshqa qurilmaning eski refresh'i yangi sessiyani "token_reuse" bilan o'ldirmaydi
    ref = client.post("/parent/auth/refresh", json={"refresh_token": new_tokens["refresh_token"]})
    assert ref.status_code == 200

    assert _login(client).status_code == 401
    assert _login(client, password=NEW).status_code == 200
    db.expire_all()
    assert security.verify_password(NEW, db.query(Parent).filter_by(id=p.id).one().hashed_password)


def test_change_password_wrong_current_keeps_session(client, db):
    _mk_parent(db)
    tokens = _login(client).json()
    r = _change(client, _bearer(tokens), current="not-the-password")
    assert r.status_code == 400 and r.json()["code"] == "invalid_current_password"
    assert "current_password" in r.json()["errors"]
    assert client.get("/parent/profile", headers=_bearer(tokens)).status_code == 200
    assert _login(client).status_code == 200 and _login(client, password=NEW).status_code == 401


def test_change_password_validation(client, db):
    _mk_parent(db)
    h = _bearer(_login(client).json())
    for body in (
        {"current_password": OLD, "new_password": "short"},
        {"current_password": OLD, "new_password": "x1-" * 25},              # 75 bayt
        {"current_password": OLD, "new_password": OLD},                     # o'zgarmagan
        {"current_password": OLD, "new_password": NEW, "phone": "+998900000000"},   # ortiqcha maydon
        {"new_password": NEW},
    ):
        r = client.post("/parent/auth/change-password", headers=h, json=body)
        assert r.status_code == 422 and r.json()["code"] == "validation_error", body
    errs = client.post("/parent/auth/change-password", headers=h,
                       json={"current_password": OLD, "new_password": "short"}).json()["errors"]
    assert "new_password" in errs and "15" in errs["new_password"][0]
    assert _login(client).status_code == 200                                # parol o'zgarmadi


def test_change_password_requires_parent_token(client, db, hunter_user):
    assert client.post("/parent/auth/change-password",
                       json={"current_password": OLD, "new_password": NEW}).status_code == 401
    r = client.post("/parent/auth/change-password", headers=_staff(client),
                    json={"current_password": OLD, "new_password": NEW})
    assert r.status_code == 401


def test_change_password_rate_limited(client, db):
    _mk_parent(db)
    h = _bearer(_login(client).json())
    codes = [_change(client, h, current=f"wrong-{i}").status_code for i in range(6)]
    assert codes[:5] == [400] * 5 and codes[5] == 429
    r = _change(client, h)                                                  # to'g'ri parol ham kutadi
    assert r.status_code == 429 and r.headers.get("retry-after") and r.json()["code"] == "rate_limited"


def test_change_password_after_account_deletion_is_401(client, db):
    _mk_parent(db)
    h = _bearer(_login(client).json())
    assert client.delete("/parent/account", headers=h).status_code == 204
    assert _change(client, h).status_code == 401


def test_new_tokens_keep_child_ownership_boundary(client, db):
    mine, other = _mk_student(db, "Mine", "+998900000011"), _mk_student(db, "Other", "+998900000012")
    _mk_parent(db, children=[mine])
    _mk_parent(db, phone="+998901119999", children=[other])
    h = _bearer(_change(client, _bearer(_login(client).json())).json())
    assert client.get(f"/parent/children/{mine.id}/grades", headers=h).status_code == 200
    r = client.get(f"/parent/children/{other.id}/grades", headers=h)
    assert r.status_code == 404 and r.json()["code"] == "child_not_found"


# ── Login: anti-enumeration, eski tokenlar ──────────────────────────────────

def test_erased_account_old_password_is_plain_invalid(client, db):
    _mk_parent(db)
    h = _bearer(_login(client).json())
    assert client.delete("/parent/account", headers=h).status_code == 204
    wrong = _login(client, password="definitely-wrong-pass")
    assert wrong.status_code == 401 and wrong.json()["code"] == "invalid_credentials"
    unknown = _login(client, username="+998909999999", password="definitely-wrong-pass")
    assert unknown.json()["code"] == "invalid_credentials"
    # Production erasure: login/parol tombstone bilan almashtiriladi — eski ma'lumot bilan kirish
    # oddiy invalid_credentials (akkaunt avval bo'lganini ham oshkor qilmaydi).
    right = _login(client)
    assert right.status_code == 401 and right.json()["code"] == "invalid_credentials"


def test_legacy_access_token_without_pwv_still_works(client, db):
    p = _mk_parent(db)
    legacy = jwt.encode({"sub": str(p.id), "role": "parent", "exp": datetime.utcnow() + timedelta(minutes=5)},
                        security.SECRET_KEY, algorithm=security.ALGORITHM)
    assert client.get("/parent/profile", headers={"Authorization": f"Bearer {legacy}"}).status_code == 200
    forged = jwt.encode({"sub": str(p.id), "role": "parent", "pwv": "x" * 22,
                         "exp": datetime.utcnow() + timedelta(minutes=5)},
                        security.SECRET_KEY, algorithm=security.ALGORITHM)
    assert client.get("/parent/profile", headers={"Authorization": f"Bearer {forged}"}).status_code == 401


def test_ios_phone_and_password_contract(client, db):
    _mk_parent(db, phone="+998 90 111 22 33", username="nodira-opa")   # eski CRM formati, boshqa login
    r = _login(client, PHONE)
    assert r.status_code == 200 and set(r.json()) == {"access_token", "refresh_token"}


def test_otp_endpoints_stay_mounted(client, db, monkeypatch):
    # Eski App Store build OTP ishlatadi — endpointlar o'chirilmagan (validatsiya 400, 404 emas).
    from backend.main import app
    from backend.parent.phone_auth.gateway import get_gateway_client

    class _NoGateway:                       # hech qachon haqiqiy Telegram'ga murojaat bo'lmasin
        configured = False

        def __getattr__(self, name):
            raise AssertionError(f"gateway.{name} chaqirilmasligi kerak")

    monkeypatch.setitem(app.dependency_overrides, get_gateway_client, lambda: _NoGateway())
    for path, body in (("/auth/phone/request-code", {"phoneNumber": "123"}),
                       ("/auth/phone/resend-code", {"verificationId": "x" * 20, "phoneNumber": "123"}),
                       ("/auth/phone/verify-code", {"verificationId": "x" * 20, "phoneNumber": "123", "code": "123456"})):
        r = client.post(path, json=body)
        assert r.status_code == 400, (path, r.status_code)


# ── App Review akkaunti: statik kod → kuchli parolga migratsiya ─────────────

REVIEW = "+998900000777"


def test_review_account_migrates_from_static_code_to_strong_password(client, db, monkeypatch):
    monkeypatch.setenv("PARENT_REVIEW_PHONE", REVIEW)
    monkeypatch.setenv("PARENT_REVIEW_OTP", "4321")
    static = _login(client, "900000777", "4321")
    assert static.status_code == 200, static.text                         # hozirgi kirish buzilmagan
    kids = client.get("/parent/children", headers=_bearer(static.json())).json()
    assert len(kids) == 1 and kids[0]["full_name"].startswith("TEST — App Review")

    # Reviewer ilovada parolni almashtirishni sinasa — joriy parol sifatida qat'iy kod qabul qilinadi
    strong = "Review-Strong-Password-2026"
    r = _change(client, _bearer(static.json()), current="4321", new=strong)
    assert r.status_code == 200, r.text
    assert _login(client, REVIEW, strong).status_code == 200
    assert _login(client, REVIEW, "4321").status_code == 200              # env turganicha ishlaydi

    # Operator yangi build tasdiqlangach PARENT_REVIEW_OTP ni olib tashlaydi
    monkeypatch.delenv("PARENT_REVIEW_OTP")
    assert _login(client, REVIEW, "4321").status_code == 401
    ok = _login(client, REVIEW, strong)
    assert ok.status_code == 200
    kids = client.get("/parent/children", headers=_bearer(ok.json())).json()
    assert len(kids) == 1 and kids[0]["full_name"].startswith("TEST — App Review")   # hali ham faqat xayoliy


# ── Hunter: ota-ona akkauntlari bilan ishlash audit'i ───────────────────────
def test_hunter_parent_actions_are_audited_without_password(client, db, hunter_user):
    h = _staff(client)
    s1, s2 = _mk_student(db, "Alibek"), _mk_student(db, "Bekzod", "+998900000002")
    r = client.post("/parents", headers=h, json={"full_name": "Nodira Karimova", "phone": "90 111 22 33",
                                                 "student_ids": [s1.id]})
    assert r.status_code == 201, r.text
    pid, pwd = r.json()["id"], r.json()["generated_password"]
    assert r.json()["phone"] == PHONE and r.headers["cache-control"] == "no-store"
    assert client.post(f"/parents/{pid}/children", headers=h, json={"student_id": s2.id}).status_code == 200
    assert client.delete(f"/parents/{pid}/children/{s2.id}", headers=h).status_code == 204
    assert client.patch(f"/parents/{pid}", headers=h, json={"is_active": False}).status_code == 200
    reset = client.post(f"/parents/{pid}/reset-password", headers=h, json={})
    assert reset.status_code == 200

    rows = db.query(AuditLog).filter(AuditLog.entity_type == "parent", AuditLog.entity_id == pid).all()
    assert {a.action for a in rows} == {"create", "link_child", "unlink_child", "update", "reset_password"}
    assert all(a.changed_by_id == hunter_user.id for a in rows)
    blob = " ".join(f"{a.old_value} {a.new_value}" for a in rows)
    assert pwd not in blob and reset.json()["generated_password"] not in blob


def test_hunter_cannot_duplicate_parent_with_other_phone_format(client, db, hunter_user):
    s = _mk_student(db)
    existing = _mk_parent(db)          # masalan OTP orqali o'zi ro'yxatdan o'tgan
    for raw in ("+998 90 111 22 33", "901112233", "998901112233"):
        r = client.post("/parents", headers=_staff(client),
                        json={"full_name": "Nodira", "phone": raw, "student_ids": [s.id]})
        assert r.status_code == 409 and f"ID {existing.id}" in r.json()["detail"]
    assert db.query(Parent).count() == 1


def test_hunter_short_manual_password_rejected(client, db, hunter_user):
    s = _mk_student(db)
    r = client.post("/parents", headers=_staff(client),
                    json={"full_name": "Nodira", "phone": PHONE, "password": "12345", "student_ids": [s.id]})
    assert r.status_code == 422
    assert db.query(Parent).count() == 0


@pytest.mark.parametrize("full_name,phone,expected", [
    ("Nodira Karimova", "+998901112233", "Nodira2233"),
    ("  nodira  ", "+998901112233", "Nodira2233"),
    ("G'ulomjon Aliyev", "+998935554411", "Gulomjon4411"),      # apostrof olib tashlanadi
    ("Oʻgʻiloy", "+998977770009", "Ogiloy0009"),
    ("ДИЛШОД Каримов", "+998901234567", "Дилшод4567"),
])
def test_auto_password_is_name_plus_last4(full_name, phone, expected):
    from backend.main import _auto_parent_password
    assert _auto_parent_password(full_name, phone) == expected


def test_auto_password_falls_back_to_random_without_name_or_digits():
    from backend.main import _auto_parent_password
    for name, phone in (("123", "+998901112233"), ("Nodira", "abc"), ("", "+998901112233")):
        pw = _auto_parent_password(name, phone)
        assert len(pw) == 20 and security.parent_password_problem(pw) is None


# ── Ism-familiya: formatlash, parol uchun ism, ilovada to'ldirish ──────────
@pytest.mark.parametrize("raw,expected", [
    ("nodira karimova", "Nodira Karimova"),
    ("  NODIRA   KARIMOVA ", "Nodira Karimova"),
    ("o'g'iloy rahimova", "O'g'iloy Rahimova"),
    ("karimova nodira akmal QIZI", "Karimova Nodira Akmal qizi"),
    ("anna-mariya ivanova", "Anna-Mariya Ivanova"),
    ("дилшод каримов", "Дилшод Каримов"),
])
def test_format_person_name(raw, expected):
    from backend.parent.service import format_person_name
    assert format_person_name(raw) == expected


@pytest.mark.parametrize("full_name,phone,expected", [
    ("Karimova Nodira", "+998901112233", "Nodira2233"),            # familiya oldin
    ("Karimova Nodira Akmal qizi", "+998901112233", "Nodira2233"),
    ("Aliyev Dilshod Karim o'g'li", "+998935554411", "Dilshod4411"),
    ("Нодира Каримова", "+998901112233", "Нодира2233"),
    ("Karimov", "+998901112233", "Karimov2233"),                   # faqat familiya — birinchi so'z
])
def test_auto_password_skips_surname(full_name, phone, expected):
    from backend.main import _auto_parent_password
    assert _auto_parent_password(full_name, phone) == expected


def _patch_name(client, h, name):
    return client.patch("/parent/profile", headers=h, json={"display_name": name})


def test_app_completes_single_word_crm_name_and_capitalizes(client, db):
    p = _mk_parent(db)                                    # CRM: full_name = "Nodira" (faqat ism)
    h = _bearer(_login(client).json())
    before = client.get("/parent/profile", headers=h).json()
    assert len(before["full_name"].split()) == 1          # ilova shundan bilib, to'liq ism so'raydi
    r = _patch_name(client, h, "  nodira   karimova ")
    assert r.status_code == 204 and r.content == b""
    after = client.get("/parent/profile", headers=h).json()
    assert set(after) == set(before) == {"display_name", "full_name", "phone"}   # JSON shakli o'zgarmagan
    assert after["full_name"] == after["display_name"] == "Nodira Karimova"
    db.refresh(p)
    assert p.full_name == "Nodira Karimova"               # CRM'da ham to'liq ism
    assert _login(client).status_code == 200              # parol o'zgarmaydi


def test_app_name_change_does_not_overwrite_full_crm_name(client, db):
    p = _mk_parent(db)
    p.full_name = "Karimova Nodira Akmal qizi"; db.commit()
    h = _bearer(_login(client).json())
    assert _patch_name(client, h, "nodira opa").status_code == 204
    prof = client.get("/parent/profile", headers=h).json()
    assert prof["display_name"] == "Nodira Opa" and prof["full_name"] == "Karimova Nodira Akmal qizi"


def test_app_single_word_name_only_capitalized(client, db):
    _mk_parent(db)
    h = _bearer(_login(client).json())
    assert _patch_name(client, h, "nodira").status_code == 204
    prof = client.get("/parent/profile", headers=h).json()
    assert prof["display_name"] == "Nodira" and prof["full_name"] == "Nodira"


def test_profile_patch_contract_unchanged(client, db):
    _mk_parent(db)
    h = _bearer(_login(client).json())
    assert client.patch("/parent/profile", headers=h, json={"full_name": "X Y"}).status_code == 422  # yangi maydon yo'q
    assert _patch_name(client, h, "   ").status_code == 422
    assert client.patch("/parent/profile", headers=h, json={}).status_code == 422
