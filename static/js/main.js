document.addEventListener("DOMContentLoaded", function () {
    // --- GLOBAL SETUP ---
    initTheme();
    setupActiveNav();
    setupMobileSidebar();
    
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
    const toggleMobile = document.getElementById("darkModeToggleMobile");
    const currentTheme = localStorage.getItem("theme") || "light";
    
    document.documentElement.setAttribute("data-theme", currentTheme);
    document.body.setAttribute("data-theme", currentTheme);

    // Set both toggles to current state
    if (toggle) toggle.checked = currentTheme === "dark";
    if (toggleMobile) toggleMobile.checked = currentTheme === "dark";

    function applyTheme(theme) {
        document.documentElement.setAttribute("data-theme", theme);
        document.body.setAttribute("data-theme", theme);
        localStorage.setItem("theme", theme);
        // Sync both toggles
        if (toggle) toggle.checked = theme === "dark";
        if (toggleMobile) toggleMobile.checked = theme === "dark";
        // Refresh current page charts if present
        window.location.reload();
    }

    if (toggle) {
        toggle.addEventListener("change", function () {
            applyTheme(this.checked ? "dark" : "light");
        });
    }
    if (toggleMobile) {
        toggleMobile.addEventListener("change", function () {
            applyTheme(this.checked ? "dark" : "light");
        });
    }
}

/* --- MOBILE SIDEBAR TOGGLE --- */
function setupMobileSidebar() {
    const sidebar = document.getElementById("appSidebar");
    const backdrop = document.getElementById("sidebarBackdrop");
    const toggleBtn = document.getElementById("sidebarToggleBtn");
    const closeBtn = document.getElementById("sidebarCloseBtn");

    if (!sidebar || !toggleBtn) return; // Not on a sidebar page

    function openSidebar() {
        sidebar.classList.add("show");
        if (backdrop) backdrop.classList.add("show");
        document.body.style.overflow = "hidden"; // Prevent background scroll
    }

    function closeSidebar() {
        sidebar.classList.remove("show");
        if (backdrop) backdrop.classList.remove("show");
        document.body.style.overflow = "";
    }

    toggleBtn.addEventListener("click", openSidebar);
    if (closeBtn) closeBtn.addEventListener("click", closeSidebar);
    if (backdrop) backdrop.addEventListener("click", closeSidebar);

    // Close sidebar when a nav link is tapped on mobile
    sidebar.querySelectorAll(".nav-item").forEach(link => {
        link.addEventListener("click", () => {
            if (window.innerWidth <= 768) closeSidebar();
        });
    });
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
    Promise.all([
        fetch('/api/statements').then(res => res.json()).catch(() => ({ success: false, statements: [] })),
        fetch('/api/dashboard').then(res => res.json()).catch(() => ({ success: false }))
    ])
    .then(([stmtData, data]) => {
        const hasStatements = stmtData.success && stmtData.statements && stmtData.statements.length > 0;
        if (hasStatements) {
            document.getElementById("sidebar-dynamic-sections").style.display = "block";
            
            // 1. Populate loaded statements list from database
            const stmtContainer = document.getElementById("sidebar-statements-list");
            stmtContainer.innerHTML = "";
            
            stmtData.statements.forEach(s => {
                const item = document.createElement("div");
                item.className = "sidebar-list-item d-flex justify-content-between align-items-center mb-1";

                const content = document.createElement("div");
                content.className = "sidebar-list-item-content flex-grow-1 overflow-hidden d-flex align-items-center gap-2";

                const icon = document.createElement("i");
                icon.className = "bi bi-file-earmark-spreadsheet-fill text-success";
                icon.style.cssText = "font-size: 16px; flex-shrink: 0;";

                const textDiv = document.createElement("div");
                textDiv.style.minWidth = "0";

                const titleDiv = document.createElement("div");
                titleDiv.className = "sidebar-list-item-title text-truncate fw-bold";
                titleDiv.style.fontSize = "13px";
                titleDiv.textContent = s.file_name;
                titleDiv.title = s.file_name;

                const subDiv = document.createElement("div");
                subDiv.className = "sidebar-list-item-sub text-muted text-truncate";
                subDiv.style.fontSize = "10px";
                subDiv.textContent = `${s.bank_name || 'Unknown'} • ${formatMonthLabel(s.statement_month)}`;

                textDiv.appendChild(titleDiv);
                textDiv.appendChild(subDiv);
                content.appendChild(icon);
                content.appendChild(textDiv);

                const deleteBtn = document.createElement("button");
                deleteBtn.type = "button";
                deleteBtn.className = "btn btn-link text-danger p-0 ms-2 delete-statement-btn";
                deleteBtn.setAttribute("data-id", s.statement_id);
                deleteBtn.setAttribute("data-filename", s.file_name);
                deleteBtn.style.cssText = "text-decoration: none; font-size: 14px; flex-shrink: 0;";
                deleteBtn.title = "Delete this statement";

                const trashIcon = document.createElement("i");
                trashIcon.className = "bi bi-trash-fill";
                deleteBtn.appendChild(trashIcon);

                item.appendChild(content);
                item.appendChild(deleteBtn);
                stmtContainer.appendChild(item);
            });

            // 2. Populate data coverage list from analytics trends
            const coverageContainer = document.getElementById("sidebar-coverage-list");
            coverageContainer.innerHTML = "";
            
            const coverageHeader = document.querySelector("#sidebar-dynamic-sections .sidebar-section-title:nth-of-type(2)");
            const coverageDivider = document.querySelector("#sidebar-dynamic-sections hr:nth-of-type(2)");

            if (data.success && data.analytics && data.analytics.raw_count > 0) {
                if (coverageHeader) coverageHeader.style.display = "block";
                if (coverageDivider) coverageDivider.style.display = "block";
                coverageContainer.style.display = "block";

                const coverage = data.analytics.data_coverage || [];
                coverage.forEach(item => {
                    const itemDiv = document.createElement("div");
                    itemDiv.className = "sidebar-coverage-item";

                    const nameSpan = document.createElement("span");
                    nameSpan.textContent = item.name;

                    const dotSpan = document.createElement("span");
                    if (item.status === 'placeholder') {
                        nameSpan.className = "text-muted";
                        dotSpan.className = "missing-dash";
                        dotSpan.textContent = "-";
                    } else if (item.status === 'active') {
                        dotSpan.className = "active-dot";
                        const checkIcon = document.createElement("i");
                        checkIcon.className = "bi bi-check-circle-fill";
                        dotSpan.appendChild(checkIcon);
                    } else {
                        nameSpan.className = "text-muted";
                        dotSpan.className = "missing-dash";
                        dotSpan.textContent = "-";
                    }
                    itemDiv.appendChild(nameSpan);
                    itemDiv.appendChild(dotSpan);
                    coverageContainer.appendChild(itemDiv);
                });
            } else {
                if (coverageHeader) coverageHeader.style.display = "none";
                if (coverageDivider) coverageDivider.style.display = "none";
                coverageContainer.style.display = "none";
            }
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

        const item = document.createElement("div");
        item.className = "list-premium-item py-2 d-flex flex-column align-items-stretch gap-1";

        const flexDiv = document.createElement("div");
        flexDiv.className = "d-flex justify-content-between align-items-center";

        const nameSpan = document.createElement("span");
        nameSpan.className = "fw-semibold small text-truncate";
        nameSpan.style.maxWidth = "140px";
        nameSpan.textContent = c.category_name;

        const amountSpan = document.createElement("span");
        amountSpan.className = "small font-bold";
        amountSpan.textContent = formatCurrency(c.amount);

        flexDiv.appendChild(nameSpan);
        flexDiv.appendChild(amountSpan);

        const progBar = document.createElement("div");
        progBar.className = "list-progress-bar";

        const progFill = document.createElement("div");
        progFill.className = "list-progress-fill";
        progFill.style.width = `${pct}%`;
        progFill.style.backgroundColor = color;

        progBar.appendChild(progFill);
        item.appendChild(flexDiv);
        item.appendChild(progBar);
        topCatContainer.appendChild(item);
    });

    // 4. Lists - Top Merchants
    const topMerchantContainer = document.getElementById("dashboard-top-merchants");
    topMerchantContainer.innerHTML = "";
    
    // Find max value for progress fills
    const maxMerchantSpend = analytics.top_merchants.length > 0 ? analytics.top_merchants[0].total_spend : 1;
    
    analytics.top_merchants.slice(0, 5).forEach(m => {
        const pct = (m.total_spend / maxMerchantSpend) * 100;

        const item = document.createElement("div");
        item.className = "list-premium-item py-2 d-flex flex-column align-items-stretch gap-1";

        const flexDiv = document.createElement("div");
        flexDiv.className = "d-flex justify-content-between align-items-center";

        const nameSpan = document.createElement("span");
        nameSpan.className = "fw-semibold small text-truncate";
        nameSpan.style.maxWidth = "140px";
        nameSpan.textContent = m.merchant_name;

        const amountSpan = document.createElement("span");
        amountSpan.className = "small font-bold";
        amountSpan.textContent = formatCurrency(m.total_spend);

        flexDiv.appendChild(nameSpan);
        flexDiv.appendChild(amountSpan);

        const progBar = document.createElement("div");
        progBar.className = "list-progress-bar";

        const progFill = document.createElement("div");
        progFill.className = "list-progress-fill";
        progFill.style.width = `${pct}%`;

        progBar.appendChild(progFill);
        item.appendChild(flexDiv);
        item.appendChild(progBar);
        topMerchantContainer.appendChild(item);
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

                    const tr = document.createElement("tr");
                    tr.style.fontSize = "11px";

                    const dateTd = document.createElement("td");
                    dateTd.className = "text-nowrap";
                    dateTd.style.fontSize = "10px";
                    dateTd.style.color = "var(--text-muted)";
                    dateTd.textContent = formatDateString(t.transaction_date);

                    const descTd = document.createElement("td");
                    descTd.className = "fw-semibold text-truncate";
                    descTd.style.maxWidth = "110px";
                    descTd.title = t.description;
                    descTd.textContent = t.description.replace(/\n/g, ' ');

                    const catTd = document.createElement("td");
                    const catBadge = document.createElement("span");
                    catBadge.className = `badge-category ${catClass}`;
                    catBadge.style.cssText = "padding: 2px 8px; font-size: 9px;";
                    catBadge.textContent = t.category_name;
                    catTd.appendChild(catBadge);

                    const typeTd = document.createElement("td");
                    const typeSpan = document.createElement("span");
                    typeSpan.className = `fw-semibold text-capitalize ${t.transaction_type === 'Credit' ? 'text-success' : 'text-danger'}`;
                    typeSpan.textContent = t.transaction_type;
                    typeTd.appendChild(typeSpan);

                    const amountTd = document.createElement("td");
                    amountTd.className = `${amtClass} text-nowrap text-end`;
                    amountTd.textContent = `${prefix} ${formatCurrency(t.amount)}`;

                    tr.appendChild(dateTd);
                    tr.appendChild(descTd);
                    tr.appendChild(catTd);
                    tr.appendChild(typeTd);
                    tr.appendChild(amountTd);
                    recentTxContainer.appendChild(tr);
                });
            }
        });

    // 6. Insights Drawer Preview
    const insightsContainer = document.getElementById("dashboard-insights-preview");
    insightsContainer.innerHTML = "";
    insights.slice(0, 3).forEach(i => {
        const card = document.createElement("div");
        card.className = "insight-card p-2 px-3 mb-2";

        const iconDiv = document.createElement("div");
        iconDiv.className = `insight-card-icon ${i.status}`;
        const icon = document.createElement("i");
        icon.className = `bi ${i.icon}`;
        iconDiv.appendChild(icon);

        const textDiv = document.createElement("div");
        textDiv.className = "insight-card-text small";
        textDiv.style.lineHeight = "1.3";
        textDiv.textContent = i.text;

        card.appendChild(iconDiv);
        card.appendChild(textDiv);
        insightsContainer.appendChild(card);
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
        
        const tr = document.createElement("tr");

        const monthTd = document.createElement("td");
        monthTd.className = "fw-bold";
        monthTd.textContent = formatMonthLabel(t.month);

        const incomeTd = document.createElement("td");
        incomeTd.className = "amount-credit";
        incomeTd.textContent = `+ ${formatCurrency(t.income)}`;

        const expenseTd = document.createElement("td");
        expenseTd.className = "amount-debit";
        expenseTd.textContent = `- ${formatCurrency(t.expense)}`;

        const savingsTd = document.createElement("td");
        savingsTd.className = `${t.savings >= 0 ? 'text-success' : 'text-danger'} font-semibold`;
        savingsTd.textContent = formatCurrency(t.savings);

        const rateTd = document.createElement("td");
        const rateSpan = document.createElement("span");
        rateSpan.className = "badge bg-light text-dark border px-2 py-1";
        rateSpan.textContent = `${t.savings_rate.toFixed(1)}%`;
        rateTd.appendChild(rateSpan);

        const sparkTd = document.createElement("td");
        sparkTd.innerHTML = `
            <svg width="80" height="24" viewBox="0 0 80 24" class="overflow-visible">
                ${sparklineBars}
            </svg>`;

        tr.appendChild(monthTd);
        tr.appendChild(incomeTd);
        tr.appendChild(expenseTd);
        tr.appendChild(savingsTd);
        tr.appendChild(rateTd);
        tr.appendChild(sparkTd);
        monthlyTableBody.appendChild(tr);
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
                    const opt1 = document.createElement("option");
                    opt1.value = c.category_id;
                    opt1.textContent = c.category_name;
                    catSelect.appendChild(opt1);

                    const opt2 = document.createElement("option");
                    opt2.value = c.category_id;
                    opt2.textContent = c.category_name;
                    modalSelect.appendChild(opt2);
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

                    const tr = document.createElement("tr");

                    const dateTd = document.createElement("td");
                    dateTd.textContent = formatDateString(t.transaction_date);

                    const descTd = document.createElement("td");
                    descTd.className = "text-truncate fw-semibold";
                    descTd.style.maxWidth = "260px";
                    descTd.title = t.description;
                    descTd.textContent = t.description.replace(/\n/g, ' ');

                    const catTd = document.createElement("td");
                    const catBadge = document.createElement("span");
                    catBadge.className = `badge-category ${getCategoryClass(t.category_name)}`;
                    catBadge.textContent = t.category_name;
                    catTd.appendChild(catBadge);

                    const typeTd = document.createElement("td");
                    typeTd.textContent = t.transaction_type;

                    const amountTd = document.createElement("td");
                    amountTd.className = `${amtClass} font-bold`;
                    amountTd.textContent = `${prefix} ${formatCurrency(t.amount)}`;

                    const actionTd = document.createElement("td");
                    const actionBtn = document.createElement("button");
                    actionBtn.type = "button";
                    actionBtn.className = "btn btn-outline-primary btn-xs px-2 py-1 classify-btn";
                    actionBtn.setAttribute("data-id", t.transaction_id);
                    actionBtn.setAttribute("data-category-id", t.category_id);
                    
                    const tagIcon = document.createElement("i");
                    tagIcon.className = "bi bi-tag-fill me-1";
                    
                    actionBtn.appendChild(tagIcon);
                    actionBtn.appendChild(document.createTextNode(" Classify"));
                    actionTd.appendChild(actionBtn);

                    tr.appendChild(dateTd);
                    tr.appendChild(descTd);
                    tr.appendChild(catTd);
                    tr.appendChild(typeTd);
                    tr.appendChild(amountTd);
                    tr.appendChild(actionTd);
                    tbody.appendChild(tr);
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

function formatMonthWithAmount(monthStr, amount) {
    if (!monthStr || monthStr === "No data available") return "No data available";
    const parts = monthStr.split('-');
    const year = parts[0];
    const month = parts[1];
    const months = {
        "01": "January", "02": "February", "03": "March", "04": "April", "05": "May", "06": "June",
        "07": "July", "08": "August", "09": "September", "10": "October", "11": "November", "12": "December"
    };
    const monthName = months[month] || monthStr;
    const formattedAmount = Math.round(amount).toLocaleString('en-IN');
    return `${monthName} ${year} (₹${formattedAmount})`;
}

function updateSpendingOverviewChart(analytics) {
    const trends = analytics.monthly_trends || [];
    
    // Calculate highest and lowest spending month dynamically
    let highestMonthStr = "No data available";
    let lowestMonthStr = "No data available";
    
    const totalTransactions = trends.reduce((acc, t) => acc + (t.transaction_count || 0), 0);
    const hasTransactions = totalTransactions > 0;
    
    if (trends.length > 0 && hasTransactions) {
        let highest = trends[0];
        let lowest = trends[0];
        
        for (let i = 1; i < trends.length; i++) {
            if (trends[i].expense > highest.expense) {
                highest = trends[i];
            }
            if (trends[i].expense < lowest.expense) {
                lowest = trends[i];
            }
        }
        
        highestMonthStr = formatMonthWithAmount(highest.month, highest.expense);
        lowestMonthStr = formatMonthWithAmount(lowest.month, lowest.expense);
    }
    
    const highestEl = document.getElementById("overview-highest-month");
    const lowestEl = document.getElementById("overview-lowest-month");
    if (highestEl) highestEl.innerText = highestMonthStr;
    if (lowestEl) lowestEl.innerText = lowestMonthStr;

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
        const item = document.createElement("div");
        item.className = "list-premium-item py-2 px-3";

        const leftDiv = document.createElement("div");
        leftDiv.className = "list-premium-item-left";

        const rankSpan = document.createElement("span");
        rankSpan.className = "list-premium-item-rank";
        rankSpan.textContent = idx + 1;

        const infoDiv = document.createElement("div");
        
        const nameDiv = document.createElement("div");
        nameDiv.className = "list-premium-item-name";
        nameDiv.textContent = m.merchant_name;

        const subDiv = document.createElement("div");
        subDiv.className = "list-premium-item-sub small text-muted";
        subDiv.textContent = `${m.transaction_count} transactions`;

        infoDiv.appendChild(nameDiv);
        infoDiv.appendChild(subDiv);
        leftDiv.appendChild(rankSpan);
        leftDiv.appendChild(infoDiv);

        const rightDiv = document.createElement("div");
        rightDiv.className = "list-premium-item-right text-danger";
        rightDiv.textContent = formatCurrency(m.total_spend);

        item.appendChild(leftDiv);
        item.appendChild(rightDiv);
        mContainer.appendChild(item);
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
            const tr = document.createElement("tr");

            const nameTd = document.createElement("td");
            nameTd.className = "fw-bold";
            nameTd.textContent = s.merchant_name;

            const catTd = document.createElement("td");
            const catBadge = document.createElement("span");
            catBadge.className = `badge-category ${getCategoryClass(s.category_name)}`;
            catBadge.textContent = s.category_name;
            catTd.appendChild(catBadge);

            const amountTd = document.createElement("td");
            amountTd.className = "font-semibold text-danger";
            amountTd.textContent = `- ${formatCurrency(s.amount)}`;

            const freqTd = document.createElement("td");
            freqTd.textContent = s.frequency;

            const dateTd = document.createElement("td");
            dateTd.textContent = formatDateString(s.next_billing);

            tr.appendChild(nameTd);
            tr.appendChild(catTd);
            tr.appendChild(amountTd);
            tr.appendChild(freqTd);
            tr.appendChild(dateTd);
            subContainer.appendChild(tr);
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
                    const card = document.createElement("div");
                    card.className = "insight-card p-3 mb-3 shadow-sm";

                    const iconDiv = document.createElement("div");
                    iconDiv.className = `insight-card-icon ${i.status}`;
                    const icon = document.createElement("i");
                    icon.className = `bi ${i.icon}`;
                    iconDiv.appendChild(icon);

                    const textDiv = document.createElement("div");
                    textDiv.className = "insight-card-text";

                    const badge = document.createElement("span");
                    badge.className = `badge bg-${i.status}-subtle text-${i.status} border border-${i.status}-subtle rounded-pill px-2 py-1 mb-1 font-bold small text-uppercase`;
                    badge.style.fontSize = "9px";
                    badge.textContent = i.type;

                    const descDiv = document.createElement("div");
                    descDiv.className = "font-semibold";
                    descDiv.style.lineHeight = "1.4";
                    descDiv.textContent = i.text;

                    textDiv.appendChild(badge);
                    textDiv.appendChild(descDiv);
                    card.appendChild(iconDiv);
                    card.appendChild(textDiv);
                    insightsContainer.appendChild(card);
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
                
                const alertMsg = document.getElementById("what-if-alert-message");
                alertMsg.innerHTML = ""; // Clear
                
                const titleStrong = document.createElement("strong");
                titleStrong.textContent = "Simulation Result: ";
                
                const text1 = document.createTextNode("By reducing ");
                const catStrong = document.createElement("strong");
                catStrong.textContent = cat;
                
                const text2 = document.createTextNode(" spend by ");
                const redStrong = document.createElement("strong");
                redStrong.textContent = `${reduction}%`;
                
                const text3 = document.createTextNode(", you will save an additional ");
                const saveStrong = document.createElement("strong");
                saveStrong.textContent = formatCurrency(simData.what_if.adjusted_saving);
                
                const text4 = document.createTextNode(" per month. Projections updated!");
                
                alertMsg.appendChild(titleStrong);
                alertMsg.appendChild(text1);
                alertMsg.appendChild(catStrong);
                alertMsg.appendChild(text2);
                alertMsg.appendChild(redStrong);
                alertMsg.appendChild(text3);
                alertMsg.appendChild(saveStrong);
                alertMsg.appendChild(text4);
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
                        borderDash: ctx => {
                            const p0 = ctx.p0DataIndex;
                            const p1 = ctx.p1DataIndex;
                            if (chartData.status) {
                                const s0 = chartData.status[p0];
                                const s1 = chartData.status[p1];
                                if (s0 === 'actual' && s1 === 'actual') {
                                    return [];
                                }
                            }
                            return [6, 6];
                        }
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
                        borderDash: ctx => {
                            const p0 = ctx.p0DataIndex;
                            const p1 = ctx.p1DataIndex;
                            if (chartData.status) {
                                const s0 = chartData.status[p0];
                                const s1 = chartData.status[p1];
                                if (s0 === 'actual' && s1 === 'actual') {
                                    return [];
                                }
                            }
                            return [6, 6];
                        }
                    }
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: 'bottom' },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const index = context.dataIndex;
                            const status = chartData.status ? chartData.status[index] : 'actual';
                            let label = context.dataset.label || '';
                            if (label) {
                                label += ': ';
                            }
                            if (context.parsed.y !== null) {
                                label += formatCurrency(context.parsed.y);
                            }
                            if (status === 'interpolated') {
                                label += ' (Missing month data - possible inaccurate forecast)';
                            } else if (status === 'projected') {
                                label += ' (Projected)';
                            }
                            return label;
                        }
                    }
                }
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
        
        const item = document.createElement("div");
        item.className = "list-premium-item py-2 d-flex flex-column align-items-stretch gap-1";

        const topDiv = document.createElement("div");
        topDiv.className = "d-flex justify-content-between align-items-center";

        const leftDiv = document.createElement("div");
        
        const catBadge = document.createElement("span");
        catBadge.className = `badge-category ${getCategoryClass(c.category_name)} py-1 px-2 me-2`;
        catBadge.style.fontSize = "10px";
        catBadge.textContent = c.category_name;

        const pctSpan = document.createElement("span");
        pctSpan.className = "small font-semibold text-muted";
        pctSpan.textContent = `${c.percentage.toFixed(0)}% of total`;

        leftDiv.appendChild(catBadge);
        leftDiv.appendChild(pctSpan);

        const rightDiv = document.createElement("div");
        rightDiv.className = "d-flex align-items-center gap-2";

        const spendSpan = document.createElement("span");
        spendSpan.className = "small font-bold";
        spendSpan.textContent = formatCurrency(c.projected_spend);

        const changeSpan = document.createElement("span");
        changeSpan.className = `small font-bold ${changeClass}`;
        changeSpan.style.fontSize = "11px";
        changeSpan.textContent = `${changePrefix} ${Math.abs(c.change).toFixed(1)}%`;

        rightDiv.appendChild(spendSpan);
        rightDiv.appendChild(changeSpan);

        topDiv.appendChild(leftDiv);
        topDiv.appendChild(rightDiv);

        const progBar = document.createElement("div");
        progBar.className = "list-progress-bar";

        const progFill = document.createElement("div");
        progFill.className = "list-progress-fill";
        progFill.style.width = `${pct}%`;

        progBar.appendChild(progFill);
        item.appendChild(topDiv);
        item.appendChild(progBar);
        catList.appendChild(item);
    });

    // 4. Lists - Upcoming Large Bills
    const billsList = document.getElementById("forecast-upcoming-expenses");
    billsList.innerHTML = "";
    data.upcoming_expenses.forEach(b => {
        const item = document.createElement("div");
        item.className = "list-premium-item py-2 px-3";

        const leftDiv = document.createElement("div");
        leftDiv.className = "list-premium-item-left";

        const wrapperDiv = document.createElement("div");
        
        const nameDiv = document.createElement("div");
        nameDiv.className = "list-premium-item-name small";
        nameDiv.textContent = b.description;

        const monthDiv = document.createElement("div");
        monthDiv.className = "text-muted";
        monthDiv.style.fontSize = "10px";
        monthDiv.textContent = `Expected: ${b.expected_month}`;

        wrapperDiv.appendChild(nameDiv);
        wrapperDiv.appendChild(monthDiv);
        leftDiv.appendChild(wrapperDiv);

        const rightDiv = document.createElement("div");
        rightDiv.className = "list-premium-item-right text-danger small font-bold";
        rightDiv.textContent = formatCurrency(b.amount);

        item.appendChild(leftDiv);
        item.appendChild(rightDiv);
        billsList.appendChild(item);
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
        const card = document.createElement("div");
        card.className = "insight-card p-3 mb-3 shadow-sm border-start border-4 border-primary";

        const iconDiv = document.createElement("div");
        iconDiv.className = "insight-card-icon info";
        const icon = document.createElement("i");
        icon.className = `bi ${r.icon}`;
        iconDiv.appendChild(icon);

        const textDiv = document.createElement("div");
        textDiv.className = "insight-card-text";
        
        const descDiv = document.createElement("div");
        descDiv.className = "font-semibold";
        descDiv.style.cssText = "line-height: 1.4; color: var(--text-primary);";
        descDiv.textContent = r.text;

        textDiv.appendChild(descDiv);
        card.appendChild(iconDiv);
        card.appendChild(textDiv);
        recContainer.appendChild(card);
    });
}

function populateWhatIfDropdown(data) {
    const select = document.getElementById("whatIfCategory");
    // Clear dynamic options
    select.innerHTML = '<option value="">Choose category...</option>';
    
    data.category_forecasts.forEach(c => {
        if (c.category_name !== 'Uncategorized' && c.category_name !== 'Salary' && c.category_name !== 'Transfer') {
            const opt = document.createElement("option");
            opt.value = c.category_name;
            opt.textContent = c.category_name;
            select.appendChild(opt);
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
                    const tr = document.createElement("tr");

                    const nameTd = document.createElement("td");
                    nameTd.className = "fw-bold";
                    
                    const pdfIcon = document.createElement("i");
                    pdfIcon.className = "bi bi-file-earmark-pdf-fill text-danger me-2";
                    nameTd.appendChild(pdfIcon);
                    nameTd.appendChild(document.createTextNode(` ${r.name}`));

                    const typeTd = document.createElement("td");
                    const typeBadge = document.createElement("span");
                    typeBadge.className = `badge ${badgeClass} px-2 py-1`;
                    typeBadge.textContent = r.type;
                    typeTd.appendChild(typeBadge);

                    const rangeTd = document.createElement("td");
                    rangeTd.className = "text-muted small";
                    rangeTd.textContent = r.date_range;

                    const dateTd = document.createElement("td");
                    dateTd.className = "text-muted small";
                    dateTd.textContent = r.generated_on;

                    const sizeTd = document.createElement("td");
                    const sizeBadge = document.createElement("span");
                    sizeBadge.className = "badge bg-light text-dark border";
                    sizeBadge.textContent = r.file_size;
                    sizeTd.appendChild(sizeBadge);

                    const actionsTd = document.createElement("td");
                    const actionsDiv = document.createElement("div");
                    actionsDiv.className = "d-flex gap-2";

                    const viewBtn = document.createElement("button");
                    viewBtn.className = "btn btn-outline-primary btn-xs px-2 py-1 view-report-btn";
                    viewBtn.setAttribute("data-filename", r.filename);
                    const viewIcon = document.createElement("i");
                    viewIcon.className = "bi bi-eye";
                    viewBtn.appendChild(viewIcon);
                    viewBtn.appendChild(document.createTextNode(" View"));

                    const downloadLink = document.createElement("a");
                    downloadLink.className = "btn btn-outline-success btn-xs px-2 py-1";
                    downloadLink.href = `/api/report/download/${encodeURIComponent(r.filename)}`;
                    const downloadIcon = document.createElement("i");
                    downloadIcon.className = "bi bi-download";
                    downloadLink.appendChild(downloadIcon);
                    downloadLink.appendChild(document.createTextNode(" Download"));

                    const deleteBtn = document.createElement("button");
                    deleteBtn.className = "btn btn-outline-danger btn-xs px-2 py-1 delete-report-btn";
                    deleteBtn.setAttribute("data-filename", r.filename);
                    const deleteIcon = document.createElement("i");
                    deleteIcon.className = "bi bi-trash";
                    deleteBtn.appendChild(deleteIcon);
                    deleteBtn.appendChild(document.createTextNode(" Delete"));

                    actionsDiv.appendChild(viewBtn);
                    actionsDiv.appendChild(downloadLink);
                    actionsDiv.appendChild(deleteBtn);
                    actionsTd.appendChild(actionsDiv);

                    tr.appendChild(nameTd);
                    tr.appendChild(typeTd);
                    tr.appendChild(rangeTd);
                    tr.appendChild(dateTd);
                    tr.appendChild(sizeTd);
                    tr.appendChild(actionsTd);
                    tbody.appendChild(tr);
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
    pane.innerHTML = "";
    const iframe = document.createElement("iframe");
    iframe.src = `/api/report/view/${encodeURIComponent(filename)}`;
    iframe.width = "100%";
    iframe.height = "400px";
    iframe.style.border = "none";
    iframe.style.borderRadius = "8px";
    pane.appendChild(iframe);
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
                    const card = document.createElement("div");
                    card.className = `insight-card p-2 px-3 mb-2 shadow-sm border-start border-3 border-${i.status}`;

                    const iconDiv = document.createElement("div");
                    iconDiv.className = `insight-card-icon ${i.status}`;
                    const icon = document.createElement("i");
                    icon.className = `bi ${i.icon}`;
                    iconDiv.appendChild(icon);

                    const textDiv = document.createElement("div");
                    textDiv.className = "insight-card-text small";
                    textDiv.style.lineHeight = "1.3";

                    const statusStrong = document.createElement("strong");
                    statusStrong.textContent = `[${i.type.toUpperCase()}] `;

                    const descText = document.createTextNode(i.text);

                    textDiv.appendChild(statusStrong);
                    textDiv.appendChild(descText);
                    card.appendChild(iconDiv);
                    card.appendChild(textDiv);
                    container.appendChild(card);
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
    
    const icon = document.createElement("i");
    icon.className = "bi bi-info-circle-fill text-primary";

    const textSpan = document.createElement("span");
    textSpan.textContent = message;

    el.appendChild(icon);
    el.appendChild(textSpan);
    
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

let deleteModalEl = null;
let deleteModal = null;
let activeDeleteStatementId = null;

window.deleteStatement = function(statementId, fileName) {
    activeDeleteStatementId = statementId;
    
    // Set the file name in the modal body
    const fileNameSpan = document.getElementById("deleteConfirmFileName");
    if (fileNameSpan) {
        fileNameSpan.textContent = fileName;
    }
    
    // Initialize modal if not done already
    if (!deleteModalEl) {
        deleteModalEl = document.getElementById('deleteConfirmModal');
        if (deleteModalEl) {
            deleteModal = new bootstrap.Modal(deleteModalEl);
        }
    }
    
    if (deleteModal) {
        deleteModal.show();
    }
};

// Bind the modal delete button click listener once
document.addEventListener("DOMContentLoaded", function () {
    const submitBtn = document.getElementById("submitDeleteConfirmBtn");
    if (submitBtn) {
        submitBtn.addEventListener("click", function () {
            if (!activeDeleteStatementId) return;
            
            // Disable button to prevent double-clicks
            submitBtn.disabled = true;
            const originalText = submitBtn.innerHTML;
            submitBtn.innerHTML = `<span class="spinner-border spinner-border-sm me-1" role="status" aria-hidden="true"></span> Deleting...`;
            
            fetch(`/api/statement/${activeDeleteStatementId}`, {
                method: 'DELETE'
            })
            .then(res => res.json())
            .then(data => {
                if (deleteModal) {
                    deleteModal.hide();
                }
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
                if (deleteModal) {
                    deleteModal.hide();
                }
                alert("An error occurred: " + err.message);
            })
            .finally(() => {
                submitBtn.disabled = false;
                submitBtn.innerHTML = originalText;
                activeDeleteStatementId = null;
            });
        });
    }
});

// Delegated click listener to prevent event propagation conflicts and native form/link triggers
document.addEventListener("click", function(e) {
    const deleteBtn = e.target.closest(".delete-statement-btn");
    if (deleteBtn) {
        e.preventDefault();
        e.stopPropagation();
        const statementId = deleteBtn.getAttribute("data-id");
        const fileName = deleteBtn.getAttribute("data-filename");
        if (statementId && fileName) {
            window.deleteStatement(statementId, fileName);
        }
    }
});
