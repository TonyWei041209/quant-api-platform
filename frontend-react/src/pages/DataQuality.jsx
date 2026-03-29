import { useState, useEffect } from 'react';
import {
  ShieldCheck, RefreshCw, CheckCircle, AlertTriangle, XCircle,
  Database, Clock, Hash, TrendingDown, Layers, BarChart3,
  Calendar, ArrowUpDown, GitBranch, Percent, Activity
} from 'lucide-react';
import { apiFetch } from '../hooks/useApi';
import { useI18n } from '../hooks/useI18n';
import { formatDate } from '../utils';

const DQ_RULES = [
  { code: 'DQ-1', labelKey: 'dq_r1_label', descKey: 'dq_r1_desc', severity: 'CRITICAL', icon: BarChart3 },
  { code: 'DQ-2', labelKey: 'dq_r2_label', descKey: 'dq_r2_desc', severity: 'CRITICAL', icon: TrendingDown },
  { code: 'DQ-3', labelKey: 'dq_r3_label', descKey: 'dq_r3_desc', severity: 'HIGH', icon: Hash },
  { code: 'DQ-4', labelKey: 'dq_r4_label', descKey: 'dq_r4_desc', severity: 'MEDIUM', icon: Calendar },
  { code: 'DQ-5', labelKey: 'dq_r5_label', descKey: 'dq_r5_desc', severity: 'HIGH', icon: GitBranch },
  { code: 'DQ-6', labelKey: 'dq_r6_label', descKey: 'dq_r6_desc', severity: 'CRITICAL', icon: Clock },
  { code: 'DQ-7', labelKey: 'dq_r7_label', descKey: 'dq_r7_desc', severity: 'HIGH', icon: ArrowUpDown },
  { code: 'DQ-8', labelKey: 'dq_r8_label', descKey: 'dq_r8_desc', severity: 'MEDIUM', icon: Activity },
  { code: 'DQ-9', labelKey: 'dq_r9_label', descKey: 'dq_r9_desc', severity: 'HIGH', icon: Layers },
  { code: 'DQ-10', labelKey: 'dq_r10_label', descKey: 'dq_r10_desc', severity: 'LOW', icon: Database },
  { code: 'DQ-11', labelKey: 'dq_r11_label', descKey: 'dq_r11_desc', severity: 'CRITICAL', icon: ShieldCheck },
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
  const { t } = useI18n();
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
      <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
        <div className="min-w-0">
          <h1 className="text-2xl font-bold text-text-primary tracking-tight flex items-center gap-2">
            <ShieldCheck size={24} className="text-brand shrink-0" />
            {t('dq_title')}
          </h1>
          <p className="text-sm text-text-secondary mt-1">
            {ruleCount} {t('dq_rules')} // {issueCount} {t('dq_issues')}{issueCount !== 1 ? '' : ''}
          </p>
        </div>
        <button
          onClick={fetchData}
          className="inline-flex items-center gap-2 px-5 h-9 bg-gradient-to-r from-brand to-brand-dark text-white font-semibold text-sm rounded-lg shadow-[0_4px_14px_rgba(103,194,58,0.25)] hover:brightness-105 transition-all cursor-pointer shrink-0"
        >
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
          {t('dq_refresh')}
        </button>
      </div>

      {/* Summary Bar */}
      <div className={`flex flex-wrap items-center gap-3 sm:gap-4 px-4 sm:px-5 py-3 mb-6 rounded-xl border ${
        issueCount === 0
          ? 'bg-brand-light/30 border-brand/20'
          : 'bg-amber-50 border-amber-200'
      }`}>
        {issueCount === 0 ? (
          <>
            <CheckCircle size={20} className="text-brand shrink-0" />
            <div>
              <span className="text-sm font-semibold text-brand-dark">{t('dash_all_clear')}</span>
              <span className="text-sm text-brand-dark/70 ml-2">{t('dq_all_clear_banner')}</span>
            </div>
          </>
        ) : (
          <>
            <AlertTriangle size={20} className="text-amber-500 shrink-0" />
            <div>
              <span className="text-sm font-semibold text-amber-700">{issueCount} {t('dq_detected_plural')}</span>
              <span className="text-sm text-amber-600 ml-2">{t('dq_review')}</span>
            </div>
          </>
        )}
      </div>

      {/* Source Health Summary */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3 mb-6">
        {[
          { name: 'FMP', roleKey: 'dq_src_fmp_role', status: 'production' },
          { name: 'SEC EDGAR', roleKey: 'dq_src_sec_role', status: 'production' },
          { name: 'Polygon', roleKey: 'dq_src_poly_role', status: 'production' },
          { name: 'OpenFIGI', roleKey: 'dq_src_figi_role', status: 'production' },
          { name: 'Trading 212', roleKey: 'dq_src_t212_role', status: 'verified' },
        ].map(src => (
          <div key={src.name} className="bg-card rounded-xl border border-border shadow-card p-4">
            <div className="flex items-center justify-between mb-1">
              <span className="text-sm font-bold text-text-primary">{src.name}</span>
              <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wider ${
                src.status === 'production' ? 'bg-brand-light text-brand-dark' : 'bg-blue-50 text-blue-600'
              }`}>{src.status}</span>
            </div>
            <p className="text-[11px] text-text-placeholder">{t(src.roleKey)}</p>
          </div>
        ))}
      </div>

      {/* DQ Rules Grid */}
      <div className="bg-card rounded-xl border border-border shadow-card p-4 sm:p-6 mb-6">
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-base font-bold text-text-primary">{t('dq_quality')}</h2>
          <span className="text-xs text-text-placeholder">{ruleCount} {t('common_rules_active')}</span>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
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
                  <span className="text-xs text-text-secondary leading-tight">{t(rule.labelKey)}</span>
                </div>
                <p className="text-[11px] text-text-placeholder leading-snug mb-2">{t(rule.descKey)}</p>
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
          <RefreshCw size={16} className="animate-spin mr-2" /> {t('dq_checking')}
        </div>
      ) : issueCount === 0 ? (
        <div className="bg-card rounded-xl border border-border shadow-card p-6 mb-6">
          <div className="flex flex-col items-center justify-center py-12">
            <div className="w-16 h-16 rounded-full bg-brand-light flex items-center justify-center mb-4">
              <CheckCircle size={32} className="text-brand" />
            </div>
            <h3 className="text-lg font-bold text-text-primary mb-1">{t('dq_no_issues')}</h3>
            <p className="text-sm text-text-placeholder">
              {t('dq_all_pass')}
            </p>
          </div>
        </div>
      ) : (
        <div className="bg-card rounded-xl border border-border shadow-card p-6 mb-6">
          <div className="flex items-center justify-between mb-5">
            <h2 className="text-base font-bold text-text-primary">{t('dq_active_issues')}</h2>
            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wider bg-red-50 text-red-500">
              {issueCount} {t('dq_issues')}
            </span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr>
                  <th className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder bg-hover-row px-4 py-3 text-left rounded-tl-lg">{t('th_rule')}</th>
                  <th className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder bg-hover-row px-4 py-3 text-left">{t('th_instrument')}</th>
                  <th className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder bg-hover-row px-4 py-3 text-left">{t('th_severity')}</th>
                  <th className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder bg-hover-row px-4 py-3 text-left">{t('th_description')}</th>
                  <th className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder bg-hover-row px-4 py-3 text-left rounded-tr-lg">{t('th_detected')}</th>
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
            <h2 className="text-base font-bold text-text-primary">{t('dq_source_runs')}</h2>
            <span className="text-xs text-text-placeholder">{sourceRuns.length} runs</span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr>
                  <th className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder bg-hover-row px-4 py-3 text-left rounded-tl-lg">{t('th_run_id')}</th>
                  <th className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder bg-hover-row px-4 py-3 text-left">{t('th_source')}</th>
                  <th className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder bg-hover-row px-4 py-3 text-left">{t('th_status')}</th>
                  <th className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder bg-hover-row px-4 py-3 text-right">{t('th_records')}</th>
                  <th className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder bg-hover-row px-4 py-3 text-left rounded-tr-lg">{t('th_completed')}</th>
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
          <h2 className="text-base font-bold text-text-primary mb-5">{t('dq_source_runs')}</h2>
          <div className="flex flex-col items-center py-8 text-center">
            <div className="w-12 h-12 rounded-xl bg-surface flex items-center justify-center mb-3">
              <Database className="w-5 h-5 text-muted" />
            </div>
            <p className="text-sm font-medium text-text-primary mb-1">{t('dq_no_runs')}</p>
            <p className="text-xs text-text-placeholder max-w-[300px]">{t('dq_run_cli')}</p>
          </div>
        </div>
      )}
    </div>
  );
}
