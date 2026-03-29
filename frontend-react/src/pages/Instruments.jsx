import { useState, useEffect, Fragment } from 'react';
import {
  RefreshCw, ChevronDown, ChevronRight, Globe2, Search,
  CandlestickChart, Tag, Building2, DollarSign, Activity
} from 'lucide-react';
import { apiFetch } from '../hooks/useApi';
import { useI18n } from '../hooks/useI18n';
import { formatDate, truncateId } from '../utils';

export default function Instruments() {
  const { t } = useI18n();
  const [instruments, setInstruments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [expandedId, setExpandedId] = useState(null);
  const [detail, setDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [search, setSearch] = useState('');

  const fetchInstruments = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch('/instruments?limit=50');
      setInstruments(Array.isArray(res) ? res : res.items || res.instruments || res.data || []);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchInstruments(); }, []);

  const handleRowClick = async (inst) => {
    const id = inst.instrument_id || inst.id;
    if (expandedId === id) {
      setExpandedId(null);
      setDetail(null);
      return;
    }
    setExpandedId(id);
    setDetailLoading(true);
    try {
      const res = await apiFetch(`/instruments/${id}`);
      setDetail(res);
    } catch {
      setDetail(null);
    } finally {
      setDetailLoading(false);
    }
  };

  const filtered = instruments.filter((inst) => {
    const q = search.toLowerCase();
    if (!q) return true;
    return (
      (inst.ticker || '').toLowerCase().includes(q) ||
      (inst.issuer_name_current || inst.name || '').toLowerCase().includes(q) ||
      (inst.asset_type || '').toLowerCase().includes(q)
    );
  });

  return (
    <div>
      {/* Page Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
        <div className="min-w-0">
          <h1 className="text-2xl font-bold text-text-primary tracking-tight flex items-center gap-2">
            <CandlestickChart size={24} className="text-brand shrink-0" />
            {t('inst_title')}
          </h1>
          <p className="text-sm text-text-secondary mt-1">
            {t('inst_subtitle')}
          </p>
        </div>
        <button
          onClick={fetchInstruments}
          className="inline-flex items-center gap-2 px-5 h-9 bg-gradient-to-r from-brand to-brand-dark text-white font-semibold text-sm rounded-lg shadow-[0_4px_14px_rgba(103,194,58,0.25)] hover:brightness-105 transition-all cursor-pointer shrink-0"
        >
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
          {t('refresh')}
        </button>
      </div>

      {/* Search */}
      <div className="relative w-full max-w-sm mb-4">
        <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-placeholder pointer-events-none" />
        <input
          type="text"
          placeholder={t('inst_search_ph')}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full h-10 pl-9 pr-4 bg-card border border-border rounded-lg text-sm focus:border-brand focus:ring-2 focus:ring-brand-light outline-none transition-all"
        />
      </div>

      {/* Table Card */}
      <div className="bg-card rounded-xl border border-border shadow-card p-4 sm:p-6 mb-6 overflow-hidden">
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-base font-bold text-text-primary">
            {t('inst_universe')}
          </h2>
          <span className="text-xs text-text-placeholder">
            {filtered.length} {t('common_instruments')}
          </span>
        </div>

        {error && (
          <div className="text-sm text-red-500 mb-4 p-3 bg-red-50 rounded-lg">
            {t('inst_load_fail')}: {error}
          </div>
        )}

        {loading ? (
          <div className="flex items-center justify-center py-16 text-text-placeholder text-sm">
            <RefreshCw size={16} className="animate-spin mr-2" /> {t('inst_loading')}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr>
                  <th className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder bg-hover-row px-4 py-3 text-left rounded-tl-lg" />
                  <th className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder bg-hover-row px-4 py-3 text-left">{t('th_ticker')}</th>
                  <th className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder bg-hover-row px-4 py-3 text-left">{t('th_name')}</th>
                  <th className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder bg-hover-row px-4 py-3 text-left">{t('th_asset')}</th>
                  <th className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder bg-hover-row px-4 py-3 text-left">{t('th_exchange')}</th>
                  <th className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder bg-hover-row px-4 py-3 text-left">{t('th_currency')}</th>
                  <th className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder bg-hover-row px-4 py-3 text-left">{t('th_status')}</th>
                  <th className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder bg-hover-row px-4 py-3 text-left rounded-tr-lg">{t('th_ids')}</th>
                </tr>
              </thead>
              <tbody>
                {filtered.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="px-4 py-12 text-center text-text-placeholder text-sm">
                      {t('inst_none')}
                    </td>
                  </tr>
                ) : (
                  filtered.map((inst) => {
                    const id = inst.instrument_id || inst.id;
                    const isExpanded = expandedId === id;
                    return (
                      <Fragment key={id}>
                        <tr
                          onClick={() => handleRowClick(inst)}
                          className="hover:bg-hover-row cursor-pointer transition-colors"
                        >
                          <td className="px-4 py-3 border-b border-border/50 w-8">
                            {isExpanded ? (
                              <ChevronDown size={14} className="text-brand" />
                            ) : (
                              <ChevronRight size={14} className="text-text-placeholder" />
                            )}
                          </td>
                          <td className="px-4 py-3 border-b border-border/50 font-semibold text-text-primary">
                            {inst.ticker || truncateId(id)}
                          </td>
                          <td className="px-4 py-3 border-b border-border/50 text-text-secondary">
                            {inst.issuer_name_current || inst.name || '--'}
                          </td>
                          <td className="px-4 py-3 border-b border-border/50">
                            <span className="inline-flex items-center gap-1 text-text-secondary">
                              <Tag size={12} className="text-text-placeholder" />
                              {inst.asset_type || '--'}
                            </span>
                          </td>
                          <td className="px-4 py-3 border-b border-border/50 text-text-secondary">
                            <span className="inline-flex items-center gap-1">
                              <Building2 size={12} className="text-text-placeholder" />
                              {inst.exchange_primary || inst.exchange || '--'}
                            </span>
                          </td>
                          <td className="px-4 py-3 border-b border-border/50 text-text-secondary">
                            <span className="inline-flex items-center gap-1">
                              <DollarSign size={12} className="text-text-placeholder" />
                              {inst.currency || '--'}
                            </span>
                          </td>
                          <td className="px-4 py-3 border-b border-border/50">
                            <span
                              className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wider ${
                                (inst.is_active === true || (inst.status || '').toUpperCase() === 'ACTIVE')
                                  ? 'bg-brand-light text-brand-dark'
                                  : 'bg-red-50 text-red-500'
                              }`}
                            >
                              <Activity size={10} className="mr-1" />
                              {inst.is_active === true ? 'ACTIVE' : inst.is_active === false ? 'INACTIVE' : (inst.status || '--')}
                            </span>
                          </td>
                          <td className="px-4 py-3 border-b border-border/50 text-text-placeholder text-xs">
                            {inst.isin || inst.figi || truncateId(id)}
                          </td>
                        </tr>

                        {/* Expanded Detail */}
                        {isExpanded && (
                          <tr>
                            <td colSpan={8} className="px-4 py-0 border-b border-border/50 bg-hover-row/30">
                              <div className="py-4">
                                {detailLoading ? (
                                  <div className="flex items-center text-sm text-text-placeholder py-4">
                                    <RefreshCw size={14} className="animate-spin mr-2" /> {t('inst_loading')}
                                  </div>
                                ) : detail ? (
                                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                    {/* Identifiers */}
                                    <div>
                                      <h4 className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder mb-3">
                                        {t('inst_identifiers')}
                                      </h4>
                                      <div className="overflow-x-auto">
                                        <table className="w-full text-sm">
                                          <thead>
                                            <tr>
                                              <th className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder bg-hover-row px-3 py-2 text-left rounded-tl-lg">{t('inst_type')}</th>
                                              <th className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder bg-hover-row px-3 py-2 text-left rounded-tr-lg">{t('inst_value')}</th>
                                            </tr>
                                          </thead>
                                          <tbody>
                                            {(detail.identifiers || []).length > 0 ? (
                                              detail.identifiers.map((ident, i) => (
                                                <tr key={i}>
                                                  <td className="px-3 py-2 border-b border-border/50 font-medium text-text-primary">
                                                    {ident.id_type || ident.type || ident.identifier_type || '--'}
                                                  </td>
                                                  <td className="px-3 py-2 border-b border-border/50 text-text-secondary font-mono text-xs">
                                                    {ident.id_value || ident.value || ident.identifier_value || '--'}
                                                  </td>
                                                </tr>
                                              ))
                                            ) : (
                                              <tr>
                                                <td colSpan={2} className="px-3 py-4 text-center text-text-placeholder text-xs">
                                                  {t('inst_no_ids')}
                                                </td>
                                              </tr>
                                            )}
                                          </tbody>
                                        </table>
                                      </div>
                                    </div>

                                    {/* Ticker History */}
                                    <div>
                                      <h4 className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder mb-3">
                                        {t('inst_ticker_history')}
                                      </h4>
                                      <div className="overflow-x-auto">
                                        <table className="w-full text-sm">
                                          <thead>
                                            <tr>
                                              <th className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder bg-hover-row px-3 py-2 text-left rounded-tl-lg">{t('th_ticker')}</th>
                                              <th className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder bg-hover-row px-3 py-2 text-left">{t('inst_from')}</th>
                                              <th className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder bg-hover-row px-3 py-2 text-left rounded-tr-lg">{t('inst_to')}</th>
                                            </tr>
                                          </thead>
                                          <tbody>
                                            {(detail.ticker_history || []).length > 0 ? (
                                              detail.ticker_history.map((th, i) => (
                                                <tr key={i}>
                                                  <td className="px-3 py-2 border-b border-border/50 font-semibold text-text-primary">
                                                    {th.ticker || '--'}
                                                  </td>
                                                  <td className="px-3 py-2 border-b border-border/50 text-text-secondary">
                                                    {formatDate(th.effective_from || th.valid_from || th.start_date)}
                                                  </td>
                                                  <td className="px-3 py-2 border-b border-border/50 text-text-secondary">
                                                    {th.effective_to || th.valid_to || th.end_date ? formatDate(th.effective_to || th.valid_to || th.end_date) : t('inst_present')}
                                                  </td>
                                                </tr>
                                              ))
                                            ) : (
                                              <tr>
                                                <td colSpan={3} className="px-3 py-4 text-center text-text-placeholder text-xs">
                                                  {t('inst_no_history')}
                                                </td>
                                              </tr>
                                            )}
                                          </tbody>
                                        </table>
                                      </div>
                                    </div>
                                  </div>
                                ) : (
                                  <div className="text-sm text-text-placeholder py-4">
                                    {t('inst_no_detail')}
                                  </div>
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
