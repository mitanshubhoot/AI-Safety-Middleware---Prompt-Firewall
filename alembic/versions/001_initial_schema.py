"""Initial database schema

Revision ID: 001
Revises:
Create Date: 2024-01-01 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade database schema."""
    # Create extension for UUID generation
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')

    # Create prompts table
    op.create_table(
        'prompts',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('content_hash', sa.String(length=64), nullable=False, comment='SHA-256 hash of prompt content'),
        sa.Column('user_id', sa.String(length=200), nullable=True),
        sa.Column('policy_id', sa.String(length=200), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('is_safe', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('latency_ms', sa.Float(), nullable=False),
        sa.Column('detection_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('cached', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('context', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_prompts_content_hash', 'prompts', ['content_hash'])
    op.create_index('ix_prompts_user_id', 'prompts', ['user_id'])
    op.create_index('ix_prompts_policy_id', 'prompts', ['policy_id'])
    op.create_index('ix_prompts_status', 'prompts', ['status'])
    op.create_index('ix_prompts_created_at', 'prompts', ['created_at'])

    # Create detections table
    op.create_table(
        'detections',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('prompt_id', postgresql.UUID(as_uuid=True), nullable=False, comment='Foreign key to prompts table'),
        sa.Column('detection_type', sa.String(length=50), nullable=False),
        sa.Column('matched_pattern', sa.String(length=500), nullable=False),
        sa.Column('confidence_score', sa.Float(), nullable=False),
        sa.Column('severity', sa.String(length=50), nullable=False),
        sa.Column('category', sa.String(length=100), nullable=True),
        sa.Column('blocked', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('match_positions', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('metadata', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_detections_prompt_id', 'detections', ['prompt_id'])
    op.create_index('ix_detections_detection_type', 'detections', ['detection_type'])
    op.create_index('ix_detections_severity', 'detections', ['severity'])
    op.create_index('ix_detections_category', 'detections', ['category'])
    op.create_index('ix_detections_created_at', 'detections', ['created_at'])

    # Create policies table
    op.create_table(
        'policies',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('policy_id', sa.String(length=200), nullable=False, comment='Human-readable policy identifier'),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('rules', postgresql.JSON(astext_type=sa.Text()), nullable=False, comment='Policy rules in JSON format'),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('policy_id')
    )
    op.create_index('ix_policies_policy_id', 'policies', ['policy_id'], unique=True)
    op.create_index('ix_policies_enabled', 'policies', ['enabled'])

    # Create audit_logs table
    op.create_table(
        'audit_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('timestamp', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('user_id', sa.String(length=200), nullable=True),
        sa.Column('action', sa.String(length=100), nullable=False),
        sa.Column('resource_type', sa.String(length=100), nullable=False),
        sa.Column('resource_id', sa.String(length=200), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.String(length=500), nullable=True),
        sa.Column('details', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_audit_logs_timestamp', 'audit_logs', ['timestamp'])
    op.create_index('ix_audit_logs_user_id', 'audit_logs', ['user_id'])
    op.create_index('ix_audit_logs_action', 'audit_logs', ['action'])
    op.create_index('ix_audit_logs_resource_type', 'audit_logs', ['resource_type'])

    # Create sensitive_data_patterns table
    op.create_table(
        'sensitive_data_patterns',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('pattern_text', sa.Text(), nullable=False, comment='Example of sensitive data pattern'),
        sa.Column('category', sa.String(length=100), nullable=False),
        sa.Column('severity', sa.String(length=50), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('embedding_hash', sa.String(length=64), nullable=True, comment='Hash of embedding stored in Redis'),
        sa.Column('metadata', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_sensitive_data_patterns_category', 'sensitive_data_patterns', ['category'])
    op.create_index('ix_sensitive_data_patterns_embedding_hash', 'sensitive_data_patterns', ['embedding_hash'])


def downgrade() -> None:
    """Downgrade database schema."""
    op.drop_table('sensitive_data_patterns')
    op.drop_table('audit_logs')
    op.drop_table('policies')
    op.drop_table('detections')
    op.drop_table('prompts')
    op.execute('DROP EXTENSION IF EXISTS "pgcrypto"')
    op.execute('DROP EXTENSION IF EXISTS "uuid-ossp"')
