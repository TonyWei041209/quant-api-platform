import { useState, useEffect, useCallback } from 'react';

// In production: set VITE_API_URL to Cloud Run URL
// In dev: empty string = same-origin (Vite proxy or localhost)
const API_BASE = import.meta.env.VITE_API_URL || '';
const TIMEOUT_MS = 30_000;

async function extractError(res) {
  try {
    const body = await res.json();
    return body.detail || body.message || body.error || `API ${res.status}`;
  } catch {
    return `API ${res.status} ${res.statusText || ''}`.trim();
  }
}

function withTimeout(signal) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  // Forward any external abort
  if (signal) signal.addEventListener('abort', () => controller.abort());
  return { signal: controller.signal, clear: () => clearTimeout(timer) };
}

export async function apiFetch(path, { signal } = {}) {
  const timeout = withTimeout(signal);
  try {
    const res = await fetch(API_BASE + path, { signal: timeout.signal });
    if (!res.ok) throw new Error(await extractError(res));
    return res.json();
  } catch (e) {
    if (e.name === 'AbortError') throw new Error('Request timed out');
    throw e;
  } finally {
    timeout.clear();
  }
}

export async function apiPost(path, body, { signal } = {}) {
  const timeout = withTimeout(signal);
  try {
    const res = await fetch(API_BASE + path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: timeout.signal,
    });
    if (!res.ok) throw new Error(await extractError(res));
    return res.json();
  } catch (e) {
    if (e.name === 'AbortError') throw new Error('Request timed out');
    throw e;
  } finally {
    timeout.clear();
  }
}

export async function apiPut(path, body, { signal } = {}) {
  const timeout = withTimeout(signal);
  try {
    const res = await fetch(API_BASE + path, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: timeout.signal,
    });
    if (!res.ok) throw new Error(await extractError(res));
    return res.json();
  } catch (e) {
    if (e.name === 'AbortError') throw new Error('Request timed out');
    throw e;
  } finally {
    timeout.clear();
  }
}

export async function apiDelete(path, { signal } = {}) {
  const timeout = withTimeout(signal);
  try {
    const res = await fetch(API_BASE + path, { method: 'DELETE', signal: timeout.signal });
    if (!res.ok) throw new Error(await extractError(res));
    return res.json();
  } catch (e) {
    if (e.name === 'AbortError') throw new Error('Request timed out');
    throw e;
  } finally {
    timeout.clear();
  }
}

export function useApi(path, deps = []) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const refetch = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await apiFetch(path);
      setData(result);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [path]);

  useEffect(() => { refetch(); }, [refetch, ...deps]);

  return { data, loading, error, refetch };
}
