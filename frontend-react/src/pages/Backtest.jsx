import { useState, useEffect, Fragment } from 'react';
import {
  History, Plus, Play, RefreshCw, ChevronDown, ChevronRight,
  TrendingUp, BarChart3, TrendingDown, ArrowUpDown, Calendar
} from 'lucide-react';
import { apiFetch, apiPost } from '../hooks/useApi';
import { formatDate, formatPercent, formatNumber, truncateId } from '../utils';

const STRATEGIES = [
  'momentum', 'mean-reversion', 'pairs-trading', 'risk-parity',
  'equal-weight', 'min-variance', 'factor-tilt',
];

const REBALANCE_OPTIONS = ['daily', 'weekly', 'monthly', 'quarterly'];

export default function Backtest() {
  const [runs, setRuns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showForm, setShowForm] = useState(false);
  const [expandedId, setExpandedId] = useState(null);
  const [detail, setDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  // Form state
  const [form, setForm] = useState({
    strategy: 'momentum',
    tickers: '',
    start_date: '',
    end_date: '',
    slippage_bps: '10',
    max_positions: '10',
    rebalance_frequency: 'monthly',
  });

  const fetchRuns = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch('/backtest/runs?limit=20');
      setRuns(Array.isArray(res) ? res : res.runs || res.data || []);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchRuns(); }, []);

  const handleSubmit = async () => {
    setSubmitting(true);
    try {
      const body = {
        strategy: form.strategy,
        tickers: form.tickers.split(',').map((t) => t.trim()).filter(Boolean),
        start_date: form.start_date,
        end_date: form.end_date,
        slippage_bps: parseFloat(form.slippage_bps) || 10,
        max_positions: parseInt(form.max_positions) || 10,
        rebalance_frequency: form.rebalance_frequency,
      };
      await apiPost('/backtest/run', body);
      setShowForm(false);
      fetchRuns();
    } catch (e) {
      setError(e.message);
    } finally {
      setSubmitting(false);
    }
  };

  const handleRowClick = async (run) => {
    const id = run.run_id || run.id;
    if (expandedId === id) {
      setExpandedId(null);
      setDetail(null);
      return;
    }
    setExpandedId(id);
    setDetailLoading(true);
    try {
      const res = await apiFetch(`/backtest/runs/${id}`);
      setDetail(res);
    } catch {
      setDetail(null);
    } finally {
      setDetailLoading(false);
    }
  };

  const renderMiniChart = (navSeries) => {
    if (!navSeries || navSeries.length === 0) return null;
    const vals = navSeries.map((p) => (typeof p === 'number' ? p : p.nav || p.value || 0));
    const max = Math.max(...vals);
    const min = Math.min(...vals);
    const range = max - min || 1;
    const barW = Math.max(2, Math.floor(320 / vals.length));
    return (
      <div className="flex items-end gap-px h-20" style={{ width: vals.length * (barW + 1) }}>
        {vals.map((v, i) => {
          const h = ((v - min) / range) * 100;
          return (
            <div
              key={i}
              className="bg-brand/60 rounded-t-sm"
              style={{ width: barW, height: `${Math.max(4, h)}%` }}
            />
          );
        })}
      </div>
    );
  };

  return (
    <div>
      {/* Page Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-text-primary tracking-tight flex items-center gap-2">
            <History size={24} className="text-brand" />
            Backtest Engine
          </h1>
          <p className="text-sm text-text-secondary mt-1">
            {runs.length} Historical Run{runs.length !== 1 ? 's' : ''}
          </p>
        </div>
        <button
          onClick={() => setShowForm(!showForm)}
          className="inline-flex items-center gap-2 px-5 h-9 bg-gradient-to-r from-brand to-brand-dark text-white font-semibold text-sm rounded-lg shadow-[0_4px_14px_rgba(103,194,58,0.25)] hover:brightness-105 transition-all cursor-pointer"
        >
          <Plus size={14} /> New Backtest
        </button>
      </div>

      {/* New Backtest Form */}
      {showForm && (
        <div className="bg-card rounded-xl border border-border shadow-card p-6 mb-6">
          <div className="flex items-center justify-between mb-5">
            <h2 className="text-base font-bold text-text-primary">Configure Backtest</h2>
            <button
              onClick={() => setShowForm(false)}
              className="text-xs text-text-placeholder hover:text-text-secondary cursor-pointer"
            >
              Cancel
            </button>
          </div>

          <div className="grid grid-cols-3 gap-4 mb-5">
            <div>
              <label className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder mb-1.5 block">
                Strategy
              </label>
              <select
                value={form.strategy}
                onChange={(e) => setForm({ ...form, strategy: e.target.value })}
                className="w-full h-10 px-4 bg-card border border-border rounded-lg text-sm focus:border-brand focus:ring-2 focus:ring-brand-light outline-none transition-all"
              >
                {STRATEGIES.map((s) => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
            </div>

            <div className="col-span-2">
              <label className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder mb-1.5 block">
                Tickers (comma-separated)
              </label>
              <input
                type="text"
                placeholder="AAPL, MSFT, GOOGL..."
                value={form.tickers}
                onChange={(e) => setForm({ ...form, tickers: e.target.value })}
                className="w-full h-10 px-4 bg-card border border-border rounded-lg text-sm focus:border-brand focus:ring-2 focus:ring-brand-light outline-none transition-all"
              />
            </div>

            <div>
              <label className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder mb-1.5 block">
                Start Date
              </label>
              <input
                type="date"
                value={form.start_date}
                onChange={(e) => setForm({ ...form, start_date: e.target.value })}
                className="w-full h-10 px-4 bg-card border border-border rounded-lg text-sm focus:border-brand focus:ring-2 focus:ring-brand-light outline-none transition-all"
              />
            </div>

            <div>
              <label className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder mb-1.5 block">
                End Date
              </label>
              <input
                type="date"
                value={form.end_date}
                onChange={(e) => setForm({ ...form, end_date: e.target.value })}
                className="w-full h-10 px-4 bg-card border border-border rounded-lg text-sm focus:border-brand focus:ring-2 focus:ring-brand-light outline-none transition-all"
              />
            </div>

            <div>
              <label className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder mb-1.5 block">
                Slippage (bps)
              </label>
              <input
                type="number"
                value={form.slippage_bps}
                onChange={(e) => setForm({ ...form, slippage_bps: e.target.value })}
                className="w-full h-10 px-4 bg-card border border-border rounded-lg text-sm focus:border-brand focus:ring-2 focus:ring-brand-light outline-none transition-all"
              />
            </div>

            <div>
              <label className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder mb-1.5 block">
                Max Positions
              </label>
              <input
                type="number"
                value={form.max_positions}
                onChange={(e) => setForm({ ...form, max_positions: e.target.value })}
                className="w-full h-10 px-4 bg-card border border-border rounded-lg text-sm focus:border-brand focus:ring-2 focus:ring-brand-light outline-none transition-all"
              />
            </div>

            <div>
              <label className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder mb-1.5 block">
                Rebalance Frequency
              </label>
              <select
                value={form.rebalance_frequency}
                onChange={(e) => setForm({ ...form, rebalance_frequency: e.target.value })}
                className="w-full h-10 px-4 bg-card border border-border rounded-lg text-sm focus:border-brand focus:ring-2 focus:ring-brand-light outline-none transition-all"
              >
                {REBALANCE_OPTIONS.map((r) => (
                  <option key={r} value={r}>{r}</option>
                ))}
              </select>
            </div>
          </div>

          <button
            onClick={handleSubmit}
            disabled={submitting}
            className="inline-flex items-center gap-2 px-5 h-9 bg-gradient-to-r from-brand to-brand-dark text-white font-semibold text-sm rounded-lg shadow-[0_4px_14px_rgba(103,194,58,0.25)] hover:brightness-105 transition-all cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Play size={14} className={submitting ? 'animate-spin' : ''} />
            {submitting ? 'Running...' : 'RUN BACKTEST'}
          </button>
        </div>
      )}

      {/* Runs Table */}
      <div className="bg-card rounded-xl border border-border shadow-card p-6 mb-6">
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-base font-bold text-text-primary">Past Runs</h2>
          <button
            onClick={fetchRuns}
            className="inline-flex items-center gap-1 text-xs text-text-placeholder hover:text-text-secondary cursor-pointer"
          >
            <RefreshCw size={12} className={loading ? 'animate-spin' : ''} /> Refresh
          </button>
        </div>

        {error && (
          <div className="text-sm text-red-500 mb-4 p-3 bg-red-50 rounded-lg">{error}</div>
        )}

        {loading ? (
          <div className="flex items-center justify-center py-16 text-text-placeholder text-sm">
            <RefreshCw size={16} className="animate-spin mr-2" /> Loading runs...
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr>
                  <th className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder bg-hover-row px-4 py-3 text-left rounded-tl-lg w-8" />
                  <th className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder bg-hover-row px-4 py-3 text-left">Strategy</th>
                  <th className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder bg-hover-row px-4 py-3 text-left">Start</th>
                  <th className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder bg-hover-row px-4 py-3 text-left">End</th>
                  <th className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder bg-hover-row px-4 py-3 text-right">Return</th>
                  <th className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder bg-hover-row px-4 py-3 text-right">Sharpe</th>
                  <th className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder bg-hover-row px-4 py-3 text-right">Max DD</th>
                  <th className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder bg-hover-row px-4 py-3 text-right">Trades</th>
                  <th className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder bg-hover-row px-4 py-3 text-left rounded-tr-lg">Created</th>
                </tr>
              </thead>
              <tbody>
                {runs.length === 0 ? (
                  <tr>
                    <td colSpan={9} className="px-4 py-12 text-center text-text-placeholder text-sm">
                      No backtest runs yet
                    </td>
                  </tr>
                ) : (
                  runs.map((run) => {
                    const id = run.run_id || run.id;
                    const isExpanded = expandedId === id;
                    const ret = run.total_return ?? run.return_pct ?? null;
                    const retPositive = ret !== null && ret >= 0;
                    return (
                      <Fragment key={id}>
                        <tr
                          onClick={() => handleRowClick(run)}
                          className="hover:bg-hover-row cursor-pointer transition-colors"
                        >
                          <td className="px-4 py-3 border-b border-border/50">
                            {isExpanded ? (
                              <ChevronDown size={14} className="text-brand" />
                            ) : (
                              <ChevronRight size={14} className="text-text-placeholder" />
                            )}
                          </td>
                          <td className="px-4 py-3 border-b border-border/50 font-semibold text-text-primary">
                            {run.strategy || '--'}
                          </td>
                          <td className="px-4 py-3 border-b border-border/50 text-text-secondary">
                            {formatDate(run.start_date)}
                          </td>
                          <td className="px-4 py-3 border-b border-border/50 text-text-secondary">
                            {formatDate(run.end_date)}
                          </td>
                          <td className={`px-4 py-3 border-b border-border/50 text-right font-semibold ${retPositive ? 'text-brand-dark' : 'text-red-500'}`}>
                            {formatPercent(ret)}
                          </td>
                          <td className="px-4 py-3 border-b border-border/50 text-right text-text-secondary">
                            {run.sharpe_ratio != null ? Number(run.sharpe_ratio).toFixed(2) : '--'}
                          </td>
                          <td className="px-4 py-3 border-b border-border/50 text-right text-red-500">
                            {formatPercent(run.max_drawdown)}
                          </td>
                          <td className="px-4 py-3 border-b border-border/50 text-right text-text-secondary">
                            {run.total_trades != null ? formatNumber(run.total_trades) : '--'}
                          </td>
                          <td className="px-4 py-3 border-b border-border/50 text-text-placeholder text-xs">
                            {formatDate(run.created_at)}
                          </td>
                        </tr>

                        {/* Detail Panel */}
                        {isExpanded && (
                          <tr>
                            <td colSpan={9} className="px-4 py-0 border-b border-border/50 bg-hover-row/30">
                              <div className="py-5">
                                {detailLoading ? (
                                  <div className="flex items-center text-sm text-text-placeholder py-4">
                                    <RefreshCw size={14} className="animate-spin mr-2" /> Loading detail...
                                  </div>
                                ) : detail ? (
                                  <div>
                                    {/* Metric Cards */}
                                    <div className="grid grid-cols-3 gap-4 mb-5">
                                      <div className="bg-card rounded-lg border border-border p-4 text-center">
                                        <div className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder mb-1">Total Return</div>
                                        <div className={`text-xl font-bold ${(detail.total_return ?? detail.return_pct ?? 0) >= 0 ? 'text-brand-dark' : 'text-red-500'}`}>
                                          {formatPercent(detail.total_return ?? detail.return_pct)}
                                        </div>
                                        <TrendingUp size={14} className="mx-auto mt-1 text-text-placeholder" />
                                      </div>
                                      <div className="bg-card rounded-lg border border-border p-4 text-center">
                                        <div className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder mb-1">Sharpe Ratio</div>
                                        <div className="text-xl font-bold text-text-primary">
                                          {detail.sharpe_ratio != null ? Number(detail.sharpe_ratio).toFixed(2) : '--'}
                                        </div>
                                        <BarChart3 size={14} className="mx-auto mt-1 text-text-placeholder" />
                                      </div>
                                      <div className="bg-card rounded-lg border border-border p-4 text-center">
                                        <div className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder mb-1">Max Drawdown</div>
                                        <div className="text-xl font-bold text-red-500">
                                          {formatPercent(detail.max_drawdown)}
                                        </div>
                                        <TrendingDown size={14} className="mx-auto mt-1 text-text-placeholder" />
                                      </div>
                                    </div>

                                    {/* NAV Chart */}
                                    {(detail.nav_series || detail.equity_curve) && (
                                      <div className="mb-5">
                                        <h4 className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder mb-3">NAV Curve</h4>
                                        <div className="bg-card rounded-lg border border-border p-4 overflow-x-auto">
                                          {renderMiniChart(detail.nav_series || detail.equity_curve)}
                                        </div>
                                      </div>
                                    )}

                                    {/* Trades Table */}
                                    {(detail.trades || []).length > 0 && (
                                      <div>
                                        <h4 className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder mb-3">
                                          Trades ({detail.trades.length})
                                        </h4>
                                        <div className="overflow-x-auto max-h-64">
                                          <table className="w-full text-sm">
                                            <thead>
                                              <tr>
                                                <th className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder bg-hover-row px-3 py-2 text-left">Date</th>
                                                <th className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder bg-hover-row px-3 py-2 text-left">Ticker</th>
                                                <th className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder bg-hover-row px-3 py-2 text-left">Side</th>
                                                <th className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder bg-hover-row px-3 py-2 text-right">Qty</th>
                                                <th className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder bg-hover-row px-3 py-2 text-right">Price</th>
                                              </tr>
                                            </thead>
                                            <tbody>
                                              {detail.trades.slice(0, 20).map((t, i) => (
                                                <tr key={i}>
                                                  <td className="px-3 py-2 border-b border-border/50 text-text-secondary">{formatDate(t.date || t.trade_date)}</td>
                                                  <td className="px-3 py-2 border-b border-border/50 font-semibold text-text-primary">{t.ticker || t.symbol || '--'}</td>
                                                  <td className="px-3 py-2 border-b border-border/50">
                                                    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wider ${
                                                      (t.side || '').toUpperCase() === 'BUY' ? 'bg-brand-light text-brand-dark' : 'bg-red-50 text-red-500'
                                                    }`}>
                                                      {t.side || '--'}
                                                    </span>
                                                  </td>
                                                  <td className="px-3 py-2 border-b border-border/50 text-right text-text-secondary">{formatNumber(t.quantity || t.qty)}</td>
                                                  <td className="px-3 py-2 border-b border-border/50 text-right text-text-secondary">${Number(t.price || 0).toFixed(2)}</td>
                                                </tr>
                                              ))}
                                            </tbody>
                                          </table>
                                        </div>
                                      </div>
                                    )}
                                  </div>
                                ) : (
                                  <div className="text-sm text-text-placeholder py-4">No detail available</div>
                                )}
                              </div>
                            </td>
                          </tr>
                        )}
                      </Fragment>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
