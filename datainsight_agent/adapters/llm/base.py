from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict


class LLMAdapter(ABC):
    """Abstract LLM adapter interface."""

    @abstractmethod
    def generate(self, prompt: str, **kwargs: Any) -> str:
        raise NotImplementedError

    @abstractmethod
    def tool_call(self, *, system: str, user: str, tool_name: str, json_schema: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError



