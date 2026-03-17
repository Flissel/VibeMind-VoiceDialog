/**
 * eyeTerm Camera Preview Manager for VibeMind Desktop Space
 *
 * Embeds the eyeTerm MJPEG camera feed as a small BrowserView panel
 * in the bottom-right corner of the Desktop Space.
 *
 * Pattern: follows clawport-manager.js (BrowserView overlay).
 */

const { BrowserView } = require('electron');
const path = require('path');

class EyeTermManager {
  constructor(mainWindow) {
    this.mainWindow = mainWindow;
    this.eyetermView = null;
    this.isVisible = false;

    // Panel size and position
    this.panelWidth = 320;
    this.panelHeight = 240;
    this.margin = 12;

    // MJPEG stream URL (Python camera_server.py)
    this.streamPort = parseInt(process.env.EYETERM_STREAM_PORT || '8099', 10);
    this.streamUrl = `http://127.0.0.1:${this.streamPort}`;

    // Listen for window resize
    if (this.mainWindow) {
      this.mainWindow.on('resize', () => {
        if (this.isVisible && this.eyetermView) {
          this.updateBounds();
        }
      });
    }
  }

  /**
   * Create the BrowserView for the eyeTerm camera preview
   */
  createView() {
    if (this.eyetermView) return this.eyetermView;

    this.eyetermView = new BrowserView({
      webPreferences: {
        preload: path.join(__dirname, 'eyeterm-preload.js'),
        contextIsolation: true,
        nodeIntegration: false,
        sandbox: false,
      },
    });

    // Load simple HTML page with MJPEG stream
    const html = `data:text/html;charset=utf-8,${encodeURIComponent(this._getHTML())}`;
    this.eyetermView.webContents.loadURL(html);

    this.eyetermView.webContents.on('did-finish-load', () => {
      console.log('[EyeTermManager] Camera preview loaded');
    });

    return this.eyetermView;
  }

  /**
   * Generate the HTML for the camera preview panel
   */
  _getHTML() {
    return `<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
      background: #1a1a1e;
      overflow: hidden;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    }
    .container {
      position: relative;
      width: 100vw;
      height: 100vh;
    }
    .header {
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      height: 24px;
      background: rgba(0,0,0,0.7);
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0 8px;
      z-index: 10;
      -webkit-app-region: drag;
    }
    .header-title {
      color: #00d4ff;
      font-size: 11px;
      font-weight: 600;
      letter-spacing: 0.5px;
    }
    .header-btn {
      background: none;
      border: none;
      color: #888;
      cursor: pointer;
      font-size: 14px;
      -webkit-app-region: no-drag;
    }
    .header-btn:hover { color: #fff; }
    img {
      width: 100%;
      height: 100%;
      object-fit: cover;
    }
    .status {
      position: absolute;
      bottom: 4px;
      right: 8px;
      font-size: 10px;
      color: #0c0;
      text-shadow: 0 0 4px rgba(0,204,0,0.5);
    }
    .offline {
      display: flex;
      align-items: center;
      justify-content: center;
      width: 100%;
      height: 100%;
      color: #666;
      font-size: 12px;
    }
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <span class="header-title">eyeTerm</span>
      <button class="header-btn" onclick="window.vibemindEyeterm.toggle()" title="Close">✕</button>
    </div>
    <img id="feed" src="${this.streamUrl}/stream"
         onerror="this.style.display='none';document.getElementById('offline').style.display='flex'"
         onload="this.style.display='block';document.getElementById('offline').style.display='none'">
    <div id="offline" class="offline" style="display:none">Camera offline</div>
    <div class="status" id="status">● LIVE</div>
  </div>
</body>
</html>`;
  }

  /**
   * Show the eyeTerm camera preview panel
   */
  show() {
    if (!this.mainWindow) {
      console.error('[EyeTermManager] No main window available');
      return;
    }

    if (!this.eyetermView) {
      this.createView();
    }

    this.mainWindow.addBrowserView(this.eyetermView);
    this.updateBounds();
    this.isVisible = true;
    console.log('[EyeTermManager] Camera preview shown');
  }

  /**
   * Hide the eyeTerm camera preview panel
   */
  hide() {
    if (!this.mainWindow || !this.eyetermView) return;

    this.mainWindow.removeBrowserView(this.eyetermView);
    this.isVisible = false;
    console.log('[EyeTermManager] Camera preview hidden');
  }

  /**
   * Toggle visibility
   */
  toggle() {
    if (this.isVisible) {
      this.hide();
    } else {
      this.show();
    }
    return this.isVisible;
  }

  /**
   * Update panel bounds — bottom-right corner
   */
  updateBounds() {
    if (!this.mainWindow || !this.eyetermView) return;

    const bounds = this.mainWindow.getContentBounds();
    this.eyetermView.setBounds({
      x: bounds.width - this.panelWidth - this.margin,
      y: bounds.height - this.panelHeight - this.margin,
      width: this.panelWidth,
      height: this.panelHeight,
    });
  }

  /**
   * Check if eyeTerm is currently visible
   */
  getIsVisible() {
    return this.isVisible;
  }

  /**
   * Get the stream status
   */
  getStatus() {
    return {
      visible: this.isVisible,
      streamUrl: this.streamUrl,
      port: this.streamPort,
    };
  }

  /**
   * Reload the camera feed
   */
  reload() {
    if (this.eyetermView) {
      this.eyetermView.webContents.reload();
    }
  }

  /**
   * Destroy the eyeTerm view
   */
  destroy() {
    if (this.eyetermView) {
      this.hide();
      this.eyetermView = null;
    }
  }
}

module.exports = EyeTermManager;
