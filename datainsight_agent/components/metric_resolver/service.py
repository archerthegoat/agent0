from __future__ import annotations

from typing import List

from datainsight_agent.core.interfaces import MetricResolverInterface

# Bridge to existing parsing pipeline
from datainsight_agent.services.parsers.metric_parser import MetricParser


class MetricResolver(MetricResolverInterface):
    """Adapter wrapper that exposes a simple resolve() API leveraging
    the existing MetricParser implementation.
    """

    def __init__(self) -> None:
        self._impl = MetricParser()

    def process(self, question: str) -> List[str]:  # type: ignore[override]
        return self.resolve(question)

    def resolve(self, question: str) -> List[str]:  # type: ignore[override]
        state = {"question": question}
        # Leverage parse_metrics to get normalized aggregations, then return aliases/keys
        aggs = self._impl.parse_metrics(state)
        return [a.alias for a in aggs if getattr(a, "alias", None)]




