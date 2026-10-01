"""Create the initial workout and meal tables."""

from alembic import op
import sqlalchemy as sa


revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "meals",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("log_date", sa.Date(), nullable=True),
        sa.Column("food", sa.String(), nullable=False),
        sa.Column("calories", sa.Integer(), nullable=True),
        sa.Column("protein_g", sa.Float(), nullable=True),
        sa.Column("carbs_g", sa.Float(), nullable=True),
        sa.Column("fat_g", sa.Float(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_meals_log_date", "meals", ["log_date"], unique=False)

    op.create_table(
        "workouts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("log_date", sa.Date(), nullable=True),
        sa.Column("exercise", sa.String(), nullable=False),
        sa.Column("sets", sa.Integer(), nullable=True),
        sa.Column("reps", sa.Integer(), nullable=True),
        sa.Column("weight_kg", sa.Float(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_workouts_log_date", "workouts", ["log_date"], unique=False)


def downgrade():
    op.drop_index("ix_workouts_log_date", table_name="workouts")
    op.drop_table("workouts")
    op.drop_index("ix_meals_log_date", table_name="meals")
    op.drop_table("meals")