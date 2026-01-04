// Simple Electron test
console.log('Starting...');
console.log('Process type:', process.type);
console.log('Process versions:', process.versions);

try {
    const { app, BrowserWindow } = require('electron');
    console.log('app type:', typeof app);
    console.log('BrowserWindow type:', typeof BrowserWindow);

    if (!app) {
        console.error('app is undefined!');
        process.exit(1);
    }

    app.whenReady().then(() => {
        console.log('App ready!');
        const win = new BrowserWindow({
            width: 800,
            height: 600,
            webPreferences: {
                nodeIntegration: true
            }
        });
        win.loadURL('data:text/html,<h1>Hello Electron!</h1>');
        console.log('Window created!');
    });

    app.on('window-all-closed', () => {
        console.log('All windows closed');
        app.quit();
    });
} catch (err) {
    console.error('Error:', err);
}
