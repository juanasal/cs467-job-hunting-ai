
# Authentication Testing

## Database Connection Testing

Before testing authentication, verify that the backend can successfully connect to the MySQL database.

The database configuration is stored in `backend/.env` and contains the following settings:

```env
DB_HOST=localhost
DB_PORT=3306
DB_NAME=jobhunt
DB_USER=root
DB_PASSWORD=your_mysql_password   
```

From the `backend/` directory, activate the virtual environment and run the database connection test:

```bash
.venv\Scripts\activate
python -m tests.test_db_connection
```

A successful connection displays a message similar to:

```text
Database connection successful!
Database: jobhunt
MySQL version: 8.0.46
```

## Starting the Backend

From the `backend/` directory, start the FastAPI development server:

```bash
uvicorn app.main:app --reload
```

Open the interactive API documentation in a browser:

`http://127.0.0.1:8000/docs`

You can try out the /api/auth/register and /api/auth/login
This is known as the Swagger UI

## Registration Testing

Registration is performed using `POST /api/auth/register`.

In Swagger UI, expand the registration endpoint, select **Try it out**, and submit the something like the example:

```json
{
    "email": "happyface@example.com",
    "password": "happyface123!"
}
```

A successful registration returns HTTP `201 Created`.

Example response:

```json
{
    "message": "Account created successfully.",
    "user": {
        "user_id": 3,
        "email": "happyface@example.com"
    }
}
```

The returned `user_id` may differ depending on existing database records.

To verify that the account was saved, execute the following query in MySQL Workbench:

```sql
USE jobhunt;

SELECT user_id, email, password_hash, created_at
FROM users
ORDER BY user_id DESC
LIMIT 5;
```

The account should appear in the results. The `password_hash` field should contain an Argon2id hash rather than the original password.

## Login Testing

Login is performed using `POST /api/auth/login`.

In Swagger UI, expand the login endpoint, select **Try it out**, and submit the credentials used during registration:

```json
{
    "email": "testuser@example.com",
    "password": "TestPassword123!"
}
```

A successful login returns HTTP `200 OK`.

Example response:

```json
{
    "message": "Login successful.",
    "user": {
        "user_id": 3,
        "email": "testuser@example.com"
    }
}
```

The response also sets an HTTP-only session cookie containing the generated session token.

An incorrect password or an unregistered email should return HTTP `401 Unauthorized`.

## Session Creation Testing

After a successful login, verify that a session was created in MySQL.

Execute the following query in MySQL Workbench:

```sql
USE jobhunt;

SELECT session_id, user_id, token_hash,
       created_at, last_activity_at,
       expires_at, revoked_at
FROM user_sessions
ORDER BY session_id DESC
LIMIT 5;
```

A successful login should create a new session record.

The returned database results should show:

| Field | Expected result |
| --- | --- |
| `session_id` | Automatically generated session ID |
| `user_id` | ID of the logged-in user |
| `token_hash` | 64-character SHA-256 hash |
| `created_at` | Session creation timestamp |
| `last_activity_at` | Initial activity timestamp |
| `expires_at` | Approximately seven days after creation |
| `revoked_at` | NULL |

To check the total number of sessions:

```sql
SELECT COUNT(*) AS total_sessions
FROM user_sessions;
```

Each successful login should increase the session count by one.

## Implemented Functionality

Database connectivity has been tested successfully. User registration, Argon2id password hashing, login credential verification, session token generation, SHA-256 token hashing, MySQL session creation, and HTTP-only session cookie creation have been implemented and tested.
