# Login Authentication**

## Registration and Login**

Users, including developers, can create their own accounts using an email address and password.

- Registration endpoint: `POST /api/auth/register`
- Login endpoint: `POST /api/auth/login`
- Logout endpoint: `POST /api/auth/logout`

Passwords will be hashed using Argon2id through the `pwdlib[argon2]` library before being stored in MySQL.

The existing `users` table in `backend/db/001_create_tables.sql` supports authentication with these fields:

| Field | Purpose |
| --- | --- |
| `user_id` | Unique account identifier |
| `email` | User's login email; duplicate emails are prevented by a unique constraint |
| `password_hash` | Hashed password |
| `created_at` | Account creation timestamp |

Registration accepts an email and password. The backend validates the inputs, hashes the password, and stores the account in the existing `users` table. Login verifies the submitted password against the stored hash.

## Session Management**

The application will use server-side sessions stored in MySQL.

- Maximum session lifetime: 7 days.
- Idle timeout: 30 minutes.
- Logout: Revoke the current session and clear the browser cookie.
- Multiple sessions per user are allowed.

The browser will store the session identifier in an HTTP-only cookie. The backend will validate the session on authenticated requests and reject expired or revoked sessions.

The current database schema does not include a session table. A `user_sessions` table will be needed to store session information, including the associated user, session token hash, creation time, last activity, expiration, and revocation.

## Cookie Settings**

In production, the session cookie will use the name `__Host-session` and the following settings:

| Setting | Value | Purpose |
| --- | --- | --- |
| `HttpOnly` | `true` | Prevents JavaScript from reading the session cookie |
| `Secure` | `true` | Sends the cookie only over HTTPS |
| `SameSite` | `Lax` | Restricts cookie sending in cross-site contexts |
| `Path` | `/` | Makes the cookie available across the site's paths |
| `Domain` | Not set | Restricts the cookie to the host that created it |

The cookie will expire when the session expires. The backend must enforce session expiration independently of the cookie.

## Cross-Origin Requests (CORS)**

- Enable credentialed requests because authentication uses cookies.
- Configure frontend API requests to include credentials when needed.
- Use HTTPS for production frontend and backend traffic.

## CSRF Protection
- Require and validate a CSRF token for state-changing requests authenticated by cookies.
- Validate the Origin header against trusted frontend origins.
- Protect logout requests against CSRF.

## References
FastAPI security documentation: https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/
FastAPI CORS documentation: https://fastapi.tiangolo.com/tutorial/cors/
pwdlib documentation: https://frankie567.github.io/pwdlib/