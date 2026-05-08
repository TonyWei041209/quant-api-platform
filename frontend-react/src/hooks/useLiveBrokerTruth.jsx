import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { apiFetch } from './useApi';

/**
 * useLiveBrokerTruth — poll the live read-through Trading 212 endpoints and
 * pick a single broker-truth source for the whole Dashboard.
 *
 * Two endpoints are polled while the page is visible:
 *   - GET /broker/t212/live/positions  (backend cache TTL ~2s, floor 1.1s)
 *   - GET /broker/t212/live/summary    (backend cache TTL ~10s, floor 5.5s)
 *
 * The backend coalesces concurrent fetches and gates upstream calls behind
 * Trading 212's rate limits (positions: 1 req/s; account summary: ≥1 req/5s
 * conservative). Multiple tabs are safe.
 *
 * Source-selection rule (returned as `selectedSource` + `displayPositions`):
 *
 *   1. LIVE      — live cache_status="fresh", show live positions.
 *   2. CACHED    — live cache_status="cached" or "rate_limited" with a known
 *                  last-good payload, show last-good positions.
 *   3. CONNECTING — first live fetch hasn't completed yet AND fallback DB
 *                  data is available, show DB positions with a note.
 *   4. DB SNAPSHOT — live errored or stale, fall back to DB positions.
 *   5. STALE     — live errored AND no DB fallback available.
 *
 * "No open positions" is shown ONLY when:
 *   - selectedSource is LIVE and live confidently returned zero positions, or
 *   - selectedSource is DB SNAPSHOT and the DB explicitly has zero positions.
 *
 * Rate-limit backoff:
 *   When the backend returns cache_status="rate_limited" the hook slows its
 *   poll interval. If the response includes x-ratelimit-reset, we wait until
 *   that epoch before resuming; otherwise we fall back to a conservative
 *   30-second delay. Backend is the source of truth for upstream calls — the
 *   slow-poll loop simply re-reads the cached envelope and never burns
 *   T212 quota.
 *
 * This hook NEVER calls a Trading 212 write endpoint, NEVER triggers the
 * scheduled DB sync job, and NEVER creates execution objects. Read-through
 * only.
 *
 * @param {object} opts
 * @param {boolean} opts.pageVisible   True while the host tab is visible.
 * @param {object|null} opts.fallback  DB-backed portfolio summary used when
 *                                     live endpoints are unavailable.
 *                                     Shape matches /portfolio/summary.
 * @param {number} [opts.positionsIntervalMs=2000]  Positions poll cadence.
 *                                     Floor of 1500ms; matches backend cache
 *                                     floor of 1100ms. Pass 1500 for an
 *                                     opt-in "fast mode".
 * @param {number} [opts.summaryIntervalMs=10000]   Summary poll cadence.
 *                                     Floor of 5000ms.
 */
export function useLiveBrokerTruth({
  pageVisible,
  fallback = null,
  positionsIntervalMs = 2000,
  summaryIntervalMs = 10000,
} = {}) {
  // Floor the intervals so a misconfigured caller cannot try to poll faster
  // than the backend cache can serve fresh values.
  const posInterval = Math.max(1500, positionsIntervalMs);
  const sumInterval = Math.max(5000, summaryIntervalMs);

  const [positions, setPositions] = useState(null);
  const [summary, setSummary] = useState(null);
  const [livePositionsMeta, setLivePositionsMeta] = useState(null);
  const [liveSummaryMeta, setLiveSummaryMeta] = useState(null);
  const [error, setError] = useState(null);
  const [backoffUntil, setBackoffUntil] = useState(0); // epoch seconds

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
        // /portfolio/summary positions so the same UI components render
        // either source. Live positions do not carry instrument_id (they
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

        // Only treat live data as authoritative when the envelope says so.
        // For "error" status we keep the previous live positions (or null
        // if we have none) and let the source-selection rule fall back.
        const isAuthoritative = res.cache_status === 'fresh'
          || res.cache_status === 'cached'
          || (res.cache_status === 'rate_limited' && normalized.length > 0);

        if (isAuthoritative) {
          setPositions(normalized);
          setError(null);
        } else if (res.cache_status === 'error') {
          // Do NOT overwrite a successful previous live snapshot with an
          // empty error envelope. The source-selection rule will pick
          // DB SNAPSHOT (or STALE if there is no fallback either).
          setError(res.stale_reason || 'live broker truth unavailable');
        }

        setLivePositionsMeta({
          source: res.source,
          cache_status: res.cache_status,
          live_fetched_at: res.live_fetched_at,
          provider_latency_ms: res.provider_latency_ms,
          rate_limit: res.rate_limit,
          stale_reason: res.stale_reason,
        });

        // Rate-limit backoff: respect x-ratelimit-reset if provided, else
        // back off conservatively for 30 seconds.
        if (res.cache_status === 'rate_limited') {
          const resetRaw = res?.rate_limit?.['x-ratelimit-reset'];
          const resetEpoch = resetRaw != null ? parseFloat(resetRaw) : NaN;
          if (Number.isFinite(resetEpoch) && resetEpoch > Date.now() / 1000) {
            setBackoffUntil(resetEpoch + 1); // +1s buffer
          } else {
            setBackoffUntil(Date.now() / 1000 + 30);
          }
        } else {
          setBackoffUntil(0);
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
        if (res.cache_status === 'fresh' || res.cache_status === 'cached') {
          setSummary(res.payload);
        }
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
  // button. Does not bypass the backend cache TTL — backend decides whether
  // to call upstream or serve cached. Never runs the DB sync job and never
  // writes the database.
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
    const tick = () => {
      // Skip the upstream-bound fetch while in a rate-limit backoff window.
      // Backend already serves cached without calling T212, but skipping
      // here also keeps console noise low.
      if (backoffUntil > Date.now() / 1000) return;
      fetchPositions();
    };
    positionsTimerRef.current = setInterval(tick, posInterval);
    return () => {
      if (positionsTimerRef.current) {
        clearInterval(positionsTimerRef.current);
        positionsTimerRef.current = null;
      }
    };
  }, [pageVisible, fetchPositions, posInterval, backoffUntil]);

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

  // ---- Source-selection rule ----
  //
  // All three Dashboard cards (Portfolio, Holdings, Unrealized P&L) read
  // these computed fields. The whole point of doing the selection here is
  // that every card sees the same answer — no more "Holdings says empty,
  // P&L says 2 positions" inconsistency.
  const selection = useMemo(() => {
    const liveStatus = livePositionsMeta?.cache_status;
    const liveLoaded = livePositionsMeta !== null;
    const liveAuthoritative = positions !== null && (
      liveStatus === 'fresh'
      || liveStatus === 'cached'
      || (liveStatus === 'rate_limited' && positions.length > 0)
    );
    const fallbackPositions = Array.isArray(fallback?.positions) ? fallback.positions : null;

    if (liveAuthoritative) {
      const badge = liveStatus === 'fresh' ? 'LIVE' : 'CACHED';
      return {
        selectedSource: badge,
        displayPositions: positions,
        dataOrigin: 'live',
        showDbWhileConnecting: false,
      };
    }
    if (!liveLoaded) {
      // First live fetch hasn't completed yet — show DB rows if we have them.
      if (fallbackPositions !== null) {
        return {
          selectedSource: 'CONNECTING',
          displayPositions: fallbackPositions,
          dataOrigin: 'db_fallback',
          showDbWhileConnecting: fallbackPositions.length > 0,
        };
      }
      return {
        selectedSource: 'CONNECTING',
        displayPositions: [],
        dataOrigin: 'none',
        showDbWhileConnecting: false,
      };
    }
    // Live errored or returned a non-authoritative envelope → DB fallback.
    if (fallbackPositions !== null) {
      return {
        selectedSource: 'DB SNAPSHOT',
        displayPositions: fallbackPositions,
        dataOrigin: 'db_fallback',
        showDbWhileConnecting: false,
      };
    }
    return {
      selectedSource: 'STALE',
      displayPositions: [],
      dataOrigin: 'none',
      showDbWhileConnecting: false,
    };
  }, [positions, livePositionsMeta, fallback]);

  // Suppress "No open positions" while the selected source is uncertain.
  // Show it only when LIVE confidently returned zero, or when DB SNAPSHOT
  // has zero (and is therefore the authoritative answer).
  const isConfidentlyEmpty =
    selection.displayPositions.length === 0 && (
      (selection.selectedSource === 'LIVE') ||
      (selection.selectedSource === 'DB SNAPSHOT'
        && Array.isArray(fallback?.positions)
        && fallback.positions.length === 0)
    );

  // Aggregate totals for the P&L card — derived from displayPositions so
  // every card agrees on the number of positions and the total P&L.
  const totalPnL = selection.displayPositions.reduce(
    (sum, p) => sum + (Number(p.pnl) || 0),
    0
  );
  const totalMarketValue = selection.displayPositions.reduce(
    (sum, p) => sum + (Number(p.market_value) || 0),
    0
  );

  return {
    positions: selection.displayPositions,
    summary,
    livePositionsMeta,
    liveSummaryMeta,
    selectedSource: selection.selectedSource,
    dataOrigin: selection.dataOrigin,
    showDbWhileConnecting: selection.showDbWhileConnecting,
    isConfidentlyEmpty,
    totalPnL,
    totalMarketValue,
    error,
    refresh,
    // Back-compat aliases for older callers; deprecated.
    truthBadge: selection.selectedSource,
    usingDbFallback: selection.dataOrigin === 'db_fallback',
  };
}
