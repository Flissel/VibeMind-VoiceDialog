"""
Health Check HTTP Server
Exposes health endpoints for monitoring and load balancers
"""

import sys
import json
import time
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
from typing import Optional, Dict, Callable
from datetime import datetime

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent))

from logger import get_logger

logger = get_logger(__name__)


class HealthStatus:
    """Health status response codes"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class HealthCheckHandler(BaseHTTPRequestHandler):
    """HTTP handler for health check endpoints"""

    # Class variables set by HealthServer
    health_provider: Optional[Callable] = None
    start_time: float = time.time()

    def log_message(self, format, *args):
        """Override to use structured logging"""
        logger.debug(f"{self.address_string()} - {format % args}")

    def _set_response(self, status_code: int, content_type: str = "application/json"):
        """Set HTTP response headers"""
        self.send_response(status_code)
        self.send_header('Content-type', content_type)
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        self.end_headers()

    def _send_json(self, data: dict, status_code: int = 200):
        """Send JSON response"""
        self._set_response(status_code)
        self.wfile.write(json.dumps(data, indent=2).encode('utf-8'))

    def _get_uptime(self) -> float:
        """Get service uptime in seconds"""
        return time.time() - self.start_time

    def do_GET(self):
        """Handle GET requests"""
        try:
            if self.path == '/health':
                self._handle_health()
            elif self.path == '/health/ready':
                self._handle_ready()
            elif self.path == '/health/live':
                self._handle_live()
            elif self.path == '/metrics':
                self._handle_metrics()
            else:
                self._handle_404()
        except Exception as e:
            logger.error(f"Error handling request {self.path}: {e}", exc_info=True)
            self._send_json({
                'status': HealthStatus.UNHEALTHY,
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat() + 'Z'
            }, 500)

    def _handle_health(self):
        """
        Basic health check endpoint
        Returns 200 if service is running, 503 if unhealthy
        """
        if not HealthCheckHandler.health_provider:
            self._send_json({
                'status': HealthStatus.HEALTHY,
                'message': 'Health provider not configured',
                'timestamp': datetime.utcnow().isoformat() + 'Z',
                'uptime_seconds': round(self._get_uptime(), 2)
            })
            return

        health_data = HealthCheckHandler.health_provider()

        # Determine overall health
        if health_data.get('overall_status') == HealthStatus.HEALTHY:
            status_code = 200
        elif health_data.get('overall_status') == HealthStatus.DEGRADED:
            status_code = 200  # Still operational, just degraded
        else:
            status_code = 503  # Unhealthy

        response = {
            'status': health_data.get('overall_status', HealthStatus.UNHEALTHY),
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'uptime_seconds': round(self._get_uptime(), 2),
            'version': health_data.get('version', 'unknown'),
            'checks': health_data.get('checks', {})
        }

        self._send_json(response, status_code)

    def _handle_ready(self):
        """
        Readiness check endpoint
        Returns 200 if service is ready to accept requests, 503 if not ready
        Used by load balancers to determine if traffic should be routed
        """
        if not HealthCheckHandler.health_provider:
            self._send_json({
                'status': HealthStatus.HEALTHY,
                'message': 'Health provider not configured',
                'ready': True,
                'timestamp': datetime.utcnow().isoformat() + 'Z'
            })
            return

        health_data = HealthCheckHandler.health_provider()
        checks = health_data.get('checks', {})

        # Service is ready if MoireTracker is connected and responding
        moire_connected = checks.get('moire_tracker', {}).get('connected', False)
        client_connected = checks.get('moire_client', {}).get('connected', False)
        circuit_open = checks.get('moire_client', {}).get('circuit_state') == 'open'

        ready = moire_connected and client_connected and not circuit_open

        status_code = 200 if ready else 503

        response = {
            'status': HealthStatus.HEALTHY if ready else HealthStatus.UNHEALTHY,
            'ready': ready,
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'checks': {
                'moire_tracker_connected': moire_connected,
                'moire_client_connected': client_connected,
                'circuit_breaker_closed': not circuit_open
            }
        }

        self._send_json(response, status_code)

    def _handle_live(self):
        """
        Liveness check endpoint
        Returns 200 if service is alive (process running), 503 if dead
        Used by orchestrators (Kubernetes) to determine if container should be restarted
        """
        # If we can respond, we're alive
        response = {
            'status': HealthStatus.HEALTHY,
            'alive': True,
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'uptime_seconds': round(self._get_uptime(), 2)
        }

        self._send_json(response, 200)

    def _handle_metrics(self):
        """
        Metrics endpoint (Prometheus-style)
        Returns detailed metrics for monitoring systems
        """
        if not HealthCheckHandler.health_provider:
            self._send_json({
                'message': 'Health provider not configured',
                'timestamp': datetime.utcnow().isoformat() + 'Z'
            })
            return

        health_data = HealthCheckHandler.health_provider()

        response = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'uptime_seconds': round(self._get_uptime(), 2),
            'version': health_data.get('version', 'unknown'),
            'metrics': health_data.get('metrics', {})
        }

        self._send_json(response)

    def _handle_404(self):
        """Handle 404 Not Found"""
        response = {
            'error': 'Not Found',
            'message': f'Path {self.path} not found',
            'available_endpoints': [
                '/health',
                '/health/ready',
                '/health/live',
                '/metrics'
            ],
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        }
        self._send_json(response, 404)


class HealthServer:
    """
    HTTP server for health check endpoints

    Endpoints:
    - GET /health       - Overall health status
    - GET /health/ready - Readiness check (ready to accept traffic)
    - GET /health/live  - Liveness check (process is alive)
    - GET /metrics      - Detailed metrics

    Usage:
        server = HealthServer(port=8080)
        server.set_health_provider(lambda: get_system_health())
        server.start()
        # ... application runs ...
        server.stop()
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 8080):
        """
        Initialize health server

        Args:
            host: Host to bind to (default: localhost only for security)
            port: Port to listen on (default: 8080)
        """
        self.host = host
        self.port = port
        self.server: Optional[HTTPServer] = None
        self.thread: Optional[Thread] = None
        self.running = False
        self.health_provider: Optional[Callable] = None

        logger.info(f"HealthServer initialized on {host}:{port}")

    def set_health_provider(self, provider: Callable[[], Dict]):
        """
        Set health data provider function

        Args:
            provider: Function that returns health data dict
        """
        self.health_provider = provider
        HealthCheckHandler.health_provider = provider
        logger.info("Health provider configured")

    def start(self):
        """Start health server in background thread"""
        if self.running:
            logger.warning("HealthServer already running")
            return

        try:
            # Create HTTP server
            HealthCheckHandler.start_time = time.time()
            self.server = HTTPServer((self.host, self.port), HealthCheckHandler)

            # Start server in background thread
            self.thread = Thread(target=self._run_server, daemon=True)
            self.thread.start()

            self.running = True
            logger.info(f"HealthServer started on http://{self.host}:{self.port}")
            logger.info(f"  - Health check: http://{self.host}:{self.port}/health")
            logger.info(f"  - Readiness:    http://{self.host}:{self.port}/health/ready")
            logger.info(f"  - Liveness:     http://{self.host}:{self.port}/health/live")
            logger.info(f"  - Metrics:      http://{self.host}:{self.port}/metrics")

        except Exception as e:
            logger.error(f"Failed to start HealthServer: {e}", exc_info=True)
            self.running = False
            raise

    def _run_server(self):
        """Run server loop (called in background thread)"""
        try:
            logger.debug("HealthServer thread started")
            self.server.serve_forever()
        except Exception as e:
            if self.running:  # Only log if not intentionally stopped
                logger.error(f"HealthServer error: {e}", exc_info=True)

    def stop(self):
        """Stop health server"""
        if not self.running:
            logger.debug("HealthServer not running")
            return

        logger.info("Stopping HealthServer...")
        self.running = False

        if self.server:
            self.server.shutdown()
            self.server.server_close()

        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2.0)

        logger.info("HealthServer stopped")

    def is_running(self) -> bool:
        """Check if server is running"""
        return self.running

    def get_url(self, endpoint: str = "/health") -> str:
        """Get full URL for endpoint"""
        return f"http://{self.host}:{self.port}{endpoint}"


def create_health_server(host: str = "127.0.0.1", port: int = 8080) -> HealthServer:
    """
    Convenience function to create health server

    Args:
        host: Host to bind to
        port: Port to listen on

    Returns:
        HealthServer instance
    """
    return HealthServer(host, port)


# Example health provider function
def example_health_provider() -> Dict:
    """
    Example health provider implementation

    Real implementation should check:
    - MoireTracker connection status
    - MoireClient health metrics
    - Database connections
    - External API availability
    """
    return {
        'overall_status': HealthStatus.HEALTHY,
        'version': '1.0.0',
        'checks': {
            'moire_tracker': {
                'connected': True,
                'process_managed': False,
                'exe_exists': True
            },
            'moire_client': {
                'connected': True,
                'circuit_state': 'closed',
                'error_rate_percent': 0.0
            }
        },
        'metrics': {
            'total_requests': 100,
            'failed_requests': 0,
            'uptime_seconds': 3600
        }
    }


if __name__ == "__main__":
    # Simple test of health server
    import sys

    logger.info("Starting health server test...")

    server = HealthServer(port=8080)
    server.set_health_provider(example_health_provider)

    try:
        server.start()
        logger.info("Health server running. Press Ctrl+C to stop.")
        logger.info(f"Try: curl http://127.0.0.1:8080/health")

        # Keep main thread alive
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
    finally:
        server.stop()
        logger.info("Test complete")
