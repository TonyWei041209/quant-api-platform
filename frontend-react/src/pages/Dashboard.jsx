import { useState, useEffect, useCallback, useRef } from 'react';
import { apiFetch, apiPost } from '../hooks/useApi';
import { useI18n } from '../hooks/useI18n';
import { useWorkspace } from '../hooks/useWorkspace';
import { usePageVisibility } from '../App';
import { formatPercent, formatNumber, formatDate, truncateId } from '../utils';
import {
  TrendingUp, Info, Database, FlaskConical, History, ArrowLeftRight,
  ShieldCheck, ExternalLink, Download, RefreshCw, Zap, Lock,
  Lightbulb, FileText, FilePen, CheckCircle, Send, ChevronRight,
  Calendar, AlertCircle, Clock, Star, Plus, BookOpen, BarChart3,
  Activity, Eye, Target, Bookmark, StickyNote, X, Wallet, PieChart,
  Briefcase, DollarSign,
} from 'lucide-react';

const CARD = 'bg-card rounded-xl border border-border shadow-card card-hover p-6';
const BADGE_BASE = 'inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wider';
const BADGE_GREEN = 'bg-brand-light text-brand-dark';
const BADGE_YELLOW = 'bg-amber-50 text-amber-600';
const BADGE_RED = 'bg-red-50 text-red-500';
const BADGE_BLUE = 'bg-blue-50 text-blue-600';

function EmptyState({ icon: Icon, title, description, action, onAction }) {
  return (
    <div className="flex flex-col items-center justify-center py-8 text-center">
      <div className="w-12 h-12 rounded-xl bg-surface flex items-center justify-center mb-3">
        <Icon className="w-5 h-5 text-muted" />
      </div>
      <p className="text-sm font-medium text-heading mb-1">{title}</p>
      <p className="text-xs text-muted max-w-[240px]">{description}</p>
      {action && (
        <button onClick={onAction} className="mt-3 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-brand text-white text-xs font-semibold hover:bg-brand-dark transition-colors">
          <Plus className="w-3 h-3" /> {action}
        </button>
      )}
    </div>
  );
}

function ActivityIcon({ type }) {
  const map = {
    ingestion: { icon: Database, color: 'text-blue-500' },
    backtest: { icon: History, color: 'text-brand' },
    note: { icon: StickyNote, color: 'text-purple-500' },
    research: { icon: FlaskConical, color: 'text-amber-500' },
    execution: { icon: ArrowLeftRight, color: 'text-red-500' },
  };
  const { icon: Icon, color } = map[type] || { icon: Activity, color: 'text-muted' };
  return <Icon className={`w-4 h-4 ${color} shrink-0`} />;
}

function timeAgo(ts) {
  if (!ts) return '';
  const diff = Date.now() - new Date(ts).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

function ContinueSection({ onNavigate }) {
  const { t } = useI18n();
  const [presets, setPresets] = useState([]);
  const [notes, setNotes] = useState([]);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    Promise.allSettled([
      apiFetch('/presets?limit=6'),
      apiFetch('/notes?limit=4'),
    ]).then(([pRes, nRes]) => {
      if (pRes.status === 'fulfilled') setPresets(pRes.value?.items || []);
      if (nRes.status === 'fulfilled') setNotes(nRes.value?.items || []);
      setLoaded(true);
    });
  }, []);

  if (!loaded) return <div className="text-sm text-muted py-4 text-center">{t('loading')}</div>;
  if (presets.length === 0 && notes.length === 0) {
    return (
      <div className="flex flex-col items-center py-6 text-center">
        <BookOpen className="w-8 h-8 text-muted/40 mb-2" />
        <p className="text-sm text-muted">{t('dash_no_presets_notes')}</p>
        <p className="text-xs text-muted mt-1">{t('dash_presets_notes_hint')}</p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 md:gap-6">
      {/* Recent Presets */}
      <div>
        <h4 className="text-xs font-semibold text-muted uppercase tracking-wider mb-3">{t('dash_saved_presets')}</h4>
        {presets.length > 0 ? (
          <div className="space-y-2">
            {presets.slice(0, 4).map(p => (
              <div key={p.preset_id} onClick={() => onNavigate?.(p.preset_type === 'backtest' ? 'backtest' : 'research')}
                className="flex items-center justify-between py-2 px-3 rounded-lg hover:bg-surface/60 border border-border/30 cursor-pointer transition-colors">
                <div className="flex items-center gap-2 min-w-0">
                  <Bookmark className="w-3.5 h-3.5 text-brand shrink-0" />
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-heading truncate">{p.name}</p>
                    <p className="text-[10px] text-muted">{p.preset_type} · used {p.use_count || 0}x</p>
                  </div>
                </div>
                <ChevronRight className="w-3.5 h-3.5 text-muted shrink-0" />
              </div>
            ))}
          </div>
        ) : (
          <p className="text-xs text-muted py-2">{t('dash_no_presets')}</p>
        )}
      </div>
      {/* Recent Notes */}
      <div>
        <h4 className="text-xs font-semibold text-muted uppercase tracking-wider mb-3">{t('dash_recent_notes')}</h4>
        {notes.length > 0 ? (
          <div className="space-y-2">
            {notes.slice(0, 4).map(n => (
              <div key={n.note_id} onClick={() => onNavigate?.('research')}
                className="flex items-center justify-between py-2 px-3 rounded-lg hover:bg-surface/60 border border-border/30 cursor-pointer transition-colors">
                <div className="min-w-0">
                  <p className="text-sm font-medium text-heading truncate">{n.title}</p>
                  <p className="text-[10px] text-muted">{n.note_type} · {formatDate(n.created_at)}</p>
                </div>
                <ChevronRight className="w-3.5 h-3.5 text-muted shrink-0" />
              </div>
            ))}
          </div>
        ) : (
          <p className="text-xs text-muted py-2">{t('dash_no_notes')}</p>
        )}
      </div>
    </div>
  );
}

export default function Dashboard({ onNavigate }) {
  const { t } = useI18n();
  const { portfolioSummary, isHeld } = useWorkspace();
  const [brief, setBrief] = useState(null);
  const [activity, setActivity] = useState([]);
  const [watchlists, setWatchlists] = useState([]);
  const [health, setHealth] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [lastRefresh, setLastRefresh] = useState(null);
  const [showNewWatchlist, setShowNewWatchlist] = useState(false);
  const [newWatchlistName, setNewWatchlistName] = useState('');
  const [researchStatus, setResearchStatus] = useState({});
  const [positionsExpanded, setPositionsExpanded] = useState(false);

  const loadData = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true); else setLoading(true);
    const [bRes, aRes, wRes, hRes, rsRes] = await Promise.allSettled([
      apiFetch('/daily/brief'),
      apiFetch('/daily/recent-activity?limit=8'),
      apiFetch('/watchlist/groups'),
      apiFetch('/health'),
      apiFetch('/portfolio/research-status'),
    ]);
    if (bRes.status === 'fulfilled') setBrief(bRes.value);
    if (aRes.status === 'fulfilled') setActivity(aRes.value?.items || []);
    if (wRes.status === 'fulfilled') setWatchlists(wRes.value?.groups || []);
    if (hRes.status === 'fulfilled') setHealth(hRes.value);
    if (rsRes.status === 'fulfilled' && rsRes.value && typeof rsRes.value === 'object') setResearchStatus(rsRes.value);
    setLoading(false);
    setRefreshing(false);
    setLastRefresh(new Date());
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  // Auto-refresh when page becomes visible again (after navigating away and back)
  const { isVisible, refreshSignal } = usePageVisibility();
  const prevVisibleRef = useRef(isVisible);
  useEffect(() => {
    // Refresh when returning to this page (was hidden, now visible)
    if (isVisible && !prevVisibleRef.current) {
      loadData(true);
    }
    prevVisibleRef.current = isVisible;
  }, [isVisible, loadData]);

  // Respond to header refresh button
  const prevRefreshRef = useRef(refreshSignal);
  useEffect(() => {
    if (refreshSignal !== prevRefreshRef.current && isVisible) {
      loadData(true);
      prevRefreshRef.current = refreshSignal;
    }
  }, [refreshSignal, isVisible, loadData]);

  const createWatchlist = async (name) => {
    if (!name?.trim()) return;
    await apiPost('/watchlist/groups', { name: name.trim(), is_default: false });
    setShowNewWatchlist(false);
    setNewWatchlistName('');
    const res = await apiFetch('/watchlist/groups');
    setWatchlists(res?.groups || []);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[60vh] animate-pulse opacity-80">
        <RefreshCw className="w-8 h-8 text-brand animate-spin" />
      </div>
    );
  }

  const ds = brief?.data_status || {};
  const dq = brief?.dq_status || {};
  const earnings = brief?.upcoming_earnings || [];
  const recentBt = brief?.recent_backtests || [];
  const execStatus = brief?.execution_status || {};
  const latency = health?.latency_ms ?? 12;
  const version = health?.version ?? '1.0.0';

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-heading">{t('dash_title')}</h1>
            <span className="text-brand font-semibold text-sm">{t('dash_live')}</span>
          </div>
          <p className="text-[11px] font-mono text-muted tracking-wider mt-1">
            {t('dash_status_prefix')} {t('dash_operational')} // {t('dash_latency')} {latency}MS // v{version}
          </p>
        </div>
        <div className="flex items-center gap-3">
          {lastRefresh && (
            <span className="text-[10px] text-muted font-mono">
              {t('dash_updated')} {lastRefresh.toLocaleTimeString()}
            </span>
          )}
          <button onClick={() => loadData(true)} disabled={refreshing} className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-brand text-white text-sm font-medium hover:bg-brand-dark transition-colors disabled:opacity-60">
            <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} /> {refreshing ? t('dash_refreshing') : t('refresh')}
          </button>
        </div>
      </div>

      {/* Row 1: Data Status | Today's Events | Platform Status */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 md:gap-6">
        {/* Data Status Hero */}
        <div className={CARD + ' relative overflow-hidden'}>
          <div className="flex items-start justify-between mb-4">
            <span className={`${BADGE_BASE} ${ds.data_freshness === 'current' ? BADGE_GREEN : BADGE_YELLOW}`}>
              {ds.data_freshness === 'current' ? t('dash_data_current') : t('dash_data_stale')}
            </span>
            <Database className="w-5 h-5 text-brand" />
          </div>
          <div className="tabular-nums text-heading" style={{ fontSize: 56, fontWeight: 800, letterSpacing: -2, lineHeight: 1 }}>
            {formatNumber(ds.total_instruments || 0)}
          </div>
          <p className="text-sm text-muted mt-2">{t('dash_active_in_universe')}</p>
          <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <p className="text-[10px] text-muted uppercase tracking-wider">{t('dash_price_bars')}</p>
              <p className="text-lg font-bold text-heading tabular-nums">{formatNumber(ds.total_price_bars || 0)}</p>
            </div>
            <div>
              <p className="text-[10px] text-muted uppercase tracking-wider">{t('dash_latest_date')}</p>
              <p className="text-sm font-semibold text-heading">{ds.latest_bar_date || '--'}</p>
            </div>
          </div>
        </div>

        {/* Today's Events */}
        <div className={CARD + ' flex flex-col'}>
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-xs font-semibold text-muted uppercase tracking-wider">{t('dash_upcoming_events')}</h3>
            <Calendar className="w-4 h-4 text-muted" />
          </div>
          {earnings.length > 0 ? (
            <div className="space-y-3 flex-1">
              {earnings.slice(0, 4).map((e, i) => (
                <div key={i} className="flex items-center justify-between py-1">
                  <div className="min-w-0">
                    <p className="text-sm font-semibold text-heading truncate">{e.issuer_name}</p>
                    <p className="text-xs text-muted">{e.report_date} · {e.event_time_code || 'TBD'}</p>
                  </div>
                  {e.eps_actual != null && (
                    <span className={`${BADGE_BASE} ${e.eps_actual >= (e.eps_estimate || 0) ? BADGE_GREEN : BADGE_RED}`}>
                      ${formatNumber(e.eps_actual)}
                    </span>
                  )}
                </div>
              ))}
              {earnings.length > 4 && (
                <p className="text-xs text-brand font-semibold cursor-pointer hover:underline">
                  +{earnings.length - 4} more events
                </p>
              )}
            </div>
          ) : (
            <EmptyState icon={Calendar} title={t('dash_no_earnings')} description={t('dash_no_earnings_desc')} />
          )}
        </div>

        {/* Platform Status */}
        <div className={CARD + ' flex flex-col'}>
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-xs font-semibold text-muted uppercase tracking-wider">{t('dash_platform_status')}</h3>
            <ShieldCheck className="w-4 h-4 text-brand" />
          </div>
          <div className="space-y-3 flex-1">
            <div className="flex items-center justify-between">
              <span className="text-sm text-secondary">{t('dash_dq_status')}</span>
              <span className={`${BADGE_BASE} ${dq.status === 'clean' ? BADGE_GREEN : BADGE_YELLOW}`}>
                {dq.unresolved_issues || 0} {t('common_issues')}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-secondary">{t('dash_pending_intents')}</span>
              <span className="text-sm font-bold text-heading tabular-nums">{execStatus.pending_intents || 0}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-secondary">{t('dash_pending_drafts')}</span>
              <span className="text-sm font-bold text-heading tabular-nums">{execStatus.pending_drafts || 0}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-secondary">{t('dash_live_submit')}</span>
              <span className={`${BADGE_BASE} ${BADGE_RED}`}>{t('ex_locked')}</span>
            </div>
          </div>
          <div className="mt-4 pt-3 border-t border-border">
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-brand animate-pulse" />
              <span className="text-xs text-muted">{t('dash_system_operational')} · {latency}ms</span>
            </div>
          </div>
        </div>
      </div>

      {/* Row 1.5: Portfolio Snapshot */}
      {portfolioSummary && (
        <div className={portfolioSummary.connected ? 'grid grid-cols-1 sm:grid-cols-3 gap-4' : 'grid grid-cols-1 gap-4'}>
          {portfolioSummary.connected ? (
            <>
              {/* Account Summary */}
              <div className={CARD}>
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <Wallet className="w-4 h-4 text-brand" />
                    <span className="text-sm font-semibold text-heading">{t('dash_portfolio')}</span>
                  </div>
                  <span className={`${BADGE_BASE} ${BADGE_GREEN}`}>{t('dash_connected')}</span>
                </div>
                <div className="text-2xl font-extrabold text-heading tabular-nums mb-1">
                  {portfolioSummary.account?.currency || '$'}{formatNumber(portfolioSummary.account?.portfolio_value || 0)}
                </div>
                <div className="flex items-center gap-4 text-xs text-muted">
                  <span>Cash: {portfolioSummary.account?.currency || '$'}{formatNumber(portfolioSummary.account?.cash_free || 0)}</span>
                  <span>·</span>
                  <span>{portfolioSummary.position_count} position{portfolioSummary.position_count !== 1 ? 's' : ''}</span>
                </div>
                {portfolioSummary.as_of && (
                  <p className="text-[10px] text-muted mt-2">{t('dash_broker_snapshot')}: {formatDate(portfolioSummary.as_of)}</p>
                )}
              </div>

              {/* Top Positions */}
              <div className={CARD}>
                <div className="flex items-center gap-2 mb-3">
                  <Briefcase className="w-4 h-4 text-brand" />
                  <span className="text-sm font-semibold text-heading">{t('dash_holdings')}</span>
                </div>
                {portfolioSummary.positions.length > 0 ? (
                  <div className="space-y-2">
                    {portfolioSummary.positions.slice(0, 4).map((pos, i) => (
                      <div key={i} className="flex items-center justify-between text-xs">
                        <span className="font-semibold text-heading">{pos.broker_ticker}</span>
                        <div className="flex items-center gap-3">
                          <span className="text-muted tabular-nums">{pos.quantity} {t('dash_shares')}</span>
                          <span className={`font-semibold tabular-nums ${pos.pnl >= 0 ? 'text-brand-dark' : 'text-red-500'}`}>
                            {pos.pnl >= 0 ? '+' : ''}{formatNumber(pos.pnl)}
                          </span>
                        </div>
                      </div>
                    ))}
                    {portfolioSummary.positions.length > 4 && (
                      <p className="text-[10px] text-muted">+{portfolioSummary.positions.length - 4} more</p>
                    )}
                  </div>
                ) : (
                  <p className="text-xs text-muted py-2">No open positions</p>
                )}
              </div>

              {/* P&L Summary */}
              <div className={CARD}>
                <div className="flex items-center gap-2 mb-3">
                  <DollarSign className="w-4 h-4 text-brand" />
                  <span className="text-sm font-semibold text-heading">{t('dash_unrealized_pnl')}</span>
                </div>
                <div className={`text-2xl font-extrabold tabular-nums mb-1 ${portfolioSummary.total_pnl >= 0 ? 'text-brand-dark' : 'text-red-500'}`}>
                  {portfolioSummary.total_pnl >= 0 ? '+' : ''}{formatNumber(portfolioSummary.total_pnl)}
                </div>
                <p className="text-xs text-muted">
                  Across {portfolioSummary.position_count} position{portfolioSummary.position_count !== 1 ? 's' : ''}
                </p>
                {portfolioSummary.recent_orders.length > 0 && (
                  <div className="mt-3 pt-3 border-t border-border">
                    <p className="text-[10px] font-semibold text-muted uppercase tracking-wider mb-1">{t('dash_last_order')}</p>
                    <p className="text-xs text-heading">
                      <span className={`font-semibold ${portfolioSummary.recent_orders[0].side === 'buy' ? 'text-brand-dark' : 'text-red-500'}`}>
                        {portfolioSummary.recent_orders[0].side?.toUpperCase()}
                      </span>
                      {' '}{portfolioSummary.recent_orders[0].broker_ticker} · {portfolioSummary.recent_orders[0].qty} {t('dash_shares')}
                    </p>
                  </div>
                )}
              </div>
            </>
          ) : (
            <div className={CARD + ' flex items-center gap-4'}>
              <div className="w-10 h-10 rounded-lg bg-surface flex items-center justify-center">
                <Wallet className="w-5 h-5 text-muted" />
              </div>
              <div>
                <p className="text-sm font-semibold text-heading">{t('dash_portfolio_not_connected')}</p>
                <p className="text-xs text-muted">{t('dash_portfolio_config')}</p>
              </div>
              <button onClick={() => onNavigate?.('settings')} className="ml-auto text-xs font-semibold text-brand hover:text-brand-dark">
                Open Settings →
              </button>
            </div>
          )}
        </div>
      )}

      {/* Row 1.6: Portfolio Positions Detail Table */}
      {portfolioSummary?.connected && portfolioSummary.positions.length > 0 && (
        <div className={CARD + ' overflow-hidden !p-0'}>
          <div className="flex items-center justify-between px-5 py-4">
            <div className="flex items-center gap-2">
              <PieChart className="w-4 h-4 text-brand" />
              <h3 className="text-sm font-semibold text-heading">{t('dash_portfolio_detail')}</h3>
              <span className="text-[10px] text-muted">{portfolioSummary.positions.length} positions</span>
            </div>
            {portfolioSummary.positions.length > 5 && (
              <button onClick={() => setPositionsExpanded(!positionsExpanded)} className="text-xs font-medium text-brand hover:text-brand-dark cursor-pointer">
                {positionsExpanded ? t('dash_show_less') : t('dash_show_all')}
              </button>
            )}
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-t border-border">
                  <th className="text-[10px] font-bold uppercase tracking-wider text-muted bg-hover-row px-4 py-2.5 text-left">{t('dash_col_ticker')}</th>
                  <th className="text-[10px] font-bold uppercase tracking-wider text-muted bg-hover-row px-4 py-2.5 text-right">{t('dash_col_qty')}</th>
                  <th className="text-[10px] font-bold uppercase tracking-wider text-muted bg-hover-row px-4 py-2.5 text-right">{t('dash_col_avg_cost')}</th>
                  <th className="text-[10px] font-bold uppercase tracking-wider text-muted bg-hover-row px-4 py-2.5 text-right">{t('dash_col_current')}</th>
                  <th className="text-[10px] font-bold uppercase tracking-wider text-muted bg-hover-row px-4 py-2.5 text-right">{t('dash_col_mkt_value')}</th>
                  <th className="text-[10px] font-bold uppercase tracking-wider text-muted bg-hover-row px-4 py-2.5 text-right">{t('dash_col_pnl')}</th>
                  <th className="text-[10px] font-bold uppercase tracking-wider text-muted bg-hover-row px-4 py-2.5 text-right">{t('dash_col_pnl_pct')}</th>
                  <th className="text-[10px] font-bold uppercase tracking-wider text-muted bg-hover-row px-4 py-2.5 text-left">{t('dash_col_research')}</th>
                </tr>
              </thead>
              <tbody>
                {(positionsExpanded ? portfolioSummary.positions : portfolioSummary.positions.slice(0, 5)).map((pos, i) => {
                  const pnlPct = pos.pnl_percent ?? (pos.avg_cost > 0 ? ((pos.current_price - pos.avg_cost) / pos.avg_cost) * 100 : 0);
                  const rs = researchStatus[pos.instrument_id] || null;
                  const totalValue = portfolioSummary.total_market_value || 1;
                  const weight = ((pos.market_value || 0) / totalValue * 100);
                  return (
                    <tr key={pos.instrument_id || i}
                      onClick={() => onNavigate?.('research')}
                      className="hover:bg-hover-row cursor-pointer transition-colors border-b border-border/50 last:border-0"
                    >
                      <td className="px-4 py-2.5">
                        <div className="font-semibold text-heading">{pos.broker_ticker || truncateId(pos.instrument_id)}</div>
                        <div className="text-[10px] text-muted">{weight.toFixed(1)}% {t('dash_col_weight')}</div>
                      </td>
                      <td className="px-4 py-2.5 text-right tabular-nums text-secondary">{formatNumber(pos.quantity, 2)}</td>
                      <td className="px-4 py-2.5 text-right tabular-nums text-secondary font-mono text-xs">{formatNumber(pos.avg_cost, 2)}</td>
                      <td className="px-4 py-2.5 text-right tabular-nums text-secondary font-mono text-xs">{formatNumber(pos.current_price, 2)}</td>
                      <td className="px-4 py-2.5 text-right tabular-nums text-heading font-semibold">{formatNumber(pos.market_value, 0)}</td>
                      <td className={`px-4 py-2.5 text-right tabular-nums font-semibold ${pos.pnl >= 0 ? 'text-brand-dark' : 'text-red-500'}`}>
                        {pos.pnl >= 0 ? '+' : ''}{formatNumber(pos.pnl, 2)}
                      </td>
                      <td className={`px-4 py-2.5 text-right tabular-nums font-semibold text-xs ${pnlPct >= 0 ? 'text-brand-dark' : 'text-red-500'}`}>
                        {pnlPct >= 0 ? '+' : ''}{pnlPct.toFixed(1)}%
                      </td>
                      <td className="px-4 py-2.5">
                        {rs ? (
                          <div className="flex flex-wrap gap-1">
                            {rs.has_thesis && <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400">{t('dash_has_thesis')}</span>}
                            {rs.has_risk && <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-amber-50 dark:bg-amber-900/20 text-amber-600 dark:text-amber-400">{t('dash_has_risk')}</span>}
                            {rs.has_observation && <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300">{t('dash_has_obs')}</span>}
                          </div>
                        ) : (
                          <span className="text-[10px] text-muted">{t('dash_no_research')}</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Row 2: Watchlists | Recent Activity */}
      <div className="grid grid-cols-1 md:grid-cols-[2fr_1fr] gap-4 md:gap-6">
        {/* My Watchlists */}
        <div className={CARD}>
          <div className="flex items-center justify-between mb-5">
            <div className="flex items-center gap-2">
              <Star className="w-4 h-4 text-brand" />
              <h3 className="text-base font-semibold text-heading">{t('dash_watchlists')}</h3>
            </div>
            {showNewWatchlist ? (
              <div className="flex items-center gap-1">
                <input type="text" value={newWatchlistName} onChange={e => setNewWatchlistName(e.target.value)}
                  onKeyDown={e => { if (e.key === 'Enter') createWatchlist(newWatchlistName); if (e.key === 'Escape') setShowNewWatchlist(false); }}
                  placeholder={t('dash_wl_name_ph')} autoFocus
                  className="h-7 px-2 border border-brand rounded-lg text-xs w-36 focus:ring-2 focus:ring-brand-light outline-none" />
                <button onClick={() => createWatchlist(newWatchlistName)} className="inline-flex items-center px-2 py-1 rounded-lg bg-brand text-white text-xs font-semibold hover:bg-brand-dark transition-colors">
                  <Plus className="w-3 h-3" />
                </button>
                <button onClick={() => setShowNewWatchlist(false)} className="p-1 rounded hover:bg-surface"><X className="w-3.5 h-3.5 text-muted" /></button>
              </div>
            ) : (
              <button onClick={() => setShowNewWatchlist(true)} className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-brand text-white text-xs font-semibold hover:bg-brand-dark transition-colors">
                <Plus className="w-3 h-3" /> {t('dash_new_list')}
              </button>
            )}
          </div>
          {watchlists.length > 0 ? (
            <div className="space-y-3">
              {watchlists.map(g => (
                <div key={g.group_id} className="flex items-center justify-between py-2 px-3 rounded-lg hover:bg-surface/60 transition-colors cursor-pointer border border-border/50">
                  <div className="flex items-center gap-3">
                    <Bookmark className="w-4 h-4 text-brand" />
                    <div>
                      <p className="text-sm font-semibold text-heading">{g.name}</p>
                      <p className="text-xs text-muted">{g.item_count} instruments · {g.description || 'No description'}</p>
                    </div>
                  </div>
                  <ChevronRight className="w-4 h-4 text-muted" />
                </div>
              ))}
            </div>
          ) : (
            <EmptyState
              icon={Star}
              title={t('dash_no_watchlists')}
              description={t('dash_create_wl_desc')}
              action={t('dash_create_watchlist')}
              onAction={() => setShowNewWatchlist(true)}
            />
          )}
        </div>

        {/* Recent Activity */}
        <div className={CARD + ' flex flex-col'}>
          <div className="flex items-center gap-2 mb-4">
            <Clock className="w-4 h-4 text-muted" />
            <h3 className="text-xs font-semibold text-muted uppercase tracking-wider">{t('dash_recent_activity')}</h3>
          </div>
          {activity.length > 0 ? (
            <div className="space-y-3 flex-1">
              {activity.slice(0, 6).map((item, i) => (
                <div key={i} className="flex gap-3 items-start">
                  <ActivityIcon type={item.type} />
                  <div className="min-w-0 flex-1">
                    <p className="text-xs font-semibold text-heading truncate">{item.title}</p>
                    <p className="text-xs text-muted truncate">{item.detail}</p>
                  </div>
                  <span className="text-[10px] text-muted whitespace-nowrap shrink-0">{timeAgo(item.timestamp)}</span>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState icon={Activity} title={t('dash_no_activity')} description={t('dash_no_activity_desc')} />
          )}
        </div>
      </div>

      {/* Row 2.5: Continue Where You Left Off */}
      <div className={CARD}>
        <div className="flex items-center gap-2 mb-5">
          <BookOpen className="w-4 h-4 text-brand" />
          <h3 className="text-base font-semibold text-heading">{t('dash_continue')}</h3>
        </div>
        <ContinueSection onNavigate={onNavigate} />
      </div>

      {/* Row 3: Recent Backtests | Quick Actions */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 md:gap-6">
        {/* Recent Backtests */}
        <div className={CARD}>
          <div className="flex items-center justify-between mb-5">
            <div className="flex items-center gap-2">
              <History className="w-4 h-4 text-brand" />
              <h3 className="text-base font-semibold text-heading">{t('dash_recent_bt')}</h3>
            </div>
            <button onClick={() => onNavigate?.('backtest')} className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-border text-xs font-semibold text-secondary hover:bg-surface transition-colors">
              {t('dash_view_all')}
            </button>
          </div>
          {recentBt.length > 0 ? (
            <div className="space-y-3">
              {recentBt.slice(0, 4).map((bt, i) => {
                const ret = bt.total_return;
                const positive = ret != null && ret >= 0;
                return (
                  <div key={bt.run_id || i} className="flex items-center justify-between py-2 border-b border-border/50 last:border-0 cursor-pointer hover:bg-surface/50 rounded px-2 -mx-2 transition-colors" onClick={() => onNavigate?.('backtest')}>
                    <div className="min-w-0">
                      <p className="text-sm font-semibold text-heading truncate">{bt.strategy_name || 'Strategy'}</p>
                      <p className="text-xs text-muted">{timeAgo(bt.created_at)}</p>
                    </div>
                    <div className="text-right shrink-0 ml-4">
                      {bt.sharpe_ratio != null && <p className="text-xs text-muted">SR {bt.sharpe_ratio.toFixed(2)}</p>}
                      <p className={`text-sm font-bold tabular-nums ${positive ? 'text-brand' : 'text-red-500'}`}>
                        {ret != null ? formatPercent(ret) : '--'}
                      </p>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <EmptyState icon={BarChart3} title={t('dash_no_bt')} description={t('dash_no_bt_desc')} action={t('nav_new_backtest')} onAction={() => onNavigate?.('backtest')} />
          )}
        </div>

        {/* Quick Actions */}
        <div className={CARD}>
          <h3 className="text-base font-semibold text-heading mb-5">{t('dash_quick_actions')}</h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {[
              { icon: FlaskConical, label: t('dash_quick_research'), desc: t('dash_quick_research_desc'), page: 'research', color: 'text-blue-500 bg-blue-50' },
              { icon: BarChart3, label: t('dash_quick_backtest'), desc: t('dash_quick_backtest_desc'), page: 'backtest', color: 'text-brand bg-brand-light' },
              { icon: Target, label: t('dash_quick_screener'), desc: t('dash_quick_screener_desc'), page: 'research', color: 'text-purple-500 bg-purple-50' },
              { icon: ArrowLeftRight, label: t('dash_quick_execution'), desc: t('dash_quick_execution_desc'), page: 'execution', color: 'text-amber-500 bg-amber-50' },
            ].map(a => (
              <button key={a.label} onClick={() => onNavigate?.(a.page)} className="flex items-center gap-3 p-3 rounded-lg border border-border/50 hover:bg-surface/60 hover:border-border transition-all text-left group">
                <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${a.color}`}>
                  <a.icon className="w-5 h-5" />
                </div>
                <div>
                  <p className="text-sm font-semibold text-heading group-hover:text-brand transition-colors">{a.label}</p>
                  <p className="text-[11px] text-muted">{a.desc}</p>
                </div>
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
