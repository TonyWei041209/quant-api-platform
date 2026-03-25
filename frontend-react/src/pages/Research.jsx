import { useState, useEffect } from 'react';
import {
  FlaskConical, ShieldCheck, Play, TrendingUp, BarChart3,
  TrendingDown, Search, Filter, Layers, Award, RefreshCw, FileJson
} from 'lucide-react';
import { apiFetch, apiPost } from '../hooks/useApi';
import { formatDate } from '../utils';

export default function Research() {
  const [instruments, setInstruments] = useState([]);
  const [selectedInstrument, setSelectedInstrument] = useState('');
  const [asOfDate, setAsOfDate] = useState('');
  const [eventTicker, setEventTicker] = useState('');
  const [eventWindow, setEventWindow] = useState('5');
  const [results, setResults] = useState(null);
  const [resultsLoading, setResultsLoading] = useState(false);
  const [resultsError, setResultsError] = useState(null);
  const [resultsLabel, setResultsLabel] = useState('');

  useEffect(() => {
    apiFetch('/instruments?limit=50')
      .then((res) => {
        const list = Array.isArray(res) ? res : res.instruments || res.data || [];
        setInstruments(list);
      })
      .catch(() => {});
  }, []);

  const runAnalysis = async (type) => {
    if (!selectedInstrument) return;
    setResultsLoading(true);
    setResultsError(null);
    setResultsLabel(`${type} Analysis`);
    try {
      const params = asOfDate ? `?as_of_date=${asOfDate}` : '';
      const res = await apiFetch(`/research/instrument/${selectedInstrument}/${type}${params}`);
      setResults(res);
    } catch (e) {
      setResultsError(e.message);
      setResults(null);
    } finally {
      setResultsLoading(false);
    }
  };

  const runEventStudy = async () => {
    if (!eventTicker) return;
    setResultsLoading(true);
    setResultsError(null);
    setResultsLabel('Event Study');
    try {
      const res = await apiPost('/research/event-study/earnings', {
        ticker: eventTicker,
        window: parseInt(eventWindow) || 5,
      });
      setResults(res);
    } catch (e) {
      setResultsError(e.message);
      setResults(null);
    } finally {
      setResultsLoading(false);
    }
  };

  const runScreener = async (type) => {
    setResultsLoading(true);
    setResultsError(null);
    setResultsLabel(`${type} Screener`);
    try {
      const res = await apiFetch(`/research/screener/${type}`);
      setResults(res);
    } catch (e) {
      setResultsError(e.message);
      setResults(null);
    } finally {
      setResultsLoading(false);
    }
  };

  return (
    <div>
      {/* Page Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-text-primary tracking-tight flex items-center gap-2">
          <FlaskConical size={24} className="text-brand" />
          Research Workbench
        </h1>
        <p className="text-sm text-text-secondary mt-1">
          Point-in-time analytics, event studies, and factor screeners
        </p>
      </div>

      {/* PIT Notice Banner */}
      <div className="flex items-center gap-3 px-5 py-3 mb-6 rounded-xl bg-brand-light border border-brand/20">
        <ShieldCheck size={20} className="text-brand-dark flex-shrink-0" />
        <div>
          <span className="text-sm font-semibold text-brand-dark">Point-in-Time Guarantee</span>
          <span className="text-sm text-brand-dark/80 ml-2">
            All research queries use as-of-date semantics to prevent look-ahead bias
          </span>
        </div>
      </div>

      {/* Quick Analysis + Event Study */}
      <div className="grid grid-cols-2 gap-6 mb-6">
        {/* Quick Analysis */}
        <div className="bg-card rounded-xl border border-border shadow-card p-6">
          <div className="flex items-center justify-between mb-5">
            <h2 className="text-base font-bold text-text-primary">Quick Analysis</h2>
          </div>

          <div className="space-y-4">
            <div>
              <label className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder mb-1.5 block">
                Instrument
              </label>
              <select
                value={selectedInstrument}
                onChange={(e) => setSelectedInstrument(e.target.value)}
                className="w-full h-10 px-4 bg-card border border-border rounded-lg text-sm focus:border-brand focus:ring-2 focus:ring-brand-light outline-none transition-all"
              >
                <option value="">Select instrument...</option>
                {instruments.map((inst) => {
                  const id = inst.instrument_id || inst.id;
                  return (
                    <option key={id} value={id}>
                      {inst.ticker} - {inst.name}
                    </option>
                  );
                })}
              </select>
            </div>

            <div>
              <label className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder mb-1.5 block">
                As-of Date
              </label>
              <input
                type="date"
                value={asOfDate}
                onChange={(e) => setAsOfDate(e.target.value)}
                className="w-full h-10 px-4 bg-card border border-border rounded-lg text-sm focus:border-brand focus:ring-2 focus:ring-brand-light outline-none transition-all"
              />
            </div>

            <div className="flex flex-wrap gap-2 pt-1">
              <button
                onClick={() => runAnalysis('summary')}
                disabled={!selectedInstrument || resultsLoading}
                className="inline-flex items-center gap-2 px-5 h-9 bg-gradient-to-r from-brand to-brand-dark text-white font-semibold text-sm rounded-lg shadow-[0_4px_14px_rgba(103,194,58,0.25)] hover:brightness-105 transition-all cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <Play size={14} /> Summary
              </button>
              <button
                onClick={() => runAnalysis('performance')}
                disabled={!selectedInstrument || resultsLoading}
                className="inline-flex items-center gap-2 px-4 h-9 border border-border rounded-lg text-sm font-medium text-text-secondary hover:bg-hover transition-all cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <TrendingUp size={14} /> Performance
              </button>
              <button
                onClick={() => runAnalysis('valuation')}
                disabled={!selectedInstrument || resultsLoading}
                className="inline-flex items-center gap-2 px-4 h-9 border border-border rounded-lg text-sm font-medium text-text-secondary hover:bg-hover transition-all cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <BarChart3 size={14} /> Valuation
              </button>
              <button
                onClick={() => runAnalysis('drawdown')}
                disabled={!selectedInstrument || resultsLoading}
                className="inline-flex items-center gap-2 px-4 h-9 border border-border rounded-lg text-sm font-medium text-text-secondary hover:bg-hover transition-all cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <TrendingDown size={14} /> Drawdown
              </button>
            </div>
          </div>
        </div>

        {/* Event Study */}
        <div className="bg-card rounded-xl border border-border shadow-card p-6">
          <div className="flex items-center justify-between mb-5">
            <h2 className="text-base font-bold text-text-primary">Event Study</h2>
          </div>

          <div className="space-y-4">
            <div>
              <label className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder mb-1.5 block">
                Ticker
              </label>
              <input
                type="text"
                placeholder="e.g. AAPL"
                value={eventTicker}
                onChange={(e) => setEventTicker(e.target.value)}
                className="w-full h-10 px-4 bg-card border border-border rounded-lg text-sm focus:border-brand focus:ring-2 focus:ring-brand-light outline-none transition-all"
              />
            </div>

            <div>
              <label className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder mb-1.5 block">
                Window (days)
              </label>
              <input
                type="number"
                value={eventWindow}
                onChange={(e) => setEventWindow(e.target.value)}
                className="w-full h-10 px-4 bg-card border border-border rounded-lg text-sm focus:border-brand focus:ring-2 focus:ring-brand-light outline-none transition-all"
              />
            </div>

            <button
              onClick={runEventStudy}
              disabled={!eventTicker || resultsLoading}
              className="inline-flex items-center gap-2 px-5 h-9 bg-gradient-to-r from-brand to-brand-dark text-white font-semibold text-sm rounded-lg shadow-[0_4px_14px_rgba(103,194,58,0.25)] hover:brightness-105 transition-all cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <Play size={14} /> RUN STUDY
            </button>
          </div>
        </div>
      </div>

      {/* Screeners */}
      <div className="bg-card rounded-xl border border-border shadow-card p-6 mb-6">
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-base font-bold text-text-primary">Screeners</h2>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <button
            onClick={() => runScreener('liquidity')}
            disabled={resultsLoading}
            className="inline-flex items-center gap-2 px-4 h-9 border border-border rounded-lg text-sm font-medium text-text-secondary hover:bg-hover transition-all cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Filter size={14} /> Liquidity Screener
          </button>
          <button
            onClick={() => runScreener('returns')}
            disabled={resultsLoading}
            className="inline-flex items-center gap-2 px-4 h-9 border border-border rounded-lg text-sm font-medium text-text-secondary hover:bg-hover transition-all cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <TrendingUp size={14} /> Returns Screener
          </button>
          <button
            onClick={() => runScreener('fundamentals')}
            disabled={resultsLoading}
            className="inline-flex items-center gap-2 px-4 h-9 border border-border rounded-lg text-sm font-medium text-text-secondary hover:bg-hover transition-all cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Layers size={14} /> Fundamentals Screener
          </button>
          <button
            onClick={() => runScreener('composite-rank')}
            disabled={resultsLoading}
            className="inline-flex items-center gap-2 px-4 h-9 border border-border rounded-lg text-sm font-medium text-text-secondary hover:bg-hover transition-all cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Award size={14} /> Composite Rank
          </button>
        </div>
      </div>

      {/* Results */}
      <div className="bg-card rounded-xl border border-border shadow-card p-6 mb-6">
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-base font-bold text-text-primary">
            {resultsLabel ? `Results: ${resultsLabel}` : 'Results'}
          </h2>
          {results && (
            <button
              onClick={() => { setResults(null); setResultsLabel(''); }}
              className="text-xs text-text-placeholder hover:text-text-secondary transition-colors cursor-pointer"
            >
              Clear
            </button>
          )}
        </div>

        {resultsLoading ? (
          <div className="flex items-center justify-center py-12 text-text-placeholder text-sm">
            <RefreshCw size={14} className="animate-spin mr-2" /> Running analysis...
          </div>
        ) : resultsError ? (
          <div className="text-sm text-red-500 p-3 bg-red-50 rounded-lg">
            {resultsError}
          </div>
        ) : results ? (
          <pre className="bg-hover-row rounded-lg p-4 text-xs text-text-secondary font-mono overflow-auto max-h-96">
            {JSON.stringify(results, null, 2)}
          </pre>
        ) : (
          <div className="flex flex-col items-center justify-center py-12 text-text-placeholder">
            <FileJson size={32} className="mb-3 opacity-40" />
            <p className="text-sm">Run an analysis to see results here</p>
          </div>
        )}
      </div>
    </div>
  );
}
