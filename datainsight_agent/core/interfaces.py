"""Core service interfaces for the decoupled architecture.

These interfaces define stable contracts that upper layers (API/CLI) and
lower layers (components/adapters) can rely on without creating circular
dependencies.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Protocol

from .types import QueryRewrite, TimeFilter


class ServiceInterface(ABC):
    """Base interface for all services."""

    @abstractmethod
    def process(self, input_data: Any) -> Any:
        """Process input and return an output.

        Concrete services are encouraged to expose explicit methods instead of
        relying on this generic method, but this provides a common base.
        """


class QueryRewriterInterface(ServiceInterface, ABC):
    """Interface for query rewrite component (Q2Q)."""

    @abstractmethod
    def rewrite(self, question: str) -> QueryRewrite:
        """Rewrite a natural language question and return structured hints."""


class TimeParserInterface(ServiceInterface, ABC):
    """Interface for time parsing component."""

    @abstractmethod
    def parse(self, question: str) -> Optional[TimeFilter]:
        """Parse time expression from question and return normalized filter."""


class SQLGeneratorInterface(ServiceInterface, ABC):
    """Interface for SQL generation component."""

    @abstractmethod
    def generate(self, ir: Any, table: Optional[str] = None) -> str:
        """Generate SQL from IR for the given table context."""


class DatabaseExecutorInterface(ServiceInterface, ABC):
    """Interface for executing SQL against a database."""

    @abstractmethod
    def execute(self, sql: str) -> List[Dict[str, Any]]:
        """Execute SQL and return rows as list of dicts."""


