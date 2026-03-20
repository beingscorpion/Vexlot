// ── api.js ────────────────────────────────────────────────────────────────────
// Shared API client for all Verdant pages.
// Include this before any page script:  <script src="api.js"></script>

// Use the same origin (host + port) the HTML was served from to avoid CORS
// preflights when everything runs locally.
const API_BASE = `${window.location.origin}/api/v1`;

// ── Token storage ─────────────────────────────────────────────────────────────
const Auth = {
  getAccess()  { return localStorage.getItem('vd_access'); },
  getRefresh() { return localStorage.getItem('vd_refresh'); },
  getUser()    { try { return JSON.parse(localStorage.getItem('vd_user')); } catch { return null; } },

  set(tokens, user) {
    localStorage.setItem('vd_access',  tokens.access_token);
    localStorage.setItem('vd_refresh', tokens.refresh_token);
    if (user) localStorage.setItem('vd_user', JSON.stringify(user));
  },

  clear() {
    localStorage.removeItem('vd_access');
    localStorage.removeItem('vd_refresh');
    localStorage.removeItem('vd_user');
  },

  isLoggedIn() { return !!this.getAccess(); },
};

// ── Auth guard ────────────────────────────────────────────────────────────────
// Call at the top of every protected page's DOMContentLoaded.
function authGuard() {
  if (!Auth.isLoggedIn()) {
    window.location.href = 'auth.html';
    return false;
  }
  // Populate sidebar user display if elements exist
  const user = Auth.getUser();
  if (user) {
    const nameEl   = document.querySelector('.user-name');
    const avatarEl = document.querySelector('.user-avatar');
    if (nameEl)   nameEl.textContent   = `${user.first_name} ${user.last_name}`;
    if (avatarEl) avatarEl.textContent =
      `${user.first_name[0]}${user.last_name[0]}`.toUpperCase();
  }
  return true;
}

// ── Core fetch wrapper ────────────────────────────────────────────────────────
let _refreshing = false;

async function apiFetch(path, options = {}) {
  const headers = { 'Content-Type': 'application/json', ...(options.headers || {}) };
  const token = Auth.getAccess();
  if (token) headers['Authorization'] = `Bearer ${token}`;

  let res = await fetch(`${API_BASE}${path}`, { ...options, headers });

  // ── Auto-refresh on 401 ───────────────────────────────────────────────────
  if (res.status === 401 && !_refreshing && Auth.getRefresh()) {
    _refreshing = true;
    try {
      const rfRes = await fetch(`${API_BASE}/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: Auth.getRefresh() }),
      });
      if (rfRes.ok) {
        const tokens = await rfRes.json();
        Auth.set(tokens, null);
        headers['Authorization'] = `Bearer ${tokens.access_token}`;
        res = await fetch(`${API_BASE}${path}`, { ...options, headers });
      } else {
        Auth.clear();
        window.location.href = 'auth.html';
        return;
      }
    } finally {
      _refreshing = false;
    }
  }

  // ── Session expired completely ────────────────────────────────────────────
  if (res.status === 401) {
    Auth.clear();
    window.location.href = 'auth.html';
    return;
  }

  return res;
}

// ── Convenience methods ───────────────────────────────────────────────────────
const api = {
  async get(path) {
    return apiFetch(path, { method: 'GET' });
  },
  async post(path, body) {
    return apiFetch(path, { method: 'POST', body: JSON.stringify(body) });
  },
  async patch(path, body) {
    return apiFetch(path, { method: 'PATCH', body: JSON.stringify(body) });
  },
  async del(path) {
    return apiFetch(path, { method: 'DELETE' });
  },

  // Parse JSON and throw a readable error if the response is not ok
  async json(res) {
    if (!res) return null;
    if (!res.ok) {
      let detail = `Request failed (${res.status})`;
      try {
        const err = await res.json();
        detail = err.detail || (Array.isArray(err.detail) ? err.detail[0].msg : detail);
      } catch (_) {}
      throw new Error(detail);
    }
    return res.json();
  },
};

// ── Global error toast ────────────────────────────────────────────────────────
function showToast(msg, type = 'success') {
  let t = document.getElementById('toast');
  if (!t) {
    t = document.createElement('div');
    t.id = 'toast';
    t.style.cssText = `
      position:fixed;bottom:28px;right:28px;z-index:9998;
      background:var(--green-dark,#0f2411);border:1px solid var(--green-mid,#1a4020);
      padding:14px 20px;font-size:0.65rem;letter-spacing:0.08em;
      color:var(--green-pale,#a8d5ad);transform:translateY(80px);opacity:0;
      transition:transform .35s cubic-bezier(.23,1,.32,1),opacity .35s;
      pointer-events:none;font-family:'DM Mono',monospace;
    `;
    document.body.appendChild(t);
  }
  t.textContent = msg;
  if (type === 'error') t.style.color = '#e08080';
  else t.style.color = 'var(--green-pale,#a8d5ad)';
  t.style.transform = 'translateY(0)';
  t.style.opacity   = '1';
  clearTimeout(t._timer);
  t._timer = setTimeout(() => {
    t.style.transform = 'translateY(80px)';
    t.style.opacity   = '0';
  }, 3500);
}

// ── Loading state helpers ─────────────────────────────────────────────────────
function setBtnLoading(btn, loading, originalText) {
  if (!btn) return;
  btn.disabled = loading;
  if (loading) {
    btn.dataset.orig = btn.querySelector('span')?.textContent || btn.textContent;
    const span = btn.querySelector('span') || btn;
    span.textContent = 'Please wait…';
  } else {
    const span = btn.querySelector('span') || btn;
    span.textContent = originalText || btn.dataset.orig || span.textContent;
  }
}
