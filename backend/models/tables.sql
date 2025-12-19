-- ============================================================================
-- LOOSELINE: SQL миграции для модуля управления деньгами
-- Создание 8 таблиц БД для работы с балансом и Stripe
-- ============================================================================

-- ============================================================================
-- ТАБЛИЦА 1: users (Пользователи - обновлённая)
-- ============================================================================
-- Основная таблица пользователей с поддержкой Stripe
-- stripe_customer_id нужен для сохранения способов оплаты в Stripe
-- Один пользователь → один Stripe Customer

CREATE TABLE IF NOT EXISTS users (
    id VARCHAR(20) PRIMARY KEY,
    email VARCHAR(100) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    stripe_customer_id VARCHAR(100) UNIQUE,
    is_verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Индексы для быстрого поиска
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_stripe_customer ON users(stripe_customer_id);

COMMENT ON TABLE users IS 'Основная таблица пользователей с интеграцией Stripe';
COMMENT ON COLUMN users.stripe_customer_id IS 'ID клиента в Stripe для сохранения способов оплаты';


-- ============================================================================
-- ТАБЛИЦА 2: users_balance (Основной баланс пользователя)
-- ============================================================================
-- Хранит текущий баланс и всю статистику по финансам пользователя
-- total_deposited: сколько всего пополнил
-- total_withdrawn: сколько всего вывел
-- total_bet: сколько всего поставил
-- total_won: сколько всего выиграл
-- total_lost: сколько всего проиграл

CREATE TABLE IF NOT EXISTS users_balance (
    user_id VARCHAR(20) PRIMARY KEY,
    balance DECIMAL(15,2) NOT NULL DEFAULT 0.00,
    total_deposited DECIMAL(15,2) DEFAULT 0.00,
    total_withdrawn DECIMAL(15,2) DEFAULT 0.00,
    total_bet DECIMAL(15,2) DEFAULT 0.00,
    total_won DECIMAL(15,2) DEFAULT 0.00,
    total_lost DECIMAL(15,2) DEFAULT 0.00,
    currency VARCHAR(3) DEFAULT 'USD',
    last_transaction TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_user_balance ON users_balance(user_id);

COMMENT ON TABLE users_balance IS 'Основной баланс и статистика пользователя';
COMMENT ON COLUMN users_balance.balance IS 'Текущий баланс пользователя';
COMMENT ON COLUMN users_balance.total_deposited IS 'Сумма всех пополнений';
COMMENT ON COLUMN users_balance.total_withdrawn IS 'Сумма всех выводов';
COMMENT ON COLUMN users_balance.total_bet IS 'Сумма всех ставок';
COMMENT ON COLUMN users_balance.total_won IS 'Сумма всех выигрышей';
COMMENT ON COLUMN users_balance.total_lost IS 'Сумма всех проигрышей';


-- ============================================================================
-- ТАБЛИЦА 3: balance_transactions (История всех транзакций)
-- ============================================================================
-- Полная история КАЖДОЙ транзакции для аудита
-- balance_before и balance_after для проверки целостности
-- stripe_payment_intent_id для связи со Stripe

CREATE TABLE IF NOT EXISTS balance_transactions (
    transaction_id BIGSERIAL PRIMARY KEY,
    user_id VARCHAR(20) NOT NULL,
    transaction_type VARCHAR(30) NOT NULL,
    amount DECIMAL(15,2) NOT NULL,
    balance_before DECIMAL(15,2) NOT NULL,
    balance_after DECIMAL(15,2) NOT NULL,
    status VARCHAR(20) DEFAULT 'completed',
    description TEXT,
    related_entity_type VARCHAR(20),
    related_entity_id INTEGER,
    stripe_payment_intent_id VARCHAR(100),
    stripe_charge_id VARCHAR(100),
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    processed_at TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_user_transactions ON balance_transactions(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_transaction_type ON balance_transactions(transaction_type);
CREATE INDEX IF NOT EXISTS idx_stripe_intent_transactions ON balance_transactions(stripe_payment_intent_id);
CREATE INDEX IF NOT EXISTS idx_transaction_status ON balance_transactions(status);

COMMENT ON TABLE balance_transactions IS 'История всех финансовых транзакций пользователя';
COMMENT ON COLUMN balance_transactions.transaction_type IS 'Тип: deposit, withdrawal, bet_placed, bet_won, bet_lost, bet_cancelled, coupon_won, coupon_lost, bonus_added, fee_charged, refund';
COMMENT ON COLUMN balance_transactions.status IS 'Статус: completed, pending, failed, cancelled';


-- ============================================================================
-- ТАБЛИЦА 4: wallet_operations (Операции пополнения/вывода)
-- ============================================================================
-- Очередь операций пополнения/вывода через Stripe
-- Может быть в процессе (pending), успешно (completed), ошибка (failed)

CREATE TABLE IF NOT EXISTS wallet_operations (
    operation_id BIGSERIAL PRIMARY KEY,
    user_id VARCHAR(20) NOT NULL,
    operation_type VARCHAR(20) NOT NULL,
    amount DECIMAL(15,2) NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    payment_method VARCHAR(50),
    stripe_payment_intent_id VARCHAR(100),
    stripe_charge_id VARCHAR(100),
    stripe_payment_method_id VARCHAR(100),
    error_message TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,
    expires_at TIMESTAMP DEFAULT (NOW() + INTERVAL '24 hours'),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(stripe_payment_intent_id)
);

CREATE INDEX IF NOT EXISTS idx_user_operations ON wallet_operations(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_stripe_intent_operations ON wallet_operations(stripe_payment_intent_id);
CREATE INDEX IF NOT EXISTS idx_operation_status ON wallet_operations(status);
CREATE INDEX IF NOT EXISTS idx_operation_type ON wallet_operations(operation_type);

COMMENT ON TABLE wallet_operations IS 'Операции пополнения и вывода средств через Stripe';
COMMENT ON COLUMN wallet_operations.operation_type IS 'Тип: deposit, withdrawal';
COMMENT ON COLUMN wallet_operations.status IS 'Статус: pending, completed, failed, cancelled';


-- ============================================================================
-- ТАБЛИЦА 5: payment_methods (Сохранённые способы оплаты)
-- ============================================================================
-- Сохранённые способы оплаты для быстрого пополнения
-- stripe_payment_method_id для работы со Stripe

CREATE TABLE IF NOT EXISTS payment_methods (
    method_id BIGSERIAL PRIMARY KEY,
    user_id VARCHAR(20) NOT NULL,
    stripe_payment_method_id VARCHAR(100) UNIQUE NOT NULL,
    payment_type VARCHAR(30) NOT NULL,
    card_brand VARCHAR(20),
    card_last4 VARCHAR(4),
    card_exp_month INTEGER,
    card_exp_year INTEGER,
    bank_name VARCHAR(100),
    bank_account_last4 VARCHAR(4),
    is_default BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    last_used TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_user_methods ON payment_methods(user_id);
CREATE INDEX IF NOT EXISTS idx_payment_method_stripe ON payment_methods(stripe_payment_method_id);
CREATE INDEX IF NOT EXISTS idx_default_method ON payment_methods(user_id, is_default) WHERE is_default = TRUE;

COMMENT ON TABLE payment_methods IS 'Сохранённые способы оплаты пользователей';
COMMENT ON COLUMN payment_methods.payment_type IS 'Тип: card, bank_account';


-- ============================================================================
-- ТАБЛИЦА 6: withdrawal_methods (Методы вывода)
-- ============================================================================
-- Сохранённые методы вывода средств
-- Пользователь должен верифицировать перед выводом

CREATE TABLE IF NOT EXISTS withdrawal_methods (
    method_id BIGSERIAL PRIMARY KEY,
    user_id VARCHAR(20) NOT NULL,
    withdrawal_type VARCHAR(30) NOT NULL,
    bank_account_number VARCHAR(100),
    bank_code VARCHAR(20),
    bank_name VARCHAR(100),
    account_holder_name VARCHAR(100),
    swift_code VARCHAR(20),
    iban VARCHAR(100),
    crypto_wallet_address VARCHAR(200),
    is_default BOOLEAN DEFAULT FALSE,
    is_verified BOOLEAN DEFAULT FALSE,
    verification_status VARCHAR(20) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT NOW(),
    verified_at TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_user_withdrawal_methods ON withdrawal_methods(user_id);
CREATE INDEX IF NOT EXISTS idx_withdrawal_verified ON withdrawal_methods(user_id, is_verified) WHERE is_verified = TRUE;

COMMENT ON TABLE withdrawal_methods IS 'Методы вывода средств пользователей';
COMMENT ON COLUMN withdrawal_methods.withdrawal_type IS 'Тип: bank_transfer, crypto';
COMMENT ON COLUMN withdrawal_methods.verification_status IS 'Статус верификации: pending, verified, rejected';


-- ============================================================================
-- ТАБЛИЦА 7: monthly_statements (Месячные отчёты)
-- ============================================================================
-- Автоматически генерируемые месячные отчёты
-- Для экспорта и налоговых отчётов

CREATE TABLE IF NOT EXISTS monthly_statements (
    statement_id BIGSERIAL PRIMARY KEY,
    user_id VARCHAR(20) NOT NULL,
    year INTEGER NOT NULL,
    month INTEGER NOT NULL,
    opening_balance DECIMAL(15,2),
    closing_balance DECIMAL(15,2),
    total_deposits DECIMAL(15,2) DEFAULT 0.00,
    total_withdrawals DECIMAL(15,2) DEFAULT 0.00,
    total_bets DECIMAL(15,2) DEFAULT 0.00,
    total_wins DECIMAL(15,2) DEFAULT 0.00,
    total_losses DECIMAL(15,2) DEFAULT 0.00,
    net_profit DECIMAL(15,2),
    roi_percent DECIMAL(10,2),
    transaction_count INTEGER DEFAULT 0,
    win_rate_percent DECIMAL(10,2),
    generated_at TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(user_id, year, month)
);

CREATE INDEX IF NOT EXISTS idx_user_statements ON monthly_statements(user_id, year, month);

COMMENT ON TABLE monthly_statements IS 'Месячные финансовые отчёты пользователей';


-- ============================================================================
-- ТАБЛИЦА 8: audit_log (Логирование для безопасности)
-- ============================================================================
-- Полный аудит всех операций для безопасности и compliance
-- Отслеживание кто, когда и откуда сделал операцию

CREATE TABLE IF NOT EXISTS audit_log (
    log_id BIGSERIAL PRIMARY KEY,
    user_id VARCHAR(20) NOT NULL,
    action VARCHAR(50) NOT NULL,
    amount DECIMAL(15,2),
    ip_address INET,
    user_agent TEXT,
    status VARCHAR(20),
    details JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_user_audit ON audit_log(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_action ON audit_log(action);
CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_log(created_at DESC);

COMMENT ON TABLE audit_log IS 'Аудит всех операций для безопасности';
COMMENT ON COLUMN audit_log.action IS 'Действие: deposit_initiated, deposit_completed, withdrawal_initiated, withdrawal_completed, balance_checked, export_requested, suspicious_activity, stripe_webhook_received';


-- ============================================================================
-- ТАБЛИЦА 9: bets (Ставки - для связи с getBetHistory)
-- ============================================================================
-- Таблица ставок для связи с методом getBetHistory

CREATE TABLE IF NOT EXISTS bets (
    bet_id BIGSERIAL PRIMARY KEY,
    user_id VARCHAR(20) NOT NULL,
    event_id INTEGER NOT NULL,
    odds_id INTEGER,
    bet_type VARCHAR(20) DEFAULT 'single',
    bet_amount DECIMAL(15,2) NOT NULL,
    coefficient DECIMAL(10,3) NOT NULL,
    potential_win DECIMAL(15,2) NOT NULL,
    status VARCHAR(20) DEFAULT 'open',
    result VARCHAR(20),
    actual_win DECIMAL(15,2),
    placed_at TIMESTAMP DEFAULT NOW(),
    resolved_at TIMESTAMP,
    metadata JSONB,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_user_bets ON bets(user_id, placed_at DESC);
CREATE INDEX IF NOT EXISTS idx_bet_status ON bets(status);
CREATE INDEX IF NOT EXISTS idx_bet_result ON bets(result);

COMMENT ON TABLE bets IS 'Таблица ставок пользователей';
COMMENT ON COLUMN bets.status IS 'Статус: open, resolved, cancelled';
COMMENT ON COLUMN bets.result IS 'Результат: win, loss, refund';


-- ============================================================================
-- ТРИГГЕР: Автообновление updated_at
-- ============================================================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Триггер для users
DROP TRIGGER IF EXISTS update_users_updated_at ON users;
CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Триггер для users_balance
DROP TRIGGER IF EXISTS update_users_balance_updated_at ON users_balance;
CREATE TRIGGER update_users_balance_updated_at
    BEFORE UPDATE ON users_balance
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();


-- ============================================================================
-- ФУНКЦИЯ: Создание баланса при регистрации пользователя
-- ============================================================================

CREATE OR REPLACE FUNCTION create_user_balance()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO users_balance (user_id, balance, currency)
    VALUES (NEW.id, 0.00, 'USD')
    ON CONFLICT (user_id) DO NOTHING;
    RETURN NEW;
END;
$$ language 'plpgsql';

DROP TRIGGER IF EXISTS create_balance_on_user_insert ON users;
CREATE TRIGGER create_balance_on_user_insert
    AFTER INSERT ON users
    FOR EACH ROW
    EXECUTE FUNCTION create_user_balance();


-- ============================================================================
-- GRANT права (для production)
-- ============================================================================

-- GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO looseline_app;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO looseline_app;


