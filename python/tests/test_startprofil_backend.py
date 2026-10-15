"""Startprofil-Regressionen fuer das Python-Backend (voice-App Teil 1, Spec 2026-10-15).

1. electron_backend/ipc duerfen nur SpaceColors-Namen nutzen, die es gibt
   (seit 6010f3e heisst ROWBOAT -> ROARBOOT; der Import brach seit 09.07. ab).
2. Profil "aus": Start-Sync loescht keine Rowboat-Quellen/Vault-Ordner.
3. Profil "aus": Bubble-Sync-Worker A/B sind per Kill-Switch aus.
4. Profil "aus" (rowboat-publish): NoOp-Publisher, kein sync_all_spaces, kein Brain-Seeding.
5. Eine .env mit 1/true ueberschreibt den Prozesswert 0 aus Electron nicht (override=False).
"""
from __future__ import annotations

import ast
import importlib
import importlib.util
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


# ---------------------------------------------------------------------------
# Final Review 2026-10-15, Important 2: Startprofil-Name `rowboat-publish` (Vorgabe aus).
# Electron setzt bei "aus" ROWBOAT_PUBLISH_ENABLED=0 und BRAIN_SEEDING_ENABLED=0, bei "an" beide
# auf "true" (startup-policy.js pythonEnv). Diese Tests nageln fest, dass Python genau diese Werte
# so versteht: aus -> NoOp-Publisher, sync_all_spaces bricht frueh ab, BrainSeeder tut nichts.
# Alles mit Fakes, keine echten Mongo-/Qdrant-/Brain-Aufrufe.
# ---------------------------------------------------------------------------
ELECTRON_AUS = "0"
ELECTRON_AN = "true"


def _fake_publisher_module(monkeypatch: pytest.MonkeyPatch, gebaut: list[str]) -> None:
    fake_mongo = types.ModuleType("publishing.rowboat_mongo_publisher")

    class _Mongo:
        is_available = True

        def __init__(self) -> None:
            gebaut.append("mongo")

    fake_mongo.RowboatMongoPublisher = _Mongo
    monkeypatch.setitem(sys.modules, "publishing.rowboat_mongo_publisher", fake_mongo)

    fake_fs = types.ModuleType("publishing.ideas_publisher")

    class _Fs:
        def __init__(self) -> None:
            gebaut.append("fs")

    fake_fs.IdeasPublisher = _Fs
    monkeypatch.setitem(sys.modules, "publishing.ideas_publisher", fake_fs)


def test_publish_aus_liefert_noop_publisher_ohne_mongo_oder_vault(monkeypatch: pytest.MonkeyPatch) -> None:
    import publishing

    monkeypatch.setenv("ROWBOAT_PUBLISH_ENABLED", ELECTRON_AUS)
    monkeypatch.setenv("ROWBOAT_PUBLISH_MONGO", "true")
    monkeypatch.setenv("ROWBOAT_PROJECT_ID", "projekt-x")
    monkeypatch.setattr(publishing, "_ideas_publisher", None)
    gebaut: list[str] = []
    _fake_publisher_module(monkeypatch, gebaut)

    publisher = publishing.get_ideas_publisher()

    assert isinstance(publisher, publishing._NoOpPublisher)
    assert publisher.sync_all() is None
    assert gebaut == []


def test_publish_an_baut_den_publisher_gegenprobe(monkeypatch: pytest.MonkeyPatch) -> None:
    import publishing

    monkeypatch.setenv("ROWBOAT_PUBLISH_ENABLED", ELECTRON_AN)
    monkeypatch.setenv("ROWBOAT_PUBLISH_MONGO", "true")
    monkeypatch.setenv("ROWBOAT_PROJECT_ID", "projekt-x")
    monkeypatch.delenv("ROWBOAT_PUBLISH_IDEAS", raising=False)
    monkeypatch.setattr(publishing, "_ideas_publisher", None)
    gebaut: list[str] = []
    _fake_publisher_module(monkeypatch, gebaut)

    publisher = publishing.get_ideas_publisher()

    assert not isinstance(publisher, publishing._NoOpPublisher)
    assert gebaut == ["mongo"]


def test_publish_aus_sync_all_spaces_bricht_frueh_ab(monkeypatch: pytest.MonkeyPatch) -> None:
    import publishing

    monkeypatch.setenv("ROWBOAT_PUBLISH_ENABLED", ELECTRON_AUS)
    # selbst mit Autoclean an darf nichts laufen, wenn Publish aus ist
    monkeypatch.setenv("VIBEMIND_ROWBOAT_AUTOCLEAN", "1")
    aufrufe: list[str] = []
    _fake_cleanup_module(monkeypatch, aufrufe)
    for name in ("get_openfang_publisher", "get_n8n_publisher", "get_blue_rose_publisher", "get_mirofish_publisher"):
        monkeypatch.setattr(publishing, name, lambda n=name: aufrufe.append(n))

    assert publishing.sync_all_spaces() == {}
    assert aufrufe == []


def _brain_seeder_modul():
    kandidaten = [PY_ROOT.parents[1]]
    if os.environ.get("VIBEMIND_OS_ROOT"):
        kandidaten.insert(0, Path(os.environ["VIBEMIND_OS_ROOT"]))
    for root in kandidaten:
        datei = root / "brain" / "brain_seeder.py"
        if datei.is_file():
            spec = importlib.util.spec_from_file_location("_startprofil_brain_seeder", datei)
            modul = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(modul)
            return modul
    pytest.skip("brain/brain_seeder.py nicht gefunden (VIBEMIND_OS_ROOT setzen)")


class _VerbotenerMongo:
    def __getattr__(self, name: str):
        raise AssertionError(f"Mongo-Zugriff trotz Seeding aus: {name}")

    def __getitem__(self, name: str):
        raise AssertionError(f"Mongo-Zugriff trotz Seeding aus: [{name}]")


def test_seeding_aus_brain_seeder_tut_nichts(monkeypatch: pytest.MonkeyPatch) -> None:
    modul = _brain_seeder_modul()
    monkeypatch.setenv("BRAIN_SEEDING_ENABLED", ELECTRON_AUS)
    monkeypatch.setenv("BRAIN_SEED_ON_STARTUP", "true")
    fake_httpx = types.ModuleType("httpx")

    def _post(*args, **kwargs):  # noqa: ARG001
        raise AssertionError("Brain-Aufruf trotz Seeding aus")

    fake_httpx.post = _post
    monkeypatch.setitem(sys.modules, "httpx", fake_httpx)

    seeder = modul.BrainSeeder(mongo_client=_VerbotenerMongo(), db_name="rowboat", project_id="projekt-x")

    assert seeder._enabled is False
    assert seeder.seed_all() is None
    assert seeder.on_source_ready("quelle-1", "VibeMind - Idee") is None


def test_seeding_an_wird_mit_dem_electron_wert_erkannt(monkeypatch: pytest.MonkeyPatch) -> None:
    modul = _brain_seeder_modul()
    monkeypatch.setenv("BRAIN_SEEDING_ENABLED", ELECTRON_AN)
    assert modul.BrainSeeder(mongo_client=None)._enabled is True
    # Gegenprobe: "1" waere fuer den Seeder AUS - deshalb setzt Electron "true"
    monkeypatch.setenv("BRAIN_SEEDING_ENABLED", "1")
    assert modul.BrainSeeder(mongo_client=None)._enabled is False


# ---------------------------------------------------------------------------
# Final Review, Minor 9: eine .env mit 1/true darf den Prozesswert 0 nicht ueberschreiben
# (electron_backend.py laedt alle .env mit override=False). Alle load_dotenv-Aufrufe des
# Backends werden auf eine temporaere .env (auf C:) umgelenkt; echte .env werden nie gelesen.
# ---------------------------------------------------------------------------
_DOTENV_BOOTSTRAP = r"""
import json, os, sys
from pathlib import Path
import dotenv
_echt = dotenv.load_dotenv
_aufrufe = []
def _umgelenkt(dotenv_path=None, *args, **kwargs):
    _aufrufe.append({"pfad": str(dotenv_path), "override": kwargs.get("override", False)})
    return _echt(os.environ["_STARTPROFIL_TMP_ENV"], *args, **kwargs)
dotenv.load_dotenv = _umgelenkt
# Genau die drei .env-Pfade aus electron_backend.py gelten als vorhanden (im Worktree fehlen sie);
# gelesen wird trotzdem nur die temporaere .env.
_backend = Path.cwd() / "electron_backend.py"
_env_pfade = {str(p) for p in (
    _backend.parent.parent.parent.parent / ".env",
    _backend.parent.parent.parent / ".env",
    _backend.parent.parent / ".env",
)}
_exists = Path.exists
Path.exists = lambda self, *a, **k: True if str(self) in _env_pfade else _exists(self, *a, **k)
try:
    import electron_backend  # noqa: F401
finally:
    Path.exists = _exists
print("ERGEBNIS=" + json.dumps({
    "VIBEMIND_BUBBLE_SYNC_ENABLED": os.environ.get("VIBEMIND_BUBBLE_SYNC_ENABLED"),
    "ROWBOAT_PUBLISH_ENABLED": os.environ.get("ROWBOAT_PUBLISH_ENABLED"),
    "STARTPROFIL_NUR_IN_DOTENV": os.environ.get("STARTPROFIL_NUR_IN_DOTENV"),
    "aufrufe": _aufrufe,
}))
"""


@pytest.mark.skipif(not os.environ.get("VOICE_PYTHON"), reason="VOICE_PYTHON (Python 3.12 der voice-venv) nicht gesetzt")
def test_dotenv_mit_1_ueberschreibt_den_prozesswert_0_nicht() -> None:
    import json
    import shutil
    import tempfile

    basis = Path.home() / ".vbu-tests"
    basis.mkdir(exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="dotenv-", dir=basis))
    try:
        tmp_env = tmp / ".env"
        tmp_env.write_text(
            "VIBEMIND_BUBBLE_SYNC_ENABLED=1\nROWBOAT_PUBLISH_ENABLED=true\nSTARTPROFIL_NUR_IN_DOTENV=geladen\n",
            encoding="utf-8",
        )
        env = dict(os.environ)
        env.update({
            "VIBEMIND_ROWBOAT_AUTOCLEAN": "0",
            "VIBEMIND_BUBBLE_SYNC_ENABLED": "0",
            "VIBEMIND_CANVAS_REFORMAT_ENABLED": "0",
            "ROWBOAT_PUBLISH_ENABLED": "0",
            "BRAIN_SEEDING_ENABLED": "0",
            "PYTHONIOENCODING": "utf-8",
            "_STARTPROFIL_TMP_ENV": str(tmp_env),
        })
        env.pop("STARTPROFIL_NUR_IN_DOTENV", None)
        ergebnis = subprocess.run(
            [os.environ["VOICE_PYTHON"], "-c", _DOTENV_BOOTSTRAP],
            cwd=PY_ROOT, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=240,
        )
        assert ergebnis.returncode == 0, ergebnis.stderr[-2000:]
        zeile = next(z for z in ergebnis.stdout.splitlines() if z.startswith("ERGEBNIS="))
        werte = json.loads(zeile[len("ERGEBNIS="):])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # Die temporaere .env wurde tatsaechlich geladen ...
    assert werte["aufrufe"], "electron_backend hat load_dotenv nicht aufgerufen"
    assert werte["STARTPROFIL_NUR_IN_DOTENV"] == "geladen"
    # ... aber der Prozesswert 0 aus Electron gewinnt
    assert werte["VIBEMIND_BUBBLE_SYNC_ENABLED"] == "0"
    assert werte["ROWBOAT_PUBLISH_ENABLED"] == "0"
    assert all(a["override"] is False for a in werte["aufrufe"])
