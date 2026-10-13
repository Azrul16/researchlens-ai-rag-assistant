"""Use timezone-aware UTC timestamps on PostgreSQL, preserving existing values."""

import sqlalchemy as sa

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

TABLES = {
    "users": ["created_at", "updated_at"],
    "workspaces": ["created_at", "updated_at"],
    "documents": ["created_at", "updated_at"],
    "document_chunks": ["created_at"],
    "conversations": ["created_at", "updated_at"],
    "messages": ["created_at"],
    "document_analyses": ["created_at"],
}


def upgrade():
    if op.get_bind().dialect.name == "postgresql":
        for table, columns in TABLES.items():
            for column in columns:
                op.alter_column(
                    table,
                    column,
                    type_=sa.DateTime(timezone=True),
                    existing_type=sa.DateTime(),
                    existing_nullable=False,
                    postgresql_using=f"{column} AT TIME ZONE 'UTC'",
                )


def downgrade():
    if op.get_bind().dialect.name == "postgresql":
        for table, columns in TABLES.items():
            for column in columns:
                op.alter_column(
                    table,
                    column,
                    type_=sa.DateTime(),
                    existing_type=sa.DateTime(timezone=True),
                    existing_nullable=False,
                    postgresql_using=f"{column} AT TIME ZONE 'UTC'",
                )
