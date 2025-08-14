#!/usr/bin/env python3
"""
Dashboard API Endpoints

WebSocket streaming and REST endpoints for the Veris Memory dashboard system.
Provides both JSON and ASCII formatted output for different client types.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional, Set
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware

from .dashboard import UnifiedDashboard
from .streaming import MetricsStreamer

logger = logging.getLogger(__name__)


class DashboardAPI:
    """
    API endpoints for the unified dashboard system.
    
    Provides WebSocket streaming for real-time updates and REST endpoints
    for on-demand dashboard data in both JSON and ASCII formats.
    """

    def __init__(self, app: FastAPI, config: Optional[Dict[str, Any]] = None):
        """Initialize dashboard API with FastAPI app."""
        self.app = app
        self.config = config or self._get_default_config()
        self.dashboard = UnifiedDashboard(self.config.get('dashboard', {}))
        self.streamer = MetricsStreamer(self.dashboard, self.config.get('streaming', {}))
        
        # WebSocket connections
        self.websocket_connections: Set[WebSocket] = set()
        
        # Setup routes
        self._setup_routes()
        self._setup_middleware()
        
        logger.info("📊 DashboardAPI initialized")

    def _get_default_config(self) -> Dict[str, Any]:
        """Get default API configuration."""
        return {
            'streaming': {
                'update_interval_seconds': 5,
                'max_connections': 100,
                'heartbeat_interval_seconds': 30
            },
            'cors': {
                'allow_origins': ["*"],
                'allow_methods': ["*"],
                'allow_headers': ["*"]
            },
            'rate_limiting': {
                'enabled': True,
                'requests_per_minute': 60
            }
        }

    def _setup_middleware(self):
        """Setup FastAPI middleware."""
        # CORS middleware for cross-origin requests
        cors_config = self.config.get('cors', {})
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_config.get('allow_origins', ["*"]),
            allow_credentials=True,
            allow_methods=cors_config.get('allow_methods', ["*"]),
            allow_headers=cors_config.get('allow_headers', ["*"])
        )

    def _setup_routes(self):
        """Setup API routes."""
        
        @self.app.websocket("/ws/dashboard")
        async def websocket_dashboard(websocket: WebSocket):
            """WebSocket endpoint for real-time dashboard streaming."""
            await self._handle_websocket_connection(websocket)

        @self.app.get("/api/dashboard")
        async def get_dashboard_json():
            """Get complete dashboard data in JSON format."""
            return await self._get_dashboard_json()

        @self.app.get("/api/dashboard/ascii", response_class=PlainTextResponse)
        async def get_dashboard_ascii():
            """Get dashboard in ASCII format for human reading."""
            return await self._get_dashboard_ascii()

        @self.app.get("/api/dashboard/system")
        async def get_system_metrics():
            """Get system metrics only."""
            return await self._get_system_metrics()

        @self.app.get("/api/dashboard/services")
        async def get_service_metrics():
            """Get service health metrics only."""
            return await self._get_service_metrics()

        @self.app.get("/api/dashboard/security")
        async def get_security_metrics():
            """Get security metrics only."""
            return await self._get_security_metrics()


        @self.app.post("/api/dashboard/refresh")
        async def refresh_dashboard():
            """Force refresh of dashboard metrics."""
            return await self._force_refresh_dashboard()

        @self.app.get("/api/dashboard/health")
        async def dashboard_health():
            """Dashboard API health check."""
            return await self._get_api_health()

        @self.app.get("/api/dashboard/connections")
        async def get_websocket_connections():
            """Get active WebSocket connection count."""
            return {"active_connections": len(self.websocket_connections)}

    async def _handle_websocket_connection(self, websocket: WebSocket):
        """Handle WebSocket connection for real-time dashboard updates."""
        try:
            await websocket.accept()
            self.websocket_connections.add(websocket)
            
            connection_count = len(self.websocket_connections)
            max_connections = self.config['streaming']['max_connections']
            
            logger.info(f"📡 WebSocket connected ({connection_count}/{max_connections})")
            
            if connection_count > max_connections:
                await websocket.close(code=1008, reason="Max connections exceeded")
                return

            # Send initial dashboard data
            metrics = await self.dashboard.collect_all_metrics(force_refresh=True)
            await websocket.send_json({
                "type": "initial_data",
                "timestamp": datetime.utcnow().isoformat(),
                "data": metrics
            })

            # Start streaming updates
            await self._stream_dashboard_updates(websocket)

        except WebSocketDisconnect:
            logger.info("📡 WebSocket disconnected")
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
            await websocket.close(code=1011, reason="Internal error")
        finally:
            self.websocket_connections.discard(websocket)

    async def _stream_dashboard_updates(self, websocket: WebSocket):
        """Stream dashboard updates to WebSocket client."""
        update_interval = self.config['streaming']['update_interval_seconds']
        heartbeat_interval = self.config['streaming']['heartbeat_interval_seconds']
        
        last_heartbeat = datetime.utcnow()
        
        try:
            while True:
                # Collect current metrics
                metrics = await self.dashboard.collect_all_metrics()
                
                # Send update
                update_message = {
                    "type": "dashboard_update",
                    "timestamp": datetime.utcnow().isoformat(),
                    "data": metrics
                }
                
                await websocket.send_json(update_message)
                
                # Send heartbeat if needed
                now = datetime.utcnow()
                if (now - last_heartbeat).total_seconds() >= heartbeat_interval:
                    await websocket.send_json({
                        "type": "heartbeat",
                        "timestamp": now.isoformat()
                    })
                    last_heartbeat = now
                
                # Wait for next update
                await asyncio.sleep(update_interval)
                
        except WebSocketDisconnect:
            logger.info("📡 WebSocket client disconnected during streaming")
        except Exception as e:
            logger.error(f"Streaming error: {e}")

    async def _get_dashboard_json(self) -> Dict[str, Any]:
        """Get complete dashboard data in JSON format."""
        try:
            metrics = await self.dashboard.collect_all_metrics()
            return {
                "success": True,
                "format": "json",
                "timestamp": datetime.utcnow().isoformat(),
                "data": metrics
            }
        except Exception as e:
            logger.error(f"Failed to get dashboard JSON: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    async def _get_dashboard_ascii(self) -> str:
        """Get dashboard in ASCII format."""
        try:
            metrics = await self.dashboard.collect_all_metrics()
            ascii_output = self.dashboard.generate_ascii_dashboard(metrics)
            return ascii_output
        except Exception as e:
            logger.error(f"Failed to get dashboard ASCII: {e}")
            return f"Dashboard Error: {str(e)}"

    async def _get_system_metrics(self) -> Dict[str, Any]:
        """Get system metrics only."""
        try:
            metrics = await self.dashboard.collect_all_metrics()
            return {
                "success": True,
                "type": "system_metrics",
                "timestamp": datetime.utcnow().isoformat(),
                "data": metrics.get("system", {})
            }
        except Exception as e:
            logger.error(f"Failed to get system metrics: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    async def _get_service_metrics(self) -> Dict[str, Any]:
        """Get service health metrics only."""
        try:
            metrics = await self.dashboard.collect_all_metrics()
            return {
                "success": True,
                "type": "service_metrics",
                "timestamp": datetime.utcnow().isoformat(),
                "data": metrics.get("services", [])
            }
        except Exception as e:
            logger.error(f"Failed to get service metrics: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    async def _get_security_metrics(self) -> Dict[str, Any]:
        """Get security metrics only."""
        try:
            metrics = await self.dashboard.collect_all_metrics()
            return {
                "success": True,
                "type": "security_metrics",
                "timestamp": datetime.utcnow().isoformat(),
                "data": metrics.get("security", {})
            }
        except Exception as e:
            logger.error(f"Failed to get security metrics: {e}")
            raise HTTPException(status_code=500, detail=str(e))


    async def _force_refresh_dashboard(self) -> Dict[str, Any]:
        """Force refresh of dashboard metrics."""
        try:
            metrics = await self.dashboard.collect_all_metrics(force_refresh=True)
            
            # Broadcast update to all WebSocket connections
            await self._broadcast_to_websockets({
                "type": "force_refresh",
                "timestamp": datetime.utcnow().isoformat(),
                "data": metrics
            })
            
            return {
                "success": True,
                "message": "Dashboard metrics refreshed",
                "timestamp": datetime.utcnow().isoformat(),
                "websocket_notifications_sent": len(self.websocket_connections)
            }
        except Exception as e:
            logger.error(f"Failed to refresh dashboard: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    async def _get_api_health(self) -> Dict[str, Any]:
        """Get dashboard API health status."""
        try:
            # Check dashboard health
            dashboard_healthy = self.dashboard.last_update is not None
            
            # Check WebSocket health
            websocket_healthy = len(self.websocket_connections) <= self.config['streaming']['max_connections']
            
            # Overall health
            overall_healthy = dashboard_healthy and websocket_healthy
            
            return {
                "success": True,
                "healthy": overall_healthy,
                "timestamp": datetime.utcnow().isoformat(),
                "components": {
                    "dashboard": {
                        "healthy": dashboard_healthy,
                        "last_update": self.dashboard.last_update.isoformat() if self.dashboard.last_update else None
                    },
                    "websockets": {
                        "healthy": websocket_healthy,
                        "active_connections": len(self.websocket_connections),
                        "max_connections": self.config['streaming']['max_connections']
                    },
                    "streaming": {
                        "enabled": True,
                        "update_interval_seconds": self.config['streaming']['update_interval_seconds']
                    }
                }
            }
        except Exception as e:
            logger.error(f"Failed to get API health: {e}")
            return {
                "success": False,
                "healthy": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }

    async def _broadcast_to_websockets(self, message: Dict[str, Any]):
        """Broadcast message to all connected WebSocket clients."""
        if not self.websocket_connections:
            return
        
        # Create list of connections to avoid modification during iteration
        connections = list(self.websocket_connections)
        
        for websocket in connections:
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.warning(f"Failed to send WebSocket message: {e}")
                # Remove failed connection
                self.websocket_connections.discard(websocket)

    async def run_monitoring_updates_stream(self):
        """Stream monitoring updates to WebSocket clients."""
        try:
            # Collect current metrics
            metrics = await self.dashboard.collect_all_metrics(force_refresh=True)
            
            # Broadcast metrics to all connected clients
            await self._broadcast_to_websockets({
                "type": "monitoring_update",
                "timestamp": datetime.utcnow().isoformat(),
                "data": metrics
            })
            
            logger.info("✅ Monitoring update streamed to clients")
            
        except Exception as e:
            logger.error(f"Monitoring streaming failed: {e}")
            
            # Broadcast error
            await self._broadcast_to_websockets({
                "type": "monitoring_error",
                "timestamp": datetime.utcnow().isoformat(),
                "error": str(e)
            })

    async def shutdown(self):
        """Clean shutdown of dashboard API."""
        logger.info("📊 Shutting down DashboardAPI")
        
        # Close all WebSocket connections
        connections = list(self.websocket_connections)
        for websocket in connections:
            try:
                await websocket.close(code=1001, reason="Server shutdown")
            except Exception:
                pass
        
        self.websocket_connections.clear()
        
        # Shutdown dashboard
        await self.dashboard.shutdown()
        
        logger.info("✅ DashboardAPI shutdown complete")


# Utility function to integrate with existing FastAPI app
def setup_dashboard_api(app: FastAPI, config: Optional[Dict[str, Any]] = None) -> DashboardAPI:
    """
    Setup dashboard API with existing FastAPI application.
    
    Args:
        app: FastAPI application instance
        config: Optional configuration dictionary
        
    Returns:
        DashboardAPI instance
    """
    dashboard_api = DashboardAPI(app, config)
    
    # Add startup and shutdown events
    @app.on_event("startup")
    async def startup_dashboard():
        logger.info("🚀 Dashboard API startup complete")
    
    @app.on_event("shutdown")
    async def shutdown_dashboard():
        await dashboard_api.shutdown()
    
    return dashboard_api


# Export main components
__all__ = ["DashboardAPI", "setup_dashboard_api"]