#!/usr/bin/env python3
"""
Test Case Generator for Clarification Testing
Uses Qwen API to generate test cases that trigger clarification mechanisms
"""

import json
import random
from pathlib import Path
from typing import List, Dict, Any
from dataclasses import dataclass

from datainsight_agent.services.llm import QwenClient
from datainsight_agent.config.settings import load_settings


@dataclass
class TestCaseTemplate:
    """Template for generating test cases"""
    category: str
    description: str
    missing_elements: List[str]
    example_questions: List[str]


class ClarificationTestGenerator:
    """Generates test cases that require clarification"""
    
    def __init__(self):
        self.settings = load_settings()
        self.qwen_client = QwenClient(self.settings)
        self.metrics = self._load_metrics()
        self.dimensions = self._load_dimensions()
        
    def _load_metrics(self) -> List[Dict[str, Any]]:
        """Load available metrics from metadata"""
        metrics_file = Path("metadata/metrics.json")
        if metrics_file.exists():
            with open(metrics_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return []
    
    def _load_dimensions(self) -> List[Dict[str, Any]]:
        """Load available dimensions from metadata"""
        dimensions_file = Path("metadata/dimensions.json")
        if dimensions_file.exists():
            with open(dimensions_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return []
    
    def _get_metric_names(self) -> List[str]:
        """Get list of metric canonical names and aliases"""
        names = []
        for metric in self.metrics:
            names.append(metric.get('canonical_name', ''))
            names.extend(metric.get('aliases', []))
        return [name for name in names if name]
    
    def _get_dimension_names(self) -> List[str]:
        """Get list of dimension names"""
        names = []
        for dim in self.dimensions:
            names.append(dim.get('name', ''))
            names.extend(dim.get('aliases', []))
        return [name for name in names if name]
    
    def _create_generation_prompt(self, template: TestCaseTemplate) -> str:
        """Create prompt for Qwen to generate test cases"""
        metric_names = self._get_metric_names()
        dimension_names = self._get_dimension_names()
        
        prompt = f"""
你是一个数据分析测试用例生成专家。请为以下类别生成一个测试用例：

类别: {template.category}
描述: {template.description}
缺失元素: {', '.join(template.missing_elements)}
示例问题: {', '.join(template.example_questions)}

可用的指标名称: {', '.join(metric_names[:20])}
可用的维度名称: {', '.join(dimension_names[:15])}

请生成一个测试用例，要求：
1. 问题要自然、真实，但故意缺少指定的元素
2. 问题应该是中文
3. 问题要符合实际业务场景

请按以下JSON格式返回：
{{
    "question": "用户问题（故意缺少指定元素）",
    "expected_metric": "澄清后期望的指标名称",
    "expected_time_filter": "澄清后期望的时间过滤（如2025-08或2025-08,2025-09）",
    "expected_group_by": ["澄清后期望的分组维度"],
    "expected_sql": "澄清后期望的SQL查询",
    "expected_result": [{{"字段名": 示例值}}],
    "category": "{template.category}",
    "description": "测试用例描述",
    "expected_rag_entities": ["期望检索到的实体"],
    "expected_rag_concepts": ["期望检索到的概念"]
}}

注意：
- expected_sql应该基于dws_user_activity表
- expected_result应该是合理的示例数据
- 确保SQL语法正确
- 时间格式使用YYYY-MM
"""
        return prompt
    
    def _generate_single_test_case(self, template: TestCaseTemplate, test_id: str) -> Dict[str, Any]:
        """Generate a single test case using Qwen"""
        prompt = self._create_generation_prompt(template)
        
        try:
            response = self.qwen_client.generate_sql(prompt)
            print(f"Raw response for {test_id}: {response[:200]}...")
            
            # Try to extract JSON from response
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                test_case = json.loads(json_str)
            else:
                raise ValueError("No JSON found in response")
            
            # Add test ID and ensure required fields
            test_case['id'] = test_id
            
            # Set defaults for missing fields
            test_case.setdefault('expected_group_by', [])
            test_case.setdefault('expected_rag_entities', [])
            test_case.setdefault('expected_rag_concepts', [])
            test_case.setdefault('expected_result', [])
            
            return test_case
            
        except Exception as e:
            print(f"Error generating test case {test_id}: {e}")
            # Return a fallback test case
            return self._create_fallback_test_case(template, test_id)
    
    def _create_fallback_test_case(self, template: TestCaseTemplate, test_id: str) -> Dict[str, Any]:
        """Create a fallback test case if LLM generation fails"""
        
        # More diverse fallback cases
        missing_time_cases = [
            {
                "question": "查询用户活跃度",
                "expected_metric": "mau",
                "expected_time_filter": "2025-08",
                "expected_group_by": [],
                "expected_sql": "SELECT COUNT(user_id) AS mau FROM dws_user_activity WHERE month = '2025-08'",
                "expected_result": [{"mau": 2}],
                "expected_rag_entities": ["mau", "month"],
                "expected_rag_concepts": ["用户活跃度"]
            },
            {
                "question": "统计DAU",
                "expected_metric": "dau",
                "expected_time_filter": "2025-09",
                "expected_group_by": [],
                "expected_sql": "SELECT COUNT(DISTINCT user_id) AS dau FROM dws_user_activity WHERE month = '2025-09'",
                "expected_result": [{"dau": 4}],
                "expected_rag_entities": ["dau", "month"],
                "expected_rag_concepts": ["日活跃用户"]
            },
            {
                "question": "分析UV数据",
                "expected_metric": "uv",
                "expected_time_filter": "2025-07",
                "expected_group_by": [],
                "expected_sql": "SELECT COUNT(DISTINCT user_id) AS uv FROM dws_user_activity WHERE month = '2025-07'",
                "expected_result": [{"uv": 2}],
                "expected_rag_entities": ["uv", "month"],
                "expected_rag_concepts": ["独立访客"]
            },
            {
                "question": "查看PV统计",
                "expected_metric": "pv",
                "expected_time_filter": "2025-08",
                "expected_group_by": [],
                "expected_sql": "SELECT COUNT(page_view_id) AS pv FROM dws_user_activity WHERE month = '2025-08'",
                "expected_result": [{"pv": 2}],
                "expected_rag_entities": ["pv", "month"],
                "expected_rag_concepts": ["页面访问"]
            },
            {
                "question": "用户留存率分析",
                "expected_metric": "retention_rate",
                "expected_time_filter": "2025-08",
                "expected_group_by": [],
                "expected_sql": "SELECT AVG(retention_flag) AS retention_rate FROM dws_user_activity WHERE month = '2025-08'",
                "expected_result": [{"retention_rate": 1.0}],
                "expected_rag_entities": ["retention_rate", "month"],
                "expected_rag_concepts": ["用户留存率"]
            }
        ]
        
        missing_metric_cases = [
            {
                "question": "2025年8月的数据分析",
                "expected_metric": "mau",
                "expected_time_filter": "2025-08",
                "expected_group_by": [],
                "expected_sql": "SELECT COUNT(user_id) AS mau FROM dws_user_activity WHERE month = '2025-08'",
                "expected_result": [{"mau": 2}],
                "expected_rag_entities": ["mau", "month"],
                "expected_rag_concepts": ["数据分析"]
            },
            {
                "question": "2025年9月的用户指标",
                "expected_metric": "dau",
                "expected_time_filter": "2025-09",
                "expected_group_by": [],
                "expected_sql": "SELECT COUNT(DISTINCT user_id) AS dau FROM dws_user_activity WHERE month = '2025-09'",
                "expected_result": [{"dau": 4}],
                "expected_rag_entities": ["dau", "month"],
                "expected_rag_concepts": ["用户指标"]
            },
            {
                "question": "2025年7月的业务数据",
                "expected_metric": "uv",
                "expected_time_filter": "2025-07",
                "expected_group_by": [],
                "expected_sql": "SELECT COUNT(DISTINCT user_id) AS uv FROM dws_user_activity WHERE month = '2025-07'",
                "expected_result": [{"uv": 2}],
                "expected_rag_entities": ["uv", "month"],
                "expected_rag_concepts": ["业务数据"]
            },
            {
                "question": "2025年8月的用户表现",
                "expected_metric": "retention_rate",
                "expected_time_filter": "2025-08",
                "expected_group_by": [],
                "expected_sql": "SELECT AVG(retention_flag) AS retention_rate FROM dws_user_activity WHERE month = '2025-08'",
                "expected_result": [{"retention_rate": 1.0}],
                "expected_rag_entities": ["retention_rate", "month"],
                "expected_rag_concepts": ["用户表现"]
            },
            {
                "question": "2025年9月的数据概览",
                "expected_metric": "pv",
                "expected_time_filter": "2025-09",
                "expected_group_by": [],
                "expected_sql": "SELECT COUNT(page_view_id) AS pv FROM dws_user_activity WHERE month = '2025-09'",
                "expected_result": [{"pv": 4}],
                "expected_rag_entities": ["pv", "month"],
                "expected_rag_concepts": ["数据概览"]
            }
        ]
        
        missing_both_cases = [
            {
                "question": "查询数据",
                "expected_metric": "mau",
                "expected_time_filter": "2025-08",
                "expected_group_by": [],
                "expected_sql": "SELECT COUNT(user_id) AS mau FROM dws_user_activity WHERE month = '2025-08'",
                "expected_result": [{"mau": 2}],
                "expected_rag_entities": ["mau", "month"],
                "expected_rag_concepts": ["数据查询"]
            },
            {
                "question": "分析趋势",
                "expected_metric": "dau",
                "expected_time_filter": "2025-09",
                "expected_group_by": [],
                "expected_sql": "SELECT COUNT(DISTINCT user_id) AS dau FROM dws_user_activity WHERE month = '2025-09'",
                "expected_result": [{"dau": 4}],
                "expected_rag_entities": ["dau", "month"],
                "expected_rag_concepts": ["趋势分析"]
            },
            {
                "question": "数据统计",
                "expected_metric": "uv",
                "expected_time_filter": "2025-07",
                "expected_group_by": [],
                "expected_sql": "SELECT COUNT(DISTINCT user_id) AS uv FROM dws_user_activity WHERE month = '2025-07'",
                "expected_result": [{"uv": 2}],
                "expected_rag_entities": ["uv", "month"],
                "expected_rag_concepts": ["数据统计"]
            },
            {
                "question": "业务分析",
                "expected_metric": "retention_rate",
                "expected_time_filter": "2025-08",
                "expected_group_by": [],
                "expected_sql": "SELECT AVG(retention_flag) AS retention_rate FROM dws_user_activity WHERE month = '2025-08'",
                "expected_result": [{"retention_rate": 1.0}],
                "expected_rag_entities": ["retention_rate", "month"],
                "expected_rag_concepts": ["业务分析"]
            },
            {
                "question": "用户分析",
                "expected_metric": "pv",
                "expected_time_filter": "2025-09",
                "expected_group_by": [],
                "expected_sql": "SELECT COUNT(page_view_id) AS pv FROM dws_user_activity WHERE month = '2025-09'",
                "expected_result": [{"pv": 4}],
                "expected_rag_entities": ["pv", "month"],
                "expected_rag_concepts": ["用户分析"]
            }
        ]
        
        # Select appropriate case based on template
        if "time" in template.missing_elements and "metric" not in template.missing_elements:
            cases = missing_time_cases
            category = "missing_time"
        elif "metric" in template.missing_elements and "time" not in template.missing_elements:
            cases = missing_metric_cases
            category = "missing_metric"
        else:
            cases = missing_both_cases
            category = "missing_both"
        
        # Use test_id to select a consistent case
        case_index = int(test_id.split('_')[1]) % len(cases)
        case = cases[case_index].copy()
        case['id'] = test_id
        case['category'] = category
        case['description'] = f"{category}测试用例"
        
        return case
    
    def generate_test_cases(self) -> List[Dict[str, Any]]:
        """Generate all 30 test cases"""
        templates = [
            # 15 cases with missing time dimension
            TestCaseTemplate(
                category="missing_time",
                description="缺少时间维度的查询",
                missing_elements=["time"],
                example_questions=["查询MAU", "统计用户活跃度", "分析DAU", "查看UV数据", "用户留存率"]
            ),
            TestCaseTemplate(
                category="missing_time",
                description="缺少时间维度的查询",
                missing_elements=["time"],
                example_questions=["查询MAU", "统计用户活跃度", "分析DAU", "查看UV数据", "用户留存率"]
            ),
            TestCaseTemplate(
                category="missing_time",
                description="缺少时间维度的查询",
                missing_elements=["time"],
                example_questions=["查询MAU", "统计用户活跃度", "分析DAU", "查看UV数据", "用户留存率"]
            ),
            TestCaseTemplate(
                category="missing_time",
                description="缺少时间维度的查询",
                missing_elements=["time"],
                example_questions=["查询MAU", "统计用户活跃度", "分析DAU", "查看UV数据", "用户留存率"]
            ),
            TestCaseTemplate(
                category="missing_time",
                description="缺少时间维度的查询",
                missing_elements=["time"],
                example_questions=["查询MAU", "统计用户活跃度", "分析DAU", "查看UV数据", "用户留存率"]
            ),
            TestCaseTemplate(
                category="missing_time",
                description="缺少时间维度的查询",
                missing_elements=["time"],
                example_questions=["查询MAU", "统计用户活跃度", "分析DAU", "查看UV数据", "用户留存率"]
            ),
            TestCaseTemplate(
                category="missing_time",
                description="缺少时间维度的查询",
                missing_elements=["time"],
                example_questions=["查询MAU", "统计用户活跃度", "分析DAU", "查看UV数据", "用户留存率"]
            ),
            TestCaseTemplate(
                category="missing_time",
                description="缺少时间维度的查询",
                missing_elements=["time"],
                example_questions=["查询MAU", "统计用户活跃度", "分析DAU", "查看UV数据", "用户留存率"]
            ),
            TestCaseTemplate(
                category="missing_time",
                description="缺少时间维度的查询",
                missing_elements=["time"],
                example_questions=["查询MAU", "统计用户活跃度", "分析DAU", "查看UV数据", "用户留存率"]
            ),
            TestCaseTemplate(
                category="missing_time",
                description="缺少时间维度的查询",
                missing_elements=["time"],
                example_questions=["查询MAU", "统计用户活跃度", "分析DAU", "查看UV数据", "用户留存率"]
            ),
            TestCaseTemplate(
                category="missing_time",
                description="缺少时间维度的查询",
                missing_elements=["time"],
                example_questions=["查询MAU", "统计用户活跃度", "分析DAU", "查看UV数据", "用户留存率"]
            ),
            TestCaseTemplate(
                category="missing_time",
                description="缺少时间维度的查询",
                missing_elements=["time"],
                example_questions=["查询MAU", "统计用户活跃度", "分析DAU", "查看UV数据", "用户留存率"]
            ),
            TestCaseTemplate(
                category="missing_time",
                description="缺少时间维度的查询",
                missing_elements=["time"],
                example_questions=["查询MAU", "统计用户活跃度", "分析DAU", "查看UV数据", "用户留存率"]
            ),
            TestCaseTemplate(
                category="missing_time",
                description="缺少时间维度的查询",
                missing_elements=["time"],
                example_questions=["查询MAU", "统计用户活跃度", "分析DAU", "查看UV数据", "用户留存率"]
            ),
            TestCaseTemplate(
                category="missing_time",
                description="缺少时间维度的查询",
                missing_elements=["time"],
                example_questions=["查询MAU", "统计用户活跃度", "分析DAU", "查看UV数据", "用户留存率"]
            ),
            
            # 10 cases with ambiguous/invalid metrics
            TestCaseTemplate(
                category="missing_metric",
                description="缺少明确指标的查询",
                missing_elements=["metric"],
                example_questions=["2025年8月的数据分析", "用户指标统计", "业务数据查询", "用户表现分析", "数据概览"]
            ),
            TestCaseTemplate(
                category="missing_metric",
                description="缺少明确指标的查询",
                missing_elements=["metric"],
                example_questions=["2025年8月的数据分析", "用户指标统计", "业务数据查询", "用户表现分析", "数据概览"]
            ),
            TestCaseTemplate(
                category="missing_metric",
                description="缺少明确指标的查询",
                missing_elements=["metric"],
                example_questions=["2025年8月的数据分析", "用户指标统计", "业务数据查询", "用户表现分析", "数据概览"]
            ),
            TestCaseTemplate(
                category="missing_metric",
                description="缺少明确指标的查询",
                missing_elements=["metric"],
                example_questions=["2025年8月的数据分析", "用户指标统计", "业务数据查询", "用户表现分析", "数据概览"]
            ),
            TestCaseTemplate(
                category="missing_metric",
                description="缺少明确指标的查询",
                missing_elements=["metric"],
                example_questions=["2025年8月的数据分析", "用户指标统计", "业务数据查询", "用户表现分析", "数据概览"]
            ),
            TestCaseTemplate(
                category="missing_metric",
                description="缺少明确指标的查询",
                missing_elements=["metric"],
                example_questions=["2025年8月的数据分析", "用户指标统计", "业务数据查询", "用户表现分析", "数据概览"]
            ),
            TestCaseTemplate(
                category="missing_metric",
                description="缺少明确指标的查询",
                missing_elements=["metric"],
                example_questions=["2025年8月的数据分析", "用户指标统计", "业务数据查询", "用户表现分析", "数据概览"]
            ),
            TestCaseTemplate(
                category="missing_metric",
                description="缺少明确指标的查询",
                missing_elements=["metric"],
                example_questions=["2025年8月的数据分析", "用户指标统计", "业务数据查询", "用户表现分析", "数据概览"]
            ),
            TestCaseTemplate(
                category="missing_metric",
                description="缺少明确指标的查询",
                missing_elements=["metric"],
                example_questions=["2025年8月的数据分析", "用户指标统计", "业务数据查询", "用户表现分析", "数据概览"]
            ),
            TestCaseTemplate(
                category="missing_metric",
                description="缺少明确指标的查询",
                missing_elements=["metric"],
                example_questions=["2025年8月的数据分析", "用户指标统计", "业务数据查询", "用户表现分析", "数据概览"]
            ),
            
            # 5 cases with both missing
            TestCaseTemplate(
                category="missing_both",
                description="缺少时间和指标的查询",
                missing_elements=["time", "metric"],
                example_questions=["查询数据", "分析趋势", "数据统计", "业务分析", "用户分析"]
            ),
            TestCaseTemplate(
                category="missing_both",
                description="缺少时间和指标的查询",
                missing_elements=["time", "metric"],
                example_questions=["查询数据", "分析趋势", "数据统计", "业务分析", "用户分析"]
            ),
            TestCaseTemplate(
                category="missing_both",
                description="缺少时间和指标的查询",
                missing_elements=["time", "metric"],
                example_questions=["查询数据", "分析趋势", "数据统计", "业务分析", "用户分析"]
            ),
            TestCaseTemplate(
                category="missing_both",
                description="缺少时间和指标的查询",
                missing_elements=["time", "metric"],
                example_questions=["查询数据", "分析趋势", "数据统计", "业务分析", "用户分析"]
            ),
            TestCaseTemplate(
                category="missing_both",
                description="缺少时间和指标的查询",
                missing_elements=["time", "metric"],
                example_questions=["查询数据", "分析趋势", "数据统计", "业务分析", "用户分析"]
            ),
        ]
        
        test_cases = []
        for i, template in enumerate(templates, 1):
            test_id = f"clarify_{i:03d}"
            print(f"Generating test case {test_id} ({template.category})...")
            test_case = self._generate_single_test_case(template, test_id)
            test_cases.append(test_case)
        
        return test_cases
    
    def create_clarification_config(self, test_cases: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create clarification configuration for test cases"""
        config = {}
        
        for test_case in test_cases:
            test_id = test_case['id']
            category = test_case['category']
            
            clarification_input = {}
            missing = []
            
            if category == "missing_time":
                missing = ["time"]
                clarification_input = {
                    "time": test_case.get('expected_time_filter', '2025-08'),
                    "metric": None
                }
            elif category == "missing_metric":
                missing = ["metric"]
                clarification_input = {
                    "time": None,
                    "metric": test_case.get('expected_metric', 'mau')
                }
            elif category == "missing_both":
                missing = ["time", "metric"]
                clarification_input = {
                    "time": test_case.get('expected_time_filter', '2025-08'),
                    "metric": test_case.get('expected_metric', 'mau')
                }
            
            config[test_id] = {
                "needs_clarification": True,
                "missing": missing,
                "clarification_input": clarification_input
            }
        
        return config


def main():
    """Main function to generate test cases"""
    print("Starting clarification test case generation...")
    
    generator = ClarificationTestGenerator()
    
    # Generate test cases
    print("Generating 30 test cases...")
    test_cases = generator.generate_test_cases()
    
    # Create clarification config
    print("Creating clarification configuration...")
    clarification_config = generator.create_clarification_config(test_cases)
    
    # Save test cases
    test_cases_file = Path("test_cases_clarification.json")
    with open(test_cases_file, 'w', encoding='utf-8') as f:
        json.dump(test_cases, f, ensure_ascii=False, indent=2)
    print(f"Saved {len(test_cases)} test cases to {test_cases_file}")
    
    # Save clarification config
    config_file = Path("test_clarification_config.json")
    with open(config_file, 'w', encoding='utf-8') as f:
        json.dump(clarification_config, f, ensure_ascii=False, indent=2)
    print(f"Saved clarification config to {config_file}")
    
    # Print summary
    print("\nGeneration Summary:")
    categories = {}
    for test_case in test_cases:
        category = test_case['category']
        categories[category] = categories.get(category, 0) + 1
    
    for category, count in categories.items():
        print(f"  {category}: {count} test cases")
    
    print(f"\nTotal: {len(test_cases)} test cases generated successfully!")


if __name__ == "__main__":
    main()
