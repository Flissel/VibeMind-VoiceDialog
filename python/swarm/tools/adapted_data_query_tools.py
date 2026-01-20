"""
Adapted Data Query Tools for AutoGen Swarm

Tools for SQL queries and data analysis from PostgreSQL.
These provide user-facing functionality for data exploration.
"""

import logging
from typing import Optional, Dict, Any, List
import sys
from pathlib import Path

# Add parent directories to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

logger = logging.getLogger(__name__)


def execute_sql_query(query: str, params: Optional[List[Any]] = None) -> str:
    """
    Execute a custom SQL query against the PostgreSQL database.

    SECURITY: Only SELECT queries are allowed for safety.
    For data modifications, use the specific DML tools below.

    Args:
        query: The SQL query to execute (SELECT only)
        params: Optional parameters for parameterized queries

    Returns:
        Query results formatted as readable text
    """
    try:
        from swarm.tools.data_query_engine import DataQueryEngine
        query_engine = DataQueryEngine()

        # Execute query synchronously for tool use
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            result = loop.run_until_complete(query_engine.execute_query_async(query, params or []))
            return result
        finally:
            loop.close()

    except Exception as e:
        logger.error(f"SQL query execution failed: {e}")
        return f"Query failed: {str(e)}"


def execute_dml_query(query: str, params: Optional[List[Any]] = None, confirm: bool = False) -> str:
    """
    Execute a Data Manipulation Language (DML) query.

    SECURITY: Allows INSERT, UPDATE, DELETE operations with confirmation requirement.
    DROP and ALTER operations are NOT allowed.

    Args:
        query: The DML query to execute (INSERT, UPDATE, DELETE only)
        params: Optional parameters for parameterized queries
        confirm: Must be True to execute destructive operations

    Returns:
        Execution results or confirmation prompt
    """
    try:
        from swarm.tools.data_query_engine import DataQueryEngine
        query_engine = DataQueryEngine()

        # Execute query synchronously for tool use
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            result = loop.run_until_complete(query_engine.execute_dml_async(query, params or [], confirm))
            return result
        finally:
            loop.close()

    except Exception as e:
        logger.error(f"DML query execution failed: {e}")
        return f"DML operation failed: {str(e)}"


def update_idea_data(idea_id: str, updates: Dict[str, Any], confirm: bool = False) -> str:
    """
    Update idea data in PostgreSQL.

    Args:
        idea_id: The idea ID to update
        updates: Dictionary of fields to update (title, content, etc.)
        confirm: Must be True to execute the update

    Returns:
        Update confirmation or error message
    """
    try:
        from swarm.tools.data_query_engine import DataQueryEngine
        query_engine = DataQueryEngine()

        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            result = loop.run_until_complete(query_engine.update_idea_async(idea_id, updates, confirm))
            return result
        finally:
            loop.close()

    except Exception as e:
        logger.error(f"Idea update failed: {e}")
        return f"Update failed: {str(e)}"


def delete_idea_data(idea_id: str, confirm: bool = False) -> str:
    """
    Delete idea data from PostgreSQL.

    Args:
        idea_id: The idea ID to delete
        confirm: Must be True to execute the deletion

    Returns:
        Deletion confirmation or error message
    """
    try:
        from swarm.tools.data_query_engine import DataQueryEngine
        query_engine = DataQueryEngine()

        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            result = loop.run_until_complete(query_engine.delete_idea_async(idea_id, confirm))
            return result
        finally:
            loop.close()

    except Exception as e:
        logger.error(f"Idea deletion failed: {e}")
        return f"Deletion failed: {str(e)}"


def insert_custom_data(table: str, data: Dict[str, Any], confirm: bool = False) -> str:
    """
    Insert custom data into a PostgreSQL table.

    SECURITY: Only allowed for specific safe tables (ideas, metadata).
    General INSERT operations require explicit confirmation.

    Args:
        table: Target table name (restricted to safe tables)
        data: Data to insert
        confirm: Must be True to execute the insert

    Returns:
        Insert confirmation or error message
    """
    try:
        from swarm.tools.data_query_engine import DataQueryEngine
        query_engine = DataQueryEngine()

        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            result = loop.run_until_complete(query_engine.insert_data_async(table, data, confirm))
            return result
        finally:
            loop.close()

    except Exception as e:
        logger.error(f"Data insertion failed: {e}")
        return f"Insertion failed: {str(e)}"


def get_bubble_statistics(bubble_id: Optional[str] = None) -> str:
    """
    Get statistics about bubbles and their contents.

    Args:
        bubble_id: Optional specific bubble ID, or None for all bubbles

    Returns:
        Statistics about bubbles, ideas, and connections
    """
    try:
        from swarm.tools.data_query_engine import DataQueryEngine
        query_engine = DataQueryEngine()

        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            result = loop.run_until_complete(query_engine.get_bubble_stats_async(bubble_id))
            return result
        finally:
            loop.close()

    except Exception as e:
        logger.error(f"Failed to get bubble statistics: {e}")
        return f"Statistics query failed: {str(e)}"


def search_ideas_by_content(search_text: str, bubble_id: Optional[str] = None, limit: int = 10) -> str:
    """
    Search for ideas using full-text search.

    Args:
        search_text: Text to search for
        bubble_id: Optional bubble to limit search to
        limit: Maximum number of results

    Returns:
        Search results with matching ideas
    """
    try:
        from swarm.tools.data_query_engine import DataQueryEngine
        query_engine = DataQueryEngine()

        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            result = loop.run_until_complete(query_engine.search_ideas_async(search_text, bubble_id, limit))
            return result
        finally:
            loop.close()

    except Exception as e:
        logger.error(f"Idea search failed: {e}")
        return f"Search failed: {str(e)}"


def analyze_idea_connections(idea_id: str) -> str:
    """
    Analyze connections and relationships for a specific idea.

    Args:
        idea_id: The idea ID to analyze

    Returns:
        Analysis of connections, related ideas, and network metrics
    """
    try:
        from swarm.tools.data_query_engine import DataQueryEngine
        query_engine = DataQueryEngine()

        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            result = loop.run_until_complete(query_engine.analyze_connections_async(idea_id))
            return result
        finally:
            loop.close()

    except Exception as e:
        logger.error(f"Connection analysis failed: {e}")
        return f"Analysis failed: {str(e)}"


def get_recent_activity(hours: int = 24) -> str:
    """
    Get recent activity across all bubbles.

    Args:
        hours: Number of hours to look back

    Returns:
        Recent changes and new content
    """
    try:
        from swarm.tools.data_query_engine import DataQueryEngine
        query_engine = DataQueryEngine()

        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            result = loop.run_until_complete(query_engine.get_recent_activity_async(hours))
            return result
        finally:
            loop.close()

    except Exception as e:
        logger.error(f"Recent activity query failed: {e}")
        return f"Activity query failed: {str(e)}"


def generate_data_report(report_type: str, bubble_id: Optional[str] = None) -> str:
    """
    Generate various data analysis reports.

    Args:
        report_type: Type of report ('summary', 'activity', 'connections', 'content_analysis')
        bubble_id: Optional bubble to limit report to

    Returns:
        Formatted report with insights and statistics
    """
    try:
        from swarm.tools.data_query_engine import DataQueryEngine
        query_engine = DataQueryEngine()

        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            result = loop.run_until_complete(query_engine.generate_report_async(report_type, bubble_id))
            return result
        finally:
            loop.close()

    except Exception as e:
        logger.error(f"Report generation failed: {e}")
        return f"Report generation failed: {str(e)}"


# Collect all query tools for export
DATA_QUERY_TOOLS = [
    # Read-only operations
    execute_sql_query,
    get_bubble_statistics,
    search_ideas_by_content,
    analyze_idea_connections,
    get_recent_activity,
    generate_data_report,

    # Data manipulation operations (with safety checks)
    execute_dml_query,
    update_idea_data,
    delete_idea_data,
    insert_custom_data,
]


__all__ = [
    "execute_sql_query",
    "get_bubble_statistics",
    "search_ideas_by_content",
    "analyze_idea_connections",
    "get_recent_activity",
    "generate_data_report",
    "execute_dml_query",
    "update_idea_data",
    "delete_idea_data",
    "insert_custom_data",
    "DATA_QUERY_TOOLS",
]