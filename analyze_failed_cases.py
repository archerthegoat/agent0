"""分析失败的测试用例，找出 Result Correctness Rate 低的原因"""
import json
from datainsight_agent.services.core.sql_executor import SQLExecutor
from datainsight_agent.config.settings import load_settings

# 加载测试用例
with open('test_cases_rag.json', 'r', encoding='utf-8') as f:
    test_cases = json.load(f)

# 初始化 SQL 执行器
settings = load_settings()
executor = SQLExecutor(settings)

failed_cases = []
success_cases = []

print("=== 分析测试用例结果正确性 ===\n")

for i, test_case in enumerate(test_cases, 1):
    test_id = test_case['id']
    question = test_case['question']
    expected_sql = test_case['expected_sql']
    expected_result = test_case['expected_result']
    
    print(f"--- Test {i}/40: {test_id} ---")
    print(f"Question: {question}")
    print(f"Expected SQL: {expected_sql}")
    print(f"Expected Result: {expected_result}")
    
    try:
        # 执行 SQL
        actual_result = executor.execute(expected_sql)
        print(f"Actual Result: {actual_result}")
        
        # 使用测试框架的比较逻辑
        from test_batch_evaluation import BatchTestEvaluator
        evaluator = BatchTestEvaluator()
        if evaluator._compare_results(actual_result, expected_result):
            print("[PASS]")
            success_cases.append(test_id)
        else:
            print("[FAIL]")
            failed_cases.append({
                'id': test_id,
                'question': question,
                'expected_sql': expected_sql,
                'expected_result': expected_result,
                'actual_result': actual_result,
                'reason': 'result_mismatch'
            })
            
            # 分析失败原因
            if len(actual_result) != len(expected_result):
                print(f"  Reason: Row count mismatch - Expected: {len(expected_result)}, Actual: {len(actual_result)}")
            elif actual_result and expected_result:
                actual_row = actual_result[0]
                expected_row = expected_result[0]
                print(f"  Reason: Row content mismatch")
                print(f"    Expected: {expected_row}")
                print(f"    Actual: {actual_row}")
                
                # 详细比较字段
                if isinstance(actual_row, dict) and isinstance(expected_row, dict):
                    actual_keys = set(actual_row.keys())
                    expected_keys = set(expected_row.keys())
                    if actual_keys != expected_keys:
                        print(f"    Key mismatch - Expected: {expected_keys}, Actual: {actual_keys}")
                    else:
                        for key in expected_keys:
                            if actual_row[key] != expected_row[key]:
                                print(f"    Value mismatch for '{key}': Expected {expected_row[key]}, Actual {actual_row[key]}")
        
    except Exception as e:
        print(f"[ERROR]: {str(e)}")
        failed_cases.append({
            'id': test_id,
            'question': question,
            'expected_sql': expected_sql,
            'expected_result': expected_result,
            'actual_result': None,
            'reason': 'execution_error',
            'error': str(e)
        })
    
    print()

print("=== 失败案例分析 ===")
print(f"成功案例: {len(success_cases)}/{len(test_cases)} ({len(success_cases)/len(test_cases)*100:.1f}%)")
print(f"失败案例: {len(failed_cases)}/{len(test_cases)} ({len(failed_cases)/len(test_cases)*100:.1f}%)")

print("\n=== 失败原因统计 ===")
reason_counts = {}
for case in failed_cases:
    reason = case['reason']
    reason_counts[reason] = reason_counts.get(reason, 0) + 1

for reason, count in reason_counts.items():
    print(f"{reason}: {count} cases")

print("\n=== 详细失败案例 ===")
for case in failed_cases[:10]:  # 只显示前10个
    print(f"\n{case['id']}: {case['question']}")
    print(f"  Reason: {case['reason']}")
    if case['reason'] == 'execution_error':
        print(f"  Error: {case['error']}")
    else:
        print(f"  Expected: {case['expected_result']}")
        print(f"  Actual: {case['actual_result']}")

if len(failed_cases) > 10:
    print(f"\n... and {len(failed_cases) - 10} more failed cases")