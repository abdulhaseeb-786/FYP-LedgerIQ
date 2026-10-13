"""initial_schema

Revision ID: 2026_10_14_0001
Revises: 
Create Date: 2026-10-14 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2026_10_14_0001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. organizations
    op.create_table(
        'organizations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('slug', sa.String(length=255), nullable=False),
        sa.Column('max_projects_quota', sa.Integer(), nullable=False, server_default='5'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_organizations_id'), 'organizations', ['id'], unique=False)
    op.create_index(op.f('ix_organizations_slug'), 'organizations', ['slug'], unique=True)

    # 2. users
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('hashed_password', sa.String(length=255), nullable=False),
        sa.Column('full_name', sa.String(length=255), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('is_superuser', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=False)
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_index(op.f('ix_users_organization_id'), 'users', ['organization_id'], unique=False)

    # 3. credit_balances
    op.create_table(
        'credit_balances',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('balance', sa.Integer(), nullable=False, server_default='100'),
        sa.Column('lifetime_purchased', sa.Integer(), nullable=False, server_default='100'),
        sa.Column('lifetime_consumed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_credit_balances_id'), 'credit_balances', ['id'], unique=False)
    op.create_index(op.f('ix_credit_balances_organization_id'), 'credit_balances', ['organization_id'], unique=True)

    # 4. projects
    op.create_table(
        'projects',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('entity_name', sa.String(length=255), nullable=True),
        sa.Column('reporting_period', sa.String(length=100), nullable=True),
        sa.Column('is_archived', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('last_accessed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_projects_id'), 'projects', ['id'], unique=False)
    op.create_index(op.f('ix_projects_is_archived'), 'projects', ['is_archived'], unique=False)
    op.create_index(op.f('ix_projects_organization_id'), 'projects', ['organization_id'], unique=False)

    # 5. project_revisions
    op.create_table(
        'project_revisions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('revision_number', sa.Integer(), nullable=False),
        sa.Column('trial_balance_filename', sa.String(length=255), nullable=False),
        sa.Column('output_workbook_filename', sa.String(length=255), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='PENDING'),
        sa.Column('summary_notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_project_revisions_id'), 'project_revisions', ['id'], unique=False)
    op.create_index(op.f('ix_project_revisions_project_id'), 'project_revisions', ['project_id'], unique=False)

    # 6. statement_runs
    op.create_table(
        'statement_runs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('entity_name', sa.String(length=255), nullable=True),
        sa.Column('reporting_period', sa.String(length=100), nullable=True),
        sa.Column('input_filename', sa.String(length=255), nullable=False),
        sa.Column('input_file_path', sa.String(length=1024), nullable=True),
        sa.Column('output_filename', sa.String(length=255), nullable=True),
        sa.Column('output_file_path', sa.String(length=1024), nullable=True),
        sa.Column('data_health_report', sa.JSON(), nullable=True),
        sa.Column('verification_report', sa.JSON(), nullable=True),
        sa.Column('workbook_audit_report', sa.JSON(), nullable=True),
        sa.Column('audit_trail', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_statement_runs_id'), 'statement_runs', ['id'], unique=False)
    op.create_index(op.f('ix_statement_runs_project_id'), 'statement_runs', ['project_id'], unique=False)
    op.create_index(op.f('ix_statement_runs_user_id'), 'statement_runs', ['user_id'], unique=False)

    # 7. audit_analytics_runs
    op.create_table(
        'audit_analytics_runs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('entity_name', sa.String(length=255), nullable=False),
        sa.Column('reporting_period', sa.String(length=100), nullable=False),
        sa.Column('input_filename', sa.String(length=255), nullable=False),
        sa.Column('input_file_path', sa.String(length=1024), nullable=True),
        sa.Column('risk_score', sa.Float(), nullable=False),
        sa.Column('risk_classification', sa.String(length=50), nullable=False),
        sa.Column('benford_mad', sa.Float(), nullable=False),
        sa.Column('benford_conformity', sa.String(length=100), nullable=False),
        sa.Column('flagged_entries_count', sa.Integer(), nullable=False),
        sa.Column('report_payload', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_audit_analytics_runs_id'), 'audit_analytics_runs', ['id'], unique=False)
    op.create_index(op.f('ix_audit_analytics_runs_project_id'), 'audit_analytics_runs', ['project_id'], unique=False)
    op.create_index(op.f('ix_audit_analytics_runs_user_id'), 'audit_analytics_runs', ['user_id'], unique=False)

    # 8. digitization_run_records
    op.create_table(
        'digitization_run_records',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('document_id', sa.String(length=100), nullable=False),
        sa.Column('document_type', sa.String(length=50), nullable=False),
        sa.Column('document_no', sa.String(length=100), nullable=True),
        sa.Column('is_balanced', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('calculated_total', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('discrepancy_delta', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('recovery_applied', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('execution_profile', sa.String(length=50), nullable=False, server_default='CPU_HIGH_PRECISION_PARSER'),
        sa.Column('result_payload', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_digitization_run_records_id'), 'digitization_run_records', ['id'], unique=False)
    op.create_index(op.f('ix_digitization_run_records_document_id'), 'digitization_run_records', ['document_id'], unique=False)
    op.create_index(op.f('ix_digitization_run_records_document_type'), 'digitization_run_records', ['document_type'], unique=False)
    op.create_index(op.f('ix_digitization_run_records_project_id'), 'digitization_run_records', ['project_id'], unique=False)
    op.create_index(op.f('ix_digitization_run_records_user_id'), 'digitization_run_records', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_table('digitization_run_records')
    op.drop_table('audit_analytics_runs')
    op.drop_table('statement_runs')
    op.drop_table('project_revisions')
    op.drop_table('projects')
    op.drop_table('credit_balances')
    op.drop_table('users')
    op.drop_table('organizations')

