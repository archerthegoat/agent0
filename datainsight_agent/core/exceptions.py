"""Unified exception hierarchy for the decoupled architecture."""


class DataInsightError(Exception):
    """Base exception for all agent errors."""


class ConfigurationError(DataInsightError):
    """Configuration related errors (missing envs, invalid values, etc.)."""


class AdapterError(DataInsightError):
    """Errors thrown by adapters (LLM/DB/Vector)."""


class ValidationError(DataInsightError):
    """Input or IR/SQL validation errors."""


class TimeoutError(DataInsightError):
    """Operation exceeded the configured timeout."""


