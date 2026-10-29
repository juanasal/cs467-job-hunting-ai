
from app.database import get_db_connection

with get_db_connection() as connection:
    cursor = connection.cursor()
    cursor.execute("SELECT DATABASE(), VERSION()")
    result = cursor.fetchone()
    cursor.close()

    print("Database connection successful!")
    print("Database:", result[0])
    print("MySQL version:", result[1])
