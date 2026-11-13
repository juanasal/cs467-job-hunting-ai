# Authentication and Session Management Decision

- **Status:** Accepted for the MVP
- **Scope:** Backend registration, login, cookie sessions, CSRF validation, and logout

## Context

The Job Hunting AI API needs account authentication for protected user data. The MVP uses MySQL already present in the project and should support multiple active browser sessions per account without storing raw session credentials in the database.

## Decision

### Accounts and passwords

- `POST /api/auth/register` creates an account in `users`.
- `POST /api/auth/login` verifies credentials and creates a server-side session.
- Passwords are hashed with Argon2id through `pwdlib[argon2]`.
- Email addresses are trimmed and normalized to lowercase before lookup/storage.
- Login failures use the same `401 Invalid email or password` response for unknown email and incorrect password.

### Session storage and lifetime

The `user_sessions` table stores:

- `user_id` — account owning the session;
- `token_hash` — SHA-256 hash of a cryptographically random session token;
- `created_at` and `last_activity_at` — UTC timestamps;
- `expires_at` — absolute expiration timestamp;
- `revoked_at` — UTC logout timestamp, or `NULL` while active.

The raw session token is sent only to the browser in an HttpOnly cookie. The database stores only its SHA-256 hash.

Session rules:

- Idle timeout: 30 minutes since `last_activity_at`.
- Absolute lifetime: 7 days from session creation; activity does not extend this deadline.
- Multiple sessions per user are allowed.
- Logging out revokes only the session presented by that browser.
- Expired or revoked sessions are rejected by protected endpoints.

### Session validation and logout concurrency

Session validation reads the session row using `SELECT ... FOR UPDATE`, checks revocation and both expiration limits, updates `last_activity_at`, and commits before the protected endpoint handler proceeds. Logout updates `revoked_at` in a database transaction and commits before returning success.

The concurrency guarantee is:

1. **After the logout transaction commits, any new session validation must reject that token.** The validation query checks `revoked_at IS NULL` while taking a row lock, so it observes the committed revocation.
2. **A request that completed session validation before logout committed may continue running.** Authentication is checked at request entry; the API does not cancel handlers that are already executing.
3. **If logout cannot commit the revocation, logout returns HTTP 500 and does not report success.** Cookie-clearing headers are not returned as a successful logout. The browser can retry; the server-side session remains usable unless the database confirms revocation.

This is request-entry authorization, not immediate cancellation of in-flight work. Endpoints requiring stronger mid-operation revocation would need to re-check authorization inside their critical transaction.

### Cookies

`APP_ENV` is loaded from `backend/.env` before the authentication module selects cookie settings. Process environment variables take precedence over `.env` values.

| Environment | Session cookie name | Secure | HttpOnly | SameSite | Path | Domain |
|---|---|---:|---:|---|---|---|
| Local development | `session` | No | Yes | `Lax` | `/` | Not set |
| Production | `__Host-session` | Yes | Yes | `Lax` | `/` | Not set |

The `__Host-` prefix requires Secure, Path `/`, and no Domain attribute. The separate `csrf_token` cookie is readable by frontend JavaScript and is also Secure in production. Both cookies have a seven-day Max-Age; the server remains authoritative for idle and absolute expiration.

### CORS and CSRF

- `FRONTEND_ORIGINS` is the allowlist for credentialed CORS and Origin validation.
- State-changing logout requests require an `Origin` header exactly matching an allowed frontend origin.
- The request must include `X-CSRF-Token`, and its value must match the `csrf_token` cookie using constant-time comparison.
- Missing/untrusted Origin or missing/mismatched CSRF values are rejected with HTTP 403 before revocation.
- A rejected logout does not revoke the session.

## Deployment constraint: frontend and backend sites

`SameSite=Lax` cookies work for same-site deployments, such as a frontend and API exposed under one site (for example, a frontend `/api` proxy to the backend). They are not a reliable choice when the browser calls a backend on a different site, such as unrelated Vercel and Render hostnames. For that topology, either:

1. route API requests through a same-site frontend proxy and retain `SameSite=Lax`; or
2. deliberately configure cross-site cookies as `SameSite=None; Secure`, while retaining credentialed CORS and CSRF protections.

The deployment topology must be selected and verified before production login is considered complete. The current implementation and tests use `SameSite=Lax`; they do not claim that direct cross-site Vercel-to-Render cookies work.

## Database migration

The session table is created by `backend/db/migrations/003_create_user_sessions.sql`. Migration `002` is reserved for `002_add_jobs_first_seen_at.sql`, which already exists on `main`.

## Consequences

- Sessions can be revoked individually and audited through `revoked_at`.
- A database outage during logout prevents a false success response.
- In-flight requests that authenticated before logout commits may finish.
- The frontend must send credentials and implement the double-submit CSRF header for state-changing requests.
- Production cookie behavior depends on correct `APP_ENV` and the selected deployment topology.

## Verification

The integration suite in `backend/tests/test_auth.py` covers credential rejection, session creation, cookie attributes, altered/expired/idle sessions, absolute lifetime preservation, logout token replay, CSRF/Origin rejection, and multiple independent sessions. It requires the isolated `TEST_DB_*` MySQL database.
