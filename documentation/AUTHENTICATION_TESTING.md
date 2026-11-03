# Authentication Testing and Architecture Guide

## Purpose

This document outlines the authentication and session management design, endpoint contracts, and automated testing instructions for the Job Hunting AI Web Tool. It ensures full alignment across backend routes, database storage, frontend integrations, and validation tests.

---

## Architecture Overview

- **Session Storage:** Server-side sessions stored in MySQL (`user_sessions` table) using SHA-256 hashed tokens for database security.
- **Password Security:** Argon2id hashing via the `pwdlib` library.
- **Cookie Settings:** Configured as `__Host-session` in production and `session` in development, enforcing `HttpOnly`, `Secure`, `Lax` SameSite, and `Path=/`.
- **CSRF Defense:** Double Submit Cookie pattern requiring matching `csrf_token` cookies and `X-CSRF-Token` headers on state-changing requests, alongside strict `Origin` header validation against trusted origins (`TRUSTED_ORIGINS`).
- **Timeouts:** Enforces a 7-day absolute lifetime and a 30-minute idle inactivity timeout with sliding window updates.

---

## API Endpoints Contract

| Endpoint | Method | Status Codes | Description |
|---|---|---|---|
| `/api/auth/register` | POST | 201, 409, 422 | Registers a new user with an email and password. |
| `/api/auth/login` | POST | 200, 401, 422 | Authenticates credentials, creates a session, and sets secure cookies. |
| `/api/auth/me` | GET | 200, 401 | Validates the active session cookie and returns user profile details. |
| `/api/auth/csrf` | GET | 200 | Ensures a CSRF token cookie is present and returns it for client use. |
| `/api/auth/logout` | POST | 200, 401, 403 | Revokes session from the database and clears cookies. Requires CSRF and Origin checks. |

---

## Test Suite Structure

The integration test file is located at `tests/test_auth.py`. It automates the full 6-step lifecycle to verify correctness:

1. **Register** a test account (`POST /api/auth/register`).
2. **Login** to issue authentication and CSRF cookies (`POST /api/auth/login`).
3. **Verify Profile** using the active session (`GET /api/auth/me`).
4. **Fetch CSRF Token** for state-changing authorization (`GET /api/auth/csrf`).
5. **Logout** using valid Origin and X-CSRF-Token headers (`POST /api/auth/logout`).
6. **Verify Unauthorized Access** to ensure the session is terminated (`GET /api/auth/me` returning `401`).

---

## How to Run the Tests

Ensure your virtual environment is active and your MySQL database connection is configured in your environment variables. Run the test suite from your backend project root directory:

```powershell
pytest tests/test_auth.py -v -s
```

## Expected Terminal Output
tests/test_auth.py::test_auth_full_lifecycle 
🚀 STARTING AUTHENTICATION LIFECYCLE TESTS

============================================================
 STEP 1: POST /api/auth/register (User Registration)
============================================================
Payload: email=testuser_lifecycle@example.com, password=***
Response Status Code: 201
Response Body: {'message': 'Account created successfully.', 'user': {'user_id': 12, 'email': 'testuser_lifecycle@example.com'}}
-> STATUS: PASSED ✅
-> DETAILS: Code was 201 (Acceptable: 201 or 409)
------------------------------------------------------------

============================================================
 STEP 2: POST /api/auth/login (User Authentication)
============================================================
Payload: email=testuser_lifecycle@example.com, password=***
Response Status Code: 200
Response Body: {'message': 'Login successful.', 'user': {'user_id': 12, 'email': 'testuser_lifecycle@example.com'}}
Cookies Set by Server: ['session', 'csrf_token']
-> STATUS: PASSED ✅
-> DETAILS: Session cookies successfully established.
------------------------------------------------------------

============================================================
 STEP 3: GET /api/auth/me (Verify Active Session)
============================================================
Sending request with active session cookie...
Response Status Code: 200
Response Body: {'user': {'user_id': 12, 'email': 'testuser_lifecycle@example.com'}}
-> STATUS: PASSED ✅
-> DETAILS: Authenticated user profile retrieved successfully.
------------------------------------------------------------

============================================================
 STEP 4: GET /api/auth/csrf (Retrieve CSRF Token)
============================================================
Fetching CSRF token cookie/payload for state-changing request...
Response Status Code: 200
Response Body: {'csrf_token': 'abc123xyz...'}
-> STATUS: PASSED ✅
-> DETAILS: CSRF token acquired: abc123xyz...
------------------------------------------------------------

============================================================
 STEP 5: POST /api/auth/logout (Revoke Session & Clear Cookies)
============================================================
Headers sent: Origin=http://localhost:3000, X-CSRF-Token=abc123xyz...
Response Status Code: 200
Response Body: {'message': 'Logged out successfully.'}
Remaining Cookies: []
-> STATUS: PASSED ✅
-> DETAILS: Session revoked and cookies cleared.
------------------------------------------------------------

============================================================
 STEP 6: GET /api/auth/me (Post-Logout Check)
============================================================
Attempting to access /me with revoked/cleared session...
Response Status Code: 401
Response Body: {'error': {'status': 401, 'message': 'Authentication required.'}}
-> STATUS: PASSED ✅
-> DETAILS: Successfully rejected with 401 Unauthorized.
------------------------------------------------------------

🎉 ALL AUTHENTICATION LIFECYCLE TESTS COMPLETED SUCCESSFULLY!

PASSED [100%]