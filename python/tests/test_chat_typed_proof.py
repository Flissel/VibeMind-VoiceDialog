"""eingabe "getippt" bleibt nur mit dem Beleg des Hauptprozesses der App im Kontext.

Ueber den allgemeinen Kanal `to-python` kann jede Seite eine Nachricht `chat_text_input`
mit `context.eingabe` schicken. Der Hauptprozess legt fuer einen wirklich getippten Satz
`eingabe_beleg` bei, einen Zufallswert, den nur er und dieser Prozess (Umgebung) kennen
(electron-app/chat-input.js). Ohne ihn faellt die Marke weg, der Rest bleibt.
"""
from ipc.clawport_handlers import trusted_ui_context

PROOF = "a" * 64


def test_the_mark_stays_with_the_proof_of_the_main_process(monkeypatch):
    monkeypatch.setenv("VIBEMIND_EINGABE_BELEG", PROOF)
    message = {"type": "chat_text_input", "text": "x", "context": {"space": "desktop", "eingabe": "getippt"}, "eingabe_beleg": PROOF}
    assert trusted_ui_context(message) == {"space": "desktop", "eingabe": "getippt"}


def test_a_forged_mark_is_dropped(monkeypatch):
    monkeypatch.setenv("VIBEMIND_EINGABE_BELEG", PROOF)
    for proof in (None, "", "geraten", PROOF[:-1], 42):
        message = {"context": {"space": "desktop", "eingabe": "getippt"}, "eingabe_beleg": proof}
        assert trusted_ui_context(message) == {"space": "desktop"}, proof
    assert trusted_ui_context({"context": {"eingabe": "getippt"}}) is None


def test_without_the_proof_in_the_environment_nothing_counts_as_typed(monkeypatch):
    monkeypatch.delenv("VIBEMIND_EINGABE_BELEG", raising=False)
    message = {"context": {"space": "desktop", "eingabe": "getippt"}, "eingabe_beleg": ""}
    assert trusted_ui_context(message) == {"space": "desktop"}


def test_a_context_without_the_mark_goes_on_unchanged(monkeypatch):
    monkeypatch.delenv("VIBEMIND_EINGABE_BELEG", raising=False)
    context = {"space": "ideas", "bubble": {"id": None, "title": "Marketing"}}
    assert trusted_ui_context({"context": context}) is context
    assert trusted_ui_context({"text": "x"}) is None
    assert trusted_ui_context({"context": {}}) is None
