import { test, expect } from './fixtures';

test.describe('Space Navigation', () => {
    test('navigateToSpace API is callable', async ({ mainPage }) => {
        // Verify the navigation API exists and can be called without crashing
        const result = await mainPage.evaluate(async () => {
            try {
                const v = (window as any).vibemind;
                if (typeof v.navigateToSpace === 'function') {
                    // Call with a valid space name
                    v.navigateToSpace('desktop');
                    return { success: true };
                }
                return { success: false, reason: 'navigateToSpace not a function' };
            } catch (e: any) {
                return { success: false, reason: e.message };
            }
        });
        expect(result.success).toBe(true);
    });

    test('voice start/stop API exists', async ({ mainPage }) => {
        const apis = await mainPage.evaluate(() => {
            const v = (window as any).vibemind;
            return {
                startVoice: typeof v.startVoice === 'function',
                stopVoice: typeof v.stopVoice === 'function',
                sendChatMessage: typeof v.sendChatMessage === 'function',
            };
        });
        expect(apis.startVoice).toBe(true);
        expect(apis.stopVoice).toBe(true);
        expect(apis.sendChatMessage).toBe(true);
    });
});
