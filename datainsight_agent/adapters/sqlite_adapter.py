"""
SQLite database adapter.

This module provides SQLite-specific database operations.
"""

import sqlite3
from typing import Any, Dict, List, Optional
from .base import DatabaseAdapter


class SQLiteAdapter(DatabaseAdapter):
    """SQLite database adapter."""
    
    def __init__(self, database_url: str):
        """Initialize SQLite adapter.
        
        Args:
            database_url: SQLite database URL (e.g., sqlite:///./database.db)
        """
        super().__init__(database_url)
        self._connection = None
    
    @property
    def dialect(self) -> str:
        """Return SQLite dialect."""
        return "sqlite"
    
    def connect(self) -> sqlite3.Connection:
        """Establish SQLite connection."""
        # Extract file path from URL
        if self.database_url.startswith("sqlite:///"):
            file_path = self.database_url[10:]  # Remove "sqlite:///"
        else:
            file_path = self.database_url
        
        self._connection = sqlite3.connect(file_path)
        self._connection.row_factory = sqlite3.Row  # Enable dict-like access
        return self._connection
    
    def execute_query(self, query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Execute a SQL query and return results."""
        if not self._connection:
            self.connect()
        
        cursor = self._connection.cursor()
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        
        # Convert Row objects to dictionaries
        results = []
        for row in cursor.fetchall():
            results.append(dict(row))
        
        return results
    
    def execute_non_query(self, query: str, params: Optional[Dict[str, Any]] = None) -> int:
        """Execute a non-query SQL statement."""
        if not self._connection:
            self.connect()
        
        cursor = self._connection.cursor()
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        
        self._connection.commit()
        return cursor.rowcount
    
    def get_table_info(self, table_name: str) -> List[Dict[str, Any]]:
        """Get table column information."""
        query = f"PRAGMA table_info({table_name})"
        results = self.execute_query(query)
        
        # Convert to standard format
        columns = []
        for row in results:
            columns.append({
                "name": row["name"],
                "type": row["type"],
                "nullable": not row["notnull"],
                "default": row["dflt_value"],
                "primary_key": bool(row["pk"])
            })
        
        return columns
    
    def create_table(self, table_name: str, columns: List[Dict[str, str]]) -> None:
        """Create a table with specified columns."""
        # Build column definitions
        column_defs = []
        for col in columns:
            col_def = f"{col['name']} {col['type']}"
            if not col.get('nullable', True):
                col_def += " NOT NULL"
            if col.get('default'):
                col_def += f" DEFAULT {col['default']}"
            if col.get('primary_key'):
                col_def += " PRIMARY KEY"
            column_defs.append(col_def)
        
        query = f"CREATE TABLE IF NOT EXISTS {table_name} ({', '.join(column_defs)})"
        self.execute_non_query(query)
    
    def insert_data(self, table_name: str, data: List[Dict[str, Any]]) -> int:
        """Insert data into a table."""
        if not data:
            return 0
        
        # Get column names from first row
        columns = list(data[0].keys())
        placeholders = ', '.join(['?' for _ in columns])
        column_names = ', '.join(columns)
        
        query = f"INSERT INTO {table_name} ({column_names}) VALUES ({placeholders})"
        
        if not self._connection:
            self.connect()
        
        cursor = self._connection.cursor()
        cursor.executemany(query, [tuple(row[col] for col in columns) for row in data])
        self._connection.commit()
        
        return cursor.rowcount
    
    def get_time_range(self, table_name: str, time_column: str) -> tuple[str, str]:
        """Get the time range from a table."""
        query = f"SELECT MIN({time_column}), MAX({time_column}) FROM {table_name}"
        results = self.execute_query(query)
        
        if results and results[0][f"MIN({time_column})"] and results[0][f"MAX({time_column})"]:
            return (
                results[0][f"MIN({time_column})"],
                results[0][f"MAX({time_column})"]
            )
        else:
            return ("", "")
    
    def close(self) -> None:
        """Close SQLite connection."""
        if self._connection:
            self._connection.close()
            self._connection = None
