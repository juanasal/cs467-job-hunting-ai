"""Reusable helpers for reading and updating the MySQL database.

In a FastAPI route, ask for a connection with the DbConnection type:

    @app.get("/jobs/{job_id}")
    def read_job(job_id: int, conn: DbConnection):
        return fetch_one(conn, "SELECT * FROM jobs WHERE job_id = %s", (job_id,))

Outside a request (scripts, the job pipeline), use transaction():

    with transaction(get_settings()) as conn:
        execute(conn, "INSERT INTO user_skills (user_id, skill) VALUES (%s, %s)", (user_id, skill))

Always pass user-entered values in `params` using %s placeholders. Never build
SQL strings from user input with f-strings or +.
"""

from contextlib import contextmanager
from typing import Annotated

import pymysql
from fastapi import Depends, Request


def connect(settings):
    """Open a new connection. Rows come back as dicts, and changes need a commit."""
    # Aiven requires SSL. Giving the CA certificate also checks we reached the real server.
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
        # Make UPDATE report rows matched, not rows changed, so saving unchanged
        # values still counts as 1 instead of looking like a missing row.
        client_flag=pymysql.constants.CLIENT.FOUND_ROWS,
    )


@contextmanager
def transaction(settings):
    """Open a connection and group everything in the `with` block into one transaction.

    Saves (commits) all changes if the block finishes, undoes (rolls back) all of
    them if anything raises, and always closes the connection.
    """
    conn = connect(settings)
    try:
        yield conn
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except pymysql.MySQLError:
            # The connection is already gone, and MySQL undoes an unfinished
            # transaction when a connection drops. Ignoring this keeps the original error.
            pass
        raise
    finally:
        conn.close()


def get_db(request: Request):
    """FastAPI dependency: one transaction per request, closed when the request ends."""
    with transaction(request.app.state.settings) as conn:
        yield conn


# Use this as a route parameter's type to get a connection. scope="function" makes
# FastAPI commit before sending the response, so a failed save returns an error
# instead of a success. Plain Depends(get_db) would commit after the response is sent.
DbConnection = Annotated[pymysql.connections.Connection, Depends(get_db, scope="function")]


def fetch_one(conn, sql, params=None):
    """Run a SELECT and return the first row as a dict, or None if nothing matched."""
    with conn.cursor() as cursor:
        cursor.execute(sql, params)
        return cursor.fetchone()


def fetch_all(conn, sql, params=None):
    """Run a SELECT and return all rows as a list of dicts."""
    with conn.cursor() as cursor:
        cursor.execute(sql, params)
        return list(cursor.fetchall())


def execute(conn, sql, params=None):
    """Run an INSERT, UPDATE, or DELETE and return the number of rows it matched.

    0 means no row matched (e.g. an UPDATE for an id that doesn't exist). An UPDATE
    that matches a row but leaves its values the same still returns 1.

    The change is saved when the surrounding transaction commits. After an INSERT
    into a table with an AUTO_INCREMENT key, conn.insert_id() gives the new id.
    """
    with conn.cursor() as cursor:
        return cursor.execute(sql, params)
