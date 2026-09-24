import os
import mysql.connector

# Database configuration
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME", "soul_ai")
}

# Aiven / production SSL
if os.getenv("DB_SSL_MODE", "").upper() == "REQUIRED":
    DB_CONFIG["ssl_disabled"] = False

    if os.getenv("DB_SSL_CA"):
        DB_CONFIG["ssl_ca"] = os.getenv("DB_SSL_CA")

try:

    db = mysql.connector.connect(**DB_CONFIG)

    # Buffered cursor
    cursor = db.cursor(
        dictionary=True,
        buffered=True
    )

    print("✅ MySQL Database Connected Successfully!")

except mysql.connector.Error as err:

    print(f"❌ MySQL Connection Error: {err}")
    raise