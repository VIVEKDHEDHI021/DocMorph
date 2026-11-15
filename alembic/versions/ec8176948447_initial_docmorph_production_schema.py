"""Initial DocMorph production schema

Revision ID: ec8176948447
Revises: 
Create Date: 2026-11-01 13:06:56.663398

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ec8176948447'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Creates initial core tables and indexes."""
    # 1. Users table
    op.create_table(
        'users',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('email', sa.String(length=255), nullable=False, unique=True),
        sa.Column('hashed_password', sa.String(length=255), nullable=False),
        sa.Column('full_name', sa.String(length=100), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('is_superuser', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_users_email', 'users', ['email'], unique=True)

    # 2. Documents table
    op.create_table(
        'documents',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('user_id', sa.String(length=36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('original_filename', sa.String(length=255), nullable=False),
        sa.Column('source_storage_key', sa.String(length=255), nullable=False),
        sa.Column('page_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('file_size', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='uploaded'),
        sa.Column('error_message', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_documents_user_id', 'documents', ['user_id'])
    op.create_index('ix_documents_status', 'documents', ['status'])

    # 3. Detections table
    op.create_table(
        'detections',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('document_id', sa.String(length=36), sa.ForeignKey('documents.id', ondelete='CASCADE'), nullable=False),
        sa.Column('field_id', sa.String(length=100), nullable=False),
        sa.Column('field_type', sa.String(length=50), nullable=False),
        sa.Column('original_value', sa.String(length=255), nullable=False),
        sa.Column('suggested_value', sa.String(length=255), nullable=False),
        sa.Column('corrected_value', sa.String(length=255), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('review_status', sa.String(length=50), nullable=False, server_default='pending'),
        sa.Column('is_ambiguous', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('reasons_json', sa.Text(), nullable=False, server_default='[]'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_detections_document_id', 'detections', ['document_id'])
    op.create_index('ix_detections_field_id', 'detections', ['field_id'])

    # 4. Detection Occurrences table
    op.create_table(
        'detection_occurrences',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('detection_id', sa.String(length=36), sa.ForeignKey('detections.id', ondelete='CASCADE'), nullable=False),
        sa.Column('page_number', sa.Integer(), nullable=False),
        sa.Column('raw_text', sa.String(length=500), nullable=False, server_default=''),
        sa.Column('bbox_json', sa.Text(), nullable=False, server_default='{}'),
        sa.Column('value_bbox_json', sa.Text(), nullable=False, server_default='{}'),
        sa.Column('label_bbox_json', sa.Text(), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_detection_occurrences_detection_id', 'detection_occurrences', ['detection_id'])

    # 5. Jobs table
    op.create_table(
        'jobs',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('document_id', sa.String(length=36), sa.ForeignKey('documents.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', sa.String(length=36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='processing'),
        sa.Column('total_replacements', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('successful_replacements', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('failed_replacements', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('verification_status', sa.String(length=50), nullable=False, server_default='pending'),
        sa.Column('warnings_json', sa.Text(), nullable=False, server_default='[]'),
        sa.Column('occurrence_results_json', sa.Text(), nullable=False, server_default='[]'),
        sa.Column('verification_report_json', sa.Text(), nullable=False, server_default='{}'),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_jobs_document_id', 'jobs', ['document_id'])
    op.create_index('ix_jobs_user_id', 'jobs', ['user_id'])
    op.create_index('ix_jobs_status', 'jobs', ['status'])

    # 6. Personalized Outputs table
    op.create_table(
        'personalized_outputs',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('document_id', sa.String(length=36), sa.ForeignKey('documents.id', ondelete='CASCADE'), nullable=False),
        sa.Column('job_id', sa.String(length=36), sa.ForeignKey('jobs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('storage_key', sa.String(length=255), nullable=False),
        sa.Column('filename', sa.String(length=255), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_personalized_outputs_document_id', 'personalized_outputs', ['document_id'])
    op.create_index('ix_personalized_outputs_job_id', 'personalized_outputs', ['job_id'])


def downgrade() -> None:
    """Drops all tables in reverse order."""
    op.drop_table('personalized_outputs')
    op.drop_table('jobs')
    op.drop_table('detection_occurrences')
    op.drop_table('detections')
    op.drop_table('documents')
    op.drop_table('users')
