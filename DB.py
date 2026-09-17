import mysql.connector

try:

    db = mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="soul_ai"
    )

    # Buffered cursor
    cursor = db.cursor(
        dictionary=True,
        buffered=True
    )

    print("✅ MySQL Database Connected Successfully!")

except mysql.connector.Error as err:

    print(f"❌ MySQL Connection Error: {err}")
    raise