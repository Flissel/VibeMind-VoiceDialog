/**
 * Dashboard Manager for VibeMind
 *
 * Manages the Coding Engine Dashboard as a BrowserView overlay.
 * Shows the React-based dashboard when user navigates to Project Space.
 */

const { BrowserView } = require('electron');
const path = require('path');

class DashboardManager {
  constructor(mainWindow) {
    this.mainWindow = mainWindow;
    this.dashboardView = null;
    this.isVisible = false;

    // Dashboard source - use built files or dev server
    this.dashboardPath = process.env.DASHBOARD_DEV_URL ||
      path.join(__dirname, '..', '..', '..', 'Coding_engine', 'dashboard-app', 'dist-embedded', 'index.html');

    this.isDev = !!process.env.DASHBOARD_DEV_URL;

    // Titlebar height to offset the view
    this.titlebarHeight = 32;

    // Listen for window resize
    if (this.mainWindow) {
      this.mainWindow.on('resize', () => {
        if (this.isVisible && this.dashboardView) {
          this.updateBounds();
        }
      });
    }
  }

  /**
   * Create the BrowserView for the dashboard
   */
  createView() {
    if (this.dashboardView) {
      return this.dashboardView;
    }

    this.dashboardView = new BrowserView({
      webPreferences: {
        preload: path.join(__dirname, 'dashboard-preload.js'),
        contextIsolation: true,
        nodeIntegration: false,
        sandbox: false,
      },
    });

    // Load the dashboard
    if (this.isDev) {
      console.log('[DashboardManager] Loading from dev server:', process.env.DASHBOARD_DEV_URL);
      this.dashboardView.webContents.loadURL(process.env.DASHBOARD_DEV_URL);
    } else {
      console.log('[DashboardManager] Loading from file:', this.dashboardPath);
      this.dashboardView.webContents.loadFile(this.dashboardPath);
    }

    // Open DevTools in development
    if (process.env.NODE_ENV === 'development' || this.isDev) {
      this.dashboardView.webContents.openDevTools({ mode: 'detach' });
    }

    return this.dashboardView;
  }

  /**
   * Show the dashboard overlay
   */
  show() {
    if (!this.mainWindow) {
      console.error('[DashboardManager] No main window available');
      return;
    }

    // Create view if not exists
    if (!this.dashboardView) {
      this.createView();
    }

    // Add view to window
    this.mainWindow.setBrowserView(this.dashboardView);

    // Position the view
    this.updateBounds();

    this.isVisible = true;
    console.log('[DashboardManager] Dashboard shown');
  }

  /**
   * Hide the dashboard overlay
   */
  hide() {
    if (!this.mainWindow || !this.dashboardView) {
      return;
    }

    // Remove view from window
    this.mainWindow.setBrowserView(null);

    this.isVisible = false;
    console.log('[DashboardManager] Dashboard hidden');
  }

  /**
   * Toggle dashboard visibility
   */
  toggle() {
    if (this.isVisible) {
      this.hide();
    } else {
      this.show();
    }
  }

  /**
   * Update BrowserView bounds to match window size
   */
  updateBounds() {
    if (!this.mainWindow || !this.dashboardView) {
      return;
    }

    const bounds = this.mainWindow.getContentBounds();

    this.dashboardView.setBounds({
      x: 0,
      y: this.titlebarHeight,
      width: bounds.width,
      height: bounds.height - this.titlebarHeight,
    });
  }

  /**
   * Check if dashboard is currently visible
   */
  getIsVisible() {
    return this.isVisible;
  }

  /**
   * Reload the dashboard
   */
  reload() {
    if (this.dashboardView) {
      this.dashboardView.webContents.reload();
    }
  }

  /**
   * Send message to dashboard
   */
  sendMessage(channel, data) {
    if (this.dashboardView) {
      this.dashboardView.webContents.send(channel, data);
    }
  }

  /**
   * Destroy the dashboard view
   */
  destroy() {
    if (this.dashboardView) {
      this.hide();
      // Note: BrowserView doesn't have a destroy method in newer Electron
      // Just remove reference
      this.dashboardView = null;
    }
  }
}

module.exports = DashboardManager;
