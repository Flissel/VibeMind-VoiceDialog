"""The live preview of a project starts the sandbox of the Coding engine, safely.

Only a folder inside the projects directory is mounted, the port is bound to 127.0.0.1 only,
and nothing is started for any other path. Invented folders only; docker is never called.
"""
import asyncio
import os
import sys
import tempfile
import types

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
# project_manager imports debug_log from electron_backend; the test needs no backend
sys.modules.setdefault("electron_backend", types.SimpleNamespace(debug_log=lambda *a, **k: None))

from ipc import project_manager as pm  # noqa: E402


def _tree():
    root = tempfile.mkdtemp(prefix="vorschau-root-")
    inside = os.path.join(root, "project_beispiel")
    os.makedirs(inside)
    outside = tempfile.mkdtemp(prefix="vorschau-fremd-")
    return root, inside, outside


def test_only_a_folder_inside_the_projects_directory_is_mounted():
    root, inside, outside = _tree()
    assert pm.preview_mount(inside, root) == os.path.realpath(inside)
    assert pm.preview_mount(root, root) is None, "the directory itself is no project"
    assert pm.preview_mount(outside, root) is None
    assert pm.preview_mount(os.path.join(inside, "..", "..", os.path.basename(outside)), root) is None, "no way out with .."
    assert pm.preview_mount(os.path.join(root, "gibt-es-nicht"), root) is None
    file_path = os.path.join(inside, "datei.txt")
    with open(file_path, "w", encoding="utf-8") as f:
        f.write("x")
    assert pm.preview_mount(file_path, root) is None, "a file is no folder"
    assert pm.preview_mount(root + "-nachbar", root) is None
    assert pm.preview_mount("", root) is None
    assert pm.preview_mount(None, root) is None
    assert pm.preview_mount(inside, "") is None


def test_the_sandbox_of_the_engine_on_this_machine_only():
    cmd = pm.preview_docker_command("abc12345-xyz", "C:/projekte/project_beispiel", 51234, "1280x720")
    assert cmd[:3] == ["docker", "run", "-d"]
    assert cmd[cmd.index("--name") + 1] == "preview-abc12345"
    assert cmd[cmd.index("-p") + 1] == "127.0.0.1:51234:6090"
    assert cmd[cmd.index("-v") + 1] == "C:/projekte/project_beispiel:/workspace/app"
    assert cmd[cmd.index("-w") + 1] == "/workspace/app"
    envs = [cmd[i + 1] for i, part in enumerate(cmd) if part == "-e"]
    assert envs == ["ENABLE_VNC=true", "NOVNC_PORT=6090", "DISPLAY_RESOLUTION=1280x720"]
    assert cmd[cmd.index("--memory") + 1] == "1536m"
    assert cmd[-1] == "coding-engine/sandbox:latest"

    odd = pm.preview_docker_command("a;b c", "C:/p", 1, "1280x720 --privileged")
    assert odd[odd.index("--name") + 1] == "preview-abc"
    assert "DISPLAY_RESOLUTION=1280x720" in odd
    assert "--privileged" not in " ".join(odd)


def test_a_path_from_outside_starts_nothing_and_says_so(monkeypatch=None):
    root, _inside, outside = _tree()
    sent = []
    started = []
    backend = types.SimpleNamespace(send_message=sent.append, active_previews={}, coding_engine_path=root)
    manager = pm.ProjectManager(backend)
    original = pm.subprocess.Popen
    pm.subprocess.Popen = lambda *a, **k: started.append(a) or (_ for _ in ()).throw(AssertionError("docker called"))
    try:
        asyncio.run(manager.handle_start_project_preview("abc12345", outside))
        asyncio.run(manager.handle_start_project_preview("../x", os.path.join(root, "project_beispiel")))
    finally:
        pm.subprocess.Popen = original
    assert started == []
    assert [m["type"] for m in sent] == ["project_preview_error", "project_preview_error"]
    assert sent[0]["project_id"] == "abc12345"
    assert backend.active_previews == {}


def test_the_built_app_in_out_is_mounted_not_the_order_folder():
    root, order, _outside = _tree()
    folder, reason = pm.preview_app_folder(order, root)
    assert folder is None and reason == pm.NOT_BUILT, "no out folder: a calm sentence"

    out = os.path.join(order, "out")
    os.makedirs(out)
    assert pm.preview_app_folder(order, root) == (None, pm.NOT_BUILT), "out without package.json"

    with open(os.path.join(out, "package.json"), "w", encoding="utf-8") as f:
        f.write("{}")
    assert pm.preview_app_folder(order, root) == (os.path.realpath(out), "")
    assert pm.preview_app_folder(out, root) == (os.path.realpath(out), ""), "the out folder itself"
    assert pm.preview_app_folder(_outside, root) == (None, pm.NOT_A_PROJECT)


def test_an_order_not_yet_built_starts_nothing_and_says_so():
    root, order, _outside = _tree()
    sent = []
    backend = types.SimpleNamespace(send_message=sent.append, active_previews={}, coding_engine_path=root)
    original = pm.subprocess.Popen
    pm.subprocess.Popen = lambda *a, **k: (_ for _ in ()).throw(AssertionError("docker called"))
    try:
        asyncio.run(pm.ProjectManager(backend).handle_start_project_preview("abc12345", order))
    finally:
        pm.subprocess.Popen = original
    assert sent == [{"type": "project_preview_error", "project_id": "abc12345", "error": pm.NOT_BUILT}]


def test_the_projects_directory_can_be_named():
    old = os.environ.get("PREVIEW_PROJECTS_DIR")
    try:
        os.environ["PREVIEW_PROJECTS_DIR"] = "C:/eigene/projekte"
        assert pm.preview_projects_root("C:/engine") == "C:/eigene/projekte"
        del os.environ["PREVIEW_PROJECTS_DIR"]
        assert pm.preview_projects_root("C:/engine") == "C:/engine"
    finally:
        if old is not None:
            os.environ["PREVIEW_PROJECTS_DIR"] = old
