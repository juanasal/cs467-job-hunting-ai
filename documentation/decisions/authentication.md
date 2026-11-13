# Authentication Architecture Decision
- **Decision:** Use a Vercel reverse proxy for production API requests and retain `SameSite=Lax` authentication cookies.

## Context

The Job Hunting AI application uses a React frontend hosted on Vercel and a FastAPI backend hosted on Render.

The backend uses cookie-based authentication with server-side sessions stored in MySQL.

The session cookie is HTTP-only, secure in production, and uses the `__Host-session` name. The application also uses a CSRF token cookie and validates the request Origin.

The frontend and backend have different hostnames:

- Frontend: `https://your-app.vercel.app`
- Backend: `https://your-api.onrender.com`

When the browser sends a request directly from the Vercel frontend to the Render backend, the request is cross-site.

The production session cookie currently uses `SameSite=Lax`. Browsers generally do not send `SameSite=Lax` cookies with cross-site `fetch` requests.

As a result, a user may successfully log in but appear unauthenticated on subsequent API requests.

The architecture must provide reliable cookie-based authentication without weakening the existing session and CSRF protections.

## Decision

Use Vercel as a reverse proxy for backend API requests.

The browser will send API requests to the Vercel frontend origin under `/api/*`. Vercel will forward those requests to the Render backend.

For example:

```text
Browser
  |
  | https://your-app.vercel.app/api/auth/login
  v
Vercel
  |
  | Forward /api/* to Render
  v
Render FastAPI backend
```

The browser will not call the Render hostname directly for normal application API requests.

The frontend will use relative API paths:

```javascript
fetch("/api/auth/me", {
  credentials: "include"
});
```

Vercel will forward the request to the corresponding Render API path.

The production session cookie will retain these settings:

| Attribute | Value |
| --- | --- |
| Name | `__Host-session` |
| `HttpOnly` | `true` |
| `Secure` | `true` |
| `SameSite` | `Lax` |
| `Path` | `/` |
| `Domain` | Not set |

The CSRF cookie will remain readable by frontend JavaScript so its value can be sent in the `X-CSRF-Token` request header.

The backend will continue validating trusted Origin headers and CSRF tokens.

## Alternatives Considered

### Option 1: Vercel reverse proxy — selected

Configure Vercel to forward `/api/*` requests to the Render backend.

Advantages:

- The browser communicates with the Vercel frontend origin.
- Authentication cookies remain first-party to the browser-facing site.
- `SameSite=Lax` can be retained.
- No dependency on third-party cookie availability.
- The frontend can use consistent relative API paths in local and production environments.
- The backend can remain independently hosted on Render.

Disadvantages:

- Requires Vercel rewrite configuration.
- Requires frontend API calls to use relative paths.
- Requires deployment configuration and production verification.
- Adds a proxy hop between the browser and backend.

This is the preferred option because it addresses the cross-site cookie issue without relying on third-party cookies.

### Option 2: Use `SameSite=None; Secure` — not selected

Configure the session and CSRF cookies with `SameSite=None; Secure` and continue making direct cross-site requests from Vercel to Render.

Advantages:

- Allows cookies to be sent with cross-site requests in browsers that permit them.
- Does not require a Vercel reverse proxy.

Disadvantages:

- Requires credentialed cross-origin requests and correctly configured CORS.
- Makes authentication dependent on browser third-party cookie policies.
- Some browsers and privacy settings block or restrict third-party cookies.
- Requires additional cross-origin deployment testing.

This option was not selected because it is less reliable across browsers and privacy configurations.

## Consequences

### Frontend

The frontend must use relative API paths.

Examples:

```text
/api/auth/register
/api/auth/login
/api/auth/me
/api/auth/csrf
/api/auth/logout
```

The frontend must not use the Render backend hostname directly for normal application API requests.

Requests that rely on authentication cookies must include credentials.

### Vercel

The Vercel project must include a rewrite that forwards `/api/*` to the Render backend.

Example:

```json
{
  "rewrites": [
    {
      "source": "/api/:path*",
      "destination": "https://YOUR-RENDER-SERVICE.onrender.com/api/:path*"
    }
  ]
}
```

The destination hostname must be replaced with the actual Render service hostname.

The rewrite must preserve the `/api/` prefix.

The `vercel.json` file must be located in the Vercel project's configured Root Directory.

### Render backend

The Render backend remains responsible for:

- Account registration and login.
- Password hashing and verification.
- Creating and validating server-side sessions.
- Enforcing idle and absolute expiration.
- Revoking sessions during logout.
- Setting authentication and CSRF cookies.
- Validating CSRF tokens and request Origin headers.

The `FRONTEND_ORIGINS` environment variable must include the browser-facing Vercel frontend origin.

Example:

```text
FRONTEND_ORIGINS=https://your-app.vercel.app
```

The backend must not trust arbitrary origins.

### Cookies

The browser receives authentication cookies through the Vercel response.

Because the browser-facing response comes from the Vercel origin, the session cookie is stored for the Vercel hostname.

The `__Host-session` requirements must remain satisfied:

- `Secure` must be enabled.
- `Path=/` must be set.
- `Domain` must not be set.

The cookie must remain HTTP-only.

The session cookie must retain `SameSite=Lax`.

### CSRF protection

The reverse proxy does not replace CSRF protection.

The backend must continue requiring:

- A trusted Origin header.
- A CSRF token cookie.
- A matching `X-CSRF-Token` header.

The browser-facing Vercel origin must be included in the backend's trusted origin configuration.

### CORS

Browser requests to the Vercel `/api/*` path are same-origin requests.

CORS is therefore not required for those proxied browser requests.

The backend may retain its explicit CORS configuration for approved direct clients and local development. Credentialed CORS requests must use explicit allowed origins rather than a wildcard.

## Deployment Requirements

Before considering production authentication complete:

1. Configure the Vercel rewrite to forward `/api/*` to Render.
2. Confirm the rewrite is deployed.
3. Update frontend API calls to use relative paths.
4. Configure `FRONTEND_ORIGINS` in Render.
5. Confirm production cookie settings are selected from the production environment.
6. Verify login and session persistence in a real browser.
7. Verify that page refreshes retain authentication.
8. Verify CSRF-protected logout.
9. Verify that the original session token is rejected after logout.

## Security and Reliability Guarantee

The reverse proxy changes how requests reach the backend. It does not change the server-side session security model.

The backend must continue enforcing:

- Seven-day absolute session expiration.
- Thirty-minute idle timeout.
- Server-side session revocation.
- Password hashing with Argon2id.
- HTTP-only session cookies.
- CSRF validation.
- Trusted Origin validation.

Once logout's revocation transaction commits, subsequent session validations must reject the revoked session. Requests that already passed session validation before that commit may finish.

If database revocation fails, logout must return an error rather than report success.

## Review

Revisit this decision if:

- The frontend or backend hosting provider changes.
- The application adopts a custom shared domain.
- API requests must be made directly across different sites.
- Browser cookie policies or deployment requirements change.

The deployed authentication flow must be tested after changes to Vercel routing, Render configuration, or cookie settings.