import { useState } from 'react';
import { Search, Moon, Sun, RefreshCw, Bell, Settings as SettingsIcon, Crosshair, Layers, Menu, LogOut } from 'lucide-react';
import { useTheme } from '../hooks/useTheme';
import { useI18n } from '../hooks/useI18n';
import { useWorkspace } from '../hooks/useWorkspace';
import { useAuth } from '../hooks/useAuth';

export default function Header({ onRefresh, onNavigate, onToggleSidebar }) {
  const { theme, toggle } = useTheme();
  const { lang, setLang, t } = useI18n();
  const [bellTooltip, setBellTooltip] = useState(false);
  const { activeInstrument, activeWatchlist } = useWorkspace();
  const { user, signOut } = useAuth();

  return (
    <header className="sticky top-0 h-[60px] bg-card border-b border-border flex items-center px-3 sm:px-6 lg:px-8 gap-2 sm:gap-3 z-40">
      {/* Mobile hamburger */}
      {onToggleSidebar && (
        <button onClick={onToggleSidebar} className="lg:hidden p-2 -ml-1 rounded-lg hover:bg-hover text-text-secondary">
          <Menu size={20} />
        </button>
      )}

      {/* Workspace Context Breadcrumb — desktop only */}
      {(activeInstrument || activeWatchlist) && (
        <div className="hidden sm:flex items-center gap-2 mr-auto">
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
      {/* Spacer */}
      <div className="mr-auto" />

      {/* Search — compressed on mobile */}
      <div className="relative w-full max-w-[140px] sm:max-w-[260px]">
        <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-placeholder pointer-events-none" />
        <input
          type="text"
          placeholder={t('search_placeholder')}
          className="w-full h-9 pl-9 pr-4 bg-border-light border border-border rounded-lg text-sm text-text-primary placeholder:text-text-placeholder focus:outline-none focus:border-brand focus:ring-2 focus:ring-brand-light transition-all"
        />
      </div>

      {/* Language Toggle — desktop only */}
      <div className="hidden sm:flex gap-0.5">
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

      {/* Theme Toggle — always visible */}
      <button onClick={toggle} className="w-10 h-10 sm:w-9 sm:h-9 rounded-lg flex items-center justify-center text-text-placeholder hover:bg-hover transition-colors cursor-pointer" title={t('header_theme')}>
        {theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
      </button>

      {/* Refresh — desktop only */}
      <button onClick={onRefresh} className="hidden sm:flex w-9 h-9 rounded-lg items-center justify-center text-text-placeholder hover:bg-hover transition-colors cursor-pointer" title={t('refresh')}>
        <RefreshCw size={18} />
      </button>

      {/* Notifications — always visible */}
      <div className="relative">
        <button
          onClick={() => setBellTooltip(prev => !prev)}
          onBlur={() => setTimeout(() => setBellTooltip(false), 150)}
          className="w-10 h-10 sm:w-9 sm:h-9 rounded-lg flex items-center justify-center text-text-placeholder hover:bg-hover transition-colors cursor-pointer relative"
          title={t('header_notifications')}
        >
          <Bell size={18} />
        </button>
        {bellTooltip && (
          <div className="absolute right-0 top-full mt-1 px-3 py-2 bg-card border border-border rounded-lg shadow-lg text-xs text-text-secondary whitespace-nowrap z-50">
            {t('header_no_notif')}
          </div>
        )}
      </div>

      {/* Settings — always visible */}
      <button
        onClick={() => onNavigate?.('settings')}
        className="w-10 h-10 sm:w-9 sm:h-9 rounded-lg flex items-center justify-center text-text-placeholder hover:bg-hover transition-colors cursor-pointer"
        title={t('nav_settings')}
      >
        <SettingsIcon size={18} />
      </button>

      {/* User Avatar — always visible; Sign Out — desktop only */}
      <div className="flex items-center gap-1 ml-1">
        <div className="w-8 h-8 rounded-full bg-brand-light text-brand-dark font-bold text-sm flex items-center justify-center" title={user?.email || ''}>
          {user?.email?.[0]?.toUpperCase() || 'Q'}
        </div>
        <button onClick={signOut} className="hidden sm:flex p-2 rounded-lg hover:bg-hover text-text-placeholder hover:text-text-secondary transition-all" title={t('header_signout')}>
          <LogOut size={16} />
        </button>
      </div>
    </header>
  );
}
