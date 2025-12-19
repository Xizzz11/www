-- LOOSELINE Database Schema
-- Initial migration: Create all wallet tables

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =====================================================
-- TABLE 1: users
-- =====================================================
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    uuid UUID DEFAULT uuid_generate_v4() UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    username VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    stripe_customer_id VARCHAR(100) UNIQUE,
    is_active BOOLEAN DEFAULT TRUE,
    is_verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_stripe_customer_id ON users(stripe_customer_id);

-- =====================================================
-- TABLE 2: users_balance
-- =====================================================
CREATE TABLE IF NOT EXISTS users_balance (
    id SERIAL PRIMARY KEY,
    user_id INTEGER UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    balance DECIMAL(15, 2) DEFAULT 0.00 NOT NULL CHECK (balance >= 0),
    locked_in_bets DECIMAL(15, 2) DEFAULT 0.00 NOT NULL CHECK (locked_in_bets >= 0),
    total_deposited DECIMAL(15, 2) DEFAULT 0.00 NOT NULL,
    total_withdrawn DECIMAL(15, 2) DEFAULT 0.00 NOT NULL,
    total_bet DECIMAL(15, 2) DEFAULT 0.00 NOT NULL,
    total_won DECIMAL(15, 2) DEFAULT 0.00 NOT NULL,
    currency VARCHAR(3) DEFAULT 'USD' NOT NULL,
    last_transaction_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_users_balance_user_id ON users_balance(user_id);

-- =====================================================
-- TABLE 3: balance_transactions
-- =====================================================
CREATE TABLE IF NOT EXISTS balance_transactions (
    id SERIAL PRIMARY KEY,
    uuid UUID DEFAULT uuid_generate_v4() UNIQUE NOT NULL,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    transaction_type VARCHAR(20) NOT NULL CHECK (transaction_type IN ('deposit', 'withdrawal', 'bet', 'win', 'refund', 'bonus', 'adjustment')),
    amount DECIMAL(15, 2) NOT NULL,
    balance_before DECIMAL(15, 2) NOT NULL,
    balance_after DECIMAL(15, 2) NOT NULL,
    reference_type VARCHAR(50),
    reference_id VARCHAR(100),
    description TEXT,
    metadata JSONB DEFAULT '{}',
    status VARCHAR(20) DEFAULT 'completed' CHECK (status IN ('pending', 'processing', 'completed', 'failed', 'cancelled')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_balance_transactions_user_id ON balance_transactions(user_id);
CREATE INDEX idx_balance_transactions_type ON balance_transactions(transaction_type);
CREATE INDEX idx_balance_transactions_status ON balance_transactions(status);
CREATE INDEX idx_balance_transactions_created_at ON balance_transactions(created_at DESC);
CREATE INDEX idx_balance_transactions_reference ON balance_transactions(reference_type, reference_id);

-- =====================================================
-- TABLE 4: wallet_operations
-- =====================================================
CREATE TABLE IF NOT EXISTS wallet_operations (
    id SERIAL PRIMARY KEY,
    uuid UUID DEFAULT uuid_generate_v4() UNIQUE NOT NULL,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    operation_type VARCHAR(20) NOT NULL CHECK (operation_type IN ('deposit', 'withdrawal')),
    amount DECIMAL(15, 2) NOT NULL CHECK (amount > 0),
    currency VARCHAR(3) DEFAULT 'USD' NOT NULL,
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed', 'cancelled')),
    
    -- Stripe payment info (for deposits)
    stripe_payment_intent_id VARCHAR(100),
    stripe_payment_method_id VARCHAR(100),
    stripe_charge_id VARCHAR(100),
    
    -- Withdrawal info
    withdrawal_method_id INTEGER,
    
    -- Processing info
    processor VARCHAR(50),
    processor_reference VARCHAR(100),
    fee_amount DECIMAL(15, 2) DEFAULT 0.00,
    net_amount DECIMAL(15, 2),
    
    -- Error handling
    error_code VARCHAR(50),
    error_message TEXT,
    
    -- Timestamps
    initiated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_wallet_operations_user_id ON wallet_operations(user_id);
CREATE INDEX idx_wallet_operations_type ON wallet_operations(operation_type);
CREATE INDEX idx_wallet_operations_status ON wallet_operations(status);
CREATE INDEX idx_wallet_operations_stripe_pi ON wallet_operations(stripe_payment_intent_id);
CREATE INDEX idx_wallet_operations_created_at ON wallet_operations(created_at DESC);

-- =====================================================
-- TABLE 5: payment_methods
-- =====================================================
CREATE TABLE IF NOT EXISTS payment_methods (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    stripe_payment_method_id VARCHAR(100) UNIQUE NOT NULL,
    type VARCHAR(20) NOT NULL CHECK (type IN ('card', 'bank_account', 'wallet')),
    
    -- Card details (stored safely - last 4 only)
    card_brand VARCHAR(20),
    card_last4 VARCHAR(4),
    card_exp_month INTEGER,
    card_exp_year INTEGER,
    cardholder_name VARCHAR(100),
    
    -- Status
    is_default BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    
    -- Metadata
    billing_address JSONB DEFAULT '{}',
    metadata JSONB DEFAULT '{}',
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_payment_methods_user_id ON payment_methods(user_id);
CREATE INDEX idx_payment_methods_stripe_id ON payment_methods(stripe_payment_method_id);
CREATE INDEX idx_payment_methods_default ON payment_methods(user_id, is_default) WHERE is_default = TRUE;

-- =====================================================
-- TABLE 6: withdrawal_methods
-- =====================================================
CREATE TABLE IF NOT EXISTS withdrawal_methods (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type VARCHAR(20) NOT NULL CHECK (type IN ('bank_account', 'card', 'crypto', 'ewallet')),
    
    -- Bank account details
    bank_name VARCHAR(100),
    account_holder_name VARCHAR(100),
    account_last4 VARCHAR(4),
    routing_number_last4 VARCHAR(4),
    
    -- Crypto details
    crypto_currency VARCHAR(10),
    crypto_address VARCHAR(100),
    
    -- Status
    is_verified BOOLEAN DEFAULT FALSE,
    is_default BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    
    -- Verification
    verified_at TIMESTAMP WITH TIME ZONE,
    verification_method VARCHAR(50),
    
    -- Metadata
    metadata JSONB DEFAULT '{}',
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_withdrawal_methods_user_id ON withdrawal_methods(user_id);
CREATE INDEX idx_withdrawal_methods_default ON withdrawal_methods(user_id, is_default) WHERE is_default = TRUE;

-- =====================================================
-- TABLE 7: bets
-- =====================================================
CREATE TABLE IF NOT EXISTS bets (
    id SERIAL PRIMARY KEY,
    uuid UUID DEFAULT uuid_generate_v4() UNIQUE NOT NULL,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- Bet details
    event_id VARCHAR(100) NOT NULL,
    event_name VARCHAR(255),
    market_type VARCHAR(100),
    selection VARCHAR(255),
    odds DECIMAL(10, 4) NOT NULL,
    
    -- Amounts
    stake DECIMAL(15, 2) NOT NULL CHECK (stake > 0),
    potential_win DECIMAL(15, 2) NOT NULL,
    actual_win DECIMAL(15, 2),
    
    -- Status
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'active', 'won', 'lost', 'void', 'cashout')),
    
    -- Timestamps
    placed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    settled_at TIMESTAMP WITH TIME ZONE,
    
    -- Related transactions
    stake_transaction_id INTEGER REFERENCES balance_transactions(id),
    win_transaction_id INTEGER REFERENCES balance_transactions(id),
    
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_bets_user_id ON bets(user_id);
CREATE INDEX idx_bets_status ON bets(status);
CREATE INDEX idx_bets_event_id ON bets(event_id);
CREATE INDEX idx_bets_placed_at ON bets(placed_at DESC);
CREATE INDEX idx_bets_user_status ON bets(user_id, status);

-- =====================================================
-- TABLE 8: monthly_statements
-- =====================================================
CREATE TABLE IF NOT EXISTS monthly_statements (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    year INTEGER NOT NULL,
    month INTEGER NOT NULL CHECK (month >= 1 AND month <= 12),
    
    -- Totals
    opening_balance DECIMAL(15, 2) NOT NULL,
    closing_balance DECIMAL(15, 2) NOT NULL,
    total_deposits DECIMAL(15, 2) DEFAULT 0.00,
    total_withdrawals DECIMAL(15, 2) DEFAULT 0.00,
    total_bets DECIMAL(15, 2) DEFAULT 0.00,
    total_wins DECIMAL(15, 2) DEFAULT 0.00,
    total_losses DECIMAL(15, 2) DEFAULT 0.00,
    net_profit DECIMAL(15, 2) DEFAULT 0.00,
    
    -- Stats
    num_bets INTEGER DEFAULT 0,
    num_wins INTEGER DEFAULT 0,
    num_losses INTEGER DEFAULT 0,
    win_rate DECIMAL(5, 2) DEFAULT 0.00,
    
    -- Report
    report_url VARCHAR(255),
    generated_at TIMESTAMP WITH TIME ZONE,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(user_id, year, month)
);

CREATE INDEX idx_monthly_statements_user_id ON monthly_statements(user_id);
CREATE INDEX idx_monthly_statements_period ON monthly_statements(year, month);

-- =====================================================
-- TABLE 9: audit_log
-- =====================================================
CREATE TABLE IF NOT EXISTS audit_log (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    action VARCHAR(100) NOT NULL,
    entity_type VARCHAR(50),
    entity_id VARCHAR(100),
    
    -- Request info
    ip_address INET,
    user_agent TEXT,
    request_id VARCHAR(100),
    
    -- Change details
    old_values JSONB,
    new_values JSONB,
    
    -- Status
    status VARCHAR(20) DEFAULT 'success' CHECK (status IN ('success', 'failure', 'warning')),
    error_message TEXT,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_audit_log_user_id ON audit_log(user_id);
CREATE INDEX idx_audit_log_action ON audit_log(action);
CREATE INDEX idx_audit_log_entity ON audit_log(entity_type, entity_id);
CREATE INDEX idx_audit_log_created_at ON audit_log(created_at DESC);

-- =====================================================
-- FUNCTIONS AND TRIGGERS
-- =====================================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply updated_at trigger to all tables with updated_at column
DO $$
DECLARE
    t text;
BEGIN
    FOR t IN 
        SELECT table_name 
        FROM information_schema.columns 
        WHERE column_name = 'updated_at' 
        AND table_schema = 'public'
    LOOP
        EXECUTE format('
            DROP TRIGGER IF EXISTS update_%I_updated_at ON %I;
            CREATE TRIGGER update_%I_updated_at
            BEFORE UPDATE ON %I
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
        ', t, t, t, t);
    END LOOP;
END;
$$ language 'plpgsql';

-- Function to create user balance on user creation
CREATE OR REPLACE FUNCTION create_user_balance()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO users_balance (user_id) VALUES (NEW.id);
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER create_user_balance_trigger
AFTER INSERT ON users
FOR EACH ROW
EXECUTE FUNCTION create_user_balance();

-- =====================================================
-- SAMPLE DATA (for development)
-- =====================================================

-- Insert demo user
INSERT INTO users (email, username, password_hash, stripe_customer_id, is_verified)
VALUES ('demo@looseline.com', 'demo_user', '$2b$12$dummy_hash_for_demo', 'cus_demo123', TRUE)
ON CONFLICT (email) DO NOTHING;

-- Insert demo balance (if user was created)
INSERT INTO users_balance (user_id, balance, total_deposited, total_withdrawn, total_bet, total_won)
SELECT id, 5000.00, 10000.00, 5000.00, 2500.00, 3840.00
FROM users WHERE email = 'demo@looseline.com'
ON CONFLICT (user_id) DO NOTHING;

-- Insert demo payment methods
INSERT INTO payment_methods (user_id, stripe_payment_method_id, type, card_brand, card_last4, card_exp_month, card_exp_year, is_default)
SELECT id, 'pm_demo_visa_4242', 'card', 'Visa', '4242', 12, 2025, TRUE
FROM users WHERE email = 'demo@looseline.com'
ON CONFLICT (stripe_payment_method_id) DO NOTHING;

INSERT INTO payment_methods (user_id, stripe_payment_method_id, type, card_brand, card_last4, card_exp_month, card_exp_year, is_default)
SELECT id, 'pm_demo_mc_5555', 'card', 'Mastercard', '5555', 6, 2026, FALSE
FROM users WHERE email = 'demo@looseline.com'
ON CONFLICT (stripe_payment_method_id) DO NOTHING;

-- Insert demo withdrawal methods
INSERT INTO withdrawal_methods (user_id, type, bank_name, account_holder_name, account_last4, is_verified, is_default)
SELECT id, 'bank_account', 'Chase Bank', 'Demo User', '7890', TRUE, TRUE
FROM users WHERE email = 'demo@looseline.com';

COMMIT;

