"""Separate Android release limits and accept opaque FCM registration tokens."""
from alembic import op
import sqlalchemy as sa

revision = "20261022a_parent_android_parity"
down_revision = "20261017b_restore_staff_refs"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("parent_release_config") as table:
        table.add_column(sa.Column("android_min_supported_build", sa.Integer(),
                                   nullable=False, server_default="1"))
        table.add_column(sa.Column("android_latest_build", sa.Integer(),
                                   nullable=False, server_default="1"))
        table.add_column(sa.Column("play_store_url", sa.String(length=500),
                                   nullable=False, server_default=""))
        table.create_check_constraint("ck_parent_release_android_min_build",
                                      "android_min_supported_build >= 1")
        table.create_check_constraint("ck_parent_release_android_latest_build",
                                      "android_latest_build >= android_min_supported_build")
    with op.batch_alter_table("parent_push_devices") as table:
        table.alter_column("token", existing_type=sa.String(length=200),
                           type_=sa.String(length=4096), existing_nullable=False)


def downgrade():
    db = op.get_bind()
    if db.execute(sa.text("SELECT 1 FROM parent_push_devices WHERE length(token) > 200 LIMIT 1")).first():
        raise RuntimeError("Cannot shrink push token column while tokens exceed 200 characters")
    with op.batch_alter_table("parent_push_devices") as table:
        table.alter_column("token", existing_type=sa.String(length=4096),
                           type_=sa.String(length=200), existing_nullable=False)
    with op.batch_alter_table("parent_release_config") as table:
        table.drop_constraint("ck_parent_release_android_latest_build", type_="check")
        table.drop_constraint("ck_parent_release_android_min_build", type_="check")
        table.drop_column("play_store_url")
        table.drop_column("android_latest_build")
        table.drop_column("android_min_supported_build")
