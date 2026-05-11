import { useCallback, useEffect, useState } from 'react';
import { Calendar, Newspaper, Search, RefreshCw, ExternalLink, AlertCircle, Star, Layers, Globe, Bookmark, Moon, ChevronDown, ChevronRight } from 'lucide-react';
import { apiFetch } from '../hooks/useApi';
import { useI18n } from '../hooks/useI18n';
import { usePageVisibility } from '../App';

const CARD = 'rounded-xl border border-border bg-card p-4 sm:p-5';
const BADGE_BASE = 'inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-bold';

const SCOPES = [
  { id: 'mirror', icon: Bookmark, key: 'me_tab_mirror' },
  { id: 'scanner', icon: Layers, key: 'me_tab_scanner' },
  { id: 'all_supported', icon: Globe, key: 'me_tab_all' },
  { id: 'ticker', icon: Search, key: 'me_tab_ticker' },
];

// Compact row used inside the Overnight Market Brief preview. Pure
// presentation — no fetching of its own. Click → open the existing
// ticker detail drawer for that symbol.
function BriefCandidate({ c, t, onOpen }) {
  const tagClass = (tag) => ({
    HELD: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300',
    RECENTLY_TRADED: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300',
    WATCHED: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300',
    SCANNER: 'bg-violet-100 text-violet-700 dark:bg-violet-900/30 dark:text-violet-300',
    UNMAPPED: 'bg-gray-200 text-gray-700 dark:bg-gray-700 dark:text-gray-300',
  }[tag] || 'bg-gray-100 text-gray-600');
  return (
    <div
      onClick={() => onOpen(c.ticker)}
      className="flex items-center justify-between gap-2 py-1.5 px-2 rounded hover:bg-hover-row/30 cursor-pointer"
    >
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-1.5 flex-wrap">
          <span className="text-xs font-bold text-heading">{c.ticker}</span>
          {(c.source_tags || []).slice(0, 4).map(tag => (
            <span key={tag} className={`${BADGE_BASE} ${tagClass(tag)}`}>
              {tag}
            </span>
          ))}
          {c.research_priority >= 4 && (
            <span className={`${BADGE_BASE} bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300`}>
              P{c.research_priority}
            </span>
          )}
        </div>
        <p className="text-[10px] text-muted truncate">
          {c.company_name || '—'}
          {c.taxonomy?.broad && <> · {c.taxonomy.broad}</>}
        </p>
      </div>
      <div className="text-right shrink-0 text-[10px]">
        {c.recent_news?.length > 0 && (
          <p className="text-blue-600 dark:text-blue-400">
            {c.recent_news.length} {t('mb_news')}
          </p>
        )}
        {c.upcoming_earnings?.length > 0 && (
          <p className="text-amber-600 dark:text-amber-400">
            {c.upcoming_earnings.length} {t('mb_earnings')}
          </p>
        )}
        {c.price_move?.change_1d_pct != null && (
          <p className={c.price_move.change_1d_pct >= 0
            ? 'text-emerald-600 dark:text-emerald-400'
            : 'text-red-500 dark:text-red-400'}>
            {c.price_move.change_1d_pct >= 0 ? '+' : ''}{c.price_move.change_1d_pct.toFixed(1)}%
          </p>
        )}
      </div>
      {/* Research priority factor chips + why-it-matters tooltip line.
          Renders only when the brief response carries the new fields
          (graceful when an older snapshot is loaded from history). */}
      {(c.research_priority_factors?.length > 0 || c.why_it_matters) && (
        <div
          className="basis-full text-[10px] text-muted mt-1 space-y-1"
          onClick={(e) => e.stopPropagation()}
        >
          {c.research_priority_factors?.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {c.research_priority_factors.map((f) => {
                const cls = {
                  high: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300',
                  medium: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300',
                  low: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300',
                  info: 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400',
                }[f.weight] || 'bg-gray-100 text-gray-600';
                return (
                  <span key={f.id} className={`${BADGE_BASE} ${cls}`}>
                    {f.label}
                  </span>
                );
              })}
            </div>
          )}
          {c.why_it_matters && (
            <p className="italic">{c.why_it_matters}</p>
          )}
        </div>
      )}
    </div>
  );
}


export default function MarketEvents() {
  const { t } = useI18n();
  const { isVisible } = usePageVisibility();
  const [scope, setScope] = useState('mirror');
  const [days, setDays] = useState(7);
  const [tickerInput, setTickerInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [feed, setFeed] = useState(null);
  const [error, setError] = useState(null);
  const [tickerDetail, setTickerDetail] = useState(null);
  const [selectedTicker, setSelectedTicker] = useState(null);

  const loadFeed = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      params.set('scope', scope);
      params.set('days', String(days));
      if (scope === 'ticker') {
        if (!tickerInput.trim()) {
          setFeed(null);
          setLoading(false);
          return;
        }
        params.set('ticker', tickerInput.trim().toUpperCase());
      }
      const res = await apiFetch(`/market-events/feed?${params.toString()}`);
      setFeed(res);
    } catch (e) {
      setError(e?.message || 'failed to load market events');
      setFeed(null);
    } finally {
      setLoading(false);
    }
  }, [scope, days, tickerInput]);

  useEffect(() => {
    if (!isVisible) return;
    if (scope === 'ticker') return; // require explicit submit
    loadFeed();
  }, [scope, days, loadFeed, isVisible]);

  const openTickerDetail = useCallback(async (ticker) => {
    if (!ticker) return;
    setSelectedTicker(ticker);
    setTickerDetail({ loading: true });
    try {
      const res = await apiFetch(`/market-events/ticker/${encodeURIComponent(ticker)}?days=30`);
      setTickerDetail(res);
    } catch (e) {
      setTickerDetail({ error: e?.message || 'failed' });
    }
  }, []);

  const closeDetail = () => { setSelectedTicker(null); setTickerDetail(null); };

  // Overnight Market Brief preview state. The brief panel can show one
  // of three things: a freshly generated brief, the most recent
  // persisted brief from history, or a specific historical run by id.
  const [briefOpen, setBriefOpen] = useState(false);
  const [brief, setBrief] = useState(null);
  const [briefLoading, setBriefLoading] = useState(false);
  const [briefError, setBriefError] = useState(null);
  const [briefHistory, setBriefHistory] = useState(null);
  const [briefHistoryLoading, setBriefHistoryLoading] = useState(false);

  const loadBrief = useCallback(async () => {
    setBriefLoading(true);
    setBriefError(null);
    try {
      // Default news_top_n is 5 — kept low for the on-demand interactive
      // preview to stay below provider rate-limit ceilings. Cached news
      // fallback is used automatically when a provider hits 429.
      const res = await apiFetch('/market-brief/overnight-preview?days=7&scanner_limit=50&news_top_n=5');
      setBrief(res);
    } catch (e) {
      setBriefError(e?.message || 'brief_failed');
      setBrief(null);
    } finally {
      setBriefLoading(false);
    }
  }, []);

  const loadLatestBrief = useCallback(async () => {
    setBriefLoading(true);
    setBriefError(null);
    try {
      const res = await apiFetch('/market-brief/latest');
      setBrief(res);
    } catch (e) {
      setBriefError(e?.message || 'brief_latest_failed');
    } finally {
      setBriefLoading(false);
    }
  }, []);

  const loadBriefById = useCallback(async (runId) => {
    if (!runId) return;
    setBriefLoading(true);
    setBriefError(null);
    try {
      const res = await apiFetch(`/market-brief/${encodeURIComponent(runId)}`);
      setBrief(res);
    } catch (e) {
      setBriefError(e?.message || 'brief_by_id_failed');
    } finally {
      setBriefLoading(false);
    }
  }, []);

  const loadBriefHistory = useCallback(async () => {
    setBriefHistoryLoading(true);
    try {
      const res = await apiFetch('/market-brief/history?limit=10');
      setBriefHistory(res?.items || []);
    } catch {
      setBriefHistory([]);
    } finally {
      setBriefHistoryLoading(false);
    }
  }, []);

  const toggleBrief = () => {
    setBriefOpen(o => {
      const next = !o;
      if (next && !brief && !briefLoading) {
        loadBrief();
      }
      return next;
    });
  };

  const renderProviderStatus = (status) => {
    if (!status) return null;
    const colorMap = {
      ok: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300',
      cached: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300',
      empty: 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400',
      partial: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300',
      timeout: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300',
      rate_limited: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300',
      unavailable: 'bg-gray-200 text-gray-700 dark:bg-gray-700 dark:text-gray-300',
      error: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300',
    };
    return Object.entries(status).map(([k, v]) => (
      <span key={k} className={`${BADGE_BASE} ${colorMap[v] || colorMap.unavailable}`}>
        {k}: {v}
      </span>
    ));
  };

  const renderTags = (tags) => (tags || []).map(tag => {
    const tagClass = {
      HELD: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300',
      RECENTLY_TRADED: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300',
      WATCHED: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300',
      UNMAPPED: 'bg-gray-200 text-gray-700 dark:bg-gray-700 dark:text-gray-300',
    }[tag] || 'bg-gray-100 text-gray-600';
    const label = {
      HELD: t('me_tag_held'),
      RECENTLY_TRADED: t('me_tag_recent'),
      WATCHED: t('me_tag_watched'),
      UNMAPPED: t('me_tag_unmapped'),
    }[tag] || tag;
    return <span key={tag} className={`${BADGE_BASE} ${tagClass}`}>{label}</span>;
  });

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className={CARD}>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-lg font-bold text-heading flex items-center gap-2">
            <Calendar className="w-5 h-5 text-brand" /> {t('me_title')}
          </h2>
          <button
            onClick={loadFeed}
            disabled={loading}
            className="inline-flex items-center gap-1 px-3 py-1.5 rounded-md border border-brand/40 text-xs font-semibold text-brand hover:bg-brand-light transition-colors"
          >
            <RefreshCw className={`w-3 h-3 ${loading ? 'animate-spin' : ''}`} />
            {t('me_refresh')}
          </button>
        </div>
        <p className="text-xs text-muted italic mb-3">{t('me_disclaimer')}</p>

        {/* Scope tabs */}
        <div className="flex flex-wrap items-center gap-2 mb-3">
          {SCOPES.map(s => {
            const Icon = s.icon;
            const active = scope === s.id;
            return (
              <button
                key={s.id}
                onClick={() => setScope(s.id)}
                className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-semibold transition-colors ${
                  active
                    ? 'bg-brand text-white'
                    : 'border border-border text-muted hover:bg-surface'
                }`}
              >
                <Icon className="w-3.5 h-3.5" /> {t(s.key)}
              </button>
            );
          })}
        </div>

        {/* Filters */}
        <div className="flex flex-wrap items-center gap-3 text-xs text-muted">
          <label>
            {t('me_days')}:
            <select
              value={days}
              onChange={e => setDays(parseInt(e.target.value, 10))}
              className="ml-1 px-2 py-1 border border-border rounded text-xs"
            >
              <option value={3}>3</option>
              <option value={7}>7</option>
              <option value={14}>14</option>
              <option value={30}>30</option>
            </select>
          </label>
          {scope === 'ticker' && (
            <span className="flex items-center gap-1">
              <input
                type="text"
                value={tickerInput}
                onChange={e => setTickerInput(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter') loadFeed(); }}
                placeholder={t('me_ticker_ph')}
                className="px-2 py-1 border border-border rounded text-xs font-mono w-32"
              />
              <button
                onClick={loadFeed}
                className="px-2 py-1 rounded-md bg-brand text-white text-xs font-semibold hover:bg-brand-dark"
              >
                {t('me_search')}
              </button>
            </span>
          )}
        </div>
      </div>

      {/* Provider status */}
      {feed && (
        <div className={CARD + ' !py-3'}>
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <span className="text-muted">{t('me_provider_status')}:</span>
            {renderProviderStatus(feed.provider_status)}
            <span className="text-muted">·</span>
            <span className="text-muted">
              {t('me_counts_earnings')}: <b>{feed.counts?.earnings ?? 0}</b>
            </span>
            <span className="text-muted">
              {t('me_counts_news')}: <b>{feed.counts?.news ?? 0}</b>
            </span>
            <span className="text-muted">
              {t('me_counts_tickers')}: <b>{feed.counts?.tickers ?? 0}</b>
            </span>
          </div>
          {feed.any_section_partial && (
            <p className="text-[11px] text-amber-600 dark:text-amber-400 mt-2 italic">
              {t('me_partial_warning')}
            </p>
          )}
          {/* P4-content + multi-provider diagnostics row */}
          {feed.diagnostics && (
            <div className="text-[10px] text-muted mt-2 space-y-0.5 font-mono">
              <p>
                <b>Earnings</b> raw/parsed: {feed.diagnostics.earnings_raw_item_count}/{feed.diagnostics.earnings_parsed_item_count}
                {feed.diagnostics.earnings_skipped_count > 0 &&
                  <> · skipped {feed.diagnostics.earnings_skipped_count}</>}
              </p>
              {feed.diagnostics.news_providers ? (
                <>
                  <p>
                    <b>News (merged)</b>
                    {' raw='}
                    {(feed.diagnostics.news_providers.fmp.raw_count ?? 0)
                      + (feed.diagnostics.news_providers.polygon.raw_count ?? 0)}
                    {' parsed='}{feed.diagnostics.news_providers.merged.pre_dedup_count}
                    {' deduped='}{feed.diagnostics.news_providers.merged.deduped_count}
                    {' · dropped dupes '}
                    {feed.diagnostics.news_providers.merged.dropped_duplicates}
                    {feed.diagnostics.news_ticker_count > 0 &&
                      <> · {feed.diagnostics.news_ticker_count} tickers polled</>}
                  </p>
                  <p>
                    &nbsp;&nbsp;FMP: <b>{feed.diagnostics.news_providers.fmp.status}</b>
                    {' raw='}{feed.diagnostics.news_providers.fmp.raw_count}
                    {' parsed='}{feed.diagnostics.news_providers.fmp.parsed_count}
                  </p>
                  <p>
                    &nbsp;&nbsp;Massive: <b>{feed.diagnostics.news_providers.polygon.status}</b>
                    {' raw='}{feed.diagnostics.news_providers.polygon.raw_count}
                    {' parsed='}{feed.diagnostics.news_providers.polygon.parsed_count}
                  </p>
                </>
              ) : (
                <p>
                  <b>News</b> raw/parsed: {feed.diagnostics.news_raw_item_count}/{feed.diagnostics.news_parsed_item_count}
                  {feed.diagnostics.news_ticker_count > 0 &&
                    <> · {feed.diagnostics.news_ticker_count} tickers polled</>}
                </p>
              )}
              {feed.provider_notes?.fmp_earnings && (
                <p className="italic text-amber-600 dark:text-amber-400">
                  earnings note: {feed.provider_notes.fmp_earnings}
                </p>
              )}
              {feed.provider_notes?.fmp_news && (
                <p className="italic text-amber-600 dark:text-amber-400">
                  fmp news note: {feed.provider_notes.fmp_news}
                </p>
              )}
              {feed.provider_notes?.massive_news && (
                <p className="italic text-amber-600 dark:text-amber-400">
                  massive news note: {feed.provider_notes.massive_news}
                </p>
              )}
            </div>
          )}
        </div>
      )}

      {/* Loading / error */}
      {loading && !feed && (
        <div className={CARD + ' text-center'}>
          <RefreshCw className="w-5 h-5 text-brand animate-spin mx-auto mb-1" />
          <p className="text-xs text-muted">{t('me_loading')}</p>
        </div>
      )}
      {error && !loading && (
        <div className={CARD + ' border-red-300 dark:border-red-700'}>
          <div className="flex items-center gap-2 text-red-600 dark:text-red-400">
            <AlertCircle className="w-4 h-4" />
            <span className="text-sm">{error}</span>
          </div>
        </div>
      )}

      {/* Overnight Market Brief preview — manual/on-demand only, no scheduler */}
      <div className={CARD + ' !py-4'}>
        <button
          onClick={toggleBrief}
          className="w-full flex items-center justify-between text-left"
        >
          <div className="flex items-center gap-2">
            <Moon className="w-4 h-4 text-brand" />
            <h3 className="text-sm font-semibold text-heading">{t('mb_title')}</h3>
            <span className={`${BADGE_BASE} bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300`}>
              {t('mb_preview_chip')}
            </span>
          </div>
          {briefOpen
            ? <ChevronDown className="w-4 h-4 text-muted" />
            : <ChevronRight className="w-4 h-4 text-muted" />}
        </button>
        {briefOpen && (
          <div className="mt-3 space-y-3">
            <p className="text-[11px] text-muted italic">
              {t('mb_disclaimer')}
            </p>
            <div className="flex items-center flex-wrap gap-2">
              <button
                onClick={loadBrief}
                disabled={briefLoading}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-brand/40 text-xs font-semibold text-brand hover:bg-brand-light transition-colors disabled:opacity-50"
              >
                <RefreshCw className={`w-3 h-3 ${briefLoading ? 'animate-spin' : ''}`} />
                {briefLoading ? t('me_loading') : t('mb_refresh')}
              </button>
              <button
                onClick={loadLatestBrief}
                disabled={briefLoading}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-border text-xs font-semibold text-muted hover:bg-bg-subtle transition-colors disabled:opacity-50"
                title={t('mb_show_latest_saved_hint')}
              >
                {t('mb_show_latest_saved')}
              </button>
              <button
                onClick={() => {
                  if (briefHistory == null) loadBriefHistory();
                  else setBriefHistory(null);
                }}
                disabled={briefHistoryLoading}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-border text-xs font-semibold text-muted hover:bg-bg-subtle transition-colors disabled:opacity-50"
              >
                {briefHistory == null ? t('mb_show_history') : t('mb_hide_history')}
              </button>
              {brief?.generated_at && (
                <span className="text-[10px] text-muted">
                  {t('mb_generated_at')}: {brief.generated_at.slice(0, 19).replace('T', ' ')}
                  {brief?.persisted && (
                    <span className="ml-1 px-1 py-0.5 rounded bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300">
                      {t('mb_from_history')}
                    </span>
                  )}
                </span>
              )}
            </div>

            {/* History list — collapsible */}
            {briefHistory != null && (
              <div className="rounded-md border border-border bg-bg-subtle p-2 space-y-1">
                <p className="text-[10px] uppercase tracking-wider text-muted font-semibold">
                  {t('mb_history_title')}
                </p>
                {briefHistoryLoading && (
                  <p className="text-xs text-muted">{t('me_loading')}</p>
                )}
                {!briefHistoryLoading && briefHistory.length === 0 && (
                  <p className="text-xs text-muted italic">
                    {t('mb_history_empty')}
                  </p>
                )}
                {!briefHistoryLoading && briefHistory.map((h) => (
                  <button
                    key={h.run_id}
                    onClick={() => loadBriefById(h.run_id)}
                    className="w-full text-left text-[11px] py-1 px-2 rounded hover:bg-brand-light transition-colors flex items-center justify-between gap-2"
                  >
                    <span className="font-mono">
                      {h.generated_at
                        ? h.generated_at.slice(0, 19).replace('T', ' ')
                        : h.run_id.slice(0, 8)}
                    </span>
                    <span className="text-muted">
                      {h.source} · {h.ticker_count} tickers
                      {h.news_section_state && (
                        <> · news: {h.news_section_state}</>
                      )}
                    </span>
                  </button>
                ))}
              </div>
            )}

            {briefError && (
              <p className="text-xs text-red-500">{briefError}</p>
            )}

            {brief && (
              <div className="space-y-3 text-xs">
                {/* Universe scope row */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-[11px]">
                  <div>
                    <p className="text-muted">{t('mb_scanner_matched')}</p>
                    <p className="font-bold text-heading">{brief.universe_scope?.scanner_matched ?? 0}</p>
                  </div>
                  <div>
                    <p className="text-muted">{t('mb_mirror_tickers')}</p>
                    <p className="font-bold text-heading">{brief.universe_scope?.mirror_ticker_count ?? 0}</p>
                  </div>
                  <div>
                    <p className="text-muted">{t('mb_news_fanout')}</p>
                    <p className="font-bold text-heading">{brief.universe_scope?.news_fanout_top_n ?? 0}</p>
                  </div>
                  <div>
                    <p className="text-muted">{t('mb_total_candidates')}</p>
                    <p className="font-bold text-heading">{brief.ticker_count ?? 0}</p>
                  </div>
                </div>

                {/* Rate-limited / cached news notice — friendly banner
                    above the raw diagnostics block. Shown only when the
                    news section state indicates a rate-limit or cache
                    fallback condition. */}
                {brief.provider_diagnostics?.news?.section_state &&
                 ['rate_limited_cached', 'rate_limited_no_cache', 'cached'].includes(
                   brief.provider_diagnostics.news.section_state) && (
                  <div className={`text-xs rounded-md px-3 py-2 border ${
                    brief.provider_diagnostics.news.section_state === 'rate_limited_no_cache'
                      ? 'bg-amber-50 border-amber-200 text-amber-900 dark:bg-amber-900/20 dark:border-amber-700/40 dark:text-amber-200'
                      : 'bg-blue-50 border-blue-200 text-blue-900 dark:bg-blue-900/20 dark:border-blue-700/40 dark:text-blue-200'
                  }`}>
                    {brief.provider_diagnostics.news.section_state === 'rate_limited_cached' && (
                      <>
                        <b>{t('mb_rate_limited_cached')}</b>{' '}
                        {brief.provider_diagnostics.news.cached_news_age_seconds != null ? (
                          <>
                            {t('mb_using_cached_news_age_prefix')}
                            {' '}{Math.max(0, Math.round(brief.provider_diagnostics.news.cached_news_age_seconds / 60))}{' '}
                            {t('mb_using_cached_news_age_suffix')}
                          </>
                        ) : t('mb_using_cached_news')}
                      </>
                    )}
                    {brief.provider_diagnostics.news.section_state === 'rate_limited_no_cache' && (
                      <>
                        <b>{t('mb_rate_limited_no_cache')}</b>{' '}
                        {t('mb_rate_limited_no_cache_detail_prefix')}
                        {' '}{brief.provider_diagnostics.news.skipped_due_to_rate_limit?.length ?? 0}{' '}
                        {t('mb_rate_limited_no_cache_detail_suffix')}
                      </>
                    )}
                    {brief.provider_diagnostics.news.section_state === 'cached' && (
                      <>
                        <b>{t('mb_cached_news')}</b>{' '}
                        {brief.provider_diagnostics.news.cached_news_age_seconds != null ? (
                          <>
                            {t('mb_using_cached_news_age_prefix')}
                            {' '}{Math.max(0, Math.round(brief.provider_diagnostics.news.cached_news_age_seconds / 60))}{' '}
                            {t('mb_using_cached_news_age_suffix')}
                          </>
                        ) : t('mb_using_cached_news')}
                      </>
                    )}
                    <span className="block text-[10px] opacity-80 mt-0.5">
                      {t('mb_research_only_disclaimer_short')}
                    </span>
                  </div>
                )}

                {/* Provider diagnostics */}
                {brief.provider_diagnostics && (
                  <div className="font-mono text-[10px] text-muted space-y-0.5 border-t border-border/40 pt-2">
                    <p>
                      <b>News (merged):</b>
                      {' '}{brief.provider_diagnostics.news?.section_state
                        || brief.provider_diagnostics.news?.merged?.status}
                      {' · pre_dedup '}{brief.provider_diagnostics.news?.merged?.pre_dedup_count ?? 0}
                      {' · deduped '}{brief.provider_diagnostics.news?.merged?.deduped_count ?? 0}
                      {' · dropped '}{brief.provider_diagnostics.news?.merged?.dropped_duplicates ?? 0}
                    </p>
                    <p>
                      &nbsp;&nbsp;FMP {brief.provider_diagnostics.news?.fmp?.status} ·
                      {' '}Massive {brief.provider_diagnostics.news?.polygon?.status}
                      {brief.provider_diagnostics.news?.used_cached_news_count > 0 && (
                        <> · cached items {brief.provider_diagnostics.news.used_cached_news_count}</>
                      )}
                    </p>
                    <p>
                      &nbsp;&nbsp;fan-out effective {brief.provider_diagnostics.news?.effective_news_top_n ?? 0}
                      {brief.provider_diagnostics.news?.requested_news_top_n != null
                       && brief.provider_diagnostics.news?.requested_news_top_n
                          !== brief.provider_diagnostics.news?.effective_news_top_n && (
                        <> (requested {brief.provider_diagnostics.news.requested_news_top_n})</>
                      )}
                      {brief.provider_diagnostics.news?.skipped_due_to_rate_limit?.length > 0 && (
                        <> · skipped (rate-limited) {brief.provider_diagnostics.news.skipped_due_to_rate_limit.length}</>
                      )}
                    </p>
                    <p>
                      <b>Earnings:</b> {brief.provider_diagnostics.earnings_status}
                    </p>
                    <p>
                      <b>Scanner:</b> matched {brief.provider_diagnostics.scanner?.matched ?? 0}/{brief.provider_diagnostics.scanner?.scanned ?? 0}
                    </p>
                  </div>
                )}

                {/* Top news-linked candidates */}
                {brief.top_news_linked_candidates?.length > 0 && (
                  <div>
                    <p className="text-[11px] font-semibold text-muted uppercase tracking-wider mb-1">
                      {t('mb_top_news_linked')} ({brief.top_news_linked_candidates.length})
                    </p>
                    <div className="space-y-1.5">
                      {brief.top_news_linked_candidates.slice(0, 5).map(c => (
                        <BriefCandidate key={c.ticker} c={c} t={t} onOpen={openTickerDetail} />
                      ))}
                    </div>
                  </div>
                )}

                {/* Top scanner / price-anomaly candidates */}
                {brief.top_price_anomaly_candidates?.length > 0 && (
                  <div>
                    <p className="text-[11px] font-semibold text-muted uppercase tracking-wider mb-1">
                      {t('mb_top_scanner')} ({brief.top_price_anomaly_candidates.length})
                    </p>
                    <div className="space-y-1.5">
                      {brief.top_price_anomaly_candidates.slice(0, 5).map(c => (
                        <BriefCandidate key={c.ticker} c={c} t={t} onOpen={openTickerDetail} />
                      ))}
                    </div>
                  </div>
                )}

                {/* Earnings nearby */}
                {brief.earnings_nearby_candidates?.length > 0 && (
                  <div>
                    <p className="text-[11px] font-semibold text-muted uppercase tracking-wider mb-1">
                      {t('mb_earnings_nearby')} ({brief.earnings_nearby_candidates.length})
                    </p>
                    <div className="space-y-1.5">
                      {brief.earnings_nearby_candidates.slice(0, 5).map(c => (
                        <BriefCandidate key={c.ticker} c={c} t={t} onOpen={openTickerDetail} />
                      ))}
                    </div>
                  </div>
                )}

                {/* Unmapped */}
                {brief.unmapped_candidates?.length > 0 && (
                  <div>
                    <p className="text-[11px] font-semibold text-muted uppercase tracking-wider mb-1">
                      {t('mb_unmapped')} ({brief.unmapped_candidates.length})
                    </p>
                    <div className="flex flex-wrap gap-1">
                      {brief.unmapped_candidates.slice(0, 20).map(c => (
                        <button
                          key={c.ticker}
                          onClick={() => openTickerDetail(c.ticker)}
                          className={`${BADGE_BASE} ${c.mapping_status === 'newly_resolvable'
                            ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300'
                            : 'bg-gray-200 text-gray-700 dark:bg-gray-700 dark:text-gray-300'}`}
                        >
                          {c.ticker}{' '}
                          <span className="opacity-60">({c.mapping_status})</span>
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {/* Categories summary */}
                {brief.categories_summary?.length > 0 && (
                  <div>
                    <p className="text-[11px] font-semibold text-muted uppercase tracking-wider mb-1">
                      {t('mb_categories')}
                    </p>
                    <div className="flex flex-wrap gap-1.5">
                      {brief.categories_summary.slice(0, 12).map(c => (
                        <span key={c.broad}
                          className="px-2 py-0.5 rounded text-[10px] font-semibold bg-blue-50 text-blue-700 dark:bg-blue-900/20 dark:text-blue-300">
                          {c.broad}: {c.ticker_count}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Empty state if everything is empty */}
                {brief.ticker_count === 0 && (
                  <p className="text-xs text-muted py-3 text-center italic">
                    {t('mb_empty_state')}
                  </p>
                )}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Earnings */}
      <div className={CARD}>
        <h3 className="text-sm font-semibold text-heading mb-3 flex items-center gap-2">
          <Calendar className="w-4 h-4 text-brand" /> {t('me_earnings_title')}
        </h3>
        {feed && feed.earnings && feed.earnings.length > 0 ? (
          <div className="divide-y divide-border/40">
            {feed.earnings.map((e, i) => (
              <div
                key={`${e.ticker}-${e.report_date}-${i}`}
                className="py-2 flex items-center justify-between gap-3 cursor-pointer hover:bg-hover-row/30 -mx-2 px-2 rounded"
                onClick={() => openTickerDetail(e.ticker)}
              >
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-1.5 flex-wrap">
                    <span className="text-xs font-bold text-heading">{e.ticker}</span>
                    {e.is_in_mirror && renderTags(e.source_tags)}
                    {e.mapping_status === 'unmapped' && (
                      <span className={`${BADGE_BASE} bg-gray-200 text-gray-700 dark:bg-gray-700 dark:text-gray-300`}>
                        {t('me_tag_unmapped')}
                      </span>
                    )}
                  </div>
                  <p className="text-[10px] text-muted truncate">
                    {e.company_name || '—'}
                  </p>
                </div>
                <div className="text-right shrink-0">
                  <p className="text-xs font-semibold text-heading">{e.report_date}</p>
                  <p className="text-[10px] text-muted">{e.time}</p>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="py-3 text-center">
            <p className="text-xs text-muted">{t('me_no_earnings')}</p>
            {feed?.provider_status?.fmp_earnings === 'unavailable' && (
              <p className="text-[10px] text-amber-600 dark:text-amber-400 italic mt-1">
                {t('me_earnings_plan_blocked')}
              </p>
            )}
            {feed?.provider_status?.fmp_earnings === 'timeout' && (
              <p className="text-[10px] text-amber-600 dark:text-amber-400 italic mt-1">
                {t('me_earnings_timeout_hint')}
              </p>
            )}
          </div>
        )}
      </div>

      {/* News */}
      <div className={CARD}>
        <h3 className="text-sm font-semibold text-heading mb-3 flex items-center gap-2">
          <Newspaper className="w-4 h-4 text-brand" /> {t('me_news_title')}
        </h3>
        {/* External-headline disclaimer — headlines below come straight
            from upstream news providers (FMP / Polygon-Massive). They
            may include words like "Buy", "Prediction", "Forecast".
            Those reflect the publisher's editorial choices, not a
            platform recommendation. */}
        <p className="text-[10px] text-amber-600 dark:text-amber-400 italic mb-2 border-l-2 border-amber-300 dark:border-amber-700 pl-2">
          {t('me_external_headline_disclaimer')}
        </p>
        {scope === 'all_supported' ? (
          <p className="text-xs text-muted py-3 text-center italic">
            {t('me_news_omitted_all')}
          </p>
        ) : feed && feed.news && feed.news.length > 0 ? (
          <div className="divide-y divide-border/40">
            {feed.news.slice(0, 50).map((n, i) => (
              <div
                key={`${n.ticker}-${n.published_at}-${i}`}
                className="py-2 cursor-pointer hover:bg-hover-row/30 -mx-2 px-2 rounded"
                onClick={() => openTickerDetail(n.ticker)}
              >
                <div className="flex items-center gap-1.5 flex-wrap">
                  <span className="text-xs font-bold text-heading">{n.ticker}</span>
                  {n.is_in_mirror && renderTags(n.source_tags)}
                  <span className="text-[10px] text-muted">{n.published_at?.slice(0, 16) || ''}</span>
                  {n.url && (
                    <a
                      href={n.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      onClick={ev => ev.stopPropagation()}
                      className="ml-auto text-brand hover:text-brand-dark"
                      title="Open in new tab"
                    >
                      <ExternalLink className="w-3 h-3" />
                    </a>
                  )}
                </div>
                <p className="text-xs text-heading mt-0.5 line-clamp-2">{n.title}</p>
                {n.source_name && (
                  <p className="text-[10px] text-muted mt-0.5">{n.source_name}</p>
                )}
              </div>
            ))}
          </div>
        ) : (
          <div className="py-3 text-center">
            <p className="text-xs text-muted">{t('me_no_news')}</p>
            {feed?.provider_status?.merged_news === 'unavailable' && (
              <p className="text-[10px] text-amber-600 dark:text-amber-400 italic mt-1">
                {t('me_news_all_unavailable')}
              </p>
            )}
            {feed?.provider_status?.merged_news === 'rate_limited' && (
              <p className="text-[10px] text-amber-600 dark:text-amber-400 italic mt-1">
                {t('me_news_rate_limited')}
              </p>
            )}
            {feed?.provider_status?.merged_news === 'timeout' && (
              <p className="text-[10px] text-amber-600 dark:text-amber-400 italic mt-1">
                {t('me_news_timeout_hint')}
              </p>
            )}
            {feed?.provider_status?.merged_news === 'empty' && scope !== 'all_supported' && (
              <p className="text-[10px] text-muted italic mt-1">
                {t('me_news_all_empty')}
              </p>
            )}
            {/* Per-provider hints — show if FMP is the only blocker */}
            {(feed?.provider_status?.fmp_news === 'unavailable'
              || feed?.provider_status?.fmp_news === 'rate_limited')
              && feed?.provider_status?.massive_news === 'ok' && (
              <p className="text-[10px] text-muted italic mt-1">
                {feed?.provider_status?.fmp_news === 'rate_limited'
                  ? t('me_fmp_rate_limited')
                  : t('me_fmp_only_blocked')}
              </p>
            )}
          </div>
        )}
      </div>

      {/* Ticker detail drawer */}
      {selectedTicker && (
        <div
          className="fixed inset-0 z-40 bg-black/40 flex justify-end"
          onClick={closeDetail}
        >
          <div
            className="bg-card w-full sm:w-[480px] h-full overflow-y-auto p-5"
            onClick={ev => ev.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-base font-bold text-heading">{selectedTicker}</h3>
              <button onClick={closeDetail} className="text-muted hover:text-heading text-sm">×</button>
            </div>
            {tickerDetail?.loading ? (
              <p className="text-xs text-muted">{t('me_loading')}</p>
            ) : tickerDetail?.error ? (
              <p className="text-xs text-red-500">{tickerDetail.error}</p>
            ) : tickerDetail ? (
              <div className="space-y-3 text-xs">
                <div>
                  <p className="text-[10px] text-muted uppercase">{t('me_detail_company')}</p>
                  <p className="font-semibold text-heading">{tickerDetail.company_name || '—'}</p>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <p className="text-[10px] text-muted uppercase">{t('me_detail_exchange')}</p>
                    <p className="font-semibold text-heading">{tickerDetail.exchange_primary || '—'}</p>
                  </div>
                  <div>
                    <p className="text-[10px] text-muted uppercase">{t('me_detail_currency')}</p>
                    <p className="font-semibold text-heading">{tickerDetail.currency || '—'}</p>
                  </div>
                </div>
                <div>
                  <p className="text-[10px] text-muted uppercase">{t('me_detail_mapping')}</p>
                  <span className={`${BADGE_BASE} ${tickerDetail.mapping_status === 'mapped' ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300' : 'bg-gray-200 text-gray-700 dark:bg-gray-700 dark:text-gray-300'}`}>
                    {tickerDetail.mapping_status}
                  </span>
                  {tickerDetail.mapping_status === 'unmapped' && (
                    <p className="text-[10px] text-muted italic mt-1">{t('me_unmapped_explanation')}</p>
                  )}
                </div>
                {tickerDetail.upcoming_earnings?.length > 0 && (
                  <div>
                    <p className="text-[10px] text-muted uppercase mb-1">{t('me_earnings_title')}</p>
                    {tickerDetail.upcoming_earnings.slice(0, 3).map((e, i) => (
                      <p key={i} className="text-xs text-heading">{e.report_date} · {e.time}</p>
                    ))}
                  </div>
                )}
                {tickerDetail.recent_news?.length > 0 && (
                  <div>
                    <p className="text-[10px] text-muted uppercase mb-1">{t('me_news_title')}</p>
                    {/* External headlines (FMP/Polygon-Massive) —
                        publisher language, not platform guidance. */}
                    <p className="text-[10px] text-amber-600 dark:text-amber-400 italic mb-1">
                      {t('me_external_headline_disclaimer')}
                    </p>
                    {tickerDetail.recent_news.slice(0, 5).map((n, i) => (
                      <a
                        key={i}
                        href={n.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="block text-xs text-heading mb-1 hover:underline"
                      >
                        {n.title}
                      </a>
                    ))}
                  </div>
                )}
                <p className="text-[10px] text-muted italic mt-3">{tickerDetail.disclaimer}</p>
              </div>
            ) : null}
          </div>
        </div>
      )}
    </div>
  );
}
