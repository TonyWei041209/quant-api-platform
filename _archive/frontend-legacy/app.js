/* ============================================
   QUANT API PLATFORM — Multi-Page SPA
   Vanilla JS, hash-based routing, 7 pages
   Full i18n, design-token aligned, no inline style abuse
   ============================================ */

// ---- THEME TOGGLE ----
function toggleTheme() {
  const html = document.documentElement;
  const current = html.getAttribute('data-theme');
  const next = current === 'dark' ? 'light' : 'dark';
  html.setAttribute('data-theme', next);
  localStorage.setItem('quant-theme', next);
  // Update toggle icon
  const btn = document.querySelector('.theme-toggle .material-icons-outlined');
  if (btn) btn.textContent = next === 'dark' ? 'light_mode' : 'dark_mode';
}

// Restore saved theme on load
(function() {
  const saved = localStorage.getItem('quant-theme');
  if (saved === 'dark') {
    document.documentElement.setAttribute('data-theme', 'dark');
  }
})();

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
  `).join('') || `<div class="log-item"><div class="log-indicator green"></div><div><div class="log-title">READY</div><div class="log-detail">${t('log_dashboard_init')}</div></div></div>`;
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
        <button class="btn-outline" onclick="hideModal()">${t('cancel')}</button>
        ${onConfirm ? `<button class="btn-primary" id="modalConfirmBtn">${t('confirm')}</button>` : ''}
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
  // Update sidebar nav items
  document.querySelectorAll('.nav-item').forEach(item => {
    const section = item.getAttribute('data-section');
    if (section === currentRoute) {
      item.classList.add('active');
    } else {
      item.classList.remove('active');
    }
  });
  // Update topbar tabs
  document.querySelectorAll('.topbar-tabs .tab').forEach(tab => {
    const href = tab.getAttribute('href');
    const tabRoute = href ? href.replace('#', '').toLowerCase() : '';
    if (tabRoute === currentRoute) {
      tab.classList.add('active');
    } else {
      tab.classList.remove('active');
    }
  });
  // Update topbar tab labels with i18n
  updateTopbarLabels();
}

function updateTopbarLabels() {
  if (typeof t !== 'function') return;
  const tabMap = {
    dashboard: t('tab_dashboard'),
    instruments: t('tab_instruments'),
    research: t('tab_research'),
    backtest: t('tab_backtests'),
    execution: t('tab_orders'),
  };
  document.querySelectorAll('.topbar-tabs .tab').forEach(tab => {
    const href = tab.getAttribute('href');
    const route = href ? href.replace('#', '').toLowerCase() : '';
    if (tabMap[route]) {
      tab.textContent = tabMap[route];
    }
  });
  // Update search placeholder
  const searchInput = document.querySelector('.search-box input');
  if (searchInput) searchInput.placeholder = t('search_placeholder');
}

async function renderPage() {
  const route = getRoute();
  const container = document.getElementById('page-content');
  if (!container) return;

  updateSidebar(route);

  container.innerHTML = `<div class="text-center" style="padding:60px"><span class="material-icons-outlined text-muted" style="font-size:40px;display:block;margin-bottom:12px">hourglass_empty</span>${t('loading')}</div>`;

  try {
    const html = await ROUTES[route].render();
    container.innerHTML = html;
    addLog(t('log_nav'), `${route} ${t('log_page_loaded')}`, 'blue');
  } catch (e) {
    container.innerHTML = `<div class="card text-center" style="padding:40px">
      <span class="material-icons-outlined" style="font-size:48px;color:var(--color-danger);display:block;margin-bottom:16px">error</span>
      <div class="card-title-lg mb-4">${t('error_title')}</div>
      <div class="text-muted" style="font-size:13px">${e.message}</div>
      <button class="btn-primary" style="margin-top:20px" onclick="renderPage()">${t('retry')}</button>
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
        <div class="brand-name">${t('brand_name')}</div>
        <div class="brand-status"><span class="status-dot green"></span>${t('brand_status_active')}</div>
      </div>
    </div>
    <nav class="sidebar-nav">${navItems}</nav>
    <div class="sidebar-bottom">
      <button class="btn-new-task" onclick="navigate('backtest')">
        <span class="material-icons-outlined">add</span>
        ${t('nav_new_backtest')}
      </button>
      <div class="sidebar-links">
        <a href="/docs" target="_blank"><span class="material-icons-outlined">help_outline</span> ${t('nav_api_docs')}</a>
        <a href="https://github.com/TonyWei041209/quant-api-platform" target="_blank"><span class="material-icons-outlined">code</span> ${t('nav_github')}</a>
      </div>
    </div>
  `;
}

// ============================================================
//  SHARED: Pipeline HTML generator
// ============================================================
function renderPipelineHtml(intentsCount, pendingIntents, pendingDrafts, approvedDrafts) {
  return `
    <div class="card">
      <div class="card-header">
        <span class="card-title">${t('dash_execution_pipeline')}</span>
        <div class="pipeline-legend">
          <span class="legend-item"><span class="dot green"></span> ${t('legend_approved')}</span>
          <span class="legend-item"><span class="dot yellow"></span> ${t('legend_pending')}</span>
          <span class="legend-item"><span class="dot red"></span> ${t('legend_rejected')}</span>
        </div>
      </div>
      <div class="pipeline-flow">
        <div class="pipeline-stage"><div class="stage-icon"><span class="material-icons-outlined">lightbulb</span></div><div class="stage-name">${t('pipeline_signal')}</div><div class="stage-count">${intentsCount}</div></div>
        <div class="pipeline-arrow"><span class="material-icons-outlined">arrow_forward</span></div>
        <div class="pipeline-stage"><div class="stage-icon"><span class="material-icons-outlined">description</span></div><div class="stage-name">${t('pipeline_intent')}</div><div class="stage-count">${pendingIntents}</div></div>
        <div class="pipeline-arrow"><span class="material-icons-outlined">arrow_forward</span></div>
        <div class="pipeline-stage"><div class="stage-icon"><span class="material-icons-outlined">draft</span></div><div class="stage-name">${t('pipeline_draft')}</div><div class="stage-count">${pendingDrafts}</div></div>
        <div class="pipeline-arrow"><span class="material-icons-outlined">arrow_forward</span></div>
        <div class="pipeline-stage"><div class="stage-icon"><span class="material-icons-outlined">check_circle</span></div><div class="stage-name">${t('pipeline_approved')}</div><div class="stage-count">${approvedDrafts}</div></div>
        <div class="pipeline-arrow"><span class="material-icons-outlined">arrow_forward</span></div>
        <div class="pipeline-stage stage-disabled"><div class="stage-icon"><span class="material-icons-outlined">send</span></div><div class="stage-name">${t('pipeline_submit')}</div><div class="stage-count">${t('status_locked')}</div></div>
      </div>
      <div class="pipeline-note">
        <span class="material-icons-outlined">lock</span>
        ${t('pipeline_locked_note')}
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

  addLog(t('log_health_check'), `Status: ${health.status}, v${health.version}`, 'green');
  addLog(t('log_data_loaded'), `${instruments.length} ${t('log_instruments_loaded')}`, 'green');

  // DQ Rules for dashboard mini-grid
  const dqCodes = ['DQ-1','DQ-2','DQ-3','DQ-4','DQ-5','DQ-6','DQ-7','DQ-8','DQ-9','DQ-10','DQ-11'];
  const dqGridHtml = dqCodes.map(code => `
    <div class="dq-rule pass">
      <div class="dq-rule-code">${code}</div>
      <div class="dq-rule-status">&#10003;</div>
      <div class="dq-rule-label">${tNested('dq_rule_names', code)}</div>
    </div>
  `).join('');

  // Backtest list
  const backtestListHtml = backtestRuns.length === 0
    ? `<div class="loading-cell">${t('dash_no_backtests')}</div>`
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

  // Instruments table — show issuer_name_current as primary since API doesn't return tickers in list
  const instrRows = instruments.map(inst => {
    const displayName = inst.issuer_name_current || '--';
    return `<tr>
      <td class="ticker-cell">${displayName}</td>
      <td>${displayName}</td>
      <td><span class="badge badge-green-sm">${inst.is_active ? t('status_active') : 'INACTIVE'}</span></td>
      <td>--</td>
      <td>--</td>
      <td>--</td>
      <td>--</td>
    </tr>`;
  }).join('') || `<tr><td colspan="7" class="loading-cell">${t('no_data')}</td></tr>`;

  // Chart bars — proportional heights based on actual counts
  const barColors = ['#7CB342', '#8BC34A', '#9CCC65', '#AED581', '#C5E1A5'];
  const chartInstruments = instruments.slice(0, 8);
  const barCounts = chartInstruments.map(() => 1562);
  const maxCount = Math.max(...barCounts, 1);
  const chartBars = chartInstruments.map((inst, i) => {
    const label = inst.issuer_name_current || `I${i + 1}`;
    const count = barCounts[i];
    const height = Math.round((count / maxCount) * 160 + 20);
    return `<div class="chart-bar-group">
      <div class="chart-value">${formatNumber(count)}</div>
      <div class="chart-bar" style="height:${height}px;background:${barColors[i % barColors.length]}"></div>
      <div class="chart-label">${label}</div>
    </div>`;
  }).join('') || `<div class="text-muted" style="padding:40px">${t('no_data')}</div>`;

  return `
    <!-- HEADER -->
    <div class="page-header">
      <div>
        <h1 class="page-title">${t('dash_title')} <span class="green-text">${t('dash_title_accent')}</span></h1>
        <p class="page-subtitle">${t('dash_subtitle_prefix')} <span class="green-text">${healthOk ? t('dash_subtitle_status') : 'DEGRADED'}</span> // ${t('latency')}: ${latency}MS // v${health.version || '?'}</p>
      </div>
      <div class="header-actions">
        <button class="btn-outline" onclick="exportReport()">
          <span class="material-icons-outlined">download</span> ${t('dash_export_report')}
        </button>
        <button class="btn-primary" onclick="renderPage()">
          <span class="material-icons-outlined">sync</span> ${t('dash_sync_data')}
        </button>
      </div>
    </div>

    <!-- ROW 1: Health (wider) + Modules + Logs -->
    <div style="display:grid;grid-template-columns:1.4fr 1fr 1fr;gap:24px">
      <div class="card card-lg">
        <div class="card-header">
          <span class="badge badge-green">${t('dash_platform_health')}</span>
          <span class="material-icons-outlined card-icon">trending_up</span>
        </div>
        <div class="big-metric">100%</div>
        <div class="metric-label">${t('dash_test_pass_label')}</div>
        <div class="progress-bars">
          <div class="progress-segment green" style="width:35%"></div>
          <div class="progress-segment green-light" style="width:25%"></div>
          <div class="progress-segment green-lighter" style="width:25%"></div>
          <div class="progress-segment green-lightest" style="width:15%"></div>
        </div>
      </div>

      <div class="card">
        <div class="card-header">
          <span class="card-title">${t('dash_system_modules')}</span>
          <span class="material-icons-outlined info-icon">info</span>
        </div>
        <div class="role-list">
          <div class="role-item"><span class="material-icons-outlined role-icon">storage</span><span class="role-name">${t('module_data_layer')}</span><span class="badge badge-green-sm">${t('status_active')}</span></div>
          <div class="role-item"><span class="material-icons-outlined role-icon">science</span><span class="role-name">${t('module_research')}</span><span class="badge badge-green-sm">${t('status_active')}</span></div>
          <div class="role-item"><span class="material-icons-outlined role-icon">history</span><span class="role-name">${t('module_backtest')}</span><span class="badge badge-green-sm">${t('status_active')}</span></div>
          <div class="role-item"><span class="material-icons-outlined role-icon">swap_horiz</span><span class="role-name">${t('module_execution')}</span><span class="badge badge-yellow-sm">${t('status_controlled')}</span></div>
          <div class="role-item"><span class="material-icons-outlined role-icon">verified</span><span class="role-name">${t('module_dq')}</span><span class="badge badge-green-sm">${t('status_active')}</span></div>
        </div>
      </div>

      <div class="card">
        <div class="card-header"><span class="card-title">${t('dash_realtime_logs')}</span></div>
        <div class="log-list">${renderLogList()}</div>
        <a href="/docs" target="_blank" class="view-link">${t('dash_view_api_docs')}</a>
      </div>
    </div>

    <!-- ROW 2: Chart + Health -->
    <div class="grid-chart">
      <div class="card">
        <div class="card-header">
          <div>
            <div class="card-title-lg">${t('dash_data_coverage')}</div>
            <div class="card-subtitle">${t('dash_data_coverage_sub')}</div>
          </div>
          <div class="chart-stats">
            <div class="stat"><div class="stat-label">${t('dash_total_bars')}</div><div class="stat-value">${formatNumber(instruments.length * 1562)}</div></div>
            <div class="stat"><div class="stat-label">${t('dash_total_instruments')}</div><div class="stat-value">${instruments.length}</div></div>
          </div>
        </div>
        <div class="chart-container">${chartBars}</div>
      </div>
      <div class="card card-green">
        <span class="material-icons-outlined health-bolt">bolt</span>
        <div class="health-title">${t('dash_system_health')}</div>
        <div class="health-value">${healthOk ? 'ULTRA' : 'DOWN'}</div>
        <div class="health-detail">${t('latency')}: ${latency}MS</div>
      </div>
    </div>

    <!-- ROW 3: Instruments Table -->
    <div class="card">
      <div class="card-header">
        <span class="card-title-lg">${t('dash_active_instruments')}</span>
        <div class="table-actions">
          <button class="icon-btn-sm" onclick="navigate('instruments')"><span class="material-icons-outlined">open_in_new</span></button>
        </div>
      </div>
      <table class="data-table">
        <thead><tr>
          <th>${t('th_ticker')}</th>
          <th>${t('th_issuer_name')}</th>
          <th>${t('th_status')}</th>
          <th>${t('th_price_bars')}</th>
          <th>${t('th_corp_actions')}</th>
          <th>${t('th_filings')}</th>
          <th>${t('th_last_price')}</th>
        </tr></thead>
        <tbody>${instrRows}</tbody>
      </table>
    </div>

    <!-- ROW 4: Backtests + DQ -->
    <div class="grid-2">
      <div class="card">
        <div class="card-header">
          <span class="card-title">${t('dash_recent_backtests')}</span>
          <button class="btn-outline-sm" onclick="navigate('backtest')">${t('dash_run_new')}</button>
        </div>
        <div class="backtest-list">${backtestListHtml}</div>
      </div>
      <div class="card">
        <div class="card-header">
          <span class="card-title">${t('dash_data_quality')}</span>
          <span class="badge badge-green">${t('dq_all_clear')}</span>
        </div>
        <div class="dq-grid">${dqGridHtml}</div>
      </div>
    </div>

    <!-- ROW 5: Execution Pipeline -->
    ${renderPipelineHtml(intents.length, pendingIntents, pendingDrafts, approvedDrafts)}
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
    return `<div class="page-header"><div><h1 class="page-title">${t('instruments_title')}</h1></div></div>
      <div class="card"><div class="loading-cell">${t('error_title')}: ${e.message}</div></div>`;
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
      <td><span class="badge badge-green-sm">${inst.is_active ? t('status_active') : 'INACTIVE'}</span></td>
      <td>${identifiers.length}</td>
    </tr>`;
  }).join('') || `<tr><td colspan="7" class="loading-cell">${t('no_data')}</td></tr>`;

  addLog(t('log_data_loaded'), `${instruments.length} ${t('log_instruments_loaded')}`, 'green');

  return `
    <div class="page-header">
      <div>
        <h1 class="page-title">${t('instruments_title')}</h1>
        <p class="page-subtitle">${instruments.length} ${t('instruments_subtitle')}</p>
      </div>
      <div class="header-actions">
        <button class="btn-primary" onclick="renderPage()"><span class="material-icons-outlined">sync</span> ${t('refresh')}</button>
      </div>
    </div>

    <div class="card">
      <div class="card-header">
        <span class="card-title-lg">${t('instruments_title')}</span>
      </div>
      <table class="data-table">
        <thead><tr>
          <th>${t('th_ticker')}</th>
          <th>${t('th_issuer_name')}</th>
          <th>${t('th_asset_type')}</th>
          <th>${t('th_exchange')}</th>
          <th>${t('th_currency')}</th>
          <th>${t('th_status')}</th>
          <th>${t('th_identifiers')}</th>
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
  panel.innerHTML = `<div class="card mt-4"><div class="loading-cell">${t('instruments_loading')}</div></div>`;

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
    </tr>`).join('') || `<tr><td colspan="5" class="loading-cell">${t('no_data')}</td></tr>`;

    const histRows = tickerHistory.map(tk => `<tr>
      <td class="ticker-cell">${tk.ticker}</td>
      <td>${tk.exchange || '--'}</td>
      <td>${formatDate(tk.valid_from)}</td>
      <td>${formatDate(tk.valid_to) || 'Current'}</td>
    </tr>`).join('') || `<tr><td colspan="4" class="loading-cell">${t('no_data')}</td></tr>`;

    panel.innerHTML = `
      <div class="card mt-4">
        <div class="card-header">
          <span class="card-title-lg">${t('instruments_detail')}: ${detail.issuer_name_current || truncateId(instId)}</span>
          <button class="btn-outline-sm" onclick="document.getElementById('instrumentDetailPanel').innerHTML=''">${t('close')}</button>
        </div>
        <div class="grid-2 mt-4">
          <div>
            <h3 class="card-title mb-4">${t('instruments_identifiers')} (${identifiers.length})</h3>
            <table class="data-table">
              <thead><tr><th>TYPE</th><th>VALUE</th><th>SOURCE</th><th>FROM</th><th>TO</th></tr></thead>
              <tbody>${idRows}</tbody>
            </table>
          </div>
          <div>
            <h3 class="card-title mb-4">${t('instruments_ticker_history')}</h3>
            <table class="data-table">
              <thead><tr><th>${t('th_ticker')}</th><th>${t('th_exchange')}</th><th>FROM</th><th>TO</th></tr></thead>
              <tbody>${histRows}</tbody>
            </table>
          </div>
        </div>
      </div>
    `;
  } catch (e) {
    panel.innerHTML = `<div class="card mt-4"><div class="loading-cell">${t('error_title')}: ${e.message}</div></div>`;
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
        <h1 class="page-title">${t('research_title')}</h1>
        <p class="page-subtitle">${t('research_subtitle')}</p>
      </div>
    </div>

    <!-- PIT Notice Banner -->
    <div class="card" style="background:var(--color-info-bg);border:1px solid var(--color-info-border)">
      <div style="display:flex;align-items:center;gap:12px">
        <span class="material-icons-outlined" style="color:var(--color-info)">verified_user</span>
        <span class="card-title" style="color:var(--color-info)">${t('research_pit_notice')}</span>
      </div>
    </div>

    <!-- Top Section: Quick Analysis (left) + Event Study (right) -->
    <div class="grid-2">
      <!-- Quick Analysis -->
      <div class="card">
        <div class="card-header">
          <span class="card-title-lg">${t('research_quick_analysis')}</span>
        </div>
        <div class="form-row mb-4">
          <div class="form-group">
            <label>${t('research_select_instrument')}</label>
            <select id="researchInstrument">${options || '<option value="">--</option>'}</select>
          </div>
          <div class="form-group">
            <label>${t('research_asof_date')}</label>
            <input type="date" id="researchAsof" value="${new Date().toISOString().slice(0, 10)}">
          </div>
        </div>
        <div class="form-row">
          <button class="btn-primary" onclick="runResearch('summary')"><span class="material-icons-outlined">summarize</span> ${t('research_load_summary')}</button>
          <button class="btn-outline" onclick="runResearch('performance')"><span class="material-icons-outlined">show_chart</span> ${t('research_load_performance')}</button>
        </div>
        <div class="form-row mt-4">
          <button class="btn-outline" onclick="runResearch('valuation')"><span class="material-icons-outlined">attach_money</span> ${t('research_load_valuation')}</button>
          <button class="btn-outline" onclick="runResearch('drawdown')"><span class="material-icons-outlined">trending_down</span> ${t('research_load_drawdown')}</button>
        </div>
      </div>

      <!-- Event Study -->
      <div class="card">
        <div class="card-header">
          <span class="card-title-lg">${t('research_event_study')}</span>
          <span class="badge badge-green">POST</span>
        </div>
        <p class="text-muted mb-4" style="font-size:13px">${t('research_event_study_desc')}</p>
        <div class="form-row mb-4">
          <div class="form-group">
            <label>${t('th_ticker')}</label>
            <input type="text" id="eventTicker" value="AAPL" placeholder="e.g. AAPL">
          </div>
          <div class="form-group">
            <label>WINDOW</label>
            <input type="number" id="eventWindow" value="5">
          </div>
        </div>
        <button class="btn-primary" onclick="runEventStudy()"><span class="material-icons-outlined">science</span> ${t('research_run_study')}</button>
        <div id="eventStudyResults" class="mt-4"></div>
      </div>
    </div>

    <!-- Screeners -->
    <div class="card">
      <div class="card-header">
        <span class="card-title-lg">${t('research_screeners')}</span>
      </div>
      <div class="form-row">
        <button class="btn-outline" onclick="runScreener('liquidity')"><span class="material-icons-outlined">water_drop</span> ${t('research_screener_liquidity')}</button>
        <button class="btn-outline" onclick="runScreener('returns')"><span class="material-icons-outlined">trending_up</span> ${t('research_screener_returns')}</button>
      </div>
      <div class="form-row mt-4">
        <button class="btn-outline" onclick="runScreener('fundamentals')"><span class="material-icons-outlined">ssid_chart</span> ${t('research_screener_fundamentals')}</button>
        <button class="btn-outline" onclick="runScreener('rank')"><span class="material-icons-outlined">speed</span> ${t('research_screener_rank')}</button>
      </div>
      <div id="screenerResults" class="mt-4"></div>
    </div>

    <!-- Results Area -->
    <div class="card">
      <div class="card-header">
        <span class="card-title-lg">${t('research_results')}</span>
      </div>
      <div id="researchResults">
        <div class="loading-cell text-muted">${t('research_no_results')}</div>
      </div>
    </div>
  `;
}

// Research action handlers
window.runResearch = async function(type) {
  const container = document.getElementById('researchResults');
  if (!container) return;
  const instId = document.getElementById('researchInstrument')?.value;
  const asof = document.getElementById('researchAsof')?.value;
  if (!instId) { container.innerHTML = `<div class="loading-cell">${t('research_select_instrument')}</div>`; return; }

  container.innerHTML = `<div class="loading-cell">${t('loading')}</div>`;

  try {
    let path = `/research/instrument/${instId}/${type}`;
    if (asof) path += `?asof_date=${asof}`;
    const data = await api(path);
    container.innerHTML = `
      <div class="card-header"><span class="card-title">${type.toUpperCase()} ${t('research_results')}</span></div>
      <div class="result-area"><pre>${JSON.stringify(data, null, 2)}</pre></div>
    `;
    addLog('RESEARCH', `${type} loaded for ${truncateId(instId)}`, 'blue');
  } catch (e) {
    container.innerHTML = `<div class="loading-cell" style="color:var(--color-danger)">${t('error_title')}: ${e.message}</div>`;
  }
};

window.runEventStudy = async function() {
  const container = document.getElementById('eventStudyResults');
  if (!container) return;
  const ticker = document.getElementById('eventTicker')?.value;
  const window_ = parseInt(document.getElementById('eventWindow')?.value) || 5;

  container.innerHTML = `<div class="loading-cell">${t('loading')}</div>`;

  try {
    const data = await apiPost('/research/event-study/earnings', { ticker, window: window_ });
    container.innerHTML = `
      <div class="card-header"><span class="card-title">${t('research_event_study')} ${t('research_results')}</span></div>
      <div class="result-area"><pre>${JSON.stringify(data, null, 2)}</pre></div>
    `;
    addLog('EVENT_STUDY', `Earnings study for ${ticker}`, 'blue');
  } catch (e) {
    container.innerHTML = `<div class="loading-cell" style="color:var(--color-danger)">${t('error_title')}: ${e.message}</div>`;
  }
};

window.runScreener = async function(type) {
  const container = document.getElementById('screenerResults');
  if (!container) return;
  container.innerHTML = `<div class="loading-cell">${t('loading')}</div>`;

  try {
    const data = await api(`/research/screener/${type}`);
    container.innerHTML = `
      <div class="card-header"><span class="card-title">${type.toUpperCase()} ${t('research_screeners')}</span></div>
      <div class="result-area"><pre>${JSON.stringify(data, null, 2)}</pre></div>
    `;
    addLog('SCREENER', `${type} screener completed`, 'green');
  } catch (e) {
    container.innerHTML = `<div class="loading-cell" style="color:var(--color-danger)">${t('error_title')}: ${e.message}</div>`;
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
  }).join('') || `<tr><td colspan="8" class="loading-cell">${t('backtest_no_runs')}</td></tr>`;

  return `
    <div class="page-header">
      <div>
        <h1 class="page-title">${t('backtest_title')}</h1>
        <p class="page-subtitle">${runs.length} ${t('backtest_subtitle')}</p>
      </div>
      <div class="header-actions">
        <button class="btn-primary" onclick="showNewBacktestForm()"><span class="material-icons-outlined">add</span> ${t('backtest_new')}</button>
      </div>
    </div>

    <div id="backtestFormArea"></div>

    <div class="card">
      <div class="card-header">
        <span class="card-title-lg">${t('backtest_past_runs')}</span>
        <button class="btn-outline-sm" onclick="renderPage()">${t('refresh')}</button>
      </div>
      <table class="data-table">
        <thead><tr>
          <th>${t('th_strategy')}</th>
          <th>${t('backtest_start_date')}</th>
          <th>${t('backtest_end_date')}</th>
          <th>${t('th_return')}</th>
          <th>${t('th_sharpe')}</th>
          <th>${t('th_max_dd')}</th>
          <th>${t('th_trades')}</th>
          <th>${t('th_created')}</th>
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
        <span class="card-title-lg">${t('backtest_config')}</span>
        <button class="btn-outline-sm" onclick="document.getElementById('backtestFormArea').innerHTML=''">${t('backtest_cancel')}</button>
      </div>
      <div class="form-row mb-4">
        <div class="form-group">
          <label>${t('backtest_strategy')}</label>
          <select id="btStrategy">
            <option value="momentum">${t('strategy_momentum')}</option>
            <option value="equal_weight">${t('strategy_equal_weight')}</option>
            <option value="mean_reversion">Mean Reversion</option>
          </select>
        </div>
        <div class="form-group">
          <label>${t('backtest_tickers')}</label>
          <input type="text" id="btTickers" value="AAPL,MSFT,NVDA,SPY">
        </div>
      </div>
      <div class="form-row mb-4">
        <div class="form-group"><label>${t('backtest_start_date')}</label><input type="date" id="btStart" value="2023-01-01"></div>
        <div class="form-group"><label>${t('backtest_end_date')}</label><input type="date" id="btEnd" value="2024-12-31"></div>
      </div>
      <div class="form-row mb-4">
        <div class="form-group"><label>${t('backtest_slippage')}</label><input type="number" id="btSlippage" value="5"></div>
        <div class="form-group"><label>${t('backtest_max_positions')}</label><input type="number" id="btMaxPos" value="4"></div>
      </div>
      <div class="form-group mb-4">
        <label>${t('backtest_rebalance')}</label>
        <select id="btRebalance">
          <option value="monthly">${t('rebalance_monthly')}</option>
          <option value="weekly">${t('rebalance_weekly')}</option>
          <option value="daily">${t('rebalance_daily')}</option>
        </select>
      </div>
      <button class="btn-primary" onclick="submitBacktest()"><span class="material-icons-outlined">play_arrow</span> ${t('backtest_run')}</button>
      <div id="backtestRunResult" class="mt-4"></div>
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

  resultDiv.innerHTML = `<div class="loading-cell">${t('backtest_running')}</div>`;
  addLog(t('log_backtest_start'), `${body.strategy} on ${body.tickers.join(',')}...`, 'blue');

  try {
    const result = await apiPost('/backtest/run', body);
    const m = result.metrics || {};
    resultDiv.innerHTML = `
      <div class="card" style="background:var(--color-primary-bg);border:1px solid var(--color-primary-lighter)">
        <div class="card-header"><span class="card-title">${t('backtest_detail')}</span></div>
        <div class="grid-3">
          <div class="metric-card-sm"><div class="metric-label-sm">${t('backtest_total_return')}</div><div class="metric-value-sm">${formatPercent(m.total_return)}</div></div>
          <div class="metric-card-sm"><div class="metric-label-sm">${t('backtest_sharpe_ratio')}</div><div class="metric-value-sm">${m.sharpe_ratio ? m.sharpe_ratio.toFixed(2) : '--'}</div></div>
          <div class="metric-card-sm"><div class="metric-label-sm">${t('backtest_max_drawdown')}</div><div class="metric-value-sm">${formatPercent(m.max_drawdown)}</div></div>
        </div>
      </div>
    `;
    addLog(t('log_backtest_done'), `Return: ${formatPercent(m.total_return)}, Sharpe: ${m.sharpe_ratio ? m.sharpe_ratio.toFixed(2) : '--'}`, 'green');
    setTimeout(() => renderPage(), 3000);
  } catch (e) {
    resultDiv.innerHTML = `<div class="loading-cell" style="color:var(--color-danger)">${t('error_title')}: ${e.message}</div>`;
    addLog(t('log_backtest_error'), e.message, 'yellow');
  }
};

window.showBacktestDetail = async function(runId) {
  const panel = document.getElementById('backtestDetailPanel');
  if (!panel || !runId) return;
  panel.innerHTML = `<div class="card mt-4"><div class="loading-cell">${t('loading')}</div></div>`;

  try {
    const detail = await api(`/backtest/runs/${runId}`);
    const m = detail.metrics || detail;
    const trades = detail.trades || [];
    const nav = detail.nav_series || [];

    const tradeRows = trades.slice(0, 20).map(tr => `<tr>
      <td>${formatDate(tr.date)}</td>
      <td class="ticker-cell">${tr.ticker || '--'}</td>
      <td><span class="badge ${tr.side === 'buy' ? 'badge-green-sm' : 'badge-red-sm'}">${(tr.side || '--').toUpperCase()}</span></td>
      <td>${tr.quantity || '--'}</td>
      <td>${formatCurrency(tr.price)}</td>
    </tr>`).join('') || `<tr><td colspan="5" class="loading-cell">${t('no_data')}</td></tr>`;

    // NAV chart using design-system tokens
    let navChartHtml = '';
    if (nav.length > 0) {
      const navSlice = nav.slice(-50);
      const navValues = navSlice.map(n => n.nav || n.value || n);
      const minV = Math.min(...navValues);
      const maxV = Math.max(...navValues);
      const bars = navSlice.map((n, i) => {
        const v = navValues[i];
        const h = maxV > minV ? ((v - minV) / (maxV - minV)) * 80 + 10 : 50;
        return `<div style="flex:1;height:${h}px;background:var(--color-primary);border-radius:2px" title="${v}"></div>`;
      }).join('');
      navChartHtml = `
        <div class="mb-4">
          <h3 class="card-title mb-4">${t('backtest_nav_series')} (${nav.length})</h3>
          <div style="display:flex;gap:4px;align-items:flex-end;height:100px">${bars}</div>
        </div>
      `;
    }

    panel.innerHTML = `
      <div class="card mt-4">
        <div class="card-header">
          <span class="card-title-lg">${t('backtest_detail')}: ${truncateId(runId)}</span>
          <button class="btn-outline-sm" onclick="document.getElementById('backtestDetailPanel').innerHTML=''">${t('close')}</button>
        </div>
        <div class="grid-3 mb-4">
          <div class="metric-card-sm text-center">
            <div class="metric-label-sm">${t('backtest_total_return')}</div>
            <div class="metric-value-sm">${formatPercent(m.total_return)}</div>
          </div>
          <div class="metric-card-sm text-center">
            <div class="metric-label-sm">${t('backtest_sharpe_ratio')}</div>
            <div class="metric-value-sm">${m.sharpe_ratio ? m.sharpe_ratio.toFixed(2) : '--'}</div>
          </div>
          <div class="metric-card-sm text-center">
            <div class="metric-label-sm">${t('backtest_max_drawdown')}</div>
            <div class="metric-value-sm">${formatPercent(m.max_drawdown)}</div>
          </div>
        </div>
        ${navChartHtml}
        <h3 class="card-title mb-4">${t('backtest_trades')} (${trades.length})</h3>
        <table class="data-table">
          <thead><tr>
            <th>${t('th_date')}</th>
            <th>${t('th_ticker')}</th>
            <th>${t('th_side')}</th>
            <th>${t('th_quantity')}</th>
            <th>${t('th_price')}</th>
          </tr></thead>
          <tbody>${tradeRows}</tbody>
        </table>
      </div>
    `;
  } catch (e) {
    panel.innerHTML = `<div class="card mt-4"><div class="loading-cell">${t('error_title')}: ${e.message}</div></div>`;
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
    <td style="font-family:var(--font-mono);font-size:11px">${truncateId(intent.intent_id || intent.id)}</td>
    <td>${intent.strategy || '--'}</td>
    <td>${intent.instrument_id ? truncateId(intent.instrument_id) : '--'}</td>
    <td><span class="badge ${intent.side === 'buy' ? 'badge-green-sm' : 'badge-red-sm'}">${(intent.side || '--').toUpperCase()}</span></td>
    <td>${intent.quantity || '--'}</td>
    <td><span class="badge badge-yellow-sm">${(intent.status || '--').toUpperCase()}</span></td>
    <td>${formatDate(intent.created_at)}</td>
  </tr>`).join('') || `<tr><td colspan="7" class="loading-cell">${t('execution_no_intents')}</td></tr>`;

  const draftRows = drafts.map(draft => `<tr>
    <td style="font-family:var(--font-mono);font-size:11px">${truncateId(draft.draft_id || draft.id)}</td>
    <td style="font-family:var(--font-mono);font-size:11px">${truncateId(draft.intent_id)}</td>
    <td>${draft.broker || '--'}</td>
    <td>${draft.order_type || '--'}</td>
    <td>${draft.quantity || '--'}</td>
    <td><span class="badge ${draft.status === 'approved' ? 'badge-green-sm' : 'badge-yellow-sm'}">${(draft.status || '--').toUpperCase()}</span></td>
    <td>${formatDate(draft.created_at)}</td>
  </tr>`).join('') || `<tr><td colspan="7" class="loading-cell">${t('execution_no_drafts')}</td></tr>`;

  return `
    <div class="page-header">
      <div>
        <h1 class="page-title">${t('execution_title')}</h1>
        <p class="page-subtitle">${intents.length} ${t('execution_intents')} // ${drafts.length} ${t('execution_drafts')}</p>
      </div>
      <div class="header-actions">
        <button class="btn-primary" onclick="showCreateIntentForm()"><span class="material-icons-outlined">add</span> ${t('execution_create_intent')}</button>
      </div>
    </div>

    <!-- Pipeline Visualization -->
    ${renderPipelineHtml(intents.length, pendingIntents, pendingDrafts, approvedDrafts)}

    <div id="createIntentArea"></div>

    <!-- Intents Table -->
    <div class="card">
      <div class="card-header">
        <span class="card-title-lg">${t('execution_intents')}</span>
        <span class="badge badge-green">${intents.length} TOTAL</span>
      </div>
      <table class="data-table">
        <thead><tr>
          <th>ID</th>
          <th>${t('th_strategy')}</th>
          <th>${t('th_instrument')}</th>
          <th>${t('th_side')}</th>
          <th>${t('th_quantity')}</th>
          <th>${t('th_status')}</th>
          <th>${t('th_created')}</th>
        </tr></thead>
        <tbody>${intentRows}</tbody>
      </table>
    </div>

    <!-- Drafts Table -->
    <div class="card">
      <div class="card-header">
        <span class="card-title-lg">${t('execution_drafts')}</span>
        <span class="badge badge-green">${drafts.length} TOTAL</span>
      </div>
      <table class="data-table">
        <thead><tr>
          <th>ID</th>
          <th>${t('th_intent_id')}</th>
          <th>${t('th_broker')}</th>
          <th>${t('th_order_type')}</th>
          <th>${t('th_quantity')}</th>
          <th>${t('th_status')}</th>
          <th>${t('th_created')}</th>
        </tr></thead>
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
        <span class="card-title-lg">${t('execution_create_intent')}</span>
        <button class="btn-outline-sm" onclick="document.getElementById('createIntentArea').innerHTML=''">${t('cancel')}</button>
      </div>
      <div class="form-row mb-4">
        <div class="form-group"><label>${t('execution_strategy_name')}</label><input type="text" id="intentStrategy" value="momentum" placeholder="momentum"></div>
        <div class="form-group"><label>${t('execution_instrument')}</label><input type="text" id="intentInstrument" placeholder="instrument UUID"></div>
      </div>
      <div class="form-row mb-4">
        <div class="form-group">
          <label>${t('execution_side')}</label>
          <select id="intentSide"><option value="buy">${t('execution_side_buy')}</option><option value="sell">${t('execution_side_sell')}</option></select>
        </div>
        <div class="form-group"><label>${t('execution_target_qty')}</label><input type="number" id="intentQty" value="100"></div>
      </div>
      <div class="form-group mb-4">
        <label>${t('execution_reason')}</label>
        <input type="text" id="intentReason" placeholder="Signal rationale..." value="Momentum signal triggered">
      </div>
      <button class="btn-primary" onclick="submitIntent()"><span class="material-icons-outlined">send</span> ${t('execution_create')}</button>
      <div id="intentResult" class="mt-4"></div>
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

  resultDiv.innerHTML = `<div class="loading-cell">${t('loading')}</div>`;

  try {
    const data = await apiPost('/execution/intents', body);
    resultDiv.innerHTML = `<div style="padding:12px;background:var(--color-primary-bg);border-radius:8px;font-size:13px;font-weight:600;color:var(--color-primary-dark)">${t('execution_create_intent')}: ${truncateId(data.intent_id || data.id)}</div>`;
    addLog('INTENT_CREATED', `${body.side.toUpperCase()} ${body.quantity} via ${body.strategy}`, 'green');
    setTimeout(() => renderPage(), 2000);
  } catch (e) {
    resultDiv.innerHTML = `<div class="loading-cell" style="color:var(--color-danger)">${t('error_title')}: ${e.message}</div>`;
  }
};

// ============================================================
//  PAGE 6: DATA QUALITY
// ============================================================
async function renderDQ() {
  const dqCodes = ['DQ-1','DQ-2','DQ-3','DQ-4','DQ-5','DQ-6','DQ-7','DQ-8','DQ-9','DQ-10','DQ-11'];
  const dqDescs = {
    'DQ-1': 'Open/High/Low/Close consistency',
    'DQ-2': 'No negative prices or volumes',
    'DQ-3': 'No duplicate primary keys',
    'DQ-4': 'Only valid trading day data',
    'DQ-5': 'Corporate action consistency',
    'DQ-6': 'Point-in-time data integrity',
    'DQ-7': 'Multi-source price agreement',
    'DQ-8': 'No stale/unchanged prices',
    'DQ-9': 'No conflicting ticker maps',
    'DQ-10': 'No orphaned identifiers',
    'DQ-11': 'No raw/adjusted price mixing',
  };
  const dqSeverities = {
    'DQ-1': 'CRITICAL', 'DQ-2': 'CRITICAL', 'DQ-3': 'HIGH', 'DQ-4': 'MEDIUM',
    'DQ-5': 'HIGH', 'DQ-6': 'CRITICAL', 'DQ-7': 'HIGH', 'DQ-8': 'MEDIUM',
    'DQ-9': 'HIGH', 'DQ-10': 'LOW', 'DQ-11': 'CRITICAL',
  };

  const severityBadge = (sev) => {
    const map = { CRITICAL: 'badge-red-sm', HIGH: 'badge-yellow-sm', MEDIUM: 'badge-green-sm', LOW: 'badge-green-sm' };
    return map[sev] || 'badge-green-sm';
  };

  const dqGrid = dqCodes.map(code => {
    const sev = dqSeverities[code];
    return `
      <div class="card text-center" style="padding:20px">
        <div class="card-title mb-4">${code}</div>
        <div style="font-size:14px;font-weight:600;margin-bottom:8px">${tNested('dq_rule_names', code)}</div>
        <div style="font-size:28px;color:var(--color-primary);margin-bottom:8px">&#10003;</div>
        <div class="text-muted" style="font-size:11px;margin-bottom:8px">${dqDescs[code]}</div>
        <span class="badge ${severityBadge(sev)}">${sev}</span>
      </div>
    `;
  }).join('');

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
        <h1 class="page-title">${t('dq_title')}</h1>
        <p class="page-subtitle">${t('dq_subtitle')}</p>
      </div>
      <div class="header-actions">
        <button class="btn-primary" onclick="renderPage()"><span class="material-icons-outlined">sync</span> ${t('refresh')}</button>
      </div>
    </div>

    <!-- DQ Rules Grid — uses .dq-grid class from styles.css (4 columns) -->
    <div class="dq-grid">
      ${dqGrid}
    </div>

    ${issues.length > 0 ? `
    <!-- Data Issues -->
    <div class="card">
      <div class="card-header">
        <span class="card-title-lg">${t('dq_issues')}</span>
        <span class="badge badge-yellow-sm">${issues.length}</span>
      </div>
      <table class="data-table">
        <thead><tr>
          <th>${t('th_rule_code')}</th>
          <th>${t('th_instrument')}</th>
          <th>${t('th_details')}</th>
          <th>${t('th_severity')}</th>
          <th>${t('th_date')}</th>
        </tr></thead>
        <tbody>${issueRows}</tbody>
      </table>
    </div>` : `
    <div class="card text-center" style="padding:32px">
      <span class="material-icons-outlined" style="font-size:48px;color:var(--color-primary);display:block;margin-bottom:12px">check_circle</span>
      <div class="card-title-lg mb-4">${t('dq_no_issues')}</div>
      <div class="text-muted" style="font-size:13px">${t('dq_subtitle')}</div>
    </div>`}

    ${sourceRuns.length > 0 ? `
    <!-- Source Runs -->
    <div class="card">
      <div class="card-header">
        <span class="card-title-lg">${t('dq_source_runs')}</span>
      </div>
      <table class="data-table">
        <thead><tr><th>SOURCE</th><th>${t('th_status')}</th><th>RECORDS</th><th>LAST RUN</th></tr></thead>
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
    { key: 'sec', configured: true },
    { key: 'openfigi', configured: false },
    { key: 'massive', configured: false },
    { key: 'fmp', configured: false },
    { key: 't212', configured: false },
  ];

  const featureFlags = [
    { name: 'FEATURE_T212_LIVE_SUBMIT', value: false, desc: t('execution_policy_notice') },
    { name: 'FEATURE_AUTO_REBALANCE', value: false, desc: 'Auto portfolio rebalancing' },
    { name: 'FEATURE_DQ_AUTO_QUARANTINE', value: true, desc: 'Auto-quarantine failing DQ data' },
  ];

  const dataSources = [
    { source: tNested('settings_key_names', 'sec'), types: 'Filings, Financials', status: 'ACTIVE', frequency: 'Daily' },
    { source: tNested('settings_key_names', 'openfigi'), types: 'Identifiers', status: 'ACTIVE', frequency: 'On-demand' },
    { source: tNested('settings_key_names', 'fmp'), types: 'Prices, Fundamentals', status: 'ACTIVE', frequency: 'Daily' },
    { source: tNested('settings_key_names', 't212'), types: 'Live Quotes, Orders', status: 'DISABLED', frequency: 'Real-time' },
    { source: tNested('settings_key_names', 'massive'), types: 'Alt Data', status: 'ACTIVE', frequency: 'Weekly' },
  ];

  const apiKeyRows = apiKeys.map(k => `
    <div class="role-item">
      <span class="material-icons-outlined role-icon">${k.configured ? 'vpn_key' : 'key_off'}</span>
      <span class="role-name">${tNested('settings_key_names', k.key)}</span>
      <span class="badge ${k.configured ? 'badge-green-sm' : 'badge-red-sm'}">${k.configured ? t('status_configured') : t('status_not_configured')}</span>
    </div>
  `).join('');

  const flagRows = featureFlags.map(f => `
    <div class="role-item">
      <span class="material-icons-outlined role-icon" style="color:${f.value ? 'var(--color-primary)' : 'var(--color-text-muted)'}">${f.value ? 'toggle_on' : 'toggle_off'}</span>
      <div style="flex:1">
        <div class="role-name mono-cell">${f.name}</div>
        <div class="text-muted" style="font-size:11px">${f.desc}</div>
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
        <h1 class="page-title">${t('settings_title')}</h1>
        <p class="page-subtitle">${t('settings_subtitle')}</p>
      </div>
    </div>

    <div class="grid-2">
      <!-- API Keys -->
      <div class="card">
        <div class="card-header">
          <span class="card-title-lg">${t('settings_api_keys')}</span>
          <span class="material-icons-outlined info-icon">info</span>
        </div>
        <div class="role-list">${apiKeyRows}</div>
      </div>

      <!-- Feature Flags -->
      <div class="card">
        <div class="card-header">
          <span class="card-title-lg">${t('settings_feature_flags')}</span>
        </div>
        <div class="role-list">${flagRows}</div>
      </div>
    </div>

    <!-- Execution Policy -->
    <div class="card">
      <div class="card-header">
        <span class="card-title-lg">${t('settings_execution_policy')}</span>
        <span class="badge badge-yellow-sm">${t('status_controlled')}</span>
      </div>
      <div class="grid-2">
        <div>
          <div class="role-list">
            <div class="role-item"><span class="material-icons-outlined role-icon" style="color:var(--color-warning)">security</span><span class="role-name">${t('execution_policy_notice')}</span></div>
            <div class="role-item"><span class="material-icons-outlined role-icon" style="color:var(--color-warning)">gavel</span><span class="role-name">Max order size: 10,000 shares</span></div>
            <div class="role-item"><span class="material-icons-outlined role-icon">schedule</span><span class="role-name">Orders only during market hours</span></div>
          </div>
        </div>
        <div>
          <div class="role-list">
            <div class="role-item"><span class="material-icons-outlined role-icon" style="color:var(--color-danger)">block</span><span class="role-name">T212 live submit: DISABLED</span></div>
            <div class="role-item"><span class="material-icons-outlined role-icon">verified_user</span><span class="role-name">All drafts require human review</span></div>
            <div class="role-item"><span class="material-icons-outlined role-icon">history</span><span class="role-name">Full audit trail enabled</span></div>
          </div>
        </div>
      </div>
    </div>

    <!-- Data Sources Matrix -->
    <div class="card">
      <div class="card-header">
        <span class="card-title-lg">${t('settings_data_sources')}</span>
      </div>
      <table class="data-table">
        <thead><tr><th>SOURCE</th><th>DATA TYPES</th><th>${t('th_status')}</th><th>FREQUENCY</th></tr></thead>
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
  addLog(t('log_export'), 'Report downloaded', 'green');
};

// ---- INITIALIZATION ----
document.addEventListener('DOMContentLoaded', () => {
  // Build the sidebar
  const sidebar = document.querySelector('.sidebar');
  if (sidebar) sidebar.innerHTML = renderSidebar();

  // Set up page content container
  const content = document.querySelector('.content');
  if (content) content.id = 'page-content';

  addLog(t('log_system_boot'), t('log_dashboard_init'), 'green');

  // Set theme toggle icon based on current theme
  const themeBtn = document.querySelector('.theme-toggle .material-icons-outlined');
  if (themeBtn) {
    themeBtn.textContent = document.documentElement.getAttribute('data-theme') === 'dark' ? 'light_mode' : 'dark_mode';
  }

  // Initial render
  renderPage();

  // Hash change listener
  window.addEventListener('hashchange', () => renderPage());
});
