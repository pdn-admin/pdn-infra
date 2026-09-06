let isDarkMode = false;

function toggleBinatPassword() {
    const input = document.getElementById('password');
    const icon  = document.getElementById('binatEyeIcon');
    if (input.type === 'password') {
        input.type = 'text';
        icon.className = 'fas fa-eye-slash';
    } else {
        input.type = 'password';
        icon.className = 'fas fa-eye';
    }
}

function showError(message) {
    const loginError = document.getElementById('loginError');
    loginError.querySelector('span').textContent = message;
    loginError.style.display = 'flex';
}

function hideError() {
    document.getElementById('loginError').style.display = 'none';
}

function showTermsError() {
    document.getElementById('termsError').style.display = 'flex';
}

function hideTermsError() {
    document.getElementById('termsError').style.display = 'none';
}

// Returns true when all fields are valid AND checkbox is checked
function validateForm() {
    const email    = document.getElementById('username').value.trim();
    const password = document.getElementById('password').value.trim();
    const agreed   = document.getElementById('termsCheckbox').checked;
    const btn      = document.getElementById('submitButton');

    const valid = email.length >= 5 && email.includes('@') && password.length >= 1 && agreed;
    btn.disabled = !valid;
    return valid;
}

// Theme toggle
function toggleTheme() {
    isDarkMode = !isDarkMode;
    document.documentElement.setAttribute('data-theme', isDarkMode ? 'dark' : 'light');
    document.querySelector('.theme-toggle i').className = isDarkMode ? 'fas fa-sun' : 'fas fa-moon';
    localStorage.setItem('darkMode', isDarkMode);
}

// Terms modal helpers
function openTermsModal() {
    document.getElementById('termsModal').style.display = 'flex';
    document.getElementById('termsModal').querySelector('.terms-accept-btn').focus();
}

function closeTermsModal() {
    document.getElementById('termsModal').style.display = 'none';
}

// "קראתי ומסכים/ה" inside the modal — check the box and close
function acceptTermsFromModal() {
    document.getElementById('termsCheckbox').checked = true;
    hideTermsError();
    validateForm();
    closeTermsModal();
}

// Close modal on backdrop click
document.addEventListener('DOMContentLoaded', function () {
    document.getElementById('termsModal').addEventListener('click', function (e) {
        if (e.target === this) closeTermsModal();
    });

    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') closeTermsModal();
    });

    // Input listeners
    document.getElementById('username').addEventListener('input', function () { hideError(); validateForm(); });
    document.getElementById('password').addEventListener('input', function () { hideError(); validateForm(); });
    document.getElementById('termsCheckbox').addEventListener('change', function () {
        hideTermsError();
        validateForm();
    });

    // Focus username
    document.getElementById('username').focus();

    // Load theme
    const savedTheme = localStorage.getItem('darkMode');
    if (savedTheme === 'true') {
        isDarkMode = true;
        document.documentElement.setAttribute('data-theme', 'dark');
        document.querySelector('.theme-toggle i').className = 'fas fa-sun';
    }

    // Auto-redirect if already logged in
    const storedUsername = sessionStorage.getItem('binat_username');
    const storedUserId   = sessionStorage.getItem('binat_user_id');
    const storedPdnCode  = sessionStorage.getItem('binat_pdn_code');
    if (storedUsername && storedUserId && storedPdnCode) {
        // Check if we were just redirected back here (redirect loop guard)
        const redirectCount = parseInt(sessionStorage.getItem('_binat_redirect_count') || '0');
        if (redirectCount >= 1) {
            // Server rejected our session - clear everything and stay on login page
            sessionStorage.removeItem('binat_username');
            sessionStorage.removeItem('binat_user_id');
            sessionStorage.removeItem('binat_pdn_code');
            sessionStorage.removeItem('_binat_redirect_count');
        } else {
            sessionStorage.setItem('_binat_redirect_count', String(redirectCount + 1));
            window.location.href = `/pdn-binat/binat?user_name=${encodeURIComponent(storedUsername)}&user_id=${encodeURIComponent(storedUserId)}&pdn_code=${encodeURIComponent(storedPdnCode)}`;
            return;
        }
    } else {
        sessionStorage.removeItem('_binat_redirect_count');
    }

    // Auto-fill stored username
    if (storedUsername) {
        document.getElementById('username').value = storedUsername;
        validateForm();
    }
});

// Form submission
document.getElementById('loginForm').addEventListener('submit', async (e) => {
    e.preventDefault();

    // Guard: checkbox must be checked
    if (!document.getElementById('termsCheckbox').checked) {
        showTermsError();
        document.getElementById('termsCheckbox').focus();
        return;
    }

    const email    = document.getElementById('username').value.trim();
    const password = document.getElementById('password').value.trim();
    const btn      = document.getElementById('submitButton');

    if (!email || !password) {
        showError('אנא הזן אימייל וסיסמה');
        return;
    }

    btn.classList.add('loading');
    btn.disabled = true;

    try {
        const response = await fetch('/pdn-binat/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password, terms_accepted: true })
        });

        const data = await response.json();

        if (data.success) {
            sessionStorage.setItem('binat_username', data.user_name);
            sessionStorage.setItem('binat_user_id',  data.user_id);
            sessionStorage.setItem('binat_pdn_code', data.pdn_code);
            sessionStorage.removeItem('_binat_redirect_count');
            window.location.href = `/pdn-binat/binat?user_name=${encodeURIComponent(data.user_name)}&user_id=${encodeURIComponent(data.user_id)}&pdn_code=${encodeURIComponent(data.pdn_code)}`;
        } else {
            showError(data.error || 'שגיאה בהתחברות');
            btn.classList.remove('loading');
            btn.disabled = false;
        }
    } catch (error) {
        showError('שגיאה בחיבור לשרת');
        btn.classList.remove('loading');
        btn.disabled = false;
    }
});
