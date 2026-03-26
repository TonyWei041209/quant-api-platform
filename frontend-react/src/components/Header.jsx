import { useState } from 'react';
import { Search, Moon, Sun, RefreshCw, Bell, Settings as SettingsIcon, Crosshair, Layers } from 'lucide-react';
import { useTheme } from '../hooks/useTheme';
import { useI18n } from '../hooks/useI18n';
import { useWorkspace } from '../hooks/useWorkspace';

export default function Header({ onRefresh, onNavigate }) {
  const { theme, toggle } = useTheme();
  const { lang, setLang, t } = useI18n();
  const [bellTooltip, setBellTooltip] = useState(false);
  const { activeInstrument, activeWatchlist } = useWorkspace();

  return (
    <header className="sticky top-0 h-[60px] bg-card border-b border-border flex items-center px-8 gap-3 z-40">
      {/* Workspace Context Breadcrumb */}
      {(activeInstrument || activeWatchlist) && (
        <div className="flex items-center gap-2 mr-auto">
          {activeWatchlist && (
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-purple-50 dark:bg-purple-900/20 text-[11px] font-semibold text-purple-600 dark:text-purple-400">
              <Layers size={11} /> {activeWatchlist.name}
            </span>
          )}
          {activeInstrument && (
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-brand-light text-[11px] font-semibold text-brand-dark">
              <Crosshair size={11} /> {activeInstrument.ticker || activeInstrument.name}
            </span>
          )}
        </div>
      )}
      {!activeInstrument && !activeWatchlist && <div className="mr-auto" />}

      {/* Search */}
      <div className="relative w-[260px]">
        <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-placeholder pointer-events-none" />
        <input
          type="text"
          placeholder={t('search_placeholder')}
          className="w-full h-9 pl-9 pr-4 bg-border-light border border-border rounded-lg text-sm text-text-primary placeholder:text-text-placeholder focus:outline-none focus:border-brand focus:ring-2 focus:ring-brand-light transition-all"
        />
      </div>

      {/* Language Toggle */}
      <div className="flex gap-0.5">
        <button
          onClick={() => setLang('en')}
          className={`w-7 h-7 rounded text-xs font-semibold transition-colors cursor-pointer ${
            lang === 'en' ? 'bg-brand-light text-brand-dark' : 'text-text-placeholder hover:bg-hover'
          }`}
        >
          EN
        </button>
        <button
          onClick={() => setLang('zh-CN')}
          className={`w-7 h-7 rounded text-xs font-semibold transition-colors cursor-pointer ${
            lang === 'zh-CN' ? 'bg-brand-light text-brand-dark' : 'text-text-placeholder hover:bg-hover'
          }`}
        >
          中
        </button>
      </div>

      {/* Theme Toggle */}
      <button onClick={toggle} className="w-9 h-9 rounded-lg flex items-center justify-center text-text-placeholder hover:bg-hover transition-colors cursor-pointer" title="Toggle theme">
        {theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
      </button>

      {/* Actions */}
      <button onClick={onRefresh} className="w-9 h-9 rounded-lg flex items-center justify-center text-text-placeholder hover:bg-hover transition-colors cursor-pointer">
        <RefreshCw size={18} />
      </button>
      <div className="relative">
        <button
          onClick={() => setBellTooltip(prev => !prev)}
          onBlur={() => setTimeout(() => setBellTooltip(false), 150)}
          className="w-9 h-9 rounded-lg flex items-center justify-center text-text-placeholder hover:bg-hover transition-colors cursor-pointer relative"
        >
          <Bell size={18} />
        </button>
        {bellTooltip && (
          <div className="absolute right-0 top-full mt-1 px-3 py-2 bg-card border border-border rounded-lg shadow-lg text-xs text-text-secondary whitespace-nowrap z-50">
            No notifications
          </div>
        )}
      </div>
      <button
        onClick={() => onNavigate?.('settings')}
        className="w-9 h-9 rounded-lg flex items-center justify-center text-text-placeholder hover:bg-hover transition-colors cursor-pointer"
        title="Settings"
      >
        <SettingsIcon size={18} />
      </button>

      {/* Avatar */}
      <div className="w-8 h-8 rounded-full bg-brand-light text-brand-dark font-bold text-sm flex items-center justify-center cursor-pointer hover:ring-2 hover:ring-brand/30 transition-all ml-1">
        Q
      </div>
    </header>
  );
}
