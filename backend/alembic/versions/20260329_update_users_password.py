"""update users schema to username+password only

Revision ID: 20260329_update_users_password
Revises: 20260329_add_users
Create Date: 2026-03-29

NOTE: This migration is a no-op for PostgreSQL. The users table was already
created with the correct schema in 20260329_add_users.
"""
from alembic import op
import sqlalchemy as sa

revision = "20260329_update_users_password"
down_revision = "20260329_add_users"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # No-op: users table already has correct schema from 20260329_add_users
    pass


def downgrade() -> None:
    pass
