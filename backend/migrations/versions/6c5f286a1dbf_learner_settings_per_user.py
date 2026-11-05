"""learner settings per user

Revision ID: 6c5f286a1dbf
Revises: e0e9d53b9bbf
Create Date: 2026-11-04 23:43:05.143925

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6c5f286a1dbf'
down_revision: Union[str, Sequence[str], None] = 'e0e9d53b9bbf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("learner_settings", sa.Column("user_id", sa.Uuid(), nullable=True))
    # The single row from before login belongs to the first account.
    op.execute(
        "UPDATE learner_settings SET user_id = "
        "(SELECT id FROM users ORDER BY created_at LIMIT 1)"
    )
    op.execute("DELETE FROM learner_settings WHERE user_id IS NULL")
    op.drop_constraint("learner_settings_pkey", "learner_settings", type_="primary")
    op.drop_column("learner_settings", "id")
    op.alter_column("learner_settings", "user_id", nullable=False)
    op.create_primary_key("learner_settings_pkey", "learner_settings", ["user_id"])
    op.create_foreign_key(
        op.f("learner_settings_user_id_fkey"),
        "learner_settings",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    """Downgrade schema. Only the first account's settings are kept, as id 1."""
    op.drop_constraint(
        op.f("learner_settings_user_id_fkey"), "learner_settings", type_="foreignkey"
    )
    op.drop_constraint("learner_settings_pkey", "learner_settings", type_="primary")
    op.execute(
        "DELETE FROM learner_settings WHERE user_id <> "
        "(SELECT id FROM users ORDER BY created_at LIMIT 1)"
    )
    op.add_column("learner_settings", sa.Column("id", sa.Integer(), nullable=True))
    op.execute("UPDATE learner_settings SET id = 1")
    op.alter_column("learner_settings", "id", nullable=False)
    op.create_primary_key("learner_settings_pkey", "learner_settings", ["id"])
    op.drop_column("learner_settings", "user_id")
