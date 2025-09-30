from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional
from datainsight_agent.config.settings import load_settings


class MetricDef:
    def __init__(
        self,
        metric_id: str,
        canonical_name: str,
        aliases: List[str],
        aggregation: Dict[str, str],
        filters: List[Dict[str, str]],
        table_mapping: Optional[Dict[str, str]] = None,
    ) -> None:
        self.metric_id = metric_id
        self.canonical_name = canonical_name
        self.aliases = aliases
        self.aggregation = aggregation
        self.filters = filters
        self.table_mapping = table_mapping or {}

    def all_names_lower(self) -> List[str]:
        names = [self.canonical_name.lower()] + [a.lower() for a in self.aliases]
        # 添加聚合别名
        agg_alias = self.aggregation.get('alias', '')
        if agg_alias:
            names.append(agg_alias.lower())
        return names


class MetricRegistry:
    """Load metric definitions from metadata directory.

    Expected JSON structure (example):
    {
      "id": "metric.mau",
      "canonical_name": "月活",
      "aliases": ["MAU", "月活跃用户"],
      "aggregation": {"function": "COUNT", "field": "DISTINCT user_id", "alias": "mau"},
      "filters": [{"field": "active", "operator": "=", "value": "1"}]
    }
    """

    def __init__(self, metadata_dir: str | Path = "metadata") -> None:
        self._dir = Path(metadata_dir)
        self._name_to_metric: Dict[str, MetricDef] = {}
        self._loaded: bool = False

    def load(self) -> None:
        if self._loaded:
            return
        if not self._dir.exists():
            self._loaded = True
            return
        s = load_settings()
        enrich = bool(getattr(s, "metric_enrichment_enabled", True))
        default_func = str(getattr(s, "default_metric_function", "COUNT") or "COUNT").upper()
        default_field = str(getattr(s, "default_metric_field", "DISTINCT user_id") or "DISTINCT user_id")
        active_keywords = [k.strip().lower() for k in str(getattr(s, "metric_active_keywords_csv", "活跃,active") or "").split(",") if k.strip()]
        active_flag_col = str(getattr(s, "active_flag_column", "active") or "active")
        for p in self._dir.glob("*.json"):
            try:
                with p.open("r", encoding="utf-8-sig") as f:
                    data = json.load(f)
                # Support both single-object and array-of-metrics formats
                items = data if isinstance(data, list) else [data]
                for it in items:
                    if not isinstance(it, dict):
                        continue
                    metric_id = str(it.get("id") or "").strip()
                    canonical_name = str(it.get("canonical_name") or "").strip()
                    aliases = [str(a) for a in (it.get("aliases") or [])]
                    aggregation = dict(it.get("aggregation") or {})
                    filters = list(it.get("filters") or [])
                    # Auto-enrich aggregation if missing
                    if enrich and (not aggregation or not str(aggregation.get("function") or "").strip()):
                        aggregation = {
                            "function": default_func,
                            "field": default_field,
                            "alias": (metric_id or canonical_name or "metric").split(".")[-1].lower(),
                        }
                    # Auto-add active=1 filter for active-like metrics when missing
                    name_text = (canonical_name + " " + " ".join(aliases)).lower()
                    if enrich and any(k in name_text for k in active_keywords):
                        has_active = any(str(f.get("field") or "").strip().lower() == active_flag_col.lower() for f in filters)
                        if not has_active:
                            filters.append({"field": active_flag_col, "operator": "=", "value": "1"})
                    if not canonical_name or not aggregation:
                        continue
                    
                    # 提取table_mapping信息 - 修复这里的关键错误！
                    table_mapping = it.get("table_mapping", {})
                    
                    mdef = MetricDef(metric_id, canonical_name, aliases, aggregation, filters, table_mapping)
                    for nm in mdef.all_names_lower():
                        self._name_to_metric[nm] = mdef
            except Exception:
                continue
        # 可选：合并同义词文件（metadata/metric_synonyms.json）
        try:
            syn_path = self._dir / "metric_synonyms.json"
            if syn_path.exists():
                with syn_path.open("r", encoding="utf-8-sig") as f:
                    syn_data = json.load(f)
                # 支持两种格式：
                # 1) { "metric_mau": ["月活跃用户", ...], ... }
                # 2) [ {"metric_id": "metric_mau", "aliases": ["..."]}, ... ]
                if isinstance(syn_data, dict):
                    for mid, extra_aliases in syn_data.items():
                        if not isinstance(extra_aliases, list):
                            continue
                        self._merge_synonyms_by_id(mid, extra_aliases)
                elif isinstance(syn_data, list):
                    for obj in syn_data:
                        if not isinstance(obj, dict):
                            continue
                        mid = str(obj.get("metric_id") or "").strip()
                        extra_aliases = obj.get("aliases") or []
                        if mid and isinstance(extra_aliases, list):
                            self._merge_synonyms_by_id(mid, extra_aliases)
        except Exception:
            pass
        self._loaded = True

    def resolve_from_signals(self, signals: List[str]) -> Optional[MetricDef]:
        """Resolve a metric by matching any signal (case-insensitive) to canonical/aliases."""
        self.load()
        for s in signals:
            s_low = str(s).lower()
            if s_low in self._name_to_metric:
                return self._name_to_metric[s_low]
        return None

    # --- 辅助：合并同义词 ---
    def _merge_synonyms_by_id(self, metric_id: str, aliases: List[str]) -> None:
        if not aliases:
            return
        # 找到该 metric 的主定义
        target: Optional[MetricDef] = None
        for m in set(self._name_to_metric.values()):
            if getattr(m, "metric_id", "") == metric_id:
                target = m
                break
        if not target:
            return
        # 规范化+去重
        existing = set(a.lower() for a in target.aliases)
        for a in aliases:
            aa = str(a).strip()
            if not aa:
                continue
            if aa.lower() in existing:
                continue
            target.aliases.append(aa)
            existing.add(aa.lower())
            # 注册别名到索引表
            self._name_to_metric[aa.lower()] = target

    # --- 候选推荐 ---
    def suggest_from_text(self, text: str, top_k: int = 5) -> List[MetricDef]:
        self.load()
        t = (text or "").lower()
        if not t:
            return []
        scored: List[tuple[int, MetricDef]] = []
        seen = set()
        for m in set(self._name_to_metric.values()):
            names = m.all_names_lower()
            score = 0
            for nm in names:
                if nm and (nm in t or t in nm):
                    score = max(score, len(nm))
            if score > 0 and id(m) not in seen:
                seen.add(id(m))
                scored.append((score, m))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [m for _, m in scored[: max(1, top_k)]]

    def has_metric(self, metric_name: str) -> bool:
        """Check if a metric exists by name (case-insensitive)"""
        self.load()
        return str(metric_name).lower() in self._name_to_metric

    def get_all_metric_names(self) -> List[str]:
        """Get all canonical metric names"""
        self.load()
        return [metric.canonical_name for metric in set(self._name_to_metric.values())]

