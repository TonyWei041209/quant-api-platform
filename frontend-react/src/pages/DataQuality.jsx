import { useState, useEffect } from 'react';
import {
  ShieldCheck, RefreshCw, CheckCircle, AlertTriangle, XCircle,
  Database, Clock, Hash, TrendingDown, Layers, BarChart3,
  Calendar, ArrowUpDown, GitBranch, Percent, Activity
} from 'lucide-react';
import { apiFetch } from '../hooks/useApi';
import { formatDate } from '../utils';

const DQ_RULES = [
  { code: 'DQ-1', label: 'OHLC Logic', desc: 'High \u2265 max(Open,Close,Low), Low \u2264 min(Open,Close,High)', severity: 'CRITICAL', icon: BarChart3 },
  { code: 'DQ-2', label: 'Non-Negative Values', desc: 'All prices \u2265 0 and volumes \u2265 0', severity: 'CRITICAL', icon: TrendingDown },
  { code: 'DQ-3', label: 'Duplicate Accession', desc: 'No duplicate filing accession numbers', severity: 'HIGH', icon: Hash },
  { code: 'DQ-4', label: 'Trading Day Consistency', desc: 'Price bars only on valid exchange trading days', severity: 'MEDIUM', icon: Calendar },
  { code: 'DQ-5', label: 'Corporate Action Validity', desc: 'Split ratio > 0, dividends \u2265 0, ex_date present', severity: 'HIGH', icon: GitBranch },
  { code: 'DQ-6', label: 'PIT Integrity', desc: 'Financial periods must have reported_at for PIT queries', severity: 'CRITICAL', icon: Clock },
  { code: 'DQ-7', label: 'Cross-Source Divergence', desc: 'Same instrument/date close prices within tolerance across sources', severity: 'HIGH', icon: ArrowUpDown },
  { code: 'DQ-8', label: 'Stale Price Detection', desc: 'No unexplained gaps exceeding configurable threshold', severity: 'MEDIUM', icon: Activity },
  { code: 'DQ-9', label: 'Ticker History Overlap', desc: 'No overlapping effective date intervals for same ticker', severity: 'HIGH', icon: Layers },
  { code: 'DQ-10', label: 'Orphan Identifiers', desc: 'All identifiers reference existing instruments', severity: 'LOW', icon: Database },
  { code: 'DQ-11', label: 'Raw/Adjusted Contamination', desc: 'No mixing of raw and adjusted prices in raw tables', severity: 'CRITICAL', icon: ShieldCheck },
];

const severityBadge = (severity) => {
  switch (severity) {
    case 'CRITICAL':
      return 'bg-red-50 text-red-500';
    case 'HIGH':
      return 'bg-amber-50 text-amber-600';
    case 'MEDIUM':
      return 'bg-brand-light text-brand-dark';
    default:
      return 'bg-hover-row text-text-placeholder';
  }
};

export default function DataQuality() {
  const [issues, setIssues] = useState([]);
  const [sourceRuns, setSourceRuns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    const [issuesRes, runsRes] = await Promise.allSettled([
      apiFetch('/dq/issues'),
      apiFetch('/dq/source-runs'),
    ]);
    if (issuesRes.status === 'fulfilled') {
      const data = issuesRes.value;
      setIssues(Array.isArray(data) ? data : data.items || data.issues || data.data || []);
    } else {
      setIssues([]);
    }
    if (runsRes.status === 'fulfilled') {
      const runs = runsRes.value;
      setSourceRuns(Array.isArray(runs) ? runs : runs.items || runs.runs || runs.data || []);
    } else {
      setSourceRuns([]);
    }
    setLoading(false);
  };

  useEffect(() => { fetchData(); }, []);

  const issueCount = issues.length;
  const ruleCount = DQ_RULES.length;

  return (
    <div>
      {/* Page Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-text-primary tracking-tight flex items-center gap-2">
            <ShieldCheck size={24} className="text-brand" />
            Data Quality Engine
          </h1>
          <p className="text-sm text-text-secondary mt-1">
            {ruleCount} Rules // {issueCount} Issue{issueCount !== 1 ? 's' : ''}
          </p>
        </div>
        <button
          onClick={fetchData}
          className="inline-flex items-center gap-2 px-5 h-9 bg-gradient-to-r from-brand to-brand-dark text-white font-semibold text-sm rounded-lg shadow-[0_4px_14px_rgba(103,194,58,0.25)] hover:brightness-105 transition-all cursor-pointer"
        >
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
          REFRESH
        </button>
      </div>

      {/* Summary Bar */}
      <div className={`flex items-center gap-4 px-5 py-3 mb-6 rounded-xl border ${
        issueCount === 0
          ? 'bg-brand-light/30 border-brand/20'
          : 'bg-amber-50 border-amber-200'
      }`}>
        {issueCount === 0 ? (
          <>
            <CheckCircle size={20} className="text-brand shrink-0" />
            <div>
              <span className="text-sm font-semibold text-brand-dark">All Clear</span>
              <span className="text-sm text-brand-dark/70 ml-2">All {ruleCount} data quality rules are passing</span>
            </div>
          </>
        ) : (
          <>
            <AlertTriangle size={20} className="text-amber-500 shrink-0" />
            <div>
              <span className="text-sm font-semibold text-amber-700">{issueCount} Issue{issueCount !== 1 ? 's' : ''} Detected</span>
              <span className="text-sm text-amber-600 ml-2">Review and resolve data quality issues below</span>
            </div>
          </>
        )}
      </div>

      {/* Source Health Summary */}
      <div className="grid grid-cols-5 gap-3 mb-6">
        {[
          { name: 'FMP', role: 'Prices & Financials', status: 'production' },
          { name: 'SEC EDGAR', role: 'Filings & PIT', status: 'production' },
          { name: 'Polygon', role: 'Corporate Actions', status: 'production' },
          { name: 'OpenFIGI', role: 'Identifiers', status: 'production' },
          { name: 'Trading 212', role: 'Broker Readonly', status: 'verified' },
        ].map(src => (
          <div key={src.name} className="bg-card rounded-xl border border-border shadow-card p-4">
            <div className="flex items-center justify-between mb-1">
              <span className="text-sm font-bold text-text-primary">{src.name}</span>
              <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wider ${
                src.status === 'production' ? 'bg-brand-light text-brand-dark' : 'bg-blue-50 text-blue-600'
              }`}>{src.status}</span>
            </div>
            <p className="text-[11px] text-text-placeholder">{src.role}</p>
          </div>
        ))}
      </div>

      {/* DQ Rules Grid */}
      <div className="bg-card rounded-xl border border-border shadow-card p-6 mb-6">
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-base font-bold text-text-primary">Quality Rules</h2>
          <span className="text-xs text-text-placeholder">{ruleCount} rules active</span>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {DQ_RULES.map((rule) => {
            const RuleIcon = rule.icon;
            const hasIssue = issues.some((iss) => (iss.rule_code || iss.rule || '').toUpperCase() === rule.code);
            return (
              <div
                key={rule.code}
                className={`rounded-lg border p-4 transition-all ${
                  hasIssue
                    ? 'border-red-200 bg-red-50/30'
                    : 'border-border bg-card hover:border-brand/30'
                }`}
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-bold text-text-primary">{rule.code}</span>
                  {hasIssue ? (
                    <AlertTriangle size={16} className="text-red-500" />
                  ) : (
                    <CheckCircle size={16} className="text-brand" />
                  )}
                </div>
                <div className="flex items-center gap-1.5 mb-1">
                  <RuleIcon size={12} className="text-text-placeholder" />
                  <span className="text-xs text-text-secondary leading-tight">{rule.label}</span>
                </div>
                <p className="text-[11px] text-text-placeholder leading-snug mb-2">{rule.desc}</p>
                <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wider ${severityBadge(rule.severity)}`}>
                  {rule.severity}
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Issues or Empty State */}
      {loading ? (
        <div className="flex items-center justify-center py-16 text-text-placeholder text-sm animate-pulse opacity-80">
          <RefreshCw size={16} className="animate-spin mr-2" /> Checking data quality...
        </div>
      ) : issueCount === 0 ? (
        <div className="bg-card rounded-xl border border-border shadow-card p-6 mb-6">
          <div className="flex flex-col items-center justify-center py-12">
            <div className="w-16 h-16 rounded-full bg-brand-light flex items-center justify-center mb-4">
              <CheckCircle size={32} className="text-brand" />
            </div>
            <h3 className="text-lg font-bold text-text-primary mb-1">No Data Issues</h3>
            <p className="text-sm text-text-placeholder">
              All {ruleCount} quality rules are passing. Your data is clean.
            </p>
          </div>
        </div>
      ) : (
        <div className="bg-card rounded-xl border border-border shadow-card p-6 mb-6">
          <div className="flex items-center justify-between mb-5">
            <h2 className="text-base font-bold text-text-primary">Active Issues</h2>
            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wider bg-red-50 text-red-500">
              {issueCount} issue{issueCount !== 1 ? 's' : ''}
            </span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr>
                  <th className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder bg-hover-row px-4 py-3 text-left rounded-tl-lg">Rule</th>
                  <th className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder bg-hover-row px-4 py-3 text-left">Instrument</th>
                  <th className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder bg-hover-row px-4 py-3 text-left">Severity</th>
                  <th className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder bg-hover-row px-4 py-3 text-left">Description</th>
                  <th className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder bg-hover-row px-4 py-3 text-left rounded-tr-lg">Detected</th>
                </tr>
              </thead>
              <tbody>
                {issues.map((iss, i) => (
                  <tr key={i} className="hover:bg-hover-row transition-colors">
                    <td className="px-4 py-3 border-b border-border/50 font-bold text-text-primary">{iss.rule_code || iss.rule || '--'}</td>
                    <td className="px-4 py-3 border-b border-border/50 text-text-secondary">{iss.record_key || iss.ticker || iss.instrument || '--'}</td>
                    <td className="px-4 py-3 border-b border-border/50">
                      <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wider ${severityBadge(iss.severity)}`}>
                        {iss.severity || '--'}
                      </span>
                    </td>
                    <td className="px-4 py-3 border-b border-border/50 text-text-secondary text-xs">{iss.details ? (typeof iss.details === 'string' ? iss.details : JSON.stringify(iss.details)) : iss.description || iss.message || '--'}</td>
                    <td className="px-4 py-3 border-b border-border/50 text-text-placeholder text-xs">{formatDate(iss.issue_time || iss.detected_at || iss.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Source Runs */}
      {sourceRuns.length > 0 ? (
        <div className="bg-card rounded-xl border border-border shadow-card p-6 mb-6">
          <div className="flex items-center justify-between mb-5">
            <h2 className="text-base font-bold text-text-primary">Source Runs</h2>
            <span className="text-xs text-text-placeholder">{sourceRuns.length} runs</span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr>
                  <th className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder bg-hover-row px-4 py-3 text-left rounded-tl-lg">Run ID</th>
                  <th className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder bg-hover-row px-4 py-3 text-left">Source</th>
                  <th className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder bg-hover-row px-4 py-3 text-left">Status</th>
                  <th className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder bg-hover-row px-4 py-3 text-right">Records</th>
                  <th className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder bg-hover-row px-4 py-3 text-left rounded-tr-lg">Completed</th>
                </tr>
              </thead>
              <tbody>
                {sourceRuns.map((run, i) => {
                  const id = run.run_id || run.id;
                  return (
                    <tr key={i} className="hover:bg-hover-row transition-colors">
                      <td className="px-4 py-3 border-b border-border/50 font-mono text-xs text-text-placeholder">{id ? String(id).substring(0, 8) : '--'}</td>
                      <td className="px-4 py-3 border-b border-border/50 font-semibold text-text-primary">{run.source || '--'}</td>
                      <td className="px-4 py-3 border-b border-border/50">
                        <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wider ${
                          (run.status || '').toUpperCase() === 'SUCCESS' || (run.status || '').toUpperCase() === 'COMPLETED'
                            ? 'bg-brand-light text-brand-dark'
                            : 'bg-amber-50 text-amber-600'
                        }`}>
                          {run.status || '--'}
                        </span>
                      </td>
                      <td className="px-4 py-3 border-b border-border/50 text-right text-text-secondary">
                        {(() => {
                          const c = run.counters;
                          if (!c) return run.record_count != null ? Number(run.record_count).toLocaleString() : '--';
                          if (typeof c === 'object') {
                            const total = c.records || c.total || c.inserted || c.processed;
                            return total != null ? Number(total).toLocaleString() : Object.entries(c).map(([k,v]) => `${k}: ${v}`).join(', ');
                          }
                          return String(c);
                        })()}
                      </td>
                      <td className="px-4 py-3 border-b border-border/50 text-text-placeholder text-xs">{formatDate(run.finished_at || run.completed_at || run.created_at)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        <div className="bg-card rounded-xl border border-border shadow-card p-6 mb-6">
          <h2 className="text-base font-bold text-text-primary mb-5">Source Runs</h2>
          <div className="flex flex-col items-center py-8 text-center">
            <div className="w-12 h-12 rounded-xl bg-surface flex items-center justify-center mb-3">
              <Database className="w-5 h-5 text-muted" />
            </div>
            <p className="text-sm font-medium text-text-primary mb-1">No Source Runs Recorded</p>
            <p className="text-xs text-text-placeholder max-w-[300px]">Run a data sync via CLI to see ingestion job history here.</p>
          </div>
        </div>
      )}
    </div>
  );
}
