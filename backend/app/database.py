from contextlib import contextmanager

import mysql.connector

from app.config import get_settings


@contextmanager
def get_db_connection():
    """Open a MySQL connection and always close it."""
    settings = get_settings()

    connection = mysql.connector.connect(
        host=settings.db_host,
        port=settings.db_port,
        database=settings.db_name,
        user=settings.db_user,
        password=settings.db_password,
    )

    try:
        yield connection
    finally:
        connection.close()