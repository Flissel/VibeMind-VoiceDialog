import { test, expect } from './fixtures';

test.describe('App Launch', () => {
    test('main window appears', async ({ electronApp }) => {
        const windowCount = (await electronApp.windows()).length;
        expect(windowCount).toBeGreaterThanOrEqual(1);
    });

    test('renderer loads without critical console errors', async ({ mainPage }) => {
        const errors: string[] = [];
        mainPage.on('console', msg => {
            if (msg.type() === 'error') errors.push(msg.text());
        });

        // Give the renderer time to initialize
        await mainPage.waitForTimeout(3000);

        // Filter out expected/benign errors
        const criticalErrors = errors.filter(e =>
            !e.includes('Sentry') &&
            !e.includes('net::') &&
            !e.includes('favicon') &&
            !e.includes('DevTools') &&
            !e.includes('Extension') &&
            !e.includes('404')
        );
        expect(criticalErrors).toHaveLength(0);
    });

    test('vibemind preload API is exposed', async ({ electronApp, mainPage }) => {
        // Debug: find the right window with the preload API
        const allWindows = electronApp.windows();
        let targetPage = mainPage;
        for (const win of allWindows) {
            const hasVibemind = await win.evaluate(() => !!(window as any).vibemind).catch(() => false);
            if (hasVibemind) {
                targetPage = win;
                break;
            }
        }

        const apiCheck = await targetPage.evaluate(() => {
            const v = (window as any).vibemind;
            if (!v) return { exists: false, methods: [], url: window.location.href };
            return {
                exists: true,
                methods: Object.keys(v),
                url: window.location.href,
            };
        });

        expect(apiCheck.exists).toBe(true);
        expect(apiCheck.methods).toContain('startVoice');
        expect(apiCheck.methods).toContain('stopVoice');
        expect(apiCheck.methods).toContain('navigateToSpace');
    });
});
