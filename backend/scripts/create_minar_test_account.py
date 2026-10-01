"""Minar Space uchun test akkaunt (haqiqiy talaba emas).

Arxivlangan "talaba" yozuvi yaratiladi — guruhsiz, to'lovsiz, CRM hisoblari
(faol talabalar, oylik, qarz) va Minar reytingiga kirmaydi. Akkaunt `is_test`
bo'lgani uchun login qila oladi. Balansga coin ledger orqali qo'shiladi.

Qayta ishga tushirilsa: yangi parol beriladi, balans --coins gacha to'ldiriladi.

Ishlatish:
    python -m backend.scripts.create_minar_test_account [--login MATEST] [--coins 1000000]
"""
import argparse
from datetime import datetime

from .. import models, security, tz
from ..database import SessionLocal
from ..minar import service
from ..minar.admin import _new_password
from ..minar.auth import normalize_login_id, revoke_sessions
from ..minar.models import MinarAccount, MinarLedger


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--login", default="MATEST")
    ap.add_argument("--coins", type=int, default=1_000_000)
    args = ap.parse_args()
    login_id = normalize_login_id(args.login)
    now = datetime.utcnow()

    db = SessionLocal()
    try:
        acc = db.query(MinarAccount).filter(MinarAccount.login_id == login_id).first()
        if acc and not acc.is_test:
            raise SystemExit(f"{login_id} — haqiqiy talabaning akkaunti, tegilmadi.")
        if not acc:
            student = models.Student(
                full_name="TEST Minar Space", phone1="000000000",
                notes="Minar Space test akkaunti — haqiqiy talaba emas.",
                is_active=False, is_archived=True, created_at=now, updated_at=now,
            )
            db.add(student)
            db.flush()
            acc = MinarAccount(student_id=student.id, login_id=login_id, password_hash="", is_test=True,
                               course="HTML", created_at=now)
            db.add(acc)
            db.flush()

        plain = _new_password()
        acc.password_hash = security.hash_password(plain)
        acc.password_changed_at = now
        acc.is_active = True
        acc.failed_attempts, acc.locked_until = 0, None
        revoke_sessions(db, acc.id)

        balance, _ = service.balance_and_earned(db, acc)
        if balance < args.coins:
            db.add(MinarLedger(
                account_id=acc.id, ref_key=f"test-grant:{now.isoformat()}", kind="reward",
                title="Test coinlar", amount=args.coins - balance, local_date=tz.today().isoformat(),
                created_at=now,
            ))
        db.commit()
        balance, _ = service.balance_and_earned(db, acc)
        print(f"login: {login_id}\nparol: {plain}\nbalans: {balance}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
