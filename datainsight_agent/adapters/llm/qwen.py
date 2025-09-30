from __future__ import annotations

from typing import Any, Dict

from datainsight_agent.adapters.llm.base import LLMAdapter
from datainsight_agent.services.llm import QwenClient
from datainsight_agent.config.settings import load_settings


class QwenAdapter(LLMAdapter):
    """Adapter wrapping existing QwenClient to satisfy LLMAdapter API."""

    def __init__(self) -> None:
        self._client = QwenClient(load_settings())

    def generate(self, prompt: str, **kwargs: Any) -> str:
        return self._client.generate_sql(prompt)

    def tool_call(self, *, system: str, user: str, tool_name: str, json_schema: Dict[str, Any]) -> Dict[str, Any]:
        return self._client.tool_call(system=system, user=user, tool_name=tool_name, json_schema=json_schema)




