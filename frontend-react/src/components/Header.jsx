import { Search, Moon, Sun, RefreshCw, Bell, Settings as SettingsIcon } from 'lucide-react';
import { useTheme } from '../hooks/useTheme';

export default function Header({ onRefresh }) {
  const { theme, toggle } = useTheme();

  return (
    <header className="sticky top-0 h-[60px] bg-card border-b border-border flex items-center justify-end px-8 gap-3 z-40">
      {/* Search */}
      <div className="relative w-[220px]">
        <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-placeholder pointer-events-none" />
        <input
          type="text"
          placeholder="Search instruments..."
          className="w-full h-9 pl-9 pr-4 bg-border-light border border-border rounded-lg text-sm text-text-primary placeholder:text-text-placeholder focus:outline-none focus:border-brand focus:ring-2 focus:ring-brand-light transition-all"
        />
      </div>

      {/* Language */}
      <div className="flex gap-0.5">
        <button className="w-7 h-7 rounded text-xs font-semibold text-text-placeholder hover:bg-hover transition-colors cursor-pointer">EN</button>
        <button className="w-7 h-7 rounded text-xs font-semibold text-text-placeholder hover:bg-hover transition-colors cursor-pointer">中</button>
      </div>

      {/* Theme Toggle */}
      <button onClick={toggle} className="w-9 h-9 rounded-lg flex items-center justify-center text-text-placeholder hover:bg-hover transition-colors cursor-pointer" title="Toggle theme">
        {theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
      </button>

      {/* Actions */}
      <button onClick={onRefresh} className="w-9 h-9 rounded-lg flex items-center justify-center text-text-placeholder hover:bg-hover transition-colors cursor-pointer">
        <RefreshCw size={18} />
      </button>
      <button className="w-9 h-9 rounded-lg flex items-center justify-center text-text-placeholder hover:bg-hover transition-colors cursor-pointer relative">
        <Bell size={18} />
      </button>
      <button className="w-9 h-9 rounded-lg flex items-center justify-center text-text-placeholder hover:bg-hover transition-colors cursor-pointer">
        <SettingsIcon size={18} />
      </button>

      {/* Avatar */}
      <div className="w-8 h-8 rounded-full bg-brand-light text-brand-dark font-bold text-sm flex items-center justify-center cursor-pointer hover:ring-2 hover:ring-brand/30 transition-all ml-1">
        Q
      </div>
    </header>
  );
}
