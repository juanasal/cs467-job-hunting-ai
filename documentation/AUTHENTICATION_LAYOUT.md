
# Login Authentication

## Registration and Login

Users, including developers, can create their own accounts using an email address and password.

- Registration endpoint: `POST /api/auth/register`
- Login endpoint: `POST /api/auth/login`
- Logout endpoint: `POST /api/auth/logout`

Example test credentials:

- **Email:** `user@example.com`
- **Password:** Secure password of your choice

Passwords are hashed using Argon2id through the `pwdlib[argon2]` library before being stored in MySQL.

The existing `users` table in `backend/db/migrations/001_create_tables.sql` supports authentication with these fields:

| Field | Purpose |
| --- | --- |
| `user_id` | Unique account identifier |
| `email` | User's login email; duplicate emails are prevented by a unique constraint |
| `password_hash` | Hashed password |
| `created_at` | Account creation timestamp |

Registration validates the submitted email and password, hashes the password, and stores the account in the existing `users` table. Login verifies the submitted password against the stored hash.

## Session Management

The application uses server-side sessions stored in MySQL.

- Maximum session lifetime: 7 days.
- Idle timeout: 30 minutes.
- Logout: Revokes the current session and clears the browser cookies.
- Multiple sessions per user are allowed.

The browser stores the session identifier in an HTTP-only cookie. The backend validates the session on authenticated requests and rejects expired or revoked sessions.

Server-side session information is stored in the `user_sessions` table, created by `backend/db/migrations/003_create_user_sessions.sql`.

The table tracks:

- Associated user (`user_id`)
- SHA-256 token hash (`CHAR(64)`)
- Session creation time (`created_at`)
- Last activity time (`last_activity_at`)
- Session expiration (`expires_at`)
- Revocation timestamp (`revoked_at`)

Only the hashed session token is stored in the database. The original session token is stored in the browser cookie.

## Cookie Settings

Cookie naming and security settings are controlled by the `APP_ENV` environment variable.

- **Production** (`APP_ENV=production`): The session cookie uses the name `__Host-session`.
- **Local development**: The session cookie defaults to `session`.

| Setting | Value | Purpose |
| --- | --- | --- |
| `HttpOnly` | `true` for session cookie | Prevents JavaScript from reading the session cookie |
| `Secure` | `true` in production | Sends the cookie only over HTTPS |
| `SameSite` | `Lax` | Restricts cookie sending in cross-site contexts |
| `Path` | `/` | Makes the cookie available across the site's paths |
| `Domain` | Not set | Restricts the cookie to the host that created it |

The CSRF cookie is readable by frontend JavaScript so it can be sent in the `X-CSRF-Token` request header. The session cookie remains HTTP-only.

The cookies have a maximum age of 7 days. The backend independently enforces session expiration and the 30-minute idle timeout.

## Cross-Origin Requests (CORS)

CORS is configured using the `FRONTEND_ORIGINS` environment variable.

- Multiple frontend origins can be separated by commas.
- Credentialed requests are enabled because authentication uses cookies.
- Frontend API requests must include credentials when needed.
- Production frontend and backend traffic must use HTTPS.
- Wildcard origins should not be used with credentialed requests.

Example local configuration:

`FRONTEND_ORIGINS=http://localhost:3000`

Example production configuration:

`FRONTEND_ORIGINS=https://your-frontend-domain.com`

## CSRF Protection

The application uses the Double Submit Cookie pattern for CSRF protection.

For logout requests:

- The frontend sends the `csrf_token` cookie value in the `X-CSRF-Token` request header.
- The backend compares the header value with the CSRF cookie.
- The backend requires an `Origin` header.
- The Origin must match one of the configured `FRONTEND_ORIGINS`.
- Requests with missing or untrusted Origin headers are rejected.

The logout endpoint requires both CSRF token and Origin validation.

## References

- FastAPI security documentation: https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/
- FastAPI CORS documentation: https://fastapi.tiangolo.com/tutorial/cors/
- pwdlib documentation: https://frankie567.github.io/pwdlib/

## AI Usage Citation

OpenAI. "Check Authentication Code" ChatGPT, conversational share link, OpenAI, 2026, https://chatgpt.com/share/6aea473a-6ca4-83e8-b5dc-f5cf30c9085c
