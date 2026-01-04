// Test script to debug electron issue
console.log('Testing Electron main process...');
console.log('process.type:', process.type);
console.log('process.versions.electron:', process.versions.electron);

// The electron npm package exports the path, not the actual API
// In Electron main process, we need to use the built-in require
// which should resolve 'electron' to the built-in module
// But apparently our require is resolving to node_modules first

// Force use of built-in electron module
let electron;
try {
    // Try process.electronBinding (available in newer Electron)
    if (process.electronBinding) {
        console.log('Using electronBinding approach');
        const electronPath = process.electronBinding('electron');
        console.log('electronPath:', electronPath);
    }
    
    // Check if this is the main process by process.type
    // But process.type is only set AFTER app is fully initialized
    
    // Try require from the internal Electron path
    const Module = require('module');
    const originalResolve = Module._resolveFilename;
    
    // Temporarily override module resolution for 'electron'
    Module._resolveFilename = function(request, parent, isMain, options) {
        if (request === 'electron') {
            return 'electron'; // Return as-is, let Electron's built-in resolver handle it
        }
        return originalResolve.call(this, request, parent, isMain, options);
    };
    
    // Clear the cache for electron
    delete require.cache[require.resolve('electron')];
    
    // Now require electron again
    electron = require('electron');
    
    // Restore original resolver
    Module._resolveFilename = originalResolve;
    
    console.log('After override - electron type:', typeof electron);
    console.log('After override - electron.app:', electron.app);
    
} catch (e) {
    console.error('Error with override approach:', e);
}

// Try a different approach - use process.binding
console.log('\n--- Trying process approach ---');
console.log('process keys:', Object.keys(process).filter(k => k.toLowerCase().includes('electron')));

// The real solution: in Electron main process, 'electron' should be a built-in module
// The npm package only returns the binary path when run under Node.js
// If require('electron') returns a string, we're not in a proper Electron context

if (typeof electron === 'string' || !electron.app) {
    console.log('\nERROR: Not running in proper Electron main process context');
    console.log('The npm "electron" package is shadowing the built-in module');
    process.exit(1);
} else {
    electron.app.whenReady().then(() => {
        console.log('App is ready!');
        electron.app.quit();
    });
}