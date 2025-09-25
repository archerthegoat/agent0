"""
ClickHouse database adapter.

This module provides ClickHouse-specific database operations.
"""

from typing import Any, Dict, List, Optional
from .base import DatabaseAdapter


class ClickHouseAdapter(DatabaseAdapter):
    """ClickHouse database adapter."""
    
    def __init__(self, database_url: str):
        """Initialize ClickHouse adapter.
        
        Args:
            database_url: ClickHouse database URL (e.g., clickhouse://user:pass@host:port/db)
        """
        super().__init__(database_url)
        self._connection = None
        self._client = None
    
    @property
    def dialect(self) -> str:
        """Return ClickHouse dialect."""
        return "clickhouse"
    
    def connect(self):
        """Establish ClickHouse connection."""
        try:
            from clickhouse_driver import Client
            
            # Parse URL to extract connection parameters
            import urllib.parse as urlparse
            parsed = urlparse.urlparse(self.database_url)
            
            self._client = Client(
                host=parsed.hostname or 'localhost',
                port=parsed.port or 9000,
                user=parsed.username or 'default',
                password=parsed.password or '',
                database=parsed.path.lstrip('/') or 'default'
            )
            
            self._connection = self._client
            return self._connection
        except ImportError:
            raise ImportError(
                "ClickHouse adapter requires clickhouse-driver. "
                "Install with: pip install clickhouse-driver"
            )
    
    def execute_query(self, query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Execute a SQL query and return results."""
        if not self._connection:
            self.connect()
        
        if params:
            # ClickHouse driver doesn't support parameterized queries in the same way
            # We'll need to format the query manually
            formatted_query = self._format_query_with_params(query, params)
            result = self._client.execute(formatted_query)
        else:
            result = self._client.execute(query)
        
        # Convert to list of dictionaries
        results = []
        if result:
            # For ClickHouse, we need to get column names differently
            # Since we can't easily get column names from the result, 
            # we'll return the raw result for now
            for row in result:
                results.append(row)
        
        return results
    
    def execute_non_query(self, query: str, params: Optional[Dict[str, Any]] = None) -> int:
        """Execute a non-query SQL statement."""
        if not self._connection:
            self.connect()
        
        if params:
            formatted_query = self._format_query_with_params(query, params)
            self._client.execute(formatted_query)
        else:
            self._client.execute(query)
        
        # ClickHouse doesn't return row count for most operations
        return 0
    
    def _format_query_with_params(self, query: str, params: Dict[str, Any]) -> str:
        """Format query with parameters (simple string replacement)."""
        formatted_query = query
        for key, value in params.items():
            if isinstance(value, str):
                formatted_query = formatted_query.replace(f":{key}", f"'{value}'")
            else:
                formatted_query = formatted_query.replace(f":{key}", str(value))
        return formatted_query
    
    def get_table_info(self, table_name: str) -> List[Dict[str, Any]]:
        """Get table column information."""
        query = f"DESCRIBE {table_name}"
        result = self._client.execute(query)
        
        columns = []
        for row in result:
            columns.append({
                "name": row[0],
                "type": row[1],
                "nullable": "Nullable" in row[1],
                "default": row[2] if len(row) > 2 else None,
                "primary_key": False  # ClickHouse doesn't have traditional primary keys
            })
        
        return columns
    
    def create_table(self, table_name: str, columns: List[Dict[str, str]]) -> None:
        """Create a table with specified columns."""
        # Build column definitions
        column_defs = []
        
        for col in columns:
            col_def = f"`{col['name']}` {col['type']}"
            if col.get('default'):
                col_def += f" DEFAULT {col['default']}"
            column_defs.append(col_def)
        
        # ClickHouse uses ENGINE specification
        query = f"CREATE TABLE IF NOT EXISTS {table_name} ({', '.join(column_defs)}) ENGINE = MergeTree() ORDER BY tuple()"
        self.execute_non_query(query)
    
    def insert_data(self, table_name: str, data: List[Dict[str, Any]]) -> int:
        """Insert data into a table."""
        if not data:
            return 0
        
        # Get column names from first row
        columns = list(data[0].keys())
        column_names = ', '.join(f"`{col}`" for col in columns)
        
        # Prepare data for insertion
        values = []
        for row in data:
            values.append([row[col] for col in columns])
        
        query = f"INSERT INTO {table_name} ({column_names}) VALUES"
        self._client.execute(query, values)
        
        return len(data)
    
    def get_time_range(self, table_name: str, time_column: str) -> tuple[str, str]:
        """Get the time range from a table."""
        query = f"SELECT MIN(`{time_column}`), MAX(`{time_column}`) FROM {table_name}"
        results = self.execute_query(query)
        
        if results and results[0][f"MIN(`{time_column}`)"] and results[0][f"MAX(`{time_column}`)"]:
            return (
                str(results[0][f"MIN(`{time_column}`)"]),
                str(results[0][f"MAX(`{time_column}`)"])
            )
        else:
            return ("", "")
    
    def close(self) -> None:
        """Close ClickHouse connection."""
        if self._client:
            self._client.disconnect()
            self._client = None
        self._connection = None
