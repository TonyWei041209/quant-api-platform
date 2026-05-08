"""add sync_session_id to broker_position_snapshot for ghost-holding fix

Adds nullable `sync_session_id` UUID column to broker_position_snapshot.
All position rows written by a single sync_trading212_readonly run share
the same sync_session_id, allowing the API layer to return only the
most recent snapshot-set rather than accumulating ghost rows from closed
positions (which never get a qty=0 marker because T212 only returns
currently-held positions).

Also adds two indexes used by the new portfolio query:
  - ix_broker_position_snapshot_broker_session: (broker, sync_session_id)
  - ix_broker_position_snapshot_broker_snapshot_at: (broker, snapshot_at DESC)

Backwards compatible: existing rows keep sync_session_id NULL, and
get_portfolio_summary() falls back to the legacy latest-positive-row
query when no non-null sync_session_id exists.

Revision ID: b8a3f2d91e47
Revises: 4621a4c260c7
Create Date: 2026-05-08
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b8a3f2d91e47'
down_revision: Union[str, None] = '4621a4c260c7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'broker_position_snapshot',
        sa.Column('sync_session_id', sa.UUID(), nullable=True),
    )
    op.create_index(
        'ix_broker_position_snapshot_broker_session',
        'broker_position_snapshot',
        ['broker', 'sync_session_id'],
        unique=False,
    )
    op.create_index(
        'ix_broker_position_snapshot_broker_snapshot_at',
        'broker_position_snapshot',
        ['broker', sa.text('snapshot_at DESC')],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        'ix_broker_position_snapshot_broker_snapshot_at',
        table_name='broker_position_snapshot',
    )
    op.drop_index(
        'ix_broker_position_snapshot_broker_session',
        table_name='broker_position_snapshot',
    )
    op.drop_column('broker_position_snapshot', 'sync_session_id')
