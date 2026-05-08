import { useCallback, useEffect, useRef, useState } from 'react';
import { apiFetch } from './useApi';

/**
 * useLiveBrokerTruth — poll the live read-through Trading 212 endpoints.
 *
 * Returns up-to-date positions + summary by polling
 *   - GET /broker/t212/live/positions  (default TTL ~2s on backend)
 *   - GET /broker/t212/live/summary    (default TTL ~10s on backend)
 *
 * Many concurrent tabs are safe: the backend coalesces and rate-limits
 * the upstream T212 calls (1 req/sec for positions per T212 docs).
 *
 * Behavior:
 *   - Polls only while `pageVisible` is true (caller passes
 *     document.visibilityState awareness).
 *   - Pauses polling when the tab is hidden; resumes on visibility return.
 *   - Falls back to the DB-backed summary in `fallback` if the live
 *     endpoint reports cache_status="error" or if the network request
 *     itself fails.
 *   - Exposes `refresh()` for the manual "Refresh broker truth" button.
 *
 * This hook NEVER calls a T212 write endpoint, NEVER triggers the
 * scheduled DB sync job, and NEVER creates execution objects. It only
 * reads via the readonly live read-through API.
 *
 * @param {object} opts
 * @param {boolean} opts.pageVisible       True while the host tab is visible.
 * @param {object|null} opts.fallback      DB-backed portfolio summary used
 *                                         when live endpoints are unavailable.
 * @param {number} [opts.positionsIntervalMs=3000]  Positions poll cadence.
 *                                         Floor of 1500ms is enforced; the
 *                                         backend cache will still throttle
 *                                         upstream T212 calls if a faster
 *                                         interval is requested.
 * @param {number} [opts.summaryIntervalMs=10000]   Summary poll cadence.
 */
export function useLiveBrokerTruth({
  pageVisible,
  fallback = null,
  positionsIntervalMs = 3000,
  summaryIntervalMs = 10000,
} = {}) {
  // Floor the intervals so a misconfigured caller cannot try to poll
  // faster than the backend cache can ever serve fresh values.
  const posInterval = Math.max(1500, positionsIntervalMs);
  const sumInterval = Math.max(5000, summaryIntervalMs);

  const [positions, setPositions] = useState(null);
  const [summary, setSummary] = useState(null);
  const [livePositionsMeta, setLivePositionsMeta] = useState(null);
  const [liveSummaryMeta, setLiveSummaryMeta] = useState(null);
  const [error, setError] = useState(null);
  const positionsTimerRef = useRef(null);
  const summaryTimerRef = useRef(null);
  const inFlightRef = useRef({ positions: false, summary: false });

  const fetchPositions = useCallback(async () => {
    if (inFlightRef.current.positions) return;
    inFlightRef.current.positions = true;
    try {
      const res = await apiFetch('/broker/t212/live/positions');
      if (res && res.payload) {
        // Normalize the live position shape to match the DB-backed
        // /portfolio/summary positions so the same UI components can render
        // either source. Live positions do NOT carry instrument_id (they
        // bypass the DB by design); consumers must handle that gracefully.
        const normalized = (res.payload.positions || []).map(p => ({
          instrument_id: null,
          broker_ticker: p.broker_ticker,
          quantity: p.quantity,
          avg_cost: p.avg_cost,
          current_price: p.current_price,
          market_value: p.current_value ?? (p.quantity || 0) * (p.current_price || 0),
          pnl: p.pnl,
          pnl_percent: p.avg_cost > 0 && p.current_price != null
            ? ((p.current_price - p.avg_cost) / p.avg_cost) * 100
            : 0,
          currency: p.account_currency || p.instrument_currency,
          snapshot_at: null,
          instrument_name: p.instrument_name,
          isin: p.isin,
        }));
        setPositions(normalized);
        setLivePositionsMeta({
          source: res.source,
          cache_status: res.cache_status,
          live_fetched_at: res.live_fetched_at,
          provider_latency_ms: res.provider_latency_ms,
          rate_limit: res.rate_limit,
          stale_reason: res.stale_reason,
        });
        if (res.cache_status === 'error') {
          setError(res.stale_reason || 'live broker truth unavailable');
        } else {
          setError(null);
        }
      }
    } catch (e) {
      setError(e?.message || 'live broker truth unavailable');
    } finally {
      inFlightRef.current.positions = false;
    }
  }, []);

  const fetchSummary = useCallback(async () => {
    if (inFlightRef.current.summary) return;
    inFlightRef.current.summary = true;
    try {
      const res = await apiFetch('/broker/t212/live/summary');
      if (res && res.payload) {
        setSummary(res.payload);
        setLiveSummaryMeta({
          source: res.source,
          cache_status: res.cache_status,
          live_fetched_at: res.live_fetched_at,
          provider_latency_ms: res.provider_latency_ms,
          rate_limit: res.rate_limit,
          stale_reason: res.stale_reason,
        });
      }
    } catch (e) {
      // Summary failure is non-fatal — positions stand alone.
    } finally {
      inFlightRef.current.summary = false;
    }
  }, []);

  // Manual refresh: forces both calls. Used by the "Refresh broker truth"
  // button. Does not bypass the backend cache TTL — the backend decides
  // whether to call upstream or serve cached.
  const refresh = useCallback(() => {
    fetchPositions();
    fetchSummary();
  }, [fetchPositions, fetchSummary]);

  // Poll positions
  useEffect(() => {
    if (!pageVisible) {
      if (positionsTimerRef.current) {
        clearInterval(positionsTimerRef.current);
        positionsTimerRef.current = null;
      }
      return;
    }
    fetchPositions();
    positionsTimerRef.current = setInterval(fetchPositions, posInterval);
    return () => {
      if (positionsTimerRef.current) {
        clearInterval(positionsTimerRef.current);
        positionsTimerRef.current = null;
      }
    };
  }, [pageVisible, fetchPositions, posInterval]);

  // Poll summary on a slower cadence
  useEffect(() => {
    if (!pageVisible) {
      if (summaryTimerRef.current) {
        clearInterval(summaryTimerRef.current);
        summaryTimerRef.current = null;
      }
      return;
    }
    fetchSummary();
    summaryTimerRef.current = setInterval(fetchSummary, sumInterval);
    return () => {
      if (summaryTimerRef.current) {
        clearInterval(summaryTimerRef.current);
        summaryTimerRef.current = null;
      }
    };
  }, [pageVisible, fetchSummary, sumInterval]);

  // Pick the badge state for the UI
  let truthBadge = 'STALE';
  if (livePositionsMeta) {
    if (livePositionsMeta.cache_status === 'fresh') truthBadge = 'LIVE';
    else if (livePositionsMeta.cache_status === 'cached') truthBadge = 'CACHED';
    else if (livePositionsMeta.cache_status === 'rate_limited') truthBadge = 'CACHED';
    else truthBadge = 'STALE';
  }

  // If live failed entirely, downgrade to DB SNAPSHOT mode
  const usingDbFallback = positions === null;
  if (usingDbFallback) {
    truthBadge = 'DB SNAPSHOT';
  }

  // Compose: prefer live positions if we have them, else fallback DB
  const effectivePositions = positions !== null ? positions : (fallback?.positions || []);

  return {
    positions: effectivePositions,
    summary,
    livePositionsMeta,
    liveSummaryMeta,
    truthBadge,
    usingDbFallback,
    error,
    refresh,
  };
}
