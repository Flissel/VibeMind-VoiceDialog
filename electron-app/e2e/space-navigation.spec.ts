import { test, expect } from './fixtures';

test.describe('Space Navigation', () => {
    test('video space embeds the Laura renderer', async ({ electronApp, mainPage }) => {
        await mainPage.evaluate(() => {
            const vibemind = (window as Window & {
                vibemind?: { showVideo?: () => void };
            }).vibemind;

            if (typeof vibemind?.showVideo !== 'function') {
                throw new Error('window.vibemind.showVideo is not available');
            }

            vibemind.showVideo();
        });

        const rendererState = await electronApp.evaluate(async ({ BrowserWindow }) => {
            const deadline = Date.now() + 20_000;
            let lastState: {
                attached: boolean;
                title: string | null;
                titleVisible: boolean;
                hasLauraGetServiceInfo: boolean;
                hasLegacyVideoApi: boolean;
            } = {
                attached: false,
                title: null,
                titleVisible: false,
                hasLauraGetServiceInfo: false,
                hasLegacyVideoApi: false,
            };

            while (Date.now() < deadline) {
                const view = BrowserWindow.getAllWindows()
                    .map((window) => window.getBrowserView())
                    .find((candidate) => candidate !== null);

                if (view && !view.webContents.isDestroyed()) {
                    try {
                        lastState = await view.webContents.executeJavaScript(`
                            (() => {
                                const heading = Array.from(document.querySelectorAll('h1'))
                                    .find((element) => element.textContent?.trim() === 'Laura') ?? null;
                                const style = heading ? getComputedStyle(heading) : null;
                                const titleVisible = Boolean(
                                    heading
                                    && style
                                    && style.display !== 'none'
                                    && style.visibility !== 'hidden'
                                    && Number(style.opacity) > 0
                                    && heading.getClientRects().length > 0
                                );

                                return {
                                    attached: true,
                                    title: heading?.textContent?.trim() ?? null,
                                    titleVisible,
                                    hasLauraGetServiceInfo:
                                        typeof window.laura?.getServiceInfo === 'function',
                                    hasLegacyVideoApi:
                                        typeof window.vibemindVideo !== 'undefined',
                                };
                            })()
                        `, true);

                        if (
                            lastState.titleVisible
                            && lastState.hasLauraGetServiceInfo
                            && !lastState.hasLegacyVideoApi
                        ) {
                            return lastState;
                        }
                    } catch {
                        lastState.attached = true;
                    }
                }

                await new Promise((resolve) => setTimeout(resolve, 100));
            }

            return lastState;
        });

        expect(rendererState).toEqual({
            attached: true,
            title: 'Laura',
            titleVisible: true,
            hasLauraGetServiceInfo: true,
            hasLegacyVideoApi: false,
        });
    });

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
