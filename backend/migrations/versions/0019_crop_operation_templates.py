"""Add crop operation templates.

Revision ID: 0019_crop_operation_templates
Revises: 0018_grading_records
Create Date: 2026-09-04
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision = "0019_crop_operation_templates"
down_revision = "0018_grading_records"
branch_labels = None
depends_on = None


TEMPLATES = (
    ("GARLIC", "LAND_PREPARATION", 0, True, "完成整地并确认墒情"),
    ("GARLIC", "SOWING", 7, True, "完成播种并记录作业面积"),
    ("GARLIC", "WEEDING", 35, False, "检查杂草并按需除草"),
    ("GARLIC", "FERTILIZATION", 45, True, "根据长势安排追肥"),
    ("GARLIC", "IRRIGATION", 60, False, "检查墒情并按需灌溉"),
    ("GARLIC", "PEST_CONTROL", 75, False, "巡查病虫害并按需防治"),
    ("RICE", "LAND_PREPARATION", 0, True, "完成整地与田面准备"),
    ("RICE", "SOWING", 7, True, "完成育秧播种"),
    ("RICE", "TRANSPLANTING", 30, True, "完成移栽并记录作业面积"),
    ("RICE", "IRRIGATION", 32, True, "移栽后检查水层"),
    ("RICE", "FERTILIZATION", 45, True, "根据苗情安排追肥"),
    ("RICE", "PEST_CONTROL", 60, False, "巡查病虫害并按需防治"),
    ("RAPESEED", "LAND_PREPARATION", 0, True, "完成整地与开沟"),
    ("RAPESEED", "SOWING", 7, True, "完成播种并记录作业面积"),
    ("RAPESEED", "WEEDING", 30, False, "检查杂草并按需除草"),
    ("RAPESEED", "FERTILIZATION", 45, True, "根据长势安排追肥"),
    ("RAPESEED", "PEST_CONTROL", 60, False, "巡查病虫害并按需防治"),
)


def upgrade():
    table = op.create_table(
        "crop_operation_templates",
        sa.Column("id", mysql.BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column("crop_type_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("operation_type", sa.String(24), nullable=False),
        sa.Column("offset_days", sa.Integer(), nullable=False),
        sa.Column("required", sa.Boolean(), server_default="1", nullable=False),
        sa.Column("default_notes", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("offset_days >= 0", name="ck_crop_operation_templates_offset_nonnegative"),
        sa.CheckConstraint(
            "operation_type IN ('LAND_PREPARATION', 'SOWING', 'TRANSPLANTING', 'IRRIGATION', "
            "'FERTILIZATION', 'PEST_CONTROL', 'WEEDING', 'OTHER')",
            name="ck_crop_operation_templates_type",
        ),
        sa.ForeignKeyConstraint(["crop_type_id"], ["crop_types.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("crop_type_id", "operation_type", name="uq_crop_operation_templates_type_operation"),
        mysql_charset="utf8mb4",
    )
    op.create_index(
        "ix_crop_operation_templates_crop_offset",
        "crop_operation_templates",
        ["crop_type_id", "offset_days", "id"],
    )
    connection = op.get_bind()
    crop_ids = dict(connection.execute(sa.text("SELECT code, id FROM crop_types")).all())
    connection.execute(table.insert(), [
        {
            "crop_type_id": crop_ids[crop_code],
            "operation_type": operation_type,
            "offset_days": offset_days,
            "required": required,
            "default_notes": default_notes,
        }
        for crop_code, operation_type, offset_days, required, default_notes in TEMPLATES
    ])


def downgrade():
    op.drop_table("crop_operation_templates")
