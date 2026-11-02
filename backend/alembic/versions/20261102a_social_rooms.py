"""Persistent online chess, checkers, UNO, Mafia and Sudoku rooms."""
from alembic import op
import sqlalchemy as sa
revision = '20261102a_social_rooms'
down_revision = '20261101a_reward_xp_bigint'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('minar_table_rooms',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('code', sa.String(8), nullable=False),
        sa.Column('game', sa.String(12), nullable=False),
        sa.Column('host_id', sa.Integer(), sa.ForeignKey('minar_accounts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('status', sa.String(12), nullable=False),
        sa.Column('state', sa.Text(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False))
    op.create_index('ix_minar_table_rooms_code', 'minar_table_rooms', ['code'], unique=True)
    op.create_index('ix_minar_table_rooms_status', 'minar_table_rooms', ['status'])
    op.create_index('ix_minar_table_rooms_expires_at', 'minar_table_rooms', ['expires_at'])
    op.create_table('minar_table_players',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('room_id', sa.String(36), sa.ForeignKey('minar_table_rooms.id', ondelete='CASCADE'), nullable=False),
        sa.Column('account_id', sa.Integer(), sa.ForeignKey('minar_accounts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('ready', sa.Boolean(), nullable=False),
        sa.UniqueConstraint('room_id', 'account_id', name='uq_table_member'))
    op.create_index('ix_minar_table_players_room_id', 'minar_table_players', ['room_id'])
    op.create_index('ix_minar_table_players_account_id', 'minar_table_players', ['account_id'])


def downgrade():
    op.drop_table('minar_table_players')
    op.drop_table('minar_table_rooms')
