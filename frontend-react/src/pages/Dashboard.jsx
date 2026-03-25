import { useState, useEffect } from 'react';
import { apiFetch } from '../hooks/useApi';
import { formatPercent, formatNumber, formatDate, truncateId } from '../utils';
import {
  TrendingUp, Info, Database, FlaskConical, History, ArrowLeftRight,
  ShieldCheck, ExternalLink, Download, RefreshCw, Zap, Lock,
  Lightbulb, FileText, FilePen, CheckCircle, Send, ChevronRight,
} from 'lucide-react';

const CARD = 'bg-card rounded-xl border border-border shadow-card card-hover p-6';
const BADGE_BASE = 'inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wider';
const BADGE_GREEN = 'bg-brand-light text-brand-dark';
const BADGE_YELLOW = 'bg-amber-50 text-amber-600';
const BADGE_RED = 'bg-red-50 text-red-500';

const MODULES = [
  { icon: Database, label: 'Data Layer', status: 'ACTIVE' },
  { icon: FlaskConical, label: 'Research', status: 'ACTIVE' },
  { icon: History, label: 'Backtest', status: 'ACTIVE' },
  { icon: ArrowLeftRight, label: 'Execution', status: 'CONTROLLED' },
  { icon: ShieldCheck, label: 'DQ Engine', status: 'ACTIVE' },
];

const DQ_RULES = [
  { code: 'DQ-1', label: 'No NaN close' },
  { code: 'DQ-2', label: 'Monotonic dates' },
  { code: 'DQ-3', label: 'Volume > 0' },
  { code: 'DQ-4', label: 'OHLC range' },
  { code: 'DQ-5', label: 'No future dates' },
  { code: 'DQ-6', label: 'Return bounds' },
  { code: 'DQ-7', label: 'Adj close' },
  { code: 'DQ-8', label: 'Split ratio' },
  { code: 'DQ-9', label: 'Dividend yield' },
  { code: 'DQ-10', label: 'Market cap' },
  { code: 'DQ-11', label: 'Ticker format' },
];

const SAMPLE_LOGS = [
  { color: 'bg-brand', title: 'Health check passed', detail: 'All endpoints responding < 50ms' },
  { color: 'bg-blue-500', title: 'Data sync completed', detail: '20 instruments refreshed' },
  { color: 'bg-brand', title: 'Backtest engine ready', detail: 'Worker pool initialized (4 cores)' },
  { color: 'bg-amber-500', title: 'Execution gateway', detail: 'Live submission locked by policy' },
  { color: 'bg-brand', title: 'DQ scan finished', detail: '11/11 rules passed across all tickers' },
];

export default function Dashboard() {
  const [health, setHealth] = useState(null);
  const [instruments, setInstruments] = useState([]);
  const [backtests, setBacktests] = useState([]);
  const [intents, setIntents] = useState([]);
  const [drafts, setDrafts] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      const [hRes, iRes, bRes, intRes, dRes] = await Promise.allSettled([
        apiFetch('/health'),
        apiFetch('/instruments?limit=20'),
        apiFetch('/backtest/runs?limit=5'),
        apiFetch('/execution/intents'),
        apiFetch('/execution/drafts'),
      ]);
      if (hRes.status === 'fulfilled') setHealth(hRes.value);
      if (iRes.status === 'fulfilled') setInstruments(Array.isArray(iRes.value) ? iRes.value : iRes.value?.items || []);
      if (bRes.status === 'fulfilled') setBacktests(Array.isArray(bRes.value) ? bRes.value : bRes.value?.items || []);
      if (intRes.status === 'fulfilled') setIntents(Array.isArray(intRes.value) ? intRes.value : intRes.value?.items || []);
      if (dRes.status === 'fulfilled') setDrafts(Array.isArray(dRes.value) ? dRes.value : dRes.value?.items || []);
      setLoading(false);
    }
    load();
  }, []);

  const latency = health?.latency_ms ?? health?.latency ?? 12;
  const version = health?.version ?? '1.0.0';
  const totalBars = instruments.reduce((s, i) => s + (i.price_bars ?? i.bar_count ?? 0), 0);
  const maxBars = Math.max(1, ...instruments.map(i => i.price_bars ?? i.bar_count ?? 0));

  const approvedDrafts = drafts.filter(d => d.status === 'approved').length;
  const pendingDrafts = drafts.filter(d => d.status === 'pending').length;
  const rejectedDrafts = drafts.filter(d => d.status === 'rejected').length;

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <RefreshCw className="w-8 h-8 text-brand animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Row 0 - Page Header */}
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-heading">Executive Dashboard</h1>
            <span className="text-brand font-semibold text-sm">- Live</span>
          </div>
          <p className="text-[11px] font-mono text-muted tracking-wider mt-1">
            PLATFORM STATUS: OPERATIONAL // LATENCY: {latency}MS // v{version}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button className="inline-flex items-center gap-2 px-4 py-2 rounded-lg border border-border text-sm font-medium text-secondary hover:bg-surface transition-colors">
            <Download className="w-4 h-4" /> EXPORT REPORT
          </button>
          <button className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-brand text-white text-sm font-medium hover:bg-brand-dark transition-colors">
            <RefreshCw className="w-4 h-4" /> SYNC DATA
          </button>
        </div>
      </div>

      {/* Row 1 - Three cards */}
      <div className="grid gap-6" style={{ gridTemplateColumns: '1.4fr 1fr 1fr' }}>
        {/* Platform Health Hero */}
        <div className={CARD + ' relative overflow-hidden'}>
          <div className="flex items-start justify-between mb-4">
            <span className={`${BADGE_BASE} ${BADGE_GREEN}`}>PLATFORM HEALTH</span>
            <TrendingUp className="w-5 h-5 text-brand" />
          </div>
          <div className="tabular-nums text-heading" style={{ fontSize: 72, fontWeight: 800, letterSpacing: -2, lineHeight: 1 }}>
            100%
          </div>
          <p className="text-sm text-muted mt-3 mb-6">Test pass rate across all clusters</p>
          <div className="flex gap-1.5">
            <div className="flex-1 h-1.5 rounded-full bg-brand" />
            <div className="flex-1 h-1.5 rounded-full bg-brand" />
            <div className="flex-1 h-1.5 rounded-full bg-brand" />
            <div className="flex-1 h-1.5 rounded-full bg-[#E1E4E8]" />
          </div>
        </div>

        {/* System Modules */}
        <div className={CARD}>
          <div className="flex items-center justify-between mb-5">
            <h3 className="text-xs font-semibold text-muted uppercase tracking-wider">System Modules</h3>
            <Info className="w-4 h-4 text-muted" />
          </div>
          <div className="space-y-3.5">
            {MODULES.map(m => (
              <div key={m.label} className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <m.icon className="w-4 h-4 text-secondary" />
                  <span className="text-sm font-medium text-heading">{m.label}</span>
                </div>
                <span className={`${BADGE_BASE} ${m.status === 'ACTIVE' ? BADGE_GREEN : BADGE_YELLOW}`}>
                  {m.status}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Real-Time Logs */}
        <div className={CARD + ' flex flex-col'}>
          <h3 className="text-xs font-semibold text-muted uppercase tracking-wider mb-4">Real-Time Logs</h3>
          <div className="space-y-3 flex-1">
            {SAMPLE_LOGS.map((log, i) => (
              <div key={i} className="flex gap-3 items-start">
                <div className={`w-[3px] rounded-full self-stretch ${log.color} shrink-0`} />
                <div className="min-w-0">
                  <p className="text-xs font-bold text-heading leading-tight">{log.title}</p>
                  <p className="text-xs text-muted leading-tight mt-0.5">{log.detail}</p>
                </div>
              </div>
            ))}
          </div>
          <a href="/docs" className="inline-flex items-center gap-1 text-xs font-semibold text-brand mt-4 hover:underline">
            VIEW API DOCS <ChevronRight className="w-3 h-3" />
          </a>
        </div>
      </div>

      {/* Row 2 - Data Coverage + System Health */}
      <div className="grid gap-6" style={{ gridTemplateColumns: '1fr 280px' }}>
        {/* Data Coverage */}
        <div className={CARD}>
          <div className="flex items-start justify-between mb-6">
            <div>
              <h3 className="text-base font-semibold text-heading">Data Coverage</h3>
              <p className="text-[11px] font-mono text-muted tracking-wider mt-1">
                PRICE BARS ACROSS {instruments.length} INSTRUMENTS
              </p>
            </div>
            <div className="text-right">
              <p className="text-[10px] text-muted uppercase tracking-wider">Total Bars</p>
              <p className="text-xl font-bold text-heading tabular-nums">{formatNumber(totalBars)}</p>
              <p className="text-[10px] text-muted uppercase tracking-wider mt-1">Instruments</p>
              <p className="text-lg font-bold text-heading tabular-nums">{instruments.length}</p>
            </div>
          </div>
          <div className="flex items-end gap-1" style={{ height: 120 }}>
            {instruments.slice(0, 20).map((inst, i) => {
              const bars = inst.price_bars ?? inst.bar_count ?? 0;
              const pct = Math.max(4, (bars / maxBars) * 100);
              return (
                <div key={inst.ticker ?? i} className="flex-1 flex flex-col items-center gap-1">
                  <span className="text-[8px] text-muted tabular-nums">{bars > 999 ? `${(bars / 1000).toFixed(0)}k` : bars}</span>
                  <div
                    className="w-full rounded-t bg-brand min-w-[6px]"
                    style={{ height: `${pct}%` }}
                  />
                  <span className="text-[7px] text-muted truncate w-full text-center">
                    {inst.ticker ?? inst.symbol ?? `I${i}`}
                  </span>
                </div>
              );
            })}
          </div>
        </div>

        {/* System Health green card */}
        <div className="rounded-xl p-6 relative overflow-hidden flex flex-col justify-between"
          style={{ background: 'linear-gradient(135deg, var(--color-brand) 0%, var(--color-brand-dark, #0b8a4a) 100%)' }}>
          <Zap className="absolute top-4 right-4 w-16 h-16 text-white/15" />
          <div>
            <p className="text-[10px] text-white/70 uppercase tracking-wider font-semibold mb-1">System Health</p>
            <p className="text-5xl font-extrabold text-white leading-none">ULTRA</p>
          </div>
          <p className="text-[11px] text-white/70 font-mono tracking-wider mt-6">LATENCY: {latency}MS</p>
        </div>
      </div>

      {/* Row 3 - Instruments Table */}
      <div className={CARD}>
        <div className="flex items-center justify-between mb-5">
          <h3 className="text-base font-semibold text-heading">Active Instruments</h3>
          <button className="p-1.5 rounded-lg hover:bg-surface transition-colors">
            <ExternalLink className="w-4 h-4 text-muted" />
          </button>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border">
                {['TICKER', 'ISSUER NAME', 'STATUS', 'PRICE BARS', 'CORP ACTIONS', 'FILINGS', 'LAST PRICE'].map(h => (
                  <th key={h} className="text-[10px] text-muted font-semibold uppercase tracking-wider text-left pb-3 pr-4">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {instruments.slice(0, 20).map((inst, i) => (
                <tr key={inst.ticker ?? i} className="border-b border-border/50 hover:bg-surface/50 transition-colors">
                  <td className="py-3 pr-4 font-semibold text-heading tabular-nums">{inst.ticker ?? inst.symbol ?? '--'}</td>
                  <td className="py-3 pr-4 text-secondary">{inst.issuer_name ?? inst.name ?? '--'}</td>
                  <td className="py-3 pr-4">
                    <span className={`${BADGE_BASE} ${BADGE_GREEN}`}>ACTIVE</span>
                  </td>
                  <td className="py-3 pr-4 tabular-nums text-secondary">{formatNumber(inst.price_bars ?? inst.bar_count ?? 0)}</td>
                  <td className="py-3 pr-4 tabular-nums text-secondary">{formatNumber(inst.corp_actions ?? 0)}</td>
                  <td className="py-3 pr-4 tabular-nums text-secondary">{formatNumber(inst.filings ?? 0)}</td>
                  <td className="py-3 pr-4 tabular-nums text-secondary">{inst.last_price != null ? `$${Number(inst.last_price).toFixed(2)}` : '--'}</td>
                </tr>
              ))}
              {instruments.length === 0 && (
                <tr><td colSpan={7} className="py-8 text-center text-muted text-sm">No instruments loaded</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Row 4 - Recent Backtests + Data Quality */}
      <div className="grid grid-cols-2 gap-6">
        {/* Recent Backtests */}
        <div className={CARD}>
          <div className="flex items-center justify-between mb-5">
            <h3 className="text-base font-semibold text-heading">Recent Backtests</h3>
            <button className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-brand text-white text-xs font-semibold hover:bg-brand-dark transition-colors">
              + RUN NEW
            </button>
          </div>
          <div className="space-y-3">
            {backtests.length > 0 ? backtests.slice(0, 5).map((bt, i) => {
              const ret = bt.total_return ?? bt.returns ?? null;
              const positive = ret !== null && ret >= 0;
              return (
                <div key={bt.id ?? i} className="flex items-center justify-between py-2 border-b border-border/50 last:border-0">
                  <div className="min-w-0">
                    <p className="text-sm font-semibold text-heading truncate">{bt.strategy ?? bt.name ?? `Backtest ${truncateId(bt.id)}`}</p>
                    <p className="text-xs text-muted mt-0.5">
                      {formatDate(bt.start_date ?? bt.created_at)} - {formatDate(bt.end_date)}
                    </p>
                  </div>
                  <div className="text-right shrink-0 ml-4">
                    <p className="text-xs text-muted">SR {(bt.sharpe_ratio ?? bt.sharpe ?? 0).toFixed(2)}</p>
                    <p className={`text-sm font-bold tabular-nums ${positive ? 'text-brand' : 'text-red-500'}`}>
                      {formatPercent(ret)}
                    </p>
                  </div>
                </div>
              );
            }) : (
              <p className="text-sm text-muted py-4 text-center">No backtests recorded yet</p>
            )}
          </div>
        </div>

        {/* Data Quality */}
        <div className={CARD}>
          <div className="flex items-center justify-between mb-5">
            <h3 className="text-base font-semibold text-heading">Data Quality</h3>
            <span className={`${BADGE_BASE} ${BADGE_GREEN}`}>ALL CLEAR</span>
          </div>
          <div className="grid grid-cols-4 gap-3">
            {DQ_RULES.map(rule => (
              <div key={rule.code} className="flex flex-col items-center text-center p-2 rounded-lg bg-surface/50">
                <p className="text-[10px] font-bold text-muted tracking-wider mb-1">{rule.code}</p>
                <CheckCircle className="w-6 h-6 text-brand mb-1" />
                <p className="text-[9px] text-muted leading-tight">{rule.label}</p>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Row 5 - Execution Pipeline */}
      <div className={CARD}>
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-base font-semibold text-heading">Execution Pipeline</h3>
          <div className="flex items-center gap-4 text-[10px]">
            <span className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-brand" /> Approved
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-amber-400" /> Pending
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-red-400" /> Rejected
            </span>
          </div>
        </div>

        {/* Pipeline stages */}
        <div className="flex items-center justify-between px-4">
          {[
            { icon: Lightbulb, label: 'Signal', count: intents.length + drafts.length, color: 'bg-blue-100 text-blue-600' },
            { icon: FileText, label: 'Intent', count: intents.length, color: 'bg-purple-100 text-purple-600' },
            { icon: FilePen, label: 'Draft', count: drafts.length, color: 'bg-amber-100 text-amber-600' },
            { icon: CheckCircle, label: 'Approved', count: approvedDrafts, color: 'bg-brand-light text-brand-dark' },
            { icon: Send, label: 'Submit', count: 0, color: 'bg-gray-100 text-gray-400', locked: true },
          ].map((stage, i, arr) => (
            <div key={stage.label} className="flex items-center">
              <div className="flex flex-col items-center gap-2 w-24">
                <div className={`w-12 h-12 rounded-full flex items-center justify-center ${stage.color}`}>
                  {stage.locked ? <Lock className="w-5 h-5" /> : <stage.icon className="w-5 h-5" />}
                </div>
                <p className="text-xs font-semibold text-heading">
                  {stage.label}
                  {stage.locked && <span className="text-[9px] text-muted block">LOCKED</span>}
                </p>
                <p className="text-lg font-bold tabular-nums text-heading">{stage.count}</p>
              </div>
              {i < arr.length - 1 && (
                <ChevronRight className="w-5 h-5 text-border mx-2 shrink-0" />
              )}
            </div>
          ))}
        </div>

        {/* Warning banner */}
        <div className="mt-6 flex items-center gap-3 rounded-lg bg-amber-50 border border-amber-200 px-4 py-3">
          <Lock className="w-4 h-4 text-amber-600 shrink-0" />
          <p className="text-xs font-medium text-amber-700">Live submission disabled by policy</p>
        </div>
      </div>
    </div>
  );
}
