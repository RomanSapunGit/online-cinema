"""Fix association object in movies

Revision ID: cd6239b9455c
Revises: 009273ca983c
Create Date: 2025-10-21 15:41:35.075311

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from database import UserGroupEnum

# revision identifiers, used by Alembic.
revision: str = 'cd6239b9455c'
down_revision: Union[str, Sequence[str], None] = '009273ca983c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    pass

def downgrade():
    pass