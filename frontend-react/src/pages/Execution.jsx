import { useState, useEffect } from 'react';
import {
  ArrowLeftRight, Plus, RefreshCw, AlertTriangle, ChevronDown, ChevronRight,
  Zap, FileText, CheckCircle, Lock, Send, ArrowRight
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
    { label: 'Signal', icon: Zap, count: '--', color: 'text-amber-500' },
    { label: 'Intent', icon: FileText, count: intentCount, color: 'text-blue-500' },
    { label: 'Draft', icon: FileText, count: draftCount, color: 'text-purple-500' },
    { label: 'Approved', icon: CheckCircle, count: approvedCount, color: 'text-brand' },
    { label: 'Submit', icon: Lock, count: submittedCount, color: 'text-text-placeholder', locked: true },
  ];

  return (
    <div>
      {/* Page Header */}
      <div className="flex items-center justify-between mb-6">
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
      </div>

      {/* Warning Banner */}
      <div className="flex items-center gap-3 px-5 py-3 mb-6 rounded-xl bg-amber-50 border border-amber-200">
        <AlertTriangle size={20} className="text-amber-500 flex-shrink-0" />
        <div>
          <span className="text-sm font-semibold text-amber-700">Live Submission Disabled</span>
          <span className="text-sm text-amber-600 ml-2">
            T212_LIVE_SUBMIT is set to false. Orders will not be sent to the broker.
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
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr>
                    <th className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder bg-hover-row px-4 py-3 text-left rounded-tl-lg">ID</th>
                    <th className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder bg-hover-row px-4 py-3 text-left">Strategy</th>
                    <th className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder bg-hover-row px-4 py-3 text-left">Instrument</th>
                    <th className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder bg-hover-row px-4 py-3 text-left">Side</th>
                    <th className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder bg-hover-row px-4 py-3 text-right">Qty</th>
                    <th className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder bg-hover-row px-4 py-3 text-left">Status</th>
                    <th className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder bg-hover-row px-4 py-3 text-left rounded-tr-lg">Created</th>
                  </tr>
                </thead>
                <tbody>
                  {intents.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="px-4 py-12 text-center text-text-placeholder text-sm">No intents</td>
                    </tr>
                  ) : (
                    intents.map((intent) => {
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
                    })
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* Drafts Table */}
          <div className="bg-card rounded-xl border border-border shadow-card p-6 mb-6">
            <div className="flex items-center justify-between mb-5">
              <h2 className="text-base font-bold text-text-primary">Drafts</h2>
              <span className="text-xs text-text-placeholder">{drafts.length} total</span>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr>
                    <th className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder bg-hover-row px-4 py-3 text-left rounded-tl-lg">ID</th>
                    <th className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder bg-hover-row px-4 py-3 text-left">Intent ID</th>
                    <th className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder bg-hover-row px-4 py-3 text-left">Broker</th>
                    <th className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder bg-hover-row px-4 py-3 text-left">Order Type</th>
                    <th className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder bg-hover-row px-4 py-3 text-right">Qty</th>
                    <th className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder bg-hover-row px-4 py-3 text-left">Status</th>
                    <th className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder bg-hover-row px-4 py-3 text-left rounded-tr-lg">Created</th>
                  </tr>
                </thead>
                <tbody>
                  {drafts.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="px-4 py-12 text-center text-text-placeholder text-sm">No drafts</td>
                    </tr>
                  ) : (
                    drafts.map((draft) => {
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
                    })
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
