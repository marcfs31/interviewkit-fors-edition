"""add user.oauth_code_nonce (makes the OAuth exchange code single-use)

Revision ID: c8d9e0f1a2b3
Revises: a7c9e1b3d5f2
Create Date: 2026-10-13 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c8d9e0f1a2b3'
down_revision = 'a7c9e1b3d5f2'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('user', sa.Column('oauth_code_nonce', sa.String(length=64), nullable=True))


def downgrade():
    op.drop_column('user', 'oauth_code_nonce')
