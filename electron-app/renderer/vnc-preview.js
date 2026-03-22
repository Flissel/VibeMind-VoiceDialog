/**
 * VNC Live Preview Panel — Show/hide VNC preview, loading states, control buttons.
 * Extracted from index.html inline script.
 *
 * Dependency: window.vibemind.stopProjectPreview (preload IPC)
 */
(function() {
    'use strict';

    var vncContainer = document.getElementById('vnc-preview-container');
    var vncFrame = document.getElementById('vnc-frame');
    var vncLoading = document.getElementById('vnc-loading');
    var vncProjectTitle = document.getElementById('vnc-project-title');
    var vncStatus = document.getElementById('vnc-status');
    var vncLoadingDetails = document.getElementById('vnc-loading-details');

    var currentPreviewProjectId = null;

    function showVncLoading(show, projectTitle) {
        projectTitle = projectTitle || 'Project';
        if (vncContainer) {
            vncContainer.classList.remove('hidden');
        }
        if (vncLoading) {
            vncLoading.style.display = show ? 'flex' : 'none';
        }
        if (vncProjectTitle) {
            vncProjectTitle.textContent = projectTitle;
        }
        if (vncStatus) {
            vncStatus.textContent = show ? 'Loading...' : 'Ready';
            vncStatus.className = 'vnc-status ' + (show ? 'loading' : 'ready');
        }
    }

    function updateVncLoadingDetails(text) {
        if (vncLoadingDetails) {
            vncLoadingDetails.textContent = text;
        }
    }

    function updateVncStatus(text) {
        if (vncStatus) {
            vncStatus.textContent = text;
            vncStatus.className = 'vnc-status ' + (text.indexOf('\u2713') !== -1 ? 'ready' : text.indexOf('\u2717') !== -1 ? 'error' : 'loading');
        }
    }

    function showVncPreview(url, projectTitle, projectId) {
        currentPreviewProjectId = projectId;

        if (vncContainer) {
            vncContainer.classList.remove('hidden');
        }
        if (vncFrame) {
            vncFrame.src = url;
        }
        if (vncProjectTitle) {
            vncProjectTitle.textContent = projectTitle || 'Live Preview';
        }
        if (vncStatus) {
            vncStatus.textContent = 'Running';
        }

        // Update Space Indicator (top right)
        var spaceIndicator = document.getElementById('space-indicator');
        if (spaceIndicator) spaceIndicator.classList.remove('hidden');
    }

    function hideVncPreview() {
        if (vncContainer) {
            vncContainer.classList.add('hidden');
        }
        if (vncFrame) {
            vncFrame.src = '';
        }
        currentPreviewProjectId = null;
    }

    // VNC Control Buttons
    var refreshBtn = document.getElementById('vnc-refresh-btn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', function() {
            if (vncFrame && vncFrame.src) {
                var currentSrc = vncFrame.src;
                vncFrame.src = '';
                setTimeout(function() {
                    vncFrame.src = currentSrc;
                }, 100);
            }
        });
    }

    var closeBtn = document.getElementById('vnc-close-btn');
    if (closeBtn) {
        closeBtn.addEventListener('click', function() {
            if (currentPreviewProjectId) {
                window.vibemind.stopProjectPreview(currentPreviewProjectId);
            }
            hideVncPreview();
        });
    }

    var fullscreenBtn = document.getElementById('vnc-fullscreen-btn');
    if (fullscreenBtn) {
        fullscreenBtn.addEventListener('click', function() {
            if (vncFrame) {
                if (vncFrame.requestFullscreen) {
                    vncFrame.requestFullscreen();
                } else if (vncFrame.webkitRequestFullscreen) {
                    vncFrame.webkitRequestFullscreen();
                }
            }
        });
    }

    // Public API
    window.vncPreview = {
        showVncLoading: showVncLoading,
        updateVncLoadingDetails: updateVncLoadingDetails,
        updateVncStatus: updateVncStatus,
        showVncPreview: showVncPreview,
        hideVncPreview: hideVncPreview
    };
})();
