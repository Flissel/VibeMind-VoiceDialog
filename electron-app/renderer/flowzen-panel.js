/**
 * Flowzen (Blaue Rose) Panel — Diary entries, status, and recommendations.
 * Extracted from index.html inline script.
 *
 * Dependency: window.vibemind.sendToPython (preload IPC)
 */
(function() {
    'use strict';

    function requestFlowzenStatus() {
        if (window.vibemind && window.vibemind.sendToPython) {
            window.vibemind.sendToPython({ type: 'flowzen_status' });
        }
    }

    function requestFlowzenDiaryEntries() {
        if (window.vibemind && window.vibemind.sendToPython) {
            window.vibemind.sendToPython({ type: 'flowzen_diary_entries' });
        }
    }

    function requestFlowzenRecommend() {
        var btn = document.getElementById('fz-recommend-btn');
        if (btn) {
            btn.classList.add('loading');
            btn.textContent = 'Thinking...';
        }
        if (window.vibemind && window.vibemind.sendToPython) {
            window.vibemind.sendToPython({ type: 'flowzen_recommend' });
        }
    }

    function updateFlowzenPanel(data) {
        var timeEl = document.getElementById('fz-time-window');
        var moodEl = document.getElementById('fz-mood');
        var catEl = document.getElementById('fz-category');
        var stateEl = document.getElementById('flowzen-state-badge');

        if (timeEl && data.current_time_window) {
            var windowNames = {
                early_morning: 'Early Morning', morning: 'Morning', midday: 'Midday',
                afternoon: 'Afternoon', evening: 'Evening', night: 'Night'
            };
            timeEl.textContent = windowNames[data.current_time_window] || data.current_time_window;
        }
        if (moodEl && data.mood) moodEl.textContent = data.mood;
        if (catEl && data.category) catEl.textContent = data.category;
        if (stateEl && data.state !== undefined) {
            var state = data.state || 'idle';
            stateEl.textContent = state;
            stateEl.className = 'flowzen-state ' + state;
        }
    }

    function renderDiaryEntries(entries) {
        var container = document.getElementById('fz-diary-journal');
        var emptyEl = document.getElementById('fz-diary-empty');
        if (!container) return;

        // Remove existing entries (keep empty placeholder)
        container.querySelectorAll('.diary-entry').forEach(function(el) { el.remove(); });

        if (!entries || entries.length === 0) {
            if (emptyEl) emptyEl.style.display = '';
            return;
        }
        if (emptyEl) emptyEl.style.display = 'none';

        entries.forEach(function(entry) {
            container.appendChild(_buildDiaryCard(entry));
        });
    }

    function addSingleDiaryEntry(entry) {
        var container = document.getElementById('fz-diary-journal');
        var emptyEl = document.getElementById('fz-diary-empty');
        if (!container) return;
        if (emptyEl) emptyEl.style.display = 'none';

        var card = _buildDiaryCard(entry);
        container.insertBefore(card, container.firstChild);

        // Limit to 10 entries
        var entries = container.querySelectorAll('.diary-entry');
        if (entries.length > 10) {
            entries[entries.length - 1].remove();
        }
    }

    function _buildDiaryCard(entry) {
        var card = document.createElement('div');
        card.className = 'diary-entry';

        var windowNames = {
            early_morning: 'Frueh', morning: 'Morgen', midday: 'Mittag',
            afternoon: 'Nachmittag', evening: 'Abend', night: 'Nacht'
        };

        // Time header
        var header = document.createElement('div');
        header.className = 'diary-entry-time';
        var timeStr = '';
        try {
            timeStr = new Date(entry.created_at).toLocaleTimeString('de-DE', {hour:'2-digit', minute:'2-digit'});
        } catch(e) {
            timeStr = (entry.hour || 0) + ':00';
        }
        header.textContent = timeStr + ' \u2014 ' + (windowNames[entry.time_window] || entry.time_window || '');
        card.appendChild(header);

        // Meta line
        var meta = document.createElement('div');
        meta.className = 'diary-entry-meta';
        var moodEmojis = { energized: '\u26A1', focused: '\uD83C\uDFAF', calm: '\uD83C\uDF3F', tired: '\uD83D\uDCA4', anxious: '\u26A0\uFE0F' };
        var emoji = moodEmojis[entry.mood] || '';
        meta.textContent = emoji + ' ' + (entry.mood || '') + ' \u00B7 energy ' + (entry.energy || '?') + '/10 \u00B7 ' + (entry.intent_count || 0) + ' activities';
        card.appendChild(meta);

        // Diary text (the warm LLM-generated text)
        var text = document.createElement('div');
        text.className = 'diary-entry-text';
        text.textContent = entry.entry_text || '';
        card.appendChild(text);

        // Source badge (manual vs periodic)
        if (entry.source === 'manual') {
            var badge = document.createElement('div');
            badge.className = 'diary-entry-source';
            badge.textContent = '\uD83C\uDF39 On request';
            card.appendChild(badge);
        }

        return card;
    }

    // Wire up Flowzen recommend button
    var btn = document.getElementById('fz-recommend-btn');
    if (btn) { btn.addEventListener('click', requestFlowzenRecommend); }

    // Public API
    window.flowzenPanel = {
        requestFlowzenStatus: requestFlowzenStatus,
        requestFlowzenDiaryEntries: requestFlowzenDiaryEntries,
        requestFlowzenRecommend: requestFlowzenRecommend,
        updateFlowzenPanel: updateFlowzenPanel,
        renderDiaryEntries: renderDiaryEntries,
        addSingleDiaryEntry: addSingleDiaryEntry
    };
})();
