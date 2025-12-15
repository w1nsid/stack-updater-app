/**
 * Accessibility Module
 * 
 * Provides screen reader announcements and accessibility utilities.
 */

export class Announcer {
    constructor() {
        this.region = null;
        this.init();
    }

    init() {
        // Find or create live region
        this.region = document.getElementById('aria-live-region');

        if (!this.region) {
            this.region = document.createElement('div');
            this.region.id = 'aria-live-region';
            this.region.setAttribute('aria-live', 'polite');
            this.region.setAttribute('aria-atomic', 'true');
            this.region.className = 'sr-only';
            document.body.appendChild(this.region);
        }
    }

    /**
     * Announce a message to screen readers
     * @param {string} message 
     * @param {string} priority - 'polite' or 'assertive'
     */
    announce(message, priority = 'polite') {
        if (!this.region) return;

        this.region.setAttribute('aria-live', priority);

        // Clear and set to trigger announcement
        this.region.textContent = '';

        // Use requestAnimationFrame to ensure the clear is processed
        requestAnimationFrame(() => {
            this.region.textContent = message;
        });
    }

    /**
     * Announce an error (assertive)
     * @param {string} message 
     */
    announceError(message) {
        this.announce(message, 'assertive');
    }

    /**
     * Announce a success message
     * @param {string} message 
     */
    announceSuccess(message) {
        this.announce(message, 'polite');
    }
}
