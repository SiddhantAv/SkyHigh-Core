"""Initial revision (no tables yet — add ORM models, then autogenerate).

Revision ID: 0001_initial
Revises:
Create Date: 2024-03-21

"""

from typing import Sequence, Union

from alembic import op

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
