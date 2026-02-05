"""
System Status Tools - Query system state and active operations.

These tools allow users to ask about what the system is currently doing,
check for stuck operations, and get performance insights.
"""

import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


def get_system_status(params: Dict[str, Any] = None) -> str:
    """
    Get current system status including active operations.

    Voice triggers:
    - "Was läuft gerade?"
    - "System status"
    - "Was macht das System?"

    Returns:
        Human-readable status string
    """
    try:
        from swarm.monitoring.system_status import get_status_monitor
        monitor = get_status_monitor()
        status = monitor.get_status()

        lines = []
        lines.append(f"System läuft seit {status['uptime_s']:.0f} Sekunden.")
        lines.append(f"Gesamt: {status['total_operations']} Operationen, {status['total_errors']} Fehler.")

        if status['active_operations']:
            lines.append(f"\nAktiv ({status['active_count']}):")
            for op in status['active_operations']:
                lines.append(f"  [{op['elapsed_s']:.1f}s] {op['type']}: {op['description'][:40]}")
        else:
            lines.append("Keine aktiven Operationen.")

        return "\n".join(lines)

    except ImportError:
        return "Status-Monitor nicht verfuegbar."
    except Exception as e:
        logger.error(f"get_system_status failed: {e}")
        return f"Fehler beim Abrufen des Status: {str(e)}"


def check_stuck_operations(params: Dict[str, Any] = None) -> str:
    """
    Check for operations that are taking too long.

    Voice triggers:
    - "Gibt es hängende Operationen?"
    - "Was hängt?"
    - "Check stuck"

    Returns:
        List of stuck operations or confirmation that all is well
    """
    try:
        from swarm.monitoring.system_status import get_status_monitor
        monitor = get_status_monitor()

        threshold = (params or {}).get("threshold_seconds", 15.0)
        stuck = monitor.check_stuck_operations(threshold)

        if stuck:
            lines = [f"{len(stuck)} möglicherweise hängende Operationen (>{threshold}s):"]
            for op in stuck:
                lines.append(f"  [{op['elapsed_s']:.0f}s] {op['type']}: {op['description'][:40]}")
            return "\n".join(lines)
        else:
            return f"Alle Operationen laufen normal (keine länger als {threshold}s)."

    except ImportError:
        return "Status-Monitor nicht verfuegbar."
    except Exception as e:
        logger.error(f"check_stuck_operations failed: {e}")
        return f"Fehler: {str(e)}"


def print_status_summary(params: Dict[str, Any] = None) -> str:
    """
    Print detailed status summary to terminal (for debugging).

    Returns:
        Confirmation message
    """
    try:
        from swarm.monitoring.system_status import get_status_monitor
        monitor = get_status_monitor()
        monitor.print_status_summary()
        return "Status-Zusammenfassung wurde in der Konsole ausgegeben."
    except ImportError:
        return "Status-Monitor nicht verfuegbar."
    except Exception as e:
        logger.error(f"print_status_summary failed: {e}")
        return f"Fehler: {str(e)}"


# Tool definitions for registration
SYSTEM_STATUS_TOOLS = {
    "system.status": get_system_status,
    "system.check_stuck": check_stuck_operations,
    "system.print_summary": print_status_summary,
}


__all__ = [
    "get_system_status",
    "check_stuck_operations",
    "print_status_summary",
    "SYSTEM_STATUS_TOOLS",
]
