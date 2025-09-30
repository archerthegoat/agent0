"""检查数据不匹配问题"""
from datainsight_agent.services.core.sql_executor import SQLExecutor
from datainsight_agent.config.settings import load_settings

settings = load_settings()
executor = SQLExecutor(settings)

# 检查 test_017 的数据
print('=== Test 017: 2025年第二季度的MAU和UV对比 ===')
result = executor.execute('SELECT COUNT(user_id) AS mau, COUNT(DISTINCT user_id) AS uv FROM dws_user_activity WHERE month BETWEEN "2025-04" AND "2025-06"')
print('Actual result:', result)
print('Expected: [{"mau": 9, "uv": 3}]')

# 检查 test_019 的数据
print('\n=== Test 019: 2025年第四季度的用户活跃度 ===')
result = executor.execute('SELECT COUNT(user_id) AS mau FROM dws_user_activity WHERE month BETWEEN "2025-10" AND "2025-12"')
print('Actual result:', result)
print('Expected: [{"mau": 7}]')

# 检查 test_020 的数据
print('\n=== Test 020: 2025年每月的DAU趋势分析 ===')
result = executor.execute('SELECT month, COUNT(DISTINCT user_id) AS dau FROM dws_user_activity WHERE month BETWEEN "2025-01" AND "2025-12" GROUP BY month ORDER BY month')
print('Actual result:', result)
print('Expected: [{"month": "2025-01", "dau": 3}, {"month": "2025-02", "dau": 3}, ...]')

# 检查具体月份的数据
print('\n=== 检查具体月份数据 ===')
months = ['2025-01', '2025-02', '2025-03', '2025-04', '2025-05', '2025-06', '2025-10', '2025-11', '2025-12']
for month in months:
    result = executor.execute(f'SELECT COUNT(DISTINCT user_id) AS dau FROM dws_user_activity WHERE month = "{month}"')
    print(f'{month}: {result[0]["dau"]} DAU')

# 检查第二季度的详细数据
print('\n=== 第二季度详细数据 ===')
result = executor.execute('SELECT month, user_id, active FROM dws_user_activity WHERE month BETWEEN "2025-04" AND "2025-06" ORDER BY month, user_id')
for row in result:
    print(f'{row["month"]}: {row["user_id"]} (active={row["active"]})')

# 检查第四季度的详细数据
print('\n=== 第四季度详细数据 ===')
result = executor.execute('SELECT month, user_id, active FROM dws_user_activity WHERE month BETWEEN "2025-10" AND "2025-12" ORDER BY month, user_id')
for row in result:
    print(f'{row["month"]}: {row["user_id"]} (active={row["active"]})')
