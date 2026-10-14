"""Parent engagement: push, explanations and teacher questions.

Revision ID: 20261014a_parent_engagement
Revises: 20261013a_parent_release_config
"""
import sqlalchemy as sa
from alembic import op

revision = "20261014a_parent_engagement"
down_revision = "20261013a_parent_release_config"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("parent_notifications", sa.Column("push_attempted_at", sa.DateTime(), nullable=True))
    op.add_column("parent_notifications", sa.Column("push_error", sa.String(120), nullable=True))
    op.add_column("parent_notifications", sa.Column("push_attempts", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("parent_notifications", sa.Column("push_next_attempt_at", sa.DateTime(), nullable=True))
    op.create_table(
        "parent_push_devices",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("parent_id", sa.Integer(), sa.ForeignKey("parents.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("token", sa.String(200), nullable=False),
        sa.Column("platform", sa.String(12), nullable=False),
        sa.Column("environment", sa.String(12), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "parent_notification_preferences",
        sa.Column("parent_id", sa.Integer(), sa.ForeignKey("parents.id", ondelete="CASCADE"), primary_key=True),
        *[sa.Column(name, sa.Boolean(), nullable=False, server_default=sa.true()) for name in
          ("attendance", "schedule", "payments", "homework", "announcements", "weekly_summary", "teacher_messages")],
    )
    op.create_table(
        "parent_absence_explanations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("parent_id", sa.Integer(), sa.ForeignKey("parents.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("attendance_id", sa.Integer(), sa.ForeignKey("attendance.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reason", sa.String(20), nullable=False),
        sa.Column("note", sa.String(1000), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("staff_note", sa.String(500), nullable=True),
        sa.Column("reviewed_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("parent_id", "attendance_id", name="uq_parent_absence_per_guardian"),
    )
    op.create_table(
        "parent_teacher_questions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("parent_id", sa.Integer(), sa.ForeignKey("parents.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("groups.id", ondelete="SET NULL"), nullable=True),
        sa.Column("subject", sa.String(120), nullable=False),
        sa.Column("body", sa.String(2000), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "parent_teacher_replies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("question_id", sa.Integer(), sa.ForeignKey("parent_teacher_questions.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("staff_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("body", sa.String(2000), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "parent_weekly_recommendations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("text", sa.String(500), nullable=False),
        sa.Column("staff_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("student_id", "week_start", name="uq_parent_weekly_recommendation"),
    )


def downgrade():
    op.drop_table("parent_weekly_recommendations")
    op.drop_table("parent_teacher_replies")
    op.drop_table("parent_teacher_questions")
    op.drop_table("parent_absence_explanations")
    op.drop_table("parent_notification_preferences")
    op.drop_table("parent_push_devices")
    op.drop_column("parent_notifications", "push_error")
    op.drop_column("parent_notifications", "push_next_attempt_at")
    op.drop_column("parent_notifications", "push_attempts")
    op.drop_column("parent_notifications", "push_attempted_at")
