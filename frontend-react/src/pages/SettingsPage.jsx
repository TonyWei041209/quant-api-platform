import { useState, useEffect } from 'react';
import {
  Settings, Key, Flag, Shield, Database, CheckCircle, XCircle,
  Lock, RefreshCw, Clock, Gauge, AlertTriangle, Scale, Layers,
  Zap, Info, ExternalLink, Globe, FileText, BarChart3, TrendingUp,
  Wallet, Eye, Sun, Moon, LogOut, Globe2, Palette, User
} from 'lucide-react';
import { apiFetch } from '../hooks/useApi';
import { useI18n } from '../hooks/useI18n';
import { useTheme } from '../hooks/useTheme';
import { useAuth } from '../hooks/useAuth';

/* ─── Data Source Matrix (matches docs/source_matrix.md) ─── */
const DATA_SOURCES = [
  { name: 'FMP', fullName: 'Financial Modeling Prep', envKey: 'FMP_API_KEY', role: 'Primary', roleColor: 'brand',
    providesKey: 'src_fmp_provides', impactKey: 'src_fmp_impact', freqKey: 'src_freq_daily', icon: TrendingUp },
  { name: 'SEC EDGAR', fullName: 'SEC EDGAR', envKey: 'SEC_USER_AGENT', role: 'Truth / PIT', roleColor: 'blue',
    providesKey: 'src_sec_provides', impactKey: 'src_sec_impact', freqKey: 'src_freq_daily', icon: FileText, noKeyNeeded: true },
  { name: 'Polygon', fullName: 'Polygon.io / Massive', envKey: 'MASSIVE_API_KEY', role: 'Corp Actions', roleColor: 'purple',
    providesKey: 'src_poly_provides', impactKey: 'src_poly_impact', freqKey: 'src_freq_daily', icon: BarChart3 },
  { name: 'OpenFIGI', fullName: 'OpenFIGI', envKey: 'OPENFIGI_API_KEY', role: 'Enrichment', roleColor: 'teal',
    providesKey: 'src_figi_provides', impactKey: 'src_figi_impact', freqKey: 'src_freq_ondemand', icon: Globe, optional: true },
  { name: 'Trading 212', fullName: 'Trading 212', envKey: 'T212_API_KEY', role: 'Broker', roleColor: 'amber',
    providesKey: 'src_t212_provides', impactKey: 'src_t212_impact', freqKey: 'src_freq_ondemand', icon: Wallet },
];

const FEATURE_FLAGS = [
  { name: 'T212_LIVE_SUBMIT', value: false, labelKey: 'ff_live_submit', descKey: 'ff_live_submit_desc', severity: 'critical' },
  { name: 'AUTO_REBALANCE', value: false, labelKey: 'ff_auto_rebalance', descKey: 'ff_auto_rebalance_desc', severity: 'warning' },
  { name: 'DQ_AUTO_QUARANTINE', value: true, labelKey: 'ff_dq_quarantine', descKey: 'ff_dq_quarantine_desc', severity: 'info' },
];

const EXECUTION_POLICIES = [
  { icon: Lock, labelKey: 'ep_approval', valueKey: 'ep_approval_val', descKey: 'ep_approval_desc' },
  { icon: Shield, labelKey: 'ep_live', valueKey: 'ep_live_val', descKey: 'ep_live_desc', critical: true },
  { icon: Gauge, labelKey: 'ep_max_size', valueKey: 'ep_max_size_val', descKey: 'ep_max_size_desc' },
  { icon: AlertTriangle, labelKey: 'ep_risk', valueKey: 'ep_risk_val', descKey: 'ep_risk_desc' },
  { icon: Eye, labelKey: 'ep_broker_mode', valueKey: 'ep_broker_mode_val', descKey: 'ep_broker_mode_desc' },
  { icon: Clock, labelKey: 'ep_stale', valueKey: 'ep_stale_val', descKey: 'ep_stale_desc' },
];

const roleBg = {
  brand: 'bg-brand-light text-brand-dark',
  blue: 'bg-blue-50 text-blue-600',
  purple: 'bg-purple-50 text-purple-600',
  teal: 'bg-teal-50 text-teal-600',
  amber: 'bg-amber-50 text-amber-600',
};

const ACTIVE_BTN = 'flex-1 inline-flex items-center justify-center gap-2 px-3 h-9 rounded-lg text-sm font-medium bg-brand-light text-brand-dark border border-brand/30 transition-all cursor-pointer';
const INACTIVE_BTN = 'flex-1 inline-flex items-center justify-center gap-2 px-3 h-9 rounded-lg text-sm font-medium text-text-secondary border border-border hover:bg-hover transition-all cursor-pointer';

export default function SettingsPage() {
  const { t, lang, setLang } = useI18n();
  const { theme, setMode } = useTheme();
  const { user, signOut } = useAuth();
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
          {t('settings_title')}
        </h1>
        <p className="text-sm text-text-secondary mt-1">
          {t('settings_subtitle')}
        </p>
        <div className="flex flex-wrap items-center gap-2 sm:gap-3 mt-2">
          <span className="text-xs font-mono text-text-placeholder">v{version}</span>
          <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wider ${
            isHealthy ? 'bg-brand-light text-brand-dark' : 'bg-amber-50 text-amber-600'
          }`}>
            {isHealthy ? <CheckCircle size={10} className="mr-1" /> : <AlertTriangle size={10} className="mr-1" />}
            {isHealthy ? t('set_operational') : status}
          </span>
        </div>
      </div>

      {/* User Preferences */}
      <div className="bg-card rounded-xl border border-border shadow-card p-6 mb-6">
        <h2 className="text-base font-bold text-text-primary mb-5">{t('set_preferences')}</h2>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
          {/* Language */}
          <div>
            <div className="flex items-center gap-2 mb-3">
              <Globe2 size={14} className="text-text-placeholder" />
              <span className="text-xs font-bold uppercase tracking-wider text-text-placeholder">{t('set_language')}</span>
            </div>
            <div className="flex gap-2">
              <button onClick={() => setLang('en')} className={lang === 'en' ? ACTIVE_BTN : INACTIVE_BTN}>
                English
              </button>
              <button onClick={() => setLang('zh-CN')} className={lang === 'zh-CN' ? ACTIVE_BTN : INACTIVE_BTN}>
                简体中文
              </button>
            </div>
          </div>
          {/* Appearance */}
          <div>
            <div className="flex items-center gap-2 mb-3">
              <Palette size={14} className="text-text-placeholder" />
              <span className="text-xs font-bold uppercase tracking-wider text-text-placeholder">{t('set_appearance')}</span>
            </div>
            <div className="flex gap-2">
              <button onClick={() => setMode('light')} className={theme === 'light' ? ACTIVE_BTN : INACTIVE_BTN}>
                <Sun size={14} /> {t('set_light')}
              </button>
              <button onClick={() => setMode('dark')} className={theme === 'dark' ? ACTIVE_BTN : INACTIVE_BTN}>
                <Moon size={14} /> {t('set_dark')}
              </button>
            </div>
          </div>
          {/* Account */}
          <div>
            <div className="flex items-center gap-2 mb-3">
              <User size={14} className="text-text-placeholder" />
              <span className="text-xs font-bold uppercase tracking-wider text-text-placeholder">{t('set_account')}</span>
            </div>
            <p className="text-sm text-text-secondary mb-2 truncate">{user?.email || '—'}</p>
            <button onClick={signOut} className="inline-flex items-center gap-2 px-4 h-9 border border-danger/30 rounded-lg text-sm font-medium text-danger hover:bg-red-50 dark:hover:bg-red-900/20 transition-all cursor-pointer">
              <LogOut size={14} /> {t('set_signout')}
            </button>
          </div>
        </div>
      </div>

      {/* ─── Data Source Matrix ─── */}
      <div className="bg-card rounded-xl border border-border shadow-card p-6 mb-6">
        <div className="flex items-center justify-between mb-1">
          <h2 className="text-base font-bold text-text-primary">{t('set_data_sources')}</h2>
          <Database size={16} className="text-text-placeholder" />
        </div>
        <p className="text-[11px] text-text-placeholder mb-5">{t('set_sources_desc')}</p>

        <div className="space-y-3">
          {DATA_SOURCES.map((src) => {
            const Icon = src.icon;
            const isActive = src.noKeyNeeded || false; // Could be enhanced with real health data
            return (
              <div key={src.name} className="flex flex-wrap sm:flex-nowrap items-start gap-3 sm:gap-4 px-4 py-3.5 rounded-lg border border-border hover:bg-hover-row transition-colors">
                <div className={`w-10 h-10 rounded-lg flex items-center justify-center shrink-0 ${roleBg[src.roleColor] || 'bg-gray-50 text-gray-500'}`}>
                  <Icon size={18} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex flex-wrap items-center gap-1.5 sm:gap-2 mb-0.5">
                    <span className="text-sm font-semibold text-text-primary">{src.fullName}</span>
                    <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider ${roleBg[src.roleColor] || 'bg-gray-100 text-gray-500'}`}>
                      {src.role}
                    </span>
                    {src.optional && (
                      <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[9px] font-medium text-text-placeholder bg-hover-row">{t('src_optional')}</span>
                    )}
                  </div>
                  <p className="text-xs text-text-secondary">{t(src.providesKey)}</p>
                  <p className="text-[11px] text-text-placeholder mt-1 flex items-start gap-1">
                    <Info size={11} className="shrink-0 mt-0.5" />
                    {t(src.impactKey)}
                  </p>
                  <div className="flex flex-wrap items-center gap-2 mt-2 sm:hidden">
                    {src.noKeyNeeded ? (
                      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold bg-brand-light text-brand-dark">
                        <CheckCircle size={10} className="mr-1" /> {t('src_no_key')}
                      </span>
                    ) : (
                      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold bg-amber-50 text-amber-600">
                        <Key size={10} className="mr-1" /> {src.envKey}
                      </span>
                    )}
                    <span className="text-[10px] text-text-placeholder flex items-center gap-1">
                      <RefreshCw size={10} /> {t(src.freqKey)}
                    </span>
                  </div>
                </div>
                <div className="hidden sm:flex flex-col items-end gap-1 shrink-0">
                  {src.noKeyNeeded ? (
                    <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold bg-brand-light text-brand-dark">
                      <CheckCircle size={10} className="mr-1" /> {t('src_no_key')}
                    </span>
                  ) : (
                    <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold bg-amber-50 text-amber-600">
                      <Key size={10} className="mr-1" /> {src.envKey}
                    </span>
                  )}
                  <span className="text-[10px] text-text-placeholder flex items-center gap-1">
                    <RefreshCw size={10} /> {t(src.freqKey)}
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
            <h2 className="text-base font-bold text-text-primary">{t('set_exec_policy')}</h2>
            <Shield size={16} className="text-text-placeholder" />
          </div>
          <p className="text-[11px] text-text-placeholder mb-5">{t('set_exec_desc')}</p>

          <div className="space-y-2.5">
            {EXECUTION_POLICIES.map((policy) => {
              const Icon = policy.icon;
              return (
                <div key={policy.labelKey} className={`flex items-start gap-3 px-3 py-2.5 rounded-lg border ${policy.critical ? 'border-red-200 bg-red-50/30' : 'border-border'} hover:bg-hover-row transition-colors`}>
                  <div className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${policy.critical ? 'bg-red-50' : 'bg-brand-light'}`}>
                    <Icon size={14} className={policy.critical ? 'text-red-500' : 'text-brand-dark'} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-semibold text-text-primary">{t(policy.labelKey)}</span>
                      <span className={`text-xs font-bold ${policy.critical ? 'text-red-500' : 'text-brand-dark'}`}>{t(policy.valueKey)}</span>
                    </div>
                    <p className="text-[10px] text-text-placeholder mt-0.5">{t(policy.descKey)}</p>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Feature Flags */}
        <div className="bg-card rounded-xl border border-border shadow-card p-6">
          <div className="flex items-center justify-between mb-1">
            <h2 className="text-base font-bold text-text-primary">{t('set_feat_flags')}</h2>
            <Flag size={16} className="text-text-placeholder" />
          </div>
          <p className="text-[11px] text-text-placeholder mb-5">{t('set_feat_desc')}</p>

          <div className="space-y-3">
            {FEATURE_FLAGS.map((flag) => (
              <div key={flag.name} className="flex flex-wrap items-center justify-between gap-2 px-3 py-2.5 rounded-lg border border-border hover:bg-hover-row transition-colors">
                <div className="flex items-center gap-3 min-w-0">
                  <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${flag.value ? 'bg-brand-light' : 'bg-gray-100'}`}>
                    <Zap size={14} className={flag.value ? 'text-brand-dark' : 'text-text-placeholder'} />
                  </div>
                  <div>
                    <div className="text-sm font-medium text-text-primary">{t(flag.labelKey)}</div>
                    <div className="text-[10px] text-text-placeholder">{t(flag.descKey)}</div>
                  </div>
                </div>
                <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wider ${
                  flag.value ? 'bg-brand-light text-brand-dark' : 'bg-gray-100 text-text-placeholder'
                }`}>
                  {flag.value ? t('ff_enabled') : t('ff_disabled')}
                </span>
              </div>
            ))}
          </div>

          {/* Dev-only warning */}
          <div className="mt-4 px-3 py-2.5 rounded-lg bg-amber-50 border border-amber-200">
            <p className="text-[11px] text-amber-700 flex items-start gap-1.5">
              <AlertTriangle size={12} className="flex-shrink-0 mt-0.5" />
              <span><strong>yfinance_dev</strong> {t('set_yfinance_warn')}</span>
            </p>
          </div>
        </div>
      </div>

      {/* ─── System Boundaries ─── */}
      <div className="bg-card rounded-xl border border-border shadow-card p-6 mb-6">
        <div className="flex items-center justify-between mb-1">
          <h2 className="text-base font-bold text-text-primary">{t('set_boundaries')}</h2>
          <Info size={16} className="text-text-placeholder" />
        </div>
        <p className="text-[11px] text-text-placeholder mb-5">{t('set_boundaries_desc')}</p>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="px-4 py-3 rounded-lg border border-brand-light bg-brand-light/20">
            <p className="text-xs font-semibold text-brand-dark mb-2 flex items-center gap-1.5">
              <CheckCircle size={12} /> {t('set_is')}
            </p>
            <ul className="text-[11px] text-text-secondary space-y-1">
              <li>• {t('set_is_1')}</li>
              <li>• {t('set_is_2')}</li>
              <li>• {t('set_is_3')}</li>
              <li>• {t('set_is_4')}</li>
              <li>• {t('set_is_5')}</li>
            </ul>
          </div>
          <div className="px-4 py-3 rounded-lg border border-red-200 bg-red-50/30">
            <p className="text-xs font-semibold text-red-600 mb-2 flex items-center gap-1.5">
              <XCircle size={12} /> {t('set_is_not')}
            </p>
            <ul className="text-[11px] text-text-secondary space-y-1">
              <li>• {t('set_not_1')}</li>
              <li>• {t('set_not_2')}</li>
              <li>• {t('set_not_3')}</li>
              <li>• {t('set_not_4')}</li>
              <li>• {t('set_not_5')}</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}
