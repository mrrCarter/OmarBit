const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export async function apiFetch(
  path: string,
  options: RequestInit & { token?: string; idempotencyKey?: string } = {}
) {
  const { token, idempotencyKey, ...fetchOptions } = options;

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
  });

  return response;
}
