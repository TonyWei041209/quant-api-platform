import {
  LayoutDashboard, CandlestickChart, FlaskConical, History,
  ArrowLeftRight, ShieldCheck, Settings, Plus, FileText, Code2
} from 'lucide-react';

const NAV_ITEMS = [
  { key: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { key: 'instruments', label: 'Instruments', icon: CandlestickChart },
  { key: 'research', label: 'Research', icon: FlaskConical },
  { key: 'backtest', label: 'Backtest', icon: History },
  { key: 'execution', label: 'Execution', icon: ArrowLeftRight },
  { key: 'dq', label: 'Data Quality', icon: ShieldCheck },
  { key: 'settings', label: 'Settings', icon: Settings },
];

export default function Sidebar({ activePage, onNavigate }) {
  return (
    <aside className="w-[240px] h-screen fixed left-0 top-0 bg-card border-r border-border flex flex-col z-50">
      {/* Brand */}
      <div className="px-5 py-4 border-b border-border flex items-center gap-3">
        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-brand to-brand-dark flex items-center justify-center text-white text-xs font-extrabold flex-shrink-0">
          Q
        </div>
        <div>
          <div className="text-[15px] font-bold text-text-primary tracking-tight">QUANT_CORE</div>
          <div className="text-[11px] text-text-placeholder flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-brand pulse-dot" />
            SYSTEM ACTIVE
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 flex flex-col gap-1 px-3 py-4 overflow-y-auto">
        {NAV_ITEMS.map(item => {
          const isActive = activePage === item.key;
          const Icon = item.icon;
          return (
            <button
              key={item.key}
              onClick={() => onNavigate(item.key)}
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
              <span>{item.label}</span>
            </button>
          );
        })}
      </nav>

      {/* Bottom */}
      <div className="px-3 pb-4 pt-3 border-t border-border mt-auto">
        <button
          onClick={() => onNavigate('backtest')}
          className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-gradient-to-r from-brand to-brand-dark text-white font-semibold text-sm rounded-lg shadow-[0_4px_14px_rgba(103,194,58,0.25)] hover:brightness-105 transition-all cursor-pointer"
        >
          <Plus size={16} />
          NEW BACKTEST
        </button>
        <div className="flex flex-col gap-1 mt-3">
          <a href="/docs" target="_blank" className="flex items-center gap-2 px-2 py-1 text-xs text-text-placeholder hover:text-text-secondary rounded transition-colors">
            <FileText size={14} /> API DOCS
          </a>
          <a href="https://github.com/TonyWei041209/quant-api-platform" target="_blank" className="flex items-center gap-2 px-2 py-1 text-xs text-text-placeholder hover:text-text-secondary rounded transition-colors">
            <Code2 size={14} /> GITHUB
          </a>
        </div>
      </div>
    </aside>
  );
}
