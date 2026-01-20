"""
Data Query Engine for PostgreSQL Queries

Handles SQL queries and data analysis against the PostgreSQL database.
Provides safe, user-friendly interfaces for data exploration.
"""

import logging
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import sys
from pathlib import Path

# Add parent directories to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

logger = logging.getLogger(__name__)


class DataQueryEngine:
    """
    Engine for executing queries against the PostgreSQL database.

    Provides safe query execution with proper formatting and error handling.
    """

    def __init__(self):
        self._connection_string = None
        self._pool = None
        self._initialized = False

    async def _ensure_initialized(self):
        """Ensure PostgreSQL connection is ready."""
        if self._initialized:
            return

        try:
            # Get PostgreSQL connection from environment
            import os
            host = os.getenv('POSTGRES_HOST', 'localhost')
            port = os.getenv('POSTGRES_PORT', '5432')
            database = os.getenv('POSTGRES_DB', 'vibemind')
            user = os.getenv('POSTGRES_USER', 'vibemind')
            password = os.getenv('POSTGRES_PASSWORD', '')

            self._connection_string = f"postgresql://{user}:{password}@{host}:{port}/{database}"

            # Import asyncpg for PostgreSQL operations
            import asyncpg

            # Create connection pool
            self._pool = await asyncpg.create_pool(
                self._connection_string,
                min_size=1,
                max_size=5,
                command_timeout=30
            )

            self._initialized = True
            logger.info("Data query engine initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize data query engine: {e}")
            raise

    async def execute_query_async(self, query: str, params: List[Any] = None) -> str:
        """
        Execute a custom SQL query safely.

        Args:
            query: The SQL query to execute
            params: Parameters for parameterized queries

        Returns:
            Formatted query results
        """
        try:
            await self._ensure_initialized()

            # Basic safety check - prevent destructive operations
            query_upper = query.upper().strip()
            if any(keyword in query_upper for keyword in ['DROP', 'DELETE', 'UPDATE', 'INSERT', 'ALTER', 'CREATE']):
                return "Error: Only SELECT queries are allowed for safety reasons."

            async with self._pool.acquire() as conn:
                if params:
                    rows = await conn.fetch(query, *params)
                else:
                    rows = await conn.fetch(query)

                if not rows:
                    return "Query executed successfully. No results returned."

                # Format results
                return self._format_query_results(rows)

        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            return f"Query failed: {str(e)}"

    async def get_bubble_stats_async(self, bubble_id: Optional[str] = None) -> str:
        """
        Get statistics about bubbles and their contents.

        Args:
            bubble_id: Optional specific bubble ID

        Returns:
            Formatted statistics
        """
        try:
            await self._ensure_initialized()

            async with self._pool.acquire() as conn:
                if bubble_id:
                    # Stats for specific bubble
                    row = await conn.fetchrow("""
                        SELECT
                            b.title,
                            COUNT(i.id) as idea_count,
                            COUNT(e.id) as edge_count,
                            b.created_at,
                            b.updated_at
                        FROM bubbles b
                        LEFT JOIN ideas i ON b.id = i.bubble_id AND NOT i.is_deleted
                        LEFT JOIN edges e ON b.id = e.bubble_id AND NOT e.is_deleted
                        WHERE b.id = $1 AND NOT b.is_deleted
                        GROUP BY b.id, b.title, b.created_at, b.updated_at
                    """, bubble_id)

                    if not row:
                        return f"No data found for bubble {bubble_id}"

                    return f"""
Bubble Statistics for "{row['title']}":
• Ideas: {row['idea_count']}
• Connections: {row['edge_count']}
• Created: {row['created_at'].strftime('%Y-%m-%d %H:%M')}
• Last Updated: {row['updated_at'].strftime('%Y-%m-%d %H:%M')}
                    """.strip()

                else:
                    # Overall statistics
                    rows = await conn.fetch("""
                        SELECT
                            b.space_type,
                            COUNT(DISTINCT b.id) as bubble_count,
                            COUNT(DISTINCT i.id) as idea_count,
                            COUNT(DISTINCT e.id) as edge_count
                        FROM bubbles b
                        LEFT JOIN ideas i ON b.id = i.bubble_id AND NOT i.is_deleted
                        LEFT JOIN edges e ON b.id = e.bubble_id AND NOT e.is_deleted
                        WHERE NOT b.is_deleted
                        GROUP BY b.space_type
                        ORDER BY b.space_type
                    """)

                    if not rows:
                        return "No bubble data found."

                    result = "Overall Statistics:\n"
                    total_bubbles = 0
                    total_ideas = 0
                    total_edges = 0

                    for row in rows:
                        result += f"\n{row['space_type'].title()} Space:"
                        result += f"\n• Bubbles: {row['bubble_count']}"
                        result += f"\n• Ideas: {row['idea_count']}"
                        result += f"\n• Connections: {row['edge_count']}"

                        total_bubbles += row['bubble_count']
                        total_ideas += row['idea_count']
                        total_edges += row['edge_count']

                    result += f"\n\nTotals:"
                    result += f"\n• Bubbles: {total_bubbles}"
                    result += f"\n• Ideas: {total_ideas}"
                    result += f"\n• Connections: {total_edges}"

                    return result

        except Exception as e:
            logger.error(f"Failed to get bubble stats: {e}")
            return f"Statistics query failed: {str(e)}"

    async def search_ideas_async(self, search_text: str, bubble_id: Optional[str] = None, limit: int = 10) -> str:
        """
        Search for ideas using full-text search.

        Args:
            search_text: Text to search for
            bubble_id: Optional bubble to limit search to
            limit: Maximum results

        Returns:
            Formatted search results
        """
        try:
            await self._ensure_initialized()

            async with self._pool.acquire() as conn:
                if bubble_id:
                    rows = await conn.fetch("""
                        SELECT i.title, i.content, b.title as bubble_title,
                               ts_rank(to_tsvector('english', i.title || ' ' || coalesce(i.content, '')), plainto_tsquery('english', $1)) as rank
                        FROM ideas i
                        JOIN bubbles b ON i.bubble_id = b.id
                        WHERE NOT i.is_deleted AND NOT b.is_deleted
                          AND i.bubble_id = $2
                          AND to_tsvector('english', i.title || ' ' || coalesce(i.content, '')) @@ plainto_tsquery('english', $1)
                        ORDER BY rank DESC
                        LIMIT $3
                    """, search_text, bubble_id, limit)
                else:
                    rows = await conn.fetch("""
                        SELECT i.title, i.content, b.title as bubble_title,
                               ts_rank(to_tsvector('english', i.title || ' ' || coalesce(i.content, '')), plainto_tsquery('english', $1)) as rank
                        FROM ideas i
                        JOIN bubbles b ON i.bubble_id = b.id
                        WHERE NOT i.is_deleted AND NOT b.is_deleted
                          AND to_tsvector('english', i.title || ' ' || coalesce(i.content, '')) @@ plainto_tsquery('english', $1)
                        ORDER BY rank DESC
                        LIMIT $2
                    """, search_text, limit)

                if not rows:
                    return f"No ideas found matching '{search_text}'"

                result = f"Search results for '{search_text}':\n"
                for i, row in enumerate(rows, 1):
                    result += f"\n{i}. **{row['title']}**"
                    result += f"\n   in bubble: {row['bubble_title']}"
                    if row['content']:
                        # Truncate content if too long
                        content = row['content'][:200] + "..." if len(row['content']) > 200 else row['content']
                        result += f"\n   {content}"
                    result += "\n"

                return result

        except Exception as e:
            logger.error(f"Idea search failed: {e}")
            return f"Search failed: {str(e)}"

    async def analyze_connections_async(self, idea_id: str) -> str:
        """
        Analyze connections for a specific idea.

        Args:
            idea_id: The idea ID to analyze

        Returns:
            Connection analysis
        """
        try:
            await self._ensure_initialized()

            async with self._pool.acquire() as conn:
                # Get the idea details
                idea_row = await conn.fetchrow("""
                    SELECT i.title, i.content, b.title as bubble_title
                    FROM ideas i
                    JOIN bubbles b ON i.bubble_id = b.id
                    WHERE i.id = $1 AND NOT i.is_deleted
                """, idea_id)

                if not idea_row:
                    return f"Idea {idea_id} not found."

                # Get connections
                connection_rows = await conn.fetch("""
                    SELECT
                        CASE WHEN source_id = $1 THEN target_id ELSE source_id END as connected_id,
                        CASE WHEN source_id = $1 THEN 'outgoing' ELSE 'incoming' END as direction,
                        i.title as connected_title,
                        e.edge_type,
                        e.weight
                    FROM edges e
                    JOIN ideas i ON (CASE WHEN e.source_id = $1 THEN e.target_id ELSE e.source_id END) = i.id
                    WHERE (e.source_id = $1 OR e.target_id = $1)
                      AND NOT e.is_deleted
                      AND NOT i.is_deleted
                    ORDER BY e.weight DESC, i.title
                """, idea_id)

                result = f"Connection Analysis for '{idea_row['title']}'\n"
                result += f"in bubble: {idea_row['bubble_title']}\n\n"

                if not connection_rows:
                    result += "No connections found."
                else:
                    result += f"Connected to {len(connection_rows)} ideas:\n"
                    for row in connection_rows:
                        direction_symbol = "→" if row['direction'] == 'outgoing' else "←"
                        result += f"• {direction_symbol} {row['connected_title']} ({row['edge_type']}, weight: {row['weight']})\n"

                return result

        except Exception as e:
            logger.error(f"Connection analysis failed: {e}")
            return f"Analysis failed: {str(e)}"

    async def get_recent_activity_async(self, hours: int = 24) -> str:
        """
        Get recent activity across all bubbles.

        Args:
            hours: Hours to look back

        Returns:
            Recent activity summary
        """
        try:
            await self._ensure_initialized()

            since_time = datetime.now() - timedelta(hours=hours)

            async with self._pool.acquire() as conn:
                # Recent bubbles
                bubble_rows = await conn.fetch("""
                    SELECT title, created_at
                    FROM bubbles
                    WHERE NOT is_deleted AND created_at >= $1
                    ORDER BY created_at DESC
                    LIMIT 5
                """, since_time)

                # Recent ideas
                idea_rows = await conn.fetch("""
                    SELECT i.title, b.title as bubble_title, i.created_at
                    FROM ideas i
                    JOIN bubbles b ON i.bubble_id = b.id
                    WHERE NOT i.is_deleted AND NOT b.is_deleted AND i.created_at >= $1
                    ORDER BY i.created_at DESC
                    LIMIT 10
                """, since_time)

                result = f"Recent Activity (last {hours} hours):\n\n"

                if bubble_rows:
                    result += "New Bubbles:\n"
                    for row in bubble_rows:
                        result += f"• {row['title']} ({row['created_at'].strftime('%H:%M')})\n"
                    result += "\n"

                if idea_rows:
                    result += "New Ideas:\n"
                    for row in idea_rows:
                        result += f"• {row['title']} in {row['bubble_title']} ({row['created_at'].strftime('%H:%M')})\n"

                if not bubble_rows and not idea_rows:
                    result += "No recent activity found."

                return result

        except Exception as e:
            logger.error(f"Recent activity query failed: {e}")
            return f"Activity query failed: {str(e)}"

    async def generate_report_async(self, report_type: str, bubble_id: Optional[str] = None) -> str:
        """
        Generate various data analysis reports.

        Args:
            report_type: Type of report
            bubble_id: Optional bubble filter

        Returns:
            Formatted report
        """
        try:
            await self._ensure_initialized()

            if report_type == 'summary':
                return await self._generate_summary_report(bubble_id)
            elif report_type == 'activity':
                return await self._generate_activity_report(bubble_id)
            elif report_type == 'connections':
                return await self._generate_connections_report(bubble_id)
            elif report_type == 'content_analysis':
                return await self._generate_content_report(bubble_id)
            else:
                return f"Unknown report type: {report_type}"

        except Exception as e:
            logger.error(f"Report generation failed: {e}")
            return f"Report generation failed: {str(e)}"

    async def _generate_summary_report(self, bubble_id: Optional[str]) -> str:
        """Generate a summary report."""
        stats = await self.get_bubble_stats_async(bubble_id)
        activity = await self.get_recent_activity_async(168)  # Last week
        return f"Summary Report\n{'='*50}\n\n{stats}\n\n{activity}"

    async def _generate_activity_report(self, bubble_id: Optional[str]) -> str:
        """Generate an activity timeline report."""
        # Implementation would show activity over time
        return "Activity Report: Implementation pending"

    async def _generate_connections_report(self, bubble_id: Optional[str]) -> str:
        """Generate a connections analysis report."""
        # Implementation would analyze network structure
        return "Connections Report: Implementation pending"

    async def _generate_content_report(self, bubble_id: Optional[str]) -> str:
        """Generate a content analysis report."""
        # Implementation would analyze content patterns
        return "Content Analysis Report: Implementation pending"

    def _format_query_results(self, rows) -> str:
        """Format query results as readable text."""
        if not rows:
            return "No results."

        # Convert to list of dicts for easier handling
        results = [dict(row) for row in rows]

        # Get column names
        columns = list(results[0].keys()) if results else []

        # Format as table-like text
        result = ""

        # Header
        for col in columns:
            result += f"{col:<20}"
        result += "\n" + "-" * (20 * len(columns)) + "\n"

        # Data rows
        for row in results[:50]:  # Limit to 50 rows
            for col in columns:
                value = str(row[col])[:18] + "..." if len(str(row[col])) > 18 else str(row[col])
                result += f"{value:<20}"
            result += "\n"

        if len(results) > 50:
            result += f"\n... and {len(results) - 50} more rows"

        return result

    async def execute_dml_async(self, query: str, params: List[Any] = None, confirm: bool = False) -> str:
        """
        Execute a Data Manipulation Language (DML) query safely.

        Args:
            query: The DML query to execute
            params: Parameters for parameterized queries
            confirm: Must be True for destructive operations

        Returns:
            Execution results
        """
        try:
            await self._ensure_initialized()

            # Security checks
            query_upper = query.upper().strip()

            # Block dangerous operations
            if any(keyword in query_upper for keyword in ['DROP', 'ALTER', 'CREATE', 'TRUNCATE']):
                return "Error: DROP, ALTER, CREATE, and TRUNCATE operations are not allowed."

            # Check for destructive operations requiring confirmation
            destructive_ops = ['DELETE', 'UPDATE', 'INSERT']
            is_destructive = any(op in query_upper for op in destructive_ops)

            if is_destructive and not confirm:
                return f"⚠️  Destructive operation detected. Add 'confirm=True' to execute:\n{query[:100]}..."

            async with self._pool.acquire() as conn:
                if params:
                    result = await conn.execute(query, *params)
                else:
                    result = await conn.execute(query)

                # Parse result for user-friendly output
                if 'DELETE' in query_upper:
                    # Try to get affected row count
                    try:
                        count = getattr(result, 'rowcount', 0)
                        return f"Successfully deleted {count} row(s)."
                    except:
                        return "Delete operation completed."
                elif 'UPDATE' in query_upper:
                    try:
                        count = getattr(result, 'rowcount', 0)
                        return f"Successfully updated {count} row(s)."
                    except:
                        return "Update operation completed."
                elif 'INSERT' in query_upper:
                    return "Insert operation completed successfully."
                else:
                    return f"DML operation completed: {str(result)}"

        except Exception as e:
            logger.error(f"DML execution failed: {e}")
            return f"DML operation failed: {str(e)}"

    async def update_idea_async(self, idea_id: str, updates: Dict[str, Any], confirm: bool = False) -> str:
        """
        Update a specific idea with safety checks.

        Args:
            idea_id: The idea ID to update
            updates: Fields to update
            confirm: Must be True to execute

        Returns:
            Update confirmation
        """
        try:
            await self._ensure_initialized()

            if not confirm:
                return f"⚠️  Update operation requires confirmation. Add 'confirm=True' to update idea {idea_id}."

            # Build safe update query
            set_parts = []
            params = []

            allowed_fields = {'title', 'content', 'idea_type'}
            for field, value in updates.items():
                if field in allowed_fields:
                    set_parts.append(f"{field} = ${len(params) + 1}")
                    params.append(value)

            if not set_parts:
                return "No valid fields to update."

            query = f"""
                UPDATE ideas
                SET {', '.join(set_parts)}, updated_at = NOW()
                WHERE id = ${len(params) + 1}
            """
            params.append(idea_id)

            async with self._pool.acquire() as conn:
                result = await conn.execute(query, *params)
                count = getattr(result, 'rowcount', 0)

                if count > 0:
                    return f"Successfully updated idea {idea_id}."
                else:
                    return f"No idea found with ID {idea_id}."

        except Exception as e:
            logger.error(f"Idea update failed: {e}")
            return f"Update failed: {str(e)}"

    async def delete_idea_async(self, idea_id: str, confirm: bool = False) -> str:
        """
        Delete a specific idea with safety checks.

        Args:
            idea_id: The idea ID to delete
            confirm: Must be True to execute

        Returns:
            Deletion confirmation
        """
        try:
            await self._ensure_initialized()

            if not confirm:
                return f"⚠️  Delete operation requires confirmation. Add 'confirm=True' to delete idea {idea_id}."

            async with self._pool.acquire() as conn:
                # First check if idea exists
                row = await conn.fetchrow("SELECT title FROM ideas WHERE id = $1", idea_id)
                if not row:
                    return f"No idea found with ID {idea_id}."

                title = row['title']

                # Delete the idea
                result = await conn.execute("DELETE FROM ideas WHERE id = $1", idea_id)
                count = getattr(result, 'rowcount', 0)

                if count > 0:
                    return f"Successfully deleted idea '{title}' (ID: {idea_id})."
                else:
                    return f"Failed to delete idea {idea_id}."

        except Exception as e:
            logger.error(f"Idea deletion failed: {e}")
            return f"Deletion failed: {str(e)}"

    async def insert_data_async(self, table: str, data: Dict[str, Any], confirm: bool = False) -> str:
        """
        Insert data into a safe table.

        Args:
            table: Target table (restricted to safe tables)
            data: Data to insert
            confirm: Must be True for non-safe tables

        Returns:
            Insert confirmation
        """
        try:
            await self._ensure_initialized()

            # Security: only allow safe tables
            safe_tables = {'ideas', 'metadata'}
            if table not in safe_tables:
                if not confirm:
                    return f"⚠️  Insert into table '{table}' requires confirmation. Add 'confirm=True'."
                else:
                    return f"Error: Table '{table}' is not in the allowed list for inserts."

            # Build insert query
            columns = list(data.keys())
            placeholders = [f"${i+1}" for i in range(len(columns))]
            values = list(data.values())

            query = f"""
                INSERT INTO {table} ({', '.join(columns)})
                VALUES ({', '.join(placeholders)})
            """

            async with self._pool.acquire() as conn:
                await conn.execute(query, *values)
                return f"Successfully inserted data into {table}."

        except Exception as e:
            logger.error(f"Data insertion failed: {e}")
            return f"Insertion failed: {str(e)}"

    async def close(self):
        """Close the database connection pool."""
        if self._pool:
            await self._pool.close()
            self._pool = None
            self._initialized = False
            logger.info("Data query engine closed")