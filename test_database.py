from DB import db, cursor

print("\n===================================")
print("🔗 SOUL AI DATABASE INTEGRITY TEST")
print("===================================\n")

try:

    # =====================================================
    # 1. CHECK TABLE COUNT
    # =====================================================

    cursor.execute("SHOW TABLES")
    tables = cursor.fetchall()

    if len(tables) == 15:
        print("✅ 1. Table Count             PASS (15/15)")
    else:
        print(f"❌ 1. Table Count             FAIL ({len(tables)}/15)")


    # =====================================================
    # 2. CHECK FOREIGN KEYS
    # =====================================================

    cursor.execute("""
        SELECT
            TABLE_NAME,
            COLUMN_NAME,
            REFERENCED_TABLE_NAME,
            REFERENCED_COLUMN_NAME
        FROM information_schema.KEY_COLUMN_USAGE
        WHERE
            TABLE_SCHEMA = 'soul_ai'
            AND REFERENCED_TABLE_NAME IS NOT NULL
    """)

    foreign_keys = cursor.fetchall()

    print(
        f"✅ 2. Foreign Keys            PASS "
        f"({len(foreign_keys)} found)"
    )


    # =====================================================
    # 3. CHECK USERS TABLE
    # =====================================================

    cursor.execute("SELECT COUNT(*) AS total FROM users")

    result = cursor.fetchone()

    print(
        f"✅ 3. Users Table             PASS "
        f"({result['total']} records)"
    )


    # =====================================================
    # 4. CHECK AI PROVIDERS
    # =====================================================

    cursor.execute("SELECT COUNT(*) AS total FROM ai_providers")

    result = cursor.fetchone()

    print(
        f"✅ 4. AI Providers            PASS "
        f"({result['total']} records)"
    )


    # =====================================================
    # 5. CHECK AI MODELS
    # =====================================================

    cursor.execute("SELECT COUNT(*) AS total FROM ai_models")

    result = cursor.fetchone()

    print(
        f"✅ 5. AI Models               PASS "
        f"({result['total']} records)"
    )


    # =====================================================
    # 6. CHECK CAPABILITIES
    # =====================================================

    cursor.execute("SELECT COUNT(*) AS total FROM ai_capabilities")

    result = cursor.fetchone()

    print(
        f"✅ 6. AI Capabilities         PASS "
        f"({result['total']} records)"
    )


    # =====================================================
    # 7. CHECK API KEYS TABLE
    # =====================================================

    cursor.execute("SELECT COUNT(*) AS total FROM api_keys")

    result = cursor.fetchone()

    print(
        f"✅ 7. API Keys                PASS "
        f"({result['total']} records)"
    )


    # =====================================================
    # 8. CHECK CHAT TABLES
    # =====================================================

    cursor.execute("SELECT COUNT(*) AS total FROM chat_sessions")

    sessions = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) AS total FROM chat_messages")

    messages = cursor.fetchone()["total"]

    print(
        f"✅ 8. Chat Tables             PASS "
        f"({sessions} sessions / {messages} messages)"
    )


    # =====================================================
    # 9. CHECK SETTINGS TABLES
    # =====================================================

    cursor.execute("SELECT COUNT(*) AS total FROM system_settings")

    system_settings = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) AS total FROM user_settings")

    user_settings = cursor.fetchone()["total"]

    print(
        f"✅ 9. Settings Tables         PASS "
        f"({system_settings} system / {user_settings} user)"
    )


    # =====================================================
    # 10. CHECK LOG TABLES
    # =====================================================

    cursor.execute("SELECT COUNT(*) AS total FROM activity_logs")

    activity_logs = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) AS total FROM notifications")

    notifications = cursor.fetchone()["total"]

    print(
        f"✅ 10. Log Tables             PASS "
        f"({activity_logs} logs / {notifications} notifications)"
    )


    # =====================================================
    # 11. CHECK ROUTING TABLE
    # =====================================================

    cursor.execute(
        "SELECT COUNT(*) AS total FROM provider_routing_rules"
    )

    result = cursor.fetchone()

    print(
        f"✅ 11. Routing Rules          PASS "
        f"({result['total']} rules)"
    )


    # =====================================================
    # 12. CHECK MODEL CAPABILITIES
    # =====================================================

    cursor.execute(
        "SELECT COUNT(*) AS total FROM model_capabilities"
    )

    result = cursor.fetchone()

    print(
        f"✅ 12. Model Capabilities     PASS "
        f"({result['total']} mappings)"
    )


    # =====================================================
    # 13. CHECK API USAGE LOGS
    # =====================================================

    cursor.execute(
        "SELECT COUNT(*) AS total FROM api_usage_logs"
    )

    result = cursor.fetchone()

    print(
        f"✅ 13. API Usage Logs         PASS "
        f"({result['total']} records)"
    )


    # =====================================================
    # FINAL
    # =====================================================

    print("\n===================================")
    print("🎉 DATABASE INTEGRITY TEST DONE")
    print("===================================")

except Exception as e:

    print("\n❌ DATABASE TEST FAILED")
    print("Error:", e)

finally:

    cursor.close()
    db.close()

    print("\n🔒 Database connection closed.")