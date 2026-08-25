import { test as base, _electron as electron, ElectronApplication, Page } from '@playwright/test';
import path from 'path';

type VibeMindFixtures = {
    electronApp: ElectronApplication;
    mainPage: Page;
    mainProcessLogs: () => string;
};

const mainProcessLogReaders = new WeakMap<ElectronApplication, () => string>();

export const test = base.extend<VibeMindFixtures>({
    electronApp: async ({}, use) => {
        // Remove ELECTRON_RUN_AS_NODE (set by Claude Code / VSCode terminals)
        // which forces Electron to behave as plain Node.js without GUI.
        const env = { ...process.env };
        delete env.ELECTRON_RUN_AS_NODE;

        const app = await electron.launch({
            args: [path.join(__dirname, '..')],
            env: {
                ...env,
                LAURA_TOKEN: '',
                LAURA_URL: 'http://127.0.0.1:0',
                NODE_ENV: 'test',
                FORCE_SYNC_MODE: 'true',
                FAST_STARTUP: 'true',
                VIBEMIND_E2E_ISOLATED_STARTUP: 'true',
                USE_TASK_MEMORY: 'false',
                USE_CONVERSATION_MEMORY: 'false',
                USE_USER_PROFILES: 'false',
                USE_RAG_CLASSIFIER: 'false',
                SCHEDULE_ENABLED: 'false',
                MINIBOOK_ENABLED: 'false',
                USE_ZEROCLAW: 'false',
                N8N_ENABLED: 'false',
                MIROFISH_ENABLED: 'false',
                SKIP_BRAIN_SPAWN: 'true',
                EYETERM_ENABLED: 'false',
            },
            timeout: 60_000,
        });

        let output = '';
        const append = (chunk: Buffer | string): void => {
            output = `${output}${String(chunk)}`.slice(-64_000);
        };
        app.process().stdout?.on('data', append);
        app.process().stderr?.on('data', append);
        mainProcessLogReaders.set(app, () => output);

        // Wait for the first window to appear
        await app.firstWindow();
        await use(app);
        await app.close();
        mainProcessLogReaders.delete(app);
    },

    mainProcessLogs: async ({ electronApp }, use) => {
        const read = mainProcessLogReaders.get(electronApp);
        if (!read) throw new Error('main process log reader was not installed');
        await use(read);
    },

    mainPage: async ({ electronApp }, use) => {
        // Find the app window with the vibemind preload API.
        // Playwright may return DevTools or other windows first.
        const allWindows = electronApp.windows();
        let mainPage: Page | null = null;

        for (const win of allWindows) {
            const hasVibemind = await win.evaluate(() => !!(window as any).vibemind).catch(() => false);
            if (hasVibemind) {
                mainPage = win;
                break;
            }
        }

        // Fallback: if no window has vibemind yet, wait for a new window
        if (!mainPage) {
            mainPage = await electronApp.firstWindow();
            await mainPage.waitForLoadState('domcontentloaded');
            // Try once more after DOM is loaded
            const hasVibemind = await mainPage.evaluate(() => !!(window as any).vibemind).catch(() => false);
            if (!hasVibemind) {
                // Last resort: wait a bit and check all windows again
                await mainPage.waitForTimeout(1000);
                for (const win of electronApp.windows()) {
                    const has = await win.evaluate(() => !!(window as any).vibemind).catch(() => false);
                    if (has) { mainPage = win; break; }
                }
            }
        }

        await mainPage.waitForLoadState('domcontentloaded');
        await use(mainPage);
    },
});

export { expect } from '@playwright/test';
