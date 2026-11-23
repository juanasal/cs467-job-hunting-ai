// Shared helper for API requests that need the user to be signed in (JH-014).
//
// - Only relative "/api/..." paths are allowed, so the session cookie is only
//   sent to the backend configured in vite.config.js (dev) or vercel.json
//   (production). See documentation/decisions/authentication.md.
// - Cookies are always included.
// - State-changing requests (POST, PUT, PATCH, DELETE) get an X-CSRF-Token header.
// - A 401 response calls the handler set with setUnauthorizedHandler, so the
//   app can clear the signed-in UI and ask the user to sign in again.

let unauthorizedHandler = null;

export function setUnauthorizedHandler(handler) {
  unauthorizedHandler = handler;
}

async function getCsrfToken() {
  const response = await fetch("/api/auth/csrf", { credentials: "include" });
  const data = await response.json().catch(() => ({}));
  if (!response.ok || !data.csrf_token) {
    throw new Error("Could not verify your session. Please try again.");
  }
  return data.csrf_token;
}

export async function apiFetch(path, options = {}) {
  if (typeof path !== "string" || !path.startsWith("/api/")) {
    throw new Error(`apiFetch only accepts relative /api/ paths, got: ${path}`);
  }

  const method = (options.method || "GET").toUpperCase();
  const headers = new Headers(options.headers);

  if (!["GET", "HEAD", "OPTIONS"].includes(method)) {
    headers.set("X-CSRF-Token", await getCsrfToken());
  }

  const response = await fetch(path, {
    ...options,
    method,
    headers,
    credentials: "include",
  });

  if (response.status === 401) {
    unauthorizedHandler?.();
  }

  return response;
}
