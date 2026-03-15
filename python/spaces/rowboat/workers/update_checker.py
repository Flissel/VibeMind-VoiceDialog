"""
Rowboat Update Checker + Auto-Pull

Periodically checks GitHub for new Rowboat releases. When a newer version
is found, automatically pulls it (stash → pull → stash pop) and notifies
the Electron UI.

Architecture:
  Python daemon thread  ──check──→  GitHub API (releases/latest)
        ↓ (if newer)
  auto-pull: git stash → git pull origin main → git stash pop
        ↓
  rowboat_update_applied  ──→  Electron main.js  ──→  Tab badge
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
        self._auto_pull = os.getenv("ROWBOAT_AUTO_PULL", "true").lower() == "true"
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
        """Get the current submodule version via git rev-parse or HEAD file."""
        if not os.path.isdir(self._submodule_path):
            logger.warning(f"[UpdateChecker] Submodule path does not exist: {self._submodule_path}")
            return None

        env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_ASKPASS": ""}

        # Fast path: rev-parse just reads .git/HEAD — should be instant
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                capture_output=True, text=True, timeout=3,
                cwd=self._submodule_path,
                env=env,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if result.returncode == 0 and result.stdout.strip():
                version = result.stdout.strip()
                logger.debug(f"[UpdateChecker] Current version (commit): {version}")
                return version
        except subprocess.TimeoutExpired:
            logger.debug("[UpdateChecker] git rev-parse timed out, trying file read")
        except Exception:
            pass

        # Fallback: read the HEAD ref directly from the filesystem
        try:
            git_path = os.path.join(self._submodule_path, ".git")
            # Submodules have a .git file pointing to the real gitdir
            if os.path.isfile(git_path):
                with open(git_path, "r") as f:
                    content = f.read().strip()
                if content.startswith("gitdir:"):
                    gitdir = content[7:].strip()
                    if not os.path.isabs(gitdir):
                        gitdir = os.path.normpath(os.path.join(self._submodule_path, gitdir))
                    head_file = os.path.join(gitdir, "HEAD")
                else:
                    head_file = None
            elif os.path.isdir(git_path):
                head_file = os.path.join(git_path, "HEAD")
            else:
                head_file = None

            if head_file and os.path.isfile(head_file):
                with open(head_file, "r") as f:
                    head_content = f.read().strip()
                if head_content.startswith("ref:"):
                    # HEAD points to a branch — resolve it
                    ref_path = head_content[4:].strip()
                    ref_file = os.path.join(os.path.dirname(head_file), ref_path)
                    if os.path.isfile(ref_file):
                        with open(ref_file, "r") as f:
                            version = f.read().strip()[:10]
                            logger.debug(f"[UpdateChecker] Current version (file): {version}")
                            return version
                else:
                    # Detached HEAD — it's a commit hash
                    version = head_content[:10]
                    logger.debug(f"[UpdateChecker] Current version (detached): {version}")
                    return version
        except Exception as e:
            logger.warning(f"[UpdateChecker] Failed to read HEAD file: {e}")

        logger.warning(f"[UpdateChecker] Could not determine version for {self._submodule_path}")
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

    def _run_git(self, *args, timeout: int = 60) -> subprocess.CompletedProcess:
        """Run a git command in the submodule directory (non-interactive, no window)."""
        env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_ASKPASS": ""}
        return subprocess.run(
            ["git", *args],
            capture_output=True, text=True, timeout=timeout,
            cwd=self._submodule_path,
            env=env,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )

    def _auto_pull_update(self) -> Dict[str, Any]:
        """
        Auto-pull latest changes: stash local changes, pull, restore.

        Returns:
            Dict with keys: success, old_version, new_version, error
        """
        old_version = self._current_version or "unknown"
        stashed = False

        try:
            # 1. Check for local changes
            status = self._run_git("status", "--porcelain", timeout=10)
            has_changes = bool(status.stdout.strip())

            # 2. Stash if dirty
            if has_changes:
                logger.info("[UpdateChecker] Stashing local changes...")
                stash_result = self._run_git(
                    "stash", "push", "-m", "auto-pull before update", "--include-untracked"
                )
                if stash_result.returncode != 0:
                    return {"success": False, "old_version": old_version,
                            "new_version": old_version, "error": f"Stash failed: {stash_result.stderr.strip()}"}
                stashed = True

            # 3. Pull
            logger.info("[UpdateChecker] Pulling latest from origin/main...")
            pull_result = self._run_git("pull", "origin", "main", timeout=30)
            if pull_result.returncode != 0:
                # Restore stash on failure
                if stashed:
                    self._run_git("stash", "pop")
                return {"success": False, "old_version": old_version,
                        "new_version": old_version, "error": f"Pull failed: {pull_result.stderr.strip()}"}

            # 4. Restore stash
            if stashed:
                logger.info("[UpdateChecker] Restoring local changes...")
                pop_result = self._run_git("stash", "pop")
                if pop_result.returncode != 0:
                    logger.warning(f"[UpdateChecker] Stash pop had conflicts: {pop_result.stderr.strip()}")

            # 5. Get new version
            new_version = self._get_current_version() or "unknown"
            logger.info(f"[UpdateChecker] Auto-pull complete: {old_version} -> {new_version}")

            return {"success": True, "old_version": old_version, "new_version": new_version, "error": None}

        except subprocess.TimeoutExpired:
            if stashed:
                self._run_git("stash", "pop")
            return {"success": False, "old_version": old_version,
                    "new_version": old_version, "error": "Git operation timed out"}
        except Exception as e:
            if stashed:
                try:
                    self._run_git("stash", "pop")
                except Exception:
                    pass
            return {"success": False, "old_version": old_version,
                    "new_version": old_version, "error": str(e)}

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
        """Main loop: check periodically, auto-pull if enabled, and notify."""
        # Short delay to let the app stabilize
        time.sleep(10)

        while self._running:
            try:
                release = self.check_once()
                if release:
                    if self._auto_pull:
                        # Auto-pull and notify result
                        result = self._auto_pull_update()
                        if result["success"]:
                            self._send_message({
                                "type": "rowboat_update_applied",
                                "old_version": result["old_version"],
                                "new_version": result["new_version"],
                                "release_name": release.get("name", ""),
                                "changelog": release.get("body", ""),
                            })
                        else:
                            # Pull failed — fall back to manual notification
                            logger.warning(f"[UpdateChecker] Auto-pull failed: {result['error']}")
                            self._send_message({
                                "type": "rowboat_update_available",
                                "current_version": self._current_version,
                                "latest_version": release["tag_name"],
                                "release_name": release.get("name", ""),
                                "release_url": release.get("html_url", ""),
                                "changelog": release.get("body", ""),
                                "auto_pull_error": result["error"],
                            })
                    else:
                        # Auto-pull disabled — just notify
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
        logger.info(f"[UpdateChecker] Started (interval={self._interval}s, auto_pull={self._auto_pull})")

    def stop(self):
        """Stop the update checker."""
        self._running = False
