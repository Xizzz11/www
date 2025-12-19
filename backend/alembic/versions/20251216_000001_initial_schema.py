"""Initial schema - Create all wallet tables

Revision ID: 20251216_000001
Revises: 
Create Date: 2025-12-16

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20251216_000001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create UUID extension
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    
    # === TABLE 1: users ===
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('uuid', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), unique=True, nullable=False),
        sa.Column('email', sa.String(255), unique=True, nullable=False),
        sa.Column('username', sa.String(100), unique=True, nullable=False),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('stripe_customer_id', sa.String(100), unique=True),
        sa.Column('is_active', sa.Boolean(), server_default='true'),
        sa.Column('is_verified', sa.Boolean(), server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP')),
    )
    op.create_index('idx_users_email', 'users', ['email'])
    op.create_index('idx_users_stripe_customer_id', 'users', ['stripe_customer_id'])

    # === TABLE 2: users_balance ===
    op.create_table(
        'users_balance',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), unique=True, nullable=False),
        sa.Column('balance', sa.Numeric(15, 2), server_default='0.00', nullable=False),
        sa.Column('locked_in_bets', sa.Numeric(15, 2), server_default='0.00', nullable=False),
        sa.Column('total_deposited', sa.Numeric(15, 2), server_default='0.00', nullable=False),
        sa.Column('total_withdrawn', sa.Numeric(15, 2), server_default='0.00', nullable=False),
        sa.Column('total_bet', sa.Numeric(15, 2), server_default='0.00', nullable=False),
        sa.Column('total_won', sa.Numeric(15, 2), server_default='0.00', nullable=False),
        sa.Column('currency', sa.String(3), server_default='USD', nullable=False),
        sa.Column('last_transaction_at', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.CheckConstraint('balance >= 0', name='check_balance_positive'),
        sa.CheckConstraint('locked_in_bets >= 0', name='check_locked_positive'),
    )
    op.create_index('idx_users_balance_user_id', 'users_balance', ['user_id'])

    # === TABLE 3: balance_transactions ===
    op.create_table(
        'balance_transactions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('uuid', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), unique=True, nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('transaction_type', sa.String(20), nullable=False),
        sa.Column('amount', sa.Numeric(15, 2), nullable=False),
        sa.Column('balance_before', sa.Numeric(15, 2), nullable=False),
        sa.Column('balance_after', sa.Numeric(15, 2), nullable=False),
        sa.Column('reference_type', sa.String(50)),
        sa.Column('reference_id', sa.String(100)),
        sa.Column('description', sa.Text()),
        sa.Column('metadata', postgresql.JSONB(), server_default='{}'),
        sa.Column('status', sa.String(20), server_default='completed'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.CheckConstraint("transaction_type IN ('deposit', 'withdrawal', 'bet', 'win', 'refund', 'bonus', 'adjustment')", name='check_transaction_type'),
        sa.CheckConstraint("status IN ('pending', 'processing', 'completed', 'failed', 'cancelled')", name='check_transaction_status'),
    )
    op.create_index('idx_balance_transactions_user_id', 'balance_transactions', ['user_id'])
    op.create_index('idx_balance_transactions_type', 'balance_transactions', ['transaction_type'])
    op.create_index('idx_balance_transactions_status', 'balance_transactions', ['status'])
    op.create_index('idx_balance_transactions_created_at', 'balance_transactions', ['created_at'])
    op.create_index('idx_balance_transactions_reference', 'balance_transactions', ['reference_type', 'reference_id'])

    # === TABLE 4: wallet_operations ===
    op.create_table(
        'wallet_operations',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('uuid', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), unique=True, nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('operation_type', sa.String(20), nullable=False),
        sa.Column('amount', sa.Numeric(15, 2), nullable=False),
        sa.Column('currency', sa.String(3), server_default='USD', nullable=False),
        sa.Column('status', sa.String(20), server_default='pending'),
        sa.Column('stripe_payment_intent_id', sa.String(100)),
        sa.Column('stripe_payment_method_id', sa.String(100)),
        sa.Column('stripe_charge_id', sa.String(100)),
        sa.Column('withdrawal_method_id', sa.Integer()),
        sa.Column('processor', sa.String(50)),
        sa.Column('processor_reference', sa.String(100)),
        sa.Column('fee_amount', sa.Numeric(15, 2), server_default='0.00'),
        sa.Column('net_amount', sa.Numeric(15, 2)),
        sa.Column('error_code', sa.String(50)),
        sa.Column('error_message', sa.Text()),
        sa.Column('initiated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('processed_at', sa.DateTime(timezone=True)),
        sa.Column('completed_at', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.CheckConstraint("operation_type IN ('deposit', 'withdrawal')", name='check_operation_type'),
        sa.CheckConstraint("status IN ('pending', 'processing', 'completed', 'failed', 'cancelled')", name='check_operation_status'),
        sa.CheckConstraint('amount > 0', name='check_amount_positive'),
    )
    op.create_index('idx_wallet_operations_user_id', 'wallet_operations', ['user_id'])
    op.create_index('idx_wallet_operations_type', 'wallet_operations', ['operation_type'])
    op.create_index('idx_wallet_operations_status', 'wallet_operations', ['status'])
    op.create_index('idx_wallet_operations_stripe_pi', 'wallet_operations', ['stripe_payment_intent_id'])
    op.create_index('idx_wallet_operations_created_at', 'wallet_operations', ['created_at'])

    # === TABLE 5: payment_methods ===
    op.create_table(
        'payment_methods',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('stripe_payment_method_id', sa.String(100), unique=True, nullable=False),
        sa.Column('type', sa.String(20), nullable=False),
        sa.Column('card_brand', sa.String(20)),
        sa.Column('card_last4', sa.String(4)),
        sa.Column('card_exp_month', sa.Integer()),
        sa.Column('card_exp_year', sa.Integer()),
        sa.Column('cardholder_name', sa.String(100)),
        sa.Column('is_default', sa.Boolean(), server_default='false'),
        sa.Column('is_active', sa.Boolean(), server_default='true'),
        sa.Column('billing_address', postgresql.JSONB(), server_default='{}'),
        sa.Column('metadata', postgresql.JSONB(), server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.CheckConstraint("type IN ('card', 'bank_account', 'wallet')", name='check_payment_method_type'),
    )
    op.create_index('idx_payment_methods_user_id', 'payment_methods', ['user_id'])
    op.create_index('idx_payment_methods_stripe_id', 'payment_methods', ['stripe_payment_method_id'])

    # === TABLE 6: withdrawal_methods ===
    op.create_table(
        'withdrawal_methods',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('type', sa.String(20), nullable=False),
        sa.Column('bank_name', sa.String(100)),
        sa.Column('account_holder_name', sa.String(100)),
        sa.Column('account_last4', sa.String(4)),
        sa.Column('routing_number_last4', sa.String(4)),
        sa.Column('crypto_currency', sa.String(10)),
        sa.Column('crypto_address', sa.String(100)),
        sa.Column('is_verified', sa.Boolean(), server_default='false'),
        sa.Column('is_default', sa.Boolean(), server_default='false'),
        sa.Column('is_active', sa.Boolean(), server_default='true'),
        sa.Column('verified_at', sa.DateTime(timezone=True)),
        sa.Column('verification_method', sa.String(50)),
        sa.Column('metadata', postgresql.JSONB(), server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.CheckConstraint("type IN ('bank_account', 'card', 'crypto', 'ewallet')", name='check_withdrawal_method_type'),
    )
    op.create_index('idx_withdrawal_methods_user_id', 'withdrawal_methods', ['user_id'])

    # === TABLE 7: bets ===
    op.create_table(
        'bets',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('uuid', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), unique=True, nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('event_id', sa.String(100), nullable=False),
        sa.Column('event_name', sa.String(255)),
        sa.Column('market_type', sa.String(100)),
        sa.Column('selection', sa.String(255)),
        sa.Column('odds', sa.Numeric(10, 4), nullable=False),
        sa.Column('stake', sa.Numeric(15, 2), nullable=False),
        sa.Column('potential_win', sa.Numeric(15, 2), nullable=False),
        sa.Column('actual_win', sa.Numeric(15, 2)),
        sa.Column('status', sa.String(20), server_default='pending'),
        sa.Column('placed_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('settled_at', sa.DateTime(timezone=True)),
        sa.Column('stake_transaction_id', sa.Integer(), sa.ForeignKey('balance_transactions.id')),
        sa.Column('win_transaction_id', sa.Integer(), sa.ForeignKey('balance_transactions.id')),
        sa.Column('metadata', postgresql.JSONB(), server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.CheckConstraint("status IN ('pending', 'active', 'won', 'lost', 'void', 'cashout')", name='check_bet_status'),
        sa.CheckConstraint('stake > 0', name='check_stake_positive'),
    )
    op.create_index('idx_bets_user_id', 'bets', ['user_id'])
    op.create_index('idx_bets_status', 'bets', ['status'])
    op.create_index('idx_bets_event_id', 'bets', ['event_id'])
    op.create_index('idx_bets_placed_at', 'bets', ['placed_at'])
    op.create_index('idx_bets_user_status', 'bets', ['user_id', 'status'])

    # === TABLE 8: monthly_statements ===
    op.create_table(
        'monthly_statements',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('year', sa.Integer(), nullable=False),
        sa.Column('month', sa.Integer(), nullable=False),
        sa.Column('opening_balance', sa.Numeric(15, 2), nullable=False),
        sa.Column('closing_balance', sa.Numeric(15, 2), nullable=False),
        sa.Column('total_deposits', sa.Numeric(15, 2), server_default='0.00'),
        sa.Column('total_withdrawals', sa.Numeric(15, 2), server_default='0.00'),
        sa.Column('total_bets', sa.Numeric(15, 2), server_default='0.00'),
        sa.Column('total_wins', sa.Numeric(15, 2), server_default='0.00'),
        sa.Column('total_losses', sa.Numeric(15, 2), server_default='0.00'),
        sa.Column('net_profit', sa.Numeric(15, 2), server_default='0.00'),
        sa.Column('num_bets', sa.Integer(), server_default='0'),
        sa.Column('num_wins', sa.Integer(), server_default='0'),
        sa.Column('num_losses', sa.Integer(), server_default='0'),
        sa.Column('win_rate', sa.Numeric(5, 2), server_default='0.00'),
        sa.Column('report_url', sa.String(255)),
        sa.Column('generated_at', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.UniqueConstraint('user_id', 'year', 'month', name='uq_monthly_statement'),
        sa.CheckConstraint('month >= 1 AND month <= 12', name='check_month_valid'),
    )
    op.create_index('idx_monthly_statements_user_id', 'monthly_statements', ['user_id'])
    op.create_index('idx_monthly_statements_period', 'monthly_statements', ['year', 'month'])

    # === TABLE 9: audit_log ===
    op.create_table(
        'audit_log',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL')),
        sa.Column('action', sa.String(100), nullable=False),
        sa.Column('entity_type', sa.String(50)),
        sa.Column('entity_id', sa.String(100)),
        sa.Column('ip_address', postgresql.INET()),
        sa.Column('user_agent', sa.Text()),
        sa.Column('request_id', sa.String(100)),
        sa.Column('old_values', postgresql.JSONB()),
        sa.Column('new_values', postgresql.JSONB()),
        sa.Column('status', sa.String(20), server_default='success'),
        sa.Column('error_message', sa.Text()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.CheckConstraint("status IN ('success', 'failure', 'warning')", name='check_audit_status'),
    )
    op.create_index('idx_audit_log_user_id', 'audit_log', ['user_id'])
    op.create_index('idx_audit_log_action', 'audit_log', ['action'])
    op.create_index('idx_audit_log_entity', 'audit_log', ['entity_type', 'entity_id'])
    op.create_index('idx_audit_log_created_at', 'audit_log', ['created_at'])

    # === Create updated_at trigger function ===
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = CURRENT_TIMESTAMP;
            RETURN NEW;
        END;
        $$ language 'plpgsql';
    """)

    # Apply trigger to tables with updated_at
    tables_with_updated_at = [
        'users', 'users_balance', 'wallet_operations', 
        'payment_methods', 'withdrawal_methods', 'bets'
    ]
    for table in tables_with_updated_at:
        op.execute(f"""
            CREATE TRIGGER update_{table}_updated_at
            BEFORE UPDATE ON {table}
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
        """)

    # === Create user balance trigger ===
    op.execute("""
        CREATE OR REPLACE FUNCTION create_user_balance()
        RETURNS TRIGGER AS $$
        BEGIN
            INSERT INTO users_balance (user_id) VALUES (NEW.id);
            RETURN NEW;
        END;
        $$ language 'plpgsql';
    """)

    op.execute("""
        CREATE TRIGGER create_user_balance_trigger
        AFTER INSERT ON users
        FOR EACH ROW
        EXECUTE FUNCTION create_user_balance();
    """)


def downgrade() -> None:
    # Drop triggers
    op.execute('DROP TRIGGER IF EXISTS create_user_balance_trigger ON users')
    op.execute('DROP FUNCTION IF EXISTS create_user_balance()')
    
    tables_with_updated_at = [
        'users', 'users_balance', 'wallet_operations', 
        'payment_methods', 'withdrawal_methods', 'bets'
    ]
    for table in tables_with_updated_at:
        op.execute(f'DROP TRIGGER IF EXISTS update_{table}_updated_at ON {table}')
    
    op.execute('DROP FUNCTION IF EXISTS update_updated_at_column()')

    # Drop tables in reverse order
    op.drop_table('audit_log')
    op.drop_table('monthly_statements')
    op.drop_table('bets')
    op.drop_table('withdrawal_methods')
    op.drop_table('payment_methods')
    op.drop_table('wallet_operations')
    op.drop_table('balance_transactions')
    op.drop_table('users_balance')
    op.drop_table('users')

