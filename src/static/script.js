// Global state and configuration
const API_BASE_URL = '/api';
let currentUser = null;
let currentFamilyId = null; // Store the selected family ID

// DOM Elements
const appContent = document.getElementById('app-content');
const mainNav = document.getElementById('main-nav');

// --- Helper Functions ---
async function apiRequest(endpoint, method = 'GET', body = null, requiresAuth = true) {
    const headers = {
        'Content-Type': 'application/json',
    };
    const token = localStorage.getItem('authToken');
    if (requiresAuth && token) {
        headers['Authorization'] = `Bearer ${token}`;
    }

    const config = {
        method: method,
        headers: headers,
    };

    if (body) {
        config.body = JSON.stringify(body);
    }

    try {
        const response = await fetch(`${API_BASE_URL}${endpoint}`, config);
        if (response.status === 401) { // Unauthorized
            logout();
            navigateTo('/login');
            showError('Sessão expirada. Por favor, faça login novamente.');
            return null;
        }
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ error: 'Erro desconhecido na API' }));
            throw new Error(errorData.error || `Erro ${response.status}`);
        }
        if (response.status === 204 || response.headers.get("content-length") === "0") { // No content
            return null;
        }
        return await response.json();
    } catch (error) {
        console.error('API Request Error:', error);
        showError(error.message);
        return null;
    }
}

function showError(message) {
    const errorDiv = document.createElement('div');
    errorDiv.className = 'error-message';
    errorDiv.textContent = message;
    
    const existingError = appContent.querySelector('.error-message');
    if (existingError) {
        existingError.remove();
    }
    // Prepend to appContent or a specific error container if available
    if (appContent.firstChild) {
        appContent.insertBefore(errorDiv, appContent.firstChild);
    } else {
        appContent.appendChild(errorDiv);
    }
    setTimeout(() => errorDiv.remove(), 5000); // Auto-remove after 5 seconds
}

function showSuccess(message) {
    const successDiv = document.createElement('div');
    successDiv.className = 'success-message';
    successDiv.textContent = message;

    const existingSuccess = appContent.querySelector('.success-message');
    if (existingSuccess) {
        existingSuccess.remove();
    }
    if (appContent.firstChild) {
        appContent.insertBefore(successDiv, appContent.firstChild);
    } else {
        appContent.appendChild(successDiv);
    }
    setTimeout(() => successDiv.remove(), 3000);
}

// --- Navigation and Routing ---
function navigateTo(path) {
    history.pushState(null, null, path);
    router();
}

const routes = {
    '/': showDashboard,
    '/login': showLoginForm,
    '/register': showRegisterForm,
    '/families': showFamiliesManagement, // To select or create a family
    '/budget': showBudgetPage, // Current month budget, expenses, credits
    '/expenses': showExpensesPage, // Add/edit/delete expenses
    '/credits': showCreditsPage, // Add/edit/delete credits
    '/recurring': showRecurringExpensesPage, // Manage recurring expense rules
    '/reports': showReportsPage,
    '/settings': showSettingsPage, // User settings, family settings (categories, payment types)
};

async function router() {
    const path = window.location.pathname;
    const routeHandler = routes[path] || showNotFound;

    // Clear previous content
    appContent.innerHTML = '<p>Carregando...</p>';
    // Clear previous error/success messages that might be outside the dynamic content area
    const messages = document.querySelectorAll('.error-message, .success-message');
    messages.forEach(msg => msg.remove());

    await checkAuth(); // Ensure currentUser is up-to-date
    updateNavigation();

    if (!currentUser && !['/login', '/register'].includes(path)) {
        navigateTo('/login');
        return;
    }
    
    // If user is logged in but hasn't selected a family, redirect to family management
    // except for pages that don't require a family context (like settings for creating a family)
    if (currentUser && !currentFamilyId && !['/login', '/register', '/families', '/settings'].includes(path)) {
        const userFamilies = await apiRequest(`/user/${currentUser.id}/families`);
        if (userFamilies && userFamilies.length > 0) {
            currentFamilyId = userFamilies[0].id; // Auto-select first family or implement selection
            localStorage.setItem('currentFamilyId', currentFamilyId);
            showSuccess(`Família "${userFamilies[0].name}" selecionada.`);
        } else {
            navigateTo('/families');
            showError('Por favor, crie ou selecione uma família para continuar.');
            return;
        }
    }

    routeHandler();
}

function updateNavigation() {
    mainNav.innerHTML = ''; // Clear existing nav
    const ul = document.createElement('ul');

    if (currentUser) {
        ul.innerHTML = `
            <li><a href="/" onclick="navigateTo('/'); return false;">Painel</a></li>
            <li><a href="/budget" onclick="navigateTo('/budget'); return false;">Orçamento Mensal</a></li>
            <li><a href="/recurring" onclick="navigateTo('/recurring'); return false;">Despesas Recorrentes</a></li>
            <li><a href="/reports" onclick="navigateTo('/reports'); return false;">Relatórios</a></li>
            <li><a href="/families" onclick="navigateTo('/families'); return false;">Minhas Famílias</a></li>
            <li><a href="/settings" onclick="navigateTo('/settings'); return false;">Configurações</a></li>
            <li><a href="#" onclick="logout(); return false;">Sair (${currentUser.username})</a></li>
        `;
    } else {
        ul.innerHTML = `
            <li><a href="/login" onclick="navigateTo('/login'); return false;">Login</a></li>
            <li><a href="/register" onclick="navigateTo('/register'); return false;">Registrar</a></li>
        `;
    }
    mainNav.appendChild(ul);
}

// --- Authentication ---
async function checkAuth() {
    const token = localStorage.getItem('authToken');
    if (token) {
        // Optionally: verify token with a lightweight backend endpoint if needed
        // For now, assume token is valid if present and rely on API calls to fail if it's not
        const storedUser = localStorage.getItem('currentUser');
        if (storedUser) {
            currentUser = JSON.parse(storedUser);
        }
        const storedFamilyId = localStorage.getItem('currentFamilyId');
        if (storedFamilyId) {
            currentFamilyId = parseInt(storedFamilyId);
        }
    } else {
        currentUser = null;
        currentFamilyId = null;
    }
}

async function login(email, password) {
    const data = await apiRequest('/login', 'POST', { email, password }, false);
    if (data && data.access_token) {
        localStorage.setItem('authToken', data.access_token);
        localStorage.setItem('currentUser', JSON.stringify(data.user));
        currentUser = data.user;
        // After login, try to load families and set currentFamilyId
        const userFamilies = await apiRequest(`/user/${currentUser.id}/families`);
        if (userFamilies && userFamilies.length > 0) {
            currentFamilyId = userFamilies[0].id; // Auto-select first family
            localStorage.setItem('currentFamilyId', currentFamilyId);
            showSuccess(`Login bem-sucedido! Família "${userFamilies[0].name}" selecionada.`);
            navigateTo('/');
        } else {
            showSuccess('Login bem-sucedido! Por favor, crie ou junte-se a uma família.');
            navigateTo('/families'); 
        }
        updateNavigation();
    } else {
        showError(data ? data.error : 'Falha no login. Verifique suas credenciais.');
    }
}

async function register(username, email, password) {
    const data = await apiRequest('/register', 'POST', { username, email, password }, false);
    if (data && data.message) {
        showSuccess(data.message + ' Por favor, faça login.');
        navigateTo('/login');
    } else {
        showError(data ? data.error : 'Falha no registro.');
    }
}

function logout() {
    localStorage.removeItem('authToken');
    localStorage.removeItem('currentUser');
    localStorage.removeItem('currentFamilyId');
    currentUser = null;
    currentFamilyId = null;
    showSuccess('Você saiu com sucesso.');
    navigateTo('/login');
    updateNavigation();
}

// --- Page Render Functions (Placeholders - to be implemented) ---
function showLoginForm() {
    appContent.innerHTML = `
        <h2>Login</h2>
        <form id="login-form">
            <div>
                <label for="email">Email:</label>
                <input type="email" id="email" name="email" required autocomplete="off">
            </div>
            <div>
                <label for="password">Senha:</label>
                <input type="password" id="password" name="password" required autocomplete="off">
            </div>
            <button type="submit">Entrar</button>
        </form>
        <p>Não tem uma conta? <a href="/register" onclick="navigateTo('/register'); return false;">Registre-se aqui</a>.</p>
    `;
    document.getElementById('login-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const email = e.target.email.value;
        const password = e.target.password.value;
        await login(email, password);
    });
}

function showRegisterForm() {
    appContent.innerHTML = `
        <h2>Registrar</h2>
        <form id="register-form">
            <div>
                <label for="username">Nome de Usuário:</label>
                <input type="text" id="username" name="username" required autocomplete="off">
            </div>
            <div>
                <label for="email">Email:</label>
                <input type="email" id="email" name="email" required autocomplete="off">
            </div>
            <div>
                <label for="password">Senha:</label>
                <input type="password" id="password" name="password" required autocomplete="off">
            </div>
            <div>
                <label for="confirm_password">Confirmar Senha:</label>
                <input type="password" id="confirm_password" name="confirm_password" required autocomplete="off">
            </div>
            <button type="submit">Registrar</button>
        </form>
        <p>Já tem uma conta? <a href="/login" onclick="navigateTo('/login'); return false;">Faça login aqui</a>.</p>
    `;
    document.getElementById('register-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const username = e.target.username.value;
        const email = e.target.email.value;
        const password = e.target.password.value;
        const confirm_password = e.target.confirm_password.value;
        if (password !== confirm_password) {
            showError('As senhas não coincidem.');
            return;
        }
        await register(username, email, password);
    });
}

async function showDashboard() {
    if (!currentUser) { navigateTo('/login'); return; }
    if (!currentFamilyId) { navigateTo('/families'); return; }
    appContent.innerHTML = `<h2>Painel Principal</h2><p>Bem-vindo, ${currentUser.username}!</p><p>Família ID selecionada: ${currentFamilyId}</p><div class="dashboard-grid"></div>`;
    // TODO: Load dashboard widgets (summary, quick actions, etc.)
    // Example: Load budget vs actual for current month
    const today = new Date();
    const budgetData = await apiRequest(`/reports/budget_vs_actual?family_id=${currentFamilyId}&year=${today.getFullYear()}&month=${today.getMonth() + 1}`);
    const dashboardGrid = appContent.querySelector('.dashboard-grid');
    if (budgetData && dashboardGrid) {
        const budgetWidget = document.createElement('div');
        budgetWidget.className = 'card';
        budgetWidget.innerHTML = `
            <h3>Resumo do Mês Atual (${String(today.getMonth() + 1).padStart(2, '0')}/${today.getFullYear()})</h3>
            <p>Orçamento Planejado: R$ ${budgetData.planned_budget.toFixed(2)}</p>
            <p>Total Gasto: R$ ${budgetData.total_spent.toFixed(2)}</p>
            <p>Saldo: R$ ${budgetData.difference.toFixed(2)}</p>
        `;
        dashboardGrid.appendChild(budgetWidget);
    }
    // Placeholder for charts
    const chartContainer = document.createElement('div');
    chartContainer.className = 'card';
    chartContainer.innerHTML = '<h3>Gastos por Categoria (Mês Atual)</h3><div class="chart-container"><canvas id="categoryPieChart"></canvas></div>';
    dashboardGrid.appendChild(chartContainer);
    loadCategoryPieChart(today.getFullYear(), today.getMonth() + 1, 'categoryPieChart');
}

async function showFamiliesManagement() {
    if (!currentUser) { navigateTo('/login'); return; }
    appContent.innerHTML = `
        <h2>Gerenciar Famílias/Orçamentos</h2>
        <div id="family-list"></div>
        <h3>Criar Nova Família</h3>
        <form id="create-family-form">
            <label for="family-name">Nome da Família:</label>
            <input type="text" id="family-name" required>
            <button type="submit">Criar Família</button>
        </form>
        <h3>Juntar-se a uma Família Existente (TODO)</h3>
        <!-- TODO: Implement join family functionality -->
    `;

    const familyListDiv = document.getElementById('family-list');
    const families = await apiRequest(`/user/${currentUser.id}/families`);
    if (families && families.length > 0) {
        let listHtml = '<h3>Suas Famílias:</h3><ul>';
        families.forEach(family => {
            listHtml += `<li>${family.name} (ID: ${family.id}) 
                <button class="btn btn-sm ${family.id === currentFamilyId ? 'btn-secondary' : 'btn'}" 
                        onclick="selectFamily(${family.id}, '${family.name}')">
                    ${family.id === currentFamilyId ? 'Selecionada' : 'Selecionar'}
                </button></li>`;
        });
        listHtml += '</ul>';
        familyListDiv.innerHTML = listHtml;
    } else {
        familyListDiv.innerHTML = '<p>Você ainda não faz parte de nenhuma família.</p>';
    }

    document.getElementById('create-family-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const name = document.getElementById('family-name').value;
        const newFamily = await apiRequest('/family', 'POST', { name });
        if (newFamily) {
            showSuccess(`Família "${newFamily.name}" criada com sucesso!`);
            // Auto-select this new family
            selectFamily(newFamily.id, newFamily.name);
            router(); // Refresh page to show new family and potentially redirect
        }
    });
}

function selectFamily(familyId, familyName) {
    currentFamilyId = familyId;
    localStorage.setItem('currentFamilyId', currentFamilyId);
    showSuccess(`Família "${familyName}" selecionada.`);
    updateNavigation(); // Reflect selection if needed
    navigateTo('/'); // Go to dashboard or refresh current page
}

// --- Placeholder functions for other pages ---
async function showBudgetPage() {
    if (!currentFamilyId) { navigateTo('/families'); return; }
    appContent.innerHTML = `<h2>Orçamento Mensal (Família ID: ${currentFamilyId})</h2> <p>Conteúdo da página de orçamento aqui...</p>`;
    // TODO: Implement full budget page with expenses, credits, planned budget for current/selected month
    // Add forms to add expense/credit, list items, etc.
}

async function showExpensesPage() { 
    if (!currentFamilyId) { navigateTo('/families'); return; }
    appContent.innerHTML = `<h2>Gerenciar Despesas (Família ID: ${currentFamilyId})</h2> <p>TODO: Formulário para adicionar/editar despesas e lista de despesas.</p>`; 
}
async function showCreditsPage() { 
    if (!currentFamilyId) { navigateTo('/families'); return; }
    appContent.innerHTML = `<h2>Gerenciar Créditos (Família ID: ${currentFamilyId})</h2> <p>TODO: Formulário para adicionar/editar créditos e lista de créditos.</p>`; 
}
async function showRecurringExpensesPage() { 
    if (!currentFamilyId) { navigateTo('/families'); return; }
    appContent.innerHTML = `<h2>Despesas Recorrentes (Família ID: ${currentFamilyId})</h2> <p>TODO: Gerenciar regras de despesas recorrentes e botão para gerar despesas do mês.</p>`; 
}
async function showReportsPage() { 
    if (!currentFamilyId) { navigateTo('/families'); return; }
    appContent.innerHTML = `<h2>Relatórios (Família ID: ${currentFamilyId})</h2>
        <div class="card">
            <h3>Gastos por Categoria (Mês Atual)</h3>
            <div class="chart-container"><canvas id="reportsCategoryPieChart"></canvas></div>
        </div>
        <div class="card">
            <h3>Evolução dos Gastos (Últimos 6 Meses)</h3>
            <div class="chart-container"><canvas id="reportsEvolutionLineChart"></canvas></div>
        </div>
         <div class="card">
            <h3>Orçamento vs. Realizado (Mês Atual)</h3>
            <div id="budgetVsActualReport">Carregando...</div>
        </div>
    `; 
    const today = new Date();
    loadCategoryPieChart(today.getFullYear(), today.getMonth() + 1, 'reportsCategoryPieChart');
    loadEvolutionLineChart('reportsEvolutionLineChart');
    loadBudgetVsActualReport('budgetVsActualReport', today.getFullYear(), today.getMonth() + 1);
}

async function showSettingsPage() {
    if (!currentUser) { navigateTo('/login'); return; }
    appContent.innerHTML = `<h2>Configurações</h2>
        <div class="card">
            <h3>Configurações da Família (ID: ${currentFamilyId || 'Nenhuma selecionada'})</h3>
            ${currentFamilyId ? `
            <p><button class="btn" onclick="manageCategories()">Gerenciar Categorias</button></p>
            <p><button class="btn" onclick="managePaymentTypes()">Gerenciar Tipos de Pagamento</button></p>
            <p><button class="btn" onclick="manageFamilyMembers()">Gerenciar Membros da Família</button></p>
            ` : '<p>Selecione uma família para ver as configurações.</p>'}
        </div>
        <div class="card">
            <h3>Configurações do Usuário</h3>
            <p>Nome de usuário: ${currentUser.username}</p>
            <p>Email: ${currentUser.email}</p>
            <p><button class="btn btn-secondary" onclick="changePassword()">Alterar Senha (TODO)</button></p>
        </div>
    `;
    // TODO: Implement category, payment type, members management, change password
}

function manageCategories() { showSuccess('TODO: Gerenciar Categorias'); }
function managePaymentTypes() { showSuccess('TODO: Gerenciar Tipos de Pagamento'); }
function manageFamilyMembers() { showSuccess('TODO: Gerenciar Membros da Família'); }
function changePassword() { showSuccess('TODO: Alterar Senha'); }

function showNotFound() {
    appContent.innerHTML = '<h2>Página Não Encontrada</h2><p>A página que você está procurando não existe.</p>';
}

// --- Charting Functions (using Chart.js CDN) ---
async function loadCategoryPieChart(year, month, canvasId) {
    if (!currentFamilyId) return;
    const canvasElement = document.getElementById(canvasId);
    if (!canvasElement) {
        console.warn(`Canvas element ${canvasId} not found for pie chart.`);
        return;
    }
    const data = await apiRequest(`/reports/expenses_by_category?family_id=${currentFamilyId}&year=${year}&month=${month}`);
    if (data && data.length > 0) {
        new Chart(canvasElement, {
            type: 'pie',
            data: {
                labels: data.map(item => item.name),
                datasets: [{
                    label: 'Gastos por Categoria',
                    data: data.map(item => item.value),
                    backgroundColor: [
                        'rgba(255, 99, 132, 0.7)', 'rgba(54, 162, 235, 0.7)',
                        'rgba(255, 206, 86, 0.7)', 'rgba(75, 192, 192, 0.7)',
                        'rgba(153, 102, 255, 0.7)', 'rgba(255, 159, 64, 0.7)',
                        'rgba(199, 199, 199, 0.7)', 'rgba(83, 102, 255, 0.7)'
                    ],
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                onClick: (event, elements) => {
                    if (elements.length > 0) {
                        const chartElement = elements[0];
                        const categoryId = data[chartElement.index].id;
                        const categoryName = data[chartElement.index].name;
                        // Drill down to subcategories - this needs a new chart or update current
                        showSubcategoryPieChart(year, month, categoryId, categoryName);
                    }
                }
            }
        });
    } else if (data) {
        canvasElement.parentElement.innerHTML = '<p>Sem dados de despesas para este período.</p>';
    }
}

async function showSubcategoryPieChart(year, month, categoryId, categoryName) {
    // This could replace the current chart or open a modal/new section
    const subcategoryData = await apiRequest(`/reports/expenses_by_category?family_id=${currentFamilyId}&year=${year}&month=${month}&category_id=${categoryId}`);
    const reportsPageContent = document.getElementById('reportsCategoryPieChart'); // Assuming this is where the main chart is
    if (reportsPageContent && subcategoryData && subcategoryData.length > 0) {
        // For simplicity, let's add a new chart below the existing one or replace it.
        // A modal or dedicated drill-down view would be better UX for complex apps.
        let subcategoryChartContainer = document.getElementById('subcategoryPieChartContainer');
        if (!subcategoryChartContainer) {
            subcategoryChartContainer = document.createElement('div');
            subcategoryChartContainer.id = 'subcategoryPieChartContainer';
            subcategoryChartContainer.className = 'card';
            subcategoryChartContainer.innerHTML = `<h3>Subcategorias de ${categoryName}</h3><div class="chart-container"><canvas id="subcategoryPieChart"></canvas></div>`;
            reportsPageContent.closest('.card').insertAdjacentElement('afterend', subcategoryChartContainer);
        } else {
            subcategoryChartContainer.querySelector('h3').textContent = `Subcategorias de ${categoryName}`;
        }
        
        new Chart(document.getElementById('subcategoryPieChart'), {
            type: 'pie',
            data: {
                labels: subcategoryData.map(item => item.name),
                datasets: [{ data: subcategoryData.map(item => item.value) }]
            },
            options: { responsive: true, maintainAspectRatio: false }
        });
    } else if (subcategoryData) {
        showInfo(`Nenhuma subcategoria encontrada para ${categoryName} neste período.`);
    }
}

async function loadEvolutionLineChart(canvasId) {
    if (!currentFamilyId) return;
    const canvasElement = document.getElementById(canvasId);
     if (!canvasElement) {
        console.warn(`Canvas element ${canvasId} not found for line chart.`);
        return;
    }
    const data = await apiRequest(`/reports/expenses_evolution?family_id=${currentFamilyId}&months=6`);
    if (data && data.length > 0) {
        new Chart(canvasElement, {
            type: 'line',
            data: {
                labels: data.map(item => item.label),
                datasets: [
                    {
                        label: 'Total Gasto',
                        data: data.map(item => item.total_spent),
                        borderColor: 'rgba(255, 99, 132, 1)',
                        tension: 0.1
                    },
                    {
                        label: 'Orçamento Planejado',
                        data: data.map(item => item.planned_budget),
                        borderColor: 'rgba(54, 162, 235, 1)',
                        tension: 0.1
                    }
                ]
            },
            options: { responsive: true, maintainAspectRatio: false }
        });
    } else if (data) {
         canvasElement.parentElement.innerHTML = '<p>Sem dados suficientes para o gráfico de evolução.</p>';
    }
}

async function loadBudgetVsActualReport(elementId, year, month) {
    if (!currentFamilyId) return;
    const element = document.getElementById(elementId);
    if (!element) return;
    const data = await apiRequest(`/reports/budget_vs_actual?family_id=${currentFamilyId}&year=${year}&month=${month}`);
    if (data) {
        element.innerHTML = `
            <p>Orçamento Planejado: R$ ${data.planned_budget.toFixed(2)}</p>
            <p>Total Gasto: R$ ${data.total_spent.toFixed(2)}</p>
            <p><strong>Saldo: R$ ${data.difference.toFixed(2)}</strong></p>
        `;
    }
}

function showInfo(message) { // Similar to showError/showSuccess but for general info
    const infoDiv = document.createElement('div');
    infoDiv.className = 'info-message'; // Needs CSS class
    infoDiv.textContent = message;
    if (appContent.firstChild) {
        appContent.insertBefore(infoDiv, appContent.firstChild);
    } else {
        appContent.appendChild(infoDiv);
    }
    setTimeout(() => infoDiv.remove(), 4000);
}

// --- Initial Load ---
document.addEventListener('DOMContentLoaded', () => {
    window.addEventListener('popstate', router); // Handle browser back/forward
    checkAuth().then(() => {
        router(); // Initial route handling
    });
});

// Add Chart.js CDN to index.html if not already present.
// This script assumes Chart.js is available globally.
// Example: <script src="https://cdn.jsdelivr.net/npm/chart.js"></script> in index.html <head>

