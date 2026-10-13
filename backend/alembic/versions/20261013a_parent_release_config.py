"""Parent iOS maintenance and release control, disabled by default.

Revision ID: 20261013a_parent_release_config
Revises: 20261012a_parent_deleted_at
"""
import sqlalchemy as sa
from alembic import op

revision = "20261013a_parent_release_config"
down_revision = "20261012a_parent_deleted_at"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "parent_release_config",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("maintenance_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("maintenance_title", sa.String(120), nullable=False),
        sa.Column("maintenance_message", sa.String(600), nullable=False),
        sa.Column("min_supported_build", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("latest_build", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("app_store_url", sa.String(500), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.CheckConstraint("id = 1", name="ck_parent_release_config_singleton"),
        sa.CheckConstraint("min_supported_build >= 1", name="ck_parent_release_min_build"),
        sa.CheckConstraint("latest_build >= min_supported_build", name="ck_parent_release_latest_build"),
    )
    op.execute(
        sa.text("""
            INSERT INTO parent_release_config
              (id, maintenance_enabled, maintenance_title, maintenance_message,
               min_supported_build, latest_build, app_store_url)
            VALUES
              (1, false, 'Texnik xizmat davom etmoqda',
               'Ilova ustida qisqa texnik ishlar olib borilmoqda. Birozdan so‘ng qayta urinib ko‘ring.',
               1, 5, 'https://apps.apple.com/uz/app/minar-parents/id6820518218')
        """)
    )


def downgrade():
    op.drop_table("parent_release_config")
