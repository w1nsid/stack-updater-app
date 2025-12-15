/**
 * Table Renderer Module
 * 
 * Handles rendering and updating the stacks table.
 */

export class TableRenderer {
    constructor(store, onAction) {
        this.store = store;
        this.onAction = onAction;
        this.tbody = document.getElementById('stackTableBody');
    }

    /**
     * Render the entire table
     * @param {Array} stacks 
     */
    render(stacks) {
        if (!this.tbody) return;

        this.tbody.innerHTML = '';

        if (stacks.length === 0) {
            this.renderEmptyState();
            return;
        }

        stacks.forEach(stack => {
            const row = this.createRow(stack);
            this.tbody.appendChild(row);
        });

        this.refreshIcons();
    }

    /**
     * Render empty state message
     */
    renderEmptyState() {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td colspan="5" class="empty-state">
                <div class="empty-content">
                    <i data-lucide="inbox" class="empty-icon"></i>
                    <p>No stacks found</p>
                    <p class="empty-hint">Click "Import" to fetch stacks from Portainer</p>
                </div>
            </td>
        `;
        this.tbody.appendChild(row);
    }

    /**
     * Create a table row for a stack
     * @param {Object} stack 
     * @returns {HTMLTableRowElement}
     */
    createRow(stack) {
        const tr = document.createElement('tr');
        tr.setAttribute('data-stack-id', stack.id);
        tr.setAttribute('tabindex', '0');

        tr.innerHTML = `
            <td class="cell-name">
                <i data-lucide="layers" class="icon-stack"></i>
                <span class="stack-name">${this.escapeHtml(stack.name)}</span>
            </td>
            <td class="cell-status" data-col="indicator">
                ${this.renderBadge(stack.image_status)}
            </td>
            <td class="cell-date" data-col="lastChecked">
                ${this.formatDate(stack.image_last_checked)}
            </td>
            <td class="cell-date" data-col="lastUpdated">
                ${this.formatDate(stack.last_updated_at)}
            </td>
            <td class="cell-actions">
                <div class="action-group">
                    <button 
                        data-action="check" 
                        data-id="${stack.id}" 
                        class="btn btn-ghost btn-sm"
                        title="Check for updates"
                        aria-label="Check updates for ${stack.name}"
                    >
                        <i data-lucide="refresh-cw"></i>
                        <span class="btn-label">Check</span>
                    </button>
                    <button 
                        data-action="update" 
                        data-id="${stack.id}" 
                        class="btn btn-primary btn-sm"
                        title="Pull and redeploy"
                        aria-label="Update ${stack.name}"
                    >
                        <i data-lucide="download"></i>
                        <span class="btn-label">Update</span>
                    </button>
                </div>
            </td>
        `;

        return tr;
    }

    /**
     * Update a single row without re-rendering entire table
     * @param {Object} stackData 
     */
    updateRow(stackData) {
        const row = this.tbody?.querySelector(`tr[data-stack-id="${stackData.id}"]`);
        if (!row) return;

        // Update indicator
        const indicatorCell = row.querySelector('[data-col="indicator"]');
        if (indicatorCell && stackData.image_status) {
            indicatorCell.innerHTML = this.renderBadge(stackData.image_status);
        }

        // Update last checked
        const lastCheckedCell = row.querySelector('[data-col="lastChecked"]');
        if (lastCheckedCell && stackData.image_last_checked) {
            lastCheckedCell.textContent = this.formatDate(stackData.image_last_checked);
        }

        // Update last updated
        const lastUpdatedCell = row.querySelector('[data-col="lastUpdated"]');
        if (lastUpdatedCell && stackData.last_updated_at) {
            lastUpdatedCell.textContent = this.formatDate(stackData.last_updated_at);
        }

        this.refreshIcons();
    }

    /**
     * Render a status badge
     * @param {string} status 
     * @returns {string}
     */
    renderBadge(status) {
        const statusClass = this.getStatusClass(status);
        const icon = this.getStatusIcon(statusClass);
        const spin = statusClass === 'processing' ? 'spin' : '';
        const label = this.getStatusLabel(status);

        return `
            <span class="badge ${statusClass}" title="${label}">
                <i data-lucide="${icon}" class="icon ${spin}"></i>
                <span class="label">${label}</span>
            </span>
        `;
    }

    /**
     * Get status class from status string
     * @param {string} status 
     * @returns {string}
     */
    getStatusClass(status) {
        if (!status) return 'unknown';

        const normalized = status.toString().trim().toLowerCase();
        const mapping = {
            'processing': 'processing',
            'preparing': 'processing',
            'updated': 'ok',
            'outdated': 'warn',
            'skipped': 'unknown',
            'error': 'error'
        };

        return mapping[normalized] || 'unknown';
    }

    /**
     * Get icon name for status class
     * @param {string} statusClass 
     * @returns {string}
     */
    getStatusIcon(statusClass) {
        const icons = {
            ok: 'check-circle',
            warn: 'alert-triangle',
            error: 'x-circle',
            processing: 'loader',
            unknown: 'help-circle'
        };
        return icons[statusClass] || 'help-circle';
    }

    /**
     * Get human-readable status label
     * @param {string} status 
     * @returns {string}
     */
    getStatusLabel(status) {
        if (!status) return 'Unknown';
        return status.charAt(0).toUpperCase() + status.slice(1).toLowerCase();
    }

    /**
     * Format a date string for display
     * @param {string} dateStr 
     * @returns {string}
     */
    formatDate(dateStr) {
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

    /**
     * Escape HTML to prevent XSS
     * @param {string} str 
     * @returns {string}
     */
    escapeHtml(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    /**
     * Refresh Lucide icons
     */
    refreshIcons() {
        if (window.lucide?.createIcons) {
            lucide.createIcons();
        }
    }
}
