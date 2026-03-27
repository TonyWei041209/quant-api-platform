import {
  LayoutDashboard, CandlestickChart, FlaskConical, History,
  ArrowLeftRight, ShieldCheck, Settings, Plus, FileText, Code2, X
} from 'lucide-react';
import { useI18n } from '../hooks/useI18n';

const NAV_ITEMS = [
  { key: 'dashboard', labelKey: 'nav_dashboard', icon: LayoutDashboard },
  { key: 'instruments', labelKey: 'nav_instruments', icon: CandlestickChart },
  { key: 'research', labelKey: 'nav_research', icon: FlaskConical },
  { key: 'backtest', labelKey: 'nav_backtest', icon: History },
  { key: 'execution', labelKey: 'nav_execution', icon: ArrowLeftRight },
  { key: 'dq', labelKey: 'nav_dq', icon: ShieldCheck },
  { key: 'settings', labelKey: 'nav_settings', icon: Settings },
];

export default function Sidebar({ activePage, onNavigate, isOpen, onClose }) {
  const { t } = useI18n();

  const handleNav = (key) => {
    onNavigate(key);
    if (onClose) onClose();
  };

  return (
    <>
      {/* Backdrop for mobile */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/40 z-40 lg:hidden"
          onClick={onClose}
        />
      )}

      <aside className={`
        w-[240px] h-screen fixed left-0 top-0 bg-card border-r border-border flex flex-col z-50
        transition-transform duration-200 ease-in-out
        ${isOpen ? 'translate-x-0' : '-translate-x-full'}
        lg:translate-x-0
      `}>
        {/* Brand + close button for mobile */}
        <div className="px-5 py-4 border-b border-border flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-brand to-brand-dark flex items-center justify-center text-white text-xs font-extrabold flex-shrink-0">
            Q
          </div>
          <div className="flex-1">
            <div className="text-[15px] font-bold text-text-primary tracking-tight">{t('brand_name')}</div>
            <div className="text-[11px] text-text-placeholder flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-brand pulse-dot" />
              {t('brand_status')}
            </div>
          </div>
          {onClose && (
            <button onClick={onClose} className="lg:hidden p-1 rounded-md hover:bg-hover text-text-placeholder">
              <X size={18} />
            </button>
          )}
        </div>

        {/* Navigation */}
        <nav className="flex-1 flex flex-col gap-1 px-3 py-4 overflow-y-auto">
          {NAV_ITEMS.map(item => {
            const isActive = activePage === item.key;
            const Icon = item.icon;
            return (
              <button
                key={item.key}
                onClick={() => handleNav(item.key)}
                className={`
                  relative flex items-center gap-3 px-4 py-2.5 rounded-lg text-sm font-medium
                  transition-all duration-150 cursor-pointer text-left w-full
                  ${isActive
                    ? 'bg-brand-light text-brand-dark font-semibold'
                    : 'text-text-secondary hover:bg-hover'
                  }
                `}
              >
                {isActive && (
                  <span className="absolute left-0 top-[6px] bottom-[6px] w-1 rounded-full bg-brand" />
                )}
                <Icon size={18} className={isActive ? 'text-brand' : 'text-text-placeholder'} />
                <span>{t(item.labelKey)}</span>
              </button>
            );
          })}
        </nav>

        {/* Bottom */}
        <div className="px-3 pb-4 pt-3 border-t border-border mt-auto">
          <button
            onClick={() => handleNav('backtest')}
            className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-gradient-to-r from-brand to-brand-dark text-white font-semibold text-sm rounded-lg shadow-[0_4px_14px_rgba(103,194,58,0.25)] hover:brightness-105 transition-all cursor-pointer"
          >
            <Plus size={16} />
            {t('nav_new_backtest')}
          </button>
          <div className="flex flex-col gap-1 mt-3">
            <a href="/docs" target="_blank" className="flex items-center gap-2 px-2 py-1 text-xs text-text-placeholder hover:text-text-secondary rounded transition-colors">
              <FileText size={14} /> {t('nav_api_docs')}
            </a>
            <a href="https://github.com/TonyWei041209/quant-api-platform" target="_blank" className="flex items-center gap-2 px-2 py-1 text-xs text-text-placeholder hover:text-text-secondary rounded transition-colors">
              <Code2 size={14} /> {t('nav_github')}
            </a>
          </div>
        </div>
      </aside>
    </>
  );
}
