import { useState, useEffect, useCallback } from 'react';
import {
  ArrowLeftRight, Plus, RefreshCw, AlertTriangle, ChevronDown, ChevronRight,
  FileText, CheckCircle, Lock, Send, ArrowRight, Shield, Wallet,
  TrendingUp, TrendingDown, Package, ShoppingCart, Unplug,
} from 'lucide-react';
import { apiFetch, apiPost } from '../hooks/useApi';
import { useI18n } from '../hooks/useI18n';
import { formatDate, truncateId, formatNumber } from '../utils';

export default function Execution() {
  const { t } = useI18n();
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

  const fetchData = useCallback(async () => {
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
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

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
      // Only refetch intents, not all data
      const intentsRes = await apiFetch('/execution/intents');
      setIntents(Array.isArray(intentsRes) ? intentsRes : intentsRes.intents || intentsRes.data || []);
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
    { label: t('pip_intent'), icon: FileText, count: intentCount, color: 'text-blue-500' },
    { label: t('pip_draft'), icon: FileText, count: draftCount, color: 'text-purple-500' },
    { label: t('pip_approved'), icon: CheckCircle, count: approvedCount, color: 'text-brand' },
    { label: t('pip_submit'), icon: Lock, count: submittedCount, color: 'text-text-placeholder', locked: true },
  ];

  const thClass = 'text-[11px] font-bold uppercase tracking-wider text-text-placeholder bg-hover-row px-4 py-3 text-left';

  return (
    <div>
      {/* Page Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
        <div className="min-w-0">
          <h1 className="text-2xl font-bold text-text-primary tracking-tight flex items-center gap-2">
            <ArrowLeftRight size={24} className="text-brand shrink-0" />
            {t('ex_title')}
          </h1>
          <p className="text-sm text-text-secondary mt-1">
            {intentCount} {t('ex_intents')} // {draftCount} {t('ex_drafts')}
          </p>
        </div>
        <button
          onClick={() => setShowForm(!showForm)}
          className="inline-flex items-center gap-2 px-5 h-9 bg-gradient-to-r from-brand to-brand-dark text-white font-semibold text-sm rounded-lg shadow-[0_4px_14px_rgba(103,194,58,0.25)] hover:brightness-105 transition-all cursor-pointer shrink-0"
        >
          <Plus size={14} /> {t('ex_create')}
        </button>
      </div>

      {/* Mode Status Bar */}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 px-4 py-2 mb-6 rounded-lg bg-hover-row border border-border text-xs">
        <div className="flex items-center gap-1.5">
          <Shield size={12} className="text-brand shrink-0" />
          <span className="font-semibold text-text-secondary">{t('ex_mode')}</span>
          <span className="font-bold text-brand">{t('ex_controlled')}</span>
        </div>
        <span className="text-border hidden sm:inline">|</span>
        <div className="flex items-center gap-1.5">
          <Wallet size={12} className="text-text-placeholder shrink-0" />
          <span className="font-semibold text-text-secondary">{t('ex_broker')}</span>
          <span className={brokerConnected ? 'text-brand font-medium' : 'text-text-placeholder font-medium'}>
            {brokerConnected ? t('ex_t212_readonly') : t('ex_na')}
          </span>
        </div>
        <span className="text-border hidden sm:inline">|</span>
        <div className="flex items-center gap-1.5">
          <Lock size={12} className="text-text-placeholder shrink-0" />
          <span className="font-semibold text-text-secondary">{t('ex_live')}</span>
          <span className="text-text-placeholder font-bold">{t('ex_locked')}</span>
        </div>
      </div>

      {/* Pipeline Visualization */}
      <div className="bg-card rounded-xl border border-border shadow-card p-6 mb-6">
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-base font-bold text-text-primary">{t('ex_pipeline')}</h2>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {pipelineSteps.map((step) => {
            const Icon = step.icon;
            return (
              <div key={step.label} className={`flex flex-col items-center px-4 py-3 rounded-lg border border-border ${step.locked ? 'bg-hover-row opacity-60' : 'bg-card'}`}>
                <Icon size={20} className={step.color} />
                <span className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder mt-1">{step.label}</span>
                <span className="text-lg font-bold text-text-primary mt-0.5">{step.count}</span>
                {step.locked && <Lock size={10} className="text-text-placeholder mt-0.5" />}
              </div>
            );
          })}
        </div>
        <p className="text-xs text-text-placeholder text-center mt-4">
          {t('ex_pipeline_desc')}
        </p>
      </div>

      {/* Policy Notice */}
      <div className="flex items-start gap-3 px-4 sm:px-5 py-3 mb-6 rounded-xl bg-amber-50 border border-amber-200">
        <AlertTriangle size={20} className="text-amber-500 shrink-0 mt-0.5" />
        <div>
          <span className="text-sm font-semibold text-amber-700">{t('ex_warning')}</span>
          <span className="text-sm text-amber-600 sm:ml-2 block sm:inline mt-0.5 sm:mt-0">
            {t('ex_warning_desc')}
          </span>
        </div>
      </div>

      {/* Create Intent Form */}
      {showForm && (
        <div className="bg-card rounded-xl border border-border shadow-card p-6 mb-6">
          <div className="flex items-center justify-between mb-5">
            <h2 className="text-base font-bold text-text-primary">{t('ex_new_intent')}</h2>
            <button onClick={() => setShowForm(false)} className="text-xs text-text-placeholder hover:text-text-secondary cursor-pointer">
              {t('common_cancel')}
            </button>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-5">
            <div>
              <label className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder mb-1.5 block">{t('ex_strategy')}</label>
              <input
                type="text"
                placeholder="e.g. momentum"
                value={form.strategy}
                onChange={(e) => setForm({ ...form, strategy: e.target.value })}
                className="w-full h-10 px-4 bg-card border border-border rounded-lg text-sm focus:border-brand focus:ring-2 focus:ring-brand-light outline-none transition-all"
              />
            </div>
            <div>
              <label className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder mb-1.5 block">{t('ex_instrument_id')}</label>
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
              <label className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder mb-1.5 block">{t('ex_quantity')}</label>
              <input
                type="number"
                value={form.quantity}
                onChange={(e) => setForm({ ...form, quantity: e.target.value })}
                className="w-full h-10 px-4 bg-card border border-border rounded-lg text-sm focus:border-brand focus:ring-2 focus:ring-brand-light outline-none transition-all"
              />
            </div>
            <div>
              <label className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder mb-1.5 block">{t('ex_order_type')}</label>
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
              <label className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder mb-1.5 block">{t('ex_limit_price')}</label>
              <input
                type="number"
                step="0.01"
                placeholder={t('ex_optional')}
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
            <Send size={14} /> {submitting ? t('ex_creating') : t('ex_create_intent')}
          </button>
        </div>
      )}

      {error && (
        <div className="text-sm text-red-500 mb-4 p-3 bg-red-50 rounded-lg">{error}</div>
      )}

      {loading ? (
        <div className="flex items-center justify-center py-16 text-text-placeholder text-sm animate-pulse opacity-80">
          <RefreshCw size={16} className="animate-spin mr-2" /> Loading execution data...
        </div>
      ) : (
        <>
          {/* Intents Table */}
          <div className="bg-card rounded-xl border border-border shadow-card p-6 mb-6">
            <div className="flex items-center justify-between mb-5">
              <h2 className="text-base font-bold text-text-primary">{t('ex_intents_title')}</h2>
              <span className="text-xs text-text-placeholder">{intents.length} {t('common_total')}</span>
            </div>
            {intents.length === 0 ? (
              <div className="flex flex-col items-center py-12 text-center">
                <div className="w-12 h-12 rounded-xl bg-hover-row flex items-center justify-center mb-3">
                  <FileText className="w-5 h-5 text-text-placeholder" />
                </div>
                <p className="text-sm font-medium text-text-primary mb-1">{t('ex_no_intents')}</p>
                <p className="text-xs text-text-placeholder max-w-[280px]">{t('ex_no_intents_desc')}</p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr>
                      <th className={`${thClass} rounded-tl-lg`}>ID</th>
                      <th className={thClass}>{t('ex_strategy')}</th>
                      <th className={thClass}>{t('res_instrument')}</th>
                      <th className={thClass}>Side</th>
                      <th className={`${thClass} text-right`}>Qty</th>
                      <th className={thClass}>{t('th_status')}</th>
                      <th className={`${thClass} rounded-tr-lg`}>{t('th_created')}</th>
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
              <h2 className="text-base font-bold text-text-primary">{t('ex_drafts_title')}</h2>
              <span className="text-xs text-text-placeholder">{drafts.length} {t('common_total')}</span>
            </div>
            {drafts.length === 0 ? (
              <div className="flex flex-col items-center py-12 text-center">
                <div className="w-12 h-12 rounded-xl bg-hover-row flex items-center justify-center mb-3">
                  <FileText className="w-5 h-5 text-text-placeholder" />
                </div>
                <p className="text-sm font-medium text-text-primary mb-1">{t('ex_no_drafts')}</p>
                <p className="text-xs text-text-placeholder max-w-[280px]">{t('ex_no_drafts_desc')}</p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr>
                      <th className={`${thClass} rounded-tl-lg`}>ID</th>
                      <th className={thClass}>Intent ID</th>
                      <th className={thClass}>{t('ex_broker')}</th>
                      <th className={thClass}>{t('ex_order_type')}</th>
                      <th className={`${thClass} text-right`}>Qty</th>
                      <th className={thClass}>{t('th_status')}</th>
                      <th className={`${thClass} rounded-tr-lg`}>{t('th_created')}</th>
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
                {t('ex_broker_account')}
              </h2>
              {brokerConnected && (
                <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wider bg-brand-light text-brand-dark">
                  {t('ex_broker_readonly')}
                </span>
              )}
            </div>
            {brokerConnected && brokerAccount ? (
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                <div>
                  <p className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder mb-1">{t('ex_broker')}</p>
                  <p className="text-sm font-semibold text-text-primary">Trading 212</p>
                </div>
                <div>
                  <p className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder mb-1">{t('ex_total_value')}</p>
                  <p className="text-sm font-semibold text-text-primary">
                    {brokerAccount.currencyCode === 'GBP' ? '\u00a3' : brokerAccount.currencyCode === 'USD' ? '$' : (brokerAccount.currencyCode || '')}{' '}
                    {formatNumber(brokerAccount.total ?? brokerAccount.totalValue ?? brokerAccount.value, 2)}
                  </p>
                </div>
                <div>
                  <p className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder mb-1">{t('ex_cash')}</p>
                  <p className="text-sm font-semibold text-text-primary">
                    {brokerAccount.currencyCode === 'GBP' ? '\u00a3' : brokerAccount.currencyCode === 'USD' ? '$' : (brokerAccount.currencyCode || '')}{' '}
                    {formatNumber(brokerAccount.cash ?? brokerAccount.free ?? 0, 2)}
                  </p>
                </div>
                <div>
                  <p className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder mb-1">{t('ex_positions_currency')}</p>
                  <p className="text-sm font-semibold text-text-primary">
                    {brokerPositions.length} &middot; {brokerAccount.currencyCode || t('ex_na')}
                  </p>
                </div>
              </div>
            ) : (
              <div className="flex flex-col items-center py-12 text-center">
                <div className="w-12 h-12 rounded-xl bg-hover-row flex items-center justify-center mb-3">
                  <Unplug className="w-5 h-5 text-text-placeholder" />
                </div>
                <p className="text-sm font-medium text-text-primary mb-1">{t('ex_broker_not_connected')}</p>
                <p className="text-xs text-text-placeholder max-w-[320px]">
                  {t('ex_broker_config')}
                </p>
              </div>
            )}
          </div>

          {/* Broker Positions Table */}
          <div className="bg-card rounded-xl border border-border shadow-card p-6 mb-6">
            <div className="flex items-center justify-between mb-5">
              <h2 className="text-base font-bold text-text-primary flex items-center gap-2">
                <Package size={18} className="text-brand" />
                {t('ex_broker_positions')}
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
                      <th className={`${thClass} rounded-tl-lg`}>{t('ex_ticker')}</th>
                      <th className={thClass}>{t('ex_name')}</th>
                      <th className={`${thClass} text-right`}>Qty</th>
                      <th className={`${thClass} text-right`}>{t('ex_avg_cost')}</th>
                      <th className={`${thClass} text-right`}>{t('ex_current')}</th>
                      <th className={`${thClass} text-right rounded-tr-lg`}>{t('ex_pnl')}</th>
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
                <p className="text-sm font-medium text-text-primary mb-1">{t('ex_no_positions')}</p>
                <p className="text-xs text-text-placeholder max-w-[280px]">Your Trading 212 account has no open positions.</p>
              </div>
            ) : (
              <div className="flex flex-col items-center py-12 text-center">
                <div className="w-12 h-12 rounded-xl bg-hover-row flex items-center justify-center mb-3">
                  <Unplug className="w-5 h-5 text-text-placeholder" />
                </div>
                <p className="text-sm font-medium text-text-primary mb-1">{t('ex_broker_not_connected')}</p>
                <p className="text-xs text-text-placeholder max-w-[320px]">
                  {t('ex_broker_config')}
                </p>
              </div>
            )}
          </div>

          {/* Recent Broker Orders */}
          <div className="bg-card rounded-xl border border-border shadow-card p-6 mb-6">
            <div className="flex items-center justify-between mb-5">
              <h2 className="text-base font-bold text-text-primary flex items-center gap-2">
                <ShoppingCart size={18} className="text-brand" />
                {t('ex_recent_orders')}
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
                      <th className={thClass}>{t('ex_ticker')}</th>
                      <th className={thClass}>Side</th>
                      <th className={`${thClass} text-right`}>Qty</th>
                      <th className={`${thClass} text-right`}>{t('bt_price')}</th>
                      <th className={thClass}>{t('th_status')}</th>
                      <th className={`${thClass} rounded-tr-lg`}>{t('bt_date')}</th>
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
                <p className="text-sm font-medium text-text-primary mb-1">{t('ex_no_orders')}</p>
                <p className="text-xs text-text-placeholder max-w-[280px]">No orders have been placed through Trading 212 recently.</p>
              </div>
            ) : (
              <div className="flex flex-col items-center py-12 text-center">
                <div className="w-12 h-12 rounded-xl bg-hover-row flex items-center justify-center mb-3">
                  <Unplug className="w-5 h-5 text-text-placeholder" />
                </div>
                <p className="text-sm font-medium text-text-primary mb-1">{t('ex_broker_not_connected')}</p>
                <p className="text-xs text-text-placeholder max-w-[320px]">
                  {t('ex_broker_config')}
                </p>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
