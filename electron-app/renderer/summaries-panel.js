/**
 * Summaries Panel — Toggle, close, and add idea summaries.
 * Extracted from index.html inline script.
 */
(function() {
    'use strict';

    const summariesToggle = document.getElementById('summaries-toggle');
    const summariesPanel = document.getElementById('summaries-panel');
    const summariesClose = document.getElementById('summaries-close');
    const summariesContent = document.getElementById('summaries-content');

    // Store summaries in memory
    let summaries = [];

    // Toggle summaries panel
    if (summariesToggle) {
        summariesToggle.onclick = function() {
            summariesPanel.classList.toggle('hidden');
            summariesToggle.classList.toggle('hidden');
        };
    }

    // Close summaries panel
    if (summariesClose) {
        summariesClose.onclick = function() {
            summariesPanel.classList.add('hidden');
            summariesToggle.classList.remove('hidden');
        };
    }

    // Add a summary to the panel
    function addSummary(ideaTitle, summaryText, style, nodeCount) {
        style = style || 'concise';
        nodeCount = nodeCount || 0;

        // Remove "no summaries" message if present
        const noSummaries = summariesContent.querySelector('.no-summaries');
        if (noSummaries) {
            noSummaries.remove();
        }

        // Check if this idea already has a summary (update instead of add)
        const existingCard = summariesContent.querySelector('[data-idea-title="' + ideaTitle + '"]');
        if (existingCard) {
            existingCard.querySelector('.summary-text').textContent = summaryText;
            existingCard.querySelector('.summary-meta').textContent = 'Style: ' + style + ' \u2022 ' + nodeCount + ' notes \u2022 Updated just now';
            existingCard.classList.add('updated');
            setTimeout(function() { existingCard.classList.remove('updated'); }, 1000);
            return;
        }

        // Create new summary card using DOM methods
        const card = document.createElement('div');
        card.className = 'summary-card';
        card.dataset.ideaTitle = ideaTitle;

        const titleDiv = document.createElement('div');
        titleDiv.className = 'summary-title';
        const iconSpan = document.createElement('span');
        iconSpan.className = 'summary-title-icon';
        iconSpan.textContent = '\uD83D\uDCDD';
        titleDiv.appendChild(iconSpan);
        titleDiv.appendChild(document.createTextNode(' ' + ideaTitle));
        card.appendChild(titleDiv);

        const textDiv = document.createElement('div');
        textDiv.className = 'summary-text';
        textDiv.textContent = summaryText;
        card.appendChild(textDiv);

        const metaDiv = document.createElement('div');
        metaDiv.className = 'summary-meta';
        metaDiv.textContent = 'Style: ' + style + ' \u2022 ' + nodeCount + ' notes \u2022 Just now';
        card.appendChild(metaDiv);

        // Add to top of list
        summariesContent.insertBefore(card, summariesContent.firstChild);

        // Store in memory
        summaries.push({ ideaTitle: ideaTitle, summaryText: summaryText, style: style, nodeCount: nodeCount, timestamp: Date.now() });

        // Show panel if hidden
        if (summariesPanel.classList.contains('hidden')) {
            summariesPanel.classList.remove('hidden');
            summariesToggle.classList.add('hidden');
        }

        // Flash animation
        card.classList.add('updated');
        setTimeout(function() { card.classList.remove('updated'); }, 1000);
    }

    // Public API
    window.summariesPanel = {
        addSummary: addSummary
    };
})();
