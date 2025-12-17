/**
 * LOOSELINE Wallet - Single Page Application
 */

const CONFIG = {
    API_BASE: 'http://127.0.0.1:8000/api/wallet',
    USER_ID: 'demo_user',
    STRIPE_PK: 'pk_test_TYooMQauvdEDq54NiTphI7jx'
};

let state = {
    balance: 5000.00,
    availableBalance: 4750.00,
    lockedBalance: 250.00,
    totalDeposited: 10000.00,
    totalWithdrawn: 5000.00,
    netProfit: 2180.00,
    winRate: 64,
    roi: 87.2,
    totalBets: 25,
    transactions: [],
    paymentMethods: [],
    withdrawalMethods: [],
    historyPage: 1,
    historyPerPage: 10,
    sortField: 'date',
    sortOrder: 'desc',
    selectedPaymentMethod: 'new'
};

let stripe, cardElement, balanceChart;

// === INIT ===
document.addEventListener('DOMContentLoaded', async () => {
    initStripe();
    loadDemoData();
    updateDisplays();
    renderHistory();
    renderPaymentMethods();
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
    } catch (e) { console.log('Stripe unavailable'); }
}

function loadDemoData() {
    state.transactions = [
        { id: 1, type: 'deposit', amount: 500, status: 'completed', created_at: new Date().toISOString(), description: 'Пополнение баланса' },
        { id: 2, type: 'win', amount: 185, status: 'completed', created_at: new Date(Date.now() - 86400000).toISOString(), description: 'Выигрыш: Реал - Барселона' },
        { id: 3, type: 'bet', amount: 100, status: 'completed', created_at: new Date(Date.now() - 86400000).toISOString(), description: 'Ставка: Реал - Барселона' },
        { id: 4, type: 'deposit', amount: 1000, status: 'completed', created_at: new Date(Date.now() - 172800000).toISOString(), description: 'Пополнение баланса' },
        { id: 5, type: 'loss', amount: 50, status: 'completed', created_at: new Date(Date.now() - 259200000).toISOString(), description: 'Проигрыш: ПСЖ - Лион' },
        { id: 6, type: 'withdrawal', amount: 2000, status: 'pending', created_at: new Date(Date.now() - 345600000).toISOString(), description: 'Вывод на Chase Bank' },
        { id: 7, type: 'win', amount: 320, status: 'completed', created_at: new Date(Date.now() - 432000000).toISOString(), description: 'Выигрыш: Ман Сити - Ливерпуль' },
    ];
    
    state.paymentMethods = [
        { id: 'pm_1', brand: 'Visa', last4: '4242', is_default: true },
        { id: 'pm_2', brand: 'Mastercard', last4: '5555', is_default: false }
    ];
    
    state.withdrawalMethods = [
        { id: 1, name: 'Chase Bank', last4: '7890' },
        { id: 2, name: 'Bank of America', last4: '1234' }
    ];
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
    document.getElementById('profitPercent').textContent = `+${state.roi}%`;
    document.getElementById('winRate').textContent = `${state.winRate}%`;
    document.getElementById('winRateBar').style.width = `${state.winRate}%`;
    document.getElementById('roi').textContent = `${state.roi}%`;
    document.getElementById('roiBar').style.width = `${Math.min(100, state.roi)}%`;
    document.getElementById('totalBets').textContent = state.totalBets;
    document.getElementById('withdrawAvailable').textContent = formatCurrency(state.availableBalance);
}

// === DROPDOWN ===
function toggleBalanceDropdown() {
    document.querySelector('.balance-dropdown').classList.toggle('open');
}

function scrollToSection(id) {
    document.querySelector('.balance-dropdown').classList.remove('open');
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
                <td><span class="status-badge ${tx.status}">${statusNames[tx.status]}</span></td>
            </tr>
        `;
    }).join('');
}

function filterHistory() { state.historyPage = 1; renderHistory(); }

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
    
    // Withdrawal modal
    const withdrawList = document.getElementById('withdrawalMethods');
    withdrawList.innerHTML = state.withdrawalMethods.map((m, i) => `
        <div class="withdrawal-method-item ${i === 0 ? 'selected' : ''}" onclick="selectWithdrawMethod(this)">
            <span class="method-icon">B</span>
            <div class="method-details">
                <div class="method-name">${m.name}</div>
                <div class="method-number">**** ${m.last4}</div>
            </div>
        </div>
    `).join('');
    
    // Cards grid
    const cardsGrid = document.getElementById('paymentMethodsList');
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
    
    // Show/hide stripe form
    document.getElementById('stripeCardContainer').style.display = state.selectedPaymentMethod === 'new' ? 'block' : 'none';
}

function selectPaymentMethod(id, el) {
    state.selectedPaymentMethod = id;
    document.querySelectorAll('.payment-method-item').forEach(e => e.classList.remove('selected'));
    el.classList.add('selected');
    document.getElementById('stripeCardContainer').style.display = id === 'new' ? 'block' : 'none';
}

function selectWithdrawMethod(el) {
    document.querySelectorAll('.withdrawal-method-item').forEach(e => e.classList.remove('selected'));
    el.classList.add('selected');
}

function addPaymentMethod() {
    openModal('depositModal');
    selectPaymentMethod('new', document.querySelector('.payment-method-item'));
}

// === DEPOSIT ===
function setDepositAmount(amount) {
    document.getElementById('depositAmount').value = amount;
    document.querySelectorAll('.quick-amount').forEach(b => b.classList.toggle('selected', b.textContent.includes(amount)));
}

async function processDeposit() {
    const amount = parseFloat(document.getElementById('depositAmount').value);
    if (!amount || amount < 1) { showToast('Введите сумму', 'error'); return; }
    
    state.balance += amount;
    state.availableBalance += amount;
    state.totalDeposited += amount;
    state.transactions.unshift({
        id: Date.now(), type: 'deposit', amount, status: 'completed',
        created_at: new Date().toISOString(), description: 'Пополнение баланса'
    });
    
    updateDisplays();
    renderHistory();
    closeModal('depositModal');
    showSuccess('Успешно', `Зачислено ${formatCurrency(amount)}`);
}

// === WITHDRAW ===
async function processWithdraw() {
    const amount = parseFloat(document.getElementById('withdrawAmount').value);
    if (!amount || amount < 10) { showToast('Минимум $10', 'error'); return; }
    if (amount > state.availableBalance) { showToast('Недостаточно средств', 'error'); return; }
    
    state.balance -= amount;
    state.availableBalance -= amount;
    state.totalWithdrawn += amount;
    state.transactions.unshift({
        id: Date.now(), type: 'withdrawal', amount, status: 'pending',
        created_at: new Date().toISOString(), description: 'Вывод средств'
    });
    
    updateDisplays();
    renderHistory();
    closeModal('withdrawModal');
    showSuccess('Заявка принята', `Вывод ${formatCurrency(amount)} обрабатывается`);
}

// === EXPORT ===
function setDefaultDates() {
    const today = new Date();
    const monthAgo = new Date();
    monthAgo.setMonth(monthAgo.getMonth() - 1);
    document.getElementById('exportDateFrom').value = monthAgo.toISOString().split('T')[0];
    document.getElementById('exportDateTo').value = today.toISOString().split('T')[0];
}

function exportReport() {
    const format = document.querySelector('input[name="format"]:checked')?.value || 'csv';
    showToast(`Отчет ${format.toUpperCase()} скачивается...`, 'success');
    closeModal('exportModal');
}

// === CHART ===
function initChart() {
    const ctx = document.getElementById('balanceChart');
    if (!ctx) return;
    
    const labels = [];
    const data = [];
    let balance = state.balance - 1500;
    
    for (let i = 6; i >= 0; i--) {
        const d = new Date();
        d.setDate(d.getDate() - i);
        labels.push(d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' }));
        balance += (Math.random() - 0.3) * 300;
        data.push(Math.max(100, balance).toFixed(0));
    }
    data[data.length - 1] = state.balance;
    
    balanceChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels,
            datasets: [{
                data,
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
}

function setChartPeriod(days, btn) {
    document.querySelectorAll('.section-actions .btn-text').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    
    // Update chart with new data
    const labels = [];
    const data = [];
    let balance = state.balance - 1500;
    
    for (let i = days - 1; i >= 0; i--) {
        const d = new Date();
        d.setDate(d.getDate() - i);
        labels.push(d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' }));
        balance += (Math.random() - 0.3) * 300;
        data.push(Math.max(100, balance).toFixed(0));
    }
    data[data.length - 1] = state.balance;
    
    balanceChart.data.labels = labels;
    balanceChart.data.datasets[0].data = data;
    balanceChart.update();
}

// === MODALS ===
function openModal(id) {
    document.querySelector('.balance-dropdown')?.classList.remove('open');
    document.getElementById(id)?.classList.add('open');
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
