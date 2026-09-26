"""merge current migration heads

Revision ID: a50010e91978
Revises: 2898e45d9813, a78496a17479
Create Date: 2026-09-06 22:42:13.903781

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a50010e91978'
down_revision: Union[str, Sequence[str], None] = ('2898e45d9813', 'a78496a17479')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
