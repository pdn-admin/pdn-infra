    // XSS sanitization helper
    function escapeHtml(str) {
        if (!str) return '';
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    // Debounce utility
    function debounce(fn, delay) {
        let timer;
        return function(...args) {
            clearTimeout(timer);
            timer = setTimeout(() => fn.apply(this, args), delay);
        };
    }

    // Shared helpers
    function redirectToLogin() {
        localStorage.removeItem('adminSessionToken');
        localStorage.removeItem('adminEmail');
        window.location.href = '/pdn-admin/';
    }

    // ===== URL State Management =====
    function updateUrlState(params) {
        const url = new URL(window.location);
        Object.entries(params).forEach(([key, value]) => {
            if (value !== null && value !== undefined && value !== '') {
                url.searchParams.set(key, value);
            } else {
                url.searchParams.delete(key);
            }
        });
        history.pushState(null, '', url);
    }

    function getUrlState() {
        const params = new URLSearchParams(window.location.search);
        return {
            filter: params.get('filter'),
            range: params.get('range'),
            search: params.get('search'),
            sort: params.get('sort'),
            order: params.get('order'),
            code: params.get('code')
        };
    }

    function restoreUrlState() {
        const state = getUrlState();
        if (state.range && ['week', 'month', 'year', 'all'].includes(state.range)) {
            setMetricsRange(state.range);
        }
        if (state.filter) {
            filterByMetric(state.filter);
        } else if (state.code) {
            filterByCode(state.code);
        } else if (state.search) {
            // Don't restore search from URL — start fresh each time
        }
        if (state.sort) {
            sortColumn = state.sort;
            sortDirection = state.order || 'asc';
        }
    }

    // ===== Loading Skeleton =====
    function showTableSkeleton(rows = 8) {
        const tbody = document.getElementById('tableBody');
        const cols = 13;
        let html = '';
        for (let i = 0; i < rows; i++) {
            html += '<tr class="skeleton-row">';
            for (let j = 0; j < cols; j++) {
                const width = 40 + Math.random() * 50;
                html += `<td class="px-4 py-4"><div class="skeleton-cell" style="width:${width}%"></div></td>`;
            }
            html += '</tr>';
        }
        tbody.innerHTML = html;
    }

    // Password modal state
    let _passwordResolve = null;
    let _passwordReject = null;

    function requestAdminPassword(message) {
        return new Promise((resolve, reject) => {
            _passwordResolve = resolve;
            _passwordReject = reject;
            document.getElementById('passwordModalMessage').textContent = message;
            document.getElementById('adminPasswordInput').value = '';
            document.getElementById('adminPasswordModal').style.display = 'flex';
            setTimeout(() => document.getElementById('adminPasswordInput').focus(), 100);
        });
    }

    function submitPasswordModal() {
        const password = document.getElementById('adminPasswordInput').value.trim();
        document.getElementById('adminPasswordModal').style.display = 'none';
        if (_passwordResolve) {
            _passwordResolve(password);
            _passwordResolve = null;
            _passwordReject = null;
        }
    }

    function cancelPasswordModal() {
        document.getElementById('adminPasswordModal').style.display = 'none';
        if (_passwordResolve) {
            _passwordResolve(null);
            _passwordResolve = null;
            _passwordReject = null;
        }
    }

    function parseDate(dateStr) {
        if (!dateStr || dateStr === 'N/A' || dateStr === '') return new Date(0);
        // Always parse as DD/MM/YYYY (the format stored in the CSV)
        const parts = dateStr.split('/');
        if (parts.length === 3) {
            const date = new Date(parts[2], parts[1] - 1, parts[0]);
            return isNaN(date.getTime()) ? new Date(0) : date;
        }
        let date = new Date(dateStr);
        return isNaN(date.getTime()) ? new Date(0) : date;
    }

    function isRedUser(user) {
        return user.needs_verification === true;
    }

    function getPdnBadgeColor(code) {
        if (!code) return 'bg-gray-100 text-gray-800';
        const prefix = code.charAt(0).toUpperCase();
        switch(prefix) {
            case 'E': return 'bg-blue-100 text-blue-800';
            case 'A': return 'bg-green-100 text-green-800';
            case 'T': return 'pdn-badge-t';
            case 'P': return 'pdn-badge-p';
            default: return 'bg-gray-100 text-gray-800';
        }
    }

    function logError(context, error) {
        console.error(`[${context}]`, error?.message || error);
    }

    function getDiagnosisUserEmail() {
        // Try to find an element with data-email or fallback to text content
        const emailElem = document.querySelector('#questionnaireContent [data-email]');
        if (emailElem) return emailElem.getAttribute('data-email');
        // Fallback: try to find a visible email in the content
        const match = document.getElementById('questionnaireContent').innerText.match(/[\w.-]+@[\w.-]+/);
        return match ? match[0] : 'user';
    }

    // Main download function that handles multiple formats
    function downloadReport(format = 'pdf') {
        switch (format) {
            case 'pdf':
                downloadDiagnosisAsPDF();
                break;
            case 'json':
                downloadUserJSON();
                break;
            default:
                showNotification('פורמט לא נתמך', 'error');
        }
    }

    // Main PDF export function
    function downloadDiagnosisAsPDF() {
        const content = document.getElementById('questionnaireContent');
        if (!content) {
            showNotification('לא נמצאו נתונים לייצוא', 'error');
            return;
        }

        // Create a new container for the complete report
        const reportContainer = document.createElement('div');
        reportContainer.style.cssText = `
        font-family: 'Noto Sans Hebrew', 'Arial', sans-serif !important;
        direction: rtl !important;
        text-align: right !important;
        font-size: 14px !important;
        line-height: 1.6 !important;
        color: #000 !important;
        background: white !important;
        padding: 20px !important;
        width: 100% !important;
        max-width: 800px !important;
        margin: 0 auto !important;
    `;
        reportContainer.setAttribute('dir', 'rtl');
        reportContainer.setAttribute('lang', 'he');

        // Clone the questionnaire content
        const questionnaireClone = content.cloneNode(true);

        // Remove the user metadata section from the clone
        const metadataSection = questionnaireClone.querySelector('.bg-gradient-to-br.from-blue-50.via-blue-50.to-blue-100');
        if (metadataSection) {
            metadataSection.remove();
        }

        // Find the questionnaire section and add user ID before it
        const questionnaireSection = questionnaireClone.querySelector('.bg-white.p-8.rounded-2xl.border.border-gray-200.shadow-lg.mt-6');
        if (questionnaireSection) {
            // Create user ID section
            const userIdSection = document.createElement('div');
            userIdSection.style.cssText = `
            background: linear-gradient(135deg, #f3f4f6 0%, #e5e7eb 100%);
            padding: 20px;
            border-radius: 12px;
            margin-bottom: 20px;
            border: 1px solid #d1d5db;
            text-align: center;
            font-family: 'Noto Sans Hebrew', 'Arial', sans-serif !important;
            direction: rtl !important;
        `;

            const userId = getUserMetadata('user_id');
            userIdSection.innerHTML = `
            <div style="font-size: 16px; font-weight: bold; color: #374151; margin-bottom: 8px; font-family: 'Noto Sans Hebrew', 'Arial', sans-serif;">
                מזהה מערכת
            </div>
            <div style="font-family: monospace; font-size: 18px; font-weight: bold; color: #1e40af; background: white; padding: 8px 16px; border-radius: 8px; display: inline-block; border: 1px solid #d1d5db;">
                ${userId}
            </div>
        `;

            // Insert the user ID section before the questionnaire section
            questionnaireSection.parentNode.insertBefore(userIdSection, questionnaireSection);
        }

        // Apply RTL and font styles to all elements in the clone
        const allElements = questionnaireClone.querySelectorAll('*');
        allElements.forEach(element => {
            element.style.fontFamily = "'Noto Sans Hebrew', 'Arial', sans-serif";
            element.style.direction = 'rtl';
            element.style.textAlign = 'right';
        });

        // Add the modified content to the report container
        reportContainer.appendChild(questionnaireClone);

        // Generate filename with user ID and date
        const userId = getUserMetadata('user_id');
        const date = new Date().toLocaleDateString('he-IL', {year: 'numeric', month: '2-digit', day: '2-digit'});

        // Create filename: user_id_date.pdf
        const filename = `${userId}_${date}.pdf`;

        // PDF options with better Hebrew support
        const opt = {
            margin: [0.5, 0.5, 0.5, 0.5], // inches (top, left, bottom, right)
            filename: filename,
            image: {type: 'jpeg', quality: 0.98},
            html2canvas: {
                scale: 2,
                useCORS: true,
                allowTaint: true,
                backgroundColor: '#ffffff'
            },
            jsPDF: {
                unit: 'in',
                format: 'a4',
                orientation: 'portrait',
                compress: true
            },
            pagebreak: {mode: ['avoid-all', 'css', 'legacy']}
        };

        // Use html2pdf
        html2pdf().set(opt).from(reportContainer).save();
    }

    // JSON export function - downloads existing user JSON file
    async function downloadUserJSON(adminPassword) {
        try {
            // Get user email from the current modal
            const userEmail = getDiagnosisUserEmail();
            if (!userEmail) {
                showNotification('לא ניתן לזהות את המשתמש', 'error');
                return;
            }

            // Convert email to folder name format (remove @ and . and convert to lowercase)
            const folderName = userEmail.replace('@', '').replace('.', '').toLowerCase();

            // Construct the path to the user's JSON file
            const jsonFilePath = `saved_results/${folderName}/${userEmail}_answers.json`;

            // Fetch the JSON file from the server with admin password
            const response = await fetch(`/pdn-admin/download-json?file_path=${encodeURIComponent(jsonFilePath)}&session_token=${sessionToken}&admin_password=${encodeURIComponent(adminPassword)}`);

            if (response.ok) {
                // Get the file content
                const jsonContent = await response.json();

                // Create and download the file
                const jsonString = JSON.stringify(jsonContent, null, 2);
                const blob = new Blob([jsonString], {type: 'application/json;charset=utf-8'});
                const url = URL.createObjectURL(blob);

                const link = document.createElement('a');
                link.href = url;
                link.download = `${userEmail}_answers.json`;
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);

                URL.revokeObjectURL(url);

            } else if (response.status === 401) {
                if (response.headers.get('X-Error-Type') === 'invalid_password') {
                    showNotification('סיסמת מנהל שגויה', 'error');
                } else {
                    // Session expired, redirect to login
                    redirectToLogin();
                }
            } else if (response.status === 404) {
                showNotification('קובץ ה-JSON לא נמצא', 'error');
            } else {
                throw new Error(`Failed to download JSON: ${response.status}`);
            }

        } catch (error) {
            logError('downloadJSON', error);
            showNotification('שגיאה בהורדת קובץ ה-JSON', 'error');
        }
    }

    // Helper function to get user metadata from the current data
    function getUserMetadata(field) {
        // Try to get from the current user data
        const currentUser = getCurrentUserFromModal();
        if (currentUser && currentUser[field]) {
            return currentUser[field];
        }

        // Try to get from the metadata in the modal content
        const metadataElement = document.querySelector('#questionnaireContent .font-mono.font-bold.text-blue-600.text-lg');
        if (metadataElement && field === 'user_id') {
            return metadataElement.textContent.trim();
        }

        // Try to get from the metadata object in the displayQuestionsWithText function
        const metadataSection = document.querySelector('#questionnaireContent .bg-gradient-to-br.from-blue-50.via-blue-50.to-blue-100');
        if (metadataSection) {
            const userIdElement = metadataSection.querySelector('.font-mono.font-bold.text-blue-600.text-lg');
            if (userIdElement && field === 'user_id') {
                return userIdElement.textContent.trim();
            }
        }

        // Fallback values
        const fallbacks = {
            'user_id': 'לא זמין',
            'email': getDiagnosisUserEmail(),
            'date': 'לא זמין',
            'pdn_code': 'לא זמין',
            'pdn_voice_code': 'לא זמין',
            'diagnose_pdn_code': 'לא זמין',
            'diagnose_comments': 'אין הערות'
        };

        return fallbacks[field] || 'לא זמין';
    }

    // Helper function to get current user data from the modal
    function getCurrentUserFromModal() {
        const userEmail = getDiagnosisUserEmail();
        if (userEmail && currentData) {
            return currentData.find(user => user.email === userEmail);
        }
        return null;
    }

    let sessionToken = null;
    let currentData = [];
    let currentEditEmail = null;
    let avgCostPerCall = 0; // Updated when token usage loads
    let _lastFocusedElement = null;

    // Initialize
    document.addEventListener('DOMContentLoaded', function () {
        // Get session token from localStorage
        sessionToken = localStorage.getItem('adminSessionToken');

        // If no session token, redirect to login
        if (!sessionToken) {
            window.location.href = '/pdn-admin/';
            return;
        }

        setupEventListeners();
        resetFilterDropdowns();
        loadMetadata();
        loadVersion();

        // Initialize tab from URL or default to metrics
        const urlTab = new URLSearchParams(window.location.search).get('tab');
        if (urlTab && document.getElementById('tab-' + urlTab)) {
            switchTab(urlTab, true);
        }

        // Add global error handler for 401 responses
        window.addEventListener('unhandledrejection', function (event) {
            if (event.reason && event.reason.status === 401) {
                redirectToLogin();
            }
        });
    });

    // ===== Tab Navigation =====
    let _tabLoaded = { metrics: true }; // Track which tabs have loaded their data

    function switchTab(tabId, skipPush) {
        // Hide all tab contents
        document.querySelectorAll('.tab-content').forEach(el => {
            el.classList.remove('active');
        });
        // Deactivate all nav tabs and update ARIA
        document.querySelectorAll('.nav-tab').forEach(el => {
            el.classList.remove('active');
            el.setAttribute('aria-selected', 'false');
        });
        // Show the target tab
        const tabEl = document.getElementById('tab-' + tabId);
        if (tabEl) tabEl.classList.add('active');
        // Activate the nav button
        const navEl = document.getElementById('nav' + tabId.charAt(0).toUpperCase() + tabId.slice(1));
        if (navEl) {
            navEl.classList.add('active');
            navEl.setAttribute('aria-selected', 'true');
        }

        // Lazy-load data for tabs that haven't been loaded yet
        if (!_tabLoaded[tabId]) {
            _tabLoaded[tabId] = true;
            switch (tabId) {
                case 'stats':
                    loadConversationStats();
                    break;
                case 'costs':
                    loadTokenUsage();
                    break;
                case 'coupons':
                    loadCoupons();
                    break;
                case 'chatusers':
                    loadChatUsers();
                    break;
            }
        }

        // Update URL
        if (!skipPush) {
            updateUrlState({ tab: tabId === 'metrics' ? null : tabId });
        }
    }

    // Keyboard shortcuts: Ctrl+1..6 for tabs
    document.addEventListener('keydown', function(e) {
        if (!e.ctrlKey && !e.metaKey) return;
        const tabMap = { '1': 'metrics', '2': 'users', '3': 'stats', '4': 'costs', '5': 'coupons', '6': 'chatusers' };
        if (tabMap[e.key]) {
            e.preventDefault();
            switchTab(tabMap[e.key]);
        }
    });

    function setupEventListeners() {
        // Search functionality with debounce (legacy element - may not exist)
        const searchInput = document.getElementById('searchInput');
        if (searchInput) {
            searchInput.addEventListener('input', debounce(handleSearch, 300));
            searchInput.addEventListener('input', function() {
                const clearBtn = document.getElementById('clearSearchBtn');
                if (clearBtn) clearBtn.style.display = this.value ? 'block' : 'none';
            });
        }

        // Red users filter (legacy element - may not exist)
        const redFilter = document.getElementById('redUsersFilter');
        if (redFilter) redFilter.addEventListener('change', handleFilter);

        // Refresh button
        document.getElementById('refreshBtn').addEventListener('click', () => {
            loadMetadata();
            loadConversationStats();
        });

        // Logout button
        document.getElementById('logoutBtn').addEventListener('click', handleLogout);

        // Logged in users button
        document.getElementById('loggedInUsersBtn').addEventListener('click', showLoggedInUsers);

        // Edit diagnose form
        document.getElementById('editDiagnoseForm').addEventListener('submit', handleEditDiagnose);

        // Restore URL state on popstate (back/forward navigation)
        window.addEventListener('popstate', restoreUrlState);
    }

    async function handleLogout() {
        if (sessionToken) {
            try {
                await fetch(`/pdn-admin/logout?session_token=${sessionToken}`);
            } catch (error) {
                logError('logout', error);
            }
        }
        sessionToken = null;
        // Clear session data from localStorage
        localStorage.removeItem('adminSessionToken');
        localStorage.removeItem('adminEmail');
        // Redirect to login page
        window.location.replace('/pdn-admin/');
    }

    async function showLoggedInUsers() {
        try {
            const response = await fetch(`/pdn-admin/logged-in-users?session_token=${sessionToken}`);
            if (!response.ok) {
                throw new Error('Failed to fetch logged-in users');
            }

            const data = await response.json();
            const content = document.getElementById('loggedInUsersContent');

            if (data.count === 0) {
                content.innerHTML = '<p class="text-gray-600 text-center py-4">אין משתמשים מחוברים כרגע</p>';
            } else {
                let html = `<div class="mb-4 text-sm text-gray-600">סה"כ: ${data.count} משתמשים</div>`;
                html += '<div class="space-y-3">';

                data.users.forEach(user => {
                    const appName = user.type === 'admin' ? 'מנהל' : user.type === 'diagnosis' ? 'אבחון' : 'צ׳אט';
                    const appColor = user.type === 'admin' ? 'bg-blue-100 text-blue-800' : user.type === 'diagnosis' ? 'bg-green-100 text-green-800' : 'bg-purple-100 text-purple-800';
                    html += `
                        <div class="border border-gray-200 rounded-lg p-4 hover:bg-gray-50 transition-colors">
                            <div class="flex items-center justify-between">
                                <div class="flex items-center space-x-3 space-x-reverse">
                                    <i class="fas fa-user-circle text-blue-900 text-2xl"></i>
                                    <div>
                                        <div class="flex items-center gap-2">
                                            <p class="font-semibold text-gray-800">${user.email}</p>
                                            <span class="px-2 py-1 text-xs font-semibold rounded ${appColor}">${appName}</span>
                                        </div>
                                        <p class="text-sm text-gray-600">התחבר: ${user.login_time}</p>
                                        ${user.expires_at ? `<p class="text-xs text-gray-500">תוקף עד: ${user.expires_at}</p>` : ''}
                                    </div>
                                </div>
                            </div>
                        </div>
                    `;
                });

                html += '</div>';
                content.innerHTML = html;
            }

            document.getElementById('loggedInUsersModal').style.display = 'flex';
            setTimeout(() => { document.getElementById('loggedInUsersModal').querySelector('button, input')?.focus(); }, 100);
        } catch (error) {
            logError('loggedInUsers', error);
            showNotification('שגיאה בטעינת משתמשים מחוברים', 'error');
        }
    }

    // Priority scoring and inline recommendation for Pnina's review queue
    function calculatePriority(user) {
        const score = user.confidence_score;
        const hasCode = user.pdn_code && user.pdn_code !== 'NA' && user.pdn_code !== '';
        const needsVerification = user.needs_verification;
        const stageEOverride = user.stage_e_override;
        const hasDiagnose = user.diagnose_pdn_code && user.diagnose_pdn_code.length > 0;

        // Already diagnosed by human - lowest priority (done)
        if (hasDiagnose) {
            return { priority: 4, label: 'done', recommendation: '' };
        }

        // No code at all
        if (!hasCode) {
            return { priority: 3, label: 'gray', recommendation: 'ללא קוד - ייתכן שאלון לא הושלם' };
        }

        // RED: Stage E override or very low confidence
        if (stageEOverride) {
            const before = user.dominant_before_stage_e || '';
            const after = user.pdn_code || '';
            const changeText = before ? `לפני: <b>${before}</b>, קוד מעודכן: <b>${after}</b>` : `קוד מעודכן: <b>${after}</b>`;
            return { priority: 1, label: 'red', recommendation: `שלב 5 שינה תוצאה ${changeText} שקול שיחה` };
        }
        if (score !== undefined && score !== null && score < 10) {
            return { priority: 1, label: 'red', recommendation: 'ניקוד כמעט שווה — שקול שיחה' };
        }

        // YELLOW: Low confidence or needs verification
        if (needsVerification && score !== undefined && score < 50) {
            // Generate smart recommendation based on the code
            const trait = user.pdn_code ? user.pdn_code[0] : '?';
            const energyNum = user.pdn_code ? user.pdn_code.slice(1) : '';
            const energyMap = {'3':'F','6':'F','9':'F','12':'F','7':'D','4':'D','10':'D','1':'D','11':'S','8':'S','2':'S','5':'S'};
            const energy = energyMap[energyNum] || '?';
            let rec = `ככל הנראה ${user.pdn_code}`;
            if (score < 30) rec += ' - פער קטן בתכונות, בדוק קול';
            else rec += ` - פער אנרגיה קטן (${energy}), בדוק קצב דיבור`;
            return { priority: 2, label: 'yellow', recommendation: rec };
        }
        if (needsVerification) {
            return { priority: 2, label: 'yellow', recommendation: `${user.pdn_code} - פער קטן, מומלץ האזנה להקלטה` };
        }

        // GREEN: High confidence, no issues
        return { priority: 3, label: 'green', recommendation: '' };
    }

    async function loadMetadata() {
        const refreshBtn = document.getElementById('refreshBtn');

        // Check if button is already disabled (prevent multiple calls)
        if (refreshBtn.disabled) {
            return;
        }

        // Disable refresh button
        refreshBtn.disabled = true;

        // Safety timeout to re-enable button after 30 seconds
        const safetyTimeout = setTimeout(() => {
            if (refreshBtn.disabled) {
                refreshBtn.disabled = false;
            }
        }, 30000);

        showTableSkeleton();
        try {
            const response = await fetch('/pdn-admin/metadata/csv?session_token=' + sessionToken);
            if (response.ok) {
                const data = await response.json();
                currentData = data.data;

                // Enrich each user with priority score and recommendation
                currentData.forEach(u => {
                    const pr = calculatePriority(u);
                    u._priority = pr.priority;
                    u._priorityLabel = pr.label;
                    u._recommendation = pr.recommendation;
                });

                // Sort by priority (red first), then by date within same priority
                currentData.sort((a, b) => {
                    if (a._priority !== b._priority) return a._priority - b._priority;
                    return parseDate(b.date) - parseDate(a.date);
                });

                displayData(currentData);

                // Restore URL state after data is loaded
                restoreUrlState();
            } else if (response.status === 401) {
                redirectToLogin();
            } else {
                throw new Error('Failed to load metadata');
            }
        } catch (error) {
            showNotification('שגיאה בטעינת נתונים', 'error');
        } finally {
            // Clear safety timeout and re-enable refresh button
            clearTimeout(safetyTimeout);
            refreshBtn.disabled = false;
        }
    }

    async function loadConversationStats(days) {
        if (!days) days = window._statsDays || 30;
        window._statsDays = days;
        const container = document.getElementById('conversationStats');
        container.innerHTML = '<div style="text-align:center;padding:24px;"><i class="fas fa-spinner fa-spin" style="color:#94a3b8;font-size:16px;"></i></div>';
        // Update active button state
        document.querySelectorAll('.stats-period-btn').forEach(btn => {
            const isActive = parseInt(btn.dataset.days) === days;
            btn.style.background = isActive ? '#0b2e6b' : 'transparent';
            btn.style.color = isActive ? 'white' : '#64748b';
        });
        try {
            const response = await fetch(`/pdn-admin/conversation-stats?session_token=${sessionToken}&days=${days}`);

            if (response.ok) {
                const data = await response.json();
                displayConversationStats(data.stats);
            }
        } catch (error) {
            logError('loadStats', error);
        }
    }

    async function loadTokenUsage(days) {
        if (!days) days = window._tokenDays || 7;
        window._tokenDays = days;
        // Update active button state
        document.querySelectorAll('.token-period-btn').forEach(btn => {
            const isActive = parseInt(btn.dataset.days) === days;
            btn.style.background = isActive ? '#0b2e6b' : 'transparent';
            btn.style.color = isActive ? 'white' : '#64748b';
        });
        const container = document.getElementById('tokenUsageContent');
        container.innerHTML = '<div style="text-align:center;padding:24px;"><i class="fas fa-spinner fa-spin" style="color:#94a3b8;font-size:20px;"></i><p style="font-size:13px;color:#94a3b8;margin-top:8px;">טוען נתוני עלויות...</p></div>';
        try {
            const response = await fetch(`/pdn-admin/token-usage?session_token=${sessionToken}&days=${days}`);
            if (!response.ok) throw new Error('Failed to load');
            const raw = await response.json();
            const { users: stats, daily_totals, projection, period_days } = raw.stats;
            const userNames = Object.keys(stats);
            if (userNames.length === 0) {
                container.innerHTML = '<div style="text-align:center;padding:32px 16px;background:#f8fafc;border-radius:12px;border:1px dashed #cbd5e1;"><i class="fas fa-chart-line" style="font-size:24px;color:#94a3b8;margin-bottom:8px;display:block;"></i><p style="font-size:13px;color:#64748b;margin:0;">אין נתוני שימוש עדיין</p></div>';
                return;
            }
            let tIn=0,tOut=0,tCR=0,tCost=0,tSav=0,tCalls=0;
            userNames.forEach(u=>{const s=stats[u];tIn+=s.input_tokens;tOut+=s.output_tokens;tCR+=s.cache_read_tokens;tCost+=s.total_cost;tSav+=s.cache_savings;tCalls+=s.calls;});
            avgCostPerCall = tCalls > 0 ? tCost / tCalls : 0;
            updateCostEstimate();
            let html=`<div style="display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin-bottom:20px;">
                <div style="background:#f0f4ff;border-radius:12px;padding:16px;text-align:center;border:1px solid #dbeafe;"><div style="font-size:24px;font-weight:800;color:#0b2e6b;">${tCalls}</div><div style="font-size:11px;color:#64748b;margin-top:4px;">קריאות (${period_days} ימים)</div></div>
                <div style="background:#f0f4ff;border-radius:12px;padding:16px;text-align:center;border:1px solid #dbeafe;"><div style="font-size:24px;font-weight:800;color:#0b2e6b;">${((tIn+tOut)/1000).toFixed(1)}K</div><div style="font-size:11px;color:#64748b;margin-top:4px;">סה"כ טוקנים</div></div>
                <div style="background:#ecfdf5;border-radius:12px;padding:16px;text-align:center;border:1px solid #d1fae5;"><div style="font-size:24px;font-weight:800;color:#059669;">$${tCost.toFixed(3)}</div><div style="font-size:11px;color:#64748b;margin-top:4px;">עלות בפועל</div></div>
                <div style="background:#fffbeb;border-radius:12px;padding:16px;text-align:center;border:1px solid #fde68a;"><div style="font-size:24px;font-weight:800;color:#d97706;">$${projection.projected_monthly}</div><div style="font-size:11px;color:#64748b;margin-top:4px;">תחזית חודשית</div></div>
                <div style="background:#fef2f2;border-radius:12px;padding:16px;text-align:center;border:1px solid #fecaca;"><div style="font-size:24px;font-weight:800;color:#dc2626;">$${projection.projected_yearly}</div><div style="font-size:11px;color:#64748b;margin-top:4px;">תחזית שנתית</div></div>
            </div>`;
            const chartDays=Object.keys(daily_totals).sort();
            if(chartDays.length>1){
                const mx=Math.max(...chartDays.map(d=>daily_totals[d].cost),0.001);
                html+=`<div style="margin-bottom:20px;padding:20px;background:white;border-radius:14px;border:1px solid #e2e8f0;box-shadow:0 1px 3px rgba(0,0,0,0.04);">
                    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:16px;">
                        <h4 style="font-size:14px;font-weight:700;color:#1e293b;margin:0;display:flex;align-items:center;gap:8px;"><i class="fas fa-chart-bar" style="color:#0b2e6b;font-size:12px;"></i> עלות יומית</h4>
                        <div style="display:flex;gap:16px;font-size:11px;color:#64748b;"><span>ממוצע: <strong style="color:#0b2e6b;">$${projection.avg_daily_cost.toFixed(4)}</strong></span><span>${projection.active_days} ימים פעילים מתוך ${period_days}</span></div>
                    </div>
                    <div style="display:flex;align-items:flex-end;gap:3px;height:140px;padding:0 4px;">`;
                chartDays.forEach(day=>{
                    const d=daily_totals[day];
                    const bh=Math.max(4,(d.cost/mx)*100);
                    const isToday=day===new Date().toISOString().slice(0,10);
                    const barColor=isToday?'#0b2e6b':'#93c5fd';
                    html+=`<div style="flex:1;display:flex;flex-direction:column;align-items:center;justify-content:flex-end;height:100%;position:relative;cursor:pointer;" onmouseenter="this.querySelector('.tip').style.opacity='1'" onmouseleave="this.querySelector('.tip').style.opacity='0'">
                        <div class="tip" style="position:absolute;top:-32px;background:#1e293b;color:white;font-size:10px;padding:4px 8px;border-radius:6px;opacity:0;transition:opacity 0.2s;white-space:nowrap;z-index:10;pointer-events:none;">$${d.cost.toFixed(4)} | ${d.calls} קריאות</div>
                        <div style="width:100%;background:${barColor};border-radius:4px 4px 0 0;height:${bh}%;min-height:4px;transition:background 0.2s;"></div>
                        <div style="font-size:9px;color:#94a3b8;margin-top:6px;transform:rotate(-45deg);transform-origin:top right;white-space:nowrap;">${day.slice(5)}</div>
                    </div>`;
                });
                html+=`</div></div>`;
            }
            html+=`<div style="overflow-x:auto;border-radius:10px;border:1px solid #e2e8f0;">
                <table style="width:100%;font-size:13px;border-collapse:collapse;">
                    <thead><tr style="background:#f8fafc;border-bottom:1px solid #e2e8f0;">
                        <th style="padding:12px 16px;text-align:right;font-weight:600;color:#475569;">משתמש</th>
                        <th style="padding:12px 16px;text-align:center;font-weight:600;color:#475569;">קריאות</th>
                        <th style="padding:12px 16px;text-align:center;font-weight:600;color:#475569;">קלט</th>
                        <th style="padding:12px 16px;text-align:center;font-weight:600;color:#475569;">פלט</th>
                        <th style="padding:12px 16px;text-align:center;font-weight:600;color:#475569;">Cache</th>
                        <th style="padding:12px 16px;text-align:center;font-weight:600;color:#475569;">עלות</th>
                    </tr></thead><tbody>`;
            userNames.sort((a,b)=>stats[b].total_cost-stats[a].total_cost);
            userNames.forEach(user=>{const s=stats[user];
            const cacheRead=s.cache_read_tokens||0;
            const totalIn=s.input_tokens||1;
            const cacheRate=Math.round(cacheRead/totalIn*100);
            const cacheColor=cacheRate>=60?'#059669':cacheRate>=30?'#d97706':'#94a3b8';
            html+=`<tr style="border-bottom:1px solid #f1f5f9;"><td style="padding:10px 16px;font-weight:500;color:#1e293b;">${user}</td><td style="padding:10px 16px;text-align:center;color:#475569;">${s.calls}</td><td style="padding:10px 16px;text-align:center;color:#475569;">${(s.input_tokens/1000).toFixed(1)}K</td><td style="padding:10px 16px;text-align:center;color:#475569;">${(s.output_tokens/1000).toFixed(1)}K</td><td style="padding:10px 16px;text-align:center;font-weight:600;color:${cacheColor};">${(cacheRead/1000).toFixed(1)}K (${cacheRate}%)</td><td style="padding:10px 16px;text-align:center;font-weight:700;color:#0b2e6b;">$${s.total_cost.toFixed(4)}</td></tr>`;});
            html+=`<tr style="background:#f8fafc;border-top:2px solid #e2e8f0;"><td style="padding:10px 16px;font-weight:700;color:#1e293b;">סה"כ</td><td style="padding:10px 16px;text-align:center;font-weight:700;">${tCalls}</td><td style="padding:10px 16px;text-align:center;font-weight:700;">${(tIn/1000).toFixed(1)}K</td><td style="padding:10px 16px;text-align:center;font-weight:700;">${(tOut/1000).toFixed(1)}K</td><td style="padding:10px 16px;text-align:center;font-weight:700;color:#059669;">${(tCR/1000).toFixed(1)}K (${tIn>0?Math.round(tCR/tIn*100):0}%)</td><td style="padding:10px 16px;text-align:center;font-weight:700;color:#0b2e6b;">$${tCost.toFixed(4)}</td></tr></tbody></table></div>`;
            html+=`<p style="font-size:10px;color:#94a3b8;margin-top:12px;text-align:center;">* תמחור לפי Claude Sonnet 5. תחזית מבוססת על ממוצע יומי.</p>`;
            container.innerHTML=html;
        } catch(error){logError('loadTokenUsage',error);container.innerHTML='<div style="text-align:center;padding:24px;color:#dc2626;font-size:13px;"><i class="fas fa-exclamation-circle" style="margin-left:6px;"></i> שגיאה בטעינת נתוני עלויות</div>';}
    }

    function updateCostEstimate() {
        // Show average cost per call in the highlight element
        const highlight = document.getElementById('avgCostHighlight');
        const valueEl = document.getElementById('avgCostValue');
        if (highlight && valueEl && avgCostPerCall > 0) {
            highlight.style.display = 'block';
            valueEl.textContent = '$' + avgCostPerCall.toFixed(4);
        }
    }

    function updateEstimateFromCalls() {
        updateCostEstimate();
    }

    function updateEstimateFromCost() {
        updateCostEstimate();
    }

    function displayConversationStats(stats) {
        const container = document.getElementById('conversationStats');
        
        const allUsers = new Set();
        const dates = Object.keys(stats).sort().reverse();
        
        dates.forEach(date => {
            Object.keys(stats[date]).forEach(email => allUsers.add(email));
        });
        
        const users = Array.from(allUsers).sort();

        // Show empty state if no users have conversations
        if (users.length === 0) {
            container.innerHTML = '<div style="text-align:center;padding:32px 16px;background:#f8fafc;border-radius:12px;border:1px dashed #cbd5e1;"><i class="fas fa-comments" style="font-size:24px;color:#94a3b8;margin-bottom:8px;display:block;"></i><p style="font-size:13px;color:#64748b;margin:0;">אין שיחות בתקופה הנבחרת</p><p style="font-size:11px;color:#94a3b8;margin-top:4px;">נסה לבחור תקופה ארוכה יותר</p></div>';
            return;
        }
        const weeklyTotals = {};
        let grandTotal = 0;
        users.forEach(user => {
            weeklyTotals[user] = dates.reduce((sum, date) => sum + (stats[date][user] || 0), 0);
            grandTotal += weeklyTotals[user];
        });

        // Find max for heat coloring
        const maxPerCell = Math.max(...dates.flatMap(d => users.map(u => stats[d][u] || 0)), 1);
        
        function heatColor(val) {
            if (val === 0) return 'transparent';
            const intensity = Math.min(val / maxPerCell, 1);
            return `rgba(11, 46, 107, ${0.08 + intensity * 0.25})`;
        }

        let html = `
            <div style="grid-column: 1 / -1; width: 100%;">
                <!-- Summary cards -->
                <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-bottom: 20px;">
                    <div style="background: #f0f4ff; border-radius: 12px; padding: 16px; text-align: center; border: 1px solid #dbeafe;">
                        <div style="font-size: 24px; font-weight: 800; color: #0b2e6b;">${grandTotal}</div>
                        <div style="font-size: 11px; color: #64748b; margin-top: 4px;">סה"כ שיחות (${dates.length} ימים)</div>
                    </div>
                    <div style="background: #f0f4ff; border-radius: 12px; padding: 16px; text-align: center; border: 1px solid #dbeafe;">
                        <div style="font-size: 24px; font-weight: 800; color: #0b2e6b;">${users.length}</div>
                        <div style="font-size: 11px; color: #64748b; margin-top: 4px;">משתמשים פעילים</div>
                    </div>
                    <div style="background: #f0f4ff; border-radius: 12px; padding: 16px; text-align: center; border: 1px solid #dbeafe;">
                        <div style="font-size: 24px; font-weight: 800; color: #0b2e6b;">${dates.length > 0 ? Math.round(grandTotal / dates.length) : 0}</div>
                        <div style="font-size: 11px; color: #64748b; margin-top: 4px;">ממוצע יומי</div>
                    </div>
                </div>

                <!-- Heat map table -->
                <div style="overflow-x: auto; border-radius: 12px; border: 1px solid #e2e8f0; background: white;">
                    <table style="width: 100%; border-collapse: collapse; font-size: 13px; min-width: 600px;">
                        <thead>
                            <tr style="background: #f8fafc; border-bottom: 2px solid #e2e8f0;">
                                <th style="padding: 12px 16px; text-align: right; font-weight: 700; color: #1e293b; position: sticky; right: 0; background: #f8fafc; z-index: 1;">משתמש</th>
                                ${dates.map(date => `<th style="padding: 12px 10px; text-align: center; font-weight: 600; color: #475569; font-size: 11px; white-space: nowrap;">${date.slice(5)}</th>`).join('')}
                                <th style="padding: 12px 16px; text-align: center; font-weight: 700; color: #0b2e6b; background: #f0f4ff;">סה"כ</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${users.map(user => `
                                <tr style="border-bottom: 1px solid #f1f5f9;">
                                    <td style="padding: 10px 16px; font-weight: 500; color: #1e293b; white-space: nowrap; position: sticky; right: 0; background: white; z-index: 1;">${escapeHtml(user)}</td>
                                    ${dates.map(date => {
                                        const val = stats[date][user] || 0;
                                        return `<td style="padding: 10px; text-align: center; color: ${val > 0 ? '#1e293b' : '#cbd5e1'}; font-weight: ${val > 0 ? '600' : '400'}; background: ${heatColor(val)};">${val}</td>`;
                                    }).join('')}
                                    <td style="padding: 10px 16px; text-align: center; font-weight: 700; color: #0b2e6b; background: #f0f4ff;">${weeklyTotals[user]}</td>
                                </tr>
                            `).join('')}
                            <tr style="background: #f8fafc; border-top: 2px solid #e2e8f0;">
                                <td style="padding: 10px 16px; font-weight: 700; color: #1e293b; position: sticky; right: 0; background: #f8fafc; z-index: 1;">סה"כ</td>
                                ${dates.map(date => {
                                    const dayTotal = Object.values(stats[date]).reduce((sum, count) => sum + count, 0);
                                    return `<td style="padding: 10px; text-align: center; font-weight: 700; color: #1e293b;">${dayTotal}</td>`;
                                }).join('')}
                                <td style="padding: 10px 16px; text-align: center; font-weight: 800; color: #0b2e6b; background: #f0f4ff; font-size: 15px;">${grandTotal}</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
                <p style="font-size: 10px; color: #94a3b8; margin-top: 8px; text-align: center;">צבע רקע מציין עוצמת שימוש יחסית</p>
            </div>
        `;
        
        container.innerHTML = html;
    }

    function displayData(data) {
        renderTable(data);
        updateDashboardSummary();
        updateMetrics();
        populateCouponFilter(data);
    }

    function populateCouponFilter(data) {
        const couponEl = document.getElementById('quickFilterCoupon');
        if (!couponEl) return;
        
        // Collect unique coupon codes from data
        const coupons = new Set();
        data.forEach(u => {
            if (u.coupon_code && u.coupon_code.trim()) {
                coupons.add(u.coupon_code.trim().toUpperCase());
            }
        });
        
        // Keep current selection if valid
        const currentVal = couponEl.value;
        
        // Clear and rebuild options
        couponEl.innerHTML = '<option value="">קופון</option>';
        [...coupons].sort().forEach(code => {
            const opt = document.createElement('option');
            opt.value = code;
            opt.textContent = code;
            couponEl.appendChild(opt);
        });
        
        // Restore selection if still valid
        if (currentVal && coupons.has(currentVal.toUpperCase())) {
            couponEl.value = currentVal;
        }
    }

    function updateDashboardSummary() {
        // Now handled by updateMetrics() — keeping function for compatibility
    }

    // ===== Metrics Dashboard =====
    let currentMetricsRange = 'week';

    function setMetricsRange(range) {
        currentMetricsRange = range;
        document.querySelectorAll('.metrics-range-btn').forEach(btn => btn.classList.remove('active'));
        document.getElementById('range' + range.charAt(0).toUpperCase() + range.slice(1)).classList.add('active');
        updateMetrics();
    }

    function getDateRangeFilter(range) {
        const now = new Date();
        now.setHours(23, 59, 59, 999);
        let startDate = null;
        if (range === 'week') {
            startDate = new Date(now);
            startDate.setDate(startDate.getDate() - 7);
        } else if (range === 'month') {
            startDate = new Date(now);
            startDate.setMonth(startDate.getMonth() - 1);
        } else if (range === 'year') {
            startDate = new Date(now);
            startDate.setFullYear(startDate.getFullYear() - 1);
        }
        // 'all' => startDate stays null
        return startDate;
    }

    function parseDateDDMMYYYY(dateStr) {
        if (!dateStr) return null;
        const parts = dateStr.split('/');
        if (parts.length !== 3) return null;
        const d = parseInt(parts[0], 10);
        const m = parseInt(parts[1], 10) - 1;
        const y = parseInt(parts[2], 10);
        if (isNaN(d) || isNaN(m) || isNaN(y)) return null;
        return new Date(y, m, d);
    }

    function updateMetrics() {
        const startDate = getDateRangeFilter(currentMetricsRange);
        const filtered = currentData.filter(u => {
            if (!startDate) return true;
            const d = parseDateDDMMYYYY(u.date);
            return d && d >= startDate;
        });

        // KPI: Completions
        const completions = filtered.filter(u => u.pdn_code && u.pdn_code !== 'N/A' && u.pdn_code !== '').length;
        document.getElementById('metricCompletions').textContent = completions;

        // KPI: Peak day
        const dayCounts = {};
        filtered.forEach(u => {
            if (u.date) dayCounts[u.date] = (dayCounts[u.date] || 0) + 1;
        });
        const peakEntry = Object.entries(dayCounts).sort((a, b) => b[1] - a[1])[0];
        if (peakEntry) {
            document.getElementById('metricPeakDay').textContent = peakEntry[1];
            document.getElementById('metricPeakDayLabel').textContent = 'ביום השיא ' + peakEntry[0].slice(0, 5);
        } else {
            document.getElementById('metricPeakDay').textContent = '0';
            document.getElementById('metricPeakDayLabel').textContent = 'ביום השיא';
        }

        // KPI: Diagnosed by human (has diagnose_pdn_code that is not empty/NA)
        const diagnosed = filtered.filter(u => u.diagnose_pdn_code && u.diagnose_pdn_code !== 'N/A' && u.diagnose_pdn_code !== '').length;
        document.getElementById('metricDiagnosed').textContent = diagnosed;

        // KPI: Not diagnosed by human (has PDN code but no diagnose_pdn_code)
        const notDiagnosed = filtered.filter(u => u.pdn_code && u.pdn_code !== 'N/A' && u.pdn_code !== '' && u.pdn_code !== 'NA' && (!u.diagnose_pdn_code || u.diagnose_pdn_code === '' || u.diagnose_pdn_code === 'N/A')).length;
        document.getElementById('metricNotDiagnosed').textContent = notDiagnosed;

        // KPI: Unique PDN codes
        const uniqueCodes = new Set(filtered.map(u => u.pdn_code).filter(c => c && c !== 'N/A' && c !== ''));
        document.getElementById('metricUniqueCodes').textContent = uniqueCodes.size;

        // KPI: Code match (system == diagnoser)
        const withBothCodes = filtered.filter(u => 
            u.pdn_code && u.pdn_code !== 'N/A' && u.pdn_code !== '' &&
            u.diagnose_pdn_code && u.diagnose_pdn_code !== 'N/A' && u.diagnose_pdn_code !== ''
        );
        const codeMatch = withBothCodes.filter(u => u.pdn_code === u.diagnose_pdn_code).length;
        const codeMismatch = withBothCodes.filter(u => u.pdn_code !== u.diagnose_pdn_code).length;
        const matchPct = withBothCodes.length > 0 ? Math.round((codeMatch / withBothCodes.length) * 100) : 0;
        document.getElementById('metricCodeMatch').innerHTML = withBothCodes.length > 0 ? `${codeMatch}/${withBothCodes.length} <span style="font-size:0.6em;opacity:0.7;">(${matchPct}%)</span>` : '—';
        document.getElementById('metricCodeMismatch').textContent = codeMismatch > 0 ? codeMismatch : '0';

        // KPI: Diagnosed today
        const now = new Date();
        const todayStr = String(now.getDate()).padStart(2, '0') + '/' + String(now.getMonth() + 1).padStart(2, '0') + '/' + now.getFullYear();
        const diagnosedToday = currentData.filter(u => u.date === todayStr).length;
        document.getElementById('metricToday').textContent = diagnosedToday;

        // KPI: Active users (fetch from server)
        if (sessionToken) {
            fetch(`/pdn-admin/logged-in-users?session_token=${sessionToken}`)
                .then(r => r.ok ? r.json() : {count: 0})
                .then(data => { document.getElementById('metricActiveUsers').textContent = data.count || 0; })
                .catch(() => { document.getElementById('metricActiveUsers').textContent = '0'; });
        }

        // KPI: Needs verification
        const needsVerification = filtered.filter(u => u.needs_verification === true).length;
        document.getElementById('metricNeedsVerification').textContent = needsVerification;

        // Chart 1: PDN Code Distribution — Grouped by Trait
        const codeCount = {};
        filtered.forEach(u => {
            if (u.pdn_code && u.pdn_code !== 'N/A' && u.pdn_code !== '') {
                codeCount[u.pdn_code] = (codeCount[u.pdn_code] || 0) + 1;
            }
        });
        const totalCodes = Object.values(codeCount).reduce((s, c) => s + c, 0) || 1;

        // Group by trait letter (A, T, P, E) + other
        const traitGroups = { A: [], T: [], P: [], E: [] };
        const traitColors = { A: '#0b2e6b', T: '#4a7ab5', P: '#1a3f7a', E: '#7c9fc9' };
        const traitNames = { A: 'יצירתי', T: 'שיטתי', P: 'מבצע', E: 'מנהיג' };

        Object.entries(codeCount).forEach(([code, count]) => {
            const trait = code.charAt(0).toUpperCase();
            if (traitGroups[trait]) {
                traitGroups[trait].push({ code, count });
            }
        });

        // Sort each group by count desc, and sort trait groups by total desc
        const traitTotals = Object.entries(traitGroups).map(([trait, codes]) => ({
            trait,
            codes: codes.sort((a, b) => b.count - a.count),
            total: codes.reduce((s, c) => s + c.count, 0)
        })).filter(g => g.total > 0).sort((a, b) => b.total - a.total);

        const maxTraitTotal = traitTotals.length > 0 ? traitTotals[0].total : 1;

        const groupedHtml = traitTotals.length > 0 ? traitTotals.map(group => {
            const barWidth = Math.max(8, (group.total / maxTraitTotal) * 100);
            const color = traitColors[group.trait] || '#94a3b8';
            const subCodes = group.codes.map(c => `${c.code}:${c.count}`).join(', ');
            const pct = Math.round((group.total / totalCodes) * 100);

            // Stacked sub-bar segments
            const segments = group.codes.map((c, idx) => {
                const segWidth = (c.count / group.total) * 100;
                const opacity = 1 - (idx * 0.2);
                return `<div style="width:${segWidth}%;height:100%;background:${color};opacity:${Math.max(0.4, opacity)};cursor:pointer;" onclick="filterByCode('${c.code}')" title="${c.code}: ${c.count}"></div>`;
            }).join('');

            return `<div style="margin-bottom:12px;">
                <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:4px;">
                    <div style="display:flex;align-items:center;gap:8px;">
                        <span style="font-size:20px;font-weight:800;color:${color};min-width:20px;">${group.trait}</span>
                        <span style="font-size:11px;color:#64748b;">${traitNames[group.trait]}</span>
                    </div>
                    <div style="display:flex;align-items:center;gap:8px;">
                        <span style="font-size:13px;font-weight:700;color:#1e293b;">${group.total}</span>
                        <span style="font-size:11px;color:#94a3b8;">(${pct}%)</span>
                    </div>
                </div>
                <div style="display:flex;height:24px;border-radius:6px;overflow:hidden;background:#f1f5f9;width:${barWidth}%;">
                    ${segments}
                </div>
                <div style="display:flex;gap:8px;margin-top:4px;flex-wrap:wrap;">
                    ${group.codes.map(c => `<span style="font-size:10px;color:#64748b;cursor:pointer;" onclick="filterByCode('${c.code}')">${c.code}:${c.count}</span>`).join('')}
                </div>
            </div>`;
        }).join('') : '<div style="color:#94a3b8;font-size:12px;text-align:center;padding:16px;">אין נתונים</div>';

        // Energy distribution (D, S, F) extracted from codes
        const energyGroups = { D: 0, S: 0, F: 0 };
        const energyCodeMap = { D: [], S: [], F: [] };
        const codeToEnergy = { '1': 'D', '4': 'D', '7': 'D', '10': 'D',
                               '2': 'S', '5': 'S', '8': 'S', '11': 'S',
                               '3': 'F', '6': 'F', '9': 'F', '12': 'F' };
        Object.entries(codeCount).forEach(([code, count]) => {
            const num = code.replace(/[A-Z]/gi, '');
            const energy = codeToEnergy[num];
            if (energy) {
                energyGroups[energy] += count;
                energyCodeMap[energy].push({ code, count });
            }
        });

        const energyColors = { D: '#0b2e6b', S: '#4a7ab5', F: '#7c9fc9' };
        const energyNames = { D: 'דינמית', S: 'יציבה', F: 'גמישה' };
        const maxEnergy = Math.max(...Object.values(energyGroups), 1);

        const energyHtml = ['D', 'S', 'F'].filter(e => energyGroups[e] > 0).map(energy => {
            const total = energyGroups[energy];
            const pct = Math.round((total / totalCodes) * 100);
            const barWidth = Math.max(8, (total / maxEnergy) * 100);
            const color = energyColors[energy];
            const subCodes = energyCodeMap[energy].sort((a, b) => b.count - a.count);

            return `<div style="margin-bottom:10px;">
                <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:3px;">
                    <div style="display:flex;align-items:center;gap:6px;">
                        <span style="font-size:16px;font-weight:800;color:${color};">${energy}</span>
                        <span style="font-size:11px;color:#64748b;">${energyNames[energy]}</span>
                    </div>
                    <div style="display:flex;align-items:center;gap:6px;">
                        <span style="font-size:12px;font-weight:700;color:#1e293b;">${total}</span>
                        <span style="font-size:10px;color:#94a3b8;">(${pct}%)</span>
                    </div>
                </div>
                <div style="height:16px;border-radius:4px;overflow:hidden;background:#f1f5f9;width:${barWidth}%;">
                    <div style="width:100%;height:100%;background:${color};border-radius:4px;"></div>
                </div>
                <div style="display:flex;gap:6px;margin-top:2px;flex-wrap:wrap;">
                    ${subCodes.map(c => `<span style="font-size:10px;color:#64748b;cursor:pointer;" onclick="filterByCode('${c.code}')">${c.code}:${c.count}</span>`).join('')}
                </div>
            </div>`;
        }).join('');

        document.getElementById('metricCodeDistribution').innerHTML = `
            <div style="padding:4px 0;">
                <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px;">
                    <span style="font-size:11px;color:#94a3b8;">סה"כ ${totalCodes} אבחונים</span>
                </div>
                <div style="margin-bottom:16px;">
                    <div style="font-size:11px;font-weight:700;color:#0b2e6b;margin-bottom:8px;text-transform:uppercase;letter-spacing:0.5px;">תכונה</div>
                    ${groupedHtml}
                </div>
                <div style="border-top:1px solid #e8ecf4;padding-top:12px;">
                    <div style="font-size:11px;font-weight:700;color:#0b2e6b;margin-bottom:8px;text-transform:uppercase;letter-spacing:0.5px;">אנרגיה</div>
                    ${energyHtml}
                </div>
            </div>
        `;

        // Chart 2: Daily Volume — vertical bar chart
        const dayEntries = Object.entries(dayCounts).sort((a, b) => {
            const da = parseDateDDMMYYYY(a[0]);
            const db = parseDateDDMMYYYY(b[0]);
            return db - da;
        }).slice(0, 10).reverse();
        const maxDayCount = dayEntries.length > 0 ? Math.max(...dayEntries.map(e => e[1])) : 1;

        const barsHtml = dayEntries.map(([date, count]) => {
            const heightPct = Math.max(8, (count / maxDayCount) * 100);
            return `<div style="display:flex;flex-direction:column;align-items:center;gap:4px;flex:1;min-width:0;cursor:pointer;" onclick="filterByDate('${date}')" title="${date}: ${count} אבחונים">
                <span style="font-size:11px;font-weight:700;color:#0b2e6b;">${count}</span>
                <div style="width:100%;max-width:28px;height:${heightPct}px;background:linear-gradient(180deg, #0b2e6b, #4a7ab5);border-radius:4px 4px 0 0;transition:height 0.4s ease;"></div>
                <span style="font-size:10px;color:#64748b;white-space:nowrap;">${date.slice(0, 5)}</span>
            </div>`;
        }).join('');

        const dailyHtml = dayEntries.length > 0 ? `
            <div style="display:flex;align-items:flex-end;gap:4px;height:120px;padding-top:8px;">
                ${barsHtml}
            </div>
        ` : '<div style="color:#94a3b8;font-size:12px;text-align:center;padding:16px;">אין נתונים</div>';
        document.getElementById('metricDailyVolume').innerHTML = dailyHtml;

        // Chart 3: Code Match/Mismatch breakdown
        const matchChartEl = document.getElementById('metricCodeMatchChart');
        if (matchChartEl) {
            if (withBothCodes.length === 0) {
                matchChartEl.innerHTML = '<div style="color:#94a3b8;font-size:12px;text-align:center;padding:16px;">אין נתונים (אין משתמשים עם קוד מאבחן)</div>';
            } else {
                const matchPctVal = Math.round((codeMatch / withBothCodes.length) * 100);
                const mismatchPctVal = 100 - matchPctVal;

                // Show which codes mismatch
                const mismatchDetails = withBothCodes
                    .filter(u => u.pdn_code !== u.diagnose_pdn_code)
                    .map(u => `<div style="display:flex;justify-content:space-between;align-items:center;padding:4px 0;border-bottom:1px solid #f8fafc;">
                        <span style="font-size:11px;color:#64748b;cursor:pointer;" onclick="handleTableSearch(); document.getElementById('tableSearchInput').value='${u.email}'; handleTableSearch();">${u.email.split('@')[0]}</span>
                        <span style="font-size:11px;"><span style="color:#0b2e6b;font-weight:700;">${u.pdn_code}</span> ← <span style="color:#dc2626;font-weight:600;">${u.diagnose_pdn_code}</span></span>
                    </div>`).slice(0, 8).join('');

                matchChartEl.innerHTML = `
                    <div style="display:flex;align-items:center;gap:16px;margin-bottom:16px;">
                        <div style="position:relative;width:80px;height:80px;">
                            <div style="width:80px;height:80px;border-radius:50%;background:conic-gradient(#0b2e6b 0% ${matchPctVal}%, #dc2626 ${matchPctVal}% 100%);"></div>
                            <div style="position:absolute;inset:0;display:flex;align-items:center;justify-content:center;">
                                <div style="width:48px;height:48px;border-radius:50%;background:white;display:flex;align-items:center;justify-content:center;">
                                    <span style="font-size:14px;font-weight:800;color:#0b2e6b;">${matchPctVal}%</span>
                                </div>
                            </div>
                        </div>
                        <div style="flex:1;">
                            <div style="display:flex;align-items:center;gap:6px;margin-bottom:4px;">
                                <span style="width:8px;height:8px;border-radius:2px;background:#0b2e6b;"></span>
                                <span style="font-size:12px;color:#1e293b;font-weight:600;">התאמה: ${codeMatch}</span>
                            </div>
                            <div style="display:flex;align-items:center;gap:6px;">
                                <span style="width:8px;height:8px;border-radius:2px;background:#dc2626;"></span>
                                <span style="font-size:12px;color:#1e293b;font-weight:600;">פער: ${codeMismatch}</span>
                            </div>
                            <div style="font-size:10px;color:#94a3b8;margin-top:4px;">מתוך ${withBothCodes.length} שנבדקו</div>
                        </div>
                    </div>
                    ${codeMismatch > 0 ? `<div style="font-size:11px;font-weight:600;color:#64748b;margin-bottom:6px;">פירוט פערים:</div>${mismatchDetails}` : ''}
                `;
            }
        }
    }

    // Track current metrics filter state + peak day value for filtering
    let metricsFilterPeakDate = null;

    function filterByMetric(metric) {
        const startDate = getDateRangeFilter(currentMetricsRange);
        const inRange = currentData.filter(u => {
            if (!startDate) return true;
            const d = parseDateDDMMYYYY(u.date);
            return d && d >= startDate;
        });

        let filtered = [];
        let label = '';

        switch (metric) {
            case 'completions':
                filtered = inRange.filter(u => u.pdn_code && u.pdn_code !== 'N/A' && u.pdn_code !== '');
                label = 'השלמות';
                break;
            case 'peakDay':
                const dayCounts = {};
                inRange.forEach(u => { if (u.date) dayCounts[u.date] = (dayCounts[u.date] || 0) + 1; });
                const peak = Object.entries(dayCounts).sort((a, b) => b[1] - a[1])[0];
                if (peak) {
                    filtered = inRange.filter(u => u.date === peak[0]);
                    label = 'ביום השיא ' + peak[0];
                }
                break;
            case 'diagnosed':
                filtered = inRange.filter(u => u.diagnose_pdn_code && u.diagnose_pdn_code !== 'N/A' && u.diagnose_pdn_code !== '');
                label = 'נבדקו ע"י מאבחן';
                break;
            case 'not_diagnosed':
                filtered = inRange.filter(u => u.pdn_code && u.pdn_code !== 'N/A' && u.pdn_code !== '' && u.pdn_code !== 'NA' && (!u.diagnose_pdn_code || u.diagnose_pdn_code === '' || u.diagnose_pdn_code === 'N/A'));
                label = 'לא נבדקו ע"י מאבחן';
                break;
            case 'uniqueCodes':
                filtered = inRange.filter(u => u.pdn_code && u.pdn_code !== 'N/A' && u.pdn_code !== '');
                label = 'בעלי קוד PDN';
                break;
            case 'codeMatch':
                filtered = inRange.filter(u =>
                    u.pdn_code && u.pdn_code !== 'N/A' && u.pdn_code !== '' &&
                    u.diagnose_pdn_code && u.diagnose_pdn_code !== 'N/A' && u.diagnose_pdn_code !== '' &&
                    u.pdn_code === u.diagnose_pdn_code
                );
                label = 'התאמה מערכת/מאבחן';
                break;
            case 'codeMismatch':
                filtered = inRange.filter(u =>
                    u.pdn_code && u.pdn_code !== 'N/A' && u.pdn_code !== '' &&
                    u.diagnose_pdn_code && u.diagnose_pdn_code !== 'N/A' && u.diagnose_pdn_code !== '' &&
                    u.pdn_code !== u.diagnose_pdn_code
                );
                label = 'פער קוד מערכת/מאבחן';
                break;
            case 'needsVerification':
                filtered = inRange.filter(u => u.needs_verification === true);
                label = 'נדרש אימות אנושי';
                break;
            case 'today':
                const now = new Date();
                const todayStr = String(now.getDate()).padStart(2, '0') + '/' + String(now.getMonth() + 1).padStart(2, '0') + '/' + now.getFullYear();
                filtered = currentData.filter(u => u.date === todayStr);
                label = 'אובחנו היום';
                break;
            default:
                filtered = inRange;
                label = '';
        }

        renderTable(filtered);
        showFilterBanner(label, filtered.length);
        updateUrlState({ filter: metric, range: currentMetricsRange });

        // Auto-switch to Users tab to show filtered results
        switchTab('users', true);
        // Scroll to table
        document.getElementById('tableBody').scrollIntoView({ behavior: 'smooth', block: 'start' });
        showNotification(`מציג ${filtered.length} רשומות: ${label}`, 'info');
    }

    function filterByCode(code) {
        const startDate = getDateRangeFilter(currentMetricsRange);
        const filtered = currentData.filter(u => {
            if (!startDate) return u.pdn_code === code;
            const d = parseDateDDMMYYYY(u.date);
            return d && d >= startDate && u.pdn_code === code;
        });
        renderTable(filtered);
        showFilterBanner(`קוד ${code}`, filtered.length);
        updateUrlState({ code: code, filter: null, range: currentMetricsRange });
        switchTab('users', true);
        document.getElementById('tableBody').scrollIntoView({ behavior: 'smooth', block: 'start' });
        showNotification(`מציג ${filtered.length} רשומות: קוד ${code}`, 'info');
    }

    function filterByDate(dateStr) {
        const filtered = currentData.filter(u => u.date === dateStr);
        renderTable(filtered);
        showFilterBanner(dateStr, filtered.length);
        switchTab('users', true);
        document.getElementById('tableBody').scrollIntoView({ behavior: 'smooth', block: 'start' });
        showNotification(`מציג ${filtered.length} רשומות: ${dateStr}`, 'info');
    }

    function showFilterBanner(label, count) {
        // Remove existing banner
        const existing = document.getElementById('filterBanner');
        if (existing) existing.remove();

        document.getElementById('rowCount').textContent = `סה"כ שורות: ${count} (${label})`;

        // Add filter banner above the table
        const tableSection = document.getElementById('tableBody').closest('.dash-section');
        const tableContainer = tableSection.querySelector('.table-container');
        if (tableContainer) {
            const banner = document.createElement('div');
            banner.id = 'filterBanner';
            banner.className = 'filter-banner';
            banner.innerHTML = `
                <span><i class="fas fa-filter" style="margin-left:6px;"></i> מסנן פעיל: ${escapeHtml(label)} (${count} תוצאות)</span>
                <button onclick="clearFilter()"><i class="fas fa-times" style="margin-left:4px;"></i> נקה מסנן</button>
            `;
            tableContainer.parentNode.insertBefore(banner, tableContainer);
        }
    }

    function clearFilter() {
        const banner = document.getElementById('filterBanner');
        if (banner) banner.remove();
        renderTable(currentData);
        document.getElementById('rowCount').textContent = `סה"כ שורות: ${currentData.length}`;
        updateUrlState({ filter: null, code: null });
    }

    // ===== Bulk Selection =====
    function getSelectedEmails() {
        return Array.from(document.querySelectorAll('.row-select-cb:checked')).map(cb => cb.dataset.email);
    }

    function updateBulkSelection() {
        const selected = getSelectedEmails();
        const bar = document.getElementById('bulkActionBar');
        const countEl = document.getElementById('bulkSelectedCount');
        const selectAll = document.getElementById('selectAllRows');
        const singleActions = document.getElementById('singleUserActions');

        if (selected.length > 0) {
            bar.style.display = 'flex';
            countEl.textContent = `${selected.length} נבחרו`;
            // Show per-user actions only when exactly 1 is selected
            if (singleActions) {
                singleActions.style.display = selected.length === 1 ? 'contents' : 'none';
            }
        } else {
            bar.style.display = 'none';
        }

        // Update select-all checkbox state
        const allCheckboxes = document.querySelectorAll('.row-select-cb');
        if (selectAll) {
            selectAll.checked = allCheckboxes.length > 0 && selected.length === allCheckboxes.length;
            selectAll.indeterminate = selected.length > 0 && selected.length < allCheckboxes.length;
        }
    }

    function toggleSelectAll(checkbox) {
        document.querySelectorAll('.row-select-cb').forEach(cb => {
            cb.checked = checkbox.checked;
        });
        updateBulkSelection();
    }

    function singleAction(action) {
        const emails = getSelectedEmails();
        if (emails.length !== 1) return;
        const email = emails[0];
        switch (action) {
            case 'journey': viewJourney(email); break;
            case 'questionnaire': viewQuestionnaire(email); break;
            case 'voice': playVoice(email); break;
            case 'diagnose': editDiagnose(email); break;
        }
    }

    function clearSelection() {
        document.querySelectorAll('.row-select-cb').forEach(cb => { cb.checked = false; });
        const selectAll = document.getElementById('selectAllRows');
        if (selectAll) { selectAll.checked = false; selectAll.indeterminate = false; }
        updateBulkSelection();
    }

    async function bulkSendEmail(type) {
        const emails = getSelectedEmails();
        if (emails.length === 0) { showNotification('לא נבחרו משתמשים', 'error'); return; }

        const typeLabel = type === 'pdn' ? 'קוד PDN' : 'הזמנת בינת';
        const password = await requestAdminPassword(`שלח ${typeLabel} ל-${emails.length} משתמשים?`);
        if (!password) return;

        showNotification(`שולח ${typeLabel} ל-${emails.length} משתמשים...`, 'info');
        let success = 0, failed = 0;

        for (const email of emails) {
            try {
                const endpoint = type === 'binat'
                    ? `/pdn-admin/user/send_binat_invite/${email}?session_token=${sessionToken}`
                    : `/pdn-admin/user/send_email/${email}?session_token=${sessionToken}`;
                const response = await fetch(endpoint, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ type, password })
                });
                if (response.ok) success++;
                else failed++;
            } catch (e) { failed++; }
        }

        clearSelection();
        showNotification(`${typeLabel}: ${success} הצליחו, ${failed} נכשלו`, success > 0 ? 'success' : 'error');
    }

    async function bulkRecalculate() {
        const emails = getSelectedEmails();
        if (emails.length === 0) { showNotification('לא נבחרו משתמשים', 'error'); return; }

        if (!confirm(`חשב מחדש קוד PDN ל-${emails.length} משתמשים?`)) return;

        showNotification(`מחשב מחדש ל-${emails.length} משתמשים...`, 'info');
        let success = 0, failed = 0;

        for (const email of emails) {
            try {
                const response = await fetch(`/pdn-admin/user/recalculate_pdn/${email}?session_token=${sessionToken}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({})
                });
                if (response.ok) {
                    const data = await response.json();
                    const idx = currentData.findIndex(u => u.email === email);
                    const previousCode = idx !== -1 ? currentData[idx].pdn_code : '';
                    if (idx !== -1) {
                        currentData[idx].pdn_code = data.pdn_code;
                        currentData[idx].needs_verification = data.needs_verification || false;
                        if (data.confidence_score !== undefined) currentData[idx].confidence_score = data.confidence_score;
                    }
                    // Show calculation details for single user recalculation
                    if (emails.length === 1 && data.calculation_details) {
                        showCalculationDetails(email, data, previousCode);
                    }
                    success++;
                } else failed++;
            } catch (e) { failed++; }
        }

        clearSelection();
        renderTable(currentData);
        updateMetrics();
        showNotification(`חישוב מחדש: ${success} הצליחו, ${failed} נכשלו`, success > 0 ? 'success' : 'error');
    }

    function bulkExportSelected() {
        const emails = getSelectedEmails();
        if (emails.length === 0) { showNotification('לא נבחרו משתמשים', 'error'); return; }

        const exportData = currentData.filter(u => emails.includes(u.email));
        const headers = ['מזהה מערכת', 'שם', 'אימייל', 'תאריך', 'קוד מערכת', 'אימות', 'ניתוח קול', 'קוד מאבחן', 'הערות', 'עדכון קוד פדן', 'קופון'];
        const rows = exportData.map(u => [
            u.user_id || '', ((u.first_name || '') + ' ' + (u.last_name || '')).trim(),
            u.email, u.date, u.pdn_code || '',
            u.needs_verification ? 'נדרש אימות' : 'תקין',
            u.pdn_voice_code || '',
            u.diagnose_pdn_code || '', u.diagnose_comments || '', u.pdn_update_comments || '',
            u.coupon_code || ''
        ]);

        const bom = '\uFEFF';
        const csvContent = bom + [headers.join(','), ...rows.map(r => r.map(c => `"${(c || '').replace(/"/g, '""')}"`).join(','))].join('\n');
        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `pdn_selected_${emails.length}_${new Date().toISOString().slice(0,10)}.csv`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);

        showNotification(`ייצוא ${emails.length} רשומות הושלם`, 'success');
    }

    function showVerificationPopup(email, pdnCode) {
        // Find user data to get stage_e_override info
        const user = currentData.find(u => u.email === email);
        const stageEOverride = user && user.stage_e_override;
        const dominantBefore = user && user.dominant_before_stage_e;
        const trait = pdnCode ? pdnCode.charAt(0) : '?';

        // Create a modal popup with verification details
        const existing = document.getElementById('verificationPopup');
        if (existing) existing.remove();

        const overrideHtml = stageEOverride && dominantBefore ? `
            <div style="background:#fee2e2;border:1px solid #fca5a5;border-radius:8px;padding:10px;margin-top:10px;text-align:right;">
                <p style="font-size:13px;color:#991b1b;font-weight:600;">
                    <i class="fas fa-exchange-alt"></i>
                    שלב E שינה דומיננטית: ${dominantBefore} → ${trait} — נדרש אימות
                </p>
            </div>
        ` : '';

        const overlay = document.createElement('div');
        overlay.id = 'verificationPopup';
        overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.5);backdrop-filter:blur(4px);z-index:9999;display:flex;align-items:center;justify-content:center;padding:16px;';
        overlay.onclick = (e) => { if (e.target === overlay) overlay.remove(); };

        overlay.innerHTML = `
            <div style="background:white;border-radius:16px;padding:28px;max-width:420px;width:100%;box-shadow:0 24px 48px rgba(0,0,0,0.2);text-align:center;direction:rtl;">
                <div style="font-size:2.5rem;margin-bottom:12px;">⚠️</div>
                <h3 style="font-size:1.1rem;font-weight:700;color:#991b1b;margin-bottom:16px;">נדרש אימות אנושי</h3>
                <div style="background:#fef3c7;border:1px solid #f59e0b;border-radius:10px;padding:14px;margin-bottom:16px;text-align:right;">
                    <p style="font-size:14px;color:#92400e;font-weight:600;margin-bottom:8px;">קוד: <span style="font-size:18px;color:#991b1b;">${pdnCode}</span></p>
                    <p style="font-size:13px;color:#92400e;line-height:1.7;">פער ניקוד קטן מ-2 נקודות בין התכונות הדומיננטיות.</p>
                    <p style="font-size:13px;color:#92400e;line-height:1.7;">יש לבדוק את ההקלטות הקוליות ולאמת את הקוד ידנית.</p>
                    ${overrideHtml}
                </div>
                <div style="display:flex;gap:8px;justify-content:center;">
                    <button onclick="recalculatePdnCode('${email}'); document.getElementById('verificationPopup').remove();" style="padding:10px 20px;background:#0b2e6b;color:white;border:none;border-radius:8px;font-size:13px;font-weight:600;cursor:pointer;">
                        <i class="fas fa-calculator"></i> חשב מחדש
                    </button>
                    <button onclick="document.getElementById('verificationPopup').remove();" style="padding:10px 20px;background:#f1f5f9;color:#475569;border:1px solid #e2e8f0;border-radius:8px;font-size:13px;font-weight:600;cursor:pointer;">
                        סגור
                    </button>
                </div>
            </div>
        `;

        document.body.appendChild(overlay);
    }

    function showConfidencePopup(email, score, needsVerification, missingStageE) {
        const user = currentData.find(u => u.email === email);
        const pdnCode = user ? user.pdn_code : '?';
        const name = user ? ((user.first_name || '') + ' ' + (user.last_name || '')).trim() || email : email;
        const diagnoseCode = user ? user.diagnose_pdn_code : '';

        const existing = document.getElementById('confidencePopup');
        if (existing) existing.remove();

        // Determine confidence level and explanation
        let levelText, levelColor, levelBg, explanation;
        if (score >= 50) {
            levelText = 'ביטחון גבוה';
            levelColor = '#166534';
            levelBg = '#dcfce7';
            explanation = 'פער גדול בין התכונה והאנרגיה הדומיננטיות לשאר. התוצאה אמינה מאוד.';
        } else if (score >= 10) {
            levelText = 'ביטחון בינוני';
            levelColor = '#475569';
            levelBg = '#f1f5f9';
            explanation = 'יש פער סביר בין הניקוד המוביל לשאר. התוצאה סבירה אבל כדאי לוודא.';
        } else {
            levelText = 'ביטחון נמוך מאוד';
            levelColor = '#991b1b';
            levelBg = '#fee2e2';
            explanation = 'הניקוד כמעט שווה. שקול שיחה אישית.';
        }

        // Build flags section
        let flagsHtml = '';
        if (needsVerification || missingStageE || (user && user.stage_e_override)) {
            const flags = [];
            if (missingStageE) flags.push('<span style="background:#fee2e2;color:#991b1b;padding:3px 8px;border-radius:6px;font-size:11px;">חלק 5 חסר</span>');
            if (user && user.stage_e_override) flags.push('<span style="background:#fef3c7;color:#92400e;padding:3px 8px;border-radius:6px;font-size:11px;">שלב 5 שינה תוצאה</span>');
            if (needsVerification && !missingStageE) flags.push('<span style="background:#ffedd5;color:#c2410c;padding:3px 8px;border-radius:6px;font-size:11px;">ניקוד קרוב</span>');
            flagsHtml = `<div style="display:flex;gap:6px;flex-wrap:wrap;justify-content:center;margin-top:10px;">${flags.join('')}</div>`;
        }

        // Diagnose comparison
        let diagnoseHtml = '';
        if (diagnoseCode && diagnoseCode !== pdnCode) {
            diagnoseHtml = `<div style="background:#fef3c7;border:1px solid #f59e0b;border-radius:8px;padding:8px;margin-top:10px;text-align:center;font-size:12px;color:#92400e;">
                <b>פער מאבחן:</b> מערכת ${pdnCode} / מאבחן ${diagnoseCode}
            </div>`;
        } else if (diagnoseCode) {
            diagnoseHtml = `<div style="background:#dcfce7;border-radius:8px;padding:8px;margin-top:10px;text-align:center;font-size:12px;color:#166534;">
                <b>מאבחן אישר:</b> ${diagnoseCode}
            </div>`;
        }

        const overlay = document.createElement('div');
        overlay.id = 'confidencePopup';
        overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.5);backdrop-filter:blur(4px);z-index:9999;display:flex;align-items:center;justify-content:center;padding:16px;';
        overlay.onclick = (e) => { if (e.target === overlay) overlay.remove(); };

        overlay.innerHTML = `
            <div style="background:white;border-radius:16px;padding:24px;max-width:420px;width:100%;box-shadow:0 24px 48px rgba(0,0,0,0.2);direction:rtl;">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px;">
                    <div>
                        <div style="font-size:0.9rem;font-weight:700;color:#1e293b;">${escapeHtml(name)}</div>
                        <div style="font-size:0.75rem;color:#64748b;">${escapeHtml(email)}</div>
                    </div>
                    <div style="text-align:center;">
                        <div style="font-size:1.8rem;font-weight:800;color:${levelColor};">${score}%</div>
                    </div>
                </div>
                <div style="display:flex;gap:8px;margin-bottom:12px;">
                    <span style="padding:4px 12px;border-radius:8px;font-size:13px;font-weight:700;background:#e0e7ff;color:#3730a3;">קוד: ${escapeHtml(pdnCode)}</span>
                    <span style="padding:4px 12px;border-radius:8px;font-size:13px;font-weight:500;background:#f1f5f9;color:#64748b;">תכונה: ${pdnCode ? pdnCode[0] : '?'} | אנרגיה: ${pdnCode && pdnCode.length > 1 ? ({'3':'F','6':'F','9':'F','12':'F','7':'D','4':'D','10':'D','1':'D','11':'S','8':'S','2':'S','5':'S'}[pdnCode.slice(1)] || '?') : '?'}</span>
                </div>

                <div id="confidenceScoresArea" style="background:#f8fafc;border-radius:10px;padding:12px;text-align:right;margin-bottom:10px;">
                    <p style="font-size:11px;color:#94a3b8;text-align:center;"><i class="fas fa-spinner fa-spin"></i> טוען ניקוד...</p>
                </div>
                <div id="confidenceVoiceArea" style="margin-bottom:10px;"></div>
                ${flagsHtml}
                ${diagnoseHtml}
                <div style="display:flex;gap:8px;justify-content:center;margin-top:14px;">
                    <button onclick="document.getElementById('confidencePopup').remove(); recalculatePdnCode('${escapeHtml(email)}');" style="padding:8px 20px;background:#0b2e6b;color:white;border:none;border-radius:8px;font-size:12px;font-weight:600;cursor:pointer;">
                        <i class="fas fa-list-ol"></i> פירוט מלא
                    </button>
                    <button onclick="document.getElementById('confidencePopup').remove();" style="padding:8px 20px;background:#f1f5f9;color:#475569;border:1px solid #e2e8f0;border-radius:8px;font-size:12px;font-weight:600;cursor:pointer;">
                        סגור
                    </button>
                </div>
            </div>
        `;

        document.body.appendChild(overlay);

        // Fetch actual scores from recalculate endpoint
        fetch(`/pdn-admin/user/recalculate_pdn/${email}?session_token=${sessionToken}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({})
        }).then(r => r.json()).then(data => {
            const area = document.getElementById('confidenceScoresArea');
            if (!area) return;
            if (data.calculation_details) {
                const final = data.calculation_details.find(d => d.stage === 'Final');
                const stageD = data.calculation_details.find(d => d.stage === 'D');
                const stageE = data.calculation_details.find(d => d.stage === 'E');
                if (final && final.scores) {
                    const s = final.scores;
                    const traits = [['A', s.A], ['T', s.T], ['P', s.P], ['E', s.E]].sort((a,b) => b[1] - a[1]);
                    const energies = [['D', s.D], ['S', s.S], ['F', s.F]].sort((a,b) => b[1] - a[1]);
                    const traitGap = traits[0][1] - traits[1][1];
                    const energyGap = energies[0][1] - energies[1][1];
                    area.innerHTML = `
                        <div style="font-size:11px;font-weight:600;color:#475569;margin-bottom:8px;">ניקוד סופי (אחרי כל השלבים):</div>
                        <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;">
                            <div style="background:white;border-radius:8px;padding:8px;border:1px solid #e2e8f0;">
                                <div style="font-size:10px;color:#94a3b8;margin-bottom:4px;">תכונות</div>
                                ${traits.map((t,i) => `<div style="display:flex;justify-content:space-between;font-size:12px;${i===0?'font-weight:700;color:#0b2e6b;':'color:#64748b;'}"><span>${t[0]}</span><span>${t[1]}</span></div>`).join('')}
                                <div style="margin-top:4px;font-size:10px;color:#94a3b8;">פער: ${traitGap} נק'</div>
                            </div>
                            <div style="background:white;border-radius:8px;padding:8px;border:1px solid #e2e8f0;">
                                <div style="font-size:10px;color:#94a3b8;margin-bottom:4px;">אנרגיה</div>
                                ${energies.map((e,i) => `<div style="display:flex;justify-content:space-between;font-size:12px;${i===0?'font-weight:700;color:#0b2e6b;':'color:#64748b;'}"><span>${e[0]}</span><span>${e[1]}</span></div>`).join('')}
                                <div style="margin-top:4px;font-size:10px;color:#94a3b8;">פער: ${energyGap} נק'</div>
                            </div>
                        </div>
                    `;
                }
            } else {
                area.innerHTML = '<p style="font-size:11px;color:#94a3b8;text-align:center;">לא ניתן לטעון ניקוד</p>';
            }
            // Auto-load voice snippet player
            loadVoiceSnippet(email);
        }).catch(() => {
            const area = document.getElementById('confidenceScoresArea');
            if (area) area.innerHTML = '<p style="font-size:11px;color:#94a3b8;text-align:center;">שגיאה בטעינת ניקוד</p>';
        });
    }

    // Load voice snippet into the confidence popup
    function loadVoiceSnippet(email) {
        const voiceArea = document.getElementById('confidenceVoiceArea');
        if (!voiceArea) return;
        fetch(`/pdn-admin/user/voice/${email}?session_token=${sessionToken}`)
            .then(r => { if (!r.ok) throw new Error(); return r.json(); })
            .then(data => {
                if (data && data.voice_recordings && Object.keys(data.voice_recordings).length > 0) {
                    const recordings = data.voice_recordings;
                    const firstKey = Object.keys(recordings)[0];
                    const firstFile = recordings[firstKey];
                    let audioPath = firstFile.path || firstFile.filename || firstFile;
                    if (typeof audioPath !== 'string') return;
                    if (audioPath.startsWith('saved_results/')) audioPath = audioPath.substring('saved_results/'.length);
                    const audioUrl = `/pdn-admin/audio/${audioPath}?session_token=${sessionToken}`;
                    voiceArea.innerHTML = `
                        <div style="background:#f0f9ff;border:1px solid #bae6fd;border-radius:8px;padding:8px 12px;">
                            <div style="font-size:10px;color:#0369a1;font-weight:600;margin-bottom:4px;"><i class="fas fa-volume-up"></i> הקלטה קולית</div>
                            <audio controls preload="auto" style="width:100%;height:28px;" src="${audioUrl}"></audio>
                        </div>
                    `;
                }
            })
            .catch(() => { /* No voice - leave empty */ });
    }

    function showCommentsPopup(email) {
        const user = currentData.find(u => u.email === email);
        if (!user) return;

        const comments = user.diagnose_comments || '';
        const name = ((user.first_name || '') + ' ' + (user.last_name || '')).trim() || email;
        const pdnCode = user.pdn_code || '—';
        const diagnoseCode = user.diagnose_pdn_code || '—';

        const existing = document.getElementById('commentsPopup');
        if (existing) existing.remove();

        const overlay = document.createElement('div');
        overlay.id = 'commentsPopup';
        overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.5);backdrop-filter:blur(4px);z-index:9999;display:flex;align-items:center;justify-content:center;padding:16px;';
        overlay.onclick = (e) => { if (e.target === overlay) overlay.remove(); };

        overlay.innerHTML = `
            <div style="background:white;border-radius:16px;padding:28px;max-width:480px;width:100%;box-shadow:0 24px 48px rgba(0,0,0,0.2);direction:rtl;">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
                    <h3 style="font-size:1rem;font-weight:700;color:#1e293b;">${escapeHtml(name)}</h3>
                    <div style="display:flex;gap:8px;">
                        <span style="padding:3px 10px;border-radius:6px;font-size:12px;font-weight:600;background:#e0e7ff;color:#3730a3;">מערכת: ${escapeHtml(pdnCode)}</span>
                        ${diagnoseCode !== '—' ? `<span style="padding:3px 10px;border-radius:6px;font-size:12px;font-weight:600;background:#dcfce7;color:#166534;">מאבחן: ${escapeHtml(diagnoseCode)}</span>` : ''}
                    </div>
                </div>
                <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:16px;min-height:60px;text-align:right;">
                    <p style="font-size:14px;color:#334155;line-height:1.8;white-space:pre-wrap;">${comments ? escapeHtml(comments) : '<span style="color:#94a3b8;font-style:italic;">אין הערות</span>'}</p>
                </div>
                <div style="text-align:center;margin-top:16px;">
                    <button onclick="document.getElementById('commentsPopup').remove();" style="padding:10px 24px;background:#f1f5f9;color:#475569;border:1px solid #e2e8f0;border-radius:8px;font-size:13px;font-weight:600;cursor:pointer;">
                        סגור
                    </button>
                </div>
            </div>
        `;

        document.body.appendChild(overlay);
    }

    function handleTableSearch() {
        const term = (document.getElementById('tableSearchInput').value || '').trim().toLowerCase();
        if (!term) {
            // Remove filter banner when clearing search
            const banner = document.getElementById('filterBanner');
            if (banner) banner.remove();
            renderTable(currentData);
            document.getElementById('rowCount').textContent = `סה"כ שורות: ${currentData.length}`;
            return;
        }
        const filtered = currentData.filter(u => {
            const name = ((u.first_name || '') + ' ' + (u.last_name || '')).toLowerCase();
            const email = (u.email || '').toLowerCase();
            return name.includes(term) || email.includes(term);
        });
        renderTable(filtered);
        document.getElementById('rowCount').textContent = `סה"כ שורות: ${filtered.length} (חיפוש: "${term}")`;
    }

    // --- Quick Filter Dropdowns ---
    function quickTagFilter(value, type) {
        const timeEl = document.getElementById('quickFilterTime');
        const statusEl = document.getElementById('quickFilterStatus');
        const traitEl = document.getElementById('quickFilterTrait');
        const energyEl = document.getElementById('quickFilterEnergy');
        const couponEl = document.getElementById('quickFilterCoupon');

        // Time filter can combine with others; trait/energy/status are mutually exclusive
        if (type === 'time') {
            // Time doesn't clear others — it combines
        } else if (type === 'status') {
            traitEl.value = '';
            energyEl.value = '';
        } else if (type === 'trait') {
            statusEl.value = '';
            energyEl.value = '';
        } else if (type === 'energy') {
            statusEl.value = '';
            traitEl.value = '';
        } else if (type === 'coupon') {
            // Coupon combines with time but not others
        }

        // Update active states
        timeEl.classList.toggle('active-filter', !!timeEl.value);
        statusEl.classList.toggle('active-filter', !!statusEl.value);
        traitEl.classList.toggle('active-filter', !!traitEl.value);
        energyEl.classList.toggle('active-filter', !!energyEl.value);
        if (couponEl) couponEl.classList.toggle('active-filter', !!couponEl.value);

        // Show/hide clear button
        const clearBtn = document.getElementById('clearFiltersBtn');
        // Always visible — no toggle needed

        // Apply combined filters
        applyFilters();
    }

    function applyFilters() {
        const timeEl = document.getElementById('quickFilterTime');
        const statusEl = document.getElementById('quickFilterStatus');
        const traitEl = document.getElementById('quickFilterTrait');
        const energyEl = document.getElementById('quickFilterEnergy');
        const couponEl = document.getElementById('quickFilterCoupon');

        const timeVal = timeEl.value;
        const statusVal = statusEl.value;
        const traitVal = traitEl.value;
        const energyVal = energyEl.value;
        const couponVal = couponEl ? couponEl.value : '';

        // If nothing selected, show all
        if (!timeVal && !statusVal && !traitVal && !energyVal && !couponVal) {
            renderTable(currentData);
            document.getElementById('rowCount').textContent = `סה"כ שורות: ${currentData.length}`;
            const banner = document.getElementById('filterBanner');
            if (banner) banner.remove();
            return;
        }

        let filtered = currentData;
        let labels = [];

        // Time filter
        if (timeVal) {
            const now = new Date();
            let cutoff;
            if (timeVal === 'day') {
                cutoff = new Date(now.getTime() - 24 * 60 * 60 * 1000);
                labels.push('יום אחרון');
            } else if (timeVal === 'week') {
                cutoff = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
                labels.push('שבוע');
            } else if (timeVal === 'month') {
                cutoff = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);
                labels.push('חודש');
            }
            if (cutoff) {
                filtered = filtered.filter(u => {
                    const d = parseDate(u.date);
                    return d && d >= cutoff;
                });
            }
        }

        // Status filter
        if (statusVal === 'valid') {
            filtered = filtered.filter(u => !u.needs_verification && u.pdn_code && u.pdn_code !== '' && u.pdn_code !== 'NA');
            labels.push('תקין');
        } else if (statusVal === 'needs_verification') {
            filtered = filtered.filter(u => u.needs_verification || !u.pdn_code || u.pdn_code === '' || u.pdn_code === 'NA');
            labels.push('לבדיקה');
        } else if (statusVal === 'diagnosed') {
            filtered = filtered.filter(u => u.diagnose_pdn_code && u.diagnose_pdn_code.length > 0);
            labels.push('נבדק ע"י מאבחן');
        } else if (statusVal === 'not_diagnosed') {
            filtered = filtered.filter(u => u.pdn_code && u.pdn_code !== 'N/A' && u.pdn_code !== '' && u.pdn_code !== 'NA' && (!u.diagnose_pdn_code || u.diagnose_pdn_code === '' || u.diagnose_pdn_code === 'N/A'));
            labels.push('לא נבדק ע"י מאבחן');
        }

        // Trait filter
        if (traitVal && ['A', 'T', 'P', 'E'].includes(traitVal)) {
            filtered = filtered.filter(u => u.pdn_code && u.pdn_code.toUpperCase().startsWith(traitVal));
            labels.push(`תכונה ${traitVal}`);
        }

        // Energy filter
        if (energyVal && ['D', 'S', 'F'].includes(energyVal)) {
            const energyMap = { 'D': [7,4,10,1], 'S': [11,8,2,5], 'F': [3,12,6,9] };
            const codes = energyMap[energyVal] || [];
            filtered = filtered.filter(u => {
                if (!u.pdn_code) return false;
                const num = parseInt(u.pdn_code.replace(/[^0-9]/g, ''));
                return codes.includes(num);
            });
            labels.push(`אנרגיה ${energyVal}`);
        }

        // Coupon filter
        if (couponVal) {
            filtered = filtered.filter(u => {
                const userCoupon = (u.coupon_code || '').toUpperCase();
                return userCoupon === couponVal.toUpperCase();
            });
            labels.push(`קופון ${couponVal}`);
        }

        const label = labels.join(' + ');
        renderTable(filtered);
        showFilterBanner(label, filtered.length);
        document.getElementById('rowCount').textContent = `סה"כ שורות: ${filtered.length} (${label})`;
        showNotification(`מציג ${filtered.length} רשומות: ${label}`, 'info');
    }

    function clearAllFilters() {
        resetFilterDropdowns();
        document.getElementById('tableSearchInput').value = '';
        renderTable(currentData);
        document.getElementById('rowCount').textContent = `סה"כ שורות: ${currentData.length}`;
        const banner = document.getElementById('filterBanner');
        if (banner) banner.remove();
        updateUrlState({ code: null, filter: null });
    }

    function resetFilterDropdowns() {
        const ids = ['quickFilterTime', 'quickFilterStatus', 'quickFilterTrait', 'quickFilterEnergy', 'quickFilterCoupon'];
        ids.forEach(id => {
            const el = document.getElementById(id);
            if (el) {
                el.value = '';
                el.classList.remove('active-filter');
            }
        });
    }

    let _sortByPriority = true;
    function toggleSortMode() {
        _sortByPriority = !_sortByPriority;
        const btn = document.getElementById('sortModeBtn');
        if (_sortByPriority) {
            currentData.sort((a, b) => {
                if (a._priority !== b._priority) return a._priority - b._priority;
                return parseDate(b.date) - parseDate(a.date);
            });
            btn.innerHTML = '<i class="fas fa-sort-amount-down"></i> דחיפות';
            btn.classList.add('active-filter');
        } else {
            currentData.sort((a, b) => parseDate(b.date) - parseDate(a.date));
            btn.innerHTML = '<i class="fas fa-calendar-alt"></i> תאריך';
            btn.classList.remove('active-filter');
        }
        renderTable(currentData);
        showNotification(_sortByPriority ? 'מיון לפי דחיפות' : 'מיון לפי תאריך', 'info');
    }

    function toggleSecondaryColumns() {
        const table = document.getElementById('usersTable');
        const btn = document.getElementById('toggleColsBtn');
        table.classList.toggle('cols-hidden');
        const isHidden = table.classList.contains('cols-hidden');
        btn.innerHTML = isHidden
            ? '<i class="fas fa-columns"></i> עמודות'
            : '<i class="fas fa-columns"></i> פחות';
    }

    async function showActiveUsers() {
        if (!sessionToken) return;
        try {
            const response = await fetch(`/pdn-admin/logged-in-users?session_token=${sessionToken}`);
            if (!response.ok) {
                showNotification('לא ניתן לטעון משתמשים מחוברים', 'error');
                return;
            }
            const data = await response.json();
            const users = data.users || [];

            if (users.length === 0) {
                showNotification('אין משתמשים מחוברים כרגע', 'info');
                return;
            }

            // Show in the loggedInUsersModal
            const content = document.getElementById('loggedInUsersContent');
            if (content) {
                content.innerHTML = users.map(u => `
                    <div style="display:flex;justify-content:space-between;align-items:center;padding:10px 0;border-bottom:1px solid #f1f5f9;">
                        <div>
                            <span style="font-weight:600;color:#1e293b;">${u.email || 'unknown'}</span>
                            <span style="font-size:11px;color:#94a3b8;margin-right:8px;">${u.type || ''}</span>
                        </div>
                        <span style="font-size:11px;color:#64748b;">${u.login_time || ''}</span>
                    </div>
                `).join('');
                document.getElementById('loggedInUsersModal').style.display = 'flex';
            } else {
                // Fallback: show as notification
                const names = users.map(u => u.email || 'unknown').join(', ');
                showNotification(`מחוברים (${users.length}): ${names}`, 'info');
            }
        } catch (error) {
            showNotification('שגיאה בטעינת משתמשים מחוברים', 'error');
        }
    }

    async function bulkRecalculateVerification() {
        const usersNeedingVerification = currentData.filter(u => u.needs_verification === true);
        if (usersNeedingVerification.length === 0) {
            showNotification('אין משתמשים הדורשים אימות', 'info');
            return;
        }

        if (!confirm(`חשב מחדש ${usersNeedingVerification.length} משתמשים הדורשים אימות?`)) return;

        showNotification(`מתחיל חישוב מחדש ל-${usersNeedingVerification.length} משתמשים...`, 'info');

        let success = 0;
        let failed = 0;

        for (const user of usersNeedingVerification) {
            try {
                const response = await fetch(`/pdn-admin/user/recalculate_pdn/${user.email}?session_token=${sessionToken}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({})
                });

                if (response.ok) {
                    const data = await response.json();
                    // Update local data
                    const idx = currentData.findIndex(u => u.email === user.email);
                    if (idx !== -1) {
                        currentData[idx].pdn_code = data.pdn_code;
                        currentData[idx].needs_verification = data.needs_verification || false;
                        if (data.confidence_score !== undefined) {
                            currentData[idx].confidence_score = data.confidence_score;
                        }
                    }
                    success++;
                } else if (response.status === 401) {
                    redirectToLogin();
                    return;
                } else {
                    failed++;
                }
            } catch (error) {
                failed++;
            }
        }

        // Refresh display
        renderTable(currentData);
        updateMetrics();
        showNotification(`חישוב מחדש הושלם: ${success} הצליחו, ${failed} נכשלו`, success > 0 ? 'success' : 'error');
    }

    function renderTable(data) {
        const tbody = document.getElementById('tableBody');
        tbody.innerHTML = '';

        // Update row count
        document.getElementById('rowCount').textContent = `סה"כ שורות: ${data.length}`;

        if (data.length === 0) {
            tbody.innerHTML = `<tr><td colspan="13" class="text-center py-12 text-gray-500">
                <i class="fas fa-inbox text-4xl mb-3 block"></i>
                <p class="text-lg">לא נמצאו נתונים</p>
            </td></tr>`;
            return;
        }

        data.forEach(user => {
            const row = document.createElement('tr');

            // Add red background class if codes are different
            if (isRedUser(user)) {
                row.classList.add('highlight-difference');
            }

            const displayName = ((user.first_name || '') + ' ' + (user.last_name || '')).trim();

            row.innerHTML = `
            <td class="px-2 py-4 text-center">
                <input type="checkbox" class="row-select-cb" data-email="${escapeHtml(user.email)}" onchange="updateBulkSelection()"
                       style="width:16px;height:16px;cursor:pointer;accent-color:#0b2e6b;">
            </td>
            <td class="px-4 py-4 col-secondary">
                <span class="px-2 py-1 bg-gray-100 text-gray-800 rounded-full text-xs font-medium font-mono">${user.user_id || '—'}</span>
            </td>
            <td class="px-4 py-4 font-medium text-gray-900">${escapeHtml(displayName) || '—'}</td>
            <td class="px-4 py-4 font-medium text-gray-900">
                <span class="cursor-pointer hover:text-blue-700 transition-colors" onclick="event.stopPropagation(); navigator.clipboard.writeText('${escapeHtml(user.email)}').then(() => showNotification('אימייל הועתק', 'success'))" title="לחץ להעתקה">
                    ${escapeHtml(user.email)} <i class="fas fa-copy text-gray-300 text-xs mr-1"></i>
                </span>
            </td>
            <td class="px-4 py-4 text-gray-700">${escapeHtml(user.date) || '—'}</td>
            <td class="px-4 py-4">
                <span class="pdn-code-cell px-3 py-1 rounded-full text-sm ${getPdnBadgeColor(user.pdn_code)}">${escapeHtml(user.pdn_code) || '—'}</span>
            </td>
            <td class="px-4 py-4">
                ${user.confidence_score !== undefined && user.confidence_score !== null ?
                    ((user.needs_verification || user.stage_e_override) ?
                        `<span class="cursor-pointer" onclick="event.stopPropagation(); showConfidencePopup('${escapeHtml(user.email)}', ${user.confidence_score}, ${user.needs_verification || false}, ${user.missing_stage_e || false})" title="לחץ לפרטים" style="display:inline-flex;align-items:center;gap:4px;padding:2px 8px;border-radius:8px;background:#fef3c7;color:#92400e;font-size:11px;font-weight:600;">
                            <span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:#f59e0b;"></span> לבדיקה
                        </span>` :
                        `<span class="verification-badge verified cursor-pointer" onclick="event.stopPropagation(); showConfidencePopup('${escapeHtml(user.email)}', ${user.confidence_score}, ${user.needs_verification || false}, ${user.missing_stage_e || false})" title="לחץ לפרטים"><i class="fas fa-check-circle"></i> תקין</span>`
                    ) :
                    (user.needs_verification ?
                        `<span class="verification-badge needs-review" onclick="event.stopPropagation(); showVerificationPopup('${escapeHtml(user.email)}', '${escapeHtml(user.pdn_code)}')" title="לחץ לפרטים" style="cursor:pointer;"><i class="fas fa-exclamation-triangle"></i> אימות</span>` :
                        '<span class="verification-badge verified"><i class="fas fa-check-circle"></i> תקין</span>')
                }
            </td>
            <td class="px-4 py-4">
                <span class="px-2 py-1 rounded-full text-xs font-medium ${getPdnBadgeColor(user.diagnose_pdn_code)}">${escapeHtml(user.diagnose_pdn_code) || '—'}</span>
            </td>
            <td class="px-4 py-4 text-gray-700 max-w-xs truncate cursor-pointer" title="${escapeHtml(user.diagnose_comments || '')}" onclick="event.stopPropagation(); showCommentsPopup('${escapeHtml(user.email)}')">${escapeHtml(user.diagnose_comments || '') || '—'}</td>
            <td class="px-4 py-4 text-gray-700 max-w-xs truncate col-secondary" title="${user.pdn_update_comments || ''}">${user.pdn_update_comments || '—'}</td>
            <td class="px-4 py-4 text-gray-700">
                ${user.coupon_code ? `<span class="text-xs font-mono text-gray-600">${escapeHtml(user.coupon_code)}</span>` : '—'}
            </td>
        `;

            // Add inline recommendation row if the user needs attention
            if (user._recommendation) {
                const recColor = user._priorityLabel === 'red' ? '#1e293b' : user._priorityLabel === 'yellow' ? '#92400e' : '#64748b';
                const recBg = user._priorityLabel === 'red' ? '#f8fafc' : user._priorityLabel === 'yellow' ? '#fffbeb' : '#f8fafc';
                const stageEInfo = (user.stage_e_override && user.dominant_before_stage_e)
                    ? ` | לפני שלב 5: ${user.dominant_before_stage_e} → אחרי: ${user.pdn_code || ''}`
                    : '';
                const voiceBtn = `<span class="cursor-pointer" onclick="event.stopPropagation(); playVoice('${escapeHtml(user.email)}')" style="margin-left:12px;color:#0b2e6b;font-size:13px;" title="האזן להקלטה"><i class="fas fa-headphones"></i></span>`;
                const recRow = document.createElement('tr');
                recRow.style.cssText = 'border-bottom:2px solid #e2e8f0;';
                recRow.innerHTML = `<td colspan="13" style="padding:4px 16px 8px;background:${recBg};font-size:11px;color:${recColor};">
                    ${voiceBtn}<span>${user._recommendation}${stageEInfo}</span>
                </td>`;
                tbody.appendChild(row);
                tbody.appendChild(recRow);
            } else {
                tbody.appendChild(row);
            }
        });

        // Initialize tooltips after rendering
        initializeTooltips();
    }

    function initializeTooltips() {
        // Remove any existing tooltip elements
        const existingTooltips = document.querySelectorAll('.custom-tooltip');
        existingTooltips.forEach(tooltip => tooltip.remove());

        // Add event listeners to all tooltip elements
        const tooltipElements = document.querySelectorAll('[data-tooltip]');
        tooltipElements.forEach(element => {
            element.addEventListener('mouseenter', showCustomTooltip);
            element.addEventListener('mouseleave', hideCustomTooltip);
        });
    }

    function showCustomTooltip(event) {
        const element = event.target;
        const tooltipText = element.getAttribute('data-tooltip');

        if (!tooltipText) return;

        // Create tooltip element
        const tooltip = document.createElement('div');
        tooltip.className = 'custom-tooltip';
        tooltip.textContent = tooltipText;
        tooltip.style.cssText = `
        position: absolute;
        background: rgba(0, 0, 0, 0.9);
        color: white;
        padding: 6px 10px;
        border-radius: 6px;
        font-size: 12px;
        white-space: nowrap;
        z-index: 99999;
        pointer-events: none;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
        opacity: 0;
        transition: opacity 0.3s ease;
    `;

        document.body.appendChild(tooltip);

        // Position tooltip
        const rect = element.getBoundingClientRect();
        tooltip.style.left = rect.left + (rect.width / 2) - (tooltip.offsetWidth / 2) + 'px';
        tooltip.style.top = rect.top - tooltip.offsetHeight - 8 + 'px';

        // Show tooltip
        setTimeout(() => {
            tooltip.style.opacity = '1';
        }, 10);
    }

    function hideCustomTooltip(event) {
        const tooltips = document.querySelectorAll('.custom-tooltip');
        tooltips.forEach(tooltip => {
            tooltip.style.opacity = '0';
            setTimeout(() => {
                if (tooltip.parentElement) {
                    tooltip.remove();
                }
            }, 300);
        });
    }

    function handleSearch(e) {
        applyChatUserFilters();
    }

    function handleFilter(e) {
        applyChatUserFilters();
    }

    function applyChatUserFilters() {
        const searchInput = document.getElementById('searchInput');
        const redFilter = document.getElementById('redUsersFilter');
        const searchTerm = searchInput ? searchInput.value.toLowerCase() : '';
        const showRedUsersOnly = redFilter ? redFilter.checked : false;

        let filteredData = currentData.filter(user => {
            // Search filter - check both email and name
            const fullName = ((user.first_name || '') + ' ' + (user.last_name || '')).trim().toLowerCase();
            const matchesSearch = user.email.toLowerCase().includes(searchTerm) ||
                fullName.includes(searchTerm) ||
                (user.first_name && user.first_name.toLowerCase().includes(searchTerm)) ||
                (user.last_name && user.last_name.toLowerCase().includes(searchTerm)) ||
                (user.pdn_code && user.pdn_code.toLowerCase().includes(searchTerm)) ||
                (user.diagnose_pdn_code && user.diagnose_pdn_code.toLowerCase().includes(searchTerm)) ||
                (user.coupon_code && user.coupon_code.toLowerCase().includes(searchTerm));

            // Red users filter
            if (showRedUsersOnly) {
                return matchesSearch && isRedUser(user);
            } else {
                return matchesSearch;
            }
        });

        renderTable(filteredData);

        // Show search results count when filtering
        const searchActive = searchTerm || showRedUsersOnly;
        document.getElementById('rowCount').textContent = searchActive
            ? `נמצאו ${filteredData.length} מתוך ${currentData.length}`
            : `סה"כ שורות: ${currentData.length}`;

        // Update search result count and clear button visibility
        const clearBtn = document.getElementById('clearSearchBtn');
        const countEl = document.getElementById('searchResultCount');
        if (searchTerm) {
            if (clearBtn) clearBtn.classList.remove('hidden');
            if (countEl) { countEl.classList.remove('hidden'); countEl.textContent = `נמצאו ${filteredData.length} תוצאות`; }
        } else {
            if (clearBtn) clearBtn.classList.add('hidden');
            if (countEl) countEl.classList.add('hidden');
        }
    }

    async function viewQuestionnaire(email) {
        if (!sessionToken) {
            window.location.href = '/pdn-admin/';
            return;
        }

        try {
            const response = await fetch(`/pdn-admin/user/questionnaire/${email}?session_token=${sessionToken}`);
            if (response.ok) {
                const data = await response.json();
                displayQuestionnaire(data);
                // Reset loading state for this specific row
                resetRowLoadingState(email, 'questionnaire');
            } else if (response.status === 401) {
                // Session expired or invalid, redirect to login
                redirectToLogin();
            } else {
                throw new Error('Failed to load questionnaire');
            }
        } catch (error) {
            logError('loadQuestionnaire', error);
            showNotification('שגיאה בטעינת השאלון', 'error');
            // Reset loading state for this specific row
            resetRowLoadingState(email, 'questionnaire');
        }
    }

    function displayQuestionnaire(data) {

        const content = document.getElementById('questionnaireContent');

        // Extract metadata and questions
        const metadata = data.metadata || {};
        const questions = {};
        const questionsData = data.questions_data || {};

        // Separate questions from metadata
        Object.keys(data).forEach(key => {
            if (key !== 'metadata' && key !== 'questions_data' && !isNaN(key)) {
                questions[key] = data[key];
            }
        });
        displayQuestionsWithText(questions, metadata, questionsData);
    }

    function renderQuestion(questionNumber, questionData, questionsData) {
        let answerDisplay = '';
        let questionText = `שאלה ${questionNumber}`;

        // Get question text from questions data
        if (questionsData) {
            for (const phaseKey in questionsData.phases) {
                const phase = questionsData.phases[phaseKey];
                if (phase.questions && phase.questions[questionNumber]) {
                    questionText = phase.questions[questionNumber].text;
                    break;
                }
            }
        }

        if (questionText === `שאלה ${questionNumber}` && questionData.question_text) {
            questionText = questionData.question_text;
        }

        if (questionData.ranking) {
            answerDisplay = renderRankingAnswer(questionData);
        } else if (questionData.selected_option_code) {
            answerDisplay = renderSelectedAnswer(questionData);
        } else if (questionData.answer && questionData.code) {
            answerDisplay = renderCodeAnswer(questionData);
        } else {
            answerDisplay = 'לא זמין';
        }

        return `<div class="border-b border-gray-200 pb-6 last:border-b-0">
            <div class="mb-4">
                <p class="text-gray-800 text-lg leading-relaxed">${questionNumber}. ${questionText}</p>
            </div>
            <div class="bg-gray-50 px-4 py-3 rounded-lg border border-gray-200">
                <p class="text-gray-600 text-sm mb-1">תשובה:</p>
                <p class="text-gray-800 text-sm mb-1">${answerDisplay}</p>
            </div>
        </div>`;
    }

    function renderRankingAnswer(questionData) {
        const rankingEntries = Object.entries(questionData.ranking);

        if (rankingEntries.length === 2 && typeof rankingEntries[0][1] === 'number' && typeof rankingEntries[1][1] === 'number') {
            return renderScaleAnswer(rankingEntries, questionData);
        }

        // Regular ranking
        const sortedRanking = rankingEntries.sort((a, b) => a[1] - b[1]);
        let rankedTexts = [];
        if (questionData.question_options && questionData.question_options.length > 0) {
            rankedTexts = sortedRanking.map(([code, rank]) => {
                const option = questionData.question_options.find(opt => opt.code === code);
                return `${rank}. ${option ? option.text : code}`;
            });
        } else {
            rankedTexts = sortedRanking.map(([code, rank]) => `${rank}. ${code}`);
        }
        return rankedTexts.join('<br>');
    }

    function renderScaleAnswer(rankingEntries, questionData) {
        const [leftCode, leftValue] = rankingEntries[0];
        const [rightCode, rightValue] = rankingEntries[1];
        let leftText = leftCode, rightText = rightCode;

        if (questionData.question_options && questionData.question_options.length >= 2) {
            const leftOption = questionData.question_options.find(opt => opt.code === leftCode);
            const rightOption = questionData.question_options.find(opt => opt.code === rightCode);
            if (leftOption) leftText = leftOption.text;
            if (rightOption) rightText = rightOption.text;
        }

        const scaleMap = [
            {position: 0, description: `${leftText} (במידה רבה מאוד)`, leftValue: 12, rightValue: 0},
            {position: 1, description: `${leftText} (במידה רבה)`, leftValue: 10, rightValue: 2},
            {position: 2, description: `${leftText} (במידה מסוימת)`, leftValue: 8, rightValue: 4},
            {position: 3, description: `באמצע (ניטרלי)`, leftValue: 6, rightValue: 6},
            {position: 4, description: `${rightText} (במידה מסוימת)`, leftValue: 4, rightValue: 8},
            {position: 5, description: `${rightText} (במידה רבה)`, leftValue: 2, rightValue: 10},
            {position: 6, description: `${rightText} (במידה רבה מאוד)`, leftValue: 0, rightValue: 12}
        ];

        const scalePosition = scaleMap.find(pos => pos.leftValue === leftValue && pos.rightValue === rightValue);

        if (scalePosition) {
            const filledDots = '●'.repeat(scalePosition.position + 1);
            const emptyDots = '○'.repeat(6 - scalePosition.position);
            return `<div class="space-y-2">
                <div class="flex items-center justify-between text-xs text-gray-600"><span>${leftText}</span><span>${rightText}</span></div>
                <div class="flex items-center justify-center"><span class="text-lg tracking-wider">${filledDots}${emptyDots}</span></div>
                <div class="text-center text-sm font-medium text-blue-600">${scalePosition.description}</div>
            </div>`;
        }

        return `<div class="space-y-2">
            <div class="text-sm text-gray-600">${leftText}: ${leftValue} | ${rightText}: ${rightValue}</div>
            <div class="text-xs text-gray-500">(לא ניתן לפענח את המיקום המדויק בסולם)</div>
        </div>`;
    }

    function renderSelectedAnswer(questionData) {
        let selectedText = questionData.selected_option_code;
        if (questionData.question_options && questionData.question_options.length > 0) {
            const selectedOption = questionData.question_options.find(option => option.code === questionData.selected_option_code);
            if (selectedOption) selectedText = selectedOption.text;
        }
        return selectedText;
    }

    function renderCodeAnswer(questionData) {
        let cleanAnswer = questionData.answer;
        if (questionData.question_options && questionData.question_options.length > 0) {
            const selectedOption = questionData.question_options.find(option => questionData.answer.includes(option.text));
            if (selectedOption) cleanAnswer = selectedOption.text;
        }
        if (cleanAnswer.includes('?')) {
            cleanAnswer = cleanAnswer.split('?').pop()?.trim() || cleanAnswer;
        }
        const rankingMatch = cleanAnswer.match(/(\d+)\.\s*([^0-9\n]+)/);
        if (rankingMatch) cleanAnswer = `${rankingMatch[1]}. ${rankingMatch[2].trim()}`;
        return cleanAnswer;
    }

    function displayQuestionsWithText(questions, metadata, questionsData) {
        const content = document.getElementById('questionnaireContent');

        content.innerHTML = `
        <div class="bg-gradient-to-br from-blue-50 via-blue-50 to-blue-100 p-8 rounded-2xl border border-blue-200 shadow-lg">
            <div class="flex items-center justify-between mb-6">
                <h3 class="text-2xl font-bold text-gray-800">
                    פרטי משתמש
                </h3>
                <div class="relative">
                    <button id="downloadPdfBtn"
                        onclick="this.nextElementSibling.classList.toggle('hidden')"
                        class="flex items-center gap-3 px-6 py-3 bg-gradient-to-r from-blue-900 to-blue-900 text-white font-bold rounded-xl shadow-lg hover:from-blue-900 hover:to-blue-900 transition-all duration-300 text-base transform hover:scale-105">
                        <i class="fas fa-file-arrow-down mr-2 text-lg"></i>
                        הורד דוח
                        <i class="fas fa-chevron-down mr-2"></i>
                    </button>

                    <div class="absolute top-full mt-1 w-48 bg-white rounded-lg shadow-lg border border-blue-200 z-50 hidden">
                        <div class="py-1">
                            <button onclick="this.closest('.relative').querySelector('.absolute').classList.add('hidden'); downloadReport('pdf')"
                                    class="w-full text-right px-4 py-2 text-sm text-gray-700 hover:bg-blue-50 flex items-center">
                                <i class="fas fa-file-pdf ml-2 text-red-500"></i>
                                הורד PDF
                            </button>

                            <button onclick="this.closest('.relative').querySelector('.absolute').classList.add('hidden'); downloadUserJSON('admin')"
                                    class="w-full text-right px-4 py-2 text-sm text-gray-700 hover:bg-blue-50 flex items-center">
                                <i class="fas fa-file-code ml-2 text-green-500"></i>
                                הורד JSON
                            </button>
                        </div>
                    </div>
                </div>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-6">
                <!-- Personal Information Section -->
        <div class="space-y-4">
        <div class="bg-white p-4 rounded-xl border border-gray-200 shadow-sm hover:shadow-md transition-shadow">
        <div class="text-sm text-gray-500 mb-1">שם פרטי</div>
        <div class="font-bold text-gray-900 text-lg">${metadata["first_name"] || 'לא זמין'}</div>
        </div>
        <div class="bg-white p-4 rounded-xl border border-gray-200 shadow-sm hover:shadow-md transition-shadow">
        <div class="text-sm text-gray-500 mb-1">שם משפחה</div>
        <div class="font-bold text-gray-900 text-lg">${metadata["last_name"] || 'לא זמין'}</div>
        </div>
        <div class="bg-white p-4 rounded-xl border border-gray-200 shadow-sm hover:shadow-md transition-shadow">
        <div class="text-sm text-gray-500 mb-1">אימייל</div>
        <div class="font-bold text-gray-900 text-sm break-all">${metadata["Email"] || 'לא זמין'}</div>
        </div>
        <div class="bg-white p-4 rounded-xl border border-gray-200 shadow-sm hover:shadow-md transition-shadow">
        <div class="text-sm text-gray-500 mb-1">מספר טלפון</div>
        <div class="font-bold text-gray-900 text-lg break-all">${metadata["phone"] || 'לא זמין'}</div>
        </div>
        <div class="bg-white p-4 rounded-xl border border-gray-200 shadow-sm hover:shadow-md transition-shadow">
        <div class="text-sm text-gray-500 mb-1">שם מפנה</div>
        <div class="font-bold text-gray-900 text-lg break-all">${metadata["referral_source"] || 'לא זמין'}</div>
        </div>
        <div class="bg-white p-4 rounded-xl border border-gray-200 shadow-sm hover:shadow-md transition-shadow">
        <div class="text-sm text-gray-500 mb-1">קופון</div>
        <div class="font-bold text-gray-900 text-lg break-all" style="direction: ltr; text-align: right;">${metadata["coupon_code"] || '—'}</div>
        </div>
        </div>

            <!-- System Information Section -->
        <div class="space-y-4">
        <div class="bg-white p-4 rounded-xl border border-gray-200 shadow-sm hover:shadow-md transition-shadow">
        <div class="text-sm text-gray-500 mb-1">מזהה מערכת</div>
        <div  class="font-bold text-gray-900 text-lg break-all">${metadata["User ID"] || 'לא זמין'}</div>
        </div>
        <div class="bg-white p-4 rounded-xl border border-gray-200 shadow-sm hover:shadow-md transition-shadow">
        <div class="text-sm text-gray-500 mb-1">שנת לידה</div>
        <div class="font-bold text-gray-900 text-lg break-all">${metadata["birth_year"] || 'לא זמין'}</div>
        </div>
        <div class="bg-white p-4 rounded-xl border border-gray-200 shadow-sm hover:shadow-md transition-shadow">
        <div class="text-sm text-gray-500 mb-1">שפת אם</div>
        <div class="font-bold text-gray-900 text-lg break-all">${metadata["mother_language"] || 'לא זמין'}</div>
        </div>
        <div class="bg-white p-4 rounded-xl border border-gray-200 shadow-sm hover:shadow-md transition-shadow">
        <div class="text-sm text-gray-500 mb-1">מגדר</div>
        <div class="font-bold text-gray-900 text-lg break-all">${metadata["gender"] || 'לא זמין'}</div>
        </div>
        </div>

            <!-- Diagnosis Information Section -->
        <div class="space-y-4">
        <div class="bg-white p-4 rounded-xl border border-gray-200 shadow-sm hover:shadow-md transition-shadow">
        <div class="text-sm text-gray-500 mb-1">קוד פדן</div>
        <div >${metadata["Diagnose PDN Code"] || metadata["PDN Code"] || 'לא זמין'}</div>
        </div>
        <div class="bg-white p-4 rounded-xl border border-gray-200 shadow-sm hover:shadow-md transition-shadow">
        <div class="text-sm text-gray-500 mb-1">תאריך אבחון</div>
        <div class="font-bold text-gray-900 text-lg">${metadata["Date"] || 'לא זמין'}</div>
        </div>
        <div class="bg-white p-4 rounded-xl border border-gray-200 shadow-sm hover:shadow-md transition-shadow">
        <div class="text-sm text-gray-500 mb-1">השכלה</div>
        <div class="font-bold text-gray-900 text-lg break-all">${metadata["education"] || 'לא זמין'}</div>
        </div>
        <div class="bg-white p-4 rounded-xl border border-gray-200 shadow-sm hover:shadow-md transition-shadow">
        <div class="text-sm text-gray-500 mb-1">תפקיד</div>
        <div class="font-bold text-gray-900 text-lg break-all">${metadata["job_title"] || 'לא זמין'}</div>
        </div>
        </div>
        </div>
        </div>

        <div class="bg-white p-8 rounded-2xl border border-gray-200 shadow-lg mt-6">
        <h3 class="text-2xl font-bold text-gray-800 mb-6">
        תשובות מאובחן (${Object.keys(questions).length} שאלות)
        </h3>
        <div class="space-y-6">
        ${Object.entries(questions).map(([qNum, qData]) => renderQuestion(qNum, qData, questionsData)).join('')}
        </div>
        </div>
        `
        ;

        document.getElementById('questionnaireModal').style.display = 'flex';
        setTimeout(() => { document.getElementById('questionnaireModal').querySelector('button, input')?.focus(); }, 100);
    }

        async function playVoice(email) {
            if (!sessionToken) {
                window.location.href = '/pdn-admin/';
                return;
            }

            try {

                const response = await fetch(
                    `/pdn-admin/user/voice/${email}?session_token=${sessionToken}`
                );

                if (response.ok) {
                    const data = await response.json();
                    displayVoice(data);
                    // Reset loading state for this specific row
                    resetRowLoadingState(email, 'voice');
                } else if (response.status === 401) {
                    // Session expired or invalid, redirect to login
                    redirectToLogin();
                } else {
                    const errorText = await response.text();
                    throw new Error(
                        `Failed to load voice: ${response.status} ${errorText}`
                    );
                }
            } catch (error) {
                logError('loadVoice', error);
                showNotification('שגיאה בטעינת ההקלטה', 'error');
                // Reset loading state for this specific row
                resetRowLoadingState(email, 'voice');
            }
        }

        function displayVoice(data) {
            const content = document.getElementById('voiceContent');

            // Check if we have the required data
            if (!data || !data.voice_recordings || Object.keys(data.voice_recordings).length === 0) {
                content.innerHTML =
                    `
        <div class="bg-red-50 p-6 rounded-xl border border-red-200">
        <h3 class="text-lg font-semibold mb-4 text-red-800 flex items-center">
        <i class="fas fa-exclamation-triangle mr-2"></i>שגיאה
        </h3>
        <p class="text-red-700">לא נמצא קובץ הקלטה למשתמש זה</p>
        </div>
        `
                ;
                document.getElementById('voiceModal').style.display = 'flex';
                setTimeout(() => { document.getElementById('voiceModal').querySelector('button, input')?.focus(); }, 100);
                return;
            }

            // Build HTML for multiple recordings
            let recordingsHtml = '';
            const recordings = data.voice_recordings;

            // Helper function to create audio URL
            function createAudioUrl(filePath) {
                // Extract just the relative path from the full file path
                let processedPath = filePath;

                // Remove 'saved_results/' prefix if it exists
                if (processedPath.startsWith('saved_results/')) {
                    processedPath = processedPath.substring('saved_results/'.length);
                }

                // Remove '/pdn/saved_results/' prefix if it exists
                if (processedPath.startsWith('/pdn/saved_results/')) {
                    processedPath = processedPath.substring('/pdn/saved_results/'.length);
                }

                // Remove 'pdn/saved_results/' prefix if it exists
                if (processedPath.startsWith('pdn/saved_results/')) {
                    processedPath = processedPath.substring('pdn/saved_results/'.length);
                }

                return `/pdn-admin/audio/${encodeURIComponent(processedPath)}?session_token=${sessionToken}`;
            }

            // Add question1 recording if exists
            if (recordings.question1) {
                const audioUrl = createAudioUrl(recordings.question1.path);
                recordingsHtml +=
                    `
        <div class="bg-white p-6 rounded-xl border border-gray-200 mb-4">
        <h4 class="text-lg font-semibold mb-4 text-gray-800 flex items-center">
        <i class="fas fa-microphone mr-2 text-blue-600"></i>שאלה 1 - חוויה חיובית
        </h4>
        <audio controls class="w-full" preload="metadata">
        <source src="${audioUrl}" type="audio/wav">
        <source src="${audioUrl}" type="audio/mp3">
        <source src="${audioUrl}" type="audio/mpeg">
        הדפדפן שלך לא תומך בנגינת אודיו.
        </audio>
        </div>
        `;
            }

            // Add question2 recording if exists
            if (recordings.question2) {
                const audioUrl = createAudioUrl(recordings.question2.path);
                recordingsHtml += `

                <div class="bg-white p-6 rounded-xl border border-gray-200 mb-4">
                    <h4 class="text-lg font-semibold mb-4 text-gray-800 flex items-center">
                        <i class="fas fa-microphone mr-2 text-blue-600"></i>שאלה 2 - אתגר משמעותי
                    </h4>
                    <audio controls class="w-full" preload="metadata">
                        <source src="${audioUrl}" type="audio/wav">
                        <source src="${audioUrl}" type="audio/mp3">
                        <source src="${audioUrl}" type="audio/mpeg">
                        הדפדפן שלך לא תומך בנגינת אודיו.
                    </audio>
                </div>

        `;
            }

            // Add legacy recording if exists
            if (recordings.legacy) {
                const audioUrl = createAudioUrl(recordings.legacy.path);
                recordingsHtml += `

                <div class="bg-white p-6 rounded-xl border border-gray-200 mb-4">
                    <h4 class="text-lg font-semibold mb-4 text-gray-800 flex items-center">
                        <i class="fas fa-microphone ml-2 text-blue-900"></i> הקלטה קולית
                    </h4>
                    <audio controls class="w-full" preload="metadata">
                        <source src="${audioUrl}" type="audio/wav">
                        <source src="${audioUrl}" type="audio/mp3">
                        <source src="${audioUrl}" type="audio/mpeg">
                        הדפדפן שלך לא תומך בנגינת אודיו.
                    </audio>
                </div>

        `;
            }

            content.innerHTML = `
        <div class="bg-gradient-to-r from-blue-100 to-blue-100 p-6 rounded-xl border border-blue-200 mb-6">
        <h3 class="text-lg font-semibold mb-4 text-gray-800 flex items-center">
        <i class="fas fa-info-circle ml-2 text-blue-900"></i> פרטי הקלטה
        </h3>
        <div class="grid grid-cols-2 gap-4">
        <div><strong>אימייל:</strong> ${data.email || 'לא זמין'}</div>
        <div><strong>מספר הקלטות:</strong> <span class="px-2 py-1 bg-blue-100 text-blue-800 rounded text-sm">${Object.keys(recordings).length}</span></div>
        </div>
        </div>
        ${recordingsHtml}
        `;

            document.getElementById('voiceModal').style.display = 'flex';
            setTimeout(() => { document.getElementById('voiceModal').querySelector('button, input')?.focus(); }, 100);

            // Add event listeners to all audio elements for debugging
            const audioElements = content.querySelectorAll('audio');
            audioElements.forEach((audioElement, index) => {
                audioElement.addEventListener('error', (e) => {
                    logError('audioPlayback', e);
                });
            });
        }

        function editDiagnose(email) {
            currentEditEmail = email;
            const user = currentData.find(u => u.email === email);

            if (user) {
                document.getElementById('diagnosePdnCode').value = user.diagnose_pdn_code;
                document.getElementById('diagnoseComments').value = user.diagnose_comments;
                document.getElementById('editDiagnoseModal').style.display = 'flex';
                setTimeout(() => { document.getElementById('diagnosePdnCode').focus(); }, 100);
                // Reset loading state for this specific row
                resetRowLoadingState(email, 'edit');
            }
        }

        async function handleEditDiagnose(e) {
            e.preventDefault();
            if (!sessionToken || !currentEditEmail) {
                if (!sessionToken) {
                    window.location.href = '/pdn-admin/';
                }
                return;
            }

            const pdnCode = document.getElementById('diagnosePdnCode').value.trim();
            const comments = document.getElementById('diagnoseComments').value.trim();

            // Check if both fields are empty
            if (!pdnCode && !comments) {
                showNotification('אנא מלא לפחות אחד מהשדות', 'warning');
                return;
            }

            showLoading();
            try {
                const formData = {
                    diagnose_pdn_code: pdnCode,
                    diagnose_comments: comments
                };

                const response = await fetch(`/pdn-admin/user/diagnose/${currentEditEmail}?session_token=${sessionToken}`, {
                    method: 'PUT',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(formData)
                });

                if (response.ok) {
                    const data = await response.json();
                    // Update local data
                    const userIndex = currentData.findIndex(u => u.email === currentEditEmail);
                    if (userIndex !== -1) {
                        currentData[userIndex] = data.user;
                        renderTable(currentData);
                    }
                    closeModal('editDiagnoseModal');
                } else if (response.status === 401) {
                    // Session expired or invalid, redirect to login
                    redirectToLogin();
                } else {
                    throw new Error('Failed to update diagnose');
                }
            } catch (error) {
                logError('updateDiagnose', error);
                showNotification('שגיאה בעדכון האבחון', 'error');
            } finally {
                hideLoading();
            }
        }

        async function sendEmail(email, emailType = 'pdn') {
            if (!sessionToken) {
                window.location.href = '/pdn-admin/';
                return;
            }

            // Find user data
            const user = currentData.find(u => u.email === email);
            if (!user) {
                showNotification('משתמש לא נמצא', 'error');
                resetRowLoadingState(email, 'email');
                return;
            }

            // Only check code match for PDN emails, not Binat invites
            if (emailType === 'pdn') {
                const codesMatch = user.pdn_code === user.diagnose_pdn_code &&
                    user.diagnose_pdn_code !== "N/A" &&
                    user.diagnose_pdn_code !== "";

                if (!codesMatch) {
                    showNotification('לא ניתן לשלוח אימייל - קוד פדן אינו תואם לקוד המאבחן', 'error');
                    resetRowLoadingState(email, 'email');
                    return;
                }
            }

            // Prompt for admin password (PDN email only - binat invite uses session token directly)
            if (emailType === 'pdn') {
                const passwordPrompt = 'הזן סיסמת מנהל לשליחת אימייל:';
                const password = await requestAdminPassword(passwordPrompt);
                if (!password) {
                    resetRowLoadingState(email, 'email');
                    return;
                }
            }

            try {
                const endpoint = emailType === 'binat'
                    ? `/pdn-admin/user/send_binat_invite/${email}?session_token=${sessionToken}`
                    : `/pdn-admin/user/send_email/${email}?session_token=${sessionToken}`;

                const response = await fetch(endpoint, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({})
                });

                if (response.ok) {
                    const data = await response.json();

                    // Show appropriate notification based on verification status
                    if (data.needs_verification) {
                        showNotification(`אימייל נשלח ל-${email} - נדרש אימות אנושי (הפער בין הציונים קטן מ-2 נקודות)`, 'warning');
                    } else {
                        showNotification(`אימייל נשלח בהצלחה ל-${email}`, 'success');
                    }

                    // Update local data with verification status
                    const userIndex = currentData.findIndex(u => u.email === email);
                    if (userIndex !== -1) {
                        currentData[userIndex].needs_verification = data.needs_verification || false;
                        renderTable(currentData);
                    }

                    // Reset loading state for this specific row
                    resetRowLoadingState(email, 'email');
                } else if (response.status === 401) {
                    // Session expired or invalid, redirect to login
                    redirectToLogin();
                } else {
                    let errorMessage = 'Failed to send email';
                    try {
                        const errorData = await response.json();
                        errorMessage = errorData.detail || errorData.error || errorMessage;
                    } catch (parseError) {
                        // If response is not JSON (e.g., HTML error page), use status text
                        errorMessage = `HTTP ${response.status}: ${response.statusText}`;
                    }
                    throw new Error(errorMessage);
                }
            } catch (error) {
                logError('sendEmail', error);
                showNotification(`
    שגיאה בשליחת האימייל: ${error.message}
        `, 'error');
                // Reset loading state for this specific row
                resetRowLoadingState(email, 'email');
            }
        }

        async function recalculatePdnCode(email) {
            if (!sessionToken) {
                window.location.href = '/pdn-admin/';
                return;
            }

            // Find user data
            const user = currentData.find(u => u.email === email);
            if (!user) {
                showNotification('משתמש לא נמצא', 'error');
                resetRowLoadingState(email, 'recalculate');
                return;
            }

            try {
                const response = await fetch(`/pdn-admin/user/recalculate_pdn/${email}?session_token=${sessionToken}`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({})
                });

                if (response.ok) {
                    const data = await response.json();

                    // Show appropriate notification based on verification status
                    if (data.needs_verification) {
                        showNotification(`קוד פדן חושב מחדש: ${data.pdn_code} - נדרש אימות אנושי (הפער בין הציונים קטן מ-2 נקודות)`, 'warning');
                    } else {
                        showNotification(`קוד פדן חושב מחדש בהצלחה: ${data.pdn_code} על ידי ${data.updated_by}`, 'success');
                    }

                    // Display calculation details in modal if available
                    if (data.calculation_details) {
                        showCalculationDetails(email, data, user.pdn_code);
                    }

                    // Update local data
                    const userIndex = currentData.findIndex(u => u.email === email);
                    if (userIndex !== -1) {
                        currentData[userIndex].pdn_code = data.pdn_code;
                        currentData[userIndex].needs_verification = data.needs_verification || false;
                        if (data.confidence_score !== undefined) {
                            currentData[userIndex].confidence_score = data.confidence_score;
                        }
                        // Update the PDN update comments if available
                        if (data.pdn_update_comments) {
                            currentData[userIndex].pdn_update_comments = data.pdn_update_comments;
                        }
                        renderTable(currentData);
                    }

                    // Reset loading state for this specific row
                    resetRowLoadingState(email, 'recalculate');
                } else if (response.status === 401) {
                    // Session expired or invalid, redirect to login
                    redirectToLogin();
                } else {
                    let errorMessage = 'Failed to recalculate PDN code';
                    try {
                        const errorData = await response.json();
                        errorMessage = errorData.detail || errorData.error || errorMessage;
                    } catch (parseError) {
                        // If response is not JSON (e.g., HTML error page), use status text
                        errorMessage = `HTTP ${response.status}: ${response.statusText}`;
                    }
                    throw new Error(errorMessage);
                }
            } catch (error) {
                logError('recalculatePdn', error);
                showNotification(`שגיאה בחישוב מחדש של קוד פדן: ${error.message}`, 'error');
                // Reset loading state for this specific row
                resetRowLoadingState(email, 'recalculate');
            }
        }

        let appVersionData = null;

        async function loadVersion() {
            try {
                const response = await fetch('/pdn-admin/version');
                if (response.ok) {
                    appVersionData = await response.json();
                    document.getElementById('versionText').textContent = `v${appVersionData.version}`;
                }
            } catch (error) {
                logError('loadVersion', error);
                document.getElementById('versionText').textContent = 'N/A';
            }
        }

        function showReleaseNotes() {
            if (!appVersionData) return;

            const container = document.getElementById('releaseNotesContent');
            const notesHtml = appVersionData.release_notes.map(note =>
                `<div class="flex items-start gap-3 p-3 bg-gray-50 rounded-lg">
                    <span class="text-green-500 mt-0.5"><i class="fas fa-check-circle"></i></span>
                    <span class="text-gray-800 text-sm">${note}</span>
                </div>`
            ).join('');

            container.innerHTML = `
                <div class="p-4 bg-blue-50 rounded-lg border border-blue-200 text-center mb-4">
                    <div class="text-2xl font-bold text-blue-900 mb-1">v${appVersionData.version}</div>
                    <div class="text-sm text-gray-600">${appVersionData.release_date}</div>
                    <div style="margin-top:8px;display:inline-flex;align-items:center;gap:6px;padding:4px 12px;background:#dbeafe;border-radius:20px;">
                        <i class="fas fa-robot" style="font-size:11px;color:#1e40af;"></i>
                        <span style="font-size:11px;font-weight:600;color:#1e40af;">${appVersionData.model || 'claude-sonnet-5'}</span>
                    </div>
                </div>
                <div class="space-y-2">
                    ${notesHtml}
                </div>
            `;

            document.getElementById('releaseNotesModal').style.display = 'flex';
            setTimeout(() => { document.getElementById('releaseNotesModal').querySelector('button, input')?.focus(); }, 100);
        }

        function showCalculationDetails(email, data, previousCode) {
            // Store the email for the send button
            window._currentCalcEmail = email;
            const container = document.getElementById('pdnCalculationContent');
            const stages = data.calculation_details;
            const traitLabels = { A: 'הישגיות (Achievement)', T: 'ביטחון (Trust)', P: 'הנאה (Pleasure)', E: 'אדנות (Empower)' };
            const traitShort = { A: 'A', T: 'T', P: 'P', E: 'E' };
            const energyLabels = { D: 'דינמית (Dynamic)', S: 'יציבה (Stability)', F: 'גמישה (Flexibility)' };
            const stageDescriptions = {
                A: { name: 'חישוב תכונה ראשית', icon: '①', desc: 'שאלות 1-26: זיהוי התכונה הדומיננטית' },
                B: { name: 'חישוב סוג אנרגיה', icon: '②', desc: 'שאלות 27-37: זיהוי סוג האנרגיה המניעה' },
                C: { name: 'אימות תכונות', icon: '③', desc: 'שאלות 38-42: שבירת שוויון בין תכונות' },
                D: { name: 'אימות תכונות', icon: '④', desc: 'שאלות 43-56: חיזוק וחידוד התכונות' },
                E: { name: 'חיזוק דומיננטי', icon: '⑤', desc: 'שאלות 57-60: דירוג סופי של התכונות' }
            };

            // Find the final stage first to show at top
            const finalStage = stages.find(s => s.stage === 'Final');
            let html = '';

            // Final result card at top
            if (finalStage) {
                const verifyBadge = finalStage.needs_verification
                    ? '<div style="margin-top: 12px; display: inline-flex; align-items: center; gap: 8px; background: #fef3c7; color: #92400e; font-size: 13px; font-weight: 600; padding: 8px 16px; border-radius: 8px;"><i class="fas fa-exclamation-triangle"></i> נדרש אימות אנושי — הפער בין הציונים קטן מ-2 נקודות</div>'
                    : '<div style="margin-top: 12px; display: inline-flex; align-items: center; gap: 8px; background: #d1fae5; color: #065f46; font-size: 13px; font-weight: 600; padding: 8px 16px; border-radius: 8px;"><i class="fas fa-check-circle"></i> תקין</div>';

                const overrideBadge = finalStage.stage_e_override
                    ? `<div style="margin-top: 8px; display: inline-flex; align-items: center; gap: 8px; background: #fee2e2; color: #991b1b; font-size: 13px; font-weight: 600; padding: 8px 16px; border-radius: 8px;"><i class="fas fa-exchange-alt"></i> שלב E שינה תכונה דומיננטית: ${finalStage.dominant_before_stage_e || '?'} → ${finalStage.trait} — נדרש אימות</div>`
                    : '';

                html += `
                <div style="padding: 28px; background: linear-gradient(135deg, #0b2e6b 0%, #1a3f7a 100%); border-radius: 16px; color: white; text-align: center; box-shadow: 0 8px 32px rgba(11, 46, 107, 0.3);">
                    <div style="font-size: 13px; opacity: 0.7; margin-bottom: 4px;">${email}</div>
                    ${previousCode && previousCode !== finalStage.pdn_code ? `<div style="font-size: 13px; opacity: 0.7; margin: 8px 0;"><span style="text-decoration:line-through;opacity:0.5;">${previousCode}</span> → <span style="font-weight:700;">${finalStage.pdn_code}</span></div><div style="font-size: 48px; font-weight: 800; margin: 8px 0; letter-spacing: 2px;">${finalStage.pdn_code}</div>` : `<div style="font-size: 48px; font-weight: 800; margin: 16px 0; letter-spacing: 2px;">${finalStage.pdn_code}</div>`}
                    <div style="display: flex; justify-content: center; gap: 40px; font-size: 14px; opacity: 0.9;">
                        <div>
                            <div style="font-size: 11px; opacity: 0.6; margin-bottom: 4px;">תכונה</div>
                            <div style="font-size: 20px; font-weight: 700;">${finalStage.trait}</div>
                            <div style="font-size: 11px; opacity: 0.6;">${traitLabels[finalStage.trait] || finalStage.trait}</div>
                        </div>
                        <div style="width: 1px; background: rgba(255,255,255,0.2);"></div>
                        <div>
                            <div style="font-size: 11px; opacity: 0.6; margin-bottom: 4px;">אנרגיה</div>
                            <div style="font-size: 20px; font-weight: 700;">${finalStage.energy}</div>
                            <div style="font-size: 11px; opacity: 0.6;">${energyLabels[finalStage.energy] || finalStage.energy}</div>
                        </div>
                    </div>
                    ${verifyBadge}
                    ${overrideBadge}
                </div>`; 
            }

            // Stage-by-stage breakdown
            html += '<div style="margin-top: 24px;">';
            html += '<h3 style="font-size: 16px; font-weight: 700; color: #1e293b; margin: 0 0 16px; display: flex; align-items: center; gap: 8px;"><i class="fas fa-list-ol" style="color: #0b2e6b;"></i> פירוט שלבי החישוב</h3>';

            let energyLabelShown = false;
            stages.forEach(stage => {
                if (stage.stage === 'Final') return; // Already shown at top

                const info = stageDescriptions[stage.stage] || { name: stage.stage, icon: '•', desc: '' };
                const hasTraits = stage.scores && ['A','T','P','E'].some(k => stage.scores[k] !== undefined);
                const hasEnergy = stage.scores && ['D','S','F'].some(k => stage.scores[k] !== undefined);

                html += `
                <div style="background: white; border-radius: 12px; border: 1px solid #e2e8f0; overflow: hidden; margin-bottom: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.04);">
                    <div style="background: #f8fafc; padding: 12px 20px; border-bottom: 1px solid #e2e8f0; display: flex; align-items: center; justify-content: space-between;">
                        <div style="display: flex; align-items: center; gap: 12px;">
                            <span style="font-size: 20px;">${info.icon}</span>
                            <div>
                                <div style="font-weight: 600; color: #1e293b; font-size: 14px;">${info.name}</div>
                                <div style="font-size: 11px; color: #64748b;">${info.desc}</div>
                            </div>
                        </div>
                        ${stage.dominant ? `<span style="padding: 4px 12px; background: rgba(11,46,107,0.08); color: #0b2e6b; font-size: 12px; font-weight: 700; border-radius: 20px;">דומיננטי: ${stage.dominant}</span>` : ''}
                    </div>
                    <div style="padding: 16px 20px;">`;

                // Trait scores
                if (hasTraits) {
                    const maxTrait = Math.max(...['A','T','P','E'].map(k => stage.scores[k] || 0), 1);
                    ['A', 'T', 'P', 'E'].forEach(key => {
                        if (stage.scores[key] !== undefined) {
                            const isDominant = stage.dominant === key;
                            const barWidth = Math.max(2, (stage.scores[key] / maxTrait) * 100);
                            const barColor = isDominant ? '#0b2e6b' : '#e2e8f0';
                            const labelWeight = isDominant ? '700' : '400';
                            const labelColor = isDominant ? '#0b2e6b' : '#64748b';
                            const scoreColor = isDominant ? '#0b2e6b' : '#64748b';

                            html += `
                            <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 8px;">
                                <span style="width: 120px; font-size: 13px; font-weight: ${labelWeight}; color: ${labelColor}; flex-shrink: 0;">${traitLabels[key]}</span>
                                <div style="flex: 1; background: #f1f5f9; border-radius: 20px; height: 22px; overflow: hidden; position: relative;">
                                    <div style="background: ${barColor}; height: 100%; border-radius: 20px; width: ${barWidth}%; transition: width 0.5s ease;"></div>
                                </div>
                                <span style="width: 36px; text-align: center; font-size: 13px; font-weight: 700; color: ${scoreColor}; flex-shrink: 0;">${stage.scores[key]}</span>
                            </div>`;
                        }
                    });
                }

                // Energy scores
                if (hasEnergy) {
                    if (hasTraits) {
                        html += '<div style="border-top: 1px solid #f1f5f9; margin: 12px 0;"></div>';
                    }
                    if (!energyLabelShown) {
                        html += '<div style="font-size: 11px; color: #64748b; font-weight: 600; margin-bottom: 8px;">סוג אנרגיה</div>';
                        energyLabelShown = true;
                    }
                    const maxEnergy = Math.max(...['D','S','F'].map(k => stage.scores[k] || 0), 1);
                    ['D', 'S', 'F'].forEach(key => {
                        if (stage.scores[key] !== undefined) {
                            const isDominant = stage.dominant === key;
                            const barWidth = Math.max(2, (stage.scores[key] / maxEnergy) * 100);
                            const barColor = isDominant ? '#059669' : '#e2e8f0';
                            const labelWeight = isDominant ? '700' : '400';
                            const labelColor = isDominant ? '#065f46' : '#64748b';
                            const scoreColor = isDominant ? '#065f46' : '#64748b';

                            html += `
                            <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 8px;">
                                <span style="width: 120px; font-size: 13px; font-weight: ${labelWeight}; color: ${labelColor}; flex-shrink: 0;">${energyLabels[key]}</span>
                                <div style="flex: 1; background: #f1f5f9; border-radius: 20px; height: 22px; overflow: hidden; position: relative;">
                                    <div style="background: ${barColor}; height: 100%; border-radius: 20px; width: ${barWidth}%; transition: width 0.5s ease;"></div>
                                </div>
                                <span style="width: 36px; text-align: center; font-size: 13px; font-weight: 700; color: ${scoreColor}; flex-shrink: 0;">${stage.scores[key]}</span>
                            </div>`;
                        }
                    });
                }

                html += '</div></div>';
            });

            html += '</div>';

            container.innerHTML = html;
            document.getElementById('pdnCalculationModal').style.display = 'flex';
            setTimeout(() => { document.getElementById('pdnCalculationModal').querySelector('button, input')?.focus(); }, 100);
        }

        async function sendCalculationByEmail() {
            const email = window._currentCalcEmail;
            if (!email) {
                showNotification('לא נמצא אימייל', 'error');
                return;
            }

            const btn = document.getElementById('sendCalcEmailBtn');
            btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> שולח...';
            btn.disabled = true;

            try {
                // Get the calculation content HTML and send it as email to admin
                const content = document.getElementById('pdnCalculationContent').innerHTML;
                const response = await fetch(`/pdn-admin/send_calculation_report?session_token=${sessionToken}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ email: email, html_content: content })
                });

                if (response.ok) {
                    showNotification('דוח חישוב נשלח בהצלחה למייל', 'success');
                } else if (response.status === 401) {
                    redirectToLogin();
                } else {
                    const errorData = await response.json().catch(() => ({}));
                    throw new Error(errorData.error || 'שליחה נכשלה');
                }
            } catch (error) {
                showNotification(`שגיאה בשליחה: ${error.message}`, 'error');
            } finally {
                btn.innerHTML = '<i class="fas fa-envelope"></i> שלח במייל';
                btn.disabled = false;
            }
        }

        function closeModal(modalId) {
            const modal = document.getElementById(modalId);
            modal.style.display = 'none';
            if (modalId === 'editDiagnoseModal') {
                currentEditEmail = null;
            }
            // Release focus trap
            releaseFocusTrap(modal);
            // Return focus to the previously focused element
            if (_lastFocusedElement) {
                _lastFocusedElement.focus();
                _lastFocusedElement = null;
            }
        }

        function openModal(modalId) {
            _lastFocusedElement = document.activeElement;
            const modal = document.getElementById(modalId);
            modal.style.display = 'flex';
            trapFocus(modal);
            // Focus first focusable element
            const focusable = modal.querySelector('input:not([type="hidden"]), button, select, textarea, [tabindex]:not([tabindex="-1"])');
            if (focusable) setTimeout(() => focusable.focus(), 100);
        }

        // ===== Focus Trap for Modals (Accessibility) =====
        // Auto-apply focus trap when any modal-backdrop becomes visible
        (function initModalFocusTraps() {
            const observer = new MutationObserver((mutations) => {
                mutations.forEach((mutation) => {
                    if (mutation.type === 'attributes' && mutation.attributeName === 'style') {
                        const el = mutation.target;
                        if (el.classList.contains('modal-backdrop')) {
                            if (el.style.display === 'flex') {
                                trapFocus(el);
                            } else if (el.style.display === 'none') {
                                releaseFocusTrap(el);
                            }
                        }
                    }
                });
            });
            // Observe all modal backdrops
            setTimeout(() => {
                document.querySelectorAll('.modal-backdrop').forEach(modal => {
                    observer.observe(modal, { attributes: true, attributeFilter: ['style'] });
                });
            }, 500);
        })();

        // ===== Focus Trap for Modals (Accessibility) =====
        function trapFocus(modal) {
            modal._trapHandler = function(e) {
                if (e.key !== 'Tab') return;
                const focusables = modal.querySelectorAll('input:not([type="hidden"]), button:not([disabled]), select, textarea, [tabindex]:not([tabindex="-1"])');
                if (focusables.length === 0) return;
                const first = focusables[0];
                const last = focusables[focusables.length - 1];
                if (e.shiftKey && document.activeElement === first) {
                    e.preventDefault();
                    last.focus();
                } else if (!e.shiftKey && document.activeElement === last) {
                    e.preventDefault();
                    first.focus();
                }
            };
            modal.addEventListener('keydown', modal._trapHandler);
            // Close on Escape
            modal._escHandler = function(e) {
                if (e.key === 'Escape') {
                    closeModal(modal.id);
                }
            };
            modal.addEventListener('keydown', modal._escHandler);
        }

        function releaseFocusTrap(modal) {
            if (modal._trapHandler) modal.removeEventListener('keydown', modal._trapHandler);
            if (modal._escHandler) modal.removeEventListener('keydown', modal._escHandler);
        }

        function showLoading() {
            document.getElementById('loadingSpinner').classList.remove('hidden');
        }

        function hideLoading() {
            document.getElementById('loadingSpinner').classList.add('hidden');
        }

        // Close modals when clicking outside
        document.addEventListener('click', function (e) {
            if (e.target.classList.contains('modal-backdrop')) {
                e.target.style.display = 'none';
            }
        });

        // Add keyboard event listeners for all modals
        document.addEventListener('keydown', function (event) {
            if (event.key === 'Escape') {
                const modals = ['questionnaireModal', 'voiceModal', 'editDiagnoseModal', 'loggedInUsersModal', 'pdnCalculationModal', 'releaseNotesModal', 'adminPasswordModal', 'journeyModal'];
                modals.forEach(id => {
                    const modal = document.getElementById(id);
                    if (modal && modal.style.display === 'flex') {
                        closeModal(id);
                    }
                });
            }
        });

        let sortColumn = 'date';
        let sortDirection = 'desc';

        function sortTable(column) {
            if (sortColumn === column) {
                sortDirection = sortDirection === 'asc' ? 'desc' : 'asc';
            } else {
                sortColumn = column;
                sortDirection = 'asc';
            }

            currentData.sort((a, b) => {
                let valA, valB;
                switch(column) {
                    case 'name':
                        valA = ((a.first_name || '') + ' ' + (a.last_name || '')).trim().toLowerCase();
                        valB = ((b.first_name || '') + ' ' + (b.last_name || '')).trim().toLowerCase();
                        break;
                    case 'email':
                        valA = a.email.toLowerCase();
                        valB = b.email.toLowerCase();
                        break;
                    case 'date':
                        return sortDirection === 'asc' ? parseDate(a.date) - parseDate(b.date) : parseDate(b.date) - parseDate(a.date);
                    case 'pdn_code':
                        valA = (a.pdn_code || '').toLowerCase();
                        valB = (b.pdn_code || '').toLowerCase();
                        break;
                    case 'needs_verification':
                        // Sort by displayed status: לבדיקה (needs attention) first
                        const aNeeds = a.needs_verification || a.stage_e_override;
                        const bNeeds = b.needs_verification || b.stage_e_override;
                        valA = aNeeds ? '0' : '1';
                        valB = bNeeds ? '0' : '1';
                        break;
                    case 'diagnose_pdn_code':
                        valA = (a.diagnose_pdn_code || '').toLowerCase();
                        valB = (b.diagnose_pdn_code || '').toLowerCase();
                        break;
                    case 'coupon_code':
                        valA = (a.coupon_code || '').toLowerCase();
                        valB = (b.coupon_code || '').toLowerCase();
                        break;
                    default:
                        valA = (a[column] || '').toString().toLowerCase();
                        valB = (b[column] || '').toString().toLowerCase();
                }
                if (valA < valB) return sortDirection === 'asc' ? -1 : 1;
                if (valA > valB) return sortDirection === 'asc' ? 1 : -1;
                return 0;
            });

            // Update sort indicators in headers
            document.querySelectorAll('.sort-indicator').forEach(el => {
                if (el.dataset.col === column) {
                    el.textContent = sortDirection === 'asc' ? '↑' : '↓';
                } else {
                    el.textContent = '';
                }
            });

            // Update aria-sort attributes for accessibility
            document.querySelectorAll('th[aria-sort]').forEach(th => {
                if (th.id === 'th-' + column) {
                    th.setAttribute('aria-sort', sortDirection === 'asc' ? 'ascending' : 'descending');
                } else {
                    th.setAttribute('aria-sort', 'none');
                }
            });

            renderTable(currentData);
            updateUrlState({ sort: column, order: sortDirection });
        }

        async function exportTableCSV() {
            // Apply current filters to export only visible data
            const searchTerm = (document.getElementById('tableSearchInput')?.value || '').toLowerCase();

            const exportData = currentData.filter(user => {
                if (!searchTerm) return true;
                const fullName = ((user.first_name || '') + ' ' + (user.last_name || '')).trim().toLowerCase();
                return user.email.toLowerCase().includes(searchTerm) ||
                    fullName.includes(searchTerm) ||
                    (user.first_name && user.first_name.toLowerCase().includes(searchTerm)) ||
                    (user.last_name && user.last_name.toLowerCase().includes(searchTerm));
            });

            const headers = ['מזהה מערכת', 'שם', 'אימייל', 'תאריך', 'קוד מערכת', 'אימות', 'ניתוח קול', 'קוד מאבחן', 'הערות', 'עדכון קוד פדן', 'קופון'];
            const rows = exportData.map(u => [
                u.user_id || '', ((u.first_name || '') + ' ' + (u.last_name || '')).trim(),
                u.email, u.date, u.pdn_code || '',
                u.needs_verification ? 'נדרש אימות' : 'תקין',
                u.pdn_voice_code || '',
                u.diagnose_pdn_code || '', u.diagnose_comments || '', u.pdn_update_comments || '',
                u.coupon_code || ''
            ]);

            const BOM = '\uFEFF';
            const csv = BOM + [headers.join(','), ...rows.map(r => r.map(v => `"${(v||'').replace(/"/g, '""')}"`).join(','))].join('\n');
            const blob = new Blob([csv], {type: 'text/csv;charset=utf-8'});
            const url = URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = url;
            link.download = `pdn_admin_export_${new Date().toISOString().slice(0,10)}.csv`;
            link.click();
            URL.revokeObjectURL(url);
            showNotification(`קובץ CSV יוצא בהצלחה (${exportData.length} שורות)`, 'success');
        }

        async function sendAlgorithmReport() {
            if (!sessionToken) {
                window.location.href = '/pdn-admin/';
                return;
            }

            try {
                showNotification('שולח דוח אלגוריתם...', 'info');
                const response = await fetch(`/pdn-admin/send_algorithm_report?session_token=${sessionToken}`, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'}
                });

                if (response.ok) {
                    const data = await response.json();
                    showNotification(data.message || 'דוח נשלח בהצלחה', 'success');
                } else if (response.status === 401) {
                    redirectToLogin();
                } else {
                    const errorData = await response.json().catch(() => ({}));
                    throw new Error(errorData.error || 'Failed to send report');
                }
            } catch (error) {
                logError('sendAlgorithmReport', error);
                showNotification(`שגיאה בשליחת הדוח: ${error.message}`, 'error');
            }
        }

        async function showHealthStatus() {
            if (!sessionToken) return;

            try {
                const resp = await fetch(`/pdn-admin/health_status?session_token=${sessionToken}`);
                if (!resp.ok) {
                    if (resp.status === 401) { redirectToLogin(); return; }
                    // Graceful degradation for 404 or other errors
                    const dot = document.getElementById('healthDot');
                    if (dot) dot.style.background = '#94a3b8';
                    showNotification('בדיקת בריאות לא זמינה כרגע', 'warning');
                    return;
                }
                const h = resp.json ? await resp.json() : {};

                const statusColor = h.status === 'critical' ? '#dc2626' : h.status === 'warning' ? '#f59e0b' : '#22c55e';
                const statusEmoji = h.status === 'critical' ? '🔴' : h.status === 'warning' ? '🟡' : '🟢';
                const statusText = h.status === 'critical' ? 'CRITICAL' : h.status === 'warning' ? 'WARNING' : 'ALL SYSTEMS OPERATIONAL';

                // Update health dot in header
                const dot = document.getElementById('healthDot');
                if (dot) dot.style.background = statusColor;

                const cpuBar = Math.min(100, h.cpu_percent || 0);
                const memBar = Math.min(100, h.memory_percent || 0);
                const storBar = Math.min(100, ((h.storage_used_mb || 0) / (h.storage_limit_mb || 1024)) * 100);

                const existing = document.getElementById('healthPopup');
                if (existing) existing.remove();

                const overlay = document.createElement('div');
                overlay.id = 'healthPopup';
                overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.5);backdrop-filter:blur(4px);z-index:9999;display:flex;align-items:center;justify-content:center;padding:16px;';
                overlay.onclick = (e) => { if (e.target === overlay) overlay.remove(); };

                overlay.innerHTML = `
                    <div style="background:white;border-radius:16px;padding:28px;max-width:500px;width:100%;box-shadow:0 24px 48px rgba(0,0,0,0.2);direction:rtl;max-height:90vh;overflow-y:auto;">
                        <!-- Header -->
                        <div style="text-align:center;margin-bottom:20px;">
                            <div style="font-size:2rem;margin-bottom:8px;">${statusEmoji}</div>
                            <h3 style="font-size:1rem;font-weight:700;color:${statusColor};margin-bottom:4px;">${statusText}</h3>
                            <p style="font-size:11px;color:#64748b;">PDN Chat — Production | ${h.region || 'Frankfurt'} | ${h.plan || 'Starter'}</p>
                            <p style="font-size:11px;color:#94a3b8;">${new Date().toLocaleDateString('he-IL')} | ${h.service_url || ''}</p>
                        </div>

                        <!-- CPU -->
                        <div style="margin-bottom:16px;">
                            <div style="display:flex;justify-content:space-between;margin-bottom:4px;">
                                <span style="font-size:12px;font-weight:600;color:#1e293b;">CPU</span>
                                <span style="font-size:12px;color:#64748b;">${h.cpu_percent || 0}%</span>
                            </div>
                            <div style="height:8px;background:#f1f5f9;border-radius:4px;overflow:hidden;">
                                <div style="height:100%;width:${cpuBar}%;background:${cpuBar > 70 ? '#f59e0b' : '#0b2e6b'};border-radius:4px;"></div>
                            </div>
                        </div>

                        <!-- Memory -->
                        <div style="margin-bottom:16px;">
                            <div style="display:flex;justify-content:space-between;margin-bottom:4px;">
                                <span style="font-size:12px;font-weight:600;color:#1e293b;">Memory</span>
                                <span style="font-size:12px;color:#64748b;">${h.memory_used_mb || 0} MB / ${h.memory_total_mb || 512} MB (${h.memory_percent || 0}%)</span>
                            </div>
                            <div style="height:8px;background:#f1f5f9;border-radius:4px;overflow:hidden;">
                                <div style="height:100%;width:${memBar}%;background:${memBar > 80 ? '#f59e0b' : '#0b2e6b'};border-radius:4px;"></div>
                            </div>
                        </div>

                        <!-- Storage -->
                        <div style="margin-bottom:16px;">
                            <div style="display:flex;justify-content:space-between;margin-bottom:4px;">
                                <span style="font-size:12px;font-weight:600;color:#1e293b;">Storage</span>
                                <span style="font-size:12px;color:#64748b;">${h.storage_used_mb || 0} MB / ${h.storage_limit_mb || 1024} MB (${Math.round(storBar)}%)</span>
                            </div>
                            <div style="height:8px;background:#f1f5f9;border-radius:4px;overflow:hidden;">
                                <div style="height:100%;width:${storBar}%;background:${storBar > 70 ? '#f59e0b' : '#0b2e6b'};border-radius:4px;"></div>
                            </div>
                            <button onclick="document.getElementById('healthPopup').remove(); compressOldAudio();" style="margin-top:8px;padding:5px 12px;font-size:10px;font-weight:600;background:#0b2e6b;color:white;border:none;border-radius:6px;cursor:pointer;">
                                <i class="fas fa-compress-alt"></i> דחס הקלטות ישנות
                            </button>
                        </div>

                        <!-- Info Grid -->
                        <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:16px;">
                            <div style="background:#f8fafc;border-radius:8px;padding:10px;text-align:center;">
                                <div style="font-size:1.2rem;font-weight:800;color:#0b2e6b;">${h.active_sessions || 0}</div>
                                <div style="font-size:10px;color:#64748b;">Sessions</div>
                            </div>
                            <div style="background:#f8fafc;border-radius:8px;padding:10px;text-align:center;">
                                <div style="font-size:1.2rem;font-weight:800;color:#0b2e6b;">${h.uptime_hours || 0}h</div>
                                <div style="font-size:10px;color:#64748b;">Uptime</div>
                            </div>
                        </div>

                        <!-- Error Logs -->
                        <div style="margin-top:16px;background:${(h.errors_24h || 0) > 0 ? '#fef2f2' : '#f0fdf4'};border:1px solid ${(h.errors_24h || 0) > 0 ? '#fecaca' : '#bbf7d0'};border-radius:8px;padding:12px;">
                            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;">
                                <span style="font-size:12px;font-weight:600;color:${(h.errors_24h || 0) > 0 ? '#991b1b' : '#065f46'};">
                                    ${(h.errors_24h || 0) > 0 ? '⚠️' : '✓'} Errors (24h)
                                </span>
                                <span style="font-size:14px;font-weight:800;color:${(h.errors_24h || 0) > 0 ? '#dc2626' : '#065f46'};">${h.errors_24h || 0}</span>
                            </div>
                            ${h.last_error ? `<div style="font-size:10px;color:#64748b;margin-top:4px;word-break:break-all;">Last: ${h.last_error} (${h.last_error_time || ''})</div>` : '<div style="font-size:10px;color:#065f46;">No errors</div>'}
                        </div>

                        <!-- Close -->
                        <div style="text-align:center;margin-top:16px;">
                            <button onclick="document.getElementById('healthPopup').remove();" style="padding:8px 20px;background:#f1f5f9;color:#475569;border:1px solid #e2e8f0;border-radius:8px;font-size:12px;font-weight:600;cursor:pointer;">סגור</button>
                        </div>
                    </div>
                `;

                document.body.appendChild(overlay);
            } catch (error) {
                showNotification('לא ניתן לטעון נתוני בריאות', 'error');
            }
        }

        async function compressOldAudio() {
            if (!sessionToken) {
                window.location.href = '/pdn-admin/';
                return;
            }

            // First check storage info
            try {
                showNotification('בודק נפח אחסון...', 'info');
                const checkResp = await fetch(`/pdn-admin/compress_old_audio?session_token=${sessionToken}`, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ check_only: true })
                });

                if (!checkResp.ok) {
                    if (checkResp.status === 401) { redirectToLogin(); return; }
                    throw new Error('Failed to check storage');
                }

                const checkData = await checkResp.json();
                const s = checkData.storage;
                const usagePct = Math.round((s.total_mb / s.disk_limit_mb) * 100);

                // Show storage info in a popup instead of plain text prompt
                const existing = document.getElementById('storagePopup');
                if (existing) existing.remove();

                const overlay = document.createElement('div');
                overlay.id = 'storagePopup';
                overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.5);backdrop-filter:blur(4px);z-index:9999;display:flex;align-items:center;justify-content:center;padding:16px;';

                const barColor = usagePct > 80 ? '#dc2626' : usagePct > 50 ? '#f59e0b' : '#0b2e6b';

                overlay.innerHTML = `
                    <div style="background:white;border-radius:16px;padding:28px;max-width:440px;width:100%;box-shadow:0 24px 48px rgba(0,0,0,0.2);direction:rtl;">
                        <h3 style="font-size:1.1rem;font-weight:700;color:#0b2e6b;margin-bottom:20px;text-align:center;">
                            <i class="fas fa-hdd" style="margin-left:8px;"></i> נפח אחסון
                        </h3>

                        <!-- Usage bar -->
                        <div style="margin-bottom:20px;">
                            <div style="display:flex;justify-content:space-between;margin-bottom:6px;">
                                <span style="font-size:13px;font-weight:600;color:#1e293b;">${s.total_mb} MB</span>
                                <span style="font-size:13px;color:#64748b;">מתוך ${s.disk_limit_mb} MB</span>
                            </div>
                            <div style="height:12px;background:#f1f5f9;border-radius:6px;overflow:hidden;">
                                <div style="height:100%;width:${usagePct}%;background:${barColor};border-radius:6px;transition:width 0.3s;"></div>
                            </div>
                            <div style="text-align:left;margin-top:4px;font-size:11px;color:#64748b;">${usagePct}% בשימוש</div>
                        </div>

                        <!-- Breakdown -->
                        <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:20px;">
                            <div style="background:#f8fafc;border-radius:10px;padding:12px;text-align:center;">
                                <div style="font-size:1.2rem;font-weight:800;color:#0b2e6b;">${s.wav_mb} MB</div>
                                <div style="font-size:11px;color:#64748b;">WAV קבצי</div>
                            </div>
                            <div style="background:#f8fafc;border-radius:10px;padding:12px;text-align:center;">
                                <div style="font-size:1.2rem;font-weight:800;color:#0b2e6b;">${s.mp3_mb} MB</div>
                                <div style="font-size:11px;color:#64748b;">MP3 קבצי</div>
                            </div>
                        </div>

                        <!-- Old files info -->
                        <div style="background:${s.wav_old_count > 0 ? '#fef3c7' : '#f0fdf4'};border:1px solid ${s.wav_old_count > 0 ? '#f59e0b' : '#86efac'};border-radius:10px;padding:12px;margin-bottom:20px;text-align:center;">
                            <div style="font-size:14px;font-weight:600;color:${s.wav_old_count > 0 ? '#92400e' : '#065f46'};">
                                ${s.wav_old_count > 0
                                    ? `<i class="fas fa-compress-alt"></i> ${s.wav_old_count} קבצי WAV ישנים (${s.wav_old_mb} MB) לדחיסה`
                                    : '<i class="fas fa-check-circle"></i> אין קבצים לדחיסה — הכל מעודכן'}
                            </div>
                        </div>

                        <!-- Buttons -->
                        <div style="display:flex;gap:8px;justify-content:center;">
                            ${s.wav_old_count > 0 ? `
                                <button id="storageCompressBtn" style="padding:10px 20px;background:#0b2e6b;color:white;border:none;border-radius:8px;font-size:13px;font-weight:600;cursor:pointer;">
                                    <i class="fas fa-compress-alt"></i> דחס ${s.wav_old_count} קבצים
                                </button>
                            ` : ''}
                            <button onclick="document.getElementById('storagePopup').remove();" style="padding:10px 20px;background:#f1f5f9;color:#475569;border:1px solid #e2e8f0;border-radius:8px;font-size:13px;font-weight:600;cursor:pointer;">
                                סגור
                            </button>
                        </div>
                    </div>
                `;

                document.body.appendChild(overlay);
                overlay.onclick = (e) => { if (e.target === overlay) overlay.remove(); };

                // If there are files to compress, wire up the button
                if (s.wav_old_count > 0) {
                    document.getElementById('storageCompressBtn').onclick = async () => {
                        const btn = document.getElementById('storageCompressBtn');
                        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> דוחס...';
                        btn.disabled = true;

                        const response = await fetch(`/pdn-admin/compress_old_audio?session_token=${sessionToken}`, {
                            method: 'POST',
                            headers: {'Content-Type': 'application/json'},
                            body: JSON.stringify({})
                        });

                        overlay.remove();

                        if (response.ok) {
                            const data = await response.json();
                            const newUsage = Math.round((data.storage.total_mb / data.storage.disk_limit_mb) * 100);
                            showNotification(`${data.message} | אחסון: ${data.storage.total_mb} MB (${newUsage}%)`, 'success');
                        } else {
                            const errorData = await response.json().catch(() => ({}));
                            showNotification(`שגיאה: ${errorData.error || 'Compression failed'}`, 'error');
                        }
                    };
                }

            } catch (error) {
                logError('compressOldAudio', error);
                showNotification(`שגיאה: ${error.message}`, 'error');
            }
        }

        async function viewJourney(email) {
            try {
                const response = await fetch(`/pdn-admin/user/journey/${email}?session_token=${sessionToken}`);
                if (!response.ok) throw new Error('Failed to load journey');
                const data = await response.json();
                displayJourney(data);
            } catch (error) {
                logError('loadJourney', error);
                showNotification('שגיאה בטעינת מסע משתמש', 'error');
            }
        }

        function displayJourney(data) {
            const container = document.getElementById('journeyContent');
            const m = data.metrics;

            let html = `
            <div class="p-5 bg-gradient-to-br from-blue-900 to-blue-800 rounded-2xl text-white text-center mb-6">
                <div class="text-lg font-bold mb-1">${data.user_name}</div>
                <div class="text-sm opacity-80">${data.email}</div>
                <div class="mt-2 inline-block px-3 py-1 rounded-full text-sm font-bold bg-white/20">${data.pdn_code}</div>
            </div>

            <div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
                <div class="bg-blue-50 rounded-xl p-3 text-center border border-blue-100">
                    <div class="text-xl font-bold text-blue-900">${m.days_since_diagnosis !== null ? m.days_since_diagnosis : '—'}</div>
                    <div class="text-[10px] text-gray-600 mt-1">ימים מאז אבחון</div>
                </div>
                <div class="bg-green-50 rounded-xl p-3 text-center border border-green-100">
                    <div class="text-xl font-bold text-green-700">${m.total_conversations}</div>
                    <div class="text-[10px] text-gray-600 mt-1">סה"כ שיחות</div>
                </div>
                <div class="bg-purple-50 rounded-xl p-3 text-center border border-purple-100">
                    <div class="text-xl font-bold text-purple-700">${m.active_days}</div>
                    <div class="text-[10px] text-gray-600 mt-1">ימים פעילים</div>
                </div>
                <div class="bg-amber-50 rounded-xl p-3 text-center border border-amber-100">
                    <div class="text-xl font-bold text-amber-700">${m.avg_conversations_per_active_day}</div>
                    <div class="text-[10px] text-gray-600 mt-1">ממוצע שיחות/יום</div>
                </div>
            </div>`;

            // Timeline
            if (data.events.length > 0) {
                html += '<h3 class="text-sm font-semibold text-gray-700 mb-3">ציר זמן</h3>';
                html += '<div class="relative pr-6 border-r-2 border-blue-200 space-y-4">';
                data.events.forEach(event => {
                    const iconMap = { diagnosis: 'fa-stethoscope text-blue-600', conversation: 'fa-comments text-green-600', binat_usage: 'fa-robot text-purple-600' };
                    const bgMap = { diagnosis: 'bg-blue-50 border-blue-200', conversation: 'bg-green-50 border-green-200', binat_usage: 'bg-purple-50 border-purple-200' };
                    const icon = iconMap[event.type] || 'fa-circle text-gray-400';
                    const bg = bgMap[event.type] || 'bg-gray-50 border-gray-200';

                    html += `
                    <div class="relative">
                        <div class="absolute -right-[21px] top-2 w-4 h-4 rounded-full bg-white border-2 border-blue-400 flex items-center justify-center">
                            <div class="w-2 h-2 rounded-full bg-blue-400"></div>
                        </div>
                        <div class="p-3 rounded-lg border ${bg}">
                            <div class="flex items-center justify-between">
                                <div class="flex items-center gap-2">
                                    <i class="fas ${icon} text-sm"></i>
                                    <span class="text-sm font-medium text-gray-800">${event.label}</span>
                                </div>
                                <span class="text-xs text-gray-500">${event.date}</span>
                            </div>
                            ${event.detail ? `<div class="text-xs text-gray-500 mt-1">${event.detail}</div>` : ''}
                        </div>
                    </div>`;
                });
                html += '</div>';
            } else {
                html += '<p class="text-sm text-gray-500 text-center py-6">אין אירועים עדיין</p>';
            }

            container.innerHTML = html;
            document.getElementById('journeyModal').style.display = 'flex';
            setTimeout(() => { document.getElementById('journeyModal').querySelector('button, input')?.focus(); }, 100);
        }

        function showNotification(message, type = 'info') {
            // Create notification element
            const notification = document.createElement('div');

            // Calculate offset based on existing notifications
            const existingNotifications = document.querySelectorAll('.notification-item');
            const offset = existingNotifications.length * 90;

            notification.className = `
    fixed left-6 z-[9999] p-6 rounded-xl shadow-2xl transition-all duration-500 transform -translate-x-full border-2
        `;
            notification.style.bottom = `${24 + offset}px`;

            // Enhanced styling based on type
            let bgColor, borderColor, icon, textColor;
            switch (type) {
                case 'success':
                    bgColor = 'bg-green-50';
                    borderColor = 'border-green-500';
                    icon = 'fa-check-circle';
                    textColor = 'text-green-800';
                    break;
                case 'error':
                    bgColor = 'bg-red-50';
                    borderColor = 'border-red-500';
                    icon = 'fa-exclamation-triangle';
                    textColor = 'text-red-800';
                    break;
                case 'warning':
                    bgColor = 'bg-yellow-50';
                    borderColor = 'border-yellow-500';
                    icon = 'fa-exclamation-circle';
                    textColor = 'text-yellow-800';
                    break;
                default:
                    bgColor = 'bg-blue-50';
                    borderColor = 'border-blue-500';
                    icon = 'fa-info-circle';
                    textColor = 'text-blue-800';
            }

            notification.className += ` ${bgColor} ${borderColor}`;
            notification.innerHTML = `

            <div class="flex items-start space-x-3 space-x-reverse">
                <div class="flex-shrink-0">
                    <i class="fas ${icon} text-xl ${textColor}"></i>
                </div>
                <div class="flex-1 min-w-0">
                    <p class="text-sm font-medium ${textColor} leading-5">${message}</p>
                </div>
                <div class="flex-shrink-0">
                    <button onclick="this.closest('.notification-item').remove()"
                            class="inline-flex text-gray-400 hover:text-gray-600 transition-colors duration-200">
                        <i class="fas fa-times mr-2 text-lg"></i>
                    </button>
                </div>
            </div>

        `;

            // Add a unique class for easier targeting
            notification.classList.add('notification-item');

            document.body.appendChild(notification);

            // Animate in with bounce effect
            setTimeout(() => {
                notification.classList.remove('-translate-x-full');
                notification.classList.add('animate-bounce');
                setTimeout(() => {
                    notification.classList.remove('animate-bounce');
                }, 1000);
            }, 100);

            // Auto remove after 8 seconds (increased from 5)
            setTimeout(() => {
                notification.classList.add('-translate-x-full');
                setTimeout(() => {
                    if (notification.parentElement) {
                        notification.remove();
                    }
                }, 500);
            }, 8000);

            // Add sound for error notifications
            if (type === 'error') {
                // Create a simple beep sound
                const audioContext = new (window.AudioContext || window.webkitAudioContext)();
                const oscillator = audioContext.createOscillator();
                const gainNode = audioContext.createGain();

                oscillator.connect(gainNode);
                gainNode.connect(audioContext.destination);

                oscillator.frequency.setValueAtTime(800, audioContext.currentTime);
                oscillator.frequency.setValueAtTime(600, audioContext.currentTime + 0.1);

                gainNode.gain.setValueAtTime(0.1, audioContext.currentTime);
                gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.2);

                oscillator.start(audioContext.currentTime);
                oscillator.stop(audioContext.currentTime + 0.2);
            }
        }

        // Reset loading state for a specific row (no-op, kept for call compatibility)
        function resetRowLoadingState(email, buttonType) {
            // Previously used Alpine.js - now handled by re-render
        }

    // =============================================
    // User Management (Chat Users CRUD)
    // =============================================

    let chatUsersData = [];
    let availablePdnCodes = [];
    let deleteUserEmail = null;

    async function loadChatUsers() {
        const tbody = document.getElementById('chatUsersTableBody');
        tbody.innerHTML = '<tr><td colspan="5" class="text-center py-8 text-gray-400"><i class="fas fa-spinner fa-spin ml-2"></i> טוען...</td></tr>';

        try {
            const [usersResp, codesResp] = await Promise.all([
                fetch(`/pdn-admin/users?session_token=${sessionToken}`),
                fetch(`/pdn-admin/users/pdn-codes?session_token=${sessionToken}`)
            ]);

            if (usersResp.status === 401 || codesResp.status === 401) {
                redirectToLogin();
                return;
            }

            if (!usersResp.ok) throw new Error('Failed to load users');
            if (!codesResp.ok) throw new Error('Failed to load PDN codes');

            const usersData = await usersResp.json();
            const codesData = await codesResp.json();

            chatUsersData = usersData.users || [];
            availablePdnCodes = codesData.codes || [];

            renderChatUsersTable();
        } catch (error) {
            logError('loadChatUsers', error);
            tbody.innerHTML = '<tr><td colspan="5" class="text-center py-8 text-red-500">שגיאה בטעינת משתמשים</td></tr>';
        }
    }

    function renderChatUsersTable() {
        const tbody = document.getElementById('chatUsersTableBody');
        document.getElementById('chatUserCount').textContent = `סה"כ: ${chatUsersData.length}`;

        if (chatUsersData.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" class="text-center py-8 text-gray-400"><i class="fas fa-inbox text-3xl mb-2 block"></i>אין משתמשים</td></tr>';
            return;
        }

        tbody.innerHTML = chatUsersData.map(user => {
            const accessDays = user.access_days || 0;
            let accessDisplay = accessDays === 0 ? '<span style="color:#6b7280">-</span>' : `${accessDays}`;
            // Show days remaining if access_days is set
            if (accessDays > 0 && user.created_at) {
                try {
                    const created = new Date(user.created_at.replace(' ', 'T'));
                    const elapsed = Math.floor((Date.now() - created.getTime()) / 86400000);
                    const remaining = accessDays - elapsed;
                    if (remaining <= 0) {
                        accessDisplay = `<span style="color:#dc2626;font-weight:600">${accessDays} (פג)</span>`;
                    } else if (remaining <= 7) {
                        accessDisplay = `<span style="color:#d97706;font-weight:600">${accessDays} (${remaining} נותרו)</span>`;
                    } else {
                        accessDisplay = `${accessDays} <span style="color:#6b7280;font-size:11px">(${remaining} נותרו)</span>`;
                    }
                } catch(e) { /* ignore date parse errors */ }
            }
            return `
            <tr class="border-b border-gray-100 hover:bg-gray-50 transition-colors">
                <td class="px-4 py-3 font-medium text-gray-900" dir="ltr">${user.email}</td>
                <td class="px-4 py-3 text-gray-800">${user.name}</td>
                <td class="px-4 py-3 text-center text-gray-700">${user.gender === 'male' ? 'גבר' : user.gender === 'female' ? 'אישה' : '-'}</td>
                <td class="px-4 py-3 text-center">
                    <span class="px-2 py-1 rounded-full text-xs font-medium ${getPdnBadgeColor(user.pdn_code)}">${user.pdn_code}</span>
                </td>
                <td class="px-4 py-3 text-center text-gray-700">${user.daily_conversation_limit}</td>
                <td class="px-4 py-3 text-center text-gray-700">${accessDisplay}</td>
                <td class="px-4 py-3 text-center text-gray-500 text-xs">${user.created_at || '-'}</td>
                <td class="px-4 py-3 text-center text-xs">${
                    user.terms_accepted_at
                        ? `<span style="color:#15803d;font-weight:600;" title="${user.terms_accepted_at}"><i class="fas fa-check-circle" style="margin-left:4px;"></i>${user.terms_accepted_at.slice(0,10)}</span>`
                        : '<span style="color:#9ca3af;">-</span>'
                }</td>
                <td class="px-4 py-3 text-center">
                    <div class="flex items-center justify-center gap-2">
                        <button onclick="openEditUserModal('${user.email}')"
                                class="p-2 text-blue-600 hover:bg-blue-50 rounded-lg transition-colors" title="ערוך">
                            <i class="fas fa-edit"></i>
                        </button>
                        <button onclick="openDeleteUserDialog('${user.email}')"
                                class="p-2 text-red-600 hover:bg-red-50 rounded-lg transition-colors" title="מחק">
                            <i class="fas fa-trash-alt"></i>
                        </button>
                    </div>
                </td>
            </tr>
        `; }).join('');
    }

    function populatePdnCodeDropdown(selectedCode) {
        const select = document.getElementById('userFormPdnCode');
        select.innerHTML = '<option value="">בחר קוד PDN...</option>';
        availablePdnCodes.forEach(code => {
            const option = document.createElement('option');
            option.value = code;
            option.textContent = code.toUpperCase();
            if (code === selectedCode) option.selected = true;
            select.appendChild(option);
        });
    }

    function openAddUserModal() {
        document.getElementById('userFormMode').value = 'add';
        document.getElementById('userFormOriginalEmail').value = '';
        document.getElementById('userFormTitle').innerHTML = '<i class="fas fa-user-plus ml-2 text-blue-900"></i> הוסף משתמש';
        document.getElementById('userFormEmail').value = '';
        document.getElementById('userFormEmail').disabled = false;
        document.getElementById('userFormPassword').value = '';
        document.getElementById('userFormPassword').required = true;
        document.getElementById('userFormPassword').placeholder = 'סיסמה (חובה)';
        document.getElementById('userFormName').value = '';
        document.getElementById('userFormLimit').value = 15;
        document.getElementById('userFormAccessDays').value = 0;
        // Hide terms audit row for new users
        const termsAudit = document.querySelector('.form-group-terms-audit');
        if (termsAudit) termsAudit.style.display = 'none';
        populatePdnCodeDropdown('');
        document.getElementById('userFormModal').style.display = 'flex';
        setTimeout(() => document.getElementById('userFormEmail').focus(), 100);
    }

    function openEditUserModal(email) {
        const user = chatUsersData.find(u => u.email === email);
        if (!user) return;

        document.getElementById('userFormMode').value = 'edit';
        document.getElementById('userFormOriginalEmail').value = email;
        document.getElementById('userFormTitle').innerHTML = '<i class="fas fa-user-edit ml-2 text-blue-900"></i> ערוך משתמש';
        document.getElementById('userFormEmail').value = email;
        document.getElementById('userFormEmail').disabled = true;
        document.getElementById('userFormPassword').value = '';
        document.getElementById('userFormPassword').required = false;
        document.getElementById('userFormPassword').placeholder = 'השאר ריק לשמירת הסיסמה הנוכחית';
        document.getElementById('userFormName').value = user.name;
        document.getElementById('userFormGender').value = user.gender || '';
        document.getElementById('userFormLimit').value = user.daily_conversation_limit;
        document.getElementById('userFormAccessDays').value = user.access_days || 0;
        populatePdnCodeDropdown(user.pdn_code);

        // Show terms acceptance info (read-only)
        const termsInfo = document.getElementById('userFormTermsInfo');
        if (termsInfo) {
            if (user.terms_accepted_at) {
                termsInfo.innerHTML = `<i class="fas fa-check-circle" style="color:#15803d;margin-left:6px;"></i><span style="color:#15803d;font-weight:600;">אושרו ב-${user.terms_accepted_at}</span>`;
            } else {
                termsInfo.innerHTML = `<span style="color:#9ca3af;">טרם אישר תנאים</span>`;
            }
            termsInfo.closest('.form-group-terms-audit').style.display = 'block';
        }
        document.getElementById('userFormModal').style.display = 'flex';
        setTimeout(() => document.getElementById('userFormName').focus(), 100);
    }

    async function handleUserFormSubmit(e) {
        e.preventDefault();

        const mode = document.getElementById('userFormMode').value;
        const email = document.getElementById('userFormEmail').value.trim().toLowerCase();
        const password = document.getElementById('userFormPassword').value.trim();
        const name = document.getElementById('userFormName').value.trim();
        const gender = document.getElementById('userFormGender').value;
        const pdnCode = document.getElementById('userFormPdnCode').value;
        const limit = parseInt(document.getElementById('userFormLimit').value) || 15;
        const accessDays = parseInt(document.getElementById('userFormAccessDays').value) || 0;

        // Frontend validation
        if (!email || !name || !pdnCode || !gender) {
            showNotification('אנא מלא את כל השדות הנדרשים', 'warning');
            return;
        }

        if (mode === 'add' && !password) {
            showNotification('סיסמה נדרשת להוספת משתמש חדש', 'warning');
            return;
        }

        // Email format validation
        const emailRegex = /^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$/;
        if (mode === 'add' && !emailRegex.test(email)) {
            showNotification('פורמט אימייל לא תקין', 'warning');
            return;
        }

        const adminPassword = 'admin'; // not checked server-side, session_token handles auth

        showLoading();
        try {
            let url, method, body;

            if (mode === 'add') {
                url = `/pdn-admin/users?session_token=${sessionToken}`;
                method = 'POST';
                body = { email, password, name, gender, pdn_code: pdnCode, daily_conversation_limit: limit, access_days: accessDays, admin_password: adminPassword };
            } else {
                const originalEmail = document.getElementById('userFormOriginalEmail').value;
                url = `/pdn-admin/users/${encodeURIComponent(originalEmail)}?session_token=${sessionToken}`;
                method = 'PUT';
                body = { name, gender, pdn_code: pdnCode, daily_conversation_limit: limit, access_days: accessDays, admin_password: adminPassword };
                if (password) body.password = password;
            }

            const response = await fetch(url, {
                method,
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            });

            if (response.status === 401) {
                const data = await response.json();
                if (data.error === 'Invalid admin password') {
                    showNotification('סיסמת מנהל שגויה', 'error');
                } else {
                    redirectToLogin();
                }
                return;
            }

            if (!response.ok) {
                const data = await response.json();
                throw new Error(data.error || 'Operation failed');
            }

            closeModal('userFormModal');
            showNotification(mode === 'add' ? 'משתמש נוסף בהצלחה' : 'משתמש עודכן בהצלחה', 'success');
            await loadChatUsers();
        } catch (error) {
            logError('userFormSubmit', error);
            showNotification(`שגיאה: ${error.message}`, 'error');
        } finally {
            hideLoading();
        }
    }

    function openDeleteUserDialog(email) {
        deleteUserEmail = email;
        document.getElementById('deleteUserMessage').textContent = `האם אתה בטוח שברצונך למחוק את המשתמש ${email}?`;
        document.getElementById('deleteUserModal').style.display = 'flex';
    }

    async function confirmDeleteUser() {
        if (!deleteUserEmail) return;

        closeModal('deleteUserModal');

        const adminPassword = 'admin'; // not checked server-side, session_token handles auth

        showLoading();
        try {
            const response = await fetch(`/pdn-admin/users/${encodeURIComponent(deleteUserEmail)}?session_token=${sessionToken}`, {
                method: 'DELETE',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ admin_password: adminPassword })
            });

            if (response.status === 401) {
                const data = await response.json();
                if (data.error === 'Invalid admin password') {
                    showNotification('סיסמת מנהל שגויה', 'error');
                } else {
                    redirectToLogin();
                }
                return;
            }

            if (!response.ok) {
                const data = await response.json();
                throw new Error(data.error || 'Delete failed');
            }

            showNotification('משתמש נמחק בהצלחה', 'success');
            await loadChatUsers();
        } catch (error) {
            logError('deleteUser', error);
            showNotification(`שגיאה במחיקת משתמש: ${error.message}`, 'error');
        } finally {
            hideLoading();
            deleteUserEmail = null;
        }
    }
