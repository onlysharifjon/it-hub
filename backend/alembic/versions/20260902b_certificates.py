"""group_certificates jadvali — guruh uchun generatsiya qilingan (dizaynli,
HTML/print shabloni asosidagi) sertifikatlarni saqlaydi (bir marta
generatsiya qilingach, qayta ochilganda/regenerate qilinganda o'sha yozuv
qaytariladi; tahrirlab qayta saqlash mumkin). Mavjud `certificates`
jadvalidan (talaba profilidagi PDF-fayl havolali sertifikatlar) farqli —
nom to'qnashmasligi uchun alohida jadval.

Faqat qo'shimcha: yangi jadval, mavjud narsalarga ta'sir qilmaydi.

Revision ID: 20260902b_certificates
Revises: 20260902_salary_override_internship
Create Date: 2026-09-02
"""
import sqlalchemy as sa
from alembic import op

revision = '20260902b_certificates'
down_revision = '20260902_salary_override_internship'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'group_certificates',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('group_id', sa.Integer(), sa.ForeignKey('groups.id'), nullable=False, index=True),
        sa.Column('student_id', sa.Integer(), sa.ForeignKey('students.id'), nullable=False, index=True),
        sa.Column('cert_number', sa.String(60), nullable=False),
        sa.Column('student_name', sa.String(200), nullable=False),
        sa.Column('course_label', sa.String(120), nullable=False, server_default=''),
        sa.Column('issue_date', sa.String(30), nullable=False, server_default=''),
        sa.Column('signer_name', sa.String(200), nullable=False, server_default="Sharifjon Mo'minov"),
        sa.Column('signer_title', sa.String(60), nullable=False, server_default='CEO'),
        sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('group_id', 'student_id', name='uq_certificate_group_student'),
    )


def downgrade() -> None:
    op.drop_table('group_certificates')
