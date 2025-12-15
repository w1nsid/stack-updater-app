/**
 * Button Controller Module
 * 
 * Manages button loading states and interactions.
 */

export class ButtonController {
    constructor(api, store, announcer) {
        this.announcer = announcer;
        this.loadingButtons = new Set();
    }

    /**
     * Execute an action with button loading state
     * @param {HTMLElement} button 
     * @param {string} loadingText 
     * @param {Function} action 
     */
    async withLoading(button, loadingText, action) {
        if (!button || this.loadingButtons.has(button)) return;

        this.loadingButtons.add(button);
        const originalContent = button.innerHTML;
        const originalDisabled = button.disabled;

        try {
            button.disabled = true;
            button.classList.add('loading');

            // Set loading content with spinner
            const icon = button.querySelector('i');
            if (icon) {
                icon.setAttribute('data-lucide', 'loader-2');
                icon.classList.add('icon', 'spin');
            }

            const textSpan = button.querySelector('span');
            if (textSpan && loadingText) {
                textSpan.textContent = loadingText;
            }

            this.refreshIcons();

            await action();

        } catch (error) {
            console.error('[ButtonController] Action failed:', error);
            this.announcer?.announceError(error.message || 'Action failed');
            throw error;
        } finally {
            button.disabled = originalDisabled;
            button.classList.remove('loading');
            button.innerHTML = originalContent;
            this.refreshIcons();
            this.loadingButtons.delete(button);
        }
    }

    /**
     * Refresh Lucide icons
     */
    refreshIcons() {
        if (window.lucide?.createIcons) {
            window.lucide.createIcons();
        }
    }
}
