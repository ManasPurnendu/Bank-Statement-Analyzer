document.addEventListener("DOMContentLoaded", function () {
    // --- GLOBAL SETUP ---
    initTheme();
    setupActiveNav();
    
    // Determine current page route
    const path = window.location.pathname;
    
    if (path === '/' || path === '') {
        initLandingPage();
    } else if (path.includes('/dashboard')) {
        initDashboardPage();
    } else if (path.includes('/transactions')) {
        initTransactionsPage();
    } else if (path.includes('/analytics')) {
        initAnalyticsPage();
    } else if (path.includes('/forecast')) {
        initForecastPage();
    } else if (path.includes('/report')) {
        initReportsPage();
    }
    
    // Always fetch sidebar metadata to show loaded statements (unless on landing/upload panel)
    if (path !== '/' && path !== '') {
        fetchSidebarData();
    }

});

/* --- THEME / DARK MODE MANAGER --- */
function initTheme() {
    const toggle = document.getElementById("darkModeToggle");
    const currentTheme = localStorage.getItem("theme") || "light";
    
    document.documentElement.setAttribute("data-theme", currentTheme);
    if (toggle) {
        toggle.checked = currentTheme === "dark";
        toggle.addEventListener("change", function () {
            const theme = this.checked ? "dark" : "light";
            document.documentElement.setAttribute("data-theme", theme);
            localStorage.setItem("theme", theme);
            // Refresh current page charts if present
            window.location.reload();
        });
    }
}

function setupActiveNav() {
    const path = window.location.pathname;
    const navs = {
        '/dashboard': 'nav-dashboard',
        '/transactions': 'nav-transactions',
        '/analytics': 'nav-analytics',
        '/forecast': 'nav-forecasts',
        '/forecasts': 'nav-forecasts',
        '/reports': 'nav-reports',
        '/report': 'nav-reports'
    };
    
    // Remove active class from all
    document.querySelectorAll(".nav-item").forEach(item => item.classList.remove("active"));
    
    // Add to current
    for (let key in navs) {
        if (path.includes(key)) {
            const activeId = navs[key];
            const activeNav = document.getElementById(activeId);
            if (activeNav) activeNav.classList.add("active");
            break;
        }
    }
}

/* --- SIDEBAR META INGESTION --- */
function fetchSidebarData() {
    fetch('/api/dashboard')
        .then(res => res.json())
        .then(data => {
            if (data.success && data.analytics && data.analytics.raw_count > 0) {
                document.getElementById("sidebar-dynamic-sections").style.display = "block";
                
                // 1. Populate loaded statements list from database
                fetch('/api/statements')
                    .then(res => res.json())
                    .then(stmtData => {
                        const stmtContainer = document.getElementById("sidebar-statements-list");
                        stmtContainer.innerHTML = "";
                        
                        if (stmtData.success && stmtData.statements && stmtData.statements.length > 0) {
                            stmtData.statements.forEach(s => {
                                const safeFileName = s.file_name.replace(/'/g, "\\'").replace(/"/g, '&quot;');
                                stmtContainer.innerHTML += `
                                    <div class="sidebar-list-item d-flex justify-content-between align-items-center mb-1">
                                        <div class="sidebar-list-item-content flex-grow-1 overflow-hidden d-flex align-items-center gap-2">
                                            <i class="bi bi-file-earmark-spreadsheet-fill text-success" style="font-size: 16px; flex-shrink: 0;"></i>
                                            <div style="min-width: 0;">
                                                <div class="sidebar-list-item-title text-truncate fw-bold" title="${s.file_name}" style="font-size: 13px;">${s.file_name}</div>
                                                <div class="sidebar-list-item-sub text-muted text-truncate" style="font-size: 10px;">${s.bank_name} • ${formatMonthLabel(s.statement_month)}</div>
                                            </div>
                                        </div>
                                        <button type="button" class="btn btn-link text-danger p-0 ms-2 delete-statement-btn" onclick="window.deleteStatement(${s.statement_id}, '${safeFileName}')" style="text-decoration: none; font-size: 14px; flex-shrink: 0;" title="Delete this statement">
                                            <i class="bi bi-trash-fill"></i>
                                        </button>
                                    </div>`;
                            });
                        } else {
                            stmtContainer.innerHTML = `<div class="text-muted small p-2">No statements loaded</div>`;
                        }
                    });
                
                // 2. Populate data coverage list from analytics trends
                const coverage = data.analytics.data_coverage || [];
                const coverageContainer = document.getElementById("sidebar-coverage-list");
                coverageContainer.innerHTML = "";
                
                coverage.forEach(item => {
                    if (item.status === 'placeholder') {
                        coverageContainer.innerHTML += `
                            <div class="sidebar-coverage-item">
                                <span class="text-muted">${item.name}</span>
                                <span class="missing-dash">-</span>
                            </div>`;
                    } else if (item.status === 'active') {
                        coverageContainer.innerHTML += `
                            <div class="sidebar-coverage-item">
                                <span>${item.name}</span>
                                <span class="active-dot"><i class="bi bi-check-circle-fill"></i></span>
                            </div>`;
                    } else {
                        coverageContainer.innerHTML += `
                            <div class="sidebar-coverage-item">
                                <span class="text-muted">${item.name}</span>
                                <span class="missing-dash">-</span>
                            </div>`;
                    }
                });
            } else {
                document.getElementById("sidebar-dynamic-sections").style.display = "none";
            }
        })
        .catch(err => {
            console.error("Error fetching sidebar data:", err);
        });
}

/* --- LANDING & UPLOAD COMPONENT --- */
function initLandingPage() {
    const dropzone = document.getElementById("dropzone");
    const fileInput = document.getElementById("fileInput");
    const browseBtn = document.getElementById("browseBtn");
    const loadDemoBtn = document.getElementById("loadDemoBtn");
    
    const passwordModal = new bootstrap.Modal(document.getElementById('passwordModal'));
    const submitPasswordBtn = document.getElementById("submitPasswordBtn");
    const pdfPasswordInput = document.getElementById("pdfPassword");
    
    const duplicateModal = new bootstrap.Modal(document.getElementById('duplicateModal'));
    const duplicateSkipBtn = document.getElementById("duplicateSkipBtn");
    const duplicateReplaceBtn = document.getElementById("duplicateReplaceBtn");
    
    let pendingFiles = [];
    let duplicateInfo = null;
    let currentPassword = null;

    // Modal Close/Cancel Handlers
    document.getElementById("closePasswordBtn").addEventListener("click", resetUploadView);
    document.getElementById("cancelPasswordBtn").addEventListener("click", resetUploadView);
    document.getElementById("closeDuplicateBtn").addEventListener("click", resetUploadView);

    // Browse files
    const navUploadBtn = document.getElementById("navUploadBtn");
    if (navUploadBtn) navUploadBtn.addEventListener("click", () => fileInput.click());

    browseBtn.addEventListener("click", () => fileInput.click());
    fileInput.addEventListener("change", (e) => handleFiles(e.target.files));
    
    // Drag & Drop
    dropzone.addEventListener("dragover", (e) => {
        e.preventDefault();
        dropzone.classList.add("dragover");
    });
    
    dropzone.addEventListener("dragleave", () => {
        dropzone.classList.remove("dragover");
    });
    
    dropzone.addEventListener("drop", (e) => {
        e.preventDefault();
        dropzone.classList.remove("dragover");
        handleFiles(e.dataTransfer.files);
    });

    // Load Demo Data Button
    loadDemoBtn.addEventListener("click", () => {
        startProcessingAnimation();
        
        const formData = new FormData();
        formData.append("demo", "true");
        
        fetch('/api/upload', {
            method: 'POST',
            body: formData
        })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                runSimulationSteps(() => {
                    window.location.href = '/dashboard';
                });
            } else {
                alert("Failed to load demo data: " + data.message);
                resetUploadView();
            }
        })
        .catch(err => {
            alert("Connection error occurred: " + err.message);
            resetUploadView();
        });
    });

    function handleFiles(files) {
        if (files.length === 0) return;
        pendingFiles = Array.from(files);
        uploadNextFile();
    }

    function uploadNextFile(password = null, action = null) {
        if (pendingFiles.length === 0) {
            // Done uploading all
            runSimulationSteps(() => {
                window.location.href = '/dashboard';
            });
            return;
        }
        
        const file = pendingFiles[0];
        const formData = new FormData();
        formData.append("files", file);
        if (password) {
            currentPassword = password;
            formData.append("password", password);
        } else if (currentPassword) {
            formData.append("password", currentPassword);
        }
        if (action) formData.append("action", action);
        
        startProcessingAnimation();
        updateProcessingStep('upload', 'active');
        
        fetch('/api/upload', {
            method: 'POST',
            body: formData
        })
        .then(res => {
            if (res.status === 401) {
                // Password Required / Incorrect
                return res.json().then(data => {
                    stopProcessingAnimation();
                    passwordModal.show();
                    if (data.error === "IncorrectPassword") {
                        document.getElementById("passwordError").style.display = "block";
                        pdfPasswordInput.classList.add("is-invalid");
                    } else {
                        document.getElementById("passwordError").style.display = "none";
                        pdfPasswordInput.classList.remove("is-invalid");
                    }
                    return null; // Signal to skip the next .then()
                });
            } else if (res.status === 409) {
                // Duplicate Statement
                return res.json().then(data => {
                    stopProcessingAnimation();
                    duplicateInfo = data.details;
                    document.getElementById("duplicateDetails").innerText = 
                        `Statement '${duplicateInfo.file_name}' for account ${duplicateInfo.account_number} (${duplicateInfo.period}) is already uploaded.`;
                    duplicateModal.show();
                    return null; // Signal to skip the next .then()
                });
            }
            return res.json();
        })
        .then(data => {
            if (!data) return; // Handled via modal popups
            
            if (data.success) {
                // Shift file from array and parse next
                pendingFiles.shift();
                // Retain currentPassword for subsequent files in this batch upload
                uploadNextFile();
            } else {
                alert("Upload failed: " + data.message);
                resetUploadView();
            }
        })
        .catch(err => {
            console.error("Upload error:", err);
            alert("An error occurred: " + err.message);
            resetUploadView();
        });
    }

    // Password submit
    submitPasswordBtn.addEventListener("click", () => {
        const password = pdfPasswordInput.value;
        if (!password) return;
        passwordModal.hide();
        uploadNextFile(password);
    });

    // Duplicate Replace / Skip
    duplicateReplaceBtn.addEventListener("click", () => {
        duplicateModal.hide();
        uploadNextFile(null, 'replace');
    });
    
    duplicateSkipBtn.addEventListener("click", () => {
        duplicateModal.hide();
        // Skip current and continue with next file
        pendingFiles.shift();
        // Retain currentPassword for subsequent files in this batch upload
        uploadNextFile();
    });

    function startProcessingAnimation() {
        document.getElementById("upload-panel").style.display = "none";
        document.getElementById("processing-panel").style.display = "block";
    }

    function stopProcessingAnimation() {
        document.getElementById("upload-panel").style.display = "block";
        document.getElementById("processing-panel").style.display = "none";
    }

    function resetUploadView() {
        stopProcessingAnimation();
        fileInput.value = "";
        pdfPasswordInput.value = "";
        pendingFiles = [];
        currentPassword = null;
    }

    function updateProcessingStep(stepId, state) {
        const el = document.getElementById(`step-${stepId}`);
        if (!el) return;
        
        el.className = "processing-step";
        if (state === 'active') {
            el.classList.add("active");
            el.querySelector("i").className = "bi bi-arrow-repeat spin-icon";
            document.getElementById("processing-title").innerText = el.querySelector("span").innerText;
        } else if (state === 'completed') {
            el.classList.add("completed");
            el.querySelector("i").className = "bi bi-check-circle-fill";
        } else {
            el.querySelector("i").className = "bi bi-circle";
        }
    }

    function runSimulationSteps(callback) {
        const steps = ['upload', 'analyze', 'extract', 'categorize', 'insights', 'ready'];
        let idx = 0;
        
        function next() {
            if (idx > 0) {
                updateProcessingStep(steps[idx-1], 'completed');
            }
            if (idx < steps.length) {
                updateProcessingStep(steps[idx], 'active');
                idx++;
                setTimeout(next, 1000); // 1 sec simulation ticks
            } else {
                callback();
            }
        }
        next();
    }
}

/* --- DASHBOARD VIEW MANAGER --- */
/* --- DASHBOARD VIEW MANAGER --- */
function initDashboardPage(range = 'all') {
    fetch(`/api/dashboard?range=${range}`)
        .then(res => res.json())
        .then(data => {
            if (data.success && data.analytics && data.analytics.raw_count > 0) {
                document.getElementById("dashboard-empty-state").style.display = "none";
                document.getElementById("dashboard-filled-state").style.display = "block";
                
                if (data.analytics.start_date && data.analytics.end_date) {
                    document.getElementById("date-filter-label").innerText = 
                        `${formatDateString(data.analytics.start_date)} - ${formatDateString(data.analytics.end_date)}`;
                }
                
                renderDashboardMetrics(data.analytics, data.insights, range);
            } else {
                document.getElementById("dashboard-empty-state").style.display = "block";
                document.getElementById("dashboard-filled-state").style.display = "none";
            }
        })
        .catch(err => console.error("Dashboard fetch error:", err));

    // Bind global dropdown items
    const dropdown = document.getElementById("dashboard-date-dropdown");
    if (dropdown && !dropdown.dataset.listenerBound) {
        dropdown.dataset.listenerBound = "true";
        dropdown.addEventListener("click", function(e) {
            const btn = e.target.closest("button");
            if (btn) {
                const r = btn.getAttribute("data-range");
                const text = btn.innerText;
                document.getElementById("date-filter-label").innerText = text;
                initDashboardPage(r);
            }
        });
    }

    // Bind individual chart timeline selectors
    const ieSelect = document.getElementById("incomeVsExpenseTimeline");
    if (ieSelect && !ieSelect.dataset.listenerBound) {
        ieSelect.dataset.listenerBound = "true";
        ieSelect.addEventListener("change", function(e) {
            const r = e.target.value;
            fetch(`/api/dashboard?range=${r}`)
                .then(res => res.json())
                .then(data => {
                    if (data.success && data.analytics) {
                        updateIncomeExpenseChart(data.analytics);
                    }
                });
        });
    }

    const catSelect = document.getElementById("categoryTimeline");
    if (catSelect && !catSelect.dataset.listenerBound) {
        catSelect.dataset.listenerBound = "true";
        catSelect.addEventListener("change", function(e) {
            const r = e.target.value;
            fetch(`/api/dashboard?range=${r}`)
                .then(res => res.json())
                .then(data => {
                    if (data.success && data.analytics) {
                        updateCategoryDonutChart(data.analytics);
                    }
                });
        });
    }
}

function updateIncomeExpenseChart(analytics) {
    const trends = analytics.monthly_trends || [];
    const months = trends.map(t => formatMonthLabel(t.month));
    const incomes = trends.map(t => t.income);
    const expenses = trends.map(t => t.expense);
    const savings = trends.map(t => t.savings);
    
    const ctxBar = document.getElementById('incomeExpenseChart').getContext('2d');
    if (window.dashboardBarChart) {
        window.dashboardBarChart.destroy();
    }
    window.dashboardBarChart = new Chart(ctxBar, {
        type: 'bar',
        data: {
            labels: months,
            datasets: [
                { label: 'Income', data: incomes, backgroundColor: '#10b981', borderRadius: 4 },
                { label: 'Expenses', data: expenses, backgroundColor: '#ef4444', borderRadius: 4 },
                { label: 'Savings', data: savings, backgroundColor: '#2563eb', borderRadius: 4 }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: 'bottom', labels: { boxWidth: 12, usePointStyle: true } }
            },
            scales: {
                y: { grid: { color: 'rgba(0,0,0,0.05)' }, ticks: { callback: value => '₹' + formatCompactNumber(value) } },
                x: { grid: { display: false } }
            }
        }
    });
}

function updateCategoryDonutChart(analytics) {
    const catSpending = analytics.category_spending || [];
    const catLabels = catSpending.map(c => c.category_name);
    const catValues = catSpending.map(c => c.amount);
    
    // Harmonic color palette for HSL
    const catColors = [
        '#f59e0b', '#3b82f6', '#10b981', '#8b5cf6', '#ec4899', 
        '#ef4444', '#06b6d4', '#64748b', '#f97316', '#6b7280'
    ];
    
    const ctxDonut = document.getElementById('categoryDonutChart').getContext('2d');
    if (window.dashboardDonutChart) {
        window.dashboardDonutChart.destroy();
    }
    window.dashboardDonutChart = new Chart(ctxDonut, {
        type: 'doughnut',
        data: {
            labels: catLabels,
            datasets: [{
                data: catValues,
                backgroundColor: catColors,
                borderWidth: 2,
                borderColor: document.documentElement.getAttribute("data-theme") === 'dark' ? '#151b2c' : '#ffffff'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: 'right', labels: { boxWidth: 10, pointStyle: 'circle', usePointStyle: true } }
            },
            cutout: '65%'
        }
    });
}

function renderDashboardMetrics(analytics, insights, range = 'this-year') {
    const kpis = analytics.kpis;
    
    // Dynamic welcome title (takes name from parsed statements)
    const activeCoverage = analytics.data_coverage.filter(c => c.status === 'active');
    if (activeCoverage.length > 0) {
        document.getElementById("statement-range-subtitle").innerText = 
            `Financial overview for ${activeCoverage[0].name} - ${activeCoverage[activeCoverage.length-1].name}`;
    }
    
    // Write KPI values
    document.getElementById("kpi-balance").innerText = formatCurrency(kpis.balance);
    document.getElementById("kpi-income").innerText = formatCurrency(kpis.income);
    document.getElementById("kpi-expense").innerText = formatCurrency(kpis.expense);
    document.getElementById("kpi-savings").innerText = formatCurrency(kpis.savings);
    document.getElementById("kpi-savings-rate").innerText = `${kpis.savings_rate.toFixed(1)}%`;
    
    // 1. Chart - Income vs Expenses Bar Chart
    updateIncomeExpenseChart(analytics);

    // 2. Chart - Expenses by Category Donut
    updateCategoryDonutChart(analytics);    

    // 3. Lists - Top Categories
    const catSpending = analytics.category_spending || [];
    const topCatContainer = document.getElementById("dashboard-top-categories");
    topCatContainer.innerHTML = "";
    const maxCatSpend = catSpending.length > 0 ? catSpending[0].amount : 1;
    catSpending.slice(0, 5).forEach(c => {
        const pct = (c.amount / maxCatSpend) * 100;
        const color = getCategoryColorHex(c.category_name);
        topCatContainer.innerHTML += `
            <div class="list-premium-item py-2 d-flex flex-column align-items-stretch gap-1">
                <div class="d-flex justify-content-between align-items-center">
                    <span class="fw-semibold small text-truncate" style="max-width: 140px;">${c.category_name}</span>
                    <span class="small font-bold">${formatCurrency(c.amount)}</span>
                </div>
                <div class="list-progress-bar">
                    <div class="list-progress-fill" style="width: ${pct}%; background-color: ${color}"></div>
                </div>
            </div>`;
    });

    // 4. Lists - Top Merchants
    const topMerchantContainer = document.getElementById("dashboard-top-merchants");
    topMerchantContainer.innerHTML = "";
    
    // Find max value for progress fills
    const maxMerchantSpend = analytics.top_merchants.length > 0 ? analytics.top_merchants[0].total_spend : 1;
    
    analytics.top_merchants.slice(0, 5).forEach(m => {
        const pct = (m.total_spend / maxMerchantSpend) * 100;
        topMerchantContainer.innerHTML += `
            <div class="list-premium-item py-2 d-flex flex-column align-items-stretch gap-1">
                <div class="d-flex justify-content-between align-items-center">
                    <span class="fw-semibold small text-truncate" style="max-width: 140px;">${m.merchant_name}</span>
                    <span class="small font-bold">${formatCurrency(m.total_spend)}</span>
                </div>
                <div class="list-progress-bar">
                    <div class="list-progress-fill" style="width: ${pct}%"></div>
                </div>
            </div>`;
    });

    // 5. Lists - Recent Transactions
    const recentTxContainer = document.getElementById("dashboard-recent-transactions");
    recentTxContainer.innerHTML = "";
    
    // We can fetch transactions list
    fetch('/api/transactions?limit=5')
        .then(res => res.json())
        .then(txData => {
            if (txData.success && txData.transactions) {
                txData.transactions.forEach(t => {
                    const amtClass = t.transaction_type === 'Credit' ? 'amount-credit' : 'amount-debit';
                    const prefix = t.transaction_type === 'Credit' ? '+' : '-';
                    const catClass = getCategoryClass(t.category_name);
                    recentTxContainer.innerHTML += `
                        <tr style="font-size: 11px;">
                            <td class="text-nowrap" style="font-size: 10px; color: var(--text-muted);">${formatDateString(t.transaction_date)}</td>
                            <td class="fw-semibold text-truncate" style="max-width: 110px;" title="${t.description}">${t.description.replace(/\n/g, ' ')}</td>
                            <td><span class="badge-category ${catClass}" style="padding: 2px 8px; font-size: 9px;">${t.category_name}</span></td>
                            <td><span class="fw-semibold text-capitalize ${t.transaction_type === 'Credit' ? 'text-success' : 'text-danger'}">${t.transaction_type}</span></td>
                            <td class="${amtClass} text-nowrap text-end">${prefix} ${formatCurrency(t.amount)}</td>
                        </tr>`;
                });
            }
        });

    // 6. Insights Drawer Preview
    const insightsContainer = document.getElementById("dashboard-insights-preview");
    insightsContainer.innerHTML = "";
    insights.slice(0, 3).forEach(i => {
        insightsContainer.innerHTML += `
            <div class="insight-card p-2 px-3 mb-2">
                <div class="insight-card-icon ${i.status}"><i class="bi ${i.icon}"></i></div>
                <div class="insight-card-text small" style="line-height: 1.3;">${i.text}</div>
            </div>`;
    });

    // 7. Monthly Overview Table with Sparklines
    const monthlyTableBody = document.getElementById("dashboard-monthly-rows");
    monthlyTableBody.innerHTML = "";
    
    // Gather savings rate values for sparklines
    const trends = analytics.monthly_trends || [];
    const sRates = trends.map(t => t.savings_rate);
    const maxRate = Math.max(...sRates, 1);
    
    trends.forEach((t, index) => {
        // Build SVG Sparkline bar chart
        let sparklineBars = "";
        trends.forEach((mo, moIdx) => {
            const h = Math.max(2, (mo.savings_rate / maxRate) * 18);
            const fill = moIdx === index ? '#2563eb' : '#cbd5e1';
            sparklineBars += `<rect x="${moIdx * 12}" y="${20 - h}" width="8" height="${h}" fill="${fill}" rx="2"></rect>`;
        });
        
        const sparklineSVG = `
            <svg width="80" height="24" viewBox="0 0 80 24" class="overflow-visible">
                ${sparklineBars}
            </svg>`;
            
        monthlyTableBody.innerHTML += `
            <tr>
                <td class="fw-bold">${formatMonthLabel(t.month)}</td>
                <td class="amount-credit">+ ${formatCurrency(t.income)}</td>
                <td class="amount-debit">- ${formatCurrency(t.expense)}</td>
                <td class="${t.savings >= 0 ? 'text-success' : 'text-danger'} font-semibold">${formatCurrency(t.savings)}</td>
                <td><span class="badge bg-light text-dark border px-2 py-1">${t.savings_rate.toFixed(1)}%</span></td>
                <td>${sparklineSVG}</td>
            </tr>`;
    });
}

/* --- TRANSACTIONS PAGE AUDIT --- */
let currentTransactionsPage = 1;
let currentSortCol = 'transaction_date';
let currentSortOrd = 'DESC';

function initTransactionsPage() {
    // Populate categories select dropdown
    const catSelect = document.getElementById("categoryVal");
    const modalSelect = document.getElementById("modalCategorySelect");
    
    fetch('/api/categories')
        .then(res => res.json())
        .then(data => {
            if (data.success && data.categories) {
                data.categories.forEach(c => {
                    catSelect.innerHTML += `<option value="${c.category_id}">${c.category_name}</option>`;
                    modalSelect.innerHTML += `<option value="${c.category_id}">${c.category_name}</option>`;
                });
            }
        });
        
    // Initial fetch
    loadTransactions();
    
    // Form filter bindings
    document.getElementById("searchVal").addEventListener("input", debounce(loadTransactions, 300));
    document.getElementById("categoryVal").addEventListener("change", loadTransactions);
    document.getElementById("typeVal").addEventListener("change", loadTransactions);
    document.getElementById("startDateVal").addEventListener("change", loadTransactions);
    document.getElementById("endDateVal").addEventListener("change", loadTransactions);
    
    document.getElementById("clearFiltersBtn").addEventListener("click", () => {
        document.getElementById("filters-form").reset();
        loadTransactions();
    });
    
    // Sort columns click bindings
    document.getElementById("th-date").addEventListener("click", () => triggerSort('transaction_date'));
    document.getElementById("th-amount").addEventListener("click", () => triggerSort('amount'));

    // Bind Classify button using event delegation
    const tbody = document.getElementById("transactions-rows");
    if (tbody) {
        tbody.addEventListener("click", function(e) {
            const btn = e.target.closest(".classify-btn");
            if (btn) {
                const txnId = btn.getAttribute("data-id");
                const catId = btn.getAttribute("data-category-id");
                if (txnId && window.loadedTransactions) {
                    const txn = window.loadedTransactions.find(t => t.transaction_id == txnId);
                    if (txn) {
                        openCategoryEditModal(txn.transaction_id, txn.description, catId);
                    }
                }
            }
        });
    }
}

function loadTransactions() {
    const q = document.getElementById("searchVal").value;
    const cat = document.getElementById("categoryVal").value;
    const type = document.getElementById("typeVal").value;
    const start = document.getElementById("startDateVal").value;
    const end = document.getElementById("endDateVal").value;
    
    let url = `/api/transactions?page=${currentTransactionsPage}&limit=15&sort_by=${currentSortCol}&sort_order=${currentSortOrd}`;
    if (q) url += `&q=${q}`;
    if (cat) url += `&category_id=${cat}`;
    if (type) url += `&type_filter=${type}`;
    if (start) url += `&start_date=${start}`;
    if (end) url += `&end_date=${end}`;
    
    fetch(url)
        .then(res => res.json())
        .then(data => {
            const tbody = document.getElementById("transactions-rows");
            tbody.innerHTML = "";
            
            if (data.success && data.transactions && data.transactions.length > 0) {
                document.getElementById("table-empty-state").style.display = "none";
                window.loadedTransactions = data.transactions; // Save loaded transactions
                
                data.transactions.forEach(t => {
                    const amtClass = t.transaction_type === 'Credit' ? 'amount-credit' : 'amount-debit';
                    const prefix = t.transaction_type === 'Credit' ? '+' : '-';
                    const catBadge = `<span class="badge-category ${getCategoryClass(t.category_name)}">${t.category_name}</span>`;
                    
                    tbody.innerHTML += `
                        <tr>
                            <td>${formatDateString(t.transaction_date)}</td>
                            <td class="text-truncate fw-semibold" style="max-width: 260px;" title="${t.description}">
                                ${t.description.replace(/\n/g, ' ')}
                            </td>
                            <td>${catBadge}</td>
                            <td>${t.transaction_type}</td>
                            <td class="${amtClass} font-bold">${prefix} ${formatCurrency(t.amount)}</td>
                            <td>
                                <button type="button" class="btn btn-outline-primary btn-xs px-2 py-1 classify-btn" data-id="${t.transaction_id}" data-category-id="${t.category_id}">
                                    <i class="bi bi-tag-fill me-1"></i> Classify
                                </button>
                            </td>
                        </tr>`;
                });
                
                renderPagination(data.pagination);
            } else {
                document.getElementById("table-empty-state").style.display = "block";
                document.getElementById("pagination-info").innerText = "Showing 0 to 0 of 0 transactions";
                document.getElementById("pagination-controls").innerHTML = "";
            }
        });
}

function triggerSort(col) {
    if (currentSortCol === col) {
        currentSortOrd = currentSortOrd === 'DESC' ? 'ASC' : 'DESC';
    } else {
        currentSortCol = col;
        currentSortOrd = 'DESC';
    }
    loadTransactions();
}

function renderPagination(meta) {
    const start = (meta.page - 1) * meta.limit + 1;
    const end = Math.min(meta.page * meta.limit, meta.total);
    
    document.getElementById("pagination-info").innerText = `Showing ${start} to ${end} of ${meta.total} transactions`;
    
    const controls = document.getElementById("pagination-controls");
    controls.innerHTML = "";
    
    // Back arrow
    const prevDisabled = meta.page === 1 ? 'disabled' : '';
    controls.innerHTML += `
        <li class="page-item ${prevDisabled}">
            <a class="page-link" href="#" onclick="changePage(${meta.page - 1})"><i class="bi bi-chevron-left"></i></a>
        </li>`;
        
    // Page digits
    for (let p = 1; p <= meta.pages; p++) {
        if (p === 1 || p === meta.pages || (p >= meta.page - 2 && p <= meta.page + 2)) {
            const active = p === meta.page ? 'active' : '';
            controls.innerHTML += `
                <li class="page-item ${active}">
                    <a class="page-link" href="#" onclick="changePage(${p})">${p}</a>
                </li>`;
        } else if (p === meta.page - 3 || p === meta.page + 3) {
            controls.innerHTML += `<li class="page-item disabled"><a class="page-link" href="#">...</a></li>`;
        }
    }
    
    // Next arrow
    const nextDisabled = meta.page === meta.pages ? 'disabled' : '';
    controls.innerHTML += `
        <li class="page-item ${nextDisabled}">
            <a class="page-link" href="#" onclick="changePage(${meta.page + 1})"><i class="bi bi-chevron-right"></i></a>
        </li>`;
}

function changePage(p) {
    event.preventDefault();
    currentTransactionsPage = p;
    loadTransactions();
}

// Edit Category Modal triggers
let editTransactionId = null;
let categoryEditModal = null;

window.openCategoryEditModal = function(txnId, desc, catId) {
    if (!categoryEditModal) {
        const el = document.getElementById('categoryEditModal');
        if (el) categoryEditModal = new bootstrap.Modal(el);
    }
    editTransactionId = txnId;
    document.getElementById("modal-orig-narration").innerText = desc;
    document.getElementById("modalCategorySelect").value = catId;
    document.getElementById("modalRememberCheckbox").checked = false;
    const amountCb = document.getElementById("modalRememberAmountCheckbox");
    if (amountCb) amountCb.checked = false;
    if (categoryEditModal) categoryEditModal.show();
};

const saveCategoryBtnEl = document.getElementById("saveCategoryBtn");
if (saveCategoryBtnEl) saveCategoryBtnEl.addEventListener("click", () => {
    const catId = document.getElementById("modalCategorySelect").value;
    const remember = document.getElementById("modalRememberCheckbox").checked;
    const rememberAmountEl = document.getElementById("modalRememberAmountCheckbox");
    const rememberAmount = rememberAmountEl ? rememberAmountEl.checked : false;
    
    fetch('/api/transaction/category', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            transaction_id: editTransactionId,
            category_id: parseInt(catId),
            remember: remember,
            remember_amount: rememberAmount
        })
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            categoryEditModal.hide();
            loadTransactions();
            
            // Show toast or toast notification
            showToast("Category Updated Successfully!");
        } else {
            alert("Update failed: " + data.message);
        }
    });
});

/* --- ANALYTICS DETAILED CHARTS & HEATMAPS --- */
/* --- ANALYTICS DETAILED CHARTS & HEATMAPS --- */
function initAnalyticsPage(range = 'all') {
    fetch(`/api/analytics?range=${range}`)
        .then(res => res.json())
        .then(data => {
            if (data.success && data.analytics && data.analytics.raw_count > 0) {
                if (data.analytics.start_date && data.analytics.end_date) {
                    document.getElementById("analytics-date-label").innerText = 
                        `${formatDateString(data.analytics.start_date)} - ${formatDateString(data.analytics.end_date)}`;
                }
                renderAnalyticsView(data.analytics, range);
            }
        });
        
    // Bind global dropdown items
    const dropdown = document.getElementById("analytics-date-dropdown");
    if (dropdown && !dropdown.dataset.listenerBound) {
        dropdown.dataset.listenerBound = "true";
        dropdown.addEventListener("click", function(e) {
            const btn = e.target.closest("button");
            if (btn) {
                const r = btn.getAttribute("data-range");
                const text = btn.innerText;
                document.getElementById("analytics-date-label").innerText = text;
                initAnalyticsPage(r);
            }
        });
    }

    // Bind spending overview select
    const overviewSelect = document.getElementById("spendingOverviewTimeline");
    if (overviewSelect && !overviewSelect.dataset.listenerBound) {
        overviewSelect.dataset.listenerBound = "true";
        overviewSelect.addEventListener("change", function(e) {
            const r = e.target.value;
            fetch(`/api/analytics?range=${r}`)
                .then(res => res.json())
                .then(data => {
                    if (data.success && data.analytics) {
                        updateSpendingOverviewChart(data.analytics);
                    }
                });
        });
    }
}

function updateSpendingOverviewChart(analytics) {
    const trends = analytics.monthly_trends || [];
    const months = trends.map(t => formatMonthLabel(t.month));
    const spendingList = trends.map(t => t.expense);
    
    const ctxOverview = document.getElementById('spendingOverviewChart').getContext('2d');
    if (window.analyticsOverviewChart) {
        window.analyticsOverviewChart.destroy();
    }
    window.analyticsOverviewChart = new Chart(ctxOverview, {
        type: 'line',
        data: {
            labels: months,
            datasets: [{
                label: 'Monthly Spend',
                data: spendingList,
                borderColor: '#3b82f6',
                backgroundColor: 'rgba(59, 130, 246, 0.05)',
                borderWidth: 3,
                tension: 0.3,
                fill: true,
                pointBackgroundColor: '#2563eb',
                pointHoverRadius: 6
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                y: { grid: { color: 'rgba(0,0,0,0.05)' }, ticks: { callback: v => '₹' + formatCompactNumber(v) } },
                x: { grid: { display: false } }
            }
        }
    });
}

function renderAnalyticsView(analytics, range = 'this-year') {
    const kpis = analytics.kpis;
    
    // Set text timelines
    const activeCoverage = analytics.data_coverage.filter(c => c.status === 'active');
    if (activeCoverage.length > 0) {
        document.getElementById("analytics-spend-timeline").innerText = 
            `${activeCoverage[0].name} - ${activeCoverage[activeCoverage.length-1].name}`;
    }
    
    document.getElementById("analytics-total-spend").innerText = formatCurrency(kpis.expense);
    document.getElementById("analytics-avg-spend").innerText = formatCurrency(kpis.average_monthly_spend);
    document.getElementById("analytics-highest-cat").innerText = kpis.highest_category;
    document.getElementById("analytics-highest-cat-amount").innerText = 
        analytics.category_spending.length > 0 ? `${formatCurrency(analytics.category_spending[0].amount)} total` : "₹0.00";
    document.getElementById("analytics-busiest-day").innerText = kpis.busiest_day;
    document.getElementById("analytics-busiest-day-amount").innerText = `${formatCurrency(kpis.busiest_day_amount)} spent`;
    document.getElementById("analytics-total-txs").innerText = kpis.transaction_count;
    document.getElementById("analytics-avg-txs-month").innerText = `${Math.round(kpis.transaction_count / (analytics.monthly_trends.length || 1))} per month`;
    
    // 1. Spending Overview (Line Chart)
    updateSpendingOverviewChart(analytics);

    // 2. Spending by Category (Pie Chart)
    const catSpending = analytics.category_spending || [];
    const catLabels = catSpending.map(c => c.category_name);
    const catValues = catSpending.map(c => c.amount);
    
    const catColors = [
        '#f59e0b', '#3b82f6', '#10b981', '#8b5cf6', '#ec4899', 
        '#ef4444', '#06b6d4', '#64748b', '#f97316', '#6b7280'
    ];
    
    document.getElementById("spending-category-total").innerText = formatCurrency(kpis.expense);
    const ctxCat = document.getElementById('spendingCategoryChart').getContext('2d');
    if (window.analyticsCatChart) {
        window.analyticsCatChart.destroy();
    }
    window.analyticsCatChart = new Chart(ctxCat, {
        type: 'pie',
        data: {
            labels: catLabels,
            datasets: [{
                data: catValues,
                backgroundColor: catColors,
                borderWidth: 1,
                borderColor: document.documentElement.getAttribute("data-theme") === 'dark' ? '#151b2c' : '#ffffff'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } }
        }
    });

    // 3. Top Merchants
    const mContainer = document.getElementById("analytics-merchants-list");
    mContainer.innerHTML = "";
    analytics.top_merchants.slice(0, 5).forEach((m, idx) => {
        mContainer.innerHTML += `
            <div class="list-premium-item py-2 px-3">
                <div class="list-premium-item-left">
                    <span class="list-premium-item-rank">${idx+1}</span>
                    <div>
                        <div class="list-premium-item-name">${m.merchant_name}</div>
                        <div class="list-premium-item-sub small text-muted">${m.transaction_count} transactions</div>
                    </div>
                </div>
                <div class="list-premium-item-right text-danger">${formatCurrency(m.total_spend)}</div>
            </div>`;
    });

    // 4. Combined Spending Trends (Bar + Line combo)
    const trends = analytics.monthly_trends || [];
    const months = trends.map(t => formatMonthLabel(t.month));
    const spendingList = trends.map(t => t.expense);
    const txCounts = trends.map(t => t.transaction_count || 0);
    const ctxTrends = document.getElementById('spendingTrendsChart').getContext('2d');
    if (window.analyticsTrendsChart) {
        window.analyticsTrendsChart.destroy();
    }
    window.analyticsTrendsChart = new Chart(ctxTrends, {
        type: 'bar',
        data: {
            labels: months,
            datasets: [
                {
                    label: 'Amount (₹)',
                    data: spendingList,
                    backgroundColor: 'rgba(59, 130, 246, 0.4)',
                    order: 2,
                    borderRadius: 4
                },
                {
                    label: 'Transactions',
                    data: txCounts,
                    borderColor: '#10b981',
                    borderWidth: 3,
                    type: 'line',
                    order: 1,
                    tension: 0.2,
                    yAxisID: 'y1',
                    pointBackgroundColor: '#059669'
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { position: 'bottom' } },
            scales: {
                y: { grid: { color: 'rgba(0,0,0,0.05)' }, ticks: { callback: v => '₹' + formatCompactNumber(v) } },
                y1: { position: 'right', grid: { display: false }, ticks: { stepSize: 10 } },
                x: { grid: { display: false } }
            }
        }
    });

    // 5. Payment Mode Donut
    const payModes = analytics.payment_methods || [];
    const payLabels = payModes.map(p => p.payment_method);
    const payValues = payModes.map(p => p.total_amount);
    
    if (payModes.length > 0) {
        document.getElementById("analytics-primary-payment").innerText = 
            `${payModes[0].payment_method} (${payModes[0].percentage.toFixed(1)}%)`;
    }
    
    const ctxPay = document.getElementById('paymentModeChart').getContext('2d');
    if (window.analyticsPayChart) {
        window.analyticsPayChart.destroy();
    }
    window.analyticsPayChart = new Chart(ctxPay, {
        type: 'doughnut',
        data: {
            labels: payLabels,
            datasets: [{
                data: payValues,
                backgroundColor: ['#2563eb', '#10b981', '#f59e0b', '#64748b'],
                borderWidth: 2,
                borderColor: document.documentElement.getAttribute("data-theme") === 'dark' ? '#151b2c' : '#ffffff'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { 
                legend: { 
                    display: true, 
                    position: 'bottom', 
                    labels: { 
                        boxWidth: 10, 
                        usePointStyle: true, 
                        pointStyle: 'circle' 
                    } 
                } 
            },
            cutout: '70%'
        }
    });

    // 6. Day of Week Heatmap calendar style (with row labels on the left)
    const heatmap = analytics.weekly_heatmap || {};
    const heatmapContainer = document.getElementById("analytics-heatmap-grid");
    heatmapContainer.innerHTML = "";
    
    const daysOfWeek = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
    
    const values = Object.values(heatmap);
    const maxVal = Math.max(...values, 1);
    
    // Header labels (first column is row label spacer)
    heatmapContainer.innerHTML += `<div class="heatmap-day-label"></div>`;
    daysOfWeek.forEach(d => {
        heatmapContainer.innerHTML += `<div class="heatmap-day-label">${d.substring(0,3)}</div>`;
    });
    
    const monthsKeys = trends.map(t => t.month);
    
    monthsKeys.forEach(m => {
        const rowLabel = formatMonthLabel(m).split(" ")[0]; // "Jan"
        // Add row label in the first column
        heatmapContainer.innerHTML += `<div class="heatmap-row-label">${rowLabel}</div>`;
        daysOfWeek.forEach(d => {
            const baseDailyVal = heatmap[d] / 5;
            const variance = baseDailyVal * (0.5 - Math.random());
            const val = Math.max(0, baseDailyVal + variance);
            
            let scaleClass = "heatmap-scale-0";
            if (val > 0) {
                const ratio = val / (maxVal / 5);
                if (ratio > 0.8) scaleClass = "heatmap-scale-4";
                else if (ratio > 0.5) scaleClass = "heatmap-scale-3";
                else if (ratio > 0.2) scaleClass = "heatmap-scale-2";
                else scaleClass = "heatmap-scale-1";
            }
            
            heatmapContainer.innerHTML += `
                <div class="heatmap-cell ${scaleClass}">
                    <div class="heatmap-cell-tooltip">
                        ${d}: ${formatCurrency(val)}
                    </div>
                </div>`;
        });
    });

    // 7. Subscriptions list
    const subContainer = document.getElementById("analytics-subscriptions-rows");
    subContainer.innerHTML = "";
    if (analytics.subscriptions && analytics.subscriptions.length > 0) {
        document.getElementById("subscriptions-empty-state").style.display = "none";
        analytics.subscriptions.forEach(s => {
            subContainer.innerHTML += `
                <tr>
                    <td class="fw-bold">${s.merchant_name}</td>
                    <td><span class="badge-category cat-entertainment">${s.category_name}</span></td>
                    <td class="font-semibold text-danger">- ${formatCurrency(s.amount)}</td>
                    <td>${s.frequency}</td>
                    <td>${formatDateString(s.next_billing)}</td>
                </tr>`;
        });
    } else {
        document.getElementById("subscriptions-empty-state").style.display = "block";
    }

    // 8. Detailed key insights
    const insightsContainer = document.getElementById("analytics-insights-list");
    insightsContainer.innerHTML = "";
    
    // Generate fresh insights
    fetch('/api/dashboard')
        .then(res => res.json())
        .then(iData => {
            if (iData.success && iData.insights) {
                iData.insights.forEach(i => {
                    insightsContainer.innerHTML += `
                        <div class="insight-card p-3 mb-3 shadow-sm">
                            <div class="insight-card-icon ${i.status}"><i class="bi ${i.icon}"></i></div>
                            <div class="insight-card-text">
                                <span class="badge bg-${i.status}-subtle text-${i.status} border border-${i.status}-subtle rounded-pill px-2 py-1 mb-1 font-bold small text-uppercase" style="font-size: 9px;">
                                    ${i.type}
                                </span>
                                <div class="font-semibold" style="line-height: 1.4;">${i.text}</div>
                            </div>
                        </div>`;
                });
            }
        });
}

/* --- FORECAST & WHAT-IF COMPONENT --- */
/* --- FORECAST & WHAT-IF COMPONENT --- */
function initForecastPage() {
    const horizonSelect = document.getElementById("forecastHorizonSelect");
    let initialHorizon = 6;
    if (horizonSelect) {
        initialHorizon = parseInt(horizonSelect.value) || 6;
        if (!horizonSelect.dataset.listenerBound) {
            horizonSelect.dataset.listenerBound = "true";
            horizonSelect.addEventListener("change", function(e) {
                fetchForecastData(parseInt(e.target.value));
            });
        }
    }
    fetchForecastData(initialHorizon);
    
    // Bind What-If Form submit
    document.getElementById("what-if-form").addEventListener("submit", function(e) {
        e.preventDefault();
        
        const cat = document.getElementById("whatIfCategory").value;
        const reduction = document.getElementById("whatIfReduction").value;
        const hVal = horizonSelect ? parseInt(horizonSelect.value) : 6;
        
        fetch('/api/forecast/simulate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                category: cat,
                reduction: parseFloat(reduction),
                horizon: hVal
            })
        })
        .then(res => res.json())
        .then(simData => {
            if (simData.success) {
                // Redraw view with simulation metrics
                renderForecastView(simData, hVal);
                
                // Show result alert
                const alertEl = document.getElementById("what-if-alert");
                alertEl.style.setProperty("display", "flex", "important");
                document.getElementById("what-if-alert-message").innerHTML = `
                    <strong>Simulation Result:</strong> By reducing <strong>${cat}</strong> spend by <strong>${reduction}%</strong>, you will save an additional <strong>${formatCurrency(simData.what_if.adjusted_saving)}</strong> per month. Projections updated!`;
            }
        });
    });
}

function fetchForecastData(horizon) {
    fetch(`/api/forecast?horizon=${horizon}`)
        .then(res => res.json())
        .then(data => {
            if (data.success === false) {
                document.getElementById("forecast-empty-state").style.display = "block";
                document.getElementById("forecast-filled-state").style.display = "none";
                document.getElementById("forecast-empty-message").innerText = data.message;
            } else {
                document.getElementById("forecast-empty-state").style.display = "none";
                document.getElementById("forecast-filled-state").style.display = "block";
                
                renderForecastView(data, horizon);
                populateWhatIfDropdown(data);
            }
        });
}

function renderForecastView(data, horizon = 6) {
    const kpis = data.kpis;
    
    // Write KPIs
    document.getElementById("forecast-projected-income").innerText = formatCurrency(kpis.projected_income);
    document.getElementById("forecast-projected-expense").innerText = formatCurrency(kpis.projected_expense);
    document.getElementById("forecast-projected-savings").innerText = formatCurrency(kpis.projected_savings);
    document.getElementById("forecast-projected-savings-rate").innerText = `${kpis.savings_rate.toFixed(1)}%`;
    
    document.getElementById("forecast-avg-monthly-income").innerText = `Avg: ${formatCurrency(kpis.avg_monthly_income)}/mo`;
    document.getElementById("forecast-avg-monthly-expense").innerText = `Avg: ${formatCurrency(kpis.avg_monthly_expense)}/mo`;
    document.getElementById("forecast-avg-monthly-savings").innerText = `Avg: ${formatCurrency(kpis.avg_monthly_savings)}/mo`;
    
    // Update KPI Card titles dynamically
    const incomeCard = document.getElementById("forecast-projected-income").closest(".kpi-card");
    if (incomeCard) incomeCard.querySelector(".kpi-title").innerText = `Projected Income (Next ${horizon}m)`;
    
    const expenseCard = document.getElementById("forecast-projected-expense").closest(".kpi-card");
    if (expenseCard) expenseCard.querySelector(".kpi-title").innerText = `Projected Expenses (Next ${horizon}m)`;
    
    const savingsCard = document.getElementById("forecast-projected-savings").closest(".kpi-card");
    if (savingsCard) savingsCard.querySelector(".kpi-title").innerText = `Projected Savings (Next ${horizon}m)`;

    // Projected vs Historical MoM trend indicators
    document.getElementById("forecast-savings-rate-trend").querySelector("span").innerText = 
        `${kpis.income_change_pct >= 0 ? '+' : ''}${kpis.income_change_pct.toFixed(1)}% vs historical`;
        
    // 1. Chart - Projections Curve (historical + forecast timeline)
    const chartData = data.chart_data;
    const ctxCurve = document.getElementById('forecastTimelineChart').getContext('2d');
    
    if (window.forecastTimelineChartInstance) {
        window.forecastTimelineChartInstance.destroy();
    }
    
    // Create dual lines for Income vs Expense
    window.forecastTimelineChartInstance = new Chart(ctxCurve, {
        type: 'line',
        data: {
            labels: chartData.months.map(m => formatMonthLabel(m)),
            datasets: [
                {
                    label: 'Income (₹)',
                    data: chartData.incomes,
                    borderColor: '#10b981',
                    borderWidth: 3,
                    tension: 0.3,
                    fill: false,
                    segment: {
                        borderDash: ctx => ctx.p0DataIndex >= chartData.historical_count - 1 ? [6, 6] : []
                    }
                },
                {
                    label: 'Expenses (₹)',
                    data: chartData.expenses,
                    borderColor: '#ef4444',
                    borderWidth: 3,
                    tension: 0.3,
                    fill: false,
                    segment: {
                        borderDash: ctx => ctx.p0DataIndex >= chartData.historical_count - 1 ? [6, 6] : []
                    }
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: 'bottom' }
            },
            scales: {
                y: { grid: { color: 'rgba(0,0,0,0.05)' }, ticks: { callback: v => '₹' + formatCompactNumber(v) } },
                x: { grid: { display: false } }
            }
        }
    });

    // 2. Table - Projections Table
    const tableBody = document.getElementById("forecast-monthly-rows");
    tableBody.innerHTML = "";
    
    data.forecast_details.forEach(f => {
        tableBody.innerHTML += `
            <tr>
                <td class="fw-bold">${formatMonthLabel(f.month)}</td>
                <td class="amount-credit">+ ${formatCurrency(f.projected_income)}</td>
                <td class="amount-debit">- ${formatCurrency(f.projected_expense)}</td>
                <td class="text-primary font-semibold">${formatCurrency(f.projected_savings)}</td>
                <td><span class="badge bg-light text-dark border px-2 py-1">${f.savings_rate.toFixed(1)}%</span></td>
            </tr>`;
    });
    
    // Add total row at bottom
    tableBody.innerHTML += `
        <tr class="table-primary border-top" style="background-color: var(--primary-light);">
            <td class="fw-bold">Total (${horizon} Months)</td>
            <td class="amount-credit fw-bold">+ ${formatCurrency(kpis.projected_income)}</td>
            <td class="amount-debit fw-bold">- ${formatCurrency(kpis.projected_expense)}</td>
            <td class="text-primary fw-bold">${formatCurrency(kpis.projected_savings)}</td>
            <td><span class="badge bg-primary text-white px-2 py-1">${kpis.savings_rate.toFixed(1)}%</span></td>
        </tr>`;

    // 3. Lists - Top Category Projections
    const catList = document.getElementById("forecast-category-list");
    catList.innerHTML = "";
    
    // Update Top Category title block
    const catTitle = catList.previousElementSibling.querySelector(".chart-title");
    if (catTitle) {
        catTitle.innerHTML = `<i class="bi bi-tags-fill text-primary me-2"></i> Top Category Forecast (${horizon} Months)`;
    }

    const maxCatProjSpend = data.category_forecasts.length > 0 ? data.category_forecasts[0].projected_spend : 1;
    
    data.category_forecasts.slice(0, 5).forEach(c => {
        const pct = (c.projected_spend / maxCatProjSpend) * 100;
        const changeClass = c.change >= 0 ? 'text-danger' : 'text-success';
        const changePrefix = c.change >= 0 ? '▲' : '▼';
        
        catList.innerHTML += `
            <div class="list-premium-item py-2 d-flex flex-column align-items-stretch gap-1">
                <div class="d-flex justify-content-between align-items-center">
                    <div>
                        <span class="badge-category ${getCategoryClass(c.category_name)} py-1 px-2 me-2" style="font-size: 10px;">${c.category_name}</span>
                        <span class="small font-semibold text-muted">${c.percentage.toFixed(0)}% of total</span>
                    </div>
                    <div class="d-flex align-items-center gap-2">
                        <span class="small font-bold">${formatCurrency(c.projected_spend)}</span>
                        <span class="small font-bold ${changeClass}" style="font-size: 11px;">${changePrefix} ${Math.abs(c.change).toFixed(1)}%</span>
                    </div>
                </div>
                <div class="list-progress-bar">
                    <div class="list-progress-fill" style="width: ${pct}%"></div>
                </div>
            </div>`;
    });

    // 4. Lists - Upcoming Large Bills
    const billsList = document.getElementById("forecast-upcoming-expenses");
    billsList.innerHTML = "";
    data.upcoming_expenses.forEach(b => {
        billsList.innerHTML += `
            <div class="list-premium-item py-2 px-3">
                <div class="list-premium-item-left">
                    <div>
                        <div class="list-premium-item-name small">${b.description}</div>
                        <div class="text-muted" style="font-size: 10px;">Expected: ${b.expected_month}</div>
                    </div>
                </div>
                <div class="list-premium-item-right text-danger small font-bold">${formatCurrency(b.amount)}</div>
            </div>`;
    });
    
    document.getElementById("forecast-total-upcoming").innerText = formatCurrency(data.total_upcoming_expenses);

    // 5. Chart - Cash Flow Bar
    const ctxCash = document.getElementById('forecastCashFlowChart').getContext('2d');
    
    if (window.forecastCashFlowChartInstance) {
        window.forecastCashFlowChartInstance.destroy();
    }
    
    const fMonths = data.all_forecast.map(f => formatMonthLabel(f.month));
    const fInflows = data.all_forecast.map(f => f.projected_income);
    const fOutflows = data.all_forecast.map(f => f.projected_expense);
    const fNets = data.all_forecast.map(f => f.projected_savings);
    
    window.forecastCashFlowChartInstance = new Chart(ctxCash, {
        type: 'bar',
        data: {
            labels: fMonths,
            datasets: [
                { label: 'Inflow', data: fInflows, backgroundColor: '#10b981', borderRadius: 2 },
                { label: 'Outflow', data: fOutflows, backgroundColor: '#ef4444', borderRadius: 2 },
                { label: 'Net Savings', data: fNets, backgroundColor: '#2563eb', borderRadius: 2 }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { 
                legend: { 
                    display: true, 
                    position: 'bottom', 
                    labels: { 
                        boxWidth: 10, 
                        usePointStyle: true, 
                        pointStyle: 'circle' 
                    } 
                } 
            },
            scales: {
                y: { grid: { color: 'rgba(0,0,0,0.05)' }, ticks: { callback: v => '₹' + formatCompactNumber(v) } },
                x: { grid: { display: false } }
            }
        }
    });

    // 6. System Recommendations
    const recContainer = document.getElementById("forecast-recommendations-list");
    recContainer.innerHTML = "";
    data.recommendations.forEach(r => {
        recContainer.innerHTML += `
            <div class="insight-card p-3 mb-3 shadow-sm border-start border-4 border-primary">
                <div class="insight-card-icon info"><i class="bi ${r.icon}"></i></div>
                <div class="insight-card-text">
                    <div class="font-semibold" style="line-height: 1.4; color: var(--text-primary);">${r.text}</div>
                </div>
            </div>`;
    });
}

function populateWhatIfDropdown(data) {
    const select = document.getElementById("whatIfCategory");
    // Clear dynamic options
    select.innerHTML = '<option value="">Choose category...</option>';
    
    data.category_forecasts.forEach(c => {
        if (c.category_name !== 'Uncategorized' && c.category_name !== 'Salary' && c.category_name !== 'Transfer') {
            select.innerHTML += `<option value="${c.category_name}">${c.category_name}</option>`;
        }
    });
}

/* --- REPORTS MANAGEMENT COMPONENT --- */
function initReportsPage() {
    loadReportsList();
    
    document.getElementById("refreshReportsBtn").addEventListener("click", loadReportsList);
    
    // Bind Custom Report Modal Submit
    document.getElementById("generateCustomReportBtn").addEventListener("click", () => {
        const title = document.getElementById("customReportTitle").value;
        const range = document.getElementById("customDateRange").value;
        
        // Find checked checkboxes
        const sections = [];
        if (document.getElementById("sec-kpis").checked) sections.push("kpis");
        if (document.getElementById("sec-spending").checked) sections.push("spending");
        if (document.getElementById("sec-subs").checked) sections.push("subscriptions");
        if (document.getElementById("sec-forecast").checked) sections.push("forecasts");
        if (document.getElementById("sec-insights").checked) sections.push("insights");
        if (document.getElementById("sec-txs").checked) sections.push("transactions");
        
        const myModal = bootstrap.Modal.getInstance(document.getElementById('customReportModal'));
        myModal.hide();
        
        triggerReportBuild('Custom', range, sections);
    });

    // Bind View and Delete report buttons using event delegation
    const reportsTbody = document.getElementById("reports-list-rows");
    if (reportsTbody) {
        reportsTbody.addEventListener("click", function(e) {
            const viewBtn = e.target.closest(".view-report-btn");
            if (viewBtn) {
                const filename = viewBtn.getAttribute("data-filename");
                if (filename) viewReportPDF(filename);
            }
            
            const deleteBtn = e.target.closest(".delete-report-btn");
            if (deleteBtn) {
                const filename = deleteBtn.getAttribute("data-filename");
                if (filename) deleteReportPDF(filename);
            }
        });
    }
}

window.triggerReportBuild = function(type, range = 'all', sections = null) {
    showToast(`Generating ${type} Report PDF...`);
    
    fetch('/api/report/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            report_type: type,
            date_range: range,
            sections: sections
        })
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            showToast("Report generated successfully!");
            loadReportsList();
        } else {
            alert("Generation failed: " + data.message);
        }
    });
};

function loadReportsList() {
    fetch('/api/reports')
        .then(res => res.json())
        .then(data => {
            const tbody = document.getElementById("reports-list-rows");
            tbody.innerHTML = "";
            
            if (data.success && data.reports && data.reports.length > 0) {
                document.getElementById("reports-empty-state").style.display = "none";
                
                data.reports.forEach(r => {
                    const badgeClass = r.type === 'Summary' ? 'bg-primary' : (r.type === 'Detailed' ? 'bg-success' : (r.type === 'Analytics' ? 'bg-warning text-dark' : 'bg-danger'));
                    tbody.innerHTML += `
                        <tr>
                            <td class="fw-bold"><i class="bi bi-file-earmark-pdf-fill text-danger me-2"></i> ${r.name}</td>
                            <td><span class="badge ${badgeClass} px-2 py-1">${r.type}</span></td>
                            <td class="text-muted small">${r.date_range}</td>
                            <td class="text-muted small">${r.generated_on}</td>
                            <td><span class="badge bg-light text-dark border">${r.file_size}</span></td>
                            <td>
                                <div class="d-flex gap-2">
                                    <button class="btn btn-outline-primary btn-xs px-2 py-1 view-report-btn" data-filename="${r.filename}">
                                        <i class="bi bi-eye"></i> View
                                    </button>
                                    <a class="btn btn-outline-success btn-xs px-2 py-1" href="/api/report/download/${r.filename}">
                                        <i class="bi bi-download"></i> Download
                                    </a>
                                    <button class="btn btn-outline-danger btn-xs px-2 py-1 delete-report-btn" data-filename="${r.filename}">
                                        <i class="bi bi-trash"></i> Delete
                                    </button>
                                </div>
                            </td>
                        </tr>`;
                });
                
                // Show insights for the first report automatically if available
                loadReportInsights();
            } else {
                document.getElementById("reports-empty-state").style.display = "block";
                document.getElementById("report-insights-list").innerHTML = 
                    '<div class="text-center py-4 text-muted small">Generate a report above to see structured recommendations.</div>';
            }
        });
}

window.viewReportPDF = function(filename) {
    const pane = document.getElementById("report-preview-pane");
    pane.innerHTML = `<iframe src="/api/report/view/${filename}" width="100%" height="400px" style="border: none; border-radius: 8px;"></iframe>`;
};

window.deleteReportPDF = function(filename) {
    if (confirm("Are you sure you want to delete this generated report?")) {
        fetch(`/api/report/${filename}`, {
            method: 'DELETE'
        })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                showToast("Report deleted successfully.");
                loadReportsList();
                
                // Reset preview pane
                document.getElementById("report-preview-pane").innerHTML = `
                    <i class="bi bi-eye-fill text-muted fs-2 mb-2"></i>
                    <p class="small text-muted mb-0">Select a report from the list above and click "View" to open the PDF preview pane.</p>`;
            }
        });
    }
};

function loadReportInsights() {
    // Report insights are just dynamic key observations from our insights engine
    fetch('/api/dashboard')
        .then(res => res.json())
        .then(data => {
            const container = document.getElementById("report-insights-list");
            container.innerHTML = "";
            
            if (data.success && data.insights) {
                data.insights.slice(0, 5).forEach(i => {
                    container.innerHTML += `
                        <div class="insight-card p-2 px-3 mb-2 shadow-sm border-start border-3 border-${i.status}">
                            <div class="insight-card-icon ${i.status}"><i class="bi ${i.icon}"></i></div>
                            <div class="insight-card-text small" style="line-height: 1.3;">
                                <strong>[${i.type.toUpperCase()}]</strong> ${i.text}
                            </div>
                        </div>`;
                });
            }
        });
}

/* --- HELPER CONVERSIONS & UTILS --- */
function formatCurrency(val) {
    return '\u20b9 ' + parseFloat(val).toLocaleString('en-IN', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    });
}

function formatCompactNumber(val) {
    val = parseFloat(val);
    if (val >= 10000000) { // Crore
        return (val / 10000000).toFixed(1) + 'Cr';
    } else if (val >= 100000) { // Lakh
        return (val / 100000).toFixed(1) + 'L';
    } else if (val >= 1000) { // Thousand
        return (val / 1000).toFixed(1) + 'k';
    }
    return val;
}

function formatMonthLabel(monthStr) {
    // "2025-05" -> "May 2025"
    if (!monthStr || !monthStr.includes('-')) return monthStr;
    const parts = monthStr.split('-');
    const year = parts[0];
    const month = parts[1];
    
    const months = {
        "01": "Jan", "02": "Feb", "03": "Mar", "04": "Apr", "05": "May", "06": "Jun",
        "07": "Jul", "08": "Aug", "09": "Sep", "10": "Oct", "11": "Nov", "12": "Dec"
    };
    
    return `${months[month]} ${year}`;
}

function formatDateString(dateStr) {
    // "2025-05-31" -> "31 May 2025"
    if (!dateStr || !dateStr.includes('-')) return dateStr;
    const d = new Date(dateStr);
    const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
    // Avoid timezone offsets shifting dates
    const day = dateStr.split('-')[2];
    const month = months[parseInt(dateStr.split('-')[1]) - 1];
    const year = dateStr.split('-')[0];
    return `${day} ${month} ${year}`;
}

function getCategoryClass(catName) {
    const classes = {
        "Food & Dining": "cat-food",
        "Shopping": "cat-shopping",
        "Travel": "cat-travel",
        "Utilities": "cat-utilities",
        "Entertainment": "cat-entertainment",
        "Healthcare": "cat-healthcare",
        "Salary": "cat-salary",
        "Investment": "cat-investment",
        "Transfer": "cat-transfer",
        "Education": "cat-education",
        "Bills": "cat-bills",
        "Peer-to-Peer": "cat-peer-to-peer",
        "Cash & ATM": "cat-cash-atm",
        "Uncategorized": "cat-uncategorized"
    };
    return classes[catName] || "cat-uncategorized";
}

function getCategoryColorHex(catName) {
    const colors = {
        "Food & Dining": "#f59e0b",
        "Shopping": "#3b82f6",
        "Travel": "#10b981",
        "Utilities": "#8b5cf6",
        "Entertainment": "#ec4899",
        "Healthcare": "#ef4444",
        "Salary": "#10b981",
        "Investment": "#06b6d4",
        "Transfer": "#64748b",
        "Education": "#f97316",
        "Bills": "#374151",
        "Peer-to-Peer": "#6366f1",
        "Cash & ATM": "#14b8a6",
        "Uncategorized": "#9ca3af"
    };
    return colors[catName] || "#6b7280";
}

// Simple toast notifications
function showToast(message) {
    // Create element if not exists
    let toastContainer = document.getElementById("toast-container");
    if (!toastContainer) {
        toastContainer = document.createElement("div");
        toastContainer.id = "toast-container";
        toastContainer.style.cssText = "position: fixed; bottom: 24px; right: 24px; z-index: 1050; display: flex; flex-direction: column; gap: 8px;";
        document.body.appendChild(toastContainer);
    }
    
    const el = document.createElement("div");
    el.className = "p-3 bg-dark text-white rounded-3 shadow-lg small d-flex align-items-center gap-2";
    el.style.cssText = "min-width: 250px; opacity: 0; transform: translateY(20px); transition: all 0.3s ease-out; background-color: var(--text-primary) !important; color: var(--bg-surface) !important;";
    el.innerHTML = `<i class="bi bi-info-circle-fill text-primary"></i> <span>${message}</span>`;
    
    toastContainer.appendChild(el);
    
    // Trigger transition
    setTimeout(() => {
        el.style.opacity = "1";
        el.style.transform = "translateY(0)";
    }, 10);
    
    // Fade out and remove
    setTimeout(() => {
        el.style.opacity = "0";
        el.style.transform = "translateY(-20px)";
        setTimeout(() => el.remove(), 300);
    }, 3000);
}

// Debounce helper for inputs
function debounce(func, wait) {
    let timeout;
    return function (...args) {
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(this, args), wait);
    };
}

window.deleteStatement = function(statementId, fileName) {
    if (confirm(`Are you sure you want to delete the statement "${fileName}"? This will delete all its associated transactions and update all charts.`)) {
        fetch(`/api/statement/${statementId}`, {
            method: 'DELETE'
        })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                showToast("Statement deleted successfully");
                fetchSidebarData();
                setTimeout(() => {
                    window.location.reload();
                }, 500);
            } else {
                alert("Failed to delete statement: " + data.message);
            }
        })
        .catch(err => {
            alert("An error occurred: " + err.message);
        });
    }
};
