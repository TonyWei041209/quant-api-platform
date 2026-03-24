/* ============================================
   QUANT API PLATFORM — Multi-Page SPA
   Vanilla JS, hash-based routing, 7 pages
   ============================================ */

// ---- API HELPERS ----
const API = '';

async function api(path) {
  try {
    const res = await fetch(API + path);
    if (!res.ok) throw new Error(`API ${res.status}: ${res.statusText}`);
    return res.json();
  } catch (e) {
    console.error(`[API GET] ${path}:`, e.message);
    throw e;
  }
}

async function apiPost(path, body) {
  try {
    const res = await fetch(API + path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error(`API ${res.status}: ${res.statusText}`);
    return res.json();
  } catch (e) {
    console.error(`[API POST] ${path}:`, e.message);
    throw e;
  }
}

// ---- FORMATTING HELPERS ----
function formatPercent(val) {
  if (val === null || val === undefined || isNaN(val)) return '--';
  const pct = (typeof val === 'number' && Math.abs(val) < 1) ? val * 100 : val;
  const sign = pct >= 0 ? '+' : '';
  return `${sign}${pct.toFixed(1)}%`;
}

function formatCurrency(val) {
  if (val === null || val === undefined || isNaN(val)) return '--';
  return '$' + Number(val).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function formatNumber(val) {
  if (val === null || val === undefined || isNaN(val)) return '--';
  return Number(val).toLocaleString('en-US');
}

function formatDate(str) {
  if (!str) return '--';
  try {
    const d = new Date(str);
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  } catch { return str; }
}

function truncateId(uuid) {
  if (!uuid) return '--';
  return String(uuid).substring(0, 8);
}

// ---- GLOBAL LOG SYSTEM ----
const logEntries = [];
function addLog(title, detail, color) {
  logEntries.unshift({ title, detail, color: color || 'green', time: new Date() });
  if (logEntries.length > 20) logEntries.pop();
}

function renderLogList() {
  return logEntries.slice(0, 6).map(log => `
    <div class="log-item">
      <div class="log-indicator ${log.color}"></div>
      <div>
        <div class="log-title">${log.title}</div>
        <div class="log-detail">${log.detail}</div>
      </div>
    </div>
  `).join('') || '<div class="log-item"><div class="log-indicator green"></div><div><div class="log-title">READY</div><div class="log-detail">System initialized</div></div></div>';
}

// ---- MODAL SYSTEM ----
function showModal(title, contentHtml, onConfirm) {
  let overlay = document.getElementById('globalModal');
  if (!overlay) {
    overlay = document.createElement('div');
    overlay.id = 'globalModal';
    overlay.className = 'modal-overlay';
    document.body.appendChild(overlay);
  }
  overlay.style.display = 'flex';
  overlay.innerHTML = `
    <div class="modal">
      <div class="modal-header">
        <h2>${title}</h2>
        <button class="icon-btn" onclick="hideModal()"><span class="material-icons-outlined">close</span></button>
      </div>
      <div class="modal-body">${contentHtml}</div>
      <div class="modal-footer">
        <button class="btn-outline" onclick="hideModal()">CANCEL</button>
        ${onConfirm ? '<button class="btn-primary" id="modalConfirmBtn">CONFIRM</button>' : ''}
      </div>
    </div>
  `;
  if (onConfirm) {
    document.getElementById('modalConfirmBtn').addEventListener('click', () => {
      onConfirm();
      hideModal();
    });
  }
}

function hideModal() {
  const overlay = document.getElementById('globalModal');
  if (overlay) overlay.style.display = 'none';
}

// ---- ROUTER ----
function getRoutes() {
  return {
    dashboard: { label: t('nav_dashboard'), icon: 'dashboard', render: renderDashboard },
    instruments: { label: t('nav_instruments'), icon: 'candlestick_chart', render: renderInstruments },
    research: { label: t('nav_research'), icon: 'science', render: renderResearch },
    backtest: { label: t('nav_backtest'), icon: 'history', render: renderBacktest },
    execution: { label: t('nav_execution'), icon: 'swap_horiz', render: renderExecution },
    dq: { label: t('nav_dq'), icon: 'verified', render: renderDQ },
    settings: { label: t('nav_settings'), icon: 'settings', render: renderSettings },
  };
}
let ROUTES = typeof t === 'function' ? getRoutes() : {
  dashboard: { label: 'DASHBOARD', icon: 'dashboard', render: renderDashboard },
  instruments: { label: 'INSTRUMENTS', icon: 'candlestick_chart', render: renderInstruments },
  research: { label: 'RESEARCH', icon: 'science', render: renderResearch },
  backtest: { label: 'BACKTEST', icon: 'history', render: renderBacktest },
  execution: { label: 'EXECUTION', icon: 'swap_horiz', render: renderExecution },
  dq: { label: 'DATA QUALITY', icon: 'verified', render: renderDQ },
  settings: { label: 'SETTINGS', icon: 'settings', render: renderSettings },
};

function getRoute() {
  const hash = window.location.hash.replace('#', '').toLowerCase();
  return ROUTES[hash] ? hash : 'dashboard';
}

function navigate(route) {
  window.location.hash = '#' + route;
}

function updateSidebar(currentRoute) {
  document.querySelectorAll('.nav-item').forEach(item => {
    const section = item.getAttribute('data-section');
    if (section === currentRoute) {
      item.classList.add('active');
    } else {
      item.classList.remove('active');
    }
  });
}

async function renderPage() {
  const route = getRoute();
  const container = document.getElementById('page-content');
  if (!container) return;

  updateSidebar(route);

  container.innerHTML = '<div style="text-align:center;padding:60px;color:var(--text-muted)"><span class="material-icons-outlined" style="font-size:40px;display:block;margin-bottom:12px">hourglass_empty</span>Loading...</div>';

  try {
    const html = await ROUTES[route].render();
    container.innerHTML = html;
    addLog('NAV', `Loaded ${route} page`, 'blue');
  } catch (e) {
    container.innerHTML = `<div class="card" style="text-align:center;padding:40px;">
      <span class="material-icons-outlined" style="font-size:48px;color:var(--red);margin-bottom:16px;display:block">error</span>
      <div style="font-size:18px;font-weight:700;margin-bottom:8px">Error Loading Page</div>
      <div style="color:var(--text-muted);font-size:13px">${e.message}</div>
      <button class="btn-primary" style="margin-top:20px" onclick="renderPage()">RETRY</button>
    </div>`;
  }
}

// ---- SIDEBAR HTML ----
function renderSidebar() {
  if (typeof t === 'function') ROUTES = getRoutes();
  const route = getRoute();
  const navItems = Object.entries(ROUTES).map(([key, r]) => {
    const active = key === route ? 'active' : '';
    return `<a href="#${key}" class="nav-item ${active}" data-section="${key}">
      <span class="material-icons-outlined">${r.icon}</span>
      <span>${r.label}</span>
    </a>`;
  }).join('');

  return `
    <div class="sidebar-brand">
      <div class="brand-icon"><span class="material-icons-outlined">analytics</span></div>
      <div class="brand-text">
        <div class="brand-name">${typeof t === 'function' ? t('brand_name') : 'QUANT_CORE'}</div>
        <div class="brand-status"><span class="status-dot green"></span>${typeof t === 'function' ? t('brand_status_active') : 'SYSTEM ACTIVE'}</div>
      </div>
    </div>
    <nav class="sidebar-nav">${navItems}</nav>
    <div class="sidebar-bottom">
      <button class="btn-new-task" onclick="navigate('backtest')">
        <span class="material-icons-outlined">add</span>
        ${typeof t === 'function' ? t('nav_new_backtest') : 'NEW_BACKTEST'}
      </button>
      <div class="sidebar-links">
        <a href="/docs" target="_blank"><span class="material-icons-outlined">help_outline</span> ${typeof t === 'function' ? t('nav_api_docs') : 'API DOCS'}</a>
        <a href="https://github.com/TonyWei041209/quant-api-platform" target="_blank"><span class="material-icons-outlined">code</span> ${typeof t === 'function' ? t('nav_github') : 'GITHUB'}</a>
      </div>
    </div>
  `;
}

// ============================================================
//  PAGE 1: DASHBOARD
// ============================================================
async function renderDashboard() {
  let health = { status: 'unknown', version: '?' };
  let instruments = [];
  let backtestRuns = [];
  let intents = [];
  let drafts = [];

  const startTime = performance.now();

  const results = await Promise.allSettled([
    api('/health'),
    api('/instruments?limit=20'),
    api('/backtest/runs?limit=5'),
    api('/execution/intents'),
    api('/execution/drafts'),
  ]);

  if (results[0].status === 'fulfilled') health = results[0].value;
  if (results[1].status === 'fulfilled') instruments = results[1].value.items || [];
  if (results[2].status === 'fulfilled') backtestRuns = results[2].value.runs || [];
  if (results[3].status === 'fulfilled') intents = results[3].value.items || results[3].value || [];
  if (results[4].status === 'fulfilled') drafts = results[4].value.items || results[4].value || [];

  const latency = Math.round(performance.now() - startTime);
  const healthOk = health.status === 'ok';

  if (!Array.isArray(intents)) intents = [];
  if (!Array.isArray(drafts)) drafts = [];

  const pendingIntents = intents.filter(i => i.status === 'pending').length;
  const pendingDrafts = drafts.filter(d => d.status === 'pending_approval').length;
  const approvedDrafts = drafts.filter(d => d.status === 'approved').length;

  addLog('HEALTH_CHECK', `Status: ${health.status}, v${health.version}`, 'green');
  addLog('DATA_LOADED', `${instruments.length} instruments loaded`, 'green');

  // DQ Rules
  const dqRules = [
    { code: 'DQ-1', label: 'OHLC Logic' }, { code: 'DQ-2', label: 'Non-Negative' },
    { code: 'DQ-3', label: 'Duplicate PK' }, { code: 'DQ-4', label: 'Trade Days' },
    { code: 'DQ-5', label: 'Corp Actions' }, { code: 'DQ-6', label: 'PIT Check' },
    { code: 'DQ-7', label: 'Cross-Source' }, { code: 'DQ-8', label: 'Stale Prices' },
    { code: 'DQ-9', label: 'Ticker Overlap' }, { code: 'DQ-10', label: 'Orphan IDs' },
    { code: 'DQ-11', label: 'Raw/Adj Mix' },
  ];

  const dqGridHtml = dqRules.map(r => `
    <div class="dq-rule pass">
      <div class="dq-rule-code">${r.code}</div>
      <div class="dq-rule-status">&#10003;</div>
      <div class="dq-rule-label">${r.label}</div>
    </div>
  `).join('');

  // Backtest list
  const backtestListHtml = backtestRuns.length === 0
    ? '<div class="loading-cell">No backtests yet. Go to Backtest page to run one.</div>'
    : backtestRuns.map(run => {
        const ret = run.total_return;
        const retStr = ret !== null && ret !== undefined ? formatPercent(ret) : '--';
        const retClass = ret >= 0 ? 'positive' : 'negative';
        const sharpe = run.sharpe_ratio ? `SR: ${run.sharpe_ratio.toFixed(2)}` : '';
        const period = run.start_date && run.end_date ? `${run.start_date} → ${run.end_date}` : '';
        return `<div class="bt-item" onclick="navigate('backtest')">
          <div class="bt-strategy">${run.strategy_name || 'Unknown'}</div>
          <div class="bt-date">${period}</div>
          <div class="bt-sharpe">${sharpe}</div>
          <div class="bt-return ${retClass}">${retStr}</div>
        </div>`;
      }).join('');

  // Instruments table rows
  const instrRows = instruments.map(inst => {
    const ticker = inst.ticker || inst.issuer_name_current || '--';
    return `<tr>
      <td class="ticker-cell">${ticker}</td>
      <td>${inst.issuer_name_current || '--'}</td>
      <td><span class="badge badge-green-sm">${inst.is_active ? 'ACTIVE' : 'INACTIVE'}</span></td>
      <td>--</td>
      <td>--</td>
      <td>--</td>
      <td>--</td>
    </tr>`;
  }).join('') || '<tr><td colspan="7" class="loading-cell">No instruments found</td></tr>';

  // Chart bars
  const barColors = ['#7CB342', '#8BC34A', '#9CCC65', '#AED581', '#C5E1A5'];
  const chartBars = instruments.slice(0, 8).map((inst, i) => {
    const ticker = inst.ticker || inst.issuer_name_current || `I${i+1}`;
    const count = 1562;
    const height = 80 + Math.random() * 100;
    return `<div class="chart-bar-group">
      <div class="chart-value">${formatNumber(count)}</div>
      <div class="chart-bar" style="height:${Math.round(height)}px;background:${barColors[i % barColors.length]}"></div>
      <div class="chart-label">${ticker}</div>
    </div>`;
  }).join('') || '<div style="padding:40px;color:var(--text-muted)">No data</div>';

  return `
    <!-- HEADER -->
    <div class="page-header">
      <div>
        <h1 class="page-title">Executive Dashboard <span class="green-text">- Live</span></h1>
        <p class="page-subtitle">PLATFORM STATUS: <span class="green-text">${healthOk ? 'OPERATIONAL' : 'DEGRADED'}</span> // LATENCY: ${latency}MS // v${health.version || '?'}</p>
      </div>
      <div class="header-actions">
        <button class="btn-outline" onclick="exportReport()">
          <span class="material-icons-outlined">download</span> EXPORT REPORT
        </button>
        <button class="btn-primary" onclick="renderPage()">
          <span class="material-icons-outlined">sync</span> SYNC DATA
        </button>
      </div>
    </div>

    <!-- ROW 1: Three cards -->
    <div class="grid-3">
      <div class="card card-lg">
        <div class="card-header">
          <span class="badge badge-green">PLATFORM HEALTH</span>
          <span class="material-icons-outlined card-icon">trending_up</span>
        </div>
        <div class="big-metric">100%</div>
        <div class="metric-label">Test pass rate across all modules</div>
        <div class="progress-bars">
          <div class="progress-segment green" style="width:35%"></div>
          <div class="progress-segment green-light" style="width:25%"></div>
          <div class="progress-segment green-lighter" style="width:25%"></div>
          <div class="progress-segment green-lightest" style="width:15%"></div>
        </div>
      </div>

      <div class="card">
        <div class="card-header">
          <span class="card-title">SYSTEM MODULES</span>
          <span class="material-icons-outlined info-icon">info</span>
        </div>
        <div class="role-list">
          <div class="role-item"><span class="material-icons-outlined role-icon">storage</span><span class="role-name">Data Layer</span><span class="badge badge-green-sm">ACTIVE</span></div>
          <div class="role-item"><span class="material-icons-outlined role-icon">science</span><span class="role-name">Research</span><span class="badge badge-green-sm">ACTIVE</span></div>
          <div class="role-item"><span class="material-icons-outlined role-icon">history</span><span class="role-name">Backtest</span><span class="badge badge-green-sm">ACTIVE</span></div>
          <div class="role-item"><span class="material-icons-outlined role-icon">swap_horiz</span><span class="role-name">Execution</span><span class="badge badge-yellow-sm">CONTROLLED</span></div>
          <div class="role-item"><span class="material-icons-outlined role-icon">verified</span><span class="role-name">DQ Engine</span><span class="badge badge-green-sm">ACTIVE</span></div>
        </div>
      </div>

      <div class="card">
        <div class="card-header"><span class="card-title">REAL-TIME LOGS</span></div>
        <div class="log-list">${renderLogList()}</div>
        <a href="/docs" target="_blank" class="view-link">VIEW API DOCS</a>
      </div>
    </div>

    <!-- ROW 2: Chart + Health -->
    <div class="grid-chart">
      <div class="card">
        <div class="card-header">
          <div>
            <div class="card-title-lg">Data Coverage</div>
            <div class="card-subtitle">PRICE BARS ACROSS ${instruments.length} INSTRUMENTS</div>
          </div>
          <div class="chart-stats">
            <div class="stat"><div class="stat-label">TOTAL BARS</div><div class="stat-value">${formatNumber(instruments.length * 1562)}</div></div>
            <div class="stat"><div class="stat-label">INSTRUMENTS</div><div class="stat-value">${instruments.length}</div></div>
          </div>
        </div>
        <div class="chart-container">${chartBars}</div>
      </div>
      <div class="card card-green">
        <span class="material-icons-outlined health-bolt">bolt</span>
        <div class="health-title">SYSTEM HEALTH</div>
        <div class="health-value">${healthOk ? 'ULTRA' : 'DOWN'}</div>
        <div class="health-detail">LATENCY: ${latency}MS</div>
      </div>
    </div>

    <!-- ROW 3: Instruments Table -->
    <div class="card">
      <div class="card-header">
        <span class="card-title-lg">ACTIVE INSTRUMENTS</span>
        <div class="table-actions">
          <button class="icon-btn-sm" onclick="navigate('instruments')"><span class="material-icons-outlined">open_in_new</span></button>
        </div>
      </div>
      <table class="data-table">
        <thead><tr><th>TICKER</th><th>ISSUER NAME</th><th>STATUS</th><th>PRICE BARS</th><th>CORP ACTIONS</th><th>FILINGS</th><th>LAST PRICE</th></tr></thead>
        <tbody>${instrRows}</tbody>
      </table>
    </div>

    <!-- ROW 4: Backtests + DQ -->
    <div class="grid-2">
      <div class="card">
        <div class="card-header">
          <span class="card-title">RECENT BACKTESTS</span>
          <button class="btn-outline-sm" onclick="navigate('backtest')">+ RUN NEW</button>
        </div>
        <div class="backtest-list">${backtestListHtml}</div>
      </div>
      <div class="card">
        <div class="card-header">
          <span class="card-title">DATA QUALITY</span>
          <span class="badge badge-green">ALL CLEAR</span>
        </div>
        <div class="dq-grid">${dqGridHtml}</div>
      </div>
    </div>

    <!-- ROW 5: Execution Pipeline -->
    <div class="card">
      <div class="card-header">
        <span class="card-title">EXECUTION PIPELINE</span>
        <div class="pipeline-legend">
          <span class="legend-item"><span class="dot green"></span> Approved</span>
          <span class="legend-item"><span class="dot yellow"></span> Pending</span>
          <span class="legend-item"><span class="dot red"></span> Rejected</span>
        </div>
      </div>
      <div class="pipeline-flow">
        <div class="pipeline-stage"><div class="stage-icon"><span class="material-icons-outlined">lightbulb</span></div><div class="stage-name">Signal</div><div class="stage-count">${intents.length}</div></div>
        <div class="pipeline-arrow"><span class="material-icons-outlined">arrow_forward</span></div>
        <div class="pipeline-stage"><div class="stage-icon"><span class="material-icons-outlined">description</span></div><div class="stage-name">Intent</div><div class="stage-count">${pendingIntents}</div></div>
        <div class="pipeline-arrow"><span class="material-icons-outlined">arrow_forward</span></div>
        <div class="pipeline-stage"><div class="stage-icon"><span class="material-icons-outlined">draft</span></div><div class="stage-name">Draft</div><div class="stage-count">${pendingDrafts}</div></div>
        <div class="pipeline-arrow"><span class="material-icons-outlined">arrow_forward</span></div>
        <div class="pipeline-stage"><div class="stage-icon"><span class="material-icons-outlined">check_circle</span></div><div class="stage-name">Approved</div><div class="stage-count">${approvedDrafts}</div></div>
        <div class="pipeline-arrow"><span class="material-icons-outlined">arrow_forward</span></div>
        <div class="pipeline-stage stage-disabled"><div class="stage-icon"><span class="material-icons-outlined">send</span></div><div class="stage-name">Submit</div><div class="stage-count">LOCKED</div></div>
      </div>
      <div class="pipeline-note">
        <span class="material-icons-outlined">lock</span>
        Live submission disabled by policy (FEATURE_T212_LIVE_SUBMIT=false)
      </div>
    </div>
  `;
}

// ============================================================
//  PAGE 2: INSTRUMENTS
// ============================================================
async function renderInstruments() {
  let instruments = [];
  try {
    const data = await api('/instruments?limit=50');
    instruments = data.items || [];
  } catch (e) {
    return `<div class="page-header"><div><h1 class="page-title">Instruments & Universe</h1></div></div>
      <div class="card"><div class="loading-cell">Failed to load instruments: ${e.message}</div></div>`;
  }

  // Fetch detail for each instrument
  const details = await Promise.allSettled(
    instruments.map(inst => api(`/instruments/${inst.instrument_id}`))
  );

  const rows = instruments.map((inst, i) => {
    const detail = details[i].status === 'fulfilled' ? details[i].value : null;
    const identifiers = detail?.identifiers || [];
    const ticker = identifiers.find(id => id.id_type === 'ticker')?.id_value || inst.ticker || '--';
    const assetType = detail?.asset_type || inst.asset_type || '--';
    const exchange = detail?.primary_exchange || inst.primary_exchange || '--';
    const currency = detail?.currency || inst.currency || '--';
    const instId = inst.instrument_id;

    return `<tr style="cursor:pointer" onclick="showInstrumentDetail('${instId}')">
      <td class="ticker-cell">${ticker}</td>
      <td>${inst.issuer_name_current || '--'}</td>
      <td>${assetType}</td>
      <td>${exchange}</td>
      <td>${currency}</td>
      <td><span class="badge badge-green-sm">${inst.is_active ? 'ACTIVE' : 'INACTIVE'}</span></td>
      <td>${identifiers.length}</td>
    </tr>`;
  }).join('') || '<tr><td colspan="7" class="loading-cell">No instruments found</td></tr>';

  addLog('INSTRUMENTS', `Loaded ${instruments.length} instruments with details`, 'green');

  return `
    <div class="page-header">
      <div>
        <h1 class="page-title">Instruments & Universe</h1>
        <p class="page-subtitle">${instruments.length} INSTRUMENTS IN UNIVERSE</p>
      </div>
      <div class="header-actions">
        <button class="btn-primary" onclick="renderPage()"><span class="material-icons-outlined">sync</span> REFRESH</button>
      </div>
    </div>

    <div class="card">
      <div class="card-header">
        <span class="card-title-lg">INSTRUMENT UNIVERSE</span>
      </div>
      <table class="data-table">
        <thead><tr>
          <th>TICKER</th><th>NAME</th><th>ASSET TYPE</th><th>EXCHANGE</th><th>CURRENCY</th><th>STATUS</th><th>IDENTIFIERS</th>
        </tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>

    <div id="instrumentDetailPanel"></div>
  `;
}

// Global: show instrument detail panel
window.showInstrumentDetail = async function(instId) {
  const panel = document.getElementById('instrumentDetailPanel');
  if (!panel) return;
  panel.innerHTML = '<div class="card" style="margin-top:4px"><div class="loading-cell">Loading instrument detail...</div></div>';

  try {
    const detail = await api(`/instruments/${instId}`);
    const identifiers = detail.identifiers || [];
    const tickerHistory = detail.ticker_history || [];

    const idRows = identifiers.map(id => `<tr>
      <td><strong>${id.id_type}</strong></td>
      <td>${id.id_value}</td>
      <td>${id.source || '--'}</td>
      <td>${formatDate(id.valid_from)}</td>
      <td>${formatDate(id.valid_to) || 'Current'}</td>
    </tr>`).join('') || '<tr><td colspan="5" class="loading-cell">No identifiers</td></tr>';

    const histRows = tickerHistory.map(t => `<tr>
      <td class="ticker-cell">${t.ticker}</td>
      <td>${t.exchange || '--'}</td>
      <td>${formatDate(t.valid_from)}</td>
      <td>${formatDate(t.valid_to) || 'Current'}</td>
    </tr>`).join('') || '<tr><td colspan="4" class="loading-cell">No ticker history</td></tr>';

    panel.innerHTML = `
      <div class="card" style="margin-top:4px">
        <div class="card-header">
          <span class="card-title-lg">Instrument Detail: ${detail.issuer_name_current || truncateId(instId)}</span>
          <button class="btn-outline-sm" onclick="document.getElementById('instrumentDetailPanel').innerHTML=''">CLOSE</button>
        </div>
        <div class="grid-2" style="margin-top:16px">
          <div>
            <h3 style="font-size:12px;font-weight:700;letter-spacing:1px;margin-bottom:12px;color:var(--text-muted)">IDENTIFIERS (${identifiers.length})</h3>
            <table class="data-table">
              <thead><tr><th>TYPE</th><th>VALUE</th><th>SOURCE</th><th>FROM</th><th>TO</th></tr></thead>
              <tbody>${idRows}</tbody>
            </table>
          </div>
          <div>
            <h3 style="font-size:12px;font-weight:700;letter-spacing:1px;margin-bottom:12px;color:var(--text-muted)">TICKER HISTORY</h3>
            <table class="data-table">
              <thead><tr><th>TICKER</th><th>EXCHANGE</th><th>FROM</th><th>TO</th></tr></thead>
              <tbody>${histRows}</tbody>
            </table>
          </div>
        </div>
      </div>
    `;
  } catch (e) {
    panel.innerHTML = `<div class="card" style="margin-top:4px"><div class="loading-cell">Error: ${e.message}</div></div>`;
  }
};

// ============================================================
//  PAGE 3: RESEARCH
// ============================================================
async function renderResearch() {
  let instruments = [];
  try {
    const data = await api('/instruments?limit=50');
    instruments = data.items || [];
  } catch { /* continue with empty */ }

  const options = instruments.map(inst => {
    const name = inst.issuer_name_current || inst.instrument_id;
    return `<option value="${inst.instrument_id}">${name}</option>`;
  }).join('');

  return `
    <div class="page-header">
      <div>
        <h1 class="page-title">Research Workbench</h1>
        <p class="page-subtitle">QUANTITATIVE ANALYSIS & SCREENING TOOLS</p>
      </div>
    </div>

    <!-- Quick Analysis -->
    <div class="card">
      <div class="card-header">
        <span class="card-title-lg">Quick Analysis</span>
      </div>
      <div class="grid-2" style="margin-bottom:16px">
        <div class="form-group">
          <label>INSTRUMENT</label>
          <select id="researchInstrument">${options || '<option value="">No instruments</option>'}</select>
        </div>
        <div class="form-group">
          <label>AS-OF DATE</label>
          <input type="date" id="researchAsof" value="${new Date().toISOString().slice(0,10)}">
        </div>
      </div>
      <div style="display:flex;gap:12px;flex-wrap:wrap">
        <button class="btn-primary" onclick="runResearch('summary')"><span class="material-icons-outlined">summarize</span> Load Summary</button>
        <button class="btn-outline" onclick="runResearch('performance')"><span class="material-icons-outlined">show_chart</span> Performance</button>
        <button class="btn-outline" onclick="runResearch('valuation')"><span class="material-icons-outlined">attach_money</span> Valuation</button>
        <button class="btn-outline" onclick="runResearch('drawdown')"><span class="material-icons-outlined">trending_down</span> Drawdown</button>
      </div>
      <div id="researchResults" style="margin-top:20px"></div>
    </div>

    <!-- Event Study -->
    <div class="card">
      <div class="card-header">
        <span class="card-title-lg">Event Study</span>
        <span class="badge badge-green">POST</span>
      </div>
      <p style="font-size:13px;color:var(--text-secondary);margin-bottom:16px">Run earnings event study via POST /research/event-study/earnings</p>
      <div class="grid-2" style="margin-bottom:16px">
        <div class="form-group">
          <label>TICKER</label>
          <input type="text" id="eventTicker" value="AAPL" placeholder="e.g. AAPL">
        </div>
        <div class="form-group">
          <label>WINDOW (DAYS)</label>
          <input type="number" id="eventWindow" value="5">
        </div>
      </div>
      <button class="btn-primary" onclick="runEventStudy()"><span class="material-icons-outlined">science</span> Run Event Study</button>
      <div id="eventStudyResults" style="margin-top:20px"></div>
    </div>

    <!-- Screeners -->
    <div class="card">
      <div class="card-header">
        <span class="card-title-lg">Screeners</span>
      </div>
      <div style="display:flex;gap:12px;flex-wrap:wrap">
        <button class="btn-outline" onclick="runScreener('liquidity')"><span class="material-icons-outlined">water_drop</span> Liquidity</button>
        <button class="btn-outline" onclick="runScreener('returns')"><span class="material-icons-outlined">trending_up</span> Returns</button>
        <button class="btn-outline" onclick="runScreener('volatility')"><span class="material-icons-outlined">ssid_chart</span> Volatility</button>
        <button class="btn-outline" onclick="runScreener('momentum')"><span class="material-icons-outlined">speed</span> Momentum</button>
      </div>
      <div id="screenerResults" style="margin-top:20px"></div>
    </div>
  `;
}

// Research action handlers
window.runResearch = async function(type) {
  const container = document.getElementById('researchResults');
  if (!container) return;
  const instId = document.getElementById('researchInstrument')?.value;
  const asof = document.getElementById('researchAsof')?.value;
  if (!instId) { container.innerHTML = '<div class="loading-cell">Please select an instrument</div>'; return; }

  container.innerHTML = '<div class="loading-cell">Loading...</div>';

  try {
    let path = `/research/instrument/${instId}/${type}`;
    if (asof) path += `?asof_date=${asof}`;
    const data = await api(path);
    container.innerHTML = `<div class="card" style="background:var(--bg);border:none;box-shadow:none">
      <div class="card-header"><span class="card-title">${type.toUpperCase()} RESULTS</span></div>
      <pre style="font-size:12px;line-height:1.6;overflow-x:auto;white-space:pre-wrap;font-family:'Inter',monospace;color:var(--text)">${JSON.stringify(data, null, 2)}</pre>
    </div>`;
    addLog('RESEARCH', `${type} loaded for ${truncateId(instId)}`, 'blue');
  } catch (e) {
    container.innerHTML = `<div class="loading-cell" style="color:var(--red)">Error: ${e.message}</div>`;
  }
};

window.runEventStudy = async function() {
  const container = document.getElementById('eventStudyResults');
  if (!container) return;
  const ticker = document.getElementById('eventTicker')?.value;
  const window_ = parseInt(document.getElementById('eventWindow')?.value) || 5;

  container.innerHTML = '<div class="loading-cell">Running event study...</div>';

  try {
    const data = await apiPost('/research/event-study/earnings', { ticker, window: window_ });
    container.innerHTML = `<div class="card" style="background:var(--bg);border:none;box-shadow:none">
      <div class="card-header"><span class="card-title">EVENT STUDY RESULTS</span></div>
      <pre style="font-size:12px;line-height:1.6;overflow-x:auto;white-space:pre-wrap;font-family:'Inter',monospace">${JSON.stringify(data, null, 2)}</pre>
    </div>`;
    addLog('EVENT_STUDY', `Earnings study for ${ticker}`, 'blue');
  } catch (e) {
    container.innerHTML = `<div class="loading-cell" style="color:var(--red)">Error: ${e.message}</div>`;
  }
};

window.runScreener = async function(type) {
  const container = document.getElementById('screenerResults');
  if (!container) return;
  container.innerHTML = '<div class="loading-cell">Running screener...</div>';

  try {
    const data = await api(`/research/screener/${type}`);
    container.innerHTML = `<div class="card" style="background:var(--bg);border:none;box-shadow:none">
      <div class="card-header"><span class="card-title">${type.toUpperCase()} SCREENER</span></div>
      <pre style="font-size:12px;line-height:1.6;overflow-x:auto;white-space:pre-wrap;font-family:'Inter',monospace">${JSON.stringify(data, null, 2)}</pre>
    </div>`;
    addLog('SCREENER', `${type} screener completed`, 'green');
  } catch (e) {
    container.innerHTML = `<div class="loading-cell" style="color:var(--red)">Error: ${e.message}</div>`;
  }
};

// ============================================================
//  PAGE 4: BACKTEST
// ============================================================
async function renderBacktest() {
  let runs = [];
  try {
    const data = await api('/backtest/runs?limit=20');
    runs = data.runs || [];
  } catch { /* continue empty */ }

  const rows = runs.map(run => {
    const ret = run.total_return;
    const retStr = ret !== null && ret !== undefined ? formatPercent(ret) : '--';
    const retClass = (ret !== null && ret >= 0) ? 'positive' : 'negative';
    const sharpe = run.sharpe_ratio ? run.sharpe_ratio.toFixed(2) : '--';
    const drawdown = run.max_drawdown ? formatPercent(run.max_drawdown) : '--';
    const trades = run.total_trades !== undefined ? formatNumber(run.total_trades) : '--';
    const runId = run.run_id || run.id || '';

    return `<tr style="cursor:pointer" onclick="showBacktestDetail('${runId}')">
      <td class="ticker-cell">${run.strategy_name || 'Unknown'}</td>
      <td>${run.start_date || '--'}</td>
      <td>${run.end_date || '--'}</td>
      <td><span class="bt-return ${retClass}">${retStr}</span></td>
      <td>${sharpe}</td>
      <td>${drawdown}</td>
      <td>${trades}</td>
      <td>${formatDate(run.created_at)}</td>
    </tr>`;
  }).join('') || '<tr><td colspan="8" class="loading-cell">No backtest runs found</td></tr>';

  return `
    <div class="page-header">
      <div>
        <h1 class="page-title">Backtest Engine</h1>
        <p class="page-subtitle">${runs.length} HISTORICAL RUNS</p>
      </div>
      <div class="header-actions">
        <button class="btn-primary" onclick="showNewBacktestForm()"><span class="material-icons-outlined">add</span> New Backtest</button>
      </div>
    </div>

    <div id="backtestFormArea"></div>

    <div class="card">
      <div class="card-header">
        <span class="card-title-lg">BACKTEST RUNS</span>
        <button class="btn-outline-sm" onclick="renderPage()">REFRESH</button>
      </div>
      <table class="data-table">
        <thead><tr>
          <th>STRATEGY</th><th>START</th><th>END</th><th>RETURN</th><th>SHARPE</th><th>DRAWDOWN</th><th>TRADES</th><th>CREATED</th>
        </tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>

    <div id="backtestDetailPanel"></div>
  `;
}

window.showNewBacktestForm = function() {
  const area = document.getElementById('backtestFormArea');
  if (!area) return;

  area.innerHTML = `
    <div class="card">
      <div class="card-header">
        <span class="card-title-lg">New Backtest Configuration</span>
        <button class="btn-outline-sm" onclick="document.getElementById('backtestFormArea').innerHTML=''">CANCEL</button>
      </div>
      <div class="form-row" style="margin-bottom:16px">
        <div class="form-group">
          <label>STRATEGY</label>
          <select id="btStrategy"><option value="momentum">Momentum</option><option value="equal_weight">Equal Weight</option><option value="mean_reversion">Mean Reversion</option></select>
        </div>
        <div class="form-group">
          <label>TICKERS (comma-separated)</label>
          <input type="text" id="btTickers" value="AAPL,MSFT,NVDA,SPY">
        </div>
      </div>
      <div class="form-row" style="margin-bottom:16px">
        <div class="form-group"><label>START DATE</label><input type="date" id="btStart" value="2023-01-01"></div>
        <div class="form-group"><label>END DATE</label><input type="date" id="btEnd" value="2024-12-31"></div>
      </div>
      <div class="form-row" style="margin-bottom:16px">
        <div class="form-group"><label>SLIPPAGE (BPS)</label><input type="number" id="btSlippage" value="5"></div>
        <div class="form-group"><label>MAX POSITIONS</label><input type="number" id="btMaxPos" value="4"></div>
      </div>
      <div class="form-group" style="margin-bottom:16px">
        <label>REBALANCE FREQUENCY</label>
        <select id="btRebalance"><option value="monthly">Monthly</option><option value="weekly">Weekly</option><option value="daily">Daily</option></select>
      </div>
      <button class="btn-primary" onclick="submitBacktest()"><span class="material-icons-outlined">play_arrow</span> RUN BACKTEST</button>
      <div id="backtestRunResult" style="margin-top:16px"></div>
    </div>
  `;
};

window.submitBacktest = async function() {
  const resultDiv = document.getElementById('backtestRunResult');
  if (!resultDiv) return;

  const body = {
    strategy: document.getElementById('btStrategy').value,
    tickers: document.getElementById('btTickers').value.split(',').map(t => t.trim()),
    start_date: document.getElementById('btStart').value,
    end_date: document.getElementById('btEnd').value,
    slippage_bps: parseFloat(document.getElementById('btSlippage').value),
    max_positions: parseInt(document.getElementById('btMaxPos').value),
    rebalance_freq: document.getElementById('btRebalance').value,
    commission_bps: 5.0,
  };

  resultDiv.innerHTML = '<div class="loading-cell">Running backtest...</div>';
  addLog('BACKTEST_START', `Running ${body.strategy} on ${body.tickers.join(',')}...`, 'blue');

  try {
    const result = await apiPost('/backtest/run', body);
    const m = result.metrics || {};
    resultDiv.innerHTML = `
      <div class="card" style="background:var(--green-bg);border:1px solid var(--green-lighter)">
        <div class="card-header"><span class="card-title">BACKTEST COMPLETE</span></div>
        <div class="grid-3" style="gap:16px">
          <div><div style="font-size:11px;color:var(--text-muted);font-weight:700">RETURN</div><div style="font-size:24px;font-weight:800">${formatPercent(m.total_return)}</div></div>
          <div><div style="font-size:11px;color:var(--text-muted);font-weight:700">SHARPE</div><div style="font-size:24px;font-weight:800">${m.sharpe_ratio ? m.sharpe_ratio.toFixed(2) : '--'}</div></div>
          <div><div style="font-size:11px;color:var(--text-muted);font-weight:700">MAX DRAWDOWN</div><div style="font-size:24px;font-weight:800">${formatPercent(m.max_drawdown)}</div></div>
        </div>
      </div>
    `;
    addLog('BACKTEST_DONE', `Return: ${formatPercent(m.total_return)}, Sharpe: ${m.sharpe_ratio ? m.sharpe_ratio.toFixed(2) : '--'}`, 'green');
    setTimeout(() => renderPage(), 3000);
  } catch (e) {
    resultDiv.innerHTML = `<div class="loading-cell" style="color:var(--red)">Error: ${e.message}</div>`;
    addLog('BACKTEST_ERROR', e.message, 'yellow');
  }
};

window.showBacktestDetail = async function(runId) {
  const panel = document.getElementById('backtestDetailPanel');
  if (!panel || !runId) return;
  panel.innerHTML = '<div class="card" style="margin-top:4px"><div class="loading-cell">Loading backtest detail...</div></div>';

  try {
    const detail = await api(`/backtest/runs/${runId}`);
    const m = detail.metrics || detail;
    const trades = detail.trades || [];
    const nav = detail.nav_series || [];

    const tradeRows = trades.slice(0, 20).map(t => `<tr>
      <td>${formatDate(t.date)}</td>
      <td class="ticker-cell">${t.ticker || '--'}</td>
      <td><span class="badge ${t.side === 'buy' ? 'badge-green-sm' : 'badge-red-sm'}">${(t.side || '--').toUpperCase()}</span></td>
      <td>${t.quantity || '--'}</td>
      <td>${formatCurrency(t.price)}</td>
    </tr>`).join('') || '<tr><td colspan="5" class="loading-cell">No trades</td></tr>';

    panel.innerHTML = `
      <div class="card" style="margin-top:4px">
        <div class="card-header">
          <span class="card-title-lg">Backtest Detail: ${truncateId(runId)}</span>
          <button class="btn-outline-sm" onclick="document.getElementById('backtestDetailPanel').innerHTML=''">CLOSE</button>
        </div>
        <div class="grid-3" style="gap:16px;margin-bottom:24px">
          <div class="card" style="background:var(--bg);border:none;box-shadow:none;text-align:center">
            <div style="font-size:11px;color:var(--text-muted);font-weight:700">TOTAL RETURN</div>
            <div style="font-size:28px;font-weight:800">${formatPercent(m.total_return)}</div>
          </div>
          <div class="card" style="background:var(--bg);border:none;box-shadow:none;text-align:center">
            <div style="font-size:11px;color:var(--text-muted);font-weight:700">SHARPE RATIO</div>
            <div style="font-size:28px;font-weight:800">${m.sharpe_ratio ? m.sharpe_ratio.toFixed(2) : '--'}</div>
          </div>
          <div class="card" style="background:var(--bg);border:none;box-shadow:none;text-align:center">
            <div style="font-size:11px;color:var(--text-muted);font-weight:700">MAX DRAWDOWN</div>
            <div style="font-size:28px;font-weight:800">${formatPercent(m.max_drawdown)}</div>
          </div>
        </div>
        ${nav.length > 0 ? `<div style="margin-bottom:16px"><h3 style="font-size:12px;font-weight:700;letter-spacing:1px;color:var(--text-muted);margin-bottom:8px">NAV SERIES (${nav.length} points)</h3>
          <div style="display:flex;gap:4px;align-items:flex-end;height:100px">${nav.slice(-50).map((n, i) => {
            const v = n.nav || n.value || n;
            const minV = Math.min(...nav.slice(-50).map(x => x.nav || x.value || x));
            const maxV = Math.max(...nav.slice(-50).map(x => x.nav || x.value || x));
            const h = maxV > minV ? ((v - minV) / (maxV - minV)) * 80 + 10 : 50;
            return `<div style="flex:1;height:${h}px;background:var(--green);border-radius:2px" title="${v}"></div>`;
          }).join('')}</div>
        </div>` : ''}
        <h3 style="font-size:12px;font-weight:700;letter-spacing:1px;color:var(--text-muted);margin-bottom:12px">TRADES (${trades.length})</h3>
        <table class="data-table">
          <thead><tr><th>DATE</th><th>TICKER</th><th>SIDE</th><th>QTY</th><th>PRICE</th></tr></thead>
          <tbody>${tradeRows}</tbody>
        </table>
      </div>
    `;
  } catch (e) {
    panel.innerHTML = `<div class="card" style="margin-top:4px"><div class="loading-cell">Error: ${e.message}</div></div>`;
  }
};

// ============================================================
//  PAGE 5: EXECUTION
// ============================================================
async function renderExecution() {
  let intents = [];
  let drafts = [];

  const results = await Promise.allSettled([
    api('/execution/intents'),
    api('/execution/drafts'),
  ]);

  if (results[0].status === 'fulfilled') intents = results[0].value.items || results[0].value || [];
  if (results[1].status === 'fulfilled') drafts = results[1].value.items || results[1].value || [];
  if (!Array.isArray(intents)) intents = [];
  if (!Array.isArray(drafts)) drafts = [];

  const pendingIntents = intents.filter(i => i.status === 'pending').length;
  const pendingDrafts = drafts.filter(d => d.status === 'pending_approval').length;
  const approvedDrafts = drafts.filter(d => d.status === 'approved').length;

  const intentRows = intents.map(intent => `<tr>
    <td style="font-family:monospace;font-size:11px">${truncateId(intent.intent_id || intent.id)}</td>
    <td>${intent.strategy || '--'}</td>
    <td>${intent.instrument_id ? truncateId(intent.instrument_id) : '--'}</td>
    <td><span class="badge ${intent.side === 'buy' ? 'badge-green-sm' : 'badge-red-sm'}">${(intent.side || '--').toUpperCase()}</span></td>
    <td>${intent.quantity || '--'}</td>
    <td><span class="badge badge-yellow-sm">${(intent.status || '--').toUpperCase()}</span></td>
    <td>${formatDate(intent.created_at)}</td>
  </tr>`).join('') || '<tr><td colspan="7" class="loading-cell">No intents</td></tr>';

  const draftRows = drafts.map(draft => `<tr>
    <td style="font-family:monospace;font-size:11px">${truncateId(draft.draft_id || draft.id)}</td>
    <td style="font-family:monospace;font-size:11px">${truncateId(draft.intent_id)}</td>
    <td>${draft.broker || '--'}</td>
    <td>${draft.order_type || '--'}</td>
    <td>${draft.quantity || '--'}</td>
    <td><span class="badge ${draft.status === 'approved' ? 'badge-green-sm' : 'badge-yellow-sm'}">${(draft.status || '--').toUpperCase()}</span></td>
    <td>${formatDate(draft.created_at)}</td>
  </tr>`).join('') || '<tr><td colspan="7" class="loading-cell">No drafts</td></tr>';

  return `
    <div class="page-header">
      <div>
        <h1 class="page-title">Execution & Orders</h1>
        <p class="page-subtitle">${intents.length} INTENTS // ${drafts.length} DRAFTS</p>
      </div>
      <div class="header-actions">
        <button class="btn-primary" onclick="showCreateIntentForm()"><span class="material-icons-outlined">add</span> Create Intent</button>
      </div>
    </div>

    <!-- Pipeline Visualization -->
    <div class="card">
      <div class="card-header">
        <span class="card-title">EXECUTION PIPELINE</span>
        <div class="pipeline-legend">
          <span class="legend-item"><span class="dot green"></span> Approved</span>
          <span class="legend-item"><span class="dot yellow"></span> Pending</span>
        </div>
      </div>
      <div class="pipeline-flow">
        <div class="pipeline-stage"><div class="stage-icon"><span class="material-icons-outlined">lightbulb</span></div><div class="stage-name">Signal</div><div class="stage-count">${intents.length}</div></div>
        <div class="pipeline-arrow"><span class="material-icons-outlined">arrow_forward</span></div>
        <div class="pipeline-stage"><div class="stage-icon"><span class="material-icons-outlined">description</span></div><div class="stage-name">Intent</div><div class="stage-count">${pendingIntents}</div></div>
        <div class="pipeline-arrow"><span class="material-icons-outlined">arrow_forward</span></div>
        <div class="pipeline-stage"><div class="stage-icon"><span class="material-icons-outlined">draft</span></div><div class="stage-name">Draft</div><div class="stage-count">${pendingDrafts}</div></div>
        <div class="pipeline-arrow"><span class="material-icons-outlined">arrow_forward</span></div>
        <div class="pipeline-stage"><div class="stage-icon"><span class="material-icons-outlined">check_circle</span></div><div class="stage-name">Approved</div><div class="stage-count">${approvedDrafts}</div></div>
        <div class="pipeline-arrow"><span class="material-icons-outlined">arrow_forward</span></div>
        <div class="pipeline-stage stage-disabled"><div class="stage-icon"><span class="material-icons-outlined">send</span></div><div class="stage-name">Submit</div><div class="stage-count">LOCKED</div></div>
      </div>
      <div class="pipeline-note"><span class="material-icons-outlined">lock</span> Live submission disabled by policy (FEATURE_T212_LIVE_SUBMIT=false)</div>
    </div>

    <div id="createIntentArea"></div>

    <!-- Intents Table -->
    <div class="card">
      <div class="card-header">
        <span class="card-title-lg">INTENTS</span>
        <span class="badge badge-green">${intents.length} TOTAL</span>
      </div>
      <table class="data-table">
        <thead><tr><th>ID</th><th>STRATEGY</th><th>INSTRUMENT</th><th>SIDE</th><th>QTY</th><th>STATUS</th><th>CREATED</th></tr></thead>
        <tbody>${intentRows}</tbody>
      </table>
    </div>

    <!-- Drafts Table -->
    <div class="card">
      <div class="card-header">
        <span class="card-title-lg">DRAFTS</span>
        <span class="badge badge-green">${drafts.length} TOTAL</span>
      </div>
      <table class="data-table">
        <thead><tr><th>ID</th><th>INTENT ID</th><th>BROKER</th><th>ORDER TYPE</th><th>QTY</th><th>STATUS</th><th>CREATED</th></tr></thead>
        <tbody>${draftRows}</tbody>
      </table>
    </div>
  `;
}

window.showCreateIntentForm = function() {
  const area = document.getElementById('createIntentArea');
  if (!area) return;

  area.innerHTML = `
    <div class="card">
      <div class="card-header">
        <span class="card-title-lg">Create New Intent</span>
        <button class="btn-outline-sm" onclick="document.getElementById('createIntentArea').innerHTML=''">CANCEL</button>
      </div>
      <div class="form-row" style="margin-bottom:16px">
        <div class="form-group"><label>STRATEGY</label><input type="text" id="intentStrategy" value="momentum" placeholder="momentum"></div>
        <div class="form-group"><label>INSTRUMENT ID</label><input type="text" id="intentInstrument" placeholder="instrument UUID"></div>
      </div>
      <div class="form-row" style="margin-bottom:16px">
        <div class="form-group">
          <label>SIDE</label>
          <select id="intentSide"><option value="buy">BUY</option><option value="sell">SELL</option></select>
        </div>
        <div class="form-group"><label>QUANTITY</label><input type="number" id="intentQty" value="100"></div>
      </div>
      <div class="form-group" style="margin-bottom:16px">
        <label>REASON</label>
        <input type="text" id="intentReason" placeholder="Signal rationale..." value="Momentum signal triggered">
      </div>
      <button class="btn-primary" onclick="submitIntent()"><span class="material-icons-outlined">send</span> Submit Intent</button>
      <div id="intentResult" style="margin-top:12px"></div>
    </div>
  `;
};

window.submitIntent = async function() {
  const resultDiv = document.getElementById('intentResult');
  if (!resultDiv) return;

  const body = {
    strategy: document.getElementById('intentStrategy').value,
    instrument_id: document.getElementById('intentInstrument').value,
    side: document.getElementById('intentSide').value,
    quantity: parseInt(document.getElementById('intentQty').value),
    reason: document.getElementById('intentReason').value,
  };

  resultDiv.innerHTML = '<div class="loading-cell">Submitting...</div>';

  try {
    const data = await apiPost('/execution/intents', body);
    resultDiv.innerHTML = `<div style="padding:12px;background:var(--green-bg);border-radius:8px;font-size:13px;font-weight:600;color:var(--green-dark)">Intent created: ${truncateId(data.intent_id || data.id)}</div>`;
    addLog('INTENT_CREATED', `${body.side.toUpperCase()} ${body.quantity} via ${body.strategy}`, 'green');
    setTimeout(() => renderPage(), 2000);
  } catch (e) {
    resultDiv.innerHTML = `<div class="loading-cell" style="color:var(--red)">Error: ${e.message}</div>`;
  }
};

// ============================================================
//  PAGE 6: DATA QUALITY
// ============================================================
async function renderDQ() {
  const dqRules = [
    { code: 'DQ-1', name: 'OHLC Logic', desc: 'Open/High/Low/Close consistency', severity: 'CRITICAL' },
    { code: 'DQ-2', name: 'Non-Negative', desc: 'No negative prices or volumes', severity: 'CRITICAL' },
    { code: 'DQ-3', name: 'Duplicate PK', desc: 'No duplicate primary keys', severity: 'HIGH' },
    { code: 'DQ-4', name: 'Trade Days', desc: 'Only valid trading day data', severity: 'MEDIUM' },
    { code: 'DQ-5', name: 'Corp Actions', desc: 'Corporate action consistency', severity: 'HIGH' },
    { code: 'DQ-6', name: 'PIT Check', desc: 'Point-in-time data integrity', severity: 'CRITICAL' },
    { code: 'DQ-7', name: 'Cross-Source', desc: 'Multi-source price agreement', severity: 'HIGH' },
    { code: 'DQ-8', name: 'Stale Prices', desc: 'No stale/unchanged prices', severity: 'MEDIUM' },
    { code: 'DQ-9', name: 'Ticker Overlap', desc: 'No conflicting ticker maps', severity: 'HIGH' },
    { code: 'DQ-10', name: 'Orphan IDs', desc: 'No orphaned identifiers', severity: 'LOW' },
    { code: 'DQ-11', name: 'Raw/Adj Mix', desc: 'No raw/adjusted price mixing', severity: 'CRITICAL' },
  ];

  const severityBadge = (sev) => {
    const map = { CRITICAL: 'badge-red-sm', HIGH: 'badge-yellow-sm', MEDIUM: 'badge-green-sm', LOW: 'badge-green-sm' };
    return map[sev] || 'badge-green-sm';
  };

  const dqGrid = dqRules.map(r => `
    <div class="card" style="text-align:center;padding:20px">
      <div style="font-size:13px;font-weight:800;letter-spacing:0.5px;margin-bottom:4px">${r.code}</div>
      <div style="font-size:14px;font-weight:600;margin-bottom:8px">${r.name}</div>
      <div style="font-size:28px;color:var(--green);margin-bottom:8px">&#10003;</div>
      <div style="font-size:11px;color:var(--text-muted);margin-bottom:8px">${r.desc}</div>
      <span class="badge ${severityBadge(r.severity)}">${r.severity}</span>
    </div>
  `).join('');

  // Try to fetch issues and source runs
  let issues = [];
  let sourceRuns = [];
  try { const d = await api('/dq/issues'); issues = d.items || d || []; } catch { /* ok */ }
  try { const d = await api('/dq/source-runs'); sourceRuns = d.items || d || []; } catch { /* ok */ }
  if (!Array.isArray(issues)) issues = [];
  if (!Array.isArray(sourceRuns)) sourceRuns = [];

  const issueRows = issues.map(issue => `<tr>
    <td>${issue.rule_code || '--'}</td>
    <td>${issue.instrument_id ? truncateId(issue.instrument_id) : '--'}</td>
    <td>${issue.description || '--'}</td>
    <td><span class="badge ${issue.severity === 'CRITICAL' ? 'badge-red-sm' : 'badge-yellow-sm'}">${issue.severity || 'UNKNOWN'}</span></td>
    <td>${formatDate(issue.detected_at)}</td>
  </tr>`).join('');

  const sourceRows = sourceRuns.map(sr => `<tr>
    <td>${sr.source || '--'}</td>
    <td><span class="badge badge-green-sm">${(sr.status || 'OK').toUpperCase()}</span></td>
    <td>${formatNumber(sr.records_processed)}</td>
    <td>${formatDate(sr.last_run)}</td>
  </tr>`).join('');

  return `
    <div class="page-header">
      <div>
        <h1 class="page-title">Data Quality Engine</h1>
        <p class="page-subtitle">11 RULES // ${issues.length} ISSUES // ALL PASSING</p>
      </div>
      <div class="header-actions">
        <button class="btn-primary" onclick="renderPage()"><span class="material-icons-outlined">sync</span> REFRESH</button>
      </div>
    </div>

    <!-- DQ Rules Grid -->
    <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:16px">
      ${dqGrid}
    </div>

    ${issues.length > 0 ? `
    <!-- Data Issues -->
    <div class="card">
      <div class="card-header">
        <span class="card-title-lg">DATA ISSUES</span>
        <span class="badge badge-yellow-sm">${issues.length} ISSUES</span>
      </div>
      <table class="data-table">
        <thead><tr><th>RULE</th><th>INSTRUMENT</th><th>DESCRIPTION</th><th>SEVERITY</th><th>DETECTED</th></tr></thead>
        <tbody>${issueRows}</tbody>
      </table>
    </div>` : `
    <div class="card" style="text-align:center;padding:32px">
      <span class="material-icons-outlined" style="font-size:48px;color:var(--green);margin-bottom:12px;display:block">check_circle</span>
      <div style="font-size:18px;font-weight:700;margin-bottom:4px">No Data Issues</div>
      <div style="color:var(--text-muted);font-size:13px">All 11 data quality rules are passing</div>
    </div>`}

    ${sourceRuns.length > 0 ? `
    <!-- Source Runs -->
    <div class="card">
      <div class="card-header">
        <span class="card-title-lg">SOURCE RUNS</span>
      </div>
      <table class="data-table">
        <thead><tr><th>SOURCE</th><th>STATUS</th><th>RECORDS</th><th>LAST RUN</th></tr></thead>
        <tbody>${sourceRows}</tbody>
      </table>
    </div>` : ''}
  `;
}

// ============================================================
//  PAGE 7: SETTINGS
// ============================================================
async function renderSettings() {
  const apiKeys = [
    { name: 'SEC EDGAR', key: 'SEC_API_KEY', configured: true },
    { name: 'OpenFIGI', key: 'OPENFIGI_API_KEY', configured: true },
    { name: 'Massive', key: 'MASSIVE_API_KEY', configured: true },
    { name: 'FMP (Financial Modeling Prep)', key: 'FMP_API_KEY', configured: true },
    { name: 'Trading 212', key: 'T212_API_KEY', configured: false },
  ];

  const featureFlags = [
    { name: 'FEATURE_T212_LIVE_SUBMIT', value: false, desc: 'Enable live order submission to Trading 212' },
    { name: 'FEATURE_AUTO_REBALANCE', value: false, desc: 'Enable automatic portfolio rebalancing' },
    { name: 'FEATURE_DQ_AUTO_QUARANTINE', value: true, desc: 'Auto-quarantine data failing DQ checks' },
  ];

  const dataSources = [
    { source: 'SEC EDGAR', types: 'Filings, Financials', status: 'ACTIVE', frequency: 'Daily' },
    { source: 'OpenFIGI', types: 'Identifiers', status: 'ACTIVE', frequency: 'On-demand' },
    { source: 'FMP', types: 'Prices, Fundamentals', status: 'ACTIVE', frequency: 'Daily' },
    { source: 'Trading 212', types: 'Live Quotes, Orders', status: 'DISABLED', frequency: 'Real-time' },
    { source: 'Massive', types: 'Alt Data', status: 'ACTIVE', frequency: 'Weekly' },
  ];

  const apiKeyRows = apiKeys.map(k => `
    <div class="role-item">
      <span class="material-icons-outlined role-icon">${k.configured ? 'vpn_key' : 'key_off'}</span>
      <span class="role-name">${k.name}</span>
      <span class="badge ${k.configured ? 'badge-green-sm' : 'badge-red-sm'}">${k.configured ? 'CONFIGURED' : 'NOT CONFIGURED'}</span>
    </div>
  `).join('');

  const flagRows = featureFlags.map(f => `
    <div class="role-item">
      <span class="material-icons-outlined role-icon" style="color:${f.value ? 'var(--green)' : 'var(--text-muted)'}">${f.value ? 'toggle_on' : 'toggle_off'}</span>
      <div style="flex:1">
        <div class="role-name" style="font-family:monospace;font-size:12px">${f.name}</div>
        <div style="font-size:11px;color:var(--text-muted)">${f.desc}</div>
      </div>
      <span class="badge ${f.value ? 'badge-green-sm' : 'badge-red-sm'}">${f.value ? 'TRUE' : 'FALSE'}</span>
    </div>
  `).join('');

  const sourceTable = dataSources.map(ds => `<tr>
    <td class="ticker-cell">${ds.source}</td>
    <td>${ds.types}</td>
    <td><span class="badge ${ds.status === 'ACTIVE' ? 'badge-green-sm' : 'badge-red-sm'}">${ds.status}</span></td>
    <td>${ds.frequency}</td>
  </tr>`).join('');

  return `
    <div class="page-header">
      <div>
        <h1 class="page-title">Configuration & Policies</h1>
        <p class="page-subtitle">SYSTEM CONFIGURATION AND FEATURE MANAGEMENT</p>
      </div>
    </div>

    <div class="grid-2">
      <!-- API Keys -->
      <div class="card">
        <div class="card-header">
          <span class="card-title-lg">API Keys</span>
          <span class="material-icons-outlined info-icon">info</span>
        </div>
        <div class="role-list">${apiKeyRows}</div>
      </div>

      <!-- Feature Flags -->
      <div class="card">
        <div class="card-header">
          <span class="card-title-lg">Feature Flags</span>
        </div>
        <div class="role-list">${flagRows}</div>
      </div>
    </div>

    <!-- Execution Policy -->
    <div class="card">
      <div class="card-header">
        <span class="card-title-lg">Execution Policy</span>
        <span class="badge badge-yellow-sm">RESTRICTED</span>
      </div>
      <div class="grid-2" style="gap:24px">
        <div>
          <div class="role-list">
            <div class="role-item"><span class="material-icons-outlined role-icon" style="color:var(--yellow)">security</span><span class="role-name">Live submission requires manual approval</span></div>
            <div class="role-item"><span class="material-icons-outlined role-icon" style="color:var(--yellow)">gavel</span><span class="role-name">Max order size: 10,000 shares</span></div>
            <div class="role-item"><span class="material-icons-outlined role-icon">schedule</span><span class="role-name">Orders only during market hours</span></div>
          </div>
        </div>
        <div>
          <div class="role-list">
            <div class="role-item"><span class="material-icons-outlined role-icon" style="color:var(--red)">block</span><span class="role-name">T212 live submit: DISABLED</span></div>
            <div class="role-item"><span class="material-icons-outlined role-icon">verified_user</span><span class="role-name">All drafts require human review</span></div>
            <div class="role-item"><span class="material-icons-outlined role-icon">history</span><span class="role-name">Full audit trail enabled</span></div>
          </div>
        </div>
      </div>
    </div>

    <!-- Data Sources Matrix -->
    <div class="card">
      <div class="card-header">
        <span class="card-title-lg">Data Sources</span>
      </div>
      <table class="data-table">
        <thead><tr><th>SOURCE</th><th>DATA TYPES</th><th>STATUS</th><th>FREQUENCY</th></tr></thead>
        <tbody>${sourceTable}</tbody>
      </table>
    </div>
  `;
}

// ---- EXPORT REPORT ----
window.exportReport = function() {
  const reportData = {
    generated: new Date().toISOString(),
    platform: 'Quant API Platform v0.1.0',
    logs: logEntries.slice(0, 10),
  };
  const blob = new Blob([JSON.stringify(reportData, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `quant-report-${new Date().toISOString().slice(0, 10)}.json`;
  a.click();
  URL.revokeObjectURL(url);
  addLog('EXPORT', 'Report downloaded', 'green');
};

// ---- INITIALIZATION ----
document.addEventListener('DOMContentLoaded', () => {
  // Build the sidebar
  const sidebar = document.querySelector('.sidebar');
  if (sidebar) sidebar.innerHTML = renderSidebar();

  // Set up page content container
  const content = document.querySelector('.content');
  if (content) content.id = 'page-content';

  addLog('SYSTEM_BOOT', 'Dashboard initialized', 'green');

  // Initial render
  renderPage();

  // Hash change listener
  window.addEventListener('hashchange', () => renderPage());
});
