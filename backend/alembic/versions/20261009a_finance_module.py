"""Moliya bo'limi: Finans roli huquqlari, kassa/hisoblar, xarajat kategoriyalari,
operatsiyalar jurnali va audit sababi.

Revision ID: 20261009a_finance_module
Revises: 20261007a_phone_verifications
Create Date: 2026-10-09

Mavjud ma'lumotlar o'zgarmaydi. Barcha mavjud to'lovlar (payments) va
xarajatlar (expenses) jurnalga TASDIQLANGAN operatsiya sifatida ko'chiriladi
(hisobi "belgilanmagan" — tarixiy yozuvlar kassa qoldig'iga ta'sir qilmaydi;
kassa qoldig'i admin kiritadigan boshlang'ich qoldiqdan boshlanadi).

Qaytarish (downgrade): yangi jadvallar va ustunlar o'chiriladi; payments va
expenses jadvallariga tegilmaydi.
"""
import sqlalchemy as sa
from alembic import op

revision = '20261009a_finance_module'
down_revision = '20261007a_phone_verifications'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('permissions', sa.Text(), nullable=True))
    op.add_column('audit_logs', sa.Column('reason', sa.Text(), nullable=True))

    op.create_table(
        'finance_accounts',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(120), nullable=False),
        sa.Column('kind', sa.String(12), nullable=False, server_default='cash'),
        sa.Column('currency', sa.String(3), nullable=False, server_default='UZS'),
        sa.Column('code', sa.String(40), nullable=True, unique=True),
        sa.Column('opening_balance', sa.Numeric(14, 2), nullable=False, server_default='0'),
        sa.Column('balance', sa.Numeric(14, 2), nullable=False, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_finance_accounts_id', 'finance_accounts', ['id'])

    op.create_table(
        'expense_categories',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(120), nullable=False, unique=True),
        sa.Column('code', sa.String(40), nullable=True, unique=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_expense_categories_id', 'expense_categories', ['id'])

    op.create_table(
        'finance_transactions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('number', sa.String(24), nullable=True),
        sa.Column('kind', sa.String(12), nullable=False),
        sa.Column('flow', sa.String(12), nullable=False),
        sa.Column('status', sa.String(12), nullable=False, server_default='draft'),
        sa.Column('amount', sa.Numeric(14, 2), nullable=False),
        sa.Column('signed_amount', sa.Numeric(14, 2), nullable=False, server_default='0'),
        sa.Column('currency', sa.String(3), nullable=False, server_default='UZS'),
        sa.Column('fx_rate', sa.Numeric(14, 4), nullable=True),
        sa.Column('amount_uzs', sa.Numeric(14, 2), nullable=True),
        sa.Column('op_date', sa.Date(), nullable=False),
        sa.Column('method', sa.String(16), nullable=True),
        sa.Column('account_id', sa.Integer(), sa.ForeignKey('finance_accounts.id'), nullable=True),
        sa.Column('to_account_id', sa.Integer(), sa.ForeignKey('finance_accounts.id'), nullable=True),
        sa.Column('student_id', sa.Integer(), sa.ForeignKey('students.id'), nullable=True),
        sa.Column('group_id', sa.Integer(), sa.ForeignKey('groups.id'), nullable=True),
        sa.Column('period_month', sa.Integer(), nullable=True),
        sa.Column('period_year', sa.Integer(), nullable=True),
        sa.Column('payment_id', sa.Integer(), sa.ForeignKey('payments.id', ondelete='SET NULL'), nullable=True),
        sa.Column('parent_invoice_id', sa.Integer(), sa.ForeignKey('parent_invoices.id', ondelete='SET NULL'), nullable=True),
        sa.Column('expense_id', sa.Integer(), sa.ForeignKey('expenses.id', ondelete='SET NULL'), nullable=True),
        sa.Column('origin_id', sa.Integer(), sa.ForeignKey('finance_transactions.id'), nullable=True),
        sa.Column('category_id', sa.Integer(), sa.ForeignKey('expense_categories.id'), nullable=True),
        sa.Column('counterparty', sa.String(200), nullable=True),
        sa.Column('responsible_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('staff_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('external_ref', sa.String(120), nullable=True),
        sa.Column('external_verified', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('document_path', sa.String(500), nullable=True),
        sa.Column('idempotency_key', sa.String(80), nullable=True),
        sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('confirmed_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('confirmed_at', sa.DateTime(), nullable=True),
        sa.Column('cancelled_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('cancelled_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    for col in ('id', 'kind', 'flow', 'status', 'op_date', 'method', 'account_id', 'student_id', 'group_id',
                'payment_id', 'parent_invoice_id', 'expense_id', 'origin_id', 'category_id',
                'responsible_id', 'created_by_id', 'created_at'):
        op.create_index(f'ix_finance_transactions_{col}', 'finance_transactions', [col])
    op.create_index('ix_finance_transactions_number', 'finance_transactions', ['number'], unique=True)
    op.create_unique_constraint('uq_finance_transactions_idempotency_key', 'finance_transactions', ['idempotency_key'])

    op.create_table(
        'finance_settings',
        sa.Column('key', sa.String(60), primary_key=True),
        sa.Column('value', sa.String(200), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    # ── Tizim hisoblari va standart kategoriyalar ──
    op.execute("""
        INSERT INTO finance_accounts (name, kind, currency, code, opening_balance, balance, is_active)
        VALUES ('Asosiy kassa', 'cash', 'UZS', 'main_cash', 0, 0, true),
               ('Onlayn to''lovlar (Payme/Click/Uzum)', 'online', 'UZS', 'online', 0, 0, true)
    """)
    op.execute("""
        INSERT INTO expense_categories (name, code, is_active) VALUES
        ('Ish haqi', 'salary', true), ('Boshqa', 'other', true), ('Ijara', NULL, true),
        ('Kommunal xizmatlar', NULL, true), ('Reklama va marketing', NULL, true),
        ('Jihozlar', NULL, true), ('Ofis xarajatlari', NULL, true), ('Soliq va to''lovlar', NULL, true)
    """)
    op.execute("INSERT INTO finance_settings (key, value) VALUES ('due_day', '10'), ('upcoming_days', '7')")

    # ── Mavjud to'lovlar → jurnal (tasdiqlangan kirim, hisob belgilanmagan) ──
    op.execute("""
        INSERT INTO finance_transactions
            (kind, flow, status, amount, signed_amount, currency, amount_uzs, op_date, method,
             student_id, group_id, period_month, period_year, payment_id, parent_invoice_id,
             external_verified, notes, created_by_id, confirmed_by_id, confirmed_at, created_at)
        SELECT 'income', 'income', 'confirmed', p.amount, p.amount, 'UZS', p.amount,
               CAST(p.paid_at + INTERVAL '5 hours' AS DATE),
               CASE WHEN p.parent_invoice_id IS NOT NULL THEN 'online' ELSE 'unknown' END,
               p.student_id, p.group_id, p.month, p.year, p.id, p.parent_invoice_id,
               p.parent_invoice_id IS NOT NULL, p.notes, p.recorded_by_id, p.recorded_by_id, p.paid_at, p.paid_at
        FROM payments p ORDER BY p.paid_at, p.id
    """)
    # ── Mavjud xarajatlar → jurnal (tasdiqlangan xarajat) ──
    op.execute("""
        INSERT INTO finance_transactions
            (kind, flow, status, amount, signed_amount, currency, amount_uzs, op_date, method,
             category_id, staff_id, counterparty, expense_id, notes, confirmed_at, created_at)
        SELECT 'expense', 'expense', 'confirmed', e.amount, -e.amount, 'UZS', e.amount,
               CAST(e.created_at + INTERVAL '5 hours' AS DATE), 'unknown',
               (SELECT id FROM expense_categories WHERE code = CASE WHEN e.category = 'salary' THEN 'salary' ELSE 'other' END),
               e.staff_id, COALESCE(u.full_name, u.username), e.id, e.name, e.created_at, e.created_at
        FROM expenses e LEFT JOIN users u ON u.id = e.staff_id
        ORDER BY e.created_at, e.id
    """)
    op.execute("""
        UPDATE finance_transactions
        SET number = CASE kind WHEN 'income' THEN 'KR-' ELSE 'XR-' END || LPAD(CAST(id AS TEXT), 6, '0')
        WHERE number IS NULL
    """)


def downgrade():
    op.drop_table('finance_transactions')
    op.drop_table('finance_settings')
    op.drop_table('expense_categories')
    op.drop_table('finance_accounts')
    op.drop_column('audit_logs', 'reason')
    op.drop_column('users', 'permissions')
