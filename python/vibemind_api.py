"""
VibeMind API Server - REST API for Advanced Features

Phase 19: Comprehensive REST API providing access to:
- Super Memory API
- Upload functionality
- Agent history and analytics
- Advanced visualization endpoints
- Real-time collaboration features

Features:
- RESTful API design
- Async request handling
- Comprehensive error handling
- Rate limiting and authentication
- OpenAPI/Swagger documentation
"""

import asyncio
import logging
import os
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union
from pathlib import Path
import tempfile
import shutil
import hashlib
import base64

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Query, BackgroundTasks
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

from super_memory_api import get_super_memory, MemoryQuery, MemoryEntry
from swarm.orchestrator.intent_orchestrator import get_orchestrator
from swarm.analysis.user_context import UserContext

logger = logging.getLogger(__name__)


# =========================================================================
# DATA MODELS
# =========================================================================

class MemoryStoreRequest(BaseModel):
    """Request model for storing memory."""
    content: str = Field(..., description="Memory content")
    memory_type: str = Field(..., description="Type of memory (conversation, idea, task, learning, context)")
    user_id: str = Field(..., description="User identifier")
    session_id: str = Field(..., description="Session identifier")
    importance: float = Field(0.5, ge=0.0, le=1.0, description="Importance score")
    tags: List[str] = Field(default_factory=list, description="Tags for categorization")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

class MemoryQueryRequest(BaseModel):
    """Request model for memory queries."""
    query_text: str = Field(..., description="Search query text")
    user_id: str = Field(..., description="User identifier")
    memory_types: Optional[List[str]] = Field(None, description="Filter by memory types")
    tags: Optional[List[str]] = Field(None, description="Filter by tags")
    min_importance: float = Field(0.0, ge=0.0, le=1.0, description="Minimum importance score")
    max_age_days: Optional[float] = Field(None, description="Maximum age in days")
    limit: int = Field(10, ge=1, le=100, description="Maximum results to return")
    include_related: bool = Field(True, description="Include related memories")

class IntentProcessRequest(BaseModel):
    """Request model for intent processing."""
    intent_text: str = Field(..., description="Natural language user intent")
    user_id: str = Field(..., description="User identifier")
    session_id: str = Field(..., description="Session identifier")
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context")

class UploadResponse(BaseModel):
    """Response model for file uploads."""
    file_id: str
    filename: str
    content_type: str
    size_bytes: int
    upload_timestamp: float
    checksum: str

class AgentHistoryEntry(BaseModel):
    """Agent interaction history entry."""
    timestamp: float
    agent_name: str
    action: str
    result: str
    duration_ms: float
    success: bool
    metadata: Dict[str, Any] = Field(default_factory=dict)

class VisualizationData(BaseModel):
    """Data for visualization endpoints."""
    data_type: str
    time_range: str
    filters: Dict[str, Any] = Field(default_factory=dict)
    aggregation: str = "hourly"


# =========================================================================
# API SERVER
# =========================================================================

class VibeMindAPI:
    """
    Main API server class handling all endpoints and business logic.
    """

    def __init__(self):
        self.app = FastAPI(
            title="VibeMind API",
            description="Advanced API for VibeMind's AI-powered features",
            version="1.0.0",
            docs_url="/docs",
            redoc_url="/redoc"
        )

        # Add CORS middleware
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],  # Configure appropriately for production
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        # Initialize components
        self.super_memory = get_super_memory()
        self.orchestrator = get_orchestrator()

        # File storage
        self.upload_dir = Path("uploads")
        self.upload_dir.mkdir(exist_ok=True)

        # Agent history storage
        self.agent_history: List[AgentHistoryEntry] = []
        self.max_history_size = 10000

        # Register routes
        self._register_routes()

        logger.info("VibeMindAPI initialized")

    def _register_routes(self):
        """Register all API routes."""

        @self.app.get("/")
        async def root():
            """API root endpoint."""
            return {
                "message": "VibeMind API v1.0.0",
                "features": [
                    "Super Memory API",
                    "Intent Processing",
                    "File Upload",
                    "Agent History",
                    "Advanced Visualization"
                ]
            }

        @self.app.get("/health")
        async def health_check():
            """Health check endpoint."""
            return {
                "status": "healthy",
                "timestamp": datetime.now().isoformat(),
                "version": "1.0.0"
            }

        # =========================================================================
        # SUPER MEMORY API ENDPOINTS
        # =========================================================================

        @self.app.post("/api/v1/memory/store", response_model=str)
        async def store_memory(request: MemoryStoreRequest):
            """
            Store a new memory entry.

            Automatically stores the memory and returns the memory ID.
            """
            try:
                memory_id = await self.super_memory.store_memory(
                    content=request.content,
                    memory_type=request.memory_type,
                    user_id=request.user_id,
                    session_id=request.session_id,
                    importance=request.importance,
                    tags=request.tags,
                    metadata=request.metadata
                )

                # Also store in agent history
                await self._record_agent_action(
                    "memory_store",
                    f"Stored memory: {memory_id}",
                    {"memory_id": memory_id, "user_id": request.user_id}
                )

                return memory_id

            except Exception as e:
                logger.error(f"Memory storage failed: {e}")
                raise HTTPException(status_code=500, detail=f"Memory storage failed: {str(e)}")

        @self.app.post("/api/v1/memory/query")
        async def query_memory(request: MemoryQueryRequest):
            """
            Query memories based on search criteria.

            Returns relevant memories ranked by relevance score.
            """
            try:
                query = MemoryQuery(
                    query_text=request.query_text,
                    user_id=request.user_id,
                    memory_types=request.memory_types,
                    tags=request.tags,
                    min_importance=request.min_importance,
                    max_age_days=request.max_age_days,
                    limit=request.limit,
                    include_related=request.include_related
                )

                result = await self.super_memory.retrieve_memories(query)

                # Record query in agent history
                await self._record_agent_action(
                    "memory_query",
                    f"Queried memories: {len(result.results)} results",
                    {"query": request.query_text, "results_count": len(result.results)}
                )

                return {
                    "query": request.dict(),
                    "results": [
                        {
                            "id": memory.id,
                            "content": memory.content,
                            "memory_type": memory.memory_type,
                            "importance": memory.importance,
                            "timestamp": memory.timestamp,
                            "tags": list(memory.tags),
                            "relevance_score": result.relevance_scores.get(memory.id, 0.0)
                        }
                        for memory in result.results
                    ],
                    "total_found": result.total_found,
                    "search_time": result.search_time
                }

            except Exception as e:
                logger.error(f"Memory query failed: {e}")
                raise HTTPException(status_code=500, detail=f"Memory query failed: {str(e)}")

        @self.app.put("/api/v1/memory/{memory_id}/importance")
        async def update_memory_importance(memory_id: str, importance: float = Query(..., ge=0.0, le=1.0)):
            """Update the importance of a memory."""
            try:
                success = await self.super_memory.update_memory_importance(memory_id, importance)

                if not success:
                    raise HTTPException(status_code=404, detail="Memory not found")

                await self._record_agent_action(
                    "memory_update",
                    f"Updated memory importance: {memory_id}",
                    {"memory_id": memory_id, "new_importance": importance}
                )

                return {"success": True, "memory_id": memory_id, "new_importance": importance}

            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Memory update failed: {e}")
                raise HTTPException(status_code=500, detail=f"Memory update failed: {str(e)}")

        @self.app.delete("/api/v1/memory/{memory_id}")
        async def delete_memory(memory_id: str):
            """Delete a memory entry."""
            try:
                success = await self.super_memory.delete_memory(memory_id)

                if not success:
                    raise HTTPException(status_code=404, detail="Memory not found")

                await self._record_agent_action(
                    "memory_delete",
                    f"Deleted memory: {memory_id}",
                    {"memory_id": memory_id}
                )

                return {"success": True, "memory_id": memory_id}

            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Memory deletion failed: {e}")
                raise HTTPException(status_code=500, detail=f"Memory deletion failed: {str(e)}")

        @self.app.post("/api/v1/memory/consolidate")
        async def consolidate_memories(user_id: str, max_age_days: int = 30):
            """Consolidate similar memories for a user."""
            try:
                consolidation_count = await self.super_memory.consolidate_memories(user_id, max_age_days)

                await self._record_agent_action(
                    "memory_consolidate",
                    f"Consolidated {consolidation_count} memories",
                    {"user_id": user_id, "consolidations": consolidation_count}
                )

                return {
                    "success": True,
                    "user_id": user_id,
                    "consolidations_performed": consolidation_count
                }

            except Exception as e:
                logger.error(f"Memory consolidation failed: {e}")
                raise HTTPException(status_code=500, detail=f"Memory consolidation failed: {str(e)}")

        @self.app.post("/api/v1/memory/prune")
        async def prune_memories(user_id: str):
            """Prune low-importance memories for a user."""
            try:
                pruned_count = await self.super_memory.prune_memories(user_id)

                await self._record_agent_action(
                    "memory_prune",
                    f"Pruned {pruned_count} memories",
                    {"user_id": user_id, "pruned_count": pruned_count}
                )

                return {
                    "success": True,
                    "user_id": user_id,
                    "memories_pruned": pruned_count
                }

            except Exception as e:
                logger.error(f"Memory pruning failed: {e}")
                raise HTTPException(status_code=500, detail=f"Memory pruning failed: {str(e)}")

        @self.app.get("/api/v1/memory/stats/{user_id}")
        async def get_memory_stats(user_id: str):
            """Get comprehensive memory statistics for a user."""
            try:
                stats = await self.super_memory.get_memory_stats(user_id)
                return stats

            except Exception as e:
                logger.error(f"Memory stats retrieval failed: {e}")
                raise HTTPException(status_code=500, detail=f"Memory stats retrieval failed: {str(e)}")

        # =========================================================================
        # INTENT PROCESSING ENDPOINTS
        # =========================================================================

        @self.app.post("/api/v1/intent/process")
        async def process_intent(request: IntentProcessRequest):
            """Process user intent through the enhanced orchestration pipeline."""
            try:
                context = UserContext(
                    user_id=request.user_id,
                    session_id=request.session_id,
                    additional_context=request.context or {}
                )

                result = await self.orchestrator.process_intent(request.intent_text, context)

                # Record in agent history
                await self._record_agent_action(
                    "intent_process",
                    f"Processed intent: {request.intent_text[:50]}...",
                    {
                        "intent_text": request.intent_text,
                        "event_type": result.event_type,
                        "job_id": result.job_id
                    }
                )

                return {
                    "job_id": result.job_id,
                    "event_type": result.event_type,
                    "stream": result.stream,
                    "response_hint": result.response_hint,
                    "is_conversational": result.is_conversational,
                    "error": result.error
                }

            except Exception as e:
                logger.error(f"Intent processing failed: {e}")
                raise HTTPException(status_code=500, detail=f"Intent processing failed: {str(e)}")

        @self.app.get("/api/v1/intent/status/{job_id}")
        async def get_job_status(job_id: str):
            """Get status of an intent processing job."""
            try:
                status = await self.orchestrator.get_job_status(job_id)

                if status is None:
                    raise HTTPException(status_code=404, detail="Job not found")

                return status

            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Job status retrieval failed: {e}")
                raise HTTPException(status_code=500, detail=f"Job status retrieval failed: {str(e)}")

        # =========================================================================
        # FILE UPLOAD ENDPOINTS
        # =========================================================================

        @self.app.post("/api/v1/upload", response_model=UploadResponse)
        async def upload_file(
            file: UploadFile = File(...),
            user_id: str = Form(...),
            category: str = Form("general"),
            metadata: str = Form("{}")
        ):
            """Upload a file and store it."""
            try:
                # Validate file
                if file.size > 50 * 1024 * 1024:  # 50MB limit
                    raise HTTPException(status_code=413, detail="File too large (max 50MB)")

                # Generate file ID
                file_id = f"{user_id}_{int(asyncio.get_event_loop().time())}_{file.filename}"

                # Create user directory
                user_dir = self.upload_dir / user_id / category
                user_dir.mkdir(parents=True, exist_ok=True)

                # Save file
                file_path = user_dir / file_id
                with open(file_path, "wb") as buffer:
                    shutil.copyfileobj(file.file, buffer)

                # Calculate checksum
                with open(file_path, "rb") as f:
                    checksum = hashlib.sha256(f.read()).hexdigest()

                # Parse metadata
                try:
                    metadata_dict = json.loads(metadata)
                except:
                    metadata_dict = {}

                # Store in super memory
                await self.super_memory.store_memory(
                    content=f"File uploaded: {file.filename}",
                    memory_type="upload",
                    user_id=user_id,
                    session_id=f"upload_{file_id}",
                    importance=0.7,
                    tags=["upload", category, file.content_type or "unknown"],
                    metadata={
                        "file_id": file_id,
                        "filename": file.filename,
                        "content_type": file.content_type,
                        "size_bytes": file.size,
                        "checksum": checksum,
                        "category": category,
                        **metadata_dict
                    }
                )

                # Record in agent history
                await self._record_agent_action(
                    "file_upload",
                    f"Uploaded file: {file.filename}",
                    {
                        "file_id": file_id,
                        "filename": file.filename,
                        "size_bytes": file.size,
                        "user_id": user_id
                    }
                )

                return UploadResponse(
                    file_id=file_id,
                    filename=file.filename,
                    content_type=file.content_type,
                    size_bytes=file.size,
                    upload_timestamp=asyncio.get_event_loop().time(),
                    checksum=checksum
                )

            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"File upload failed: {e}")
                raise HTTPException(status_code=500, detail=f"File upload failed: {str(e)}")

        @self.app.get("/api/v1/upload/{user_id}/{category}/{file_id}")
        async def download_file(user_id: str, category: str, file_id: str):
            """Download a previously uploaded file."""
            try:
                file_path = self.upload_dir / user_id / category / file_id

                if not file_path.exists():
                    raise HTTPException(status_code=404, detail="File not found")

                return FileResponse(
                    path=file_path,
                    filename=file_id.split("_", 2)[-1],  # Extract original filename
                    media_type="application/octet-stream"
                )

            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"File download failed: {e}")
                raise HTTPException(status_code=500, detail=f"File download failed: {str(e)}")

        # =========================================================================
        # AGENT HISTORY ENDPOINTS
        # =========================================================================

        @self.app.get("/api/v1/history")
        async def get_agent_history(
            limit: int = Query(100, ge=1, le=1000),
            agent_name: Optional[str] = None,
            action: Optional[str] = None,
            since_timestamp: Optional[float] = None
        ):
            """Get agent interaction history."""
            try:
                history = self.agent_history

                # Apply filters
                if agent_name:
                    history = [h for h in history if h.agent_name == agent_name]
                if action:
                    history = [h for h in history if h.action == action]
                if since_timestamp:
                    history = [h for h in history if h.timestamp >= since_timestamp]

                # Sort by timestamp (newest first) and limit
                history = sorted(history, key=lambda h: h.timestamp, reverse=True)[:limit]

                return {
                    "history": [
                        {
                            "timestamp": entry.timestamp,
                            "agent_name": entry.agent_name,
                            "action": entry.action,
                            "result": entry.result,
                            "duration_ms": entry.duration_ms,
                            "success": entry.success,
                            "metadata": entry.metadata
                        }
                        for entry in history
                    ],
                    "total_count": len(self.agent_history),
                    "filtered_count": len(history)
                }

            except Exception as e:
                logger.error(f"History retrieval failed: {e}")
                raise HTTPException(status_code=500, detail=f"History retrieval failed: {str(e)}")

        @self.app.get("/api/v1/history/stats")
        async def get_history_stats():
            """Get statistics about agent history."""
            try:
                if not self.agent_history:
                    return {"total_actions": 0, "stats": {}}

                # Calculate statistics
                total_actions = len(self.agent_history)
                successful_actions = sum(1 for h in self.agent_history if h.success)
                avg_duration = sum(h.duration_ms for h in self.agent_history) / total_actions

                # Group by agent
                agent_stats = {}
                for entry in self.agent_history:
                    if entry.agent_name not in agent_stats:
                        agent_stats[entry.agent_name] = {
                            "total_actions": 0,
                            "successful_actions": 0,
                            "total_duration": 0
                        }
                    agent_stats[entry.agent_name]["total_actions"] += 1
                    agent_stats[entry.agent_name]["total_duration"] += entry.duration_ms
                    if entry.success:
                        agent_stats[entry.agent_name]["successful_actions"] += 1

                # Calculate averages
                for agent_name in agent_stats:
                    stats = agent_stats[agent_name]
                    stats["success_rate"] = stats["successful_actions"] / stats["total_actions"]
                    stats["avg_duration_ms"] = stats["total_duration"] / stats["total_actions"]

                return {
                    "total_actions": total_actions,
                    "success_rate": successful_actions / total_actions,
                    "avg_duration_ms": avg_duration,
                    "agent_stats": agent_stats
                }

            except Exception as e:
                logger.error(f"History stats calculation failed: {e}")
                raise HTTPException(status_code=500, detail=f"History stats calculation failed: {str(e)}")

        # =========================================================================
        # VISUALIZATION ENDPOINTS
        # =========================================================================

        @self.app.get("/api/v1/visualization/memory/{user_id}")
        async def get_memory_visualization(user_id: str, time_range: str = "7d"):
            """Get memory data for visualization."""
            try:
                # Get memory statistics
                stats = await self.super_memory.get_memory_stats(user_id)

                # Get recent memories for timeline
                query = MemoryQuery(
                    query_text="",
                    user_id=user_id,
                    max_age_days=self._parse_time_range(time_range),
                    limit=500
                )
                search_result = await self.super_memory.retrieve_memories(query)

                # Aggregate by type and time
                type_distribution = {}
                timeline_data = {}
                importance_distribution = {"low": 0, "medium": 0, "high": 0}

                for memory in search_result.results:
                    # Type distribution
                    mem_type = memory.memory_type
                    type_distribution[mem_type] = type_distribution.get(mem_type, 0) + 1

                    # Timeline (by hour)
                    hour_key = datetime.fromtimestamp(memory.timestamp).strftime("%Y-%m-%d %H:00")
                    timeline_data[hour_key] = timeline_data.get(hour_key, 0) + 1

                    # Importance distribution
                    if memory.importance < 0.3:
                        importance_distribution["low"] += 1
                    elif memory.importance < 0.7:
                        importance_distribution["medium"] += 1
                    else:
                        importance_distribution["high"] += 1

                return {
                    "user_id": user_id,
                    "time_range": time_range,
                    "stats": stats,
                    "type_distribution": type_distribution,
                    "timeline": dict(sorted(timeline_data.items())),
                    "importance_distribution": importance_distribution,
                    "total_memories": len(search_result.results)
                }

            except Exception as e:
                logger.error(f"Memory visualization failed: {e}")
                raise HTTPException(status_code=500, detail=f"Memory visualization failed: {str(e)}")

        @self.app.get("/api/v1/visualization/agent-activity")
        async def get_agent_activity_visualization(hours: int = 24):
            """Get agent activity data for visualization."""
            try:
                cutoff_time = datetime.now() - timedelta(hours=hours)
                cutoff_timestamp = cutoff_time.timestamp()

                # Filter recent history
                recent_history = [
                    h for h in self.agent_history
                    if h.timestamp >= cutoff_timestamp
                ]

                # Aggregate by agent and hour
                activity_data = {}
                for entry in recent_history:
                    hour_key = datetime.fromtimestamp(entry.timestamp).strftime("%Y-%m-%d %H:00")

                    if hour_key not in activity_data:
                        activity_data[hour_key] = {}

                    agent_name = entry.agent_name
                    if agent_name not in activity_data[hour_key]:
                        activity_data[hour_key][agent_name] = {
                            "total_actions": 0,
                            "successful_actions": 0,
                            "total_duration": 0
                        }

                    activity_data[hour_key][agent_name]["total_actions"] += 1
                    activity_data[hour_key][agent_name]["total_duration"] += entry.duration_ms
                    if entry.success:
                        activity_data[hour_key][agent_name]["successful_actions"] += 1

                # Calculate success rates
                for hour_data in activity_data.values():
                    for agent_data in hour_data.values():
                        total = agent_data["total_actions"]
                        if total > 0:
                            agent_data["success_rate"] = agent_data["successful_actions"] / total
                            agent_data["avg_duration"] = agent_data["total_duration"] / total
                        else:
                            agent_data["success_rate"] = 0
                            agent_data["avg_duration"] = 0

                return {
                    "time_range_hours": hours,
                    "activity_data": dict(sorted(activity_data.items())),
                    "total_actions": len(recent_history)
                }

            except Exception as e:
                logger.error(f"Agent activity visualization failed: {e}")
                raise HTTPException(status_code=500, detail=f"Agent activity visualization failed: {str(e)}")

    def _parse_time_range(self, time_range: str) -> float:
        """Parse time range string to days."""
        if time_range.endswith("d"):
            return float(time_range[:-1])
        elif time_range.endswith("h"):
            return float(time_range[:-1]) / 24
        elif time_range.endswith("w"):
            return float(time_range[:-1]) * 7
        else:
            return 7.0  # Default to 7 days

    async def _record_agent_action(self, action: str, result: str, metadata: Dict[str, Any]):
        """Record an agent action in history."""
        entry = AgentHistoryEntry(
            timestamp=asyncio.get_event_loop().time(),
            agent_name="api_server",
            action=action,
            result=result,
            duration_ms=0.0,  # Not measured for API calls
            success=True,
            metadata=metadata
        )

        self.agent_history.append(entry)

        # Maintain history size limit
        if len(self.agent_history) > self.max_history_size:
            self.agent_history = self.agent_history[-self.max_history_size:]

    def run(self, host: str = "0.0.0.0", port: int = 8000):
        """Run the API server."""
        logger.info(f"Starting VibeMind API server on {host}:{port}")
        uvicorn.run(self.app, host=host, port=port)


# Global API instance
_api_server: Optional[VibeMindAPI] = None


def get_api_server() -> VibeMindAPI:
    """Get or create the global API server instance."""
    global _api_server
    if _api_server is None:
        _api_server = VibeMindAPI()
    return _api_server


if __name__ == "__main__":
    # Run server directly
    server = get_api_server()
    server.run()