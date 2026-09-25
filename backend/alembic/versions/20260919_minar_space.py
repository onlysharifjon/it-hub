"""Minar Space (space.minaracademy.uz): akkaunt, sessiya, ledger, natija, xarid, battle

Revision ID: 20260919_minar_space
Revises: 20260917_computers
Create Date: 2026-09-19
"""
import sqlalchemy as sa
from alembic import op

revision = "20260919_minar_space"
down_revision = "20260917_computers"
branch_labels = None
depends_on = None


def _account_fk():
    return sa.ForeignKey("minar_accounts.id", ondelete="CASCADE")


def upgrade():
    op.create_table(
        "minar_accounts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("login_id", sa.String(20), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("course", sa.String(20), nullable=False, server_default="HTML"),
        sa.Column("character", sa.String(10), nullable=False, server_default="robo"),
        sa.Column("equipment", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("xp", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("streak", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_login", sa.String(10), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("failed_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("locked_until", sa.DateTime(), nullable=True),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_login_at", sa.DateTime(), nullable=True),
        sa.Column("password_changed_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("student_id", name="uq_minar_accounts_student"),
    )
    op.create_index("ix_minar_accounts_id", "minar_accounts", ["id"])
    op.create_index("ix_minar_accounts_login_id", "minar_accounts", ["login_id"], unique=True)

    op.create_table(
        "minar_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("account_id", sa.Integer(), _account_fk(), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_minar_sessions_account_id", "minar_sessions", ["account_id"])
    op.create_index("ix_minar_sessions_token_hash", "minar_sessions", ["token_hash"], unique=True)

    op.create_table(
        "minar_ledger",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("account_id", sa.Integer(), _account_fk(), nullable=False),
        sa.Column("ref_key", sa.String(120), nullable=False),
        sa.Column("kind", sa.String(12), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("local_date", sa.String(10), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("account_id", "ref_key", name="uq_minar_ledger_ref"),
    )
    op.create_index("ix_minar_ledger_account_id", "minar_ledger", ["account_id"])
    op.create_index("ix_minar_ledger_local_date", "minar_ledger", ["local_date"])

    op.create_table(
        "minar_results",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("account_id", sa.Integer(), _account_fk(), nullable=False),
        sa.Column("result_id", sa.String(64), nullable=False),
        sa.Column("game", sa.String(12), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("award", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("xp", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("local_date", sa.String(10), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("account_id", "result_id", name="uq_minar_result"),
    )
    op.create_index("ix_minar_results_account_id", "minar_results", ["account_id"])
    op.create_index("ix_minar_results_local_date", "minar_results", ["local_date"])

    op.create_table(
        "minar_lessons",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("account_id", sa.Integer(), _account_fk(), nullable=False),
        sa.Column("course", sa.String(20), nullable=False),
        sa.Column("lesson_index", sa.Integer(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("account_id", "course", "lesson_index", name="uq_minar_lesson"),
    )
    op.create_index("ix_minar_lessons_account_id", "minar_lessons", ["account_id"])

    op.create_table(
        "minar_quests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("account_id", sa.Integer(), _account_fk(), nullable=False),
        sa.Column("local_date", sa.String(10), nullable=False),
        sa.Column("quest", sa.String(12), nullable=False),
        sa.Column("claimed_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("account_id", "local_date", "quest", name="uq_minar_quest"),
    )
    op.create_index("ix_minar_quests_account_id", "minar_quests", ["account_id"])

    op.create_table(
        "minar_purchases",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("account_id", sa.Integer(), _account_fk(), nullable=False),
        sa.Column("request_id", sa.String(64), nullable=False),
        sa.Column("product_id", sa.String(30), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("price", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("local_date", sa.String(10), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("updated_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.UniqueConstraint("account_id", "request_id", name="uq_minar_purchase_req"),
    )
    op.create_index("ix_minar_purchases_account_id", "minar_purchases", ["account_id"])

    op.create_table(
        "minar_battles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(12), nullable=False),
        sa.Column("room_id", sa.String(36), nullable=False),
        sa.Column("mode", sa.String(10), nullable=False),
        sa.Column("course", sa.String(20), nullable=False),
        sa.Column("host_account_id", sa.Integer(), sa.ForeignKey("minar_accounts.id"), nullable=False),
        sa.Column("guest_account_id", sa.Integer(), sa.ForeignKey("minar_accounts.id"), nullable=True),
        sa.Column("status", sa.String(12), nullable=False, server_default="waiting"),
        sa.Column("match_id", sa.String(36), nullable=True),
        sa.Column("winner_account_id", sa.Integer(), sa.ForeignKey("minar_accounts.id"), nullable=True),
        sa.Column("draw", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("host_score", sa.Integer(), nullable=True),
        sa.Column("guest_score", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("room_id", name="uq_minar_battles_room"),
    )
    op.create_index("ix_minar_battles_code", "minar_battles", ["code"], unique=True)
    op.create_index("ix_minar_battles_host_account_id", "minar_battles", ["host_account_id"])
    op.create_index("ix_minar_battles_match_id", "minar_battles", ["match_id"])


def downgrade():
    for t in ("minar_battles", "minar_purchases", "minar_quests", "minar_lessons",
              "minar_results", "minar_ledger", "minar_sessions", "minar_accounts"):
        op.drop_table(t)
