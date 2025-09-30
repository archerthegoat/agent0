from __future__ import annotations

from typing import Any, Dict, Generator, Optional, List
from datainsight_agent.utils.timing import measure_time

# Local helpers (no LangGraph deps)
def _sanitize_sql(sql: str) -> str:
	import re as _re
	return _re.sub(r"\b(DWS|DWD|DIM|ADS)\.", "", sql, flags=_re.IGNORECASE)

# LlamaIndex 导入（暂时禁用，使用顺序执行）
# from llama_index.core.workflow import Workflow as _Workflow
# from llama_index.core.workflow import step as _step


class _DeconstructComponent:
	@measure_time("deconstruct")
	def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
		# Minimal deconstruct: surface concepts from Q2Q
		st = dict(state)
		try:
			q2q = st.get("q2q") or {}
			cpts = q2q.get("concepts") or []
			if cpts and not st.get("concepts"):
				st["concepts"] = [str(x) for x in cpts if isinstance(x, str)]
		except Exception:
			pass
		return st


class _Q2QComponent:
	def __init__(self, pipeline_instance=None):
		self._pipeline_instance = pipeline_instance
	
	@measure_time("q2q")
	def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
		# 仅负责生成 q2q 结构，不做下游执行；若已有 q2q 则直接返回
		st = dict(state)
		# 若存在澄清后的覆盖，并要求进行 enrich，则执行一次 Q2Q 以补全概念/分组，但不覆盖 metric/time
		if st.get("q2q") and st.get("q2q_enrich_after_clarify"):
			try:
				q = str(st.get("question") or "").strip()
				if not q:
					return st
				# 运行重写
				if self._pipeline_instance:
					s = self._pipeline_instance._get_settings()
					rewriter = self._pipeline_instance._get_q2q_rewriter()
					rr = rewriter.rewrite(q)
				else:
					from datainsight_agent.services.core.query_rewriter import OptimizedQ2QRewriter
					rewriter = OptimizedQ2QRewriter()
					rr = rewriter.rewrite(q)
				if rr:
					try:
						q2q_now = st.get("q2q") or {}
						merged = dict(q2q_now)
						# 仅合并 concepts / group_by，不改动 metric / time_filter
						if getattr(rr, "concepts", None):
							c_old = set([str(x) for x in (q2q_now.get("concepts") or [])])
							c_new = [str(x) for x in rr.concepts if str(x) not in c_old]
							merged["concepts"] = list(c_old) + c_new
						if getattr(rr, "group_by", None):
							g_old = set([str(x) for x in (q2q_now.get("group_by") or [])])
							g_new = [str(x) for x in rr.group_by if str(x) not in g_old]
							merged["group_by"] = list(g_old) + g_new
						st["q2q"] = merged
					except Exception:
						pass
			finally:
				# 一次性使用完成，移除标志位
				try:
					st.pop("q2q_enrich_after_clarify", None)
				except Exception:
					pass
			return st
		# 否则：已有 q2q 直接跳过
		if st.get("q2q"):
			from datainsight_agent.common.logging import get_logger
			get_logger("q2q").debug("q2q_skip_existing", concepts=st.get('q2q', {}).get('concepts', []))
			return st
		
		try:
			q = str(st.get("question") or "").strip()
			if not q:
				return st
			
			try:
				print(f"[DEBUG] Q2Q开始处理问题: '{q[:50]}...'")
			except UnicodeError:
				print(f"[DEBUG] Q2Q开始处理问题: encoding error")
			
			# 智能跳过机制：检查问题是否已经足够明确
			if self._is_question_clear_enough(q):
				# 问题明确，直接构造基础q2q结构，跳过LLM调用
				st["q2q"] = self._create_basic_q2q(q)
				st["skipped_llm"] = True
				try:
					print(f"[DEBUG] Q2Q智能跳过，生成基础q2q: {st['q2q'].get('concepts', [])}")
				except UnicodeError:
					print(f"[DEBUG] Q2Q智能跳过，生成基础q2q: encoding error")
				return st
			
			# 问题不够明确，需要LLM重写
			# 使用缓存的实例，避免重复创建
			if self._pipeline_instance:
				s = self._pipeline_instance._get_settings()
				rewriter = self._pipeline_instance._get_q2q_rewriter()
				rr = rewriter.rewrite(q)
			else:
				# 回退到原始方式
				from datainsight_agent.services.core.query_rewriter import OptimizedQ2QRewriter
				rewriter = OptimizedQ2QRewriter()
				rr = rewriter.rewrite(q)
			
			if rr:
				try:
					q2q_data = rr.model_dump()
					st["q2q"] = q2q_data
					try:
						print(f"[DEBUG] Q2Q保存的q2q数据: {q2q_data}")
					except UnicodeError:
						print(f"[DEBUG] Q2Q保存的q2q数据: encoding error")
					# 若 concepts 存在于重写结果，且当前 state 尚无概念，则填充
					cpts = getattr(rr, "concepts", None)
					try:
						print(f"[DEBUG] Q2Q LLM重写结果: concepts={cpts}")
					except UnicodeError:
						print(f"[DEBUG] Q2Q LLM重写结果: encoding error")
					if cpts and not st.get("concepts"):
						st["concepts"] = [str(x) for x in cpts if isinstance(x, str)]
						try:
							print(f"[DEBUG] Q2Q填充concepts到state: {st['concepts']}")
						except UnicodeError:
							print(f"[DEBUG] Q2Q填充concepts到state: encoding error")
				except Exception:
					pass
			st["skipped_llm"] = False
			
		except Exception as e:
			# 忽略 Q2Q 错误；继续后续节点
			try:
				print(f"[DEBUG] Q2Q异常: {str(e)}")
			except UnicodeError:
				print(f"[DEBUG] Q2Q异常: encoding error")
			pass
		
		return st
	
	def _is_question_clear_enough(self, question: str) -> bool:
		"""判断问题是否已经足够明确，可以跳过LLM重写。"""
		from datainsight_agent.config.keyword_mappings import (
			Q2Q_METRIC_KEYWORDS, Q2Q_TIME_KEYWORDS, 
			Q2Q_GROUP_KEYWORDS, Q2Q_FUZZY_KEYWORDS
		)
		
		q_lower = question.lower()
		
		# 检查关键词
		has_metric = any(keyword in q_lower for keyword in Q2Q_METRIC_KEYWORDS)
		has_time = any(keyword in q_lower for keyword in Q2Q_TIME_KEYWORDS)
		has_group = any(keyword in q_lower for keyword in Q2Q_GROUP_KEYWORDS)
		has_fuzzy = any(keyword in q_lower for keyword in Q2Q_FUZZY_KEYWORDS)
		
		# 严格条件：必须同时满足所有条件
		clarity_score = sum([has_metric, has_time, has_group])
		question_length = len(question)
		
		return (clarity_score == 3 and 
		        5 <= question_length <= 20 and 
		        not has_fuzzy)
	
	def _create_basic_q2q(self, question: str) -> Dict[str, Any]:
		"""为明确的问题创建基础的q2q结构。"""
		from datainsight_agent.config.keyword_mappings import (
			Q2Q_GROUP_KEYWORDS, Q2Q_METRIC_KEYWORDS
		)
		
		q_lower = question.lower()
		
		# 提取基础概念
		concepts = []
		for keyword in Q2Q_GROUP_KEYWORDS:
			if keyword in q_lower:
				concepts.append(keyword)
				break
		
		for keyword in Q2Q_METRIC_KEYWORDS:
			if keyword in q_lower:
				concepts.append(keyword)
				break
		
		return {
			"rewritten_question": question,
			"metric": [],
			"group_by": [],
			"time_filter": None,
			"concepts": concepts,
			"clarify": False,
			"ask": None,
		}


class _RetrieveComponent:
	@measure_time("retrieve")
	def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
		# 直接调用 RetrievalService，避免依赖 LangGraph 节点
		from datainsight_agent.config.settings import load_settings
		from pathlib import Path
		from datainsight_agent.clients.vector_store import MilvusVectorStore, EmbeddingModel
		from datainsight_agent.clients.graph_client import LocalGraphClient
		from datainsight_agent.services.retrieval import RetrievalService
		from datainsight_agent.services.utils.auth import KnowledgeBaseAuth
		
		st = dict(state)
		
		# 权限验证
		auth = KnowledgeBaseAuth()
		user_id = state.get("user_id", "default_user")
		if not auth.check_permission(user_id, "kb_access", "read"):
			print(f"[WARN] 用户 {user_id} 没有知识库访问权限")
			st["kb_entities"] = []
			return st
		concepts = st.get("concepts", [])
		q2q = st.get("q2q", {})
		q2q_concepts = q2q.get("concepts", [])
		# print(f"[DEBUG] Retrieve开始执行: state.concepts={concepts}, q2q.concepts={q2q_concepts}")
		
		# 优先使用q2q.concepts，如果state.concepts为空
		if not concepts and q2q_concepts:
			concepts = q2q_concepts
			# print(f"[DEBUG] Retrieve使用q2q.concepts: {concepts}")
		
		# 智能跳过逻辑：根据配置和查询类型决定是否跳过检索
		try:
			s = load_settings()
			q2q = st.get("q2q") or {}
			question = str(st.get("question") or "").strip()
			time_filter = str(q2q.get("time_filter") or "").strip()
			
			print(f"[DEBUG] Retrieve跳过检查: retrieve_skip_no_time={getattr(s, 'retrieve_skip_no_time', True)}, time_require_explicit={getattr(s, 'time_require_explicit', False)}, time_filter='{time_filter}', question='{question[:50]}...'")
			
			# 检查是否应该跳过检索
			if (getattr(s, "retrieve_skip_no_time", True) and
				getattr(s, "time_require_explicit", False) and not time_filter and
				not self._query_needs_kb_context(question, q2q)):
				st["kb_entities"] = []
				st["skipped_reason"] = "no_time_filter_and_no_kb_needed"
				print(f"[DEBUG] Retrieve被智能跳过: {st['skipped_reason']}")
				return st
		except Exception as e:
			print(f"[DEBUG] Retrieve跳过检查异常: {e}")
			pass
		
		entities = []
		try:
			s = load_settings()
			# 使用 Milvus 向量存储
			from datainsight_agent.clients.vector_store import MilvusVectorStore
			vector_store = None
			local_graph = None
			
			# 初始化 Milvus 向量存储
			if getattr(s, "milvus_enabled", False):
				try:
					# 根据配置决定是否使用缓存
					cache_enabled = getattr(s, "retrieve_cache_enabled", True)
					
					if cache_enabled:
						# 优化：使用类级缓存的embedding模型和向量存储，避免重复初始化
						if not hasattr(_RetrieveComponent, '_shared_embedder'):
							_RetrieveComponent._shared_embedder = EmbeddingModel()
						if not hasattr(_RetrieveComponent, '_shared_vector_store'):
							_infer_dim = len(_RetrieveComponent._shared_embedder.embed(["__probe__"])[0])
							_RetrieveComponent._shared_vector_store = MilvusVectorStore(
								dim=int(_infer_dim), space=str(s.vector_space)
							)
						vector_store = _RetrieveComponent._shared_vector_store
					else:
						# 禁用缓存：每次都创建新实例
						embedder = EmbeddingModel()
						_infer_dim = len(embedder.embed(["__probe__"])[0])
						vector_store = MilvusVectorStore(
							dim=int(_infer_dim), space=str(s.vector_space)
						)
				except Exception as e:
					from datainsight_agent.common.logging import get_logger
					get_logger("retrieve").warning("milvus_init_failed", error=str(e))
					vector_store = None
			
			# 初始化本地图数据库
			gpath = Path(s.local_graph_path)
			if gpath.exists():
				local_graph = LocalGraphClient(str(gpath))
			
			if vector_store or local_graph:
				retriever = RetrievalService(vector_store=vector_store, local_graph=local_graph)
				# 优化：减少检索数量，提高性能
				rag_top_k = max(3, int(getattr(s, "rag_top_k", 5)) // 2)
				from datainsight_agent.common.logging import get_logger
				get_logger("retrieve").debug("retrieve_start", concepts=concepts, top_k=rag_top_k)
				entities = retriever.hybrid_knowledge_retriever(concepts, top_k=rag_top_k)
				get_logger("retrieve").debug("retrieve_end", count=len(entities))
				if local_graph:
					try:
						local_graph.close()
					except Exception:
						pass
			else:
				from datainsight_agent.common.logging import get_logger
				get_logger("retrieve").debug("no_vector_or_graph_store")
		except Exception as e:
			try:
				print(f"[DEBUG] Retrieve组件异常: {str(e)}")
			except UnicodeError:
				print(f"[DEBUG] Retrieve组件异常: encoding error")
			entities = []
		
		st["kb_entities"] = entities
		return st
	
	def _query_needs_kb_context(self, question: str, q2q: dict) -> bool:
		"""智能判断查询是否需要知识库上下文"""
		from datainsight_agent.config.keyword_mappings import KB_KEYWORDS
		
		question_lower = question.lower()
		
		# 1. 检查是否包含需要知识库的关键词
		has_kb_keywords = any(keyword in question_lower for keyword in KB_KEYWORDS)
		
		# 2. 检查Q2Q结果是否包含复杂概念
		concepts = q2q.get("concepts", [])
		has_complex_concepts = len(concepts) > 1 or any(
			concept in ["渠道", "地区", "用户", "活跃"] for concept in concepts
		)
		
		# 3. 检查是否包含多个维度
		group_by = q2q.get("group_by", [])
		has_multiple_dimensions = len(group_by) > 0
		
		# 4. 检查问题长度（复杂问题通常更长）
		is_complex_query = len(question) > 10
		
		# 综合判断：如果满足多个条件，则认为需要知识库上下文
		kb_score = sum([
			has_kb_keywords,
			has_complex_concepts,
			has_multiple_dimensions,
			is_complex_query
		])
		
		return kb_score >= 2


class _PlanComponent:
	@measure_time("plan")
	def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
		# 规划阶段：根据 q2q/问题文本/时间策略确定计划
		from datainsight_agent.config.settings import load_settings
		from datainsight_agent.services.registry.metric_registry import MetricRegistry
		from datainsight_agent.services.parsers.time_filter_parser import parse_time_filter
		
		st = dict(state)
		
		# 若 Q2Q 明示需要澄清
		try:
			q2q = st.get("q2q") or {}
			if bool(q2q.get("clarify")):
				st["plan"] = "clarify"
				return st
		except Exception:
			pass
		
		# 判断是否具备 metric 与（必要时）时间
		try:
			s = load_settings()
			q2q = st.get("q2q") or {}
			# metric：若有 clarified_inputs.metric 则优先用其进行注册表精确匹配；否则仅信原始问题文本
			try:
				qtxt = str(st.get("question") or "")
				clarified_metric = str((st.get("clarified_inputs") or {}).get("metric") or "").strip()
				if not hasattr(self, '_cached_metric_registry'):
					self._cached_metric_registry = MetricRegistry()
				if clarified_metric:
					has_metric = self._cached_metric_registry.resolve_from_signals([clarified_metric]) is not None
				else:
					has_metric = self._cached_metric_registry.resolve_from_signals([qtxt]) is not None
			except Exception:
				has_metric = False
			
			# 时间：若要求明确时间，则需要 q2q.time_filter 或可从问题文本解析
			time_required = bool(getattr(s, "time_require_explicit", False))
			has_time = True
			if time_required:
				has_time = bool(str(q2q.get("time_filter") or "").strip())
				if not has_time:
					try:
						time_col = getattr(s, "dw_time_column", "month") or "month"
						tf = parse_time_filter("", str(st.get("question") or ""), time_col)
						if tf is not None:
							has_time = True
							# 回写规范化时间字符串供后续 build_ir 使用
							try:
								val = str(tf.value)
								if val:
									q2q = dict(q2q)
									q2q["time_filter"] = val
									st["q2q"] = q2q
							except Exception:
								pass
					except Exception:
						has_time = False
			
			if has_metric and (has_time or not time_required):
				st["plan"] = "execute_sql"
			else:
				st["plan"] = "clarify"
				missing = []
				if not has_metric:
					missing.append("度量（如：MAU/UV）")
				if time_required and not has_time:
					missing.append("时间范围")
				if missing:
					st["response"] = "请补充：" + ",".join(missing) + "。"
		except Exception:
			st["plan"] = "clarify"
		
		return st


class _BuildIRComponent:
	@measure_time("build_ir")
	def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
		# 构建 IR：维度→group_by，度量解析，时间过滤解析与规范化
		from datainsight_agent.config.settings import load_settings
		from datainsight_agent.models.ir import SemanticQueryIR
		from datainsight_agent.services.parsers.dimension_parser import parse_dimensions
		from datainsight_agent.services.parsers.metric_parser import parse_metrics, parse_metric_filters
		from datainsight_agent.services.parsers.time_filter_parser import parse_time_filter
		
		st = dict(state)
		ir = SemanticQueryIR()
		
		# 解析维度
		ir.group_by = parse_dimensions(st)
		# 解析度量（无兜底：异常时保持空聚合/过滤，由上游 plan 驱动 clarify）
		try:
			ir.aggregations = parse_metrics(st)
			ir.filters.extend(parse_metric_filters(st))
		except Exception:
			pass

		# 若仍未识别出任何聚合度量，则触发澄清以便二次输入指标
		if not ir.aggregations:
			st["plan"] = "clarify"
			st["response"] = "请补充：度量（如：MAU/UV）。"
			st["ir"] = ir.model_dump()
			st["ir_obj"] = ir
			return st
		# 时间过滤解析
		try:
			s2_cfg = load_settings()
			time_col = getattr(s2_cfg, "dw_time_column", "month") or "month"
			q2q = st.get("q2q") or {}
			tf_raw = str(q2q.get("time_filter") or "").strip()
			
			try:
				time_filter = parse_time_filter(tf_raw, str(st.get("question") or ""), time_col)
			except ValueError as e:
				# 时间格式错误，返回错误信息
				st["plan"] = "clarify"
				st["response"] = f"时间格式错误: {str(e)}"
				st["ir"] = ir.model_dump()
				st["ir_obj"] = ir
				return st
			
			if time_filter:
				ir.filters.append(time_filter)
			else:
				# 如果要求明确时间且无时间，提前返回并置 plan=clarify
				if getattr(s2_cfg, "time_require_explicit", False):
					st["plan"] = "clarify"
					# 检查当前状态中是否已有指标信息
					q2q = st.get("q2q", {})
					current_metrics = [str(m) for m in (q2q.get("metric") or [])]
					has_metric = len(current_metrics) > 0
					if not has_metric:
						try:
							concepts = [str(c) for c in (st.get("concepts") or [])]
							qtxt = str(st.get("question") or "")
							# 优化：缓存MetricRegistry实例
							if not hasattr(self, '_cached_metric_registry'):
								from datainsight_agent.services.registry.metric_registry import MetricRegistry
								self._cached_metric_registry = MetricRegistry()
							has_metric = self._cached_metric_registry.resolve_from_signals(concepts + [qtxt]) is not None
						except Exception:
							has_metric = False
					# 使用动态年份生成提示信息
					from datetime import datetime
					current_year = datetime.now().year
					next_year = current_year + 1
					
					st.setdefault("response", "请补充：时间范围。")
					st["ir"] = ir.model_dump()
					st["ir_obj"] = ir
					return st
				else:
					# 不要求明确时间，创建默认时间过滤器
					from datainsight_agent.services.parsers.time_filter_parser import TimeFilterParser
					parser = TimeFilterParser()
					default_time_filter = parser.create_default_filter(time_col)
					ir.filters.append(default_time_filter)
		except Exception:
			pass
		# 去重 filters
		try:
			fset = set(); unique = []
			for f in list(getattr(ir, "filters", []) or []):
				key = (str(f.field), str(f.operator).upper(), str(f.value))
				if key in fset:
					continue
				fset.add(key); unique.append(f)
			ir.filters = unique
		except Exception:
			pass
		
		# 检测归因分析需求（在已解析出聚合后再决定，避免普通查询误触发）
		try:
			if getattr(ir, "aggregations", None):
				ir.attribution_analysis = self._detect_attribution_analysis({**st, "ir_obj_preview": ir})
			else:
				ir.attribution_analysis = None
		except Exception:
			ir.attribution_analysis = None
		
		# 简化IR验证，只检查关键错误
		try:
			from datainsight_agent.services.ir_validator import validate_ir
			validation_result = validate_ir(ir)
			st["ir_validation"] = validation_result.model_dump()

			# 只检查严重错误，忽略警告
			if not validation_result.valid and validation_result.errors:
				# 只处理关键错误，忽略轻微问题
				critical_errors = [e for e in validation_result.errors if "required" in e.lower() or "invalid" in e.lower()]
				if critical_errors:
					error_msg = "IR验证失败: " + "; ".join(critical_errors[:2])  # 只显示前2个错误
					st["response"] = error_msg
					st["plan"] = "clarify"
					st["ir_obj"] = ir
					st["ir"] = ir.model_dump()
					return st
		except Exception:
			# 验证失败不应该阻止流程，静默跳过
			pass
		
		st["ir_obj"] = ir
		st["ir"] = ir.model_dump()
		return st
	
	def _detect_attribution_analysis(self, state: Dict[str, Any]) -> Optional[Any]:
		"""检测是否需要归因分析"""
		try:
			from datainsight_agent.models.ir import AttributionAnalysis
			
			question = str(state.get("question", "")).lower()
			q2q = state.get("q2q", {})
			
			# 检测归因分析关键词
			attribution_keywords = [
				"下跌", "下降", "增长", "上升", "变化", "对比", "分析", "原因",
				"归因", "为什么", "季度", "同比", "环比", "趋势"
			]
			
			has_attribution_keywords = any(keyword in question for keyword in attribution_keywords)
			
			# 检测时间对比
			has_time_comparison = any([
				"季度" in question,
				"同比" in question,
				"环比" in question,
				"对比" in question
			])
			
			# 检测多维度分析 - 从问题中检测多维度关键词
			multi_dimension_keywords = ["渠道", "用户等级", "应用版本", "设备", "地区", "营销来源", "用户分群"]
			has_multi_dimensions = any(keyword in question for keyword in multi_dimension_keywords) or len(q2q.get("group_by", [])) > 1
			
			if has_attribution_keywords and (has_time_comparison or has_multi_dimensions):
				# 解析时间期间
				base_period = None
				comparison_period = None
				
				# 动态解析季度，优先使用问题中提到的年份，否则使用2024年（数据库中的年份）
				from datetime import datetime
				current_year = str(datetime.now().year)
				
				# 检查问题中是否提到具体年份
				question_year = "2025"  # 默认使用2025年，因为数据库中有2025年的数据
				if "2024" in question:
					question_year = "2024"
				elif "2025" in question:
					question_year = "2025"
				
				if "第三季度" in question and "第二季度" in question:
					base_period = f"{question_year}-Q2"
					comparison_period = f"{question_year}-Q3"
				elif "第二季度" in question and "第一季度" in question:
					base_period = f"{question_year}-Q1"
					comparison_period = f"{question_year}-Q2"
				elif "第三季度" in question:
					# 如果只提到第三季度，假设对比第二季度
					base_period = f"{question_year}-Q2"
					comparison_period = f"{question_year}-Q3"
				elif "第二季度" in question:
					# 如果只提到第二季度，假设对比第一季度
					base_period = f"{question_year}-Q1"
					comparison_period = f"{question_year}-Q2"
				
				# 解析维度
				dimensions = []
				if "渠道" in question:
					dimensions.append("channel_code")
				if "地区" in question:
					dimensions.append("region")
				if "用户等级" in question or "用户" in question:
					dimensions.append("user_level")
				
				# 解析阈值
				threshold = 0.15  # 默认15%
				if "15%" in question:
					threshold = 0.15
				elif "10%" in question:
					threshold = 0.10
				
			# 从IR中获取指标名称
			metrics = ["mau"]  # 默认值
			try:
				ir_preview = state.get("ir_obj_preview")
				if ir_preview and getattr(ir_preview, "aggregations", None):
					metrics = [a.alias or "mau" for a in (ir_preview.aggregations or [])]
			except Exception:
				pass
				
				return AttributionAnalysis(
					analysis_type="attribution",
					base_period=base_period,
					comparison_period=comparison_period,
					comparison_type="quarter_over_quarter",
					threshold=threshold,
					dimensions=dimensions,
					metrics=metrics
				)
			
			return None
			
		except Exception:
			return None
	


class _ExecuteOrRespondComponent:
	@measure_time("execute_or_respond")
	def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
		# 直接执行 IR→SQL→校验/执行，避免依赖 LangGraph 节点
		from datainsight_agent.config.settings import load_settings
		from datainsight_agent.models.ir import SemanticQueryIR
		from datainsight_agent.services.core.sql_generator import SQLGenerator
		from datainsight_agent.services.sql_validator import SQLValidator
		from datainsight_agent.services.core.sql_executor import SQLExecutor
		
		st = dict(state)
		plan = st.get("plan")
		
		if plan == "execute_sql":
			s = load_settings()
			# 确保 IR 存在
			ir_obj: SemanticQueryIR | None = st.get("ir_obj")
			if not ir_obj:
				st = _BuildIRComponent()(st)
				ir_obj = st.get("ir_obj")
			if not ir_obj:
				st["response"] = "无法从知识库构建查询意图（IR）。请提供更明确的指标或维度。"
				return st
			
			# 需要聚合（度量）
			if not getattr(ir_obj, "aggregations", None):
				st["response"] = "缺少度量（metric）。请在问题中明确指标（例如：月活、UV、PV）。"
				return st
			
			# 生成 SQL 并清洗
			sql = SQLGenerator(database_url=s.database_url).generate(ir_obj)
			sql = _sanitize_sql(sql)
			st["sql"] = sql
			
			# 校验与执行
			val = SQLValidator().validate(sql, database_url=s.database_url, do_explain=bool(s.database_url))
			st["validation"] = val.model_dump()
			try:
				if s.database_url:
					exec_res = SQLExecutor(s).execute(sql, limit=10)
					st["rows"] = exec_res
					
					# 如果启用了归因分析，生成报告
					if ir_obj.attribution_analysis and exec_res:
						try:
							# print(f"[DEBUG] 开始生成归因分析报告，数据行数: {len(exec_res)}")
							report = self._generate_attribution_report(ir_obj, exec_res)
							st["attribution_report"] = report
							# print(f"[DEBUG] 归因分析报告生成成功，长度: {len(report)}")
						except Exception as e:
							# print(f"[DEBUG] 归因分析报告生成失败: {e}")
							st["attribution_report"] = f"报告生成失败: {str(e)}"
					# else:
						# print(f"[DEBUG] 归因分析条件不满足: attribution_analysis={bool(ir_obj.attribution_analysis)}, exec_res={bool(exec_res)}")
			except Exception as exc:
				st["exec_error"] = str(exc)
		elif plan == "analysis":
			st["response"] = "当前需要知识库上下文来进行归因，请先同步KB或提供更具体的指标定义。"
		elif plan in ["clarify", "confirm_default_time"]:
			# 不覆盖澄清/确认文案
			pass
		else:
			st["response"] = "我需要更多信息（或知识库上下文）来继续。请明确指标或提供上下文。"
		
		return st
	
	def _generate_attribution_report(self, ir_obj: Any, data: List[Dict[str, Any]]) -> str:
		"""生成归因分析报告"""
		try:
			from datainsight_agent.services.attribution_analyzer import get_attribution_analyzer
			
			analyzer = get_attribution_analyzer()
			attribution = ir_obj.attribution_analysis
			
			# 分析趋势，使用配置化的字段名
			from datainsight_agent.config.settings import load_settings
			s = load_settings()
			time_field = getattr(s, "dw_time_column", "month")
			# 从IR中获取指标字段名
			metric_field = "mau"  # 默认值，实际应该从IR的aggregations中获取
			if ir_obj.aggregations:
				metric_field = ir_obj.aggregations[0].alias or "mau"
			
			trends = analyzer.analyze_trends(data, time_field=time_field, metric_field=metric_field)
			
			# 识别异常
			threshold = attribution.threshold or 0.15
			anomalies = analyzer.identify_anomalies(trends, threshold)
			
			# 计算归因
			attributions = []
			for dimension in attribution.dimensions:
				dim_attributions = analyzer.calculate_attribution(
					data, dimension, metric_field,
					attribution.base_period, attribution.comparison_period
				)
				attributions.extend(dim_attributions)
			
			# 生成报告
			report = analyzer.generate_summary_report(trends, attributions, anomalies)
			return analyzer.format_report(report)
			
		except Exception as e:
			return f"报告生成失败: {str(e)}"


class LIPipeline:
	"""简单的 LlamaIndex 驱动骨架。

	使用 LlamaIndex QueryPipeline 进行组件化编排，将现有节点实现包装为 LlamaIndex 组件。
	"""

	def __init__(self) -> None:
		# 暂时使用顺序执行模式（LlamaIndex API 已更新）
		self._li_pipeline = None
		# 缓存常用服务实例，避免重复创建
		self._settings = None
		self._q2q_rewriter = None
		self._metric_retriever = None
		
		# 组件化骨架（当前直接调用现有节点函数）
		self._q2q = _Q2QComponent(pipeline_instance=self)
		self._deconstruct = _DeconstructComponent()
		self._retrieve = _RetrieveComponent()
		self._plan = _PlanComponent()
		self._build_ir = _BuildIRComponent()
		self._execute = _ExecuteOrRespondComponent()

	def stream(self, state: Dict[str, Any], stream_mode: str = "values") -> Generator[Dict[str, Any], None, None]:
		"""使用并行执行模式优化性能。"""
		st = dict(state)
		
		# 并行执行Q2Q和Retrieve（如果Q2Q不需要LLM调用）
		if self._should_parallel_execute(st):
			import concurrent.futures
			# import threading  # 未使用
			
			# 创建线程池，增加并行度
			with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
				# 并行执行Q2Q、Retrieve和Deconstruct
				q2q_future = executor.submit(self._q2q, st)
				retrieve_future = executor.submit(self._retrieve, st)
				deconstruct_future = executor.submit(self._deconstruct, st)
				
				# 等待Q2Q完成
				st = q2q_future.result()
				
				# 等待Retrieve完成
				retrieve_result = retrieve_future.result()
				st.update(retrieve_result)
				
				# 等待Deconstruct完成
				deconstruct_result = deconstruct_future.result()
				st.update(deconstruct_result)
		else:
			# 顺序执行（Q2Q需要LLM调用时）
			st = self._q2q(st)
			st = self._retrieve(st)
			st = self._deconstruct(st)
		
		# 继续后续组件
		st = self._plan(st)
		st = self._build_ir(st)
		st = self._execute(st)
		yield st
	
	def _should_parallel_execute(self, state: Dict[str, Any]) -> bool:
		"""判断是否应该并行执行Q2Q和Retrieve"""
		question = str(state.get("question") or "").strip()
		if not question:
			return False
		
		# 如果问题明确，Q2Q会跳过LLM调用，可以并行执行
		return self._q2q._is_question_clear_enough(question)
	
	def _get_settings(self):
		"""获取缓存的设置实例"""
		if self._settings is None:
			from datainsight_agent.config.settings import load_settings
			self._settings = load_settings()
		return self._settings
	
	def _get_q2q_rewriter(self):
		"""获取缓存的Q2Q重写器实例"""
		if self._q2q_rewriter is None:
			from datainsight_agent.services.q2q import Q2QRewriter
			self._q2q_rewriter = Q2QRewriter()
		return self._q2q_rewriter
	
	def _get_metric_retriever(self):
		"""获取缓存的指标检索器实例"""
		if self._metric_retriever is None:
			from datainsight_agent.services.registry.metric_retriever import MetricRetriever
			self._metric_retriever = MetricRetriever()
		return self._metric_retriever


def build_pipeline() -> LIPipeline:
	"""构建并返回 LlamaIndex 管道实例。"""
	return LIPipeline()


