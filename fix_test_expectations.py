#!/usr/bin/env python3
"""
修正测试用例期望值格式：从字典格式改为元组格式以匹配SQLite返回结果
"""

import json
import sqlite3
from pathlib import Path

def fix_test_expectations():
    """修正测试用例期望值格式"""
    
    # 读取测试用例
    with open('test_cases_rag.json', 'r', encoding='utf-8') as f:
        test_cases = json.load(f)
    
    # 连接SQLite数据库
    db_path = Path('datainsight.db')
    if not db_path.exists():
        print("[ERROR] SQLite database not found")
        return
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    print("=== 修正测试用例期望值格式 ===\n")
    
    # 修正每个测试用例的期望结果
    for i, test_case in enumerate(test_cases, 1):
        test_id = f"test_{i:03d}"
        expected_sql = test_case['expected_sql']
        expected_result = test_case['expected_result']
        
        try:
            # 执行期望的SQL获取实际结果
            cursor.execute(expected_sql)
            actual_result = cursor.fetchall()
            
            # 更新期望结果为实际结果格式
            test_case['expected_result'] = actual_result
            
            print(f"[SUCCESS] {test_id}: 期望结果已更新为 {actual_result}")
            
        except Exception as e:
            print(f"[ERROR] {test_id}: SQL执行失败: {e}")
    
    # 保存修正后的测试用例
    with open('test_cases_rag.json', 'w', encoding='utf-8') as f:
        json.dump(test_cases, f, ensure_ascii=False, indent=2)
    
    print(f"\n[SUCCESS] 已修正 {len(test_cases)} 个测试用例的期望值格式")
    
    conn.close()

if __name__ == "__main__":
    fix_test_expectations()
