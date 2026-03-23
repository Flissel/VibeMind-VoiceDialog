/**
 * Transcript Utils — showTranscript function with auto-hide.
 * Extracted from index.html inline script.
 */
(function() {
    'use strict';

    function showTranscript(speaker, text) {
        var panel = document.getElementById('transcript-panel');
        var content = document.getElementById('transcript-content');
        if (!panel || !content) return;
        panel.classList.remove('hidden');

        var entry = document.createElement('div');
        entry.className = 'transcript-entry';
        var strong = document.createElement('strong');
        strong.textContent = speaker + ':';
        entry.appendChild(strong);
        entry.appendChild(document.createTextNode(' ' + text));
        content.appendChild(entry);
        content.scrollTop = content.scrollHeight;

        clearTimeout(window.transcriptTimeout);
        window.transcriptTimeout = setTimeout(function() {
            panel.classList.add('hidden');
        }, 5000);
    }

    window.showTranscript = showTranscript;
})();
