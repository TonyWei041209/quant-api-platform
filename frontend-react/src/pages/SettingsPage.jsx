import {
  Settings, Key, Flag, Shield, Database, CheckCircle, XCircle,
  Lock, RefreshCw, Clock, Gauge, AlertTriangle, Scale, Layers,
  Zap, BarChart3
} from 'lucide-react';

const API_KEYS = [
  { name: 'SEC EDGAR', key: 'SEC_API_KEY', configured: true },
  { name: 'Alpha Vantage', key: 'ALPHA_VANTAGE_KEY', configured: false },
  { name: 'Trading 212', key: 'T212_API_KEY', configured: false },
  { name: 'Polygon.io', key: 'POLYGON_KEY', configured: false },
  { name: 'OpenBB', key: 'OPENBB_KEY', configured: false },
];

const FEATURE_FLAGS = [
  { name: 'T212_LIVE_SUBMIT', value: false, description: 'Allow live order submission to Trading 212' },
  { name: 'AUTO_REBALANCE', value: false, description: 'Automatically rebalance portfolios on schedule' },
  { name: 'DQ_AUTO_QUARANTINE', value: true, description: 'Auto-quarantine instruments failing DQ checks' },
];

const EXECUTION_POLICIES = [
  { icon: Lock, label: 'Pre-Trade Approval', value: 'Required', description: 'All orders require manual approval' },
  { icon: Gauge, label: 'Max Order Size', value: '$10,000', description: 'Per-order notional limit' },
  { icon: AlertTriangle, label: 'Max Daily Loss', value: '-2%', description: 'Daily portfolio loss threshold' },
  { icon: Scale, label: 'Position Limit', value: '20%', description: 'Max single-position weight' },
  { icon: Clock, label: 'Order Expiry', value: '24h', description: 'Unexecuted orders expire after 24 hours' },
  { icon: Layers, label: 'Rebalance Window', value: 'Monthly', description: 'Minimum rebalance frequency' },
];

const DATA_SOURCES = [
  { source: 'SEC EDGAR', types: 'Fundamentals, Filings', status: 'ACTIVE', frequency: 'Daily' },
  { source: 'Yahoo Finance', types: 'Prices, Dividends', status: 'ACTIVE', frequency: 'Daily' },
  { source: 'Trading 212', types: 'Portfolio, Orders', status: 'INACTIVE', frequency: 'Real-time' },
  { source: 'Alpha Vantage', types: 'Prices, Technicals', status: 'INACTIVE', frequency: 'Daily' },
  { source: 'OpenBB', types: 'Macro, Sentiment', status: 'INACTIVE', frequency: 'Daily' },
];

export default function SettingsPage() {
  return (
    <div>
      {/* Page Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-text-primary tracking-tight flex items-center gap-2">
          <Settings size={24} className="text-brand" />
          Configuration &amp; Policies
        </h1>
        <p className="text-sm text-text-secondary mt-1">
          System configuration, API keys, feature flags, and execution policies
        </p>
      </div>

      {/* API Keys + Feature Flags */}
      <div className="grid grid-cols-2 gap-6 mb-6">
        {/* API Keys */}
        <div className="bg-card rounded-xl border border-border shadow-card p-6">
          <div className="flex items-center justify-between mb-5">
            <h2 className="text-base font-bold text-text-primary">API Keys</h2>
            <Key size={16} className="text-text-placeholder" />
          </div>
          <div className="space-y-3">
            {API_KEYS.map((apiKey) => (
              <div key={apiKey.key} className="flex items-center justify-between px-3 py-2.5 rounded-lg border border-border hover:bg-hover-row transition-colors">
                <div className="flex items-center gap-3">
                  <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${apiKey.configured ? 'bg-brand-light' : 'bg-red-50'}`}>
                    <Key size={14} className={apiKey.configured ? 'text-brand-dark' : 'text-red-400'} />
                  </div>
                  <div>
                    <div className="text-sm font-medium text-text-primary">{apiKey.name}</div>
                    <div className="text-[11px] text-text-placeholder font-mono">{apiKey.key}</div>
                  </div>
                </div>
                <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wider ${
                  apiKey.configured ? 'bg-brand-light text-brand-dark' : 'bg-red-50 text-red-500'
                }`}>
                  {apiKey.configured ? (
                    <><CheckCircle size={10} className="mr-1" /> Configured</>
                  ) : (
                    <><XCircle size={10} className="mr-1" /> Not Configured</>
                  )}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Feature Flags */}
        <div className="bg-card rounded-xl border border-border shadow-card p-6">
          <div className="flex items-center justify-between mb-5">
            <h2 className="text-base font-bold text-text-primary">Feature Flags</h2>
            <Flag size={16} className="text-text-placeholder" />
          </div>
          <div className="space-y-3">
            {FEATURE_FLAGS.map((flag) => (
              <div key={flag.name} className="flex items-center justify-between px-3 py-2.5 rounded-lg border border-border hover:bg-hover-row transition-colors">
                <div className="flex items-center gap-3">
                  <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${flag.value ? 'bg-brand-light' : 'bg-red-50'}`}>
                    <Zap size={14} className={flag.value ? 'text-brand-dark' : 'text-red-400'} />
                  </div>
                  <div>
                    <div className="text-sm font-medium text-text-primary font-mono">{flag.name}</div>
                    <div className="text-[11px] text-text-placeholder">{flag.description}</div>
                  </div>
                </div>
                <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wider ${
                  flag.value ? 'bg-brand-light text-brand-dark' : 'bg-red-50 text-red-500'
                }`}>
                  {flag.value ? 'TRUE' : 'FALSE'}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Execution Policy */}
      <div className="bg-card rounded-xl border border-border shadow-card p-6 mb-6">
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-base font-bold text-text-primary">Execution Policy</h2>
          <Shield size={16} className="text-text-placeholder" />
        </div>
        <div className="grid grid-cols-2 gap-4">
          {EXECUTION_POLICIES.map((policy) => {
            const Icon = policy.icon;
            return (
              <div key={policy.label} className="flex items-start gap-3 px-4 py-3 rounded-lg border border-border hover:bg-hover-row transition-colors">
                <div className="w-9 h-9 rounded-lg bg-brand-light flex items-center justify-center flex-shrink-0 mt-0.5">
                  <Icon size={16} className="text-brand-dark" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-text-primary">{policy.label}</span>
                    <span className="text-sm font-bold text-text-primary">{policy.value}</span>
                  </div>
                  <p className="text-[11px] text-text-placeholder mt-0.5">{policy.description}</p>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Data Sources */}
      <div className="bg-card rounded-xl border border-border shadow-card p-6 mb-6">
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-base font-bold text-text-primary">Data Sources</h2>
          <Database size={16} className="text-text-placeholder" />
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr>
                <th className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder bg-hover-row px-4 py-3 text-left rounded-tl-lg">Source</th>
                <th className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder bg-hover-row px-4 py-3 text-left">Data Types</th>
                <th className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder bg-hover-row px-4 py-3 text-left">Status</th>
                <th className="text-[11px] font-bold uppercase tracking-wider text-text-placeholder bg-hover-row px-4 py-3 text-left rounded-tr-lg">Frequency</th>
              </tr>
            </thead>
            <tbody>
              {DATA_SOURCES.map((src) => (
                <tr key={src.source} className="hover:bg-hover-row transition-colors">
                  <td className="px-4 py-3 border-b border-border/50 font-semibold text-text-primary">
                    <span className="flex items-center gap-2">
                      <Database size={14} className="text-text-placeholder" />
                      {src.source}
                    </span>
                  </td>
                  <td className="px-4 py-3 border-b border-border/50 text-text-secondary">{src.types}</td>
                  <td className="px-4 py-3 border-b border-border/50">
                    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wider ${
                      src.status === 'ACTIVE' ? 'bg-brand-light text-brand-dark' : 'bg-red-50 text-red-500'
                    }`}>
                      {src.status === 'ACTIVE' ? <CheckCircle size={10} className="mr-1" /> : <XCircle size={10} className="mr-1" />}
                      {src.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 border-b border-border/50 text-text-secondary">
                    <span className="flex items-center gap-1">
                      <RefreshCw size={12} className="text-text-placeholder" />
                      {src.frequency}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
