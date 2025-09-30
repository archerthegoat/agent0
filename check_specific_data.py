#!/usr/bin/env python3
"""
检查特定测试用例相关的数据
"""

import sqlite3

def check_specific_data():
    # 连接数据库
    conn = sqlite3.connect('datainsight.db')
    cursor = conn.cursor()

    print('=== 2025-09 ARPU by Channel ===')
    cursor.execute('SELECT channel_code, AVG(user_revenue) AS arpu FROM dws_user_activity WHERE month = "2025-09" GROUP BY channel_code ORDER BY channel_code')
    rows = cursor.fetchall()
    for row in rows:
        print(f'{row[0]}: {row[1]}')

    print('\n=== 2025-08 to 2025-10 MAU by Month ===')
    cursor.execute('SELECT month, COUNT(user_id) AS mau FROM dws_user_activity WHERE month BETWEEN "2025-08" AND "2025-10" GROUP BY month ORDER BY month')
    rows = cursor.fetchall()
    for row in rows:
        print(f'{row[0]}: {row[1]}')

    print('\n=== 2025 Q4 MAU ===')
    cursor.execute('SELECT COUNT(user_id) AS mau FROM dws_user_activity WHERE month BETWEEN "2025-10" AND "2025-12"')
    result = cursor.fetchone()
    print(f'Q4 MAU: {result[0]}')

    print('\n=== 2025-08 Platform Churn Users ===')
    cursor.execute('SELECT platform, COUNT(DISTINCT user_id) AS churn_users FROM dws_user_activity WHERE month = "2025-08" GROUP BY platform ORDER BY platform')
    rows = cursor.fetchall()
    for row in rows:
        print(f'{row[0]}: {row[1]}')

    print('\n=== 2025-08 ROI ===')
    cursor.execute('SELECT AVG(roi_ratio) AS roi FROM dws_user_activity WHERE month = "2025-08"')
    result = cursor.fetchone()
    print(f'ROI: {result[0]}')

    print('\n=== 2025-09 Pages per Session by Device ===')
    cursor.execute('SELECT device_type, AVG(pages_per_session) AS avg_pages FROM dws_user_activity WHERE month = "2025-09" GROUP BY device_type ORDER BY device_type')
    rows = cursor.fetchall()
    for row in rows:
        print(f'{row[0]}: {row[1]}')

    print('\n=== 2025 Q3 Return Visitor Rate ===')
    cursor.execute('SELECT AVG(is_return_visitor) AS return_rate FROM dws_user_activity WHERE month BETWEEN "2025-07" AND "2025-09"')
    result = cursor.fetchone()
    print(f'Return Visitor Rate: {result[0]}')

    print('\n=== 2025-08 Email Open Rate by Region ===')
    cursor.execute('SELECT region, AVG(search_success) AS email_open_rate FROM dws_user_activity WHERE month = "2025-08" GROUP BY region ORDER BY region')
    rows = cursor.fetchall()
    for row in rows:
        print(f'{row[0]}: {row[1]}')

    print('\n=== 2025-08 Cart Abandonment Rate ===')
    cursor.execute('SELECT AVG(bounce_flag) AS cart_abandonment_rate FROM dws_user_activity WHERE month = "2025-08"')
    result = cursor.fetchone()
    print(f'Cart Abandonment Rate: {result[0]}')

    print('\n=== 2025-09 App Crash Rate ===')
    cursor.execute('SELECT AVG(bounce_flag) AS app_crash_rate FROM dws_user_activity WHERE month = "2025-09"')
    result = cursor.fetchone()
    print(f'App Crash Rate: {result[0]}')

    print('\n=== 2025-08 CAC by Channel ===')
    cursor.execute('SELECT channel_code, AVG(roi_ratio) AS cac FROM dws_user_activity WHERE month = "2025-08" GROUP BY channel_code ORDER BY channel_code')
    rows = cursor.fetchall()
    for row in rows:
        print(f'{row[0]}: {row[1]}')

    print('\n=== 2025-08 Retention Rate by Region ===')
    cursor.execute('SELECT region, AVG(retention_flag) AS retention_rate FROM dws_user_activity WHERE month = "2025-08" GROUP BY region ORDER BY retention_rate DESC')
    rows = cursor.fetchall()
    for row in rows:
        print(f'{row[0]}: {row[1]}')

    print('\n=== 2025 Q3 Conversion Rate by Month ===')
    cursor.execute('SELECT month, AVG(conversion_flag) AS conversion_rate FROM dws_user_activity WHERE month BETWEEN "2025-07" AND "2025-09" GROUP BY month ORDER BY month')
    rows = cursor.fetchall()
    for row in rows:
        print(f'{row[0]}: {row[1]}')

    print('\n=== 2025-08 Average Revenue ===')
    cursor.execute('SELECT AVG(user_revenue) AS avg_revenue FROM dws_user_activity WHERE month = "2025-08"')
    result = cursor.fetchone()
    print(f'Average Revenue: {result[0]}')

    print('\n=== 2025-09 Bounce Rate by Channel ===')
    cursor.execute('SELECT channel_code, AVG(bounce_flag) AS bounce_rate FROM dws_user_activity WHERE month = "2025-09" GROUP BY channel_code ORDER BY channel_code')
    rows = cursor.fetchall()
    for row in rows:
        print(f'{row[0]}: {row[1]}')

    conn.close()

if __name__ == "__main__":
    check_specific_data()
