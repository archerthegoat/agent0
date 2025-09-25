from __future__ import annotations

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))
from datainsight_agent.services.metric_registry import MetricRegistry
# Use LI build component instead of LangGraph
from datainsight_agent.orchestrator.li.pipeline import _BuildIRComponent  # type: ignore


def main() -> None:
    reg = MetricRegistry("metadata")
    reg.load()
    # Dump loaded metrics
    print("Loaded metrics:")
    seen: set[str] = set()
    for name, m in reg._name_to_metric.items():  # type: ignore[attr-defined]
        if m.metric_id in seen:
            continue
        seen.add(m.metric_id)
        print(f"- id={m.metric_id} name={m.canonical_name} aliases={m.aliases} aggr={m.aggregation} filters={m.filters}")

    # Verify injection by simulating build_ir per canonical metric name (LI component)
    print("\nInjection check:")
    for m_id in list(seen):
        # Find by canonical
        mdefs = [md for md in reg._name_to_metric.values() if md.metric_id == m_id]  # type: ignore[attr-defined]
        if not mdefs:
            continue
        m = mdefs[0]
        state = {"question": m.canonical_name, "concepts": [m.canonical_name], "kb_entities": []}
        out = _BuildIRComponent()(state)
        ir = out.get("ir") or {}
        aggs = ir.get("aggregations", [])
        print(f"* {m.canonical_name}: aggregations={aggs}")


if __name__ == "__main__":
    main()


