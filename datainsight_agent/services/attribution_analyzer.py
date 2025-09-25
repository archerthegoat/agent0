"""
归因分析服务

提供深度归因分析能力，包括趋势分析、异常检测、多维度对比等。
"""

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from datetime import datetime
import json


@dataclass
class TrendData:
    """趋势数据"""
    period: str
    value: float
    change_rate: Optional[float] = None
    change_amount: Optional[float] = None


@dataclass
class AttributionResult:
    """归因分析结果"""
    dimension: str
    dimension_value: str
    base_value: float
    comparison_value: float
    change_rate: float
    change_amount: float
    contribution: float  # 贡献度百分比


@dataclass
class AnalysisReport:
    """分析报告"""
    title: str
    summary: str
    key_findings: List[str]
    trends: List[TrendData]
    attributions: List[AttributionResult]
    recommendations: List[str]
    data_quality: str


class AttributionAnalyzer:
    """归因分析器"""
    
    def __init__(self):
        self.logger = None
    
    def analyze_trends(self, data: List[Dict[str, Any]], 
                      time_field: str = None,
                      metric_field: str = None) -> List[TrendData]:
        """分析趋势数据"""
        # 使用配置化的字段名
        if time_field is None:
            from datainsight_agent.config.settings import load_settings
            s = load_settings()
            time_field = getattr(s, "dw_time_column", "month")
        
        if metric_field is None:
            # 默认使用第一个聚合字段的别名
            metric_field = "mau"  # 这个会在调用时传入
        
        trends = []
        
        # 按时间排序
        sorted_data = sorted(data, key=lambda x: x.get(time_field, ""))
        
        for i, record in enumerate(sorted_data):
            period = record.get(time_field, "")
            value = float(record.get(metric_field, 0))
            
            change_rate = None
            change_amount = None
            
            if i > 0:
                prev_value = float(sorted_data[i-1].get(metric_field, 0))
                if prev_value > 0:
                    change_rate = (value - prev_value) / prev_value
                    change_amount = value - prev_value
            
            trends.append(TrendData(
                period=period,
                value=value,
                change_rate=change_rate,
                change_amount=change_amount
            ))
        
        return trends
    
    def identify_anomalies(self, trends: List[TrendData], 
                          threshold: float = 0.15) -> List[TrendData]:
        """识别异常趋势"""
        anomalies = []
        
        for trend in trends:
            if trend.change_rate is not None and abs(trend.change_rate) > threshold:
                anomalies.append(trend)
        
        return anomalies
    
    def calculate_attribution(self, data: List[Dict[str, Any]],
                            dimension: str,
                            metric_field: str = "mau",
                            base_period: str = None,
                            comparison_period: str = None) -> List[AttributionResult]:
        """计算归因分析 - 改进版本"""
        attributions = []
        
        # 如果没有指定期间，自动推断期间
        if not base_period or not comparison_period:
            periods = sorted(set(record.get("month", "") for record in data))
            if len(periods) >= 2:
                base_period = periods[0]
                comparison_period = periods[-1]
            else:
                return attributions
        
        # 按维度分组并聚合数据
        dimension_groups = {}
        for record in data:
            dim_value = record.get(dimension, "unknown")
            period = record.get("month", "")
            value = float(record.get(metric_field, 0))
            
            if dim_value not in dimension_groups:
                dimension_groups[dim_value] = {}
            dimension_groups[dim_value][period] = value
        
        # 计算每个维度的变化
        for dim_value, periods in dimension_groups.items():
            base_value = periods.get(base_period, 0)
            comparison_value = periods.get(comparison_period, 0)
            
            if base_value > 0 or comparison_value > 0:  # 至少有一个期间有数据
                if base_value == 0:
                    change_rate = 1.0  # 从0增长到非0，视为100%增长
                else:
                    change_rate = (comparison_value - base_value) / base_value
                
                change_amount = comparison_value - base_value
                
                attributions.append(AttributionResult(
                    dimension=dimension,
                    dimension_value=dim_value,
                    base_value=base_value,
                    comparison_value=comparison_value,
                    change_rate=change_rate,
                    change_amount=change_amount,
                    contribution=0  # 将在后续计算
                ))
        
        # 计算贡献度 - 基于绝对变化量
        total_change = sum(abs(attr.change_amount) for attr in attributions)
        if total_change > 0:
            for attr in attributions:
                attr.contribution = abs(attr.change_amount) / total_change * 100
        
        return attributions
    
    def generate_summary_report(self, trends: List[TrendData],
                              attributions: List[AttributionResult],
                              anomalies: List[TrendData] = None) -> AnalysisReport:
        """生成简要报告"""
        
        # 计算总体趋势
        if len(trends) >= 2:
            latest_trend = trends[-1]
            previous_trend = trends[-2]
            
            if latest_trend.change_rate is not None:
                overall_change = latest_trend.change_rate
                overall_change_amount = latest_trend.change_amount
            else:
                overall_change = 0
                overall_change_amount = 0
        else:
            overall_change = 0
            overall_change_amount = 0
        
        # 生成标题
        if overall_change > 0:
            title = f"用户活跃度增长分析报告 ({overall_change:.1%})"
        elif overall_change < 0:
            title = f"用户活跃度下降分析报告 ({overall_change:.1%})"
        else:
            title = "用户活跃度分析报告"
        
        # 生成摘要 - 更自然的描述
        if len(trends) >= 2:
            first_period = trends[0].period
            last_period = trends[-1].period
            first_value = trends[0].value
            last_value = trends[-1].value
            
            if overall_change > 0:
                summary = f"在{first_period}到{last_period}期间，用户活跃度呈现增长趋势，从{first_value:,.0f}增长到{last_value:,.0f}，增长幅度为{overall_change:.1%}。"
            elif overall_change < 0:
                summary = f"在{first_period}到{last_period}期间，用户活跃度呈现下降趋势，从{first_value:,.0f}下降到{last_value:,.0f}，下降幅度为{abs(overall_change):.1%}。"
            else:
                summary = f"在{first_period}到{last_period}期间，用户活跃度保持相对稳定，维持在{first_value:,.0f}左右。"
        else:
            summary = "分析期间内，用户活跃度保持稳定，"
        
        # 关键发现 - 更自然的描述
        key_findings = []
        
        # 异常发现
        if anomalies:
            key_findings.append(f"发现{len(anomalies)}个异常变化点，需要重点关注")
        
        # 主要贡献维度
        if attributions:
            top_contributors = sorted(attributions, key=lambda x: abs(x.change_amount), reverse=True)[:3]
            for attr in top_contributors:
                if abs(attr.change_rate) > 0.05:  # 变化超过5%
                    if attr.change_rate > 0:
                        key_findings.append(f"{attr.dimension_value}维度表现突出，增长{attr.change_rate:.1%}，是整体增长的主要驱动力")
                    else:
                        key_findings.append(f"{attr.dimension_value}维度出现下滑，下降{abs(attr.change_rate):.1%}，对整体表现产生负面影响")
        
        # 如果没有显著变化，添加稳定性说明
        if not key_findings and len(trends) >= 2:
            key_findings.append("各维度表现相对稳定，未发现显著异常变化")
        
        # 建议 - 更具体的建议
        recommendations = []
        
        if overall_change < -0.1:  # 下降超过10%
            recommendations.append("深入分析下降原因，重点关注主要贡献维度的变化趋势")
            recommendations.append("制定针对性的改进措施，优先解决影响最大的问题")
            if attributions:
                top_negative = [attr for attr in attributions if attr.change_rate < 0]
                if top_negative:
                    top_negative.sort(key=lambda x: abs(x.change_amount), reverse=True)
                    recommendations.append(f"重点关注{top_negative[0].dimension_value}维度，其负向影响最大")
        
        elif overall_change > 0.1:  # 增长超过10%
            recommendations.append("分析增长驱动因素，识别成功经验")
            recommendations.append("将成功经验复制到其他维度，扩大增长效果")
            if attributions:
                top_positive = [attr for attr in attributions if attr.change_rate > 0]
                if top_positive:
                    top_positive.sort(key=lambda x: abs(x.change_amount), reverse=True)
                    recommendations.append(f"重点关注{top_positive[0].dimension_value}维度的成功经验")
        
        else:  # 稳定或小幅变化
            recommendations.append("保持当前策略，持续监控各维度表现")
            recommendations.append("寻找新的增长机会，优化现有流程")
        
        if anomalies:
            recommendations.append("对异常变化点进行深入调查，识别潜在问题或机会")
        
        return AnalysisReport(
            title=title,
            summary=summary,
            key_findings=key_findings,
            trends=trends,
            attributions=attributions,
            recommendations=recommendations,
            data_quality="数据质量良好" if len(trends) > 1 else "数据点不足"
        )
    
    def format_report(self, report: AnalysisReport) -> str:
        """格式化报告输出 - 生成自然的文字报告"""
        output = []
        
        # 标题
        output.append(f"# {report.title}")
        output.append("")
        
        # 执行摘要 - 更自然的文字描述
        output.append("## 📊 执行摘要")
        output.append(report.summary)
        output.append("")
        
        # 关键发现 - 用自然语言描述
        if report.key_findings:
            output.append("## 🔍 关键发现")
            for finding in report.key_findings:
                output.append(f"• {finding}")
            output.append("")
        
        # 趋势分析 - 用文字描述替代表格
        if report.trends and len(report.trends) > 1:
            output.append("## 📈 趋势分析")
            
            # 计算总体变化
            first_trend = report.trends[0]
            last_trend = report.trends[-1]
            if first_trend.change_rate is not None:
                overall_change = first_trend.change_rate
                if overall_change > 0:
                    output.append(f"整体趋势显示{first_trend.period}到{last_trend.period}期间，指标增长了{abs(overall_change):.1%}，从{first_trend.value:,.0f}增加到{last_trend.value:,.0f}。")
                elif overall_change < 0:
                    output.append(f"整体趋势显示{first_trend.period}到{last_trend.period}期间，指标下降了{abs(overall_change):.1%}，从{first_trend.value:,.0f}减少到{last_trend.value:,.0f}。")
                else:
                    output.append(f"整体趋势显示{first_trend.period}到{last_trend.period}期间，指标保持稳定，维持在{first_trend.value:,.0f}左右。")
            
            # 详细趋势描述
            output.append("\n详细变化情况：")
            for i, trend in enumerate(report.trends):
                if trend.change_rate is not None and trend.change_rate != 0:
                    change_desc = "增长" if trend.change_rate > 0 else "下降"
                    output.append(f"• {trend.period}: {trend.value:,.0f} ({change_desc}{abs(trend.change_rate):.1%})")
                else:
                    output.append(f"• {trend.period}: {trend.value:,.0f}")
            output.append("")
        
        # 归因分析 - 用自然语言描述
        if report.attributions:
            output.append("## 🎯 归因分析")
            
            # 按贡献度排序
            sorted_attrs = sorted(report.attributions, key=lambda x: abs(x.contribution), reverse=True)
            
            output.append("通过对各维度的深入分析，发现以下主要归因因素：")
            output.append("")
            
            for i, attr in enumerate(sorted_attrs, 1):
                if attr.change_rate > 0:
                    change_desc = f"增长{attr.change_rate:.1%}"
                    impact_desc = "正向贡献"
                elif attr.change_rate < 0:
                    change_desc = f"下降{abs(attr.change_rate):.1%}"
                    impact_desc = "负向影响"
                else:
                    change_desc = "保持稳定"
                    impact_desc = "无显著影响"
                
                output.append(f"{i}. **{attr.dimension_value}**: {change_desc}，从{attr.base_value:,.0f}变化到{attr.comparison_value:,.0f}，贡献度为{attr.contribution:.1f}%，属于{impact_desc}。")
            
            # 总结主要归因
            if sorted_attrs:
                top_contributor = sorted_attrs[0]
                output.append(f"\n**主要归因**: {top_contributor.dimension_value}是影响变化的最主要因素，贡献度达到{top_contributor.contribution:.1f}%。")
            output.append("")
        
        # 建议 - 更具体的建议
        if report.recommendations:
            output.append("## 💡 建议与行动方案")
            for i, rec in enumerate(report.recommendations, 1):
                output.append(f"{i}. {rec}")
            output.append("")
        
        # 数据质量说明
        output.append("## 📋 数据质量说明")
        output.append(report.data_quality)
        if len(report.trends) < 2:
            output.append("建议收集更多时间点的数据以获得更准确的分析结果。")
        
        return "\n".join(output)


# 全局实例
_analyzer_instance = None

def get_attribution_analyzer() -> AttributionAnalyzer:
    """获取归因分析器实例"""
    global _analyzer_instance
    if _analyzer_instance is None:
        _analyzer_instance = AttributionAnalyzer()
    return _analyzer_instance