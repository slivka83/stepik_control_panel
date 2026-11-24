// Single source for the API prefix. VITE_API_URL may point to another origin
// (e.g. a separate backend); all auth and API calls must use the same base.
export const API_BASE = (import.meta.env.VITE_API_URL || '/api').replace(/\/+$/, '');

export function apiUrl(path) {
  const normalized = path.startsWith('/') ? path : `/${path}`;
  return `${API_BASE}${normalized}`;
}
