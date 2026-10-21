"""Create synthetic, one-time invoice IDs for the isolated Paycom test cashbox.

First migrate the dedicated database, then run this command inside the sandbox
container. It prints only account IDs and test amounts, never credentials.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta

from backend.paycom_sandbox_app import require_sandbox_database

require_sandbox_database()

from backend import models  # noqa: E402
from backend.database import SessionLocal  # noqa: E402


def create_invoices(amount: int, count: int, ttl_hours: int) -> list[int]:
    db = SessionLocal()
    try:
        parent = db.query(models.Parent).filter_by(username="paycom_sandbox_parent").first()
        if parent is None:
            parent = models.Parent(
                full_name="Paycom Sandbox Parent", phone="+998000000001",
                username="paycom_sandbox_parent", hashed_password="!", is_active=False,
            )
            db.add(parent)
        student = db.query(models.Student).filter_by(full_name="Paycom Sandbox Student").first()
        if student is None:
            student = models.Student(
                full_name="Paycom Sandbox Student", phone1="+998000000002",
                is_active=True, is_demo=True,
            )
            db.add(student)
        group = db.query(models.Group).filter_by(name="Paycom Sandbox Group").first()
        if group is None:
            group = models.Group(
                name="Paycom Sandbox Group", stage="foundation",
                course_price=amount, is_active=True, start_date=datetime.utcnow(),
            )
            db.add(group)
        db.flush()
        if not db.query(models.GroupStudent).filter_by(
                student_id=student.id, group_id=group.id).first():
            db.add(models.GroupStudent(student_id=student.id, group_id=group.id))
        expires_at = datetime.utcnow() + timedelta(hours=ttl_hours)
        invoices = [models.ParentInvoice(
            parent_id=parent.id, student_id=student.id, group_id=group.id,
            amount=amount, provider="payme", status="pending", expires_at=expires_at,
        ) for _ in range(count)]
        db.add_all(invoices)
        db.commit()
        return [invoice.id for invoice in invoices]
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--amount", type=int, required=True, help="Test sum in UZS")
    parser.add_argument("--count", type=int, default=4, help="Fresh one-time accounts")
    parser.add_argument("--ttl-hours", type=int, default=24)
    args = parser.parse_args()
    if not 1 <= args.amount <= 20_000_000 or not 1 <= args.count <= 20 or not 1 <= args.ttl_hours <= 72:
        parser.error("amount must be 1..20000000 UZS, count 1..20, ttl-hours 1..72")
    ids = create_invoices(args.amount, args.count, args.ttl_hours)
    print(json.dumps({
        "amount_tiyin": args.amount * 100,
        "accounts": [{"order_id": str(invoice_id)} for invoice_id in ids],
    }))


if __name__ == "__main__":
    main()
