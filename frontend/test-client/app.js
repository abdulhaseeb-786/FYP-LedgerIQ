const API_BASE = window.location.origin.includes('localhost') || window.location.origin.includes('127.0.0.1')
  ? `${window.location.origin}/api/v1`
  : 'http://localhost:8000/api/v1';

let state = {
  token: localStorage.getItem('ledgeriq_token') || null,
  user: null,
  projects: [],
  quota: null,
  selectedFile: null,
  lastCompilationResult: null,
  authMode: 'login',
};

const healthBadge = document.getElementById('healthBadge');
const healthText = document.getElementById('healthText');
const authStatusPill = document.getElementById('authStatusPill');
const userHeaderSection = document.getElementById('userHeaderSection');
const authModal = document.getElementById('authModal');
const authForm = document.getElementById('authForm');
const authErrorMessage = document.getElementById('authErrorMessage');
const dropzone = document.getElementById('dropzone');
const dropzoneLabel = document.getElementById('dropzoneLabel');
const fileInput = document.getElementById('fileInput');
const compileForm = document.getElementById('compileForm');
const compileBtn = document.getElementById('compileBtn');
const compileBtnText = document.getElementById('compileBtnText');
const compileSpinner = document.getElementById('compileSpinner');
const emptyResultPlaceholder = document.getElementById('emptyResultPlaceholder');
const resultsContainer = document.getElementById('resultsContainer');
const statusBanner = document.getElementById('statusBanner');
const statusBadge = document.getElementById('statusBadge');
const resultEntityName = document.getElementById('resultEntityName');
const resultSummaryMessage = document.getElementById('resultSummaryMessage');
const downloadWorkbookBtn = document.getElementById('downloadWorkbookBtn');
const projectsList = document.getElementById('projectsList');
const projectSelect = document.getElementById('projectSelect');
const quotaBadge = document.getElementById('quotaBadge');
const toast = document.getElementById('toast');

function showToast(message, type = 'info') {
  toast.innerText = message;
  toast.className = `fixed bottom-5 right-5 z-50 px-4 py-3 rounded-lg shadow-lg text-xs font-mono transition-all transform duration-300 block ${
    type === 'success'
      ? 'bg-emerald-900 border border-emerald-700 text-emerald-100'
      : type === 'error'
      ? 'bg-rose-900 border border-rose-700 text-rose-100'
      : 'bg-slate-800 border border-slate-700 text-slate-200'
  }`;
  setTimeout(() => { toast.className = 'hidden'; }, 4000);
}

async function checkHealth() {
  const startTime = performance.now();
  try {
    const res = await fetch(`${API_BASE}/health`);
    const duration = Math.round(performance.now() - startTime);
    if (res.ok) {
      healthBadge.className = 'flex items-center space-x-2 px-3 py-1 rounded-full text-xs font-mono bg-emerald-950 text-emerald-400 border border-emerald-800';
      healthBadge.innerHTML = `<span class="h-2 w-2 rounded-full bg-emerald-400"></span><span>Healthy (${duration}ms)</span>`;
    } else {
      throw new Error(`HTTP ${res.status}`);
    }
  } catch (err) {
    healthBadge.className = 'flex items-center space-x-2 px-3 py-1 rounded-full text-xs font-mono bg-rose-950 text-rose-400 border border-rose-800';
    healthBadge.innerHTML = `<span class="h-2 w-2 rounded-full bg-rose-400"></span><span>Disconnected</span>`;
  }
}

async function loadUserProfile() {
  if (!state.token) {
    renderAnonymousUser();
    return;
  }
  try {
    const res = await fetch(`${API_BASE}/auth/me`, {
      headers: { Authorization: `Bearer ${state.token}` },
    });
    if (res.ok) {
      const data = await res.json();
      state.user = data.data;
      renderAuthenticatedUser();
      loadProjectsAndQuota();
    } else {
      logout();
    }
  } catch (err) {
    console.error('Failed to load user profile:', err);
  }
}

function renderAnonymousUser() {
  authStatusPill.className = 'text-xs px-2 py-0.5 rounded font-mono bg-slate-800 text-slate-400 border border-slate-700';
  authStatusPill.innerText = 'Anonymous Mode';
  userHeaderSection.innerHTML = `
    <button id="openAuthModalBtn" class="px-3.5 py-1.5 text-xs font-semibold rounded-md bg-emerald-600 hover:bg-emerald-500 text-white transition">
      Login / Register
    </button>
  `;
  document.getElementById('openAuthModalBtn').addEventListener('click', openAuthModal);
  projectsList.innerHTML = `<div class="text-slate-500 py-2 text-center text-xs">Sign in to create & manage persistent projects.</div>`;
  projectSelect.innerHTML = `<option value="">None (Ad-hoc run)</option>`;
  quotaBadge.innerText = 'Quota: -- / --';
}

function renderAuthenticatedUser() {
  const credits = state.user.credit_balance !== undefined ? state.user.credit_balance : '--';
  const orgName = state.user.organization ? state.user.organization.name : 'Personal';
  authStatusPill.className = 'text-xs px-2 py-0.5 rounded font-mono bg-emerald-950 text-emerald-300 border border-emerald-800';
  authStatusPill.innerText = `Logged in: ${state.user.email}`;
  userHeaderSection.innerHTML = `
    <div class="flex items-center space-x-3 text-xs">
      <div class="hidden md:flex items-center space-x-2 bg-slate-800 px-2.5 py-1 rounded border border-slate-700 font-mono">
        <span class="text-slate-400">🏢 ${orgName}</span>
        <span class="text-slate-600">|</span>
        <span class="text-emerald-400 font-bold">💳 ${credits} Credits</span>
      </div>
      <button id="logoutBtn" class="px-2.5 py-1 text-slate-400 hover:text-slate-100 font-mono transition">
        Logout
      </button>
    </div>
  `;
  document.getElementById('logoutBtn').addEventListener('click', logout);
}

function logout() {
  state.token = null;
  state.user = null;
  state.projects = [];
  state.quota = null;
  localStorage.removeItem('ledgeriq_token');
  renderAnonymousUser();
  showToast('Logged out of session', 'info');
}

function openAuthModal() {
  authModal.classList.remove('hidden');
  authErrorMessage.classList.add('hidden');
}

function closeAuthModal() {
  authModal.classList.add('hidden');
}

document.getElementById('closeAuthModalBtn').addEventListener('click', closeAuthModal);
document.getElementById('quickLoginModalBtn').addEventListener('click', openAuthModal);
document.getElementById('refreshAuthBtn').addEventListener('click', loadUserProfile);

const authTabLogin = document.getElementById('authTabLogin');
const authTabRegister = document.getElementById('authTabRegister');
const fullNameGroup = document.getElementById('fullNameGroup');
const orgNameGroup = document.getElementById('orgNameGroup');
const authSubmitBtn = document.getElementById('authSubmitBtn');

authTabLogin.addEventListener('click', () => {
  state.authMode = 'login';
  authTabLogin.className = 'flex-1 py-1.5 rounded font-semibold bg-emerald-600 text-white transition';
  authTabRegister.className = 'flex-1 py-1.5 rounded font-semibold text-slate-400 hover:text-slate-200 transition';
  fullNameGroup.classList.add('hidden');
  orgNameGroup.classList.add('hidden');
  authSubmitBtn.innerText = 'Sign In';
  authErrorMessage.classList.add('hidden');
});

authTabRegister.addEventListener('click', () => {
  state.authMode = 'register';
  authTabRegister.className = 'flex-1 py-1.5 rounded font-semibold bg-emerald-600 text-white transition';
  authTabLogin.className = 'flex-1 py-1.5 rounded font-semibold text-slate-400 hover:text-slate-200 transition';
  fullNameGroup.classList.remove('hidden');
  orgNameGroup.classList.remove('hidden');
  authSubmitBtn.innerText = 'Create Workspace & Account';
  authErrorMessage.classList.add('hidden');
});

authForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  authErrorMessage.classList.add('hidden');
  const email = document.getElementById('authEmail').value.trim();
  const password = document.getElementById('authPassword').value;

  try {
    if (state.authMode === 'register') {
      const full_name = document.getElementById('authFullName').value.trim();
      const organization_name = document.getElementById('authOrgName').value.trim();
      const regRes = await fetch(`${API_BASE}/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password, full_name, organization_name }),
      });
      const regData = await regRes.json();
      if (!regRes.ok) throw new Error(regData.error?.message || regData.detail || 'Registration failed');
      showToast('Workspace created! Logging in...', 'success');
    }

    const loginRes = await fetch(`${API_BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });
    const loginData = await loginRes.json();
    if (!loginRes.ok) throw new Error(loginData.error?.message || loginData.detail || 'Invalid email or password');

    state.token = loginData.data.access_token;
    localStorage.setItem('ledgeriq_token', state.token);
    closeAuthModal();
    showToast('Authenticated successfully!', 'success');
    await loadUserProfile();
  } catch (err) {
    authErrorMessage.innerText = err.message;
    authErrorMessage.classList.remove('hidden');
  }
});

async function loadProjectsAndQuota() {
  if (!state.token) return;
  try {
    const quotaRes = await fetch(`${API_BASE}/projects/quota`, {
      headers: { Authorization: `Bearer ${state.token}` },
    });
    if (quotaRes.ok) {
      const qData = await quotaRes.json();
      state.quota = qData.data;
      const isFull = state.quota.active_projects_count >= state.quota.max_projects_quota;
      quotaBadge.className = `text-xs px-2 py-0.5 rounded font-mono ${
        isFull ? 'bg-rose-950 text-rose-300 border border-rose-800' : 'bg-slate-800 text-slate-300 border border-slate-700'
      }`;
      quotaBadge.innerText = `Quota: ${state.quota.active_projects_count} / ${state.quota.max_projects_quota} Active`;
    }

    const projRes = await fetch(`${API_BASE}/projects?include_archived=true`, {
      headers: { Authorization: `Bearer ${state.token}` },
    });
    if (projRes.ok) {
      const pData = await projRes.json();
      state.projects = pData.data;
      renderProjects();
    }
  } catch (err) {
    console.error('Error loading projects:', err);
  }
}

function renderProjects() {
  projectSelect.innerHTML = '<option value="">None (Ad-hoc run)</option>';
  if (state.projects.length === 0) {
    projectsList.innerHTML = `<div class="text-slate-500 py-2 text-center text-xs">No projects created yet.</div>`;
    return;
  }
  projectsList.innerHTML = '';
  state.projects.forEach((proj) => {
    if (!proj.is_archived) {
      const opt = document.createElement('option');
      opt.value = proj.id;
      opt.innerText = `${proj.name} (${proj.entity_name || 'No Entity'})`;
      projectSelect.appendChild(opt);
    }
    const item = document.createElement('div');
    item.className = `flex items-center justify-between p-2 rounded border text-xs ${
      proj.is_archived ? 'bg-slate-950/40 border-slate-800/60 opacity-60' : 'bg-slate-950 border-slate-800'
    }`;
    item.innerHTML = `
      <div>
        <div class="font-bold text-slate-200">${proj.name}</div>
        <div class="text-[10px] text-slate-400">${proj.entity_name || 'Unassigned'} • ${proj.is_archived ? 'Archived' : 'Active'}</div>
      </div>
      <button class="archive-toggle-btn px-2 py-0.5 text-[10px] rounded border border-slate-700 hover:bg-slate-800 text-slate-300 transition"
        data-id="${proj.id}" data-archived="${proj.is_archived}">
        ${proj.is_archived ? 'Unarchive' : 'Archive'}
      </button>
    `;
    projectsList.appendChild(item);
  });

  document.querySelectorAll('.archive-toggle-btn').forEach((btn) => {
    btn.addEventListener('click', async (e) => {
      const projId = e.target.getAttribute('data-id');
      const isArchived = e.target.getAttribute('data-archived') === 'true';
      await toggleArchiveProject(projId, !isArchived);
    });
  });
}

async function toggleArchiveProject(projectId, makeArchived) {
  try {
    const res = await fetch(`${API_BASE}/projects/${projectId}`, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${state.token}`,
      },
      body: JSON.stringify({ is_archived: makeArchived }),
    });
    if (res.ok) {
      showToast(makeArchived ? 'Project archived' : 'Project activated', 'info');
      await loadProjectsAndQuota();
    } else {
      const data = await res.json();
      showToast(data.error?.message || 'Failed to update project status', 'error');
    }
  } catch (err) {
    showToast('Failed to contact server', 'error');
  }
}

document.getElementById('createProjectForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  if (!state.token) { openAuthModal(); return; }
  const name = document.getElementById('newProjectName').value.trim();
  const entity_name = document.getElementById('newProjectEntity').value.trim();
  try {
    const res = await fetch(`${API_BASE}/projects`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${state.token}`,
      },
      body: JSON.stringify({ name, entity_name }),
    });
    const data = await res.json();
    if (res.ok) {
      showToast('Project created successfully!', 'success');
      document.getElementById('newProjectName').value = '';
      document.getElementById('newProjectEntity').value = '';
      await loadProjectsAndQuota();
    } else {
      showToast(data.error?.message || data.detail || 'Could not create project', 'error');
    }
  } catch (err) {
    showToast('Failed to create project', 'error');
  }
});

document.getElementById('reloadProjectsBtn').addEventListener('click', loadProjectsAndQuota);

dropzone.addEventListener('click', () => fileInput.click());
dropzone.addEventListener('dragover', (e) => { e.preventDefault(); dropzone.classList.add('dragover'); });
dropzone.addEventListener('dragleave', () => { dropzone.classList.remove('dragover'); });
dropzone.addEventListener('drop', (e) => {
  e.preventDefault();
  dropzone.classList.remove('dragover');
  if (e.dataTransfer.files.length > 0) handleFileSelected(e.dataTransfer.files[0]);
});

fileInput.addEventListener('change', (e) => {
  if (e.target.files.length > 0) handleFileSelected(e.target.files[0]);
});

function handleFileSelected(file) {
  if (!file.name.endsWith('.xlsx') && !file.name.endsWith('.xlsm')) {
    showToast('Please select an Excel workbook (.xlsx or .xlsm)', 'error');
    return;
  }
  state.selectedFile = file;
  const sizeKb = (file.size / 1024).toFixed(1);
  dropzoneLabel.innerHTML = `
    <span class="text-emerald-400 font-bold">${file.name}</span>
    <span class="text-slate-400 text-[11px] block mt-0.5">(${sizeKb} KB)</span>
  `;
}

compileForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  if (!state.selectedFile) {
    showToast('Please select or drop a Trial Balance Excel workbook first.', 'error');
    return;
  }

  compileBtn.disabled = true;
  compileBtnText.innerText = 'Compiling & Auditing Formulas...';
  compileSpinner.classList.remove('hidden');

  const formData = new FormData();
  formData.append('file', state.selectedFile);

  const entityName = document.getElementById('entityNameInput').value.trim();
  if (entityName) formData.append('entity_name', entityName);
  const period = document.getElementById('periodInput').value.trim();
  if (period) formData.append('period_ended', period);
  const sheet = document.getElementById('sheetInput').value.trim();
  if (sheet) formData.append('sheet_name', sheet);

  const runHealth = document.getElementById('healthGateCheckbox').checked;
  formData.append('run_health_gate', runHealth);
  const allowPlug = document.getElementById('workingCapitalCheckbox').checked;
  formData.append('allow_working_capital_plug', allowPlug);

  const projectId = document.getElementById('projectSelect').value;
  if (projectId) formData.append('project_id', projectId);

  const headers = {};
  if (state.token) headers['Authorization'] = `Bearer ${state.token}`;

  try {
    const res = await fetch(`${API_BASE}/statements/compile`, {
      method: 'POST',
      headers,
      body: formData,
    });
    const result = await res.json();
    if (!res.ok) throw new Error(result.error?.message || result.detail || 'Compilation failed');

    state.lastCompilationResult = result.data;
    renderCompilationOutcome(result.data);
    showToast('Compilation completed successfully!', 'success');
    if (state.token) await loadUserProfile();
  } catch (err) {
    showToast(err.message, 'error');
    console.error('Compilation error:', err);
  } finally {
    compileBtn.disabled = false;
    compileBtnText.innerText = '⚡ Compile Statutory Financial Statements';
    compileSpinner.classList.add('hidden');
  }
});

function renderCompilationOutcome(outcome) {
  emptyResultPlaceholder.classList.add('hidden');
  resultsContainer.classList.remove('hidden');

  const status = outcome.status;
  statusBadge.innerText = status;
  resultEntityName.innerText = outcome.entity_name || 'Statutory Financial Statements';
  resultSummaryMessage.innerText = outcome.summary_message || `Generated for period ended ${outcome.period_ended || 'N/A'}`;

  if (status === 'SUCCESS') {
    statusBanner.className = 'border rounded-xl p-5 flex items-center justify-between status-success';
    statusBadge.className = 'px-2.5 py-1 rounded text-xs font-mono font-bold uppercase bg-emerald-950 text-emerald-300 border border-emerald-700';
  } else if (status === 'RECOVERED_WARNING') {
    statusBanner.className = 'border rounded-xl p-5 flex items-center justify-between status-warning';
    statusBadge.className = 'px-2.5 py-1 rounded text-xs font-mono font-bold uppercase bg-amber-950 text-amber-300 border border-amber-700';
  } else {
    statusBanner.className = 'border rounded-xl p-5 flex items-center justify-between status-failure';
    statusBadge.className = 'px-2.5 py-1 rounded text-xs font-mono font-bold uppercase bg-rose-950 text-rose-300 border border-rose-700';
  }

  if (outcome.download_url) {
    downloadWorkbookBtn.href = `${window.location.origin}${outcome.download_url}`;
    downloadWorkbookBtn.classList.remove('hidden');
  } else {
    downloadWorkbookBtn.classList.add('hidden');
  }

  const dh = outcome.data_health || {};
  document.getElementById('healthProcessable').innerText = dh.is_processable ? 'VALID' : 'REJECTED';
  document.getElementById('healthRowCount').innerText = dh.row_count || 0;
  const variance = dh.unbalanced_variance || 0;
  document.getElementById('healthVariance').innerText = variance === 0 ? '0.00 (Balanced)' : `Δ ${variance.toFixed(2)}`;

  const healthIssuesList = document.getElementById('healthIssuesList');
  if (dh.issues && dh.issues.length > 0) {
    healthIssuesList.innerHTML = dh.issues.map(i => `<div>• [${i.severity || 'INFO'}] ${i.description || JSON.stringify(i)}</div>`).join('');
  } else {
    healthIssuesList.innerText = 'No pre-flight health issues detected in workbook structure.';
  }

  const ver = outcome.verification || {};
  setBadgeVal('bsCheckCard', 'bsCheckVal', ver.bs_balances, 'Balanced', 'Unbalanced');
  setBadgeVal('cfCheckCard', 'cfCheckVal', ver.cf_reconciles, 'Reconciled', 'Variance');
  setBadgeVal('eqCheckCard', 'eqCheckVal', ver.equity_reconciles, 'Reconciled', 'Variance');
  setBadgeVal('notesCheckCard', 'notesCheckVal', ver.notes_balanced, 'Agreed', 'Discrepancy');

  const diagList = document.getElementById('verificationDiagnosticsList');
  if (ver.diagnostics && ver.diagnostics.length > 0) {
    diagList.innerHTML = ver.diagnostics.map(d => `<div>• ${d}</div>`).join('');
  } else {
    diagList.innerText = 'All statutory statements and notes cross-reconcile with 100% parity.';
  }

  const audit = outcome.workbook_audit || {};
  document.getElementById('auditPassedVal').innerText = audit.verified ? 'VERIFIED' : 'FAILED';
  document.getElementById('auditChecksCount').innerText = audit.checks_run || 0;
  document.getElementById('auditFailuresCount').innerText = audit.failures ? audit.failures.length : 0;

  const auditDetails = document.getElementById('auditSummaryDetails');
  if (audit.failures && audit.failures.length > 0) {
    auditDetails.innerText = JSON.stringify(audit.failures, null, 2);
  } else {
    auditDetails.innerText = 'All formula linkages evaluated independently via OpenXML parser: 100% formula integrity confirmed.';
  }

  document.getElementById('rawJsonResponse').innerText = JSON.stringify(outcome, null, 2);
}

function setBadgeVal(cardId, valId, isOk, okText, failText) {
  const card = document.getElementById(cardId);
  const val = document.getElementById(valId);
  if (isOk) {
    card.className = 'bg-slate-950 border border-emerald-900/60 p-3 rounded-lg text-emerald-400';
    val.innerText = okText;
  } else {
    card.className = 'bg-slate-950 border border-rose-900/60 p-3 rounded-lg text-rose-400';
    val.innerText = failText;
  }
}

document.querySelectorAll('.tab-btn').forEach((btn) => {
  btn.addEventListener('click', (e) => {
    const targetTab = e.target.getAttribute('data-tab');
    document.querySelectorAll('.tab-btn').forEach((b) => {
      b.className = 'tab-btn px-4 py-3 text-slate-400 hover:text-slate-200 transition';
    });
    e.target.className = 'tab-btn px-4 py-3 text-emerald-400 border-b-2 border-emerald-500 transition';
    document.querySelectorAll('.tab-content').forEach((c) => c.classList.add('hidden'));
    document.getElementById(targetTab).classList.remove('hidden');
  });
});

document.addEventListener('DOMContentLoaded', () => {
  checkHealth();
  setInterval(checkHealth, 15000);
  loadUserProfile();
});
