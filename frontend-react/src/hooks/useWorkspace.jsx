import { createContext, useContext, useState, useCallback } from 'react';

/**
 * WorkspaceContext — lightweight cross-page state for workspace cohesion.
 *
 * Tracks the user's current working context so it persists across page
 * navigation and can be read by any page:
 *
 * - activeInstrument: currently focused instrument (id + name)
 * - activeWatchlist: currently selected watchlist group
 * - activePreset: most recently used/loaded preset
 * - recentAction: last significant user action (for continue flow)
 */

const WorkspaceContext = createContext(null);

export function WorkspaceProvider({ children }) {
  const [workspace, setWorkspace] = useState({
    activeInstrument: null,   // { id, name, ticker }
    activeWatchlist: null,     // { id, name }
    activePreset: null,        // { id, name, type }
    recentAction: null,        // { type, page, label, timestamp }
  });

  const setActiveInstrument = useCallback((inst) => {
    setWorkspace(prev => ({
      ...prev,
      activeInstrument: inst,
      recentAction: inst ? { type: 'select_instrument', page: 'research', label: inst.ticker || inst.name, timestamp: Date.now() } : prev.recentAction,
    }));
  }, []);

  const setActiveWatchlist = useCallback((wl) => {
    setWorkspace(prev => ({
      ...prev,
      activeWatchlist: wl,
      recentAction: wl ? { type: 'select_watchlist', page: 'research', label: wl.name, timestamp: Date.now() } : prev.recentAction,
    }));
  }, []);

  const setActivePreset = useCallback((preset) => {
    setWorkspace(prev => ({
      ...prev,
      activePreset: preset,
      recentAction: preset ? { type: 'load_preset', page: 'research', label: preset.name, timestamp: Date.now() } : prev.recentAction,
    }));
  }, []);

  const recordAction = useCallback((action) => {
    setWorkspace(prev => ({
      ...prev,
      recentAction: { ...action, timestamp: Date.now() },
    }));
  }, []);

  return (
    <WorkspaceContext.Provider value={{
      ...workspace,
      setActiveInstrument,
      setActiveWatchlist,
      setActivePreset,
      recordAction,
    }}>
      {children}
    </WorkspaceContext.Provider>
  );
}

export function useWorkspace() {
  const ctx = useContext(WorkspaceContext);
  if (!ctx) throw new Error('useWorkspace must be inside WorkspaceProvider');
  return ctx;
}
