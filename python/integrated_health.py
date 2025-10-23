"""
Integrated Health Provider
Aggregates health status from all system components
"""

import sys
from pathlib import Path
from typing import Dict, Optional

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent))

from tools.moire_service import MoireTrackerService
from tools.moire_client import MoireTrackerClient
from health_server import HealthStatus
from logger import get_logger

logger = get_logger(__name__)


class IntegratedHealthProvider:
    """
    Provides health status by aggregating all system components

    Usage:
        provider = IntegratedHealthProvider(service, client)
        health_data = provider.get_health()
    """

    def __init__(self,
                 service: Optional[MoireTrackerService] = None,
                 client: Optional[MoireTrackerClient] = None,
                 version: str = "1.0.0"):
        """
        Initialize health provider

        Args:
            service: Moire Tracker Service instance
            client: Moire Tracker Client instance
            version: Application version
        """
        self.service = service
        self.client = client
        self.version = version

        logger.info(f"IntegratedHealthProvider initialized (version={version})")

    def set_service(self, service: MoireTrackerService):
        """Set or update service instance"""
        self.service = service
        logger.debug("Service instance updated")

    def set_client(self, client: MoireTrackerClient):
        """Set or update client instance"""
        self.client = client
        logger.debug("Client instance updated")

    def get_health(self) -> Dict:
        """
        Get comprehensive health status

        Returns:
            Dict with overall_status, version, checks, and metrics
        """
        logger.debug("Gathering health status...")

        # Collect component health
        service_health = self._get_service_health()
        client_health = self._get_client_health()

        # Determine overall status
        overall_status = self._determine_overall_status(service_health, client_health)

        # Aggregate metrics
        metrics = self._aggregate_metrics(service_health, client_health)

        health_data = {
            'overall_status': overall_status,
            'version': self.version,
            'checks': {
                'moire_tracker': service_health,
                'moire_client': client_health
            },
            'metrics': metrics
        }

        logger.debug(f"Health status: {overall_status}")
        return health_data

    def _get_service_health(self) -> Dict:
        """Get MoireTracker service health"""
        if not self.service:
            return {
                'available': False,
                'message': 'Service not configured'
            }

        try:
            status = self.service.get_health_status()
            return {
                'available': True,
                'running': status.get('running', False),
                'process_managed': status.get('process_managed', False),
                'exe_exists': status.get('exe_exists', False),
                'start_attempts': status.get('start_attempts', 0),
                'connected': status.get('running', False)  # For readiness check
            }
        except Exception as e:
            logger.error(f"Failed to get service health: {e}")
            return {
                'available': False,
                'error': str(e)
            }

    def _get_client_health(self) -> Dict:
        """Get MoireTracker client health"""
        if not self.client:
            return {
                'available': False,
                'message': 'Client not configured'
            }

        try:
            metrics = self.client.get_health_metrics()
            return {
                'available': True,
                'connected': metrics.get('connected', False),
                'circuit_state': metrics.get('circuit_state', 'unknown'),
                'total_requests': metrics.get('total_requests', 0),
                'failed_requests': metrics.get('failed_requests', 0),
                'error_rate_percent': metrics.get('error_rate_percent', 0),
                'total_reconnects': metrics.get('total_reconnects', 0)
            }
        except Exception as e:
            logger.error(f"Failed to get client health: {e}")
            return {
                'available': False,
                'error': str(e)
            }

    def _determine_overall_status(self,
                                  service_health: Dict,
                                  client_health: Dict) -> str:
        """
        Determine overall health status based on components

        Rules:
        - HEALTHY: All components operational
        - DEGRADED: Some components have issues but system functional
        - UNHEALTHY: Critical components unavailable
        """
        # Check if critical components are available
        service_available = service_health.get('available', False)
        client_available = client_health.get('available', False)

        if not service_available and not client_available:
            return HealthStatus.UNHEALTHY

        # Check if service is running
        service_running = service_health.get('running', False)

        # Check if client is connected and circuit is closed
        client_connected = client_health.get('connected', False)
        circuit_open = client_health.get('circuit_state') == 'open'

        # UNHEALTHY: Service not running or circuit breaker open
        if not service_running or circuit_open:
            return HealthStatus.UNHEALTHY

        # DEGRADED: High error rate
        error_rate = client_health.get('error_rate_percent', 0)
        if error_rate > 10:
            return HealthStatus.DEGRADED

        # HEALTHY: All checks passed
        if service_running and client_connected:
            return HealthStatus.HEALTHY

        # Default to degraded if uncertain
        return HealthStatus.DEGRADED

    def _aggregate_metrics(self,
                          service_health: Dict,
                          client_health: Dict) -> Dict:
        """Aggregate metrics from all components"""
        return {
            'service_start_attempts': service_health.get('start_attempts', 0),
            'client_total_requests': client_health.get('total_requests', 0),
            'client_failed_requests': client_health.get('failed_requests', 0),
            'client_error_rate_percent': client_health.get('error_rate_percent', 0),
            'client_reconnects': client_health.get('total_reconnects', 0)
        }


def create_health_provider(service: Optional[MoireTrackerService] = None,
                          client: Optional[MoireTrackerClient] = None,
                          version: str = "1.0.0") -> IntegratedHealthProvider:
    """
    Convenience function to create integrated health provider

    Args:
        service: MoireTracker service instance
        client: MoireTracker client instance
        version: Application version

    Returns:
        IntegratedHealthProvider instance
    """
    return IntegratedHealthProvider(service, client, version)


if __name__ == "__main__":
    # Simple test
    print("Testing IntegratedHealthProvider...")

    provider = IntegratedHealthProvider(version="1.0.0-test")
    health = provider.get_health()

    print("\n[Health Status]")
    print(f"  Overall: {health['overall_status']}")
    print(f"  Version: {health['version']}")
    print(f"  Checks: {len(health['checks'])} components")
    print(f"  Metrics: {len(health['metrics'])} values")

    print("\n[Component Status]")
    for component, status in health['checks'].items():
        available = status.get('available', False)
        print(f"  - {component}: {'Available' if available else 'Not configured'}")

    print("\n[Test Complete]")
