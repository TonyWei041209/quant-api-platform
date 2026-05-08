import { useState, useEffect, useCallback, useRef } from 'react';
import { apiFetch, apiPost } from '../hooks/useApi';
import { useI18n } from '../hooks/useI18n';
import { useWorkspace } from '../hooks/useWorkspace';
import { useLiveBrokerTruth } from '../hooks/useLiveBrokerTruth';
import { usePageVisibility } from '../App';
import { formatPercent, formatNumber, formatDate, truncateId } from '../utils';
import {
  TrendingUp, Info, Database, FlaskConical, History, ArrowLeftRight,
  ShieldCheck, ExternalLink, Download, RefreshCw, Zap, Lock,
  Lightbulb, FileText, FilePen, CheckCircle, Send, ChevronRight, ChevronDown,
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

// Compact "X seconds ago" formatter for sub-minute live timestamps.
function timeAgoEpoch(epochSeconds) {
  if (!epochSeconds) return '';
  const diffSeconds = Math.max(0, Math.floor(Date.now() / 1000 - epochSeconds));
  if (diffSeconds < 60) return `${diffSeconds}s ago`;
  if (diffSeconds < 3600) return `${Math.floor(diffSeconds / 60)}m ago`;
  if (diffSeconds < 86400) return `${Math.floor(diffSeconds / 3600)}h ago`;
  return `${Math.floor(diffSeconds / 86400)}d ago`;
}

// Live broker truth badge: LIVE / CACHED / CONNECTING / DB SNAPSHOT / STALE.
// Read-only signal; never affects execution flow or live submit.
function LiveTruthBadge({ meta }) {
  const badge = meta?.selectedSource || meta?.truthBadge || 'STALE';
  const className =
    badge === 'LIVE'
      ? `${BADGE_BASE} ${BADGE_GREEN}`
      : badge === 'CACHED'
      ? `${BADGE_BASE} ${BADGE_BLUE}`
      : badge === 'CONNECTING'
      ? `${BADGE_BASE} ${BADGE_BLUE}`
      : badge === 'DB SNAPSHOT'
      ? `${BADGE_BASE} ${BADGE_YELLOW}`
      : `${BADGE_BASE} ${BADGE_YELLOW}`;
  return <span className={className}>{badge}</span>;
}

// Numbers row for the portfolio summary card. Reads the unified
// `displayPositions` and `summary` from the hook so every Dashboard
// portfolio card agrees on the position count and totals.
function LiveSummaryFigures({ liveSummary, fallbackSummary, displayCount, displayMarketValue }) {
  const portfolioValue = liveSummary?.portfolio_value ?? fallbackSummary?.account?.portfolio_value ?? displayMarketValue ?? 0;
  const cashFree = liveSummary?.cash_available_to_trade ?? liveSummary?.cash_free ?? fallbackSummary?.account?.cash_free ?? 0;
  const currency = liveSummary?.currency || fallbackSummary?.account?.currency || '$';
  return (
    <>
      <div className="text-2xl font-extrabold text-heading tabular-nums mb-1">
        {currency}
        {formatNumber(portfolioValue)}
      </div>
      <div className="flex items-center gap-4 text-xs text-muted">
        <span>Cash: {currency}{formatNumber(cashFree)}</span>
        <span>·</span>
        <span>
          {displayCount} position{displayCount !== 1 ? 's' : ''}
        </span>
      </div>
    </>
  );
}

// Two-line staleness indicator. Top line is the seconds-grain live read-through
// freshness; bottom line is the hours-grain DB snapshot freshness. Adds an
// extra explanatory line while live is connecting and we are showing DB
// rows in the meantime.
function LiveAndDbStaleness({ liveMeta, dbAsOf, showConnectingNote }) {
  const liveAgo = liveMeta?.live_fetched_at ? timeAgoEpoch(liveMeta.live_fetched_at) : null;
  return (
    <div className="text-[10px] text-muted mt-2 space-y-0.5">
      {liveAgo ? (
        <p>Live Trading 212 truth: {liveAgo}</p>
      ) : (
        <p className="text-muted/70">Live Trading 212 truth: connecting…</p>
      )}
      {dbAsOf && <p>Last DB snapshot: {timeAgo(dbAsOf)}</p>}
      {showConnectingNote && (
        <p className="text-[10px] text-blue-500 italic">
          Showing DB snapshot while live broker truth connects
        </p>
      )}
    </div>
  );
}

// Trading 212 Mirror watchlist card. Composed read-only view: held positions
// + recently filled trades + manually-watched tickers (per-browser localStorage).
// Trading 212's public API does not expose the in-app watchlist; we never
// scrape, never automate the browser, never call private endpoints.
function Trading212MirrorCard({
  mirror,
  loading,
  manualTickers,
  showAddManual,
  setShowAddManual,
  manualInput,
  setManualInput,
  onAdd,
  onRemove,
  onRefresh,
  onResearch,
}) {
  const items = mirror?.items || [];
  const explanation = mirror?.explanation || (
    'Trading 212 does not expose app watchlists through the public API. ' +
    'This mirror combines live holdings, recent trades, and your manually ' +
    'added watched tickers.'
  );

  const renderTag = (tag) => {
    const tagClass = {
      HELD: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300',
      RECENTLY_TRADED: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300',
      WATCHED: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300',
      UNMAPPED: 'bg-gray-200 text-gray-700 dark:bg-gray-700 dark:text-gray-300',
    }[tag] || 'bg-gray-100 text-gray-600';
    const label = {
      HELD: 'Held',
      RECENTLY_TRADED: 'Recently traded',
      WATCHED: 'Watched',
      UNMAPPED: 'Unmapped',
    }[tag] || tag;
    return (
      <span key={tag} className={`px-1.5 py-0.5 rounded text-[9px] font-bold ${tagClass}`}>
        {label}
      </span>
    );
  };

  return (
    <div className={CARD}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Bookmark className="w-4 h-4 text-brand" />
          <h3 className="text-base font-semibold text-heading">Trading 212 Mirror</h3>
          {mirror?.counts?.total != null && (
            <span className="text-[11px] text-muted">{mirror.counts.total} item{mirror.counts.total === 1 ? '' : 's'}</span>
          )}
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={() => setShowAddManual(s => !s)}
            className="inline-flex items-center gap-1 px-2 py-1 rounded-md border border-brand/40 text-[11px] font-semibold text-brand hover:bg-brand-light transition-colors"
            title="Add tickers to your watched list (saved in this browser only)"
          >
            <Plus className="w-3 h-3" /> Add tickers
          </button>
          <button
            onClick={onRefresh}
            className="inline-flex items-center gap-1 px-2 py-1 rounded-md border border-brand/40 text-[11px] font-semibold text-brand hover:bg-brand-light transition-colors"
            title="Refresh held + recently traded from the platform DB. No T212 write, no order activity."
          >
            <RefreshCw className={`w-3 h-3 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      <p className="text-[11px] text-muted mb-3 italic">{explanation}</p>

      {showAddManual && (
        <div className="mb-3 p-3 rounded-md border border-brand/30 bg-brand-light/20">
          <p className="text-[11px] text-muted mb-2">
            Comma- or newline-separated tickers (e.g. <code>RKLB, CRWV, HIMS</code>). Saved in this browser only.
          </p>
          <textarea
            value={manualInput}
            onChange={e => setManualInput(e.target.value)}
            placeholder="RKLB, CRWV, HIMS"
            rows={2}
            className="w-full px-2 py-1 border border-border rounded text-xs font-mono focus:ring-2 focus:ring-brand-light outline-none"
          />
          <div className="flex items-center gap-2 mt-2">
            <button
              onClick={() => onAdd(manualInput)}
              className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md bg-brand text-white text-[11px] font-semibold hover:bg-brand-dark transition-colors"
            >
              <Plus className="w-3 h-3" /> Add
            </button>
            <button
              onClick={() => { setShowAddManual(false); setManualInput(''); }}
              className="text-[11px] text-muted hover:text-heading"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {loading && items.length === 0 ? (
        <div className="flex items-center justify-center py-6 text-xs text-muted">
          <RefreshCw className="w-3 h-3 animate-spin mr-1.5" /> Loading mirror…
        </div>
      ) : items.length > 0 ? (
        <div className="divide-y divide-border/40">
          {items.map(item => {
            const pnl = item.live_pnl;
            const pnlClass = pnl == null ? 'text-muted' : pnl >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-500 dark:text-red-400';
            return (
              <div key={item.display_ticker} className="py-2 flex items-center justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-1.5 flex-wrap">
                    <span className="text-xs font-bold text-heading">{item.display_ticker}</span>
                    {(item.source_tags || []).map(renderTag)}
                  </div>
                  <p className="text-[10px] text-muted truncate">
                    {item.company_name || item.broker_ticker || '—'}
                    {item.live_quantity != null && (
                      <> · qty {Number(item.live_quantity).toFixed(2)}</>
                    )}
                  </p>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  {pnl != null && (
                    <span className={`text-[11px] font-semibold tabular-nums ${pnlClass}`}>
                      {pnl >= 0 ? '+' : ''}{Number(pnl).toFixed(2)}
                    </span>
                  )}
                  {item.is_user_watched && (
                    <button
                      onClick={() => onRemove(item.display_ticker)}
                      className="p-1 rounded hover:bg-surface text-muted hover:text-red-500"
                      title="Remove from watched"
                    >
                      <X className="w-3 h-3" />
                    </button>
                  )}
                  {item.instrument_id && (
                    <button
                      onClick={() => onResearch(item)}
                      className="px-2 py-1 rounded text-[10px] font-semibold text-brand border border-brand/30 hover:bg-brand-light transition-colors"
                    >
                      Research
                    </button>
                  )}
                </div>
              </div>
            );
          })}
          {manualTickers.length > 0 && (
            <p className="text-[10px] text-muted italic pt-2">
              Manual tickers saved on this browser: {manualTickers.length}
            </p>
          )}
        </div>
      ) : (
        <div className="py-4 text-center">
          <p className="text-xs text-muted mb-1">No held positions, recent trades, or watched tickers yet.</p>
          <p className="text-[10px] text-muted">Add tickers above to start tracking.</p>
        </div>
      )}
    </div>
  );
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
  const { isVisible, refreshSignal } = usePageVisibility();
  const liveBrokerTruth = useLiveBrokerTruth({
    pageVisible: isVisible,
    fallback: portfolioSummary,
  });
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
  const [expandedWatchlist, setExpandedWatchlist] = useState(null);
  const [watchlistItemsMap, setWatchlistItemsMap] = useState({});
  const [watchlistItemsLoading, setWatchlistItemsLoading] = useState({});
  const [snapshotMap, setSnapshotMap] = useState({});

  // Trading 212 Mirror watchlist — composed view (Held + Recently traded
  // + manually-watched tickers). Manual tickers are persisted in
  // localStorage on this device only; the backend endpoint is stateless
  // with respect to watched tickers (no DB schema migration this phase).
  const [mirror, setMirror] = useState(null);
  const [mirrorLoading, setMirrorLoading] = useState(false);
  const [manualTickers, setManualTickers] = useState(() => {
    try {
      const raw = localStorage.getItem('trading212_mirror_manual_tickers');
      if (!raw) return [];
      const parsed = JSON.parse(raw);
      return Array.isArray(parsed) ? parsed.filter(t => typeof t === 'string') : [];
    } catch {
      return [];
    }
  });
  const [showAddManual, setShowAddManual] = useState(false);
  const [manualInput, setManualInput] = useState('');

  const toggleWatchlistExpand = useCallback(async (groupId) => {
    if (expandedWatchlist === groupId) {
      setExpandedWatchlist(null);
      return;
    }
    setExpandedWatchlist(groupId);
    if (watchlistItemsMap[groupId]) return; // already loaded
    setWatchlistItemsLoading(prev => ({ ...prev, [groupId]: true }));
    try {
      const res = await apiFetch(`/watchlist/groups/${groupId}/items`);
      const items = res?.items || [];
      setWatchlistItemsMap(prev => ({ ...prev, [groupId]: items }));
      // Fetch research status + quant snapshots for these items
      const ids = items.map(i => i.instrument_id).filter(Boolean);
      if (ids.length > 0) {
        const idsParam = ids.join(',');
        try {
          const [rs, snapRes] = await Promise.allSettled([
            apiFetch(`/portfolio/research-status?instrument_ids=${idsParam}`),
            apiFetch(`/watchlist/snapshots?instrument_ids=${idsParam}`),
          ]);
          if (rs.status === 'fulfilled' && rs.value && typeof rs.value === 'object')
            setResearchStatus(prev => ({ ...prev, ...rs.value }));
          if (snapRes.status === 'fulfilled' && snapRes.value?.items) {
            const byId = {};
            for (const s of snapRes.value.items) byId[s.instrument_id] = s;
            setSnapshotMap(prev => ({ ...prev, ...byId }));
          }
        } catch {}
      }
    } catch {
      setWatchlistItemsMap(prev => ({ ...prev, [groupId]: [] }));
    }
    setWatchlistItemsLoading(prev => ({ ...prev, [groupId]: false }));
  }, [expandedWatchlist, watchlistItemsMap]);

  const loadMirror = useCallback(async (tickers) => {
    setMirrorLoading(true);
    try {
      const list = tickers ?? manualTickers;
      const params = new URLSearchParams();
      if (list && list.length > 0) params.set('manual', list.join(','));
      const path = '/watchlists/trading212-mirror' + (params.toString() ? `?${params.toString()}` : '');
      const data = await apiFetch(path);
      setMirror(data);
    } catch {
      setMirror(null);
    } finally {
      setMirrorLoading(false);
    }
  }, [manualTickers]);

  const persistManualTickers = useCallback((next) => {
    setManualTickers(next);
    try {
      localStorage.setItem('trading212_mirror_manual_tickers', JSON.stringify(next));
    } catch {}
    loadMirror(next);
  }, [loadMirror]);

  const addManualTickers = useCallback((raw) => {
    if (!raw || !raw.trim()) return;
    const incoming = raw
      .split(/[,\n\s]+/)
      .map(s => s.trim().toUpperCase().replace(/[^A-Z0-9.\-_]/g, ''))
      .filter(Boolean);
    if (!incoming.length) return;
    const merged = Array.from(new Set([...manualTickers, ...incoming]));
    persistManualTickers(merged);
    setManualInput('');
    setShowAddManual(false);
  }, [manualTickers, persistManualTickers]);

  const removeManualTicker = useCallback((ticker) => {
    persistManualTickers(manualTickers.filter(t => t !== ticker));
  }, [manualTickers, persistManualTickers]);

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
    // Trading 212 Mirror is loaded on initial mount and on each refresh.
    loadMirror();
    setLoading(false);
    setRefreshing(false);
    setLastRefresh(new Date());
  }, [loadMirror]);

  useEffect(() => { loadData(); }, [loadData]);

  // Auto-refresh when page becomes visible again (after navigating away and back)
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
              {/* Account Summary + Live broker truth banner.
                  All three portfolio cards (this one, Top Positions, P&L)
                  read from the same source returned by useLiveBrokerTruth so
                  they cannot disagree about the number of positions. */}
              <div className={CARD}>
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <Wallet className="w-4 h-4 text-brand" />
                    <span className="text-sm font-semibold text-heading">{t('dash_portfolio')}</span>
                  </div>
                  <LiveTruthBadge meta={liveBrokerTruth} />
                </div>
                <LiveSummaryFigures
                  liveSummary={liveBrokerTruth.summary}
                  fallbackSummary={portfolioSummary}
                  displayCount={liveBrokerTruth.positions.length}
                  displayMarketValue={liveBrokerTruth.totalMarketValue}
                />
                <LiveAndDbStaleness
                  liveMeta={liveBrokerTruth.livePositionsMeta}
                  dbAsOf={portfolioSummary.as_of}
                  showConnectingNote={liveBrokerTruth.showDbWhileConnecting}
                />
                <button
                  onClick={liveBrokerTruth.refresh}
                  className="mt-3 inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md border border-brand/40 text-[11px] font-semibold text-brand hover:bg-brand-light transition-colors"
                  title="Force a live readonly fetch from Trading 212. No DB write, no order activity."
                >
                  <RefreshCw className="w-3 h-3" /> Refresh broker truth
                </button>
              </div>

              {/* Top Positions — uses the same selected source as the other cards.
                  "No open positions" only renders when the source is confidently
                  empty (LIVE returned 0, or DB SNAPSHOT explicitly has 0). */}
              <div className={CARD}>
                <div className="flex items-center gap-2 mb-3">
                  <Briefcase className="w-4 h-4 text-brand" />
                  <span className="text-sm font-semibold text-heading">{t('dash_holdings')}</span>
                </div>
                {liveBrokerTruth.positions.length > 0 ? (
                  <div className="space-y-2">
                    {liveBrokerTruth.positions.slice(0, 4).map((pos, i) => (
                      <div key={pos.broker_ticker || i} className="flex items-center justify-between text-xs">
                        <span className="font-semibold text-heading">{pos.broker_ticker}</span>
                        <div className="flex items-center gap-3">
                          <span className="text-muted tabular-nums">{formatNumber(pos.quantity, 2)} {t('dash_shares')}</span>
                          <span className={`font-semibold tabular-nums ${pos.pnl >= 0 ? 'text-brand-dark' : 'text-red-500'}`}>
                            {pos.pnl >= 0 ? '+' : ''}{formatNumber(pos.pnl)}
                          </span>
                        </div>
                      </div>
                    ))}
                    {liveBrokerTruth.positions.length > 4 && (
                      <p className="text-[10px] text-muted">+{liveBrokerTruth.positions.length - 4} more</p>
                    )}
                  </div>
                ) : liveBrokerTruth.isConfidentlyEmpty ? (
                  <p className="text-xs text-muted py-2">No open positions</p>
                ) : (
                  <p className="text-xs text-muted py-2 italic">Loading broker truth…</p>
                )}
              </div>

              {/* P&L Summary — total derived from the SAME displayPositions
                  that Holdings renders, so the count never disagrees. */}
              <div className={CARD}>
                <div className="flex items-center gap-2 mb-3">
                  <DollarSign className="w-4 h-4 text-brand" />
                  <span className="text-sm font-semibold text-heading">{t('dash_unrealized_pnl')}</span>
                </div>
                {(() => {
                  const displayPnL = liveBrokerTruth.totalPnL;
                  const displayCount = liveBrokerTruth.positions.length;
                  return (
                    <>
                      <div className={`text-2xl font-extrabold tabular-nums mb-1 ${displayPnL >= 0 ? 'text-brand-dark' : 'text-red-500'}`}>
                        {displayPnL >= 0 ? '+' : ''}{formatNumber(displayPnL)}
                      </div>
                      <p className="text-xs text-muted">
                        Across {displayCount} position{displayCount !== 1 ? 's' : ''}
                      </p>
                    </>
                  );
                })()}
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

      {/* Row 1.6: Portfolio Positions Detail Table — live truth when available */}
      {portfolioSummary?.connected && liveBrokerTruth.positions.length > 0 && (
        <div className={CARD + ' overflow-hidden !p-0'}>
          <div className="flex items-center justify-between px-5 py-4">
            <div className="flex items-center gap-2">
              <PieChart className="w-4 h-4 text-brand" />
              <h3 className="text-sm font-semibold text-heading">{t('dash_portfolio_detail')}</h3>
              <span className="text-[10px] text-muted">{liveBrokerTruth.positions.length} positions</span>
              <LiveTruthBadge meta={liveBrokerTruth} />
            </div>
            {liveBrokerTruth.positions.length > 5 && (
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
                {(positionsExpanded ? liveBrokerTruth.positions : liveBrokerTruth.positions.slice(0, 5)).map((pos, i) => {
                  const pnlPct = pos.pnl_percent ?? (pos.avg_cost > 0 ? ((pos.current_price - pos.avg_cost) / pos.avg_cost) * 100 : 0);
                  const rs = researchStatus[pos.instrument_id] || null;
                  const totalValue = liveBrokerTruth.positions.reduce((s, p) => s + (p.market_value || 0), 0) || portfolioSummary.total_market_value || 1;
                  const weight = ((pos.market_value || 0) / totalValue * 100);
                  return (
                    <tr key={pos.instrument_id || i}
                      onClick={() => {
                        if (pos.instrument_id) try { sessionStorage.setItem('research_instrument', pos.instrument_id); } catch {}
                        onNavigate?.('research');
                      }}
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
        {/* Trading 212 Mirror + My Watchlists stacked in the same column */}
        <div className="flex flex-col gap-4">
          <Trading212MirrorCard
            mirror={mirror}
            loading={mirrorLoading}
            manualTickers={manualTickers}
            showAddManual={showAddManual}
            setShowAddManual={setShowAddManual}
            manualInput={manualInput}
            setManualInput={setManualInput}
            onAdd={addManualTickers}
            onRemove={removeManualTicker}
            onRefresh={() => loadMirror()}
            onResearch={(item) => {
              if (item.instrument_id) {
                try { sessionStorage.setItem('research_instrument', item.instrument_id); } catch {}
                onNavigate?.('research');
              }
            }}
          />
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
              {watchlists.map(g => {
                const isExpanded = expandedWatchlist === g.group_id;
                const items = watchlistItemsMap[g.group_id] || [];
                const itemsLoading = watchlistItemsLoading[g.group_id];
                return (
                  <div key={g.group_id} className="rounded-lg border border-border/50 overflow-hidden">
                    <div onClick={() => toggleWatchlistExpand(g.group_id)}
                      className="flex items-center justify-between py-2.5 px-3 hover:bg-surface/60 transition-colors cursor-pointer">
                      <div className="flex items-center gap-3">
                        <Bookmark className="w-4 h-4 text-brand" />
                        <div>
                          <p className="text-sm font-semibold text-heading">{g.name}</p>
                          <p className="text-xs text-muted">{g.item_count} {t('dash_wl_items')}</p>
                        </div>
                      </div>
                      {isExpanded
                        ? <ChevronDown className="w-4 h-4 text-muted" />
                        : <ChevronRight className="w-4 h-4 text-muted" />
                      }
                    </div>
                    {isExpanded && (
                      <div className="border-t border-border/50 bg-hover-row/30">
                        {itemsLoading ? (
                          <div className="flex items-center justify-center py-4 text-xs text-muted"><RefreshCw className="w-3 h-3 animate-spin mr-1.5" /> {t('loading')}</div>
                        ) : items.length > 0 ? (
                          <div className="divide-y divide-border/30">
                            {items.map(item => {
                              const iid = item.instrument_id;
                              const held = isHeld(iid);
                              const rs = researchStatus[iid] || null;
                              const snap = snapshotMap[iid] || null;
                              const pctClass = v => v == null ? 'text-muted' : v >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-500 dark:text-red-400';
                              const fmtPct = v => v == null ? '—' : `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`;
                              const freshLabel = () => {
                                if (!snap) return null;
                                const d = snap.research_freshness_days;
                                if (d == null) return t('snap_no_research');
                                if (d === 0) return t('snap_researched_today');
                                if (d === 1) return t('snap_researched_yesterday');
                                return t('snap_researched_ago').replace('{days}', d);
                              };
                              const w52Label = () => {
                                if (!snap || snap.week52_pct == null) return null;
                                return `${snap.week52_pct.toFixed(0)}%`;
                              };
                              return (
                                <div key={item.item_id} className="px-3 py-2 hover:bg-hover transition-colors">
                                  <div className="flex items-center justify-between">
                                    <div className="flex items-center gap-3 min-w-0">
                                      <div className="min-w-0">
                                        <div className="flex items-center gap-1.5">
                                          <span className="text-xs font-bold text-heading">{item.ticker || iid?.slice(0,8)}</span>
                                          {held && <span className="px-1 py-0.5 rounded text-[8px] font-bold bg-brand-light text-brand-dark">{t('res_held')}</span>}
                                        </div>
                                        <p className="text-[10px] text-muted truncate">{item.issuer_name}</p>
                                      </div>
                                    </div>
                                    <div className="flex items-center gap-2 shrink-0">
                                      {rs ? (
                                        <div className="flex gap-1">
                                          {rs.has_thesis && <span className="px-1 py-0.5 rounded text-[8px] font-bold bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400">{t('dash_has_thesis')}</span>}
                                          {rs.has_risk && <span className="px-1 py-0.5 rounded text-[8px] font-bold bg-amber-50 dark:bg-amber-900/20 text-amber-600 dark:text-amber-400">{t('dash_has_risk')}</span>}
                                          {rs.has_observation && <span className="px-1 py-0.5 rounded text-[8px] font-bold bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300">{t('dash_has_obs')}</span>}
                                        </div>
                                      ) : (
                                        <span className="text-[9px] text-muted">{t('dash_no_research')}</span>
                                      )}
                                      <button onClick={(e) => {
                                          e.stopPropagation();
                                          try { sessionStorage.setItem('research_instrument', item.instrument_id); } catch {}
                                          onNavigate?.('research');
                                        }}
                                        className="px-2 py-1 rounded text-[10px] font-semibold text-brand border border-brand/30 hover:bg-brand-light transition-colors">
                                        {t('dash_wl_research_btn')}
                                      </button>
                                    </div>
                                  </div>
                                  {/* Quant Snapshot Strip */}
                                  {snap && (
                                    <div className="flex items-center gap-3 mt-1 ml-0 flex-wrap">
                                      <span className="text-[9px] text-muted">{t('snap_1d')}</span>
                                      <span className={`text-[10px] font-semibold ${pctClass(snap.change_1d_pct)}`}>{fmtPct(snap.change_1d_pct)}</span>
                                      <span className="text-[9px] text-muted">{t('snap_5d')}</span>
                                      <span className={`text-[10px] font-semibold ${pctClass(snap.change_5d_pct)}`}>{fmtPct(snap.change_5d_pct)}</span>
                                      <span className="text-[9px] text-muted">{t('snap_1m')}</span>
                                      <span className={`text-[10px] font-semibold ${pctClass(snap.change_1m_pct)}`}>{fmtPct(snap.change_1m_pct)}</span>
                                      {w52Label() && (<>
                                        <span className="text-border">|</span>
                                        <span className="text-[9px] text-muted">{t('snap_52w')}</span>
                                        <span className="text-[10px] font-semibold text-heading">{w52Label()}</span>
                                      </>)}
                                      <span className="text-border">|</span>
                                      <span className="text-[9px] text-muted italic">{freshLabel()}</span>
                                    </div>
                                  )}
                                </div>
                              );
                            })}
                          </div>
                        ) : (
                          <p className="text-xs text-muted text-center py-4">{t('dash_wl_no_items')}</p>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
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
