import { useState, useEffect, useCallback } from 'react';
import { auth } from '../firebase';

// In production: set VITE_API_URL to Cloud Run URL
// In dev: empty string = same-origin (Vite proxy or localhost)
const API_BASE = import.meta.env.VITE_API_URL || '';
// AI calls route to separate US region service (avoids OpenAI geo-block from asia-east2)
const AI_API_BASE = import.meta.env.VITE_AI_API_URL || API_BASE;
const TIMEOUT_MS = 30_000;
const AI_TIMEOUT_MS = 90_000; // AI calls can take longer (model inference)

// Wait for Firebase Auth to resolve before getting token
let _authReady = null;
function waitForAuth() {
  if (_authReady) return _authReady;
  _authReady = new Promise((resolve) => {
    const unsub = auth.onAuthStateChanged(() => {
      unsub();
      resolve();
    });
  });
  return _authReady;
}

async function getAuthHeaders() {
  try {
    await waitForAuth();
    const user = auth.currentUser;
    if (user) {
      const token = await user.getIdToken();
      return { 'Authorization': `Bearer ${token}` };
    }
  } catch {}
  return {};
}

function getBase(path) {
  return path.startsWith('/ai/') ? AI_API_BASE : API_BASE;
}
function getTimeout(path) {
  return path.startsWith('/ai/') ? AI_TIMEOUT_MS : TIMEOUT_MS;
}

async function extractError(res) {
  try {
    const body = await res.json();
    return body.detail || body.message || body.error || `API ${res.status}`;
  } catch {
    return `API ${res.status} ${res.statusText || ''}`.trim();
  }
}

function withTimeout(signal, ms = TIMEOUT_MS) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), ms);
  // Forward any external abort
  if (signal) signal.addEventListener('abort', () => controller.abort());
  return { signal: controller.signal, clear: () => clearTimeout(timer) };
}

export async function apiFetch(path, { signal } = {}) {
  const timeout = withTimeout(signal, getTimeout(path));
  try {
    const headers = await getAuthHeaders();
    const res = await fetch(getBase(path) + path, { signal: timeout.signal, headers });
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
  const timeout = withTimeout(signal, getTimeout(path));
  try {
    const authHeaders = await getAuthHeaders();
    const res = await fetch(getBase(path) + path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders },
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
    const authHeaders = await getAuthHeaders();
    const res = await fetch(getBase(path) + path, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json', ...authHeaders },
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
    const authHeaders = await getAuthHeaders();
    const res = await fetch(getBase(path) + path, { method: 'DELETE', signal: timeout.signal, headers: authHeaders });
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
