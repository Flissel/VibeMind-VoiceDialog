"""Pins the 2026-10-19 SSH mode of bubble_sync._db.

Since 19.10.2026 the mini-PC Supabase (container debian-supabase-db-1 on offload-vm) is the only source
of truth; the PC no longer runs vibemind_supabase-db. The workers reach the database like the marketing
sync: `ssh <host> docker exec -i <container> psql ...` with the SQL on stdin, selected by
SUPABASE_SSH_HOST + SUPABASE_DB_CONTAINER. Without SUPABASE_SSH_HOST the old local path stays.
"""
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from publishing.bubble_sync import _db  # noqa: E402


def _ok(stdout=""):
    return subprocess.CompletedProcess(args=[], returncode=0, stdout=stdout, stderr="")


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for k in ("SUPABASE_SSH_HOST", "SUPABASE_DB_CONTAINER"):
        monkeypatch.delenv(k, raising=False)


def test_ssh_mode_uses_configured_container_without_docker_lookup(monkeypatch):
    monkeypatch.setenv("SUPABASE_SSH_HOST", "offload-vm")
    monkeypatch.setenv("SUPABASE_DB_CONTAINER", "debian-supabase-db-1")
    with patch.object(_db.subprocess, "run") as run:
        assert _db.find_supabase_container() == "debian-supabase-db-1"
        run.assert_not_called()


def test_ssh_mode_without_container_name_fails_loudly(monkeypatch):
    monkeypatch.setenv("SUPABASE_SSH_HOST", "offload-vm")
    with pytest.raises(RuntimeError, match="SUPABASE_DB_CONTAINER"):
        _db.find_supabase_container()


def test_query_over_ssh_sends_sql_on_stdin_never_on_the_command_line(monkeypatch):
    monkeypatch.setenv("SUPABASE_SSH_HOST", "offload-vm")
    monkeypatch.setenv("SUPABASE_DB_CONTAINER", "debian-supabase-db-1")
    sql = "SELECT id FROM public.ideas WHERE title = 'it''s; rm -rf /'"
    with patch.object(_db.subprocess, "run", return_value=_ok('[{"id": "a"}]')) as run:
        rows = _db.query_via_docker(sql)
    assert rows == [{"id": "a"}]
    argv = run.call_args.args[0]
    kwargs = run.call_args.kwargs
    assert argv[0] == "ssh" and "offload-vm" in argv
    remote = argv[-1]
    assert "docker exec -i debian-supabase-db-1 psql" in remote
    assert "ON_ERROR_STOP=1" in remote and "-f -" in remote
    assert "rm -rf" not in " ".join(argv)
    assert "rm -rf" in kwargs["input"] and kwargs["input"].startswith("SELECT COALESCE(jsonb_agg")
    assert kwargs["encoding"] == "utf-8"


def test_execute_over_ssh_raises_on_psql_error(monkeypatch):
    monkeypatch.setenv("SUPABASE_SSH_HOST", "offload-vm")
    monkeypatch.setenv("SUPABASE_DB_CONTAINER", "debian-supabase-db-1")
    failed = subprocess.CompletedProcess(args=[], returncode=3, stdout="", stderr="ERROR: boom")
    with patch.object(_db.subprocess, "run", return_value=failed):
        with pytest.raises(RuntimeError, match="boom"):
            _db.execute_via_docker("UPDATE public.ideas SET title = 'x'")


def test_local_mode_keeps_docker_exec_and_container_lookup():
    with patch.object(_db.subprocess, "run", side_effect=[_ok("abc123\n"), _ok("UPDATE 1")]) as run:
        out = _db.execute_via_docker("UPDATE public.ideas SET title = 'x'")
    assert out == "UPDATE 1"
    lookup, call = run.call_args_list
    assert lookup.args[0][:3] == ["docker", "ps", "-qf"]
    argv = call.args[0]
    assert argv[:4] == ["docker", "exec", "-i", "abc123"]
    assert call.kwargs["input"] == "UPDATE public.ideas SET title = 'x'"


def test_local_mode_honours_explicit_container_name(monkeypatch):
    monkeypatch.setenv("SUPABASE_DB_CONTAINER", "debian-supabase-db-1")
    with patch.object(_db.subprocess, "run") as run:
        assert _db.find_supabase_container() == "debian-supabase-db-1"
        run.assert_not_called()
