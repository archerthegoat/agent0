from __future__ import annotations

from typing import Any, Dict, List

from datainsight_agent.core.interfaces import VectorRetrieverInterface
from datainsight_agent.services.kb_vector_index import KBVectorRetriever


class VectorRetriever(VectorRetrieverInterface):
    """Adapter wrapper for KB vector retrieval using existing service."""

    def __init__(self, index_name: str = "kb_vector_index") -> None:
        self._impl = KBVectorRetriever(index_name)

    def process(self, input_data: str) -> List[Dict[str, Any]]:  # type: ignore[override]
        return self.retrieve(str(input_data))

    def retrieve(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:  # type: ignore[override]
        hits = self._impl.search(query, top_k=top_k)
        return hits




