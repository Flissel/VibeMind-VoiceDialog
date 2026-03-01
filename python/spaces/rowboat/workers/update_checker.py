"""
Rowboat Update Checker

Periodically checks GitHub for new Rowboat releases and notifies VibeMind
when an update is available. Similar to Rowboat's own update-electron-app
mechanism, but works with the git submodule model.

Architecture:
  Python daemon thread  ──check──→  GitHub API (releases/latest)
        ↓ (if newer)
  rowboat_update_available  ──→  Electron main.js  ──→  BrowserView + Tab badge
"""

import os
import json
import time
import logging
import subprocess
import urllib.request
import urllib.error
from typing import Optional, Callable, Dict, Any

logger = logging.getLogger(__name__)

# Default: check every 6 hours
DEFAULT_CHECK_INTERVAL = 6 * 60 * 60

# GitHub API endpoint
GITHUB_RELEASES_URL = "https://api.github.com/repos/rowboatlabs/rowboat/releases/latest"


class RowboatUpdateChecker:
    """
    Checks GitHub for new Rowboat releases and calls a callback
    when a newer version is found.

    Usage:
        checker = RowboatUpdateChecker(send_message_fn)
        checker.start()  # starts daemon thread
    """

    def __init__(self, send_message: Callable[[Dict[str, Any]], None]):
        self._send_message = send_message
        self._interval = int(os.getenv("ROWBOAT_UPDATE_CHECK_INTERVAL", str(DEFAULT_CHECK_INTERVAL)))
        self._current_version: Optional[str] = None
        self._latest_version: Optional[str] = None
        self._submodule_path = self._find_submodule_path()
        self._running = False
        self._thread = None

    def _find_submodule_path(self) -> str:
        """Locate the Rowboat submodule directory."""
        # Standard location relative to this file
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # roarboot/
        submodule = os.path.join(base, "rowboat")
        if os.path.isdir(submodule):
            return submodule
        # Fallback: relative to project root
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(base)))
        return os.path.join(project_root, "python", "spaces", "roarboot", "rowboat")

    def _get_current_version(self) -> Optional[str]:
        """Get the current submodule version via git describe --tags."""
        try:
            result = subprocess.run(
                ["git", "describe", "--tags", "--always"],
                capture_output=True, text=True, timeout=10,
                cwd=self._submodule_path,
            )
            if result.returncode == 0:
                version = result.stdout.strip()
                logger.debug(f"[UpdateChecker] Current version: {version}")
                return version
        except Exception as e:
            logger.warning(f"[UpdateChecker] Failed to get current version: {e}")
        return None

    def _get_latest_release(self) -> Optional[Dict[str, Any]]:
        """Fetch the latest release from GitHub API."""
        try:
            req = urllib.request.Request(
                GITHUB_RELEASES_URL,
                headers={
                    "Accept": "application/vnd.github.v3+json",
                    "User-Agent": "VibeMind-UpdateChecker/1.0",
                },
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())
                return {
                    "tag_name": data.get("tag_name", ""),
                    "name": data.get("name", ""),
                    "html_url": data.get("html_url", ""),
                    "published_at": data.get("published_at", ""),
                    "body": data.get("body", "")[:500],  # Truncate changelog
                }
        except urllib.error.HTTPError as e:
            logger.warning(f"[UpdateChecker] GitHub API error: {e.code}")
        except Exception as e:
            logger.warning(f"[UpdateChecker] Failed to fetch latest release: {e}")
        return None

    def _is_newer(self, current: str, latest_tag: str) -> bool:
        """
        Compare versions. Simple check: if the latest tag is different
        from the current git describe output, an update is available.
        Handles tags like 'v0.1.57' and git describe like 'v0.1.57-3-gabcdef'.
        """
        if not current or not latest_tag:
            return False

        # Extract base version from git describe (strip commit suffix)
        current_base = current.split("-")[0] if "-" in current else current

        # Normalize: strip leading 'v'
        current_norm = current_base.lstrip("v")
        latest_norm = latest_tag.lstrip("v")

        if current_norm == latest_norm:
            return False

        # Try semver comparison
        try:
            current_parts = [int(x) for x in current_norm.split(".")]
            latest_parts = [int(x) for x in latest_norm.split(".")]
            return latest_parts > current_parts
        except (ValueError, AttributeError):
            # Fallback: string comparison
            return latest_norm != current_norm

    def check_once(self) -> Optional[Dict[str, Any]]:
        """
        Perform a single update check.
        Returns release info if an update is available, None otherwise.
        """
        self._current_version = self._get_current_version()
        if not self._current_version:
            logger.warning("[UpdateChecker] Cannot determine current version")
            return None

        release = self._get_latest_release()
        if not release:
            return None

        latest_tag = release["tag_name"]
        if self._is_newer(self._current_version, latest_tag):
            self._latest_version = latest_tag
            logger.info(f"[UpdateChecker] Update available: {self._current_version} → {latest_tag}")
            return release

        logger.debug(f"[UpdateChecker] Up to date: {self._current_version}")
        return None

    def _run_loop(self):
        """Main loop: check periodically and notify via callback."""
        # Initial delay to let the app stabilize
        time.sleep(30)

        while self._running:
            try:
                release = self.check_once()
                if release:
                    self._send_message({
                        "type": "rowboat_update_available",
                        "current_version": self._current_version,
                        "latest_version": release["tag_name"],
                        "release_name": release.get("name", ""),
                        "release_url": release.get("html_url", ""),
                        "changelog": release.get("body", ""),
                    })
            except Exception as e:
                logger.error(f"[UpdateChecker] Check failed: {e}")

            # Wait for next check
            time.sleep(self._interval)

    def start(self):
        """Start the update checker as a daemon thread."""
        import threading

        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(
            target=self._run_loop,
            daemon=True,
            name="rowboat-update-checker",
        )
        self._thread.start()
        logger.info(f"[UpdateChecker] Started (interval={self._interval}s)")

    def stop(self):
        """Stop the update checker."""
        self._running = False
