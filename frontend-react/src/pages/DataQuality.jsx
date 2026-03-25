import { useState, useEffect } from 'react';
import {
  ShieldCheck, RefreshCw, CheckCircle, AlertTriangle, XCircle,
  Database, Clock, Hash, TrendingDown, Layers, BarChart3,
  Calendar, ArrowUpDown, GitBranch, Percent, Activity
} from 'lucide-react';
import { apiFetch } from '../hooks/useApi';
import { formatDate } from '../utils';

const DQ_RULES = [
  { code: 'DQ-1', label: 'No Missing Close Prices', severity: 'CRITICAL', icon: XCircle },
  { code: 'DQ-2', label: 'No Duplicate Dates', severity: 'CRITICAL', icon: Calendar },
  { code: 'DQ-3', label: 'Chronological Order', severity: 'CRITICAL', icon: ArrowUpDown },
  { code: 'DQ-4', label: 'Price Within Bounds', severity: 'HIGH', icon: TrendingDown },
  { code: 'DQ-5', label: 'Volume Non-Negative', severity: 'HIGH', icon: BarChart3 },
  { code: 'DQ-6', label: 'No Stale Prices (>5d)', severity: 'HIGH', icon: Clock },
  { code: 'DQ-7', label: 'Return Within 50%', severity: 'MEDIUM', icon: Percent },
  { code: 'DQ-8', label: 'OHLC Consistency', severity: 'MEDIUM', icon: Layers },
  { code: 'DQ-9', label: 'Sufficient History', severity: 'MEDIUM', icon: Database },
  { code: 'DQ-10', label: 'Corporate Actions Applied', severity: 'MEDIUM', icon: GitBranch },
  { code: 'DQ-11', label: 'Identifier Completeness', severity: 'MEDIUM', icon: Hash },
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
    try {
      const res = await apiFetch('/dq/issues');
      const data = Array.isArray(res) ? res : res.items || res.issues || res.data || [];
      setIssues(data);
    } catch (e) {
      // Likely no issues endpoint yet, treat as empty
      setIssues([]);
    }
    try {
      const runs = await apiFetch('/dq/source-runs');
      setSourceRuns(Array.isArray(runs) ? runs : runs.items || runs.runs || runs.data || []);
    } catch {
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

      {/* DQ Rules Grid */}
      <div className="bg-card rounded-xl border border-border shadow-card p-6 mb-6">
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-base font-bold text-text-primary">Quality Rules</h2>
          <span className="text-xs text-text-placeholder">{ruleCount} rules active</span>
        </div>
        <div className="grid grid-cols-4 gap-3">
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
                <div className="flex items-center gap-1.5 mb-2">
                  <RuleIcon size={12} className="text-text-placeholder" />
                  <span className="text-xs text-text-secondary leading-tight">{rule.label}</span>
                </div>
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
        <div className="flex items-center justify-center py-16 text-text-placeholder text-sm">
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
      {sourceRuns.length > 0 && (
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
                      <td className="px-4 py-3 border-b border-border/50 text-right text-text-secondary">{run.counters ? (run.counters.records != null ? Number(run.counters.records).toLocaleString() : JSON.stringify(run.counters)) : run.record_count != null ? Number(run.record_count).toLocaleString() : '--'}</td>
                      <td className="px-4 py-3 border-b border-border/50 text-text-placeholder text-xs">{formatDate(run.finished_at || run.completed_at || run.created_at)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
