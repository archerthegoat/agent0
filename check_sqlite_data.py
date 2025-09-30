#!/usr/bin/env python3
"""
检查SQLite数据库中的实际数据
"""

import sqlite3
from pathlib import Path

def check_sqlite_data():
    # 检查数据库文件是否存在
    db_path = Path('datainsight.db')
    if not db_path.exists():
        print('Database file does not exist, need to initialize first')
        return

    # 连接数据库
    conn = sqlite3.connect('datainsight.db')
    cursor = conn.cursor()

    print('=== SQLite Database Structure ===')
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    print(f'Tables: {[t[0] for t in tables]}')

    print('\n=== dws_user_activity Table Structure ===')
    cursor.execute('PRAGMA table_info(dws_user_activity)')
    columns = cursor.fetchall()
    for col in columns:
        print(f'{col[1]} ({col[2]})')

    print('\n=== 2025-08 Data ===')
    cursor.execute("SELECT user_id, month, active, channel_code, device_type, region, revenue_amount FROM dws_user_activity WHERE month = '2025-08'")
    rows = cursor.fetchall()
    for row in rows:
        print(row)

    print('\n=== 2025-09 Data ===')
    cursor.execute("SELECT user_id, month, active, channel_code, device_type, region, revenue_amount FROM dws_user_activity WHERE month = '2025-09'")
    rows = cursor.fetchall()
    for row in rows:
        print(row)

    print('\n=== 2025 Q2 Data (Apr-Jun) ===')
    cursor.execute("SELECT user_id, month, active FROM dws_user_activity WHERE month BETWEEN '2025-04' AND '2025-06' ORDER BY month")
    rows = cursor.fetchall()
    for row in rows:
        print(row)

    print('\n=== 2025 Q4 Data (Oct-Dec) ===')
    cursor.execute("SELECT user_id, month, active FROM dws_user_activity WHERE month BETWEEN '2025-10' AND '2025-12' ORDER BY month")
    rows = cursor.fetchall()
    for row in rows:
        print(row)

    print('\n=== 2025-08 MAU Count ===')
    cursor.execute("SELECT COUNT(user_id) AS mau FROM dws_user_activity WHERE month = '2025-08'")
    result = cursor.fetchone()
    print(f'MAU: {result[0]}')

    print('\n=== 2025-08 to 2025-09 DAU Count ===')
    cursor.execute("SELECT COUNT(DISTINCT user_id) AS dau FROM dws_user_activity WHERE month BETWEEN '2025-08' AND '2025-09'")
    result = cursor.fetchone()
    print(f'DAU: {result[0]}')

    print('\n=== 2025-08 Revenue Sum ===')
    cursor.execute("SELECT SUM(revenue_amount) AS revenue FROM dws_user_activity WHERE month = '2025-08'")
    result = cursor.fetchone()
    print(f'Revenue: {result[0]}')

    print('\n=== 2025-08 Channel Code Distribution ===')
    cursor.execute("SELECT channel_code, COUNT(user_id) AS count FROM dws_user_activity WHERE month = '2025-08' GROUP BY channel_code")
    rows = cursor.fetchall()
    for row in rows:
        print(f'{row[0]}: {row[1]}')

    print('\n=== 2025-08 Device Type Distribution ===')
    cursor.execute("SELECT device_type, COUNT(DISTINCT user_id) AS count FROM dws_user_activity WHERE month = '2025-08' GROUP BY device_type")
    rows = cursor.fetchall()
    for row in rows:
        print(f'{row[0]}: {row[1]}')

    print('\n=== 2025-08 Region Distribution ===')
    cursor.execute("SELECT region, COUNT(DISTINCT user_id) AS count FROM dws_user_activity WHERE month = '2025-08' GROUP BY region")
    rows = cursor.fetchall()
    for row in rows:
        print(f'{row[0]}: {row[1]}')

    print('\n=== 2025 Q2 New Users Count ===')
    cursor.execute("SELECT COUNT(DISTINCT user_id) AS new_users FROM dws_user_activity WHERE month BETWEEN '2025-04' AND '2025-06'")
    result = cursor.fetchone()
    print(f'New Users: {result[0]}')

    print('\n=== 2025-08 Platform Distribution ===')
    cursor.execute("SELECT platform, COUNT(DISTINCT user_id) AS count FROM dws_user_activity WHERE month = '2025-08' GROUP BY platform")
    rows = cursor.fetchall()
    for row in rows:
        print(f'{row[0]}: {row[1]}')

    conn.close()

if __name__ == "__main__":
    check_sqlite_data()
