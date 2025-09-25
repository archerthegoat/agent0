"""
Base database adapter interface.

This module defines the abstract base class for all database adapters,
providing a common interface for database operations across different systems.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel


class DatabaseAdapter(ABC):
    """Abstract base class for database adapters."""
    
    def __init__(self, database_url: str):
        """Initialize the adapter with a database URL.
        
        Args:
            database_url: Database connection URL
        """
        self.database_url = database_url
        self._engine = None
    
    @property
    @abstractmethod
    def dialect(self) -> str:
        """Return the SQL dialect name."""
        pass
    
    @abstractmethod
    def connect(self) -> Any:
        """Establish database connection."""
        pass
    
    @abstractmethod
    def execute_query(self, query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Execute a SQL query and return results.
        
        Args:
            query: SQL query string
            params: Query parameters
            
        Returns:
            List of result dictionaries
        """
        pass
    
    @abstractmethod
    def execute_non_query(self, query: str, params: Optional[Dict[str, Any]] = None) -> int:
        """Execute a non-query SQL statement.
        
        Args:
            query: SQL statement
            params: Statement parameters
            
        Returns:
            Number of affected rows
        """
        pass
    
    @abstractmethod
    def get_table_info(self, table_name: str) -> List[Dict[str, Any]]:
        """Get table column information.
        
        Args:
            table_name: Name of the table
            
        Returns:
            List of column information dictionaries
        """
        pass
    
    @abstractmethod
    def create_table(self, table_name: str, columns: List[Dict[str, str]]) -> None:
        """Create a table with specified columns.
        
        Args:
            table_name: Name of the table to create
            columns: List of column definitions
        """
        pass
    
    @abstractmethod
    def insert_data(self, table_name: str, data: List[Dict[str, Any]]) -> int:
        """Insert data into a table.
        
        Args:
            table_name: Name of the table
            data: List of data dictionaries
            
        Returns:
            Number of inserted rows
        """
        pass
    
    @abstractmethod
    def get_time_range(self, table_name: str, time_column: str) -> tuple[str, str]:
        """Get the time range from a table.
        
        Args:
            table_name: Name of the table
            time_column: Name of the time column
            
        Returns:
            Tuple of (min_time, max_time)
        """
        pass
    
    @abstractmethod
    def close(self) -> None:
        """Close database connection."""
        pass
    
    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


class DatabaseConfig(BaseModel):
    """Database configuration model."""
    
    dialect: str
    host: Optional[str] = None
    port: Optional[int] = None
    database: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    db_schema: Optional[str] = None  # Renamed to avoid conflict with BaseModel.schema
    ssl_mode: Optional[str] = None
    charset: Optional[str] = None
    
    class Config:
        """Pydantic configuration."""
        extra = "allow"
