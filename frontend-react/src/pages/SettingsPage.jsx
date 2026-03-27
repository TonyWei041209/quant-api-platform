import { useState, useEffect } from 'react';
import {
  Settings, Key, Flag, Shield, Database, CheckCircle, XCircle,
  Lock, RefreshCw, Clock, Gauge, AlertTriangle, Scale, Layers,
  Zap, Info, ExternalLink, Globe, FileText, BarChart3, TrendingUp,
  Wallet, Eye
} from 'lucide-react';
import { apiFetch } from '../hooks/useApi';
import { useI18n } from '../hooks/useI18n';

/* ─── Data Source Matrix (matches docs/source_matrix.md) ─── */
const DATA_SOURCES = [
  {
    name: 'FMP',
    fullName: 'Financial Modeling Prep',
    envKey: 'FMP_API_KEY',
    role: 'Primary',
    roleColor: 'brand',
    provides: 'EOD Prices, Financial Statements, Company Profiles, Earnings',
    impact: 'Core price and fundamental data. Platform cannot do price research or backtesting without this source.',
    frequency: 'Daily',
    icon: TrendingUp,
  },
  {
    name: 'SEC EDGAR',
    fullName: 'SEC EDGAR',
    envKey: 'SEC_USER_AGENT',
    role: 'Truth / PIT',
    roleColor: 'blue',
    provides: 'Filings, CompanyFacts, Security Master Bootstrap',
    impact: 'PIT truth path for financials. Security Master initialization depends on this.',
    frequency: 'Daily',
    icon: FileText,
    noKeyNeeded: true,
  },
  {
    name: 'Polygon',
    fullName: 'Polygon.io / Massive',
    envKey: 'MASSIVE_API_KEY',
    role: 'Corp Actions',
    roleColor: 'purple',
    provides: 'Splits, Dividends, Secondary Raw Price Validation',
    impact: 'Adjusted price calculations depend on corporate action data from this source.',
    frequency: 'Daily',
    icon: BarChart3,
  },
  {
    name: 'OpenFIGI',
    fullName: 'OpenFIGI',
    envKey: 'OPENFIGI_API_KEY',
    role: 'Enrichment',
    roleColor: 'teal',
    provides: 'FIGI / Composite FIGI / Share Class FIGI Identifier Mapping',
    impact: 'Identifier enrichment. Works without key at lower rate limit (25 req/min).',
    frequency: 'On-demand',
    icon: Globe,
    optional: true,
  },
  {
    name: 'Trading 212',
    fullName: 'Trading 212',
    envKey: 'T212_API_KEY',
    role: 'Broker',
    roleColor: 'amber',
    provides: 'Account Summary, Positions, Orders (Readonly)',
    impact: 'Broker integration for portfolio monitoring. Live submit disabled by default.',
    frequency: 'On-demand',
    icon: Wallet,
  },
];

const FEATURE_FLAGS = [
  {
    name: 'T212_LIVE_SUBMIT',
    value: false,
    label: 'Live Order Submission',
    description: 'Allow live order submission to Trading 212. Disabled by default for safety.',
    severity: 'critical',
  },
  {
    name: 'AUTO_REBALANCE',
    value: false,
    label: 'Auto Rebalance',
    description: 'Automatically rebalance portfolios on schedule.',
    severity: 'warning',
  },
  {
    name: 'DQ_AUTO_QUARANTINE',
    value: true,
    label: 'DQ Auto-Quarantine',
    description: 'Auto-quarantine instruments failing data quality checks.',
    severity: 'info',
  },
];

const EXECUTION_POLICIES = [
  { icon: Lock, label: 'Pre-Trade Approval', value: 'Required', description: 'All orders require manual approval before submission' },
  { icon: Shield, label: 'Live Submit', value: 'Disabled', description: 'Live broker submission disabled by default (FEATURE_T212_LIVE_SUBMIT=false)', critical: true },
  { icon: Gauge, label: 'Max Order Size', value: '10,000 shares', description: 'Maximum single-order quantity limit' },
  { icon: AlertTriangle, label: 'Risk Checks', value: 'Mandatory', description: 'All drafts must pass risk checks before approval' },
  { icon: Eye, label: 'Broker Mode', value: 'Readonly', description: 'Trading 212 connected in readonly mode — positions and orders visible, no execution' },
  { icon: Clock, label: 'Stale Intent Expiry', value: '24h', description: 'Order intents expire after 24 hours if not converted to drafts' },
];

const roleBg = {
  brand: 'bg-brand-light text-brand-dark',
  blue: 'bg-blue-50 text-blue-600',
  purple: 'bg-purple-50 text-purple-600',
  teal: 'bg-teal-50 text-teal-600',
  amber: 'bg-amber-50 text-amber-600',
};

export default function SettingsPage() {
  const { t } = useI18n();
  const [health, setHealth] = useState(null);

  useEffect(() => {
    apiFetch('/health')
      .then(res => setHealth(res))
      .catch(() => setHealth(null));
  }, []);

  const version = health?.version ?? '—';
  const status = health?.status ?? 'unknown';
  const isHealthy = status === 'ok' || status === 'healthy';

  // Count configured sources
  const configuredCount = DATA_SOURCES.filter(s => s.noKeyNeeded).length; // SEC always counted

  return (
    <div>
      {/* Page Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-text-primary tracking-tight flex items-center gap-2">
          <Settings size={24} className="text-brand" />
          {t('settings_title') || 'System Configuration'}
        </h1>
        <p className="text-sm text-text-secondary mt-1">
          {t('settings_subtitle') || 'Data sources, execution policies, feature flags, and system status'}
        </p>
        <div className="flex items-center gap-3 mt-2">
          <span className="text-xs font-mono text-text-placeholder">v{version}</span>
          <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wider ${
            isHealthy ? 'bg-brand-light text-brand-dark' : 'bg-amber-50 text-amber-600'
          }`}>
            {isHealthy ? <CheckCircle size={10} className="mr-1" /> : <AlertTriangle size={10} className="mr-1" />}
            {isHealthy ? 'Operational' : status}
          </span>
        </div>
      </div>

      {/* ─── Data Source Matrix ─── */}
      <div className="bg-card rounded-xl border border-border shadow-card p-6 mb-6">
        <div className="flex items-center justify-between mb-1">
          <h2 className="text-base font-bold text-text-primary">Data Source Matrix</h2>
          <Database size={16} className="text-text-placeholder" />
        </div>
        <p className="text-[11px] text-text-placeholder mb-5">Official API sources only — no HTML scraping, no unofficial wrappers</p>

        <div className="space-y-3">
          {DATA_SOURCES.map((src) => {
            const Icon = src.icon;
            const isActive = src.noKeyNeeded || false; // Could be enhanced with real health data
            return (
              <div key={src.name} className="flex items-start gap-4 px-4 py-3.5 rounded-lg border border-border hover:bg-hover-row transition-colors">
                <div className={`w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0 ${roleBg[src.roleColor] || 'bg-gray-50 text-gray-500'}`}>
                  <Icon size={18} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-0.5">
                    <span className="text-sm font-semibold text-text-primary">{src.fullName}</span>
                    <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider ${roleBg[src.roleColor] || 'bg-gray-100 text-gray-500'}`}>
                      {src.role}
                    </span>
                    {src.optional && (
                      <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[9px] font-medium text-text-placeholder bg-hover-row">Optional</span>
                    )}
                  </div>
                  <p className="text-xs text-text-secondary">{src.provides}</p>
                  <p className="text-[11px] text-text-placeholder mt-1 flex items-start gap-1">
                    <Info size={11} className="flex-shrink-0 mt-0.5" />
                    {src.impact}
                  </p>
                </div>
                <div className="flex flex-col items-end gap-1 flex-shrink-0">
                  {src.noKeyNeeded ? (
                    <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold bg-brand-light text-brand-dark">
                      <CheckCircle size={10} className="mr-1" /> No Key Needed
                    </span>
                  ) : (
                    <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold bg-amber-50 text-amber-600">
                      <Key size={10} className="mr-1" /> {src.envKey}
                    </span>
                  )}
                  <span className="text-[10px] text-text-placeholder flex items-center gap-1">
                    <RefreshCw size={10} /> {src.frequency}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* ─── Execution Policy + Feature Flags ─── */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
        {/* Execution Policy */}
        <div className="bg-card rounded-xl border border-border shadow-card p-6">
          <div className="flex items-center justify-between mb-1">
            <h2 className="text-base font-bold text-text-primary">Execution Policy</h2>
            <Shield size={16} className="text-text-placeholder" />
          </div>
          <p className="text-[11px] text-text-placeholder mb-5">Controlled execution — approval gate mandatory, live submit disabled</p>

          <div className="space-y-2.5">
            {EXECUTION_POLICIES.map((policy) => {
              const Icon = policy.icon;
              return (
                <div key={policy.label} className={`flex items-start gap-3 px-3 py-2.5 rounded-lg border ${policy.critical ? 'border-red-200 bg-red-50/30' : 'border-border'} hover:bg-hover-row transition-colors`}>
                  <div className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${policy.critical ? 'bg-red-50' : 'bg-brand-light'}`}>
                    <Icon size={14} className={policy.critical ? 'text-red-500' : 'text-brand-dark'} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-semibold text-text-primary">{policy.label}</span>
                      <span className={`text-xs font-bold ${policy.critical ? 'text-red-500' : 'text-brand-dark'}`}>{policy.value}</span>
                    </div>
                    <p className="text-[10px] text-text-placeholder mt-0.5">{policy.description}</p>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Feature Flags */}
        <div className="bg-card rounded-xl border border-border shadow-card p-6">
          <div className="flex items-center justify-between mb-1">
            <h2 className="text-base font-bold text-text-primary">Feature Flags</h2>
            <Flag size={16} className="text-text-placeholder" />
          </div>
          <p className="text-[11px] text-text-placeholder mb-5">Runtime feature toggles — configured via environment variables</p>

          <div className="space-y-3">
            {FEATURE_FLAGS.map((flag) => (
              <div key={flag.name} className="flex items-center justify-between px-3 py-2.5 rounded-lg border border-border hover:bg-hover-row transition-colors">
                <div className="flex items-center gap-3">
                  <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${flag.value ? 'bg-brand-light' : 'bg-gray-100'}`}>
                    <Zap size={14} className={flag.value ? 'text-brand-dark' : 'text-text-placeholder'} />
                  </div>
                  <div>
                    <div className="text-sm font-medium text-text-primary">{flag.label}</div>
                    <div className="text-[10px] text-text-placeholder">{flag.description}</div>
                  </div>
                </div>
                <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wider ${
                  flag.value ? 'bg-brand-light text-brand-dark' : 'bg-gray-100 text-text-placeholder'
                }`}>
                  {flag.value ? 'Enabled' : 'Disabled'}
                </span>
              </div>
            ))}
          </div>

          {/* Dev-only warning */}
          <div className="mt-4 px-3 py-2.5 rounded-lg bg-amber-50 border border-amber-200">
            <p className="text-[11px] text-amber-700 flex items-start gap-1.5">
              <AlertTriangle size={12} className="flex-shrink-0 mt-0.5" />
              <span><strong>yfinance_dev</strong> is available as a development fallback only. It is not a production data source and should not be used for formal research or backtesting.</span>
            </p>
          </div>
        </div>
      </div>

      {/* ─── System Boundaries ─── */}
      <div className="bg-card rounded-xl border border-border shadow-card p-6 mb-6">
        <div className="flex items-center justify-between mb-1">
          <h2 className="text-base font-bold text-text-primary">System Boundaries</h2>
          <Info size={16} className="text-text-placeholder" />
        </div>
        <p className="text-[11px] text-text-placeholder mb-5">What this platform is and is not</p>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="px-4 py-3 rounded-lg border border-brand-light bg-brand-light/20">
            <p className="text-xs font-semibold text-brand-dark mb-2 flex items-center gap-1.5">
              <CheckCircle size={12} /> This Platform Is
            </p>
            <ul className="text-[11px] text-text-secondary space-y-1">
              <li>• API-first quant research platform</li>
              <li>• PIT-aware data and analytics</li>
              <li>• Controlled execution with approval gates</li>
              <li>• Official data sources only</li>
              <li>• Daily research workflow terminal</li>
            </ul>
          </div>
          <div className="px-4 py-3 rounded-lg border border-red-200 bg-red-50/30">
            <p className="text-xs font-semibold text-red-600 mb-2 flex items-center gap-1.5">
              <XCircle size={12} /> This Platform Is Not
            </p>
            <ul className="text-[11px] text-text-secondary space-y-1">
              <li>• An unrestricted auto-trading bot</li>
              <li>• A web-scraping data platform</li>
              <li>• A high-frequency trading system</li>
              <li>• A multi-market global platform</li>
              <li>• A live trading system by default</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}
