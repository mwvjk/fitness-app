"""Add water intake logging."""

from alembic import op
import sqlalchemy as sa


revision = "0002_water_intake"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "water_intake",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("log_date", sa.Date(), nullable=True),
        sa.Column("amount_ml", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_water_intake_log_date", "water_intake", ["log_date"], unique=False
    )


def downgrade():
    op.drop_index("ix_water_intake_log_date", table_name="water_intake")
    op.drop_table("water_intake")
