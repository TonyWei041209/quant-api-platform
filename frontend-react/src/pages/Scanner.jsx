import { useState, useEffect, useCallback } from 'react';
import { apiFetch } from '../hooks/useApi';
import { useI18n } from '../hooks/useI18n';
import {
  Radar, RefreshCw, Filter, AlertTriangle, ChevronRight,
  TrendingUp, FlaskConical, History, Eye, Info,
} from 'lucide-react';

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

  useEffect(() => { runScan(); }, [runScan]);

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
          onClick={runScan}
          disabled={loading}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-brand text-white text-sm font-semibold hover:bg-brand-dark disabled:opacity-50 transition-colors"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          {loading ? t('loading') : t('scanner_rescan')}
        </button>
      </div>

      {/* Research-only banner — make platform stance crystal clear */}
      <div className="rounded-lg border border-amber-200 dark:border-amber-800 bg-amber-50/60 dark:bg-amber-900/20 px-4 py-3 flex gap-3">
        <Info className="w-4 h-4 text-amber-600 dark:text-amber-400 mt-0.5 shrink-0" />
        <p className="text-xs text-amber-700 dark:text-amber-300 leading-relaxed">
          {t('scanner_research_only_banner')}
        </p>
      </div>

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
    </div>
  );
}
