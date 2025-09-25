"""
Database adapters for DataInsight Agent.

This module provides database-specific adapters for different database systems
including SQLite, MySQL, PostgreSQL, and ClickHouse.
"""

from .base import DatabaseAdapter
from .sqlite_adapter import SQLiteAdapter
from .postgresql_adapter import PostgreSQLAdapter
from .clickhouse_adapter import ClickHouseAdapter

__all__ = [
    "DatabaseAdapter",
    "SQLiteAdapter", 
    "PostgreSQLAdapter",
    "ClickHouseAdapter"
]
