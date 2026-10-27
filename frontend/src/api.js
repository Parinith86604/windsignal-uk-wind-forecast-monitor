const configuredBase = (import.meta.env.VITE_API_BASE_URL || '').trim().replace(/\/$/, '');
const apiBase = configuredBase || '/api';

export async function getAnalysis({ month = '2026-01', horizonHours = 24 } = {}) {
  const url = new URL(`${apiBase}/analysis`, window.location.origin);
  url.searchParams.set('month', month);
  url.searchParams.set('horizon_hours', String(horizonHours));
  const response = await fetch(url.toString(), { headers: { Accept: 'application/json' } });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = payload.detail || `Request failed (${response.status})`;
    throw new Error(detail);
  }
  return payload;
}

export async function getHealth() {
  const response = await fetch(`${apiBase}/health`, { headers: { Accept: 'application/json' } });
  if (!response.ok) throw new Error('API health check failed');
  return response.json();
}
