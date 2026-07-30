import ky from 'ky';

// Distinct from neurospect-app's token key to avoid a same-origin localStorage
// collision when both apps run on localhost during development.
const TOKEN_KEY = 'neurospect_learn_token';

/** The API origin. Exported because some URLs the API returns are app-relative
 * (the local storage backend's signed evidence reads) and must be resolved
 * against the API, not the SPA origin. */
export const API_BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

export const api = ky.create({
  baseUrl: API_BASE_URL + '/',
  hooks: {
    beforeRequest: [
      ({ request }) => {
        const token = localStorage.getItem(TOKEN_KEY);
        if (token) {
          request.headers.set('Authorization', `Bearer ${token}`);
        }
      },
    ],
    afterResponse: [
      ({ response }) => {
        if (response.status === 401) {
          localStorage.removeItem(TOKEN_KEY);
          window.location.href = '/login';
        }
        return response;
      },
    ],
  },
});

export { TOKEN_KEY };

/**
 * The FastAPI `detail` payload from a failed request, or null.
 *
 * ky v2 CONSUMES the response body to populate `error.data`, so
 * `error.response.json()` throws — reading it that way silently produced ky's
 * generic "Request failed with status code 4xx" instead of the server's message.
 * (Found in Phase E2: it had been swallowing the 5e-1 ladder-gate reason too.)
 * `error.data` is the supported accessor; the `response.json()` branch stays as a
 * fallback for any error shape that still has an unread body.
 */
export async function apiErrorDetail(e: unknown): Promise<unknown> {
  const err = e as { data?: unknown; response?: { json?: () => Promise<unknown> } };
  const fromData = err?.data;
  if (fromData && typeof fromData === 'object' && 'detail' in fromData) {
    return (fromData as { detail: unknown }).detail;
  }
  if (typeof fromData === 'string' && fromData) return fromData;
  if (typeof err?.response?.json === 'function') {
    try {
      const body = (await err.response.json()) as { detail?: unknown };
      if (body?.detail) return body.detail;
    } catch {
      /* body already consumed — nothing more to read */
    }
  }
  return null;
}

/** A human-readable message for a failed request, preferring the server's. */
export async function apiErrorMessage(e: unknown, fallback = 'Request failed'): Promise<string> {
  const detail = await apiErrorDetail(e);
  if (typeof detail === 'string') return detail;
  if (detail && typeof detail === 'object') {
    if ('message' in detail && typeof (detail as { message: unknown }).message === 'string') {
      return (detail as { message: string }).message;
    }
    // FastAPI validation errors arrive as a list of {loc, msg, type}.
    if (Array.isArray(detail)) {
      const msgs = detail
        .map((d) => (d && typeof d === 'object' && 'msg' in d ? String((d as { msg: unknown }).msg) : null))
        .filter(Boolean);
      if (msgs.length) return msgs.join(' ');
    }
    return JSON.stringify(detail);
  }
  return e instanceof Error ? e.message : fallback;
}
