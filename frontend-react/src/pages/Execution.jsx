import { useState, useEffect } from 'react';
import {
  ArrowLeftRight, Plus, RefreshCw, AlertTriangle, ChevronDown, ChevronRight,
  FileText, CheckCircle, Lock, Send, ArrowRight, Shield, Wallet,
  TrendingUp, TrendingDown, Package, ShoppingCart, Unplug,
} from 'lucide-react';
import { apiFetch, apiPost } from '../hooks/useApi';
import { formatDate, truncateId, formatNumber } from '../utils';

export default function Execution() {
  const [intents, setIntents] = useState([]);
  const [drafts, setDrafts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showForm, setShowForm] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  // Broker readonly state
  const [brokerAccount, setBrokerAccount] = useState(null);
  const [brokerPositions, setBrokerPositions] = useState([]);
  const [brokerOrders, setBrokerOrders] = useState([]);
  const [brokerConnected, setBrokerConnected] = useState(false);

  // Form state
  const [form, setForm] = useState({
    strategy: '',
    instrument_id: '',
    side: 'BUY',
    quantity: '',
    order_type: 'MARKET',
    limit_price: '',
  });

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [intentsRes, draftsRes] = await Promise.all([
        apiFetch('/execution/intents'),
        apiFetch('/execution/drafts'),
      ]);
      setIntents(Array.isArray(intentsRes) ? intentsRes : intentsRes.intents || intentsRes.data || []);
      setDrafts(Array.isArray(draftsRes) ? draftsRes : draftsRes.drafts || draftsRes.data || []);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }

    // Fetch broker data separately — optional, failures are fine
    try {
      const [acctRes, posRes, ordRes] = await Promise.allSettled([
        apiFetch('/broker/t212/account'),
        apiFetch('/broker/t212/positions'),
        apiFetch('/broker/t212/orders?limit=5'),
      ]);
      if (acctRes.status === 'fulfilled') {
        setBrokerAccount(acctRes.value);
        setBrokerConnected(true);
      }
      if (posRes.status === 'fulfilled') setBrokerPositions(posRes.value || []);
      if (ordRes.status === 'fulfilled') setBrokerOrders(ordRes.value?.items || ordRes.value || []);
    } catch {
      // broker data is optional
    }
  };

  useEffect(() => { fetchData(); }, []);

  const handleCreateIntent = async () => {
    setSubmitting(true);
    try {
      await apiPost('/execution/intents', {
        strategy: form.strategy,
        instrument_id: form.instrument_id,
        side: form.side,
        quantity: parseInt(form.quantity) || 0,
        order_type: form.order_type,
        limit_price: form.limit_price ? parseFloat(form.limit_price) : undefined,
      });
      setShowForm(false);
      setForm({ strategy: '', instrument_id: '', side: 'BUY', quantity: '', order_type: 'MARKET', limit_price: '' });
      fetchData();
    } catch (e) {
      setError(e.message);
    } finally {
      setSubmitting(false);
    }
  };

  // Pipeline counts
  const intentCount = intents.length;
  const draftCount = drafts.length;
  const approvedCount = drafts.filter((d) => (d.status || '').toUpperCase() === 'APPROVED').length;
  const submittedCount = drafts.filter((d) => (d.status || '').toUpperCase() === 'SUBMITTED').length;

  const pipelineSteps = [
    { label: 'Intent', icon: FileText, count: intentCount, color: 'text-blue-500' },
    { label: 'Draft', icon: FileText, count: draftCount, color: 'text-purple-500' },
    { label: 'Approved', icon: CheckCircle, count: approvedCount, color: 'text-brand' },
    { label: 'Submit', icon: Lock, count: submittedCount, color: 'text-text-placeholder', locked: true },
  ];

  const thClass = 'text-[11px] font-bold uppercase tracking-wider text-text-placeholder bg-hover-row px-4 py-3 text-left';

  return (
    <div>
      {/* Page Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-2xl font-bold text-text-primary tracking-tight flex items-center gap-2">
            <ArrowLeftRight size={24} className="text-brand" />
            Execution &amp; Orders
          </h1>
          <p className="text-sm text-text-secondary mt-1">
            {intentCount} intent{intentCount !== 1 ? 's' : ''} // {draftCount} draft{draftCount !== 1 ? 's' : ''}
          </p>
        </div>
        <button
          onClick={() => setShowForm(!showForm)}
          className="inline-flex items-center gap-2 px-5 h-9 bg-gradient-to-r from-brand to-brand-dark text-white font-semibold text-sm rounded-lg shadow-[0_4px_14px_rgba(103,194,58,0.25)] hover:brightness-105 transition-all cursor-pointer"
        >
          <Plus size={14} /> Create Intent
        </button>
      </div>

      {/* Mode Status Bar */}
      <div className="flex items-center gap-4 px-4 py-2 mb-6 rounded-lg bg-hover-row border border-border text-xs">
        <div className="flex items-center gap-1.5">
          <Shield size={12} className="text-brand" />
          <span className="font-semibold text-text-secondary">Mode:</span>
          <span className="font-bold text-brand">CONTROLLED EXECUTION</span>
        </div>
        <span className="text-border">|</span>
        <div className="flex items-center gap-1.5">
          <Wallet size={12} className="text-text-placeholder" />
          <span className="font-semibold text-text-secondary">Broker:</span>
          <span className={brokerConnected ? 'text-brand font-medium' : 'text-text-placeholder font-medium'}>
            {brokerConnected ? 'Trading 212 \u2014 Readonly' : 'Not Connected'}
          </span>
        </div>
        <span className="text-border">|</span>
        <div className="flex items-center gap-1.5">
          <Lock size={12} className="text-text-placeholder" />
          <span className="font-semibold text-text-secondary">Live Submit:</span>
          <span className="text-text-placeholder font-bold">LOCKED</span>
        </div>
      </div>

      {/* Pipeline Visualization */}
      <div className="bg-card rounded-xl border border-border shadow-card p-6 mb-6">
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-base font-bold text-text-primary">Order Pipeline</h2>
        </div>
        <div className="flex items-center justify-center gap-2">
          {pipelineSteps.map((step, i) => {
            const Icon = step.icon;
            return (
              <div key={step.label} className="flex items-center gap-2">
                <div className={`flex flex-col items-center px-5 py-3 rounded-lg border border-border ${step.locked ? 'bg-hover-row opacity-60' : 'bg-card'}`}>
                  <Icon size={20} className={step.color} />
                  <span className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder mt-1">{step.label}</span>
                  <span className="text-lg font-bold text-text-primary mt-0.5">{step.count}</span>
                  {step.locked && <Lock size={10} className="text-text-placeholder mt-0.5" />}
                </div>
                {i < pipelineSteps.length - 1 && (
                  <ArrowRight size={16} className="text-text-placeholder flex-shrink-0" />
                )}
              </div>
            );
          })}
        </div>
        <p className="text-xs text-text-placeholder text-center mt-4">
          Research signals flow through intent &rarr; draft &rarr; approval. Live submission is disabled by policy.
        </p>
      </div>

      {/* Policy Notice */}
      <div className="flex items-center gap-3 px-5 py-3 mb-6 rounded-xl bg-amber-50 border border-amber-200">
        <AlertTriangle size={20} className="text-amber-500 flex-shrink-0" />
        <div>
          <span className="text-sm font-semibold text-amber-700">Live Submission Disabled</span>
          <span className="text-sm text-amber-600 ml-2">
            Live order submission is disabled by policy. All execution drafts require manual approval and will not be automatically sent to the broker.
          </span>
        </div>
      </div>

      {/* Create Intent Form */}
      {showForm && (
        <div className="bg-card rounded-xl border border-border shadow-card p-6 mb-6">
          <div className="flex items-center justify-between mb-5">
            <h2 className="text-base font-bold text-text-primary">New Execution Intent</h2>
            <button onClick={() => setShowForm(false)} className="text-xs text-text-placeholder hover:text-text-secondary cursor-pointer">
              Cancel
            </button>
          </div>
          <div className="grid grid-cols-3 gap-4 mb-5">
            <div>
              <label className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder mb-1.5 block">Strategy</label>
              <input
                type="text"
                placeholder="e.g. momentum"
                value={form.strategy}
                onChange={(e) => setForm({ ...form, strategy: e.target.value })}
                className="w-full h-10 px-4 bg-card border border-border rounded-lg text-sm focus:border-brand focus:ring-2 focus:ring-brand-light outline-none transition-all"
              />
            </div>
            <div>
              <label className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder mb-1.5 block">Instrument ID</label>
              <input
                type="text"
                placeholder="UUID"
                value={form.instrument_id}
                onChange={(e) => setForm({ ...form, instrument_id: e.target.value })}
                className="w-full h-10 px-4 bg-card border border-border rounded-lg text-sm focus:border-brand focus:ring-2 focus:ring-brand-light outline-none transition-all"
              />
            </div>
            <div>
              <label className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder mb-1.5 block">Side</label>
              <select
                value={form.side}
                onChange={(e) => setForm({ ...form, side: e.target.value })}
                className="w-full h-10 px-4 bg-card border border-border rounded-lg text-sm focus:border-brand focus:ring-2 focus:ring-brand-light outline-none transition-all"
              >
                <option value="BUY">BUY</option>
                <option value="SELL">SELL</option>
              </select>
            </div>
            <div>
              <label className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder mb-1.5 block">Quantity</label>
              <input
                type="number"
                value={form.quantity}
                onChange={(e) => setForm({ ...form, quantity: e.target.value })}
                className="w-full h-10 px-4 bg-card border border-border rounded-lg text-sm focus:border-brand focus:ring-2 focus:ring-brand-light outline-none transition-all"
              />
            </div>
            <div>
              <label className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder mb-1.5 block">Order Type</label>
              <select
                value={form.order_type}
                onChange={(e) => setForm({ ...form, order_type: e.target.value })}
                className="w-full h-10 px-4 bg-card border border-border rounded-lg text-sm focus:border-brand focus:ring-2 focus:ring-brand-light outline-none transition-all"
              >
                <option value="MARKET">MARKET</option>
                <option value="LIMIT">LIMIT</option>
              </select>
            </div>
            <div>
              <label className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder mb-1.5 block">Limit Price</label>
              <input
                type="number"
                step="0.01"
                placeholder="Optional"
                value={form.limit_price}
                onChange={(e) => setForm({ ...form, limit_price: e.target.value })}
                className="w-full h-10 px-4 bg-card border border-border rounded-lg text-sm focus:border-brand focus:ring-2 focus:ring-brand-light outline-none transition-all"
              />
            </div>
          </div>
          <button
            onClick={handleCreateIntent}
            disabled={submitting || !form.strategy || !form.instrument_id || !form.quantity}
            className="inline-flex items-center gap-2 px-5 h-9 bg-gradient-to-r from-brand to-brand-dark text-white font-semibold text-sm rounded-lg shadow-[0_4px_14px_rgba(103,194,58,0.25)] hover:brightness-105 transition-all cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Send size={14} /> {submitting ? 'Creating...' : 'CREATE INTENT'}
          </button>
        </div>
      )}

      {error && (
        <div className="text-sm text-red-500 mb-4 p-3 bg-red-50 rounded-lg">{error}</div>
      )}

      {loading ? (
        <div className="flex items-center justify-center py-16 text-text-placeholder text-sm">
          <RefreshCw size={16} className="animate-spin mr-2" /> Loading execution data...
        </div>
      ) : (
        <>
          {/* Intents Table */}
          <div className="bg-card rounded-xl border border-border shadow-card p-6 mb-6">
            <div className="flex items-center justify-between mb-5">
              <h2 className="text-base font-bold text-text-primary">Intents</h2>
              <span className="text-xs text-text-placeholder">{intents.length} total</span>
            </div>
            {intents.length === 0 ? (
              <div className="flex flex-col items-center py-12 text-center">
                <div className="w-12 h-12 rounded-xl bg-hover-row flex items-center justify-center mb-3">
                  <FileText className="w-5 h-5 text-text-placeholder" />
                </div>
                <p className="text-sm font-medium text-text-primary mb-1">No Execution Intents</p>
                <p className="text-xs text-text-placeholder max-w-[280px]">Create an intent from your research or backtest results to start the execution workflow.</p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr>
                      <th className={`${thClass} rounded-tl-lg`}>ID</th>
                      <th className={thClass}>Strategy</th>
                      <th className={thClass}>Instrument</th>
                      <th className={thClass}>Side</th>
                      <th className={`${thClass} text-right`}>Qty</th>
                      <th className={thClass}>Status</th>
                      <th className={`${thClass} rounded-tr-lg`}>Created</th>
                    </tr>
                  </thead>
                  <tbody>
                    {intents.map((intent) => {
                      const id = intent.intent_id || intent.id;
                      return (
                        <tr key={id} className="hover:bg-hover-row transition-colors">
                          <td className="px-4 py-3 border-b border-border/50 font-mono text-xs text-text-placeholder">{truncateId(id)}</td>
                          <td className="px-4 py-3 border-b border-border/50 font-semibold text-text-primary">{intent.strategy || '--'}</td>
                          <td className="px-4 py-3 border-b border-border/50 text-text-secondary font-mono text-xs">{truncateId(intent.instrument_id)}</td>
                          <td className="px-4 py-3 border-b border-border/50">
                            <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wider ${
                              (intent.side || '').toUpperCase() === 'BUY' ? 'bg-brand-light text-brand-dark' : 'bg-red-50 text-red-500'
                            }`}>
                              {intent.side || '--'}
                            </span>
                          </td>
                          <td className="px-4 py-3 border-b border-border/50 text-right text-text-secondary">{formatNumber(intent.quantity)}</td>
                          <td className="px-4 py-3 border-b border-border/50">
                            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wider bg-amber-50 text-amber-600">
                              {intent.status || 'PENDING'}
                            </span>
                          </td>
                          <td className="px-4 py-3 border-b border-border/50 text-text-placeholder text-xs">{formatDate(intent.created_at)}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Drafts Table */}
          <div className="bg-card rounded-xl border border-border shadow-card p-6 mb-6">
            <div className="flex items-center justify-between mb-5">
              <h2 className="text-base font-bold text-text-primary">Drafts</h2>
              <span className="text-xs text-text-placeholder">{drafts.length} total</span>
            </div>
            {drafts.length === 0 ? (
              <div className="flex flex-col items-center py-12 text-center">
                <div className="w-12 h-12 rounded-xl bg-hover-row flex items-center justify-center mb-3">
                  <FileText className="w-5 h-5 text-text-placeholder" />
                </div>
                <p className="text-sm font-medium text-text-primary mb-1">No Execution Drafts</p>
                <p className="text-xs text-text-placeholder max-w-[280px]">Drafts are generated from approved intents. They represent pending order instructions awaiting final review.</p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr>
                      <th className={`${thClass} rounded-tl-lg`}>ID</th>
                      <th className={thClass}>Intent ID</th>
                      <th className={thClass}>Broker</th>
                      <th className={thClass}>Order Type</th>
                      <th className={`${thClass} text-right`}>Qty</th>
                      <th className={thClass}>Status</th>
                      <th className={`${thClass} rounded-tr-lg`}>Created</th>
                    </tr>
                  </thead>
                  <tbody>
                    {drafts.map((draft) => {
                      const id = draft.draft_id || draft.id;
                      return (
                        <tr key={id} className="hover:bg-hover-row transition-colors">
                          <td className="px-4 py-3 border-b border-border/50 font-mono text-xs text-text-placeholder">{truncateId(id)}</td>
                          <td className="px-4 py-3 border-b border-border/50 font-mono text-xs text-text-secondary">{truncateId(draft.intent_id)}</td>
                          <td className="px-4 py-3 border-b border-border/50 text-text-secondary">{draft.broker || '--'}</td>
                          <td className="px-4 py-3 border-b border-border/50 text-text-secondary">{draft.order_type || '--'}</td>
                          <td className="px-4 py-3 border-b border-border/50 text-right text-text-secondary">{formatNumber(draft.quantity)}</td>
                          <td className="px-4 py-3 border-b border-border/50">
                            <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wider ${
                              (draft.status || '').toUpperCase() === 'APPROVED'
                                ? 'bg-brand-light text-brand-dark'
                                : (draft.status || '').toUpperCase() === 'REJECTED'
                                ? 'bg-red-50 text-red-500'
                                : 'bg-amber-50 text-amber-600'
                            }`}>
                              {draft.status || 'PENDING'}
                            </span>
                          </td>
                          <td className="px-4 py-3 border-b border-border/50 text-text-placeholder text-xs">{formatDate(draft.created_at)}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* ── Broker Section ── */}

          {/* Broker Account Card */}
          <div className="bg-card rounded-xl border border-border shadow-card p-6 mb-6">
            <div className="flex items-center justify-between mb-5">
              <h2 className="text-base font-bold text-text-primary flex items-center gap-2">
                <Wallet size={18} className="text-brand" />
                Broker Account
              </h2>
              {brokerConnected && (
                <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wider bg-brand-light text-brand-dark">
                  Readonly
                </span>
              )}
            </div>
            {brokerConnected && brokerAccount ? (
              <div className="grid grid-cols-4 gap-4">
                <div>
                  <p className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder mb-1">Broker</p>
                  <p className="text-sm font-semibold text-text-primary">Trading 212</p>
                </div>
                <div>
                  <p className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder mb-1">Total Value</p>
                  <p className="text-sm font-semibold text-text-primary">
                    {brokerAccount.currencyCode === 'GBP' ? '\u00a3' : brokerAccount.currencyCode === 'USD' ? '$' : (brokerAccount.currencyCode || '')}{' '}
                    {formatNumber(brokerAccount.total ?? brokerAccount.totalValue ?? brokerAccount.value, 2)}
                  </p>
                </div>
                <div>
                  <p className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder mb-1">Cash</p>
                  <p className="text-sm font-semibold text-text-primary">
                    {brokerAccount.currencyCode === 'GBP' ? '\u00a3' : brokerAccount.currencyCode === 'USD' ? '$' : (brokerAccount.currencyCode || '')}{' '}
                    {formatNumber(brokerAccount.cash ?? brokerAccount.free ?? 0, 2)}
                  </p>
                </div>
                <div>
                  <p className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder mb-1">Positions / Currency</p>
                  <p className="text-sm font-semibold text-text-primary">
                    {brokerPositions.length} &middot; {brokerAccount.currencyCode || 'N/A'}
                  </p>
                </div>
              </div>
            ) : (
              <div className="flex flex-col items-center py-12 text-center">
                <div className="w-12 h-12 rounded-xl bg-hover-row flex items-center justify-center mb-3">
                  <Unplug className="w-5 h-5 text-text-placeholder" />
                </div>
                <p className="text-sm font-medium text-text-primary mb-1">Broker Not Connected</p>
                <p className="text-xs text-text-placeholder max-w-[320px]">
                  Configure <span className="font-mono bg-hover-row px-1 py-0.5 rounded text-text-secondary">T212_API_KEY</span> in <span className="font-mono bg-hover-row px-1 py-0.5 rounded text-text-secondary">.env</span> to enable broker integration.
                </p>
              </div>
            )}
          </div>

          {/* Broker Positions Table */}
          <div className="bg-card rounded-xl border border-border shadow-card p-6 mb-6">
            <div className="flex items-center justify-between mb-5">
              <h2 className="text-base font-bold text-text-primary flex items-center gap-2">
                <Package size={18} className="text-brand" />
                Broker Positions
              </h2>
              {brokerConnected && (
                <span className="text-xs text-text-placeholder">{brokerPositions.length} position{brokerPositions.length !== 1 ? 's' : ''}</span>
              )}
            </div>
            {brokerConnected && brokerPositions.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr>
                      <th className={`${thClass} rounded-tl-lg`}>Ticker</th>
                      <th className={thClass}>Name</th>
                      <th className={`${thClass} text-right`}>Qty</th>
                      <th className={`${thClass} text-right`}>Avg Cost</th>
                      <th className={`${thClass} text-right`}>Current</th>
                      <th className={`${thClass} text-right rounded-tr-lg`}>P&amp;L</th>
                    </tr>
                  </thead>
                  <tbody>
                    {brokerPositions.map((pos, i) => {
                      const ticker = pos.ticker || pos.symbol || '--';
                      const name = pos.name || pos.instrument_name || '--';
                      const qty = pos.quantity ?? pos.qty ?? 0;
                      const avgCost = pos.averagePrice ?? pos.avg_cost ?? pos.avgPrice ?? 0;
                      const currentPrice = pos.currentPrice ?? pos.current_price ?? pos.price ?? 0;
                      const pnl = pos.ppl ?? pos.pnl ?? pos.profit ?? 0;
                      const pnlPositive = pnl >= 0;
                      return (
                        <tr key={ticker + '-' + i} className="hover:bg-hover-row transition-colors">
                          <td className="px-4 py-3 border-b border-border/50 font-mono text-xs font-semibold text-text-primary">{ticker}</td>
                          <td className="px-4 py-3 border-b border-border/50 text-text-secondary text-xs">{name}</td>
                          <td className="px-4 py-3 border-b border-border/50 text-right text-text-secondary">{formatNumber(qty, 2)}</td>
                          <td className="px-4 py-3 border-b border-border/50 text-right text-text-secondary font-mono text-xs">${formatNumber(avgCost, 2)}</td>
                          <td className="px-4 py-3 border-b border-border/50 text-right text-text-secondary font-mono text-xs">${formatNumber(currentPrice, 2)}</td>
                          <td className={`px-4 py-3 border-b border-border/50 text-right font-semibold text-xs ${pnlPositive ? 'text-brand' : 'text-red-500'}`}>
                            <span className="inline-flex items-center gap-1">
                              {pnlPositive ? <TrendingUp size={12} /> : <TrendingDown size={12} />}
                              {pnlPositive ? '' : '-'}{'\u00a3'}{formatNumber(Math.abs(pnl), 2)}
                            </span>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            ) : brokerConnected ? (
              <div className="flex flex-col items-center py-12 text-center">
                <div className="w-12 h-12 rounded-xl bg-hover-row flex items-center justify-center mb-3">
                  <Package className="w-5 h-5 text-text-placeholder" />
                </div>
                <p className="text-sm font-medium text-text-primary mb-1">No Open Positions</p>
                <p className="text-xs text-text-placeholder max-w-[280px]">Your Trading 212 account has no open positions.</p>
              </div>
            ) : (
              <div className="flex flex-col items-center py-12 text-center">
                <div className="w-12 h-12 rounded-xl bg-hover-row flex items-center justify-center mb-3">
                  <Unplug className="w-5 h-5 text-text-placeholder" />
                </div>
                <p className="text-sm font-medium text-text-primary mb-1">Broker Not Connected</p>
                <p className="text-xs text-text-placeholder max-w-[320px]">
                  Configure <span className="font-mono bg-hover-row px-1 py-0.5 rounded text-text-secondary">T212_API_KEY</span> in <span className="font-mono bg-hover-row px-1 py-0.5 rounded text-text-secondary">.env</span> to enable broker integration.
                </p>
              </div>
            )}
          </div>

          {/* Recent Broker Orders */}
          <div className="bg-card rounded-xl border border-border shadow-card p-6 mb-6">
            <div className="flex items-center justify-between mb-5">
              <h2 className="text-base font-bold text-text-primary flex items-center gap-2">
                <ShoppingCart size={18} className="text-brand" />
                Recent Broker Orders
              </h2>
              {brokerConnected && brokerOrders.length > 0 && (
                <span className="text-xs text-text-placeholder">Last {brokerOrders.length}</span>
              )}
            </div>
            {brokerConnected && brokerOrders.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr>
                      <th className={`${thClass} rounded-tl-lg`}>ID</th>
                      <th className={thClass}>Ticker</th>
                      <th className={thClass}>Side</th>
                      <th className={`${thClass} text-right`}>Qty</th>
                      <th className={`${thClass} text-right`}>Price</th>
                      <th className={thClass}>Status</th>
                      <th className={`${thClass} rounded-tr-lg`}>Date</th>
                    </tr>
                  </thead>
                  <tbody>
                    {brokerOrders.map((ord, i) => {
                      const ordId = ord.id || ord.orderId || ord.order_id || i;
                      const ticker = ord.ticker || ord.symbol || '--';
                      const side = (ord.type || ord.side || '--').toUpperCase();
                      const qty = ord.filledQuantity ?? ord.quantity ?? ord.qty ?? 0;
                      const price = ord.fillPrice ?? ord.price ?? ord.limitPrice ?? 0;
                      const status = (ord.status || 'UNKNOWN').toUpperCase();
                      const date = ord.dateModified || ord.dateCreated || ord.date || ord.created_at;
                      const statusColor = status === 'FILLED' || status === 'COMPLETED'
                        ? 'bg-brand-light text-brand-dark'
                        : status === 'CANCELLED' || status === 'REJECTED'
                        ? 'bg-red-50 text-red-500'
                        : 'bg-amber-50 text-amber-600';
                      return (
                        <tr key={ordId} className="hover:bg-hover-row transition-colors">
                          <td className="px-4 py-3 border-b border-border/50 font-mono text-xs text-text-placeholder">{truncateId(String(ordId))}</td>
                          <td className="px-4 py-3 border-b border-border/50 font-mono text-xs font-semibold text-text-primary">{ticker}</td>
                          <td className="px-4 py-3 border-b border-border/50">
                            <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wider ${
                              side === 'BUY' ? 'bg-brand-light text-brand-dark' : 'bg-red-50 text-red-500'
                            }`}>
                              {side}
                            </span>
                          </td>
                          <td className="px-4 py-3 border-b border-border/50 text-right text-text-secondary">{formatNumber(qty, 2)}</td>
                          <td className="px-4 py-3 border-b border-border/50 text-right text-text-secondary font-mono text-xs">${formatNumber(price, 2)}</td>
                          <td className="px-4 py-3 border-b border-border/50">
                            <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wider ${statusColor}`}>
                              {status}
                            </span>
                          </td>
                          <td className="px-4 py-3 border-b border-border/50 text-text-placeholder text-xs">{date ? formatDate(date) : '--'}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            ) : brokerConnected ? (
              <div className="flex flex-col items-center py-12 text-center">
                <div className="w-12 h-12 rounded-xl bg-hover-row flex items-center justify-center mb-3">
                  <ShoppingCart className="w-5 h-5 text-text-placeholder" />
                </div>
                <p className="text-sm font-medium text-text-primary mb-1">No Recent Orders</p>
                <p className="text-xs text-text-placeholder max-w-[280px]">No orders have been placed through Trading 212 recently.</p>
              </div>
            ) : (
              <div className="flex flex-col items-center py-12 text-center">
                <div className="w-12 h-12 rounded-xl bg-hover-row flex items-center justify-center mb-3">
                  <Unplug className="w-5 h-5 text-text-placeholder" />
                </div>
                <p className="text-sm font-medium text-text-primary mb-1">Broker Not Connected</p>
                <p className="text-xs text-text-placeholder max-w-[320px]">
                  Configure <span className="font-mono bg-hover-row px-1 py-0.5 rounded text-text-secondary">T212_API_KEY</span> in <span className="font-mono bg-hover-row px-1 py-0.5 rounded text-text-secondary">.env</span> to enable broker integration.
                </p>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
