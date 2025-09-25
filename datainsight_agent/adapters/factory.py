"""
Database adapter factory.

This module provides a factory for creating database adapters based on the database URL.
"""

from typing import Optional
from .base import DatabaseAdapter
from .sqlite_adapter import SQLiteAdapter
from .postgresql_adapter import PostgreSQLAdapter
from .clickhouse_adapter import ClickHouseAdapter


class DatabaseAdapterFactory:
    """Factory for creating database adapters."""
    
    @staticmethod
    def create_adapter(database_url: str) -> DatabaseAdapter:
        """Create a database adapter based on the URL.
        
        Args:
            database_url: Database connection URL
            
        Returns:
            Appropriate database adapter instance
            
        Raises:
            ValueError: If the URL scheme is not supported
        """
        if not database_url:
            raise ValueError("Database URL cannot be empty")
        
        # Determine adapter type from URL scheme
        if database_url.startswith("sqlite://"):
            return SQLiteAdapter(database_url)
        elif database_url.startswith("postgresql://") or database_url.startswith("postgres://"):
            return PostgreSQLAdapter(database_url)
        elif database_url.startswith("clickhouse://"):
            return ClickHouseAdapter(database_url)
        else:
            raise ValueError(f"Unsupported database URL scheme: {database_url.split('://')[0]}")
    
    @staticmethod
    def get_supported_schemes() -> list[str]:
        """Get list of supported database URL schemes.
        
        Returns:
            List of supported schemes
        """
        return ["sqlite", "postgresql", "postgres", "clickhouse"]
    
    @staticmethod
    def is_supported(database_url: str) -> bool:
        """Check if a database URL is supported.
        
        Args:
            database_url: Database connection URL
            
        Returns:
            True if supported, False otherwise
        """
        try:
            DatabaseAdapterFactory.create_adapter(database_url)
            return True
        except ValueError:
            return False
