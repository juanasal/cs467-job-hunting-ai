# Authentication Testing Guide

This guide explains how to run the Job Hunting AI authentication tests using a separate MySQL test database. The instructions use MySQL Workbench and Windows PowerShell.

## 1. What the tests cover

The current authentication test suite covers:

1. Full authentication lifecycle:
   - Register a test account (or continue if it already exists).
   - Log in.
   - Confirm `/api/auth/me` returns the authenticated user.
   - Retrieve a CSRF token.
   - Log out.
   - Confirm the session is no longer accepted.
2. Login with an incorrect password is rejected.
3. An altered session cookie is rejected.
4. An expired session is rejected.

The implementation also enforces a 30-minute idle timeout, but the four tests above do not directly test that timeout.

## 2. Create the test database and MySQL user

Open MySQL Workbench and connect using your existing MySQL administrator/root connection.

Run:

```sql
CREATE DATABASE IF NOT EXISTS job_hunting_ai_test;

CREATE USER IF NOT EXISTS 'jh_test'@'localhost'
IDENTIFIED BY 'your_private_test_password';

GRANT ALL PRIVILEGES ON job_hunting_ai_test.*
TO 'jh_test'@'localhost';

FLUSH PRIVILEGES;
```

Replace `your_private_test_password` with a password you choose.

If the account already exists and you need to reset its password:

```sql
ALTER USER 'jh_test'@'localhost'
IDENTIFIED BY 'your_private_test_password';

FLUSH PRIVILEGES;
```

## 3. Verify the MySQL setup

Check the MySQL port:

```sql
SELECT @@port;
```

The local MySQL server in this setup uses port `3306`.

Confirm the test database exists:

```sql
SHOW DATABASES LIKE 'job_hunting_ai_test';
```

Check the test user's permissions:

```sql
SHOW GRANTS FOR 'jh_test'@'localhost';
```

The account should have privileges on `job_hunting_ai_test`. It does not need global privileges.

## 4. Apply database migrations

In MySQL Workbench, select the test database:

```sql
USE job_hunting_ai_test;
```

Execute the migration files in order:

1. `backend/db/migrations/001_create_tables.sql`
2. `backend/db/migrations/002_create_tables.sql`

Make sure `job_hunting_ai_test` is the active schema before executing each migration.

Verify the tables:

```sql
SHOW TABLES;
```

The authentication tests require at least:

```sql
SHOW TABLES LIKE 'users';
SHOW TABLES LIKE 'user_sessions';
```

## 5. Configure test database credentials

The test fixture uses `TEST_DB_*` environment variables to connect to the isolated test database. Authentication routes use the application's regular `DB_*` settings outside the test fixture.

### Option A: PowerShell

Open the VS Code terminal in the `backend` directory.

Set these variables:

```powershell
$env:TEST_DB_HOST = "127.0.0.1"
$env:TEST_DB_PORT = "3306"
$env:TEST_DB_NAME = "job_hunting_ai_test"
$env:TEST_DB_USER = "jh_test"
$env:TEST_DB_PASSWORD = "your_private_test_password"
$env:TEST_DB_SSL_CA = ""
```

Replace the password placeholder with the password assigned to `jh_test`.

These variables apply to the current PowerShell terminal session. If you open a new terminal, set them again.

### Option B: backend/.env

Alternatively, add these values to `backend/.env`:

```dotenv
TEST_DB_HOST=127.0.0.1
TEST_DB_PORT=3306
TEST_DB_NAME=job_hunting_ai_test
TEST_DB_USER=jh_test
TEST_DB_PASSWORD=your_private_test_password
TEST_DB_SSL_CA=
```

Replace the password placeholder. Do not commit `.env` files or passwords to source control.

## 6. Run authentication tests

From the `backend` directory, run:

```powershell
python -m pytest tests/test_auth.py -v -s
```

The test file should run these four tests:

- `test_auth_full_lifecycle`
- `test_login_wrong_password`
- `test_altered_session_cookie`
- `test_expired_session`

A successful run should end with a summary similar to:

```text
4 passed
```

To run the entire backend test suite:

```powershell
python -m pytest -v
```

## 7. Troubleshooting

### Error 1045: Access denied for user

Example:

```text
Access denied for user 'jh_test'@'localhost'
```

Check that:

- `TEST_DB_USER` is set to `jh_test`.
- `TEST_DB_PASSWORD` matches the current password for `jh_test`.
- The MySQL account exists as `'jh_test'@'localhost'`.
- The MySQL server is running.

If necessary, reset the test account password in Workbench using the `ALTER USER` statement in Step 2. Update the PowerShell variable or `.env` value afterward.

Do not share your password in screenshots or source code.

### Unknown database

Check that the database exists:

```sql
SHOW DATABASES LIKE 'job_hunting_ai_test';
```

If it does not exist, rerun the `CREATE DATABASE` statement.

### Table does not exist

Make sure the test database is selected:

```sql
USE job_hunting_ai_test;
SHOW TABLES;
```

Then execute both migrations in order.

### Tests connect to the wrong database

Check that all five required `TEST_DB_*` variables are set in the same PowerShell terminal where pytest is running.

The test fixture should build its settings from the test variables and temporarily replace the authentication module's database connection function for the test run.

Do not replace the application's normal `DB_*` credentials with test credentials just to make the tests pass.

### Placeholder database credentials appear in an error

If an error mentions a placeholder such as `your_database_user`, a test may be opening a connection through the application's normal database configuration instead of the test database connection.

The expired-session test must use the test database connection fixture when updating `user_sessions`. It should not call the original `get_db_connection()` directly.

### Port or connection refused

The local MySQL server in this setup uses port `3306`.

Confirm that the MySQL Windows service is running and that `TEST_DB_PORT` is set to `3306`.

## 8. Manual verification checklist

After the automated tests pass, these behaviors can also be checked through the API:

- [ ] Register a new account with a valid email and password.
- [ ] Confirm duplicate registration is rejected.
- [ ] Log in with the correct credentials.
- [ ] Confirm the session cookie is set.
- [ ] Request `/api/auth/me` and confirm the logged-in user is returned.
- [ ] Request `/api/auth/csrf` and confirm a CSRF token is returned.
- [ ] Send a state-changing authenticated request with the required Origin and CSRF token.
- [ ] Log out.
- [ ] Confirm the session cookie is cleared.
- [ ] Request `/api/auth/me` again and confirm the request is unauthorized.
- [ ] Confirm an invalid or altered session cookie is rejected.
- [ ] Confirm an expired session is rejected.

## 9. Security reminders

- Use a dedicated test database.
- Do not point automated tests at a database containing data you need to preserve.
- Use a separate MySQL test account with access limited to the test database.
- Keep passwords in local environment variables or an untracked `.env` file.
- Never commit `.env` files, database passwords, session tokens, or other secrets.
- The application generates a random session token for the browser cookie and stores only its SHA-256 hash in `user_sessions`.
- Logout revokes the server-side session and clears the session and CSRF cookies.
- In production, the session cookie uses the `__Host-session` name and secure cookie settings. Local development uses the `session` cookie name.
- The current automated tests check session expiration but do not directly simulate the 30-minute idle timeout.