"""Blue Rose Stufe 1: das Tagebuch geht nur noch mit Schalter in die Rowboat-Wissensablage."""
import publishing


def test_ohne_schalter_schreibt_niemand_die_tagebuch_notiz(monkeypatch):
    monkeypatch.delenv("BLUE_ROSE_ROWBOAT_NOTIZ", raising=False)
    monkeypatch.setattr(publishing, "_blue_rose_publisher", None)
    monkeypatch.setattr(publishing, "is_space_enabled", lambda space: True)
    publisher = publishing.get_blue_rose_publisher()
    assert isinstance(publisher, publishing._NoOpPublisher)
    assert publisher.mirror() is None
    assert publishing._blue_rose_publisher is None


def test_schalter_liest_nur_klare_ja_werte(monkeypatch):
    for wert, erwartet in (("1", True), ("true", True), ("0", False), ("", False), ("vielleicht", False)):
        monkeypatch.setenv("BLUE_ROSE_ROWBOAT_NOTIZ", wert)
        assert publishing.blue_rose_notiz_erlaubt() is erwartet
