"""Startprofil-Regressionen fuer das Python-Backend (voice-App Teil 1, Spec 2026-10-15).

1. electron_backend/ipc duerfen nur SpaceColors-Namen nutzen, die es gibt
   (seit 6010f3e heisst ROWBOAT -> ROARBOOT; der Import brach seit 09.07. ab).
2. Profil "aus": Start-Sync loescht keine Rowboat-Quellen/Vault-Ordner.
3. Profil "aus": Bubble-Sync-Worker A/B sind per Kill-Switch aus.
"""
from __future__ import annotations

import ast
import importlib
import os
import subprocess
import sys
import types
from pathlib import Path

import pytest

PY_ROOT = Path(__file__).resolve().parents[1]


def _space_color_refs(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {
        node.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "SpaceColors"
    }


def test_backend_und_ipc_nutzen_nur_vorhandene_space_colors() -> None:
    from swarm.logging.space_logger import SpaceColors

    dateien = [PY_ROOT / "electron_backend.py", *sorted((PY_ROOT / "ipc").glob("*.py"))]
    fehlend = sorted(
        f"{datei.name}:{name}"
        for datei in dateien
        for name in _space_color_refs(datei)
        if not hasattr(SpaceColors, name)
    )
    assert fehlend == []


@pytest.mark.skipif(not os.environ.get("VOICE_PYTHON"), reason="VOICE_PYTHON (Python 3.12 der voice-venv) nicht gesetzt")
def test_electron_backend_importiert_mit_der_voice_venv() -> None:
    env = dict(os.environ)
    env.update({
        "VIBEMIND_ROWBOAT_AUTOCLEAN": "0",
        "VIBEMIND_BUBBLE_SYNC_ENABLED": "0",
        "VIBEMIND_CANVAS_REFORMAT_ENABLED": "0",
        "PYTHONIOENCODING": "utf-8",
    })
    ergebnis = subprocess.run(
        [os.environ["VOICE_PYTHON"], "-c", "import electron_backend; print('IMPORT_OK')"],
        cwd=PY_ROOT, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=240,
    )
    assert ergebnis.returncode == 0, ergebnis.stderr[-2000:]
    assert "IMPORT_OK" in ergebnis.stdout


def _fake_cleanup_module(monkeypatch: pytest.MonkeyPatch, aufrufe: list[str]) -> None:
    fake_data = types.ModuleType("data")

    class _Ideas:
        def list_top_level(self, limit: int):  # noqa: ARG002
            aufrufe.append("ideas")
            return []

    fake_data.IdeasRepository = _Ideas
    monkeypatch.setitem(sys.modules, "data", fake_data)

    fake_mongo = types.ModuleType("publishing.rowboat_mongo_publisher")

    class _Mongo:
        def cleanup_orphaned_sources(self, *args, **kwargs):  # noqa: ARG002
            aufrufe.append("mongo")
            return {"deleted": 0}

    fake_mongo.RowboatMongoPublisher = _Mongo
    monkeypatch.setitem(sys.modules, "publishing.rowboat_mongo_publisher", fake_mongo)

    fake_vault = types.ModuleType("publishing.ideas_publisher")

    class _Vault:
        def cleanup_orphaned_project_dirs(self, *args, **kwargs):  # noqa: ARG002
            aufrufe.append("vault")
            return {"deleted": 0}

    fake_vault.IdeasPublisher = _Vault
    monkeypatch.setitem(sys.modules, "publishing.ideas_publisher", fake_vault)


def _publishing_ohne_spiegel(monkeypatch: pytest.MonkeyPatch):
    import publishing

    for name in ("get_openfang_publisher", "get_n8n_publisher", "get_blue_rose_publisher", "get_mirofish_publisher"):
        monkeypatch.setattr(publishing, name, lambda: object())
    return publishing


def test_autoclean_aus_loescht_weder_mongo_noch_vault(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ROWBOAT_PUBLISH_ENABLED", "1")
    monkeypatch.setenv("VIBEMIND_ROWBOAT_AUTOCLEAN", "0")
    aufrufe: list[str] = []
    _fake_cleanup_module(monkeypatch, aufrufe)
    publishing = _publishing_ohne_spiegel(monkeypatch)

    ergebnis = publishing.sync_all_spaces()

    assert "rowboat-cleanup" not in ergebnis
    assert "rowboat-cleanup-vault" not in ergebnis
    assert aufrufe == []


def test_autoclean_an_ruft_beide_aufraeumer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ROWBOAT_PUBLISH_ENABLED", "1")
    monkeypatch.setenv("VIBEMIND_ROWBOAT_AUTOCLEAN", "1")
    aufrufe: list[str] = []
    _fake_cleanup_module(monkeypatch, aufrufe)
    publishing = _publishing_ohne_spiegel(monkeypatch)

    publishing.sync_all_spaces()

    assert aufrufe == ["ideas", "mongo", "vault"]


@pytest.mark.parametrize("modul", [
    "publishing.bubble_sync.worker_db_to_fs",
    "publishing.bubble_sync.worker_fs_to_db",
])
def test_bubble_worker_sind_bei_profil_aus_abgeschaltet(monkeypatch: pytest.MonkeyPatch, modul: str) -> None:
    monkeypatch.setenv("VIBEMIND_BUBBLE_SYNC_ENABLED", "0")
    geladen = importlib.reload(importlib.import_module(modul))
    assert geladen.ENABLED is False
