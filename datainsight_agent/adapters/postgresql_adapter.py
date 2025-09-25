"""
PostgreSQL database adapter.

This module provides PostgreSQL-specific database operations.
"""

from typing import Any, Dict, List, Optional
from .base import DatabaseAdapter


class PostgreSQLAdapter(DatabaseAdapter):
    """PostgreSQL database adapter."""
    
    def __init__(self, database_url: str):
        """Initialize PostgreSQL adapter.
        
        Args:
            database_url: PostgreSQL database URL (e.g., postgresql://user:pass@host:port/db)
        """
        super().__init__(database_url)
        self._connection = None
        self._engine = None
    
    @property
    def dialect(self) -> str:
        """Return PostgreSQL dialect."""
        return "postgresql"
    
    def connect(self):
        """Establish PostgreSQL connection."""
        try:
            from sqlalchemy import create_engine
            from sqlalchemy.orm import sessionmaker
            
            self._engine = create_engine(self.database_url)
            Session = sessionmaker(bind=self._engine)
            self._connection = Session()
            return self._connection
        except ImportError:
            raise ImportError(
                "PostgreSQL adapter requires sqlalchemy and psycopg2. "
                "Install with: pip install sqlalchemy psycopg2-binary"
            )
    
    def execute_query(self, query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Execute a SQL query and return results."""
        if not self._connection:
            self.connect()
        
        from sqlalchemy import text
        
        if params:
            result = self._connection.execute(text(query), params)
        else:
            result = self._connection.execute(text(query))
        
        # Convert to list of dictionaries
        results = []
        for row in result:
            results.append(dict(row._mapping))
        
        return results
    
    def execute_non_query(self, query: str, params: Optional[Dict[str, Any]] = None) -> int:
        """Execute a non-query SQL statement."""
        if not self._connection:
            self.connect()
        
        from sqlalchemy import text
        
        if params:
            result = self._connection.execute(text(query), params)
        else:
            result = self._connection.execute(text(query))
        
        self._connection.commit()
        return result.rowcount
    
    def get_table_info(self, table_name: str) -> List[Dict[str, Any]]:
        """Get table column information."""
        query = """
        SELECT 
            column_name as name,
            data_type as type,
            is_nullable = 'YES' as nullable,
            column_default as default,
            CASE WHEN pk.column_name IS NOT NULL THEN true ELSE false END as primary_key
        FROM information_schema.columns c
        LEFT JOIN (
            SELECT ku.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage ku
                ON tc.constraint_name = ku.constraint_name
            WHERE tc.table_name = :table_name
                AND tc.constraint_type = 'PRIMARY KEY'
        ) pk ON c.column_name = pk.column_name
        WHERE c.table_name = :table_name
        ORDER BY c.ordinal_position
        """
        
        results = self.execute_query(query, {"table_name": table_name})
        return results
    
    def create_table(self, table_name: str, columns: List[Dict[str, str]]) -> None:
        """Create a table with specified columns."""
        # Build column definitions
        column_defs = []
        primary_keys = []
        
        for col in columns:
            col_def = f'"{col["name"]}" {col["type"]}'
            if not col.get('nullable', True):
                col_def += " NOT NULL"
            if col.get('default'):
                col_def += f" DEFAULT {col['default']}"
            if col.get('primary_key'):
                primary_keys.append(f'"{col["name"]}"')
            column_defs.append(col_def)
        
        query = f"CREATE TABLE IF NOT EXISTS {table_name} ({', '.join(column_defs)})"
        if primary_keys:
            query += f", PRIMARY KEY ({', '.join(primary_keys)})"
        
        self.execute_non_query(query)
    
    def insert_data(self, table_name: str, data: List[Dict[str, Any]]) -> int:
        """Insert data into a table."""
        if not data:
            return 0
        
        # Get column names from first row
        columns = list(data[0].keys())
        column_names = ', '.join(f'"{col}"' for col in columns)
        placeholders = ', '.join([f':{col}' for col in columns])
        
        query = f"INSERT INTO {table_name} ({column_names}) VALUES ({placeholders})"
        
        if not self._connection:
            self.connect()
        
        from sqlalchemy import text
        
        total_rows = 0
        for row in data:
            result = self._connection.execute(text(query), row)
            total_rows += result.rowcount
        
        self._connection.commit()
        return total_rows
    
    def get_time_range(self, table_name: str, time_column: str) -> tuple[str, str]:
        """Get the time range from a table."""
        query = f'SELECT MIN("{time_column}"), MAX("{time_column}") FROM {table_name}'
        results = self.execute_query(query)
        
        if results and results[0][f'MIN("{time_column}")'] and results[0][f'MAX("{time_column}")']:
            return (
                str(results[0][f'MIN("{time_column}")']),
                str(results[0][f'MAX("{time_column}")'])
            )
        else:
            return ("", "")
    
    def close(self) -> None:
        """Close PostgreSQL connection."""
        if self._connection:
            self._connection.close()
            self._connection = None
        if self._engine:
            self._engine.dispose()
            self._engine = None
