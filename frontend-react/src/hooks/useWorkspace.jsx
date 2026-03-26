import { createContext, useContext, useState, useCallback, useEffect } from 'react';
import { apiFetch } from './useApi';

/**
 * WorkspaceContext — lightweight cross-page state for workspace cohesion.
 *
 * Three context layers (matching portfolio_service.py contract):
 *
 * SESSION layer (this context):
 *   - activeInstrument: currently focused instrument (id + name + ticker)
 *   - activeWatchlist: currently selected watchlist group
 *   - activePreset: most recently used/loaded preset
 *   - recentAction: last significant user action
 *   - portfolioSummary: latest portfolio snapshot (DERIVED, refreshed on load)
 *   - heldInstrumentIds: set of instrument IDs currently held (for quick lookup)
 *
 * DERIVED layer (portfolio_service.py):
 *   - Aggregated from broker_*_snapshot tables
 *   - Readonly, never writes to broker
 *
 * FACT layer (database):
 *   - broker_account_snapshot, broker_position_snapshot, broker_order_snapshot
 *   - Source of truth from broker readonly API
 *
 * BOUNDARY RULES:
 *   - portfolioSummary is a convenience cache, NOT a god object
 *   - It may be stale — always show snapshot_at / as_of to user
 *   - It is readonly — no write-back to broker
 *   - It is optional — pages must handle null/empty gracefully
 *   - It should NOT grow beyond: account + positions + recent_orders + held_ids
 */

const WorkspaceContext = createContext(null);

export function WorkspaceProvider({ children }) {
  const [workspace, setWorkspace] = useState({
    activeInstrument: null,     // { id, name, ticker }
    activeWatchlist: null,       // { id, name }
    activePreset: null,          // { id, name, type }
    recentAction: null,          // { type, page, label, timestamp }
    portfolioSummary: null,      // from /portfolio/summary — may be null if no broker
    heldInstrumentIds: new Set(), // quick lookup: is instrument X held?
  });

  // Load portfolio summary on mount (once)
  useEffect(() => {
    apiFetch('/portfolio/summary')
      .then(summary => {
        const heldIds = new Set(summary?.held_instrument_ids || []);
        setWorkspace(prev => ({
          ...prev,
          portfolioSummary: summary,
          heldInstrumentIds: heldIds,
        }));
      })
      .catch(() => {
        // Portfolio not available — broker not connected or no data
        // This is expected and not an error
      });
  }, []);

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

  const refreshPortfolio = useCallback(() => {
    apiFetch('/portfolio/summary')
      .then(summary => {
        const heldIds = new Set(summary?.held_instrument_ids || []);
        setWorkspace(prev => ({
          ...prev,
          portfolioSummary: summary,
          heldInstrumentIds: heldIds,
        }));
      })
      .catch(() => {});
  }, []);

  // Helper: check if a specific instrument is held
  const isHeld = useCallback((instrumentId) => {
    return workspace.heldInstrumentIds.has(instrumentId);
  }, [workspace.heldInstrumentIds]);

  return (
    <WorkspaceContext.Provider value={{
      ...workspace,
      setActiveInstrument,
      setActiveWatchlist,
      setActivePreset,
      recordAction,
      refreshPortfolio,
      isHeld,
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
