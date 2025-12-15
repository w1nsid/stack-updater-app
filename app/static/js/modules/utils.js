/**
 * Utility Functions Module
 * 
 * Shared utilities used across multiple modules.
 */

/**
 * Status class mapping from API status strings to CSS classes
 */
const STATUS_MAP = {
    'processing': 'processing',
    'preparing': 'processing',
    'updated': 'ok',
    'outdated': 'warn',
    'skipped': 'unknown',
    'error': 'error'
};

/**
 * Get CSS status class from API status string
 * @param {string} status - Raw status from API
 * @returns {string} CSS class name (ok, warn, error, processing, unknown)
 */
export function getStatusClass(status) {
    if (!status) return 'unknown';

    const normalized = status.toString().trim().toLowerCase();
    return STATUS_MAP[normalized] || 'unknown';
}

/**
 * Get icon name for a status class
 * @param {string} statusClass 
 * @returns {string} Lucide icon name
 */
export function getStatusIcon(statusClass) {
    const icons = {
        ok: 'check-circle',
        warn: 'alert-triangle',
        error: 'x-circle',
        processing: 'loader-2',
        unknown: 'help-circle'
    };
    return icons[statusClass] || 'help-circle';
}

/**
 * Refresh Lucide icons on the page
 */
export function refreshIcons() {
    if (window.lucide?.createIcons) {
        window.lucide.createIcons();
    }
}

/**
 * Escape HTML to prevent XSS
 * @param {string} str 
 * @returns {string}
 */
export function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

/**
 * Format a date string for display
 * @param {string} dateStr 
 * @returns {string}
 */
export function formatDate(dateStr) {
    if (!dateStr) return '—';

    try {
        const date = new Date(dateStr);
        return date.toLocaleString(undefined, {
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    } catch {
        return dateStr;
    }
}
