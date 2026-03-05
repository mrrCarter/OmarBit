const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

/** Thin wrapper around fetch that applies a default timeout via AbortSignal. */
export function fetchWithTimeout(url: string, init?: RequestInit & { timeoutMs?: number }): Promise<Response> {
  const { timeoutMs = 5000, ...rest } = init ?? {} as RequestInit & { timeoutMs?: number };
  return fetch(url, { ...rest, signal: rest.signal ?? AbortSignal.timeout(timeoutMs) });
}

export async function apiFetch(
  path: string,
  options: RequestInit & { token?: string; idempotencyKey?: string; timeoutMs?: number } = {}
) {
  const { token, idempotencyKey, timeoutMs = 15000, ...fetchOptions } = options;

  const headers = new Headers(fetchOptions.headers);
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  if (idempotencyKey) {
    headers.set("Idempotency-Key", idempotencyKey);
  }
  if (!headers.has("Content-Type") && fetchOptions.body) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...fetchOptions,
    headers,
    signal: fetchOptions.signal ?? AbortSignal.timeout(timeoutMs),
  });

  return response;
}
