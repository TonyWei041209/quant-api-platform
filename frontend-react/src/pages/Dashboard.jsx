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

  if (!loaded) return <div className="text-sm text-muted py-4 text-center">Loading...</div>;
  if (presets.length === 0 && notes.length === 0) {
    return (
      <div className="flex flex-col items-center py-6 text-center">
        <BookOpen className="w-8 h-8 text-muted/40 mb-2" />
        <p className="text-sm text-muted">Your saved presets and notes will appear here</p>
        <p className="text-xs text-muted mt-1">Save a research config or write a note to get started</p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 md:gap-6">
      {/* Recent Presets */}
      <div>
        <h4 className="text-xs font-semibold text-muted uppercase tracking-wider mb-3">Saved Presets</h4>
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
          <p className="text-xs text-muted py-2">No presets saved yet</p>
        )}
      </div>
      {/* Recent Notes */}
      <div>
        <h4 className="text-xs font-semibold text-muted uppercase tracking-wider mb-3">Recent Notes</h4>
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
          <p className="text-xs text-muted py-2">No notes yet</p>
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

  const loadData = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true); else setLoading(true);
    const [bRes, aRes, wRes, hRes] = await Promise.allSettled([
      apiFetch('/daily/brief'),
      apiFetch('/daily/recent-activity?limit=8'),
      apiFetch('/watchlist/groups'),
      apiFetch('/health'),
    ]);
    if (bRes.status === 'fulfilled') setBrief(bRes.value);
    if (aRes.status === 'fulfilled') setActivity(aRes.value?.items || []);
    if (wRes.status === 'fulfilled') setWatchlists(wRes.value?.groups || []);
    if (hRes.status === 'fulfilled') setHealth(hRes.value);
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
            <h1 className="text-2xl font-bold text-heading">Daily Research Home</h1>
            <span className="text-brand font-semibold text-sm">- Live</span>
          </div>
          <p className="text-[11px] font-mono text-muted tracking-wider mt-1">
            {t('dash_status_prefix')} {t('dash_operational')} // LATENCY: {latency}MS // v{version}
          </p>
        </div>
        <div className="flex items-center gap-3">
          {lastRefresh && (
            <span className="text-[10px] text-muted font-mono">
              Updated {lastRefresh.toLocaleTimeString()}
            </span>
          )}
          <button onClick={() => loadData(true)} disabled={refreshing} className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-brand text-white text-sm font-medium hover:bg-brand-dark transition-colors disabled:opacity-60">
            <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} /> {refreshing ? 'Refreshing...' : 'Refresh'}
          </button>
        </div>
      </div>

      {/* Row 1: Data Status | Today's Events | Platform Status */}
      <div className="grid gap-6" style={{ gridTemplateColumns: '1.4fr 1fr 1fr' }}>
        {/* Data Status Hero */}
        <div className={CARD + ' relative overflow-hidden'}>
          <div className="flex items-start justify-between mb-4">
            <span className={`${BADGE_BASE} ${ds.data_freshness === 'current' ? BADGE_GREEN : BADGE_YELLOW}`}>
              {ds.data_freshness === 'current' ? 'DATA CURRENT' : 'DATA STALE'}
            </span>
            <Database className="w-5 h-5 text-brand" />
          </div>
          <div className="tabular-nums text-heading" style={{ fontSize: 56, fontWeight: 800, letterSpacing: -2, lineHeight: 1 }}>
            {formatNumber(ds.total_instruments || 0)}
          </div>
          <p className="text-sm text-muted mt-2">Active instruments in universe</p>
          <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <p className="text-[10px] text-muted uppercase tracking-wider">Price Bars</p>
              <p className="text-lg font-bold text-heading tabular-nums">{formatNumber(ds.total_price_bars || 0)}</p>
            </div>
            <div>
              <p className="text-[10px] text-muted uppercase tracking-wider">Latest Date</p>
              <p className="text-sm font-semibold text-heading">{ds.latest_bar_date || '--'}</p>
            </div>
          </div>
        </div>

        {/* Today's Events */}
        <div className={CARD + ' flex flex-col'}>
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-xs font-semibold text-muted uppercase tracking-wider">Upcoming Events</h3>
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
            <EmptyState icon={Calendar} title="No upcoming earnings" description="No earnings events scheduled for the next 7 days" />
          )}
        </div>

        {/* Platform Status */}
        <div className={CARD + ' flex flex-col'}>
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-xs font-semibold text-muted uppercase tracking-wider">Platform Status</h3>
            <ShieldCheck className="w-4 h-4 text-brand" />
          </div>
          <div className="space-y-3 flex-1">
            <div className="flex items-center justify-between">
              <span className="text-sm text-secondary">DQ Status</span>
              <span className={`${BADGE_BASE} ${dq.status === 'clean' ? BADGE_GREEN : BADGE_YELLOW}`}>
                {dq.unresolved_issues || 0} ISSUES
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-secondary">Pending Intents</span>
              <span className="text-sm font-bold text-heading tabular-nums">{execStatus.pending_intents || 0}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-secondary">Pending Drafts</span>
              <span className="text-sm font-bold text-heading tabular-nums">{execStatus.pending_drafts || 0}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-secondary">Live Submit</span>
              <span className={`${BADGE_BASE} ${BADGE_RED}`}>LOCKED</span>
            </div>
          </div>
          <div className="mt-4 pt-3 border-t border-border">
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-brand animate-pulse" />
              <span className="text-xs text-muted">System operational · {latency}ms</span>
            </div>
          </div>
        </div>
      </div>

      {/* Row 1.5: Portfolio Snapshot */}
      {portfolioSummary && (
        <div className="grid gap-6" style={{ gridTemplateColumns: portfolioSummary.connected ? '1fr 1fr 1fr' : '1fr' }}>
          {portfolioSummary.connected ? (
            <>
              {/* Account Summary */}
              <div className={CARD}>
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <Wallet className="w-4 h-4 text-brand" />
                    <span className="text-sm font-semibold text-heading">Portfolio</span>
                  </div>
                  <span className={`${BADGE_BASE} ${BADGE_GREEN}`}>Connected</span>
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
                  <p className="text-[10px] text-muted mt-2">Snapshot: {formatDate(portfolioSummary.as_of)}</p>
                )}
              </div>

              {/* Top Positions */}
              <div className={CARD}>
                <div className="flex items-center gap-2 mb-3">
                  <Briefcase className="w-4 h-4 text-brand" />
                  <span className="text-sm font-semibold text-heading">Holdings</span>
                </div>
                {portfolioSummary.positions.length > 0 ? (
                  <div className="space-y-2">
                    {portfolioSummary.positions.slice(0, 4).map((pos, i) => (
                      <div key={i} className="flex items-center justify-between text-xs">
                        <span className="font-semibold text-heading">{pos.broker_ticker}</span>
                        <div className="flex items-center gap-3">
                          <span className="text-muted tabular-nums">{pos.quantity} shares</span>
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
                  <span className="text-sm font-semibold text-heading">Unrealized P&L</span>
                </div>
                <div className={`text-2xl font-extrabold tabular-nums mb-1 ${portfolioSummary.total_pnl >= 0 ? 'text-brand-dark' : 'text-red-500'}`}>
                  {portfolioSummary.total_pnl >= 0 ? '+' : ''}{formatNumber(portfolioSummary.total_pnl)}
                </div>
                <p className="text-xs text-muted">
                  Across {portfolioSummary.position_count} position{portfolioSummary.position_count !== 1 ? 's' : ''}
                </p>
                {portfolioSummary.recent_orders.length > 0 && (
                  <div className="mt-3 pt-3 border-t border-border">
                    <p className="text-[10px] font-semibold text-muted uppercase tracking-wider mb-1">Last Order</p>
                    <p className="text-xs text-heading">
                      <span className={`font-semibold ${portfolioSummary.recent_orders[0].side === 'buy' ? 'text-brand-dark' : 'text-red-500'}`}>
                        {portfolioSummary.recent_orders[0].side?.toUpperCase()}
                      </span>
                      {' '}{portfolioSummary.recent_orders[0].broker_ticker} · {portfolioSummary.recent_orders[0].qty} shares
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
                <p className="text-sm font-semibold text-heading">Portfolio Not Connected</p>
                <p className="text-xs text-muted">Configure Trading 212 API key in Settings to see holdings, positions, and orders.</p>
              </div>
              <button onClick={() => onNavigate?.('settings')} className="ml-auto text-xs font-semibold text-brand hover:text-brand-dark">
                Open Settings →
              </button>
            </div>
          )}
        </div>
      )}

      {/* Row 2: Watchlists | Recent Activity */}
      <div className="grid gap-6" style={{ gridTemplateColumns: '2fr 1fr' }}>
        {/* My Watchlists */}
        <div className={CARD}>
          <div className="flex items-center justify-between mb-5">
            <div className="flex items-center gap-2">
              <Star className="w-4 h-4 text-brand" />
              <h3 className="text-base font-semibold text-heading">My Watchlists</h3>
            </div>
            {showNewWatchlist ? (
              <div className="flex items-center gap-1">
                <input type="text" value={newWatchlistName} onChange={e => setNewWatchlistName(e.target.value)}
                  onKeyDown={e => { if (e.key === 'Enter') createWatchlist(newWatchlistName); if (e.key === 'Escape') setShowNewWatchlist(false); }}
                  placeholder="Watchlist name..." autoFocus
                  className="h-7 px-2 border border-brand rounded-lg text-xs w-36 focus:ring-2 focus:ring-brand-light outline-none" />
                <button onClick={() => createWatchlist(newWatchlistName)} className="inline-flex items-center px-2 py-1 rounded-lg bg-brand text-white text-xs font-semibold hover:bg-brand-dark transition-colors">
                  <Plus className="w-3 h-3" />
                </button>
                <button onClick={() => setShowNewWatchlist(false)} className="p-1 rounded hover:bg-surface"><X className="w-3.5 h-3.5 text-muted" /></button>
              </div>
            ) : (
              <button onClick={() => setShowNewWatchlist(true)} className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-brand text-white text-xs font-semibold hover:bg-brand-dark transition-colors">
                <Plus className="w-3 h-3" /> New List
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
              title="No watchlists yet"
              description="Create your first watchlist to track instruments you want to research daily"
              action="Create Watchlist"
              onAction={() => setShowNewWatchlist(true)}
            />
          )}
        </div>

        {/* Recent Activity */}
        <div className={CARD + ' flex flex-col'}>
          <div className="flex items-center gap-2 mb-4">
            <Clock className="w-4 h-4 text-muted" />
            <h3 className="text-xs font-semibold text-muted uppercase tracking-wider">Recent Activity</h3>
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
            <EmptyState icon={Activity} title="No activity yet" description="Activity will appear as you research and run backtests" />
          )}
        </div>
      </div>

      {/* Row 2.5: Continue Where You Left Off */}
      <div className={CARD}>
        <div className="flex items-center gap-2 mb-5">
          <BookOpen className="w-4 h-4 text-brand" />
          <h3 className="text-base font-semibold text-heading">Continue Where You Left Off</h3>
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
              <h3 className="text-base font-semibold text-heading">Recent Backtests</h3>
            </div>
            <button onClick={() => onNavigate?.('backtest')} className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-border text-xs font-semibold text-secondary hover:bg-surface transition-colors">
              View All
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
            <EmptyState icon={BarChart3} title="No backtests yet" description="Run your first backtest to see results here" action="New Backtest" onAction={() => onNavigate?.('backtest')} />
          )}
        </div>

        {/* Quick Actions */}
        <div className={CARD}>
          <h3 className="text-base font-semibold text-heading mb-5">Quick Actions</h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {[
              { icon: FlaskConical, label: 'Research', desc: 'Analyze instruments', page: 'research', color: 'text-blue-500 bg-blue-50' },
              { icon: BarChart3, label: 'Backtest', desc: 'Run strategy test', page: 'backtest', color: 'text-brand bg-brand-light' },
              { icon: Target, label: 'Screener', desc: 'Find candidates', page: 'research', color: 'text-purple-500 bg-purple-50' },
              { icon: ArrowLeftRight, label: 'Execution', desc: 'Manage orders', page: 'execution', color: 'text-amber-500 bg-amber-50' },
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
