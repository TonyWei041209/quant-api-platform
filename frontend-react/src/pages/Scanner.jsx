import { useState, useEffect, useCallback, useMemo } from 'react';
import { apiFetch } from '../hooks/useApi';
import { useI18n } from '../hooks/useI18n';
import {
  Radar, RefreshCw, Filter, AlertTriangle, ChevronRight,
  TrendingUp, FlaskConical, History, Eye, Info,
  Layers, Globe, Bookmark, Database, X, Plus,
} from 'lucide-react';

// P1-UI mode selector — legacy 36-ticker is the default to preserve
// existing behavior. The other four modes hit the deployed taxonomy
// routes and render preview lists. They are research-only; full
// all-market scanning is intentionally job_required and not executed
// from this UI.
const SCAN_MODES = [
  { id: 'legacy',       icon: Radar,    labelKey: 'scanner_mode_legacy' },
  { id: 'mirror',       icon: Bookmark, labelKey: 'scanner_mode_mirror' },
  { id: 'category',     icon: Layers,   labelKey: 'scanner_mode_category' },
  { id: 'subcategory',  icon: Layers,   labelKey: 'scanner_mode_subcategory' },
  { id: 'all_market',   icon: Globe,    labelKey: 'scanner_mode_all_market' },
];

const CARD = 'bg-card rounded-xl border border-border shadow-card p-6';

const STRENGTH_STYLE = {
  high:   'bg-red-50 dark:bg-red-900/30 text-red-600 dark:text-red-300 border-red-200 dark:border-red-800',
  medium: 'bg-amber-50 dark:bg-amber-900/30 text-amber-600 dark:text-amber-300 border-amber-200 dark:border-amber-800',
  low:    'bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-300 border-blue-200 dark:border-blue-800',
};

const SCAN_TYPE_LABELS = {
  strong_momentum:     'scan_strong_momentum',
  extreme_mover:       'scan_extreme_mover',
  breakout_candidate:  'scan_breakout',
  high_volatility:     'scan_high_vol',
  needs_research:      'scan_needs_research',
};

const RISK_LABELS = {
  extended_move:       'risk_extended',
  near_52w_high:       'risk_near_52w_high',
  no_recent_research:  'risk_no_research',
  insufficient_data:   'risk_insufficient',
  high_volatility:     'risk_high_vol',
  high_relative_volume:'risk_high_volume',
};

const NEXT_STEP_LABELS = {
  research:           'next_research',
  validate:           'next_validate',
  add_to_watchlist:   'next_add_watchlist',
  run_backtest:       'next_backtest',
  monitor:            'next_monitor',
};

function pctClass(v) {
  if (v == null) return 'text-muted';
  return v >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-500 dark:text-red-400';
}
function fmtPct(v, digits = 1) {
  if (v == null) return '—';
  return `${v >= 0 ? '+' : ''}${v.toFixed(digits)}%`;
}

export default function Scanner({ onNavigate }) {
  const { t } = useI18n();
  const [items, setItems] = useState([]);
  const [meta, setMeta] = useState({ scanned: 0, matched: 0, as_of: null });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const [universe, setUniverse] = useState('all');
  const [sortBy, setSortBy] = useState('signal_strength');
  const [includeNeedsResearch, setIncludeNeedsResearch] = useState(false);

  // P1-UI: mode + taxonomy state. Loaded lazily on first non-legacy mode.
  const [mode, setMode] = useState('legacy');
  const [taxCategories, setTaxCategories] = useState(null);   // {broad_categories, subcategories}
  const [provCaps, setProvCaps] = useState(null);
  const [selectedBroad, setSelectedBroad] = useState([]);
  const [selectedSubs, setSelectedSubs] = useState([]);
  const [taxItems, setTaxItems] = useState([]);                // [{display_ticker, taxonomy_tags}]
  const [taxLoading, setTaxLoading] = useState(false);
  const [taxError, setTaxError] = useState(null);
  const [taxJobRequired, setTaxJobRequired] = useState(false);
  const [taxTotalKnown, setTaxTotalKnown] = useState(0);
  const [mirrorPreview, setMirrorPreview] = useState(null);    // mirror watchlist response

  const runScan = useCallback(async () => {
    setLoading(true);
    setError(null);
    const params = new URLSearchParams({
      universe,
      sort_by: sortBy,
      limit: '50',
      include_needs_research: includeNeedsResearch ? 'true' : 'false',
    });
    try {
      const res = await apiFetch(`/scanner/stock?${params.toString()}`);
      setItems(res?.items || []);
      setMeta({
        scanned: res?.scanned ?? 0,
        matched: res?.matched ?? 0,
        as_of: res?.as_of ?? null,
      });
    } catch (e) {
      setError(e?.message || 'scanner_failed');
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, [universe, sortBy, includeNeedsResearch]);

  useEffect(() => { if (mode === 'legacy') runScan(); }, [runScan, mode]);

  // P1-UI: load taxonomy categories + provider capabilities once when the
  // user first enters any non-legacy mode. Cached in state thereafter.
  useEffect(() => {
    if (mode === 'legacy') return;
    if (!taxCategories) {
      apiFetch('/scanner/taxonomy/categories')
        .then(setTaxCategories)
        .catch(() => setTaxCategories({ broad_categories: [], subcategories: [] }));
    }
    if (!provCaps) {
      apiFetch('/scanner/provider-capabilities')
        .then(setProvCaps)
        .catch(() => setProvCaps(null));
    }
  }, [mode, taxCategories, provCaps]);

  // P1-UI: load taxonomy preview / mirror / all-market preview on mode change.
  const loadTaxonomyForMode = useCallback(async () => {
    setTaxLoading(true);
    setTaxError(null);
    try {
      if (mode === 'mirror') {
        const res = await apiFetch('/watchlists/trading212-mirror');
        setMirrorPreview(res);
        setTaxItems([]);
        setTaxJobRequired(false);
        setTaxTotalKnown(0);
      } else if (mode === 'category' || mode === 'subcategory') {
        const params = new URLSearchParams();
        if (mode === 'category' && selectedBroad.length === 1) {
          params.set('broad', selectedBroad[0]);
        }
        if (mode === 'subcategory' && selectedSubs.length === 1) {
          params.set('sub', selectedSubs[0]);
        }
        const path = '/scanner/taxonomy/universe-preview' +
          (params.toString() ? `?${params.toString()}` : '');
        const res = await apiFetch(path);
        setTaxItems(res?.items || []);
        setTaxJobRequired(false);
        setTaxTotalKnown(res?.count || 0);
      } else if (mode === 'all_market') {
        const params = new URLSearchParams({ limit: '100' });
        if (selectedBroad.length === 1) params.set('broad', selectedBroad[0]);
        if (selectedSubs.length === 1) params.set('sub', selectedSubs[0]);
        const res = await apiFetch(
          `/scanner/all-market/preview?${params.toString()}`
        );
        setTaxItems(res?.items || []);
        setTaxJobRequired(!!res?.job_required);
        setTaxTotalKnown(res?.total_known_in_taxonomy || 0);
      }
    } catch (e) {
      setTaxError(e?.message || 'taxonomy_failed');
      setTaxItems([]);
    } finally {
      setTaxLoading(false);
    }
  }, [mode, selectedBroad, selectedSubs]);

  useEffect(() => {
    if (mode === 'legacy') return;
    loadTaxonomyForMode();
  }, [mode, loadTaxonomyForMode]);

  const toggleBroad = (cat) => {
    setSelectedBroad(prev => prev.includes(cat) ? prev.filter(x => x !== cat) : [...prev, cat]);
  };
  const toggleSub = (sub) => {
    setSelectedSubs(prev => prev.includes(sub) ? prev.filter(x => x !== sub) : [...prev, sub]);
  };

  // Filter the taxonomy items client-side when the user has selected
  // multiple broad / subcategory tags (the preview endpoint accepts only
  // one of each via query string; multiselect refines further).
  const filteredTaxItems = useMemo(() => {
    if (!taxItems.length) return [];
    if (!selectedBroad.length && !selectedSubs.length) return taxItems;
    return taxItems.filter(it => {
      const tags = it.taxonomy_tags || {};
      const broad = tags.broad;
      const subs = new Set(tags.subs || []);
      if (selectedBroad.length && !selectedBroad.includes(broad)) return false;
      if (selectedSubs.length && !selectedSubs.some(s => subs.has(s))) return false;
      return true;
    });
  }, [taxItems, selectedBroad, selectedSubs]);

  const handleResearch = (iid) => {
    try { sessionStorage.setItem('research_instrument', iid); } catch {}
    onNavigate?.('research');
  };

  const handleBacktest = (iid, ticker) => {
    try {
      sessionStorage.setItem('backtest_context', JSON.stringify({
        source: 'scanner', instrument_id: iid, ticker,
      }));
    } catch {}
    onNavigate?.('backtest');
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h2 className="text-2xl font-bold text-heading flex items-center gap-2">
            <Radar className="w-6 h-6 text-brand" />
            {t('scanner_title')}
          </h2>
          <p className="text-sm text-muted mt-1">{t('scanner_subtitle')}</p>
        </div>
        <button
          onClick={() => mode === 'legacy' ? runScan() : loadTaxonomyForMode()}
          disabled={loading || taxLoading}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-brand text-white text-sm font-semibold hover:bg-brand-dark disabled:opacity-50 transition-colors"
        >
          <RefreshCw className={`w-4 h-4 ${(loading || taxLoading) ? 'animate-spin' : ''}`} />
          {(loading || taxLoading) ? t('loading') : t('scanner_rescan')}
        </button>
      </div>

      {/* Research-only banner — make platform stance crystal clear */}
      <div className="rounded-lg border border-amber-200 dark:border-amber-800 bg-amber-50/60 dark:bg-amber-900/20 px-4 py-3 flex gap-3">
        <Info className="w-4 h-4 text-amber-600 dark:text-amber-400 mt-0.5 shrink-0" />
        <p className="text-xs text-amber-700 dark:text-amber-300 leading-relaxed">
          {t('scanner_research_only_banner')}
        </p>
      </div>

      {/* P1-UI: scanner mode selector */}
      <div className={CARD + ' !py-4'}>
        <div className="flex items-center gap-2 mb-3">
          <Filter className="w-4 h-4 text-muted" />
          <span className="text-xs font-semibold text-muted uppercase tracking-wider">
            {t('scanner_mode_label')}
          </span>
        </div>
        <div className="flex flex-wrap gap-2">
          {SCAN_MODES.map(m => {
            const Icon = m.icon;
            const active = mode === m.id;
            return (
              <button
                key={m.id}
                onClick={() => setMode(m.id)}
                className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-semibold transition-colors ${
                  active
                    ? 'bg-brand text-white'
                    : 'border border-border text-muted hover:bg-surface'
                }`}
              >
                <Icon className="w-3.5 h-3.5" /> {t(m.labelKey)}
              </button>
            );
          })}
        </div>
        {/* Provider capability panel */}
        {mode !== 'legacy' && provCaps && (
          <div className="mt-3 pt-3 border-t border-border/40 flex flex-wrap items-center gap-2 text-[11px] text-muted">
            <Database className="w-3 h-3" />
            <span>{t('scanner_provider_caps')}:</span>
            <span className={`px-1.5 py-0.5 rounded ${provCaps.fmp?.configured ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300' : 'bg-gray-200 text-gray-700'}`}>
              FMP {provCaps.fmp?.configured ? 'on' : 'off'}
            </span>
            <span className={`px-1.5 py-0.5 rounded ${provCaps.massive_polygon?.configured ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300' : 'bg-gray-200 text-gray-700'}`}>
              Polygon {provCaps.massive_polygon?.configured ? 'on' : 'off'}
            </span>
            <span className={`px-1.5 py-0.5 rounded ${provCaps.all_market_scan_ready ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300' : 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300'}`}>
              {t('scanner_all_market_ready')}: {provCaps.all_market_scan_ready ? 'yes' : 'no'}
            </span>
          </div>
        )}
      </div>

      {/* P1-UI: category/subcategory multiselect when relevant */}
      {(mode === 'category' || mode === 'subcategory' || mode === 'all_market') && taxCategories && (
        <div className={CARD + ' !py-4'}>
          {(mode === 'category' || mode === 'all_market') && (
            <div className="mb-3">
              <p className="text-[11px] font-semibold text-muted uppercase tracking-wider mb-2">
                {t('scanner_broad_categories')}
              </p>
              <div className="flex flex-wrap gap-1.5">
                {(taxCategories.broad_categories || []).map(cat => {
                  const active = selectedBroad.includes(cat);
                  return (
                    <button
                      key={cat}
                      onClick={() => toggleBroad(cat)}
                      className={`px-2 py-1 rounded text-[10px] font-semibold transition-colors ${
                        active ? 'bg-brand text-white' : 'border border-border text-muted hover:bg-surface'
                      }`}
                    >
                      {cat}
                    </button>
                  );
                })}
              </div>
            </div>
          )}
          {(mode === 'subcategory' || mode === 'all_market') && (
            <div>
              <p className="text-[11px] font-semibold text-muted uppercase tracking-wider mb-2">
                {t('scanner_subcategories')}
              </p>
              <div className="flex flex-wrap gap-1.5">
                {(taxCategories.subcategories || []).map(sub => {
                  const active = selectedSubs.includes(sub);
                  return (
                    <button
                      key={sub}
                      onClick={() => toggleSub(sub)}
                      className={`px-2 py-1 rounded text-[10px] font-semibold transition-colors ${
                        active ? 'bg-brand text-white' : 'border border-border text-muted hover:bg-surface'
                      }`}
                    >
                      {sub}
                    </button>
                  );
                })}
              </div>
            </div>
          )}
          {(selectedBroad.length > 0 || selectedSubs.length > 0) && (
            <button
              onClick={() => { setSelectedBroad([]); setSelectedSubs([]); }}
              className="mt-3 inline-flex items-center gap-1 text-[11px] text-muted hover:text-heading"
            >
              <X className="w-3 h-3" /> {t('scanner_clear_filters')}
            </button>
          )}
        </div>
      )}

      {/* P1-UI: all-market preview disclaimer */}
      {mode === 'all_market' && (
        <div className="rounded-lg border border-blue-200 dark:border-blue-800 bg-blue-50/60 dark:bg-blue-900/20 px-4 py-3 flex gap-3">
          <Info className="w-4 h-4 text-blue-600 dark:text-blue-400 mt-0.5 shrink-0" />
          <p className="text-xs text-blue-700 dark:text-blue-300 leading-relaxed">
            {t('scanner_all_market_disclaimer')}
            {taxJobRequired && <> · <b>{t('scanner_job_required')}</b></>}
          </p>
        </div>
      )}

      {/* P1-UI: non-legacy mode results */}
      {mode !== 'legacy' && (
        <>
          {taxError && (
            <div className="rounded-lg border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/20 px-4 py-3 text-sm text-red-700 dark:text-red-300">
              {taxError}
            </div>
          )}

          {mode === 'mirror' && mirrorPreview && (
            <div className={CARD}>
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-semibold text-heading">{t('scanner_mirror_results')}</h3>
                <span className="text-[11px] text-muted">
                  {mirrorPreview.counts?.total ?? 0} {t('scanner_results_count')}
                </span>
              </div>
              {(mirrorPreview.items || []).length === 0 ? (
                <p className="text-xs text-muted py-3 text-center">{t('scanner_mirror_empty')}</p>
              ) : (
                <div className="divide-y divide-border/40">
                  {mirrorPreview.items.map(it => (
                    <div key={it.display_ticker} className="py-2 flex items-center justify-between gap-3">
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-1.5 flex-wrap">
                          <span className="text-xs font-bold text-heading">{it.display_ticker}</span>
                          {(it.source_tags || []).map(tag => (
                            <span key={tag} className="px-1 py-0.5 rounded text-[9px] font-semibold bg-brand-light text-brand-dark">
                              {tag}
                            </span>
                          ))}
                        </div>
                        <p className="text-[10px] text-muted truncate">{it.company_name || it.broker_ticker || '—'}</p>
                      </div>
                      <div className="flex items-center gap-1.5 shrink-0">
                        {it.instrument_id ? (
                          <button
                            onClick={() => handleResearch(it.instrument_id)}
                            className="px-2 py-1 rounded text-[10px] font-semibold text-brand border border-brand/40 hover:bg-brand-light transition-colors"
                          >
                            {t('scanner_btn_research')}
                          </button>
                        ) : (
                          <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-gray-200 text-gray-700 dark:bg-gray-700 dark:text-gray-300">
                            {t('me_tag_unmapped')}
                          </span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {(mode === 'category' || mode === 'subcategory' || mode === 'all_market') && (
            <div className={CARD}>
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-semibold text-heading">{t('scanner_taxonomy_results')}</h3>
                <span className="text-[11px] text-muted">
                  {filteredTaxItems.length} / {taxTotalKnown || taxItems.length} {t('scanner_results_count')}
                </span>
              </div>
              {filteredTaxItems.length === 0 ? (
                <p className="text-xs text-muted py-3 text-center">{t('scanner_taxonomy_empty')}</p>
              ) : (
                <div className="divide-y divide-border/40">
                  {filteredTaxItems.map(it => (
                    <div key={it.display_ticker} className="py-2 flex items-center justify-between gap-3">
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-1.5 flex-wrap">
                          <span className="text-xs font-bold text-heading">{it.display_ticker}</span>
                          {it.taxonomy_tags?.broad && (
                            <span className="px-1 py-0.5 rounded text-[9px] font-semibold bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300">
                              {it.taxonomy_tags.broad}
                            </span>
                          )}
                          {(it.taxonomy_tags?.subs || []).map(s => (
                            <span key={s} className="px-1 py-0.5 rounded text-[9px] font-semibold bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300">
                              {s}
                            </span>
                          ))}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </>
      )}

      {/* Filters (legacy 36-instrument scanner) — preserved unchanged when mode='legacy' */}
      {mode === 'legacy' && (
        <>
      {/* Filters */}
      <div className={CARD}>
        <div className="flex flex-wrap items-center gap-4">
          <div className="flex items-center gap-2">
            <Filter className="w-4 h-4 text-muted" />
            <span className="text-xs font-semibold text-muted uppercase tracking-wider">{t('scanner_filters')}</span>
          </div>

          <div className="flex items-center gap-2">
            <label className="text-xs text-muted">{t('scanner_universe')}</label>
            <select value={universe} onChange={e => setUniverse(e.target.value)}
              className="text-xs px-2 py-1.5 rounded border border-border bg-card text-heading">
              <option value="all">{t('scanner_universe_all')}</option>
              <option value="watchlist" disabled>{t('scanner_universe_watchlist')}</option>
              <option value="holdings" disabled>{t('scanner_universe_holdings_pending')}</option>
            </select>
          </div>

          <div className="flex items-center gap-2">
            <label className="text-xs text-muted">{t('scanner_sort_by')}</label>
            <select value={sortBy} onChange={e => setSortBy(e.target.value)}
              className="text-xs px-2 py-1.5 rounded border border-border bg-card text-heading">
              <option value="signal_strength">{t('scanner_sort_signal')}</option>
              <option value="change_1d">1D</option>
              <option value="change_5d">5D</option>
              <option value="change_1m">1M</option>
              <option value="week52">52W</option>
            </select>
          </div>

          <label className="flex items-center gap-2 text-xs text-muted cursor-pointer">
            <input type="checkbox" checked={includeNeedsResearch}
              onChange={e => setIncludeNeedsResearch(e.target.checked)}
              className="accent-brand" />
            {t('scanner_include_needs_research')}
          </label>
        </div>

        <div className="mt-4 flex items-center gap-4 text-xs text-muted border-t border-border/40 pt-3">
          <span>{t('scanner_scanned')}: <span className="font-semibold text-heading">{meta.scanned}</span></span>
          <span>{t('scanner_matched')}: <span className="font-semibold text-heading">{meta.matched}</span></span>
          {meta.as_of && (
            <span>{t('scanner_as_of')}: <span className="font-semibold text-heading">{meta.as_of}</span></span>
          )}
          <span className="px-2 py-0.5 rounded bg-surface text-[10px] uppercase tracking-wider">
            data_mode: daily_eod
          </span>
        </div>
      </div>

      {/* Results */}
      {error && (
        <div className="rounded-lg border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/20 px-4 py-3 text-sm text-red-700 dark:text-red-300">
          {error}
        </div>
      )}

      {!loading && items.length === 0 && !error && (
        <div className={CARD + ' text-center py-12'}>
          <Radar className="w-10 h-10 text-muted/40 mx-auto mb-3" />
          <p className="text-sm font-medium text-heading">{t('scanner_no_matches_title')}</p>
          <p className="text-xs text-muted mt-1 max-w-md mx-auto">{t('scanner_no_matches_hint')}</p>
        </div>
      )}

      <div className="space-y-3">
        {items.map(it => (
          <div key={it.instrument_id} className={CARD + ' hover:shadow-md transition-shadow'}>
            {/* Header row */}
            <div className="flex items-start justify-between gap-4 flex-wrap">
              <div className="flex items-center gap-3 min-w-0">
                <span className={`px-2 py-1 rounded text-[10px] font-bold uppercase tracking-wider border ${STRENGTH_STYLE[it.signal_strength] || ''}`}>
                  {t(`scanner_strength_${it.signal_strength}`)}
                </span>
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-base font-bold text-heading">{it.ticker || it.instrument_id?.slice(0,8)}</span>
                    <span className="text-xs text-muted truncate">{it.issuer_name}</span>
                  </div>
                  <div className="flex items-center gap-2 mt-0.5 flex-wrap">
                    {it.scan_types.map(st => (
                      <span key={st} className="px-1.5 py-0.5 rounded text-[9px] font-semibold bg-brand-light text-brand-dark">
                        {t(SCAN_TYPE_LABELS[st]) || st}
                      </span>
                    ))}
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-1.5 shrink-0">
                <button
                  onClick={() => handleResearch(it.instrument_id)}
                  className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded text-[11px] font-semibold text-brand border border-brand/40 hover:bg-brand-light transition-colors"
                  title={t('scanner_btn_research_tip')}
                >
                  <FlaskConical className="w-3 h-3" /> {t('scanner_btn_research')}
                </button>
                <button
                  onClick={() => handleBacktest(it.instrument_id, it.ticker)}
                  className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded text-[11px] font-semibold text-blue-600 border border-blue-300 dark:border-blue-700 hover:bg-blue-50 dark:hover:bg-blue-900/20 transition-colors"
                  title={t('scanner_btn_backtest_tip')}
                >
                  <History className="w-3 h-3" /> {t('scanner_btn_backtest')}
                </button>
                <button
                  disabled
                  className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded text-[11px] font-semibold text-muted border border-border opacity-50 cursor-not-allowed"
                  title={t('scanner_btn_watchlist_pending')}
                >
                  <Eye className="w-3 h-3" /> {t('scanner_btn_watchlist')}
                </button>
              </div>
            </div>

            {/* Metrics strip */}
            <div className="flex items-center gap-4 mt-3 flex-wrap text-xs">
              <span className="text-muted">1D</span>
              <span className={`font-semibold ${pctClass(it.change_1d_pct)}`}>{fmtPct(it.change_1d_pct)}</span>
              <span className="text-muted">5D</span>
              <span className={`font-semibold ${pctClass(it.change_5d_pct)}`}>{fmtPct(it.change_5d_pct)}</span>
              <span className="text-muted">1M</span>
              <span className={`font-semibold ${pctClass(it.change_1m_pct)}`}>{fmtPct(it.change_1m_pct)}</span>
              {it.week52_position_pct != null && (
                <>
                  <span className="text-muted">52W</span>
                  <span className="font-semibold text-heading">{it.week52_position_pct.toFixed(0)}%</span>
                </>
              )}
              {it.volume_ratio != null && (
                <>
                  <span className="text-muted">VOL</span>
                  <span className={`font-semibold ${it.volume_ratio >= 2 ? 'text-amber-600 dark:text-amber-400' : 'text-heading'}`}>
                    {it.volume_ratio.toFixed(1)}x
                  </span>
                </>
              )}
              {it.as_of && <span className="text-muted ml-auto text-[10px]">{t('scanner_as_of')}: {it.as_of}</span>}
            </div>

            {/* Risk flags */}
            {it.risk_flags?.length > 0 && (
              <div className="flex items-center gap-2 mt-3 flex-wrap">
                <AlertTriangle className="w-3 h-3 text-amber-500" />
                {it.risk_flags.map(rf => (
                  <span key={rf} className="px-1.5 py-0.5 rounded text-[9px] font-semibold bg-amber-50 dark:bg-amber-900/20 text-amber-700 dark:text-amber-300">
                    {t(RISK_LABELS[rf]) || rf}
                  </span>
                ))}
              </div>
            )}

            {/* Explanation */}
            <p className="text-xs text-muted mt-3 leading-relaxed">{it.explanation}</p>

            {/* Recommended next step */}
            <div className="mt-3 pt-3 border-t border-border/40 flex items-center gap-2 text-xs">
              <ChevronRight className="w-3 h-3 text-brand" />
              <span className="text-muted">{t('scanner_next_step')}:</span>
              <span className="font-semibold text-heading">
                {t(NEXT_STEP_LABELS[it.recommended_next_step]) || it.recommended_next_step}
              </span>
            </div>
          </div>
        ))}
      </div>
        </>
      )}
    </div>
  );
}
