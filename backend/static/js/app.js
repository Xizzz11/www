/**
 * LOOSELINE Wallet - Single Page Application
 * Adapted for FastAPI backend
 */

const CONFIG = {
    API_BASE: '/api/wallet',
    USER_ID: 'user_123',
    STRIPE_PK: document.querySelector('meta[name="stripe-publishable-key"]')?.content || ''
};

let state = {
    balance: 0,
    availableBalance: 0,
    lockedBalance: 0,
    totalDeposited: 0,
    totalWithdrawn: 0,
    netProfit: 0,
    winRate: 0,
    roi: 0,
    totalBets: 0,
    transactions: [],
    paymentMethods: [],
    withdrawalMethods: [],
    historyPage: 1,
    historyPerPage: 20,
    sortField: 'date',
    sortOrder: 'desc',
    selectedPaymentMethod: 'new'
};

let stripe, cardElement, balanceChart;

// === API HELPERS ===
async function apiRequest(endpoint, options = {}) {
    const url = `${CONFIG.API_BASE}${endpoint}`;
    const defaultOptions = {
        headers: {
            'Content-Type': 'application/json',
            'X-User-ID': CONFIG.USER_ID
        }
    };

    const config = {
        ...defaultOptions,
        ...options,
        headers: {
            ...defaultOptions.headers,
            ...(options.headers || {})
        }
    };

    if (options.body && typeof options.body === 'object') {
        config.body = JSON.stringify(options.body);
    }

    try {
        const response = await fetch(url, config);
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.detail || data.error || 'Ошибка запроса');
        }
        
        return data;
    } catch (error) {
        console.error('API Error:', error);
        throw error;
    }
}

// === INIT ===
document.addEventListener('DOMContentLoaded', async () => {
    initStripe();
    await loadBalance();
    await loadHistory();
    await loadPaymentMethods();
    await loadWithdrawalMethods();
    initChart();
    setDefaultDates();
    
    // Close dropdown on outside click
    document.addEventListener('click', (e) => {
        if (!e.target.closest('.balance-dropdown')) {
            document.querySelector('.balance-dropdown')?.classList.remove('open');
        }
    });
});

function initStripe() {
    if (!CONFIG.STRIPE_PK) {
        console.log('Stripe not configured');
        return;
    }
    
    try {
        stripe = Stripe(CONFIG.STRIPE_PK);
        const elements = stripe.elements();
        cardElement = elements.create('card', {
            style: {
                base: { fontSize: '16px', fontFamily: 'Inter, sans-serif', color: '#2c3e50' }
            }
        });
        cardElement.mount('#card-element');
        cardElement.on('change', (e) => {
            document.getElementById('card-errors').textContent = e.error ? e.error.message : '';
        });
    } catch (e) { 
        console.log('Stripe unavailable', e); 
    }
}

// === LOAD DATA ===
async function loadBalance() {
    try {
        const data = await apiRequest('/balance');
        
        state.balance = parseFloat(data.balance?.total || 0);
        state.availableBalance = parseFloat(data.balance?.available || 0);
        state.lockedBalance = parseFloat(data.balance?.pending || 0);
        
        if (data.metrics) {
            state.totalDeposited = parseFloat(data.metrics.total_deposited || 0);
            state.totalWithdrawn = parseFloat(data.metrics.total_withdrawn || 0);
            state.netProfit = parseFloat(data.metrics.net_profit || 0);
            state.winRate = parseFloat(data.metrics.win_rate || 0);
            state.roi = parseFloat(data.metrics.roi || 0);
            state.totalBets = parseInt(data.metrics.total_bets || 0);
        }
        
        updateDisplays();
    } catch (error) {
        console.error('Error loading balance:', error);
        showToast('Ошибка загрузки баланса', 'error');
    }
}

async function loadHistory() {
    try {
        const filter = document.getElementById('historyFilter')?.value || 'all';
        const endpoint = filter === 'all' ? 
            `/history?offset=${(state.historyPage - 1) * state.historyPerPage}&limit=${state.historyPerPage}` :
            `/history?type=${filter}&offset=${(state.historyPage - 1) * state.historyPerPage}&limit=${state.historyPerPage}`;
        
        const data = await apiRequest(endpoint);
        
        if (data.history) {
            state.transactions = data.history.map(item => ({
                id: item.transaction_id || item.bet_id || Date.now(),
                type: item.type || (item.amount >= 0 ? 'deposit' : 'withdrawal'),
                amount: Math.abs(parseFloat(item.amount || 0)),
                status: item.status || 'completed',
                created_at: item.date || item.created_at || item.placed_at,
                description: item.description || item.type || 'Операция'
            }));
        }
        
        renderHistory();
        updateChart();
    } catch (error) {
        console.error('Error loading history:', error);
        showToast('Ошибка загрузки истории', 'error');
    }
}

async function loadPaymentMethods() {
    try {
        const data = await apiRequest('/payment-methods');
        
        if (data.payment_methods) {
            state.paymentMethods = data.payment_methods.map(pm => ({
                id: pm.method_id,
                brand: pm.card_brand || 'Card',
                last4: pm.last4,
                is_default: pm.is_default || false
            }));
        }
        
        renderPaymentMethods();
    } catch (error) {
        console.error('Error loading payment methods:', error);
    }
}

async function loadWithdrawalMethods() {
    try {
        const data = await apiRequest('/withdrawal-methods');
        
        if (data.methods) {
            state.withdrawalMethods = data.methods.map(m => ({
                id: m.method_id,
                name: m.bank_name || 'Bank',
                last4: m.last4
            }));
        }
        
        renderPaymentMethods();
    } catch (error) {
        console.error('Error loading withdrawal methods:', error);
    }
}

// === DISPLAYS ===
function updateDisplays() {
    document.getElementById('headerBalance').textContent = formatCurrency(state.balance);
    document.getElementById('dropdownBalance').textContent = formatCurrency(state.balance);
    document.getElementById('availableBalance').textContent = formatCurrency(state.availableBalance);
    document.getElementById('lockedBalance').textContent = formatCurrency(state.lockedBalance);
    document.getElementById('totalDeposited').textContent = formatCurrency(state.totalDeposited);
    document.getElementById('totalWithdrawn').textContent = formatCurrency(state.totalWithdrawn);
    document.getElementById('netProfit').textContent = (state.netProfit >= 0 ? '+' : '') + formatCurrency(state.netProfit);
    document.getElementById('profitPercent').textContent = `+${state.roi.toFixed(1)}%`;
    document.getElementById('winRate').textContent = `${state.winRate.toFixed(0)}%`;
    document.getElementById('winRateBar').style.width = `${Math.min(100, state.winRate)}%`;
    document.getElementById('roi').textContent = `${state.roi.toFixed(1)}%`;
    document.getElementById('roiBar').style.width = `${Math.min(100, state.roi)}%`;
    document.getElementById('totalBets').textContent = state.totalBets;
    document.getElementById('withdrawAvailable').textContent = formatCurrency(state.availableBalance);
}

// === DROPDOWN ===
function toggleBalanceDropdown() {
    document.querySelector('.balance-dropdown').classList.toggle('open');
}

function scrollToSection(id) {
    document.querySelector('.balance-dropdown')?.classList.remove('open');
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' });
}

// === HISTORY ===
function renderHistory() {
    const filter = document.getElementById('historyFilter')?.value || 'all';
    let filtered = filter === 'all' ? [...state.transactions] : state.transactions.filter(t => t.type === filter);
    
    filtered.sort((a, b) => {
        let aVal = state.sortField === 'date' ? new Date(a.created_at) : a.amount;
        let bVal = state.sortField === 'date' ? new Date(b.created_at) : b.amount;
        return state.sortOrder === 'desc' ? bVal - aVal : aVal - bVal;
    });
    
    const total = filtered.length;
    const pages = Math.ceil(total / state.historyPerPage) || 1;
    const start = (state.historyPage - 1) * state.historyPerPage;
    const pageData = filtered.slice(start, start + state.historyPerPage);
    
    document.getElementById('paginationInfo').textContent = `${state.historyPage} / ${pages}`;
    
    const tbody = document.getElementById('historyTableBody');
    if (pageData.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;padding:40px;color:#95a5a6;">Нет данных</td></tr>';
        return;
    }
    
    const typeNames = { deposit: 'Депозит', withdrawal: 'Вывод', bet: 'Ставка', win: 'Выигрыш', loss: 'Проигрыш' };
    const statusNames = { completed: 'Выполнено', pending: 'В обработке', failed: 'Ошибка' };
    
    tbody.innerHTML = pageData.map(tx => {
        const isPositive = ['deposit', 'win'].includes(tx.type);
        return `
            <tr>
                <td>${formatDate(tx.created_at)}</td>
                <td>${typeNames[tx.type] || tx.type}</td>
                <td>${tx.description}</td>
                <td class="${isPositive ? 'positive' : 'negative'}" style="font-family:var(--font-family-mono);">
                    ${isPositive ? '+' : '-'}${formatCurrency(tx.amount)}
                </td>
                <td><span class="status-badge ${tx.status}">${statusNames[tx.status] || tx.status}</span></td>
            </tr>
        `;
    }).join('');
}

function filterHistory() { 
    state.historyPage = 1; 
    loadHistory(); 
}

function sortHistory(field) {
    if (state.sortField === field) {
        state.sortOrder = state.sortOrder === 'desc' ? 'asc' : 'desc';
    } else {
        state.sortField = field;
        state.sortOrder = 'desc';
    }
    renderHistory();
}

function changePage(dir) {
    const filter = document.getElementById('historyFilter')?.value || 'all';
    const filtered = filter === 'all' ? state.transactions : state.transactions.filter(t => t.type === filter);
    const pages = Math.ceil(filtered.length / state.historyPerPage) || 1;
    
    state.historyPage = Math.max(1, Math.min(pages, state.historyPage + dir));
    renderHistory();
}

// === PAYMENT METHODS ===
function renderPaymentMethods() {
    // Deposit modal
    const depositList = document.getElementById('depositPaymentMethods');
    if (depositList) {
        depositList.innerHTML = `
            <div class="payment-method-item ${state.selectedPaymentMethod === 'new' ? 'selected' : ''}" onclick="selectPaymentMethod('new', this)">
                <span class="method-icon">+</span>
                <div class="method-details">
                    <div class="method-name">Новая карта</div>
                    <div class="method-number">Visa, Mastercard</div>
                </div>
            </div>
            ${state.paymentMethods.map(pm => `
                <div class="payment-method-item ${state.selectedPaymentMethod === pm.id ? 'selected' : ''}" onclick="selectPaymentMethod('${pm.id}', this)">
                    <span class="method-icon">C</span>
                    <div class="method-details">
                        <div class="method-name">${pm.brand}</div>
                        <div class="method-number">**** ${pm.last4}</div>
                    </div>
                    ${pm.is_default ? '<span class="method-badge">Default</span>' : ''}
                </div>
            `).join('')}
        `;
    }
    
    // Withdrawal modal
    const withdrawList = document.getElementById('withdrawalMethods');
    if (withdrawList) {
        withdrawList.innerHTML = state.withdrawalMethods.map((m, i) => `
            <div class="withdrawal-method-item ${i === 0 ? 'selected' : ''}" onclick="selectWithdrawMethod(this)">
                <span class="method-icon">B</span>
                <div class="method-details">
                    <div class="method-name">${m.name}</div>
                    <div class="method-number">**** ${m.last4}</div>
                </div>
            </div>
        `).join('');
    }
    
    // Cards grid
    const cardsGrid = document.getElementById('paymentMethodsList');
    if (cardsGrid) {
        if (state.paymentMethods.length === 0) {
            cardsGrid.innerHTML = '<div style="text-align:center;padding:40px;color:#95a5a6;">Нет сохранённых карт</div>';
        } else {
            cardsGrid.innerHTML = state.paymentMethods.map((pm, i) => `
                <div class="card-item ${i === 0 ? 'primary' : ''}">
                    <div class="card-brand">${pm.brand}</div>
                    <div class="card-number">**** **** **** ${pm.last4}</div>
                    <div class="card-footer">
                        <span>CARD HOLDER</span>
                        <span>12/25</span>
                    </div>
                </div>
            `).join('');
        }
    }
    
    // Show/hide stripe form
    const stripeContainer = document.getElementById('stripeCardContainer');
    if (stripeContainer) {
        stripeContainer.style.display = state.selectedPaymentMethod === 'new' ? 'block' : 'none';
    }
}

function selectPaymentMethod(id, el) {
    state.selectedPaymentMethod = id;
    document.querySelectorAll('.payment-method-item').forEach(e => e.classList.remove('selected'));
    if (el) el.classList.add('selected');
    const stripeContainer = document.getElementById('stripeCardContainer');
    if (stripeContainer) {
        stripeContainer.style.display = id === 'new' ? 'block' : 'none';
    }
}

function selectWithdrawMethod(el) {
    document.querySelectorAll('.withdrawal-method-item').forEach(e => e.classList.remove('selected'));
    if (el) el.classList.add('selected');
}

function addPaymentMethod() {
    openModal('depositModal');
    const firstItem = document.querySelector('.payment-method-item');
    if (firstItem) selectPaymentMethod('new', firstItem);
}

// === DEPOSIT ===
function setDepositAmount(amount) {
    document.getElementById('depositAmount').value = amount;
    document.querySelectorAll('.quick-amount').forEach(b => b.classList.toggle('selected', b.textContent.includes(amount)));
}

async function processDeposit() {
    const amount = parseFloat(document.getElementById('depositAmount').value);
    if (!amount || amount < 1) { 
        showToast('Введите сумму', 'error'); 
        return; 
    }
    
    const saveCard = document.getElementById('saveCard')?.checked || false;
    
    try {
        if (state.selectedPaymentMethod === 'new') {
            if (!stripe || !cardElement) {
                showToast('Stripe не настроен', 'error');
                return;
            }
            
            const intentData = await apiRequest('/deposit', {
                method: 'POST',
                body: {
                    amount: amount,
                    save_payment_method: saveCard
                }
            });
            
            if (!intentData.client_secret) {
                throw new Error('Не получен client_secret');
            }
            
            const {error, paymentIntent} = await stripe.confirmCardPayment(
                intentData.client_secret,
                {
                    payment_method: {
                        card: cardElement,
                    }
                }
            );
            
            if (error) {
                throw new Error(error.message);
            }
            
            if (paymentIntent.status === 'succeeded') {
                showSuccess('Успешно', `Зачислено ${formatCurrency(amount)}`);
                closeModal('depositModal');
                await loadBalance();
                await loadPaymentMethods();
                await loadHistory();
            }
        } else {
            const result = await apiRequest('/deposit', {
                method: 'POST',
                body: {
                    amount: amount,
                    payment_method_id: state.selectedPaymentMethod
                }
            });
            
            if (result.success) {
                showSuccess('Успешно', `Зачислено ${formatCurrency(amount)}`);
                closeModal('depositModal');
                await loadBalance();
                await loadHistory();
            }
        }
    } catch (error) {
        showToast(error.message || 'Ошибка пополнения', 'error');
    }
}

// === WITHDRAW ===
async function processWithdraw() {
    const amount = parseFloat(document.getElementById('withdrawAmount').value);
    if (!amount || amount < 10) { 
        showToast('Минимум $10', 'error'); 
        return; 
    }
    if (amount > state.availableBalance) { 
        showToast('Недостаточно средств', 'error'); 
        return; 
    }
    
    const selectedMethod = document.querySelector('.withdrawal-method-item.selected');
    if (!selectedMethod) {
        showToast('Выберите способ вывода', 'error');
        return;
    }
    
    const methodId = state.withdrawalMethods.find(m => 
        selectedMethod.textContent.includes(m.name)
    )?.id;
    
    if (!methodId) {
        showToast('Способ вывода не выбран', 'error');
        return;
    }
    
    try {
        const result = await apiRequest('/withdraw', {
            method: 'POST',
            body: {
                amount: amount,
                withdrawal_method_id: methodId,
                reason: 'Вывод средств'
            }
        });
        
        if (result.success) {
            showSuccess('Заявка принята', `Вывод ${formatCurrency(amount)} обрабатывается`);
            closeModal('withdrawModal');
            await loadBalance();
            await loadHistory();
        }
    } catch (error) {
        showToast(error.message || 'Ошибка вывода', 'error');
    }
}

// === EXPORT ===
function setDefaultDates() {
    const today = new Date();
    const monthAgo = new Date();
    monthAgo.setMonth(monthAgo.getMonth() - 1);
    const fromInput = document.getElementById('exportDateFrom');
    const toInput = document.getElementById('exportDateTo');
    if (fromInput) fromInput.value = monthAgo.toISOString().split('T')[0];
    if (toInput) toInput.value = today.toISOString().split('T')[0];
}

async function exportReport() {
    const format = document.querySelector('input[name="format"]:checked')?.value || 'csv';
    const dateFrom = document.getElementById('exportDateFrom')?.value;
    const dateTo = document.getElementById('exportDateTo')?.value;
    
    try {
        const result = await apiRequest('/export', {
            method: 'POST',
            body: {
                format: format,
                date_from: dateFrom,
                date_to: dateTo,
                include_bets: true,
                include_transactions: true
            }
        });
        
        if (result.download_url) {
            window.open(result.download_url, '_blank');
            showToast(`Отчет ${format.toUpperCase()} скачивается...`, 'success');
            closeModal('exportModal');
        }
    } catch (error) {
        showToast(error.message || 'Ошибка экспорта', 'error');
    }
}

// === CHART ===
function initChart() {
    const ctx = document.getElementById('balanceChart');
    if (!ctx) return;
    
    balanceChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                data: [],
                borderColor: '#27ae60',
                backgroundColor: 'rgba(39,174,96,0.1)',
                fill: true,
                tension: 0.4,
                pointRadius: 4,
                pointBackgroundColor: '#27ae60'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                x: { grid: { display: false } },
                y: { ticks: { callback: v => '$' + v } }
            }
        }
    });
    
    updateChart();
}

function updateChart() {
    if (!balanceChart || !state.transactions.length) return;
    
    const sorted = [...state.transactions].sort((a, b) => 
        new Date(a.created_at) - new Date(b.created_at)
    );
    
    let runningBalance = state.balance;
    const labels = [];
    const data = [];
    
    for (let i = sorted.length - 1; i >= 0; i--) {
        const tx = sorted[i];
        const date = new Date(tx.created_at);
        labels.unshift(date.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' }));
        
        if (['deposit', 'win'].includes(tx.type)) {
            runningBalance -= tx.amount;
        } else {
            runningBalance += tx.amount;
        }
        data.unshift(runningBalance);
    }
    
    balanceChart.data.labels = labels;
    balanceChart.data.datasets[0].data = data;
    balanceChart.update();
}

function setChartPeriod(days, btn) {
    document.querySelectorAll('.section-actions .btn-text').forEach(b => b.classList.remove('active'));
    if (btn) btn.classList.add('active');
    updateChart();
}

// === MODALS ===
function openModal(id) {
    document.querySelector('.balance-dropdown')?.classList.remove('open');
    document.getElementById(id)?.classList.add('open');
    if (id === 'depositModal') {
        loadPaymentMethods();
    } else if (id === 'withdrawModal') {
        loadWithdrawalMethods();
    }
}

function closeModal(id) {
    document.getElementById(id)?.classList.remove('open');
}

function showSuccess(title, message) {
    document.getElementById('successTitle').textContent = title;
    document.getElementById('successMessage').textContent = message;
    openModal('successModal');
}

function showToast(message, type = 'info') {
    const container = document.getElementById('toastContainer');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);
}

// === UTILS ===
function formatCurrency(n) {
    return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(n);
}

function formatDate(s) {
    if (!s) return '-';
    const d = new Date(s);
    return d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
}

// ESC to close
document.addEventListener('keydown', e => {
    if (e.key === 'Escape') document.querySelectorAll('.modal.open').forEach(m => m.classList.remove('open'));
});
