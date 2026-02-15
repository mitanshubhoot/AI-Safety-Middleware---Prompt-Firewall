"""Add enterprise models for multi-tenancy and authentication

Revision ID: 002
Revises: 001
Create Date: 2024-02-14 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade database schema."""
    
    # Create organizations table
    op.create_table(
        'organizations',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('tier', sa.String(length=50), nullable=False, server_default='free', comment='Subscription tier: free, pro, enterprise'),
        sa.Column('rate_limit_per_minute', sa.Integer(), nullable=False, server_default='100'),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('settings', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )
    
    # Create users table
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('hashed_password', sa.String(length=255), nullable=False),
        sa.Column('full_name', sa.String(length=200), nullable=True),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False, comment='Foreign key to organizations'),
        sa.Column('role', sa.String(length=50), nullable=False, server_default='user', comment='Role: admin, user, viewer'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('is_verified', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('last_login', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email')
    )
    op.create_index('ix_users_email', 'users', ['email'])
    op.create_index('ix_users_organization_id', 'users', ['organization_id'])
    
    # Create api_keys table
    op.create_table(
        'api_keys',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('key_hash', sa.String(length=255), nullable=False, comment='SHA-256 hash of the API key'),
        sa.Column('key_prefix', sa.String(length=20), nullable=False, comment='First 8 chars of key for identification'),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('scopes', postgresql.JSON(astext_type=sa.Text()), nullable=False, comment='List of allowed scopes/permissions'),
        sa.Column('rate_limit_override', sa.Integer(), nullable=True, comment='Override organization rate limit'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('expires_at', sa.DateTime(), nullable=True, comment='Key expiration date'),
        sa.Column('last_used', sa.DateTime(), nullable=True, comment='Last time key was used'),
        sa.Column('usage_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('key_hash')
    )
    op.create_index('ix_api_keys_key_hash', 'api_keys', ['key_hash'], unique=True)
    op.create_index('ix_api_keys_organization_id', 'api_keys', ['organization_id'])
    op.create_index('ix_api_keys_user_id', 'api_keys', ['user_id'])
    
    # Create webhook_endpoints table
    op.create_table(
        'webhook_endpoints',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('url', sa.Text(), nullable=False),
        sa.Column('secret', sa.String(length=255), nullable=False, comment='Secret for signing webhook payloads'),
        sa.Column('events', postgresql.JSON(astext_type=sa.Text()), nullable=False, comment='List of events to trigger webhook'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('failure_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_triggered', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_webhook_endpoints_organization_id', 'webhook_endpoints', ['organization_id'])
    
    # Create rate_limit_logs table
    op.create_table(
        'rate_limit_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('api_key_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('endpoint', sa.String(length=255), nullable=False),
        sa.Column('request_count', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('window_start', sa.DateTime(), nullable=False, comment='Start of the rate limit window'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_rate_limit_logs_organization_id', 'rate_limit_logs', ['organization_id'])
    op.create_index('ix_rate_limit_logs_api_key_id', 'rate_limit_logs', ['api_key_id'])
    op.create_index('ix_rate_limit_logs_window_start', 'rate_limit_logs', ['window_start'])
    
    # Add organization_id to prompts table for multi-tenancy
    op.add_column('prompts', sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.create_index('ix_prompts_organization_id', 'prompts', ['organization_id'])


def downgrade() -> None:
    """Downgrade database schema."""
    op.drop_index('ix_prompts_organization_id', table_name='prompts')
    op.drop_column('prompts', 'organization_id')
    
    op.drop_table('rate_limit_logs')
    op.drop_table('webhook_endpoints')
    op.drop_table('api_keys')
    op.drop_table('users')
    op.drop_table('organizations')
