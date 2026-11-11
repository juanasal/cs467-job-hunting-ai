"""Reusable helpers for reading and updating the MySQL database.

In a FastAPI route, use the DbConnection type:

    @app.get("/jobs/{job_id}")
    def read_job(job_id: int, conn: DbConnection):
        return fetch_one(conn, "SELECT * FROM jobs WHERE job_id = %s", (job_id,))

Outside a request (scripts, job pipeline), use transaction():

    with transaction(get_settings()) as conn:
        execute(
            conn,
            "INSERT INTO user_skills (user_id, skill) VALUES (%s, %s)",
            (user_id, skill)
        )

For standalone connections without automatic transaction handling:

    with get_db_connection() as conn:
        rows = fetch_all(conn, "SELECT * FROM jobs")

Always pass user-entered values using %s placeholders.
Never build SQL strings from user input with f-strings or +.
"""

from contextlib import contextmanager
from typing import Annotated

import pymysql
from fastapi import Depends, Request

from app.config import get_settings


def connect(settings):
    """Open a new MySQL connection. Rows come back as dictionaries."""

    # Aiven requires SSL. Providing the CA certificate verifies the server.
    ssl = {"ca": settings.db_ssl_ca} if settings.db_ssl_ca else None

    return pymysql.connect(
        host=settings.db_host,
        port=settings.db_port,
        user=settings.db_user,
        password=settings.db_password,
        database=settings.db_name,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
        ssl=ssl,
        # Report matched rows instead of only changed rows.
        client_flag=pymysql.constants.CLIENT.FOUND_ROWS,
    )


@contextmanager
def get_db_connection(settings=None):
    """Open a MySQL connection and always close it.

    Uses the application's settings by default, or supplied settings
    when connecting to a specific database (such as a test database).
    Does not automatically commit or roll back transactions.
    """
    if settings is None:
        settings = get_settings()

    connection = connect(settings)

    try:
        yield connection
    finally:
        connection.close()


@contextmanager
def transaction(settings):
    """Manage a database transaction.

    Commits changes if successful.
    Rolls back changes if an exception occurs.
    Always closes the connection.
    """
    conn = connect(settings)

    try:
        yield conn
        conn.commit()

    except Exception:
        try:
            conn.rollback()
        except pymysql.MySQLError:
            # Preserve the original exception if the connection is unavailable.
            pass
        raise

    finally:
        conn.close()


def get_db(request: Request):
    """FastAPI dependency: one transaction per request."""

    with transaction(request.app.state.settings) as conn:
        yield conn


# FastAPI route dependency.
# scope="function" commits before sending the response.
DbConnection = Annotated[
    pymysql.connections.Connection,
    Depends(get_db, scope="function"),
]


def fetch_one(conn, sql, params=None):
    """Execute SELECT and return the first row as a dictionary or None."""

    with conn.cursor() as cursor:
        cursor.execute(sql, params)
        return cursor.fetchone()


def fetch_all(conn, sql, params=None):
    """Execute SELECT and return all rows as a list of dictionaries."""

    with conn.cursor() as cursor:
        cursor.execute(sql, params)
        return list(cursor.fetchall())


def execute(conn, sql, params=None):
    """Execute INSERT, UPDATE, or DELETE and return matched row count.

    Changes are saved when the surrounding transaction commits.

    For AUTO_INCREMENT tables, use conn.insert_id() after INSERT
    to retrieve the newly generated ID.
    """

    with conn.cursor() as cursor:
        return cursor.execute(sql, params)
