/**
 * White Paper Panel — Display, export, and print white papers with markdown rendering.
 * Extracted from index.html inline script.
 *
 * Dependency: window.showTranscript (defined in index.html inline script)
 *
 * Note: innerHTML usage for rendered markdown is safe — content is first HTML-escaped
 * by markdownToHtml() before any markdown syntax is converted to HTML tags.
 */
(function() {
    'use strict';

    const whitepaperToggle = document.getElementById('whitepaper-toggle');
    const whitepaperPanel = document.getElementById('whitepaper-panel');
    const whitepaperClose = document.getElementById('whitepaper-close');
    const whitepaperContent = document.getElementById('whitepaper-content');
    const whitepaperTitle = document.getElementById('whitepaper-title');
    const whitepaperMeta = document.getElementById('whitepaper-meta');

    // Store raw markdown for export
    let currentWhitepaperMarkdown = '';

    // Toggle white paper panel
    if (whitepaperToggle) {
        whitepaperToggle.onclick = function() {
            whitepaperPanel.classList.toggle('hidden');
            whitepaperToggle.classList.toggle('hidden');
        };
    }

    // Close white paper panel
    if (whitepaperClose) {
        whitepaperClose.onclick = function() {
            whitepaperPanel.classList.add('hidden');
            whitepaperToggle.classList.remove('hidden');
        };
    }

    // Print button - opens print dialog
    var printBtn = document.getElementById('whitepaper-print');
    if (printBtn) {
        printBtn.addEventListener('click', function() {
            window.print();
        });
    }

    // Copy button - copies markdown to clipboard
    var copyBtn = document.getElementById('whitepaper-copy');
    if (copyBtn) {
        copyBtn.addEventListener('click', async function() {
            if (currentWhitepaperMarkdown) {
                try {
                    await navigator.clipboard.writeText(currentWhitepaperMarkdown);
                    if (window.showTranscript) {
                        window.showTranscript('System', 'White Paper markdown copied to clipboard!');
                    }
                } catch(e) {
                    console.error('Failed to copy:', e);
                }
            }
        });
    }

    // Export button - downloads as .md file
    var exportBtn = document.getElementById('whitepaper-export');
    if (exportBtn) {
        exportBtn.addEventListener('click', function() {
            if (currentWhitepaperMarkdown) {
                var title = whitepaperTitle.textContent || 'white-paper';
                var filename = title.toLowerCase().replace(/[^a-z0-9]+/g, '-') + '.md';
                var blob = new Blob([currentWhitepaperMarkdown], { type: 'text/markdown' });
                var url = URL.createObjectURL(blob);
                var a = document.createElement('a');
                a.href = url;
                a.download = filename;
                a.click();
                URL.revokeObjectURL(url);
                if (window.showTranscript) {
                    window.showTranscript('System', 'Exported as ' + filename);
                }
            }
        });
    }

    /**
     * Simple Markdown to HTML converter
     * Supports: headings, bold, italic, lists, code, blockquotes
     */
    function markdownToHtml(markdown) {
        if (!markdown) return '';

        var html = markdown
            // Escape HTML first (prevents XSS)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            // Headings
            .replace(/^### (.+)$/gm, '<h3>$1</h3>')
            .replace(/^## (.+)$/gm, '<h2>$1</h2>')
            .replace(/^# (.+)$/gm, '<h1>$1</h1>')
            // Bold and italic
            .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.+?)\*/g, '<em>$1</em>')
            // Code (inline)
            .replace(/`([^`]+)`/g, '<code>$1</code>')
            // Blockquotes
            .replace(/^&gt; (.+)$/gm, '<blockquote>$1</blockquote>')
            // Unordered lists
            .replace(/^- (.+)$/gm, '<li>$1</li>')
            .replace(/(<li>.*<\/li>\n?)+/g, '<ul>$&</ul>')
            // Ordered lists
            .replace(/^\d+\. (.+)$/gm, '<li>$1</li>')
            // Paragraphs (double newlines)
            .replace(/\n\n/g, '</p><p>')
            // Single newlines within paragraphs
            .replace(/\n/g, '<br>');

        // Wrap in paragraph tags if not starting with block element
        if (!html.startsWith('<h') && !html.startsWith('<ul') && !html.startsWith('<blockquote')) {
            html = '<p>' + html + '</p>';
        }

        // Clean up empty paragraphs
        html = html.replace(/<p><\/p>/g, '').replace(/<p><br>/g, '<p>');

        return html;
    }

    /**
     * Display White Paper content in the panel
     */
    function displayWhitePaper(title, markdownContent, nodeCount, maxDepth) {
        // Store raw markdown
        currentWhitepaperMarkdown = markdownContent;

        // Update title
        if (whitepaperTitle) {
            whitepaperTitle.textContent = title || 'White Paper';
        }

        // Convert markdown to HTML and display
        var htmlContent = markdownToHtml(markdownContent);
        var a4Container = whitepaperContent ? whitepaperContent.querySelector('.whitepaper-a4') : null;
        if (a4Container) {
            a4Container.innerHTML = htmlContent;
        }

        // Update meta info
        if (whitepaperMeta) {
            whitepaperMeta.textContent = nodeCount + ' ideas \u2022 depth ' + maxDepth + ' \u2022 Just now';
        }

        // Show panel
        if (whitepaperPanel) whitepaperPanel.classList.remove('hidden');
        if (whitepaperToggle) whitepaperToggle.classList.add('hidden');

        // Flash animation
        if (a4Container) {
            a4Container.classList.add('updated');
            setTimeout(function() { a4Container.classList.remove('updated'); }, 1000);
        }
    }

    // Public API
    window.whitepaperPanel = {
        displayWhitePaper: displayWhitePaper
    };
})();
