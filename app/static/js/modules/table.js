/**
 * Table Renderer Module
 *
 * Handles rendering and updating the stacks table with inline action buttons.
 */

import { getStatusClass, getStatusIcon, refreshIcons, escapeHtml, formatDate } from './utils.js';

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
     * Render an empty state row
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
     * Build a table row for a stack
     * @param {Object} stack
     * @returns {HTMLTableRowElement}
     */
    createRow(stack) {
        const tr = document.createElement('tr');
        tr.setAttribute('data-stack-id', stack.id);
        tr.setAttribute('tabindex', '0');

        tr.innerHTML = `
            <td class="cell-name">
                <span class="cell-name-inner">
                    <i data-lucide="layers" class="icon-stack"></i>
                    <span class="stack-name">${escapeHtml(stack.name)}</span>
                </span>
            </td>
            <td class="cell-status" data-col="indicator">
                ${this.renderBadge(stack.image_status)}
            </td>
            <td class="cell-date" data-col="lastChecked">
                ${formatDate(stack.image_last_checked)}
            </td>
            <td class="cell-date" data-col="lastUpdated">
                ${formatDate(stack.last_updated_at)}
            </td>
            <td class="cell-actions">
                <div class="action-group">
                    ${this.renderActionButton('check', stack, 'refresh-cw', 'Check')}
                    ${this.renderActionButton('update', stack, 'download', 'Update')}
                </div>
            </td>
        `;

        return tr;
    }

    /**
     * Render a compact action button
     * @param {string} action
     * @param {Object} stack
     * @param {string} icon
     * @param {string} label
     * @returns {string}
     */
    renderActionButton(action, stack, icon, label) {
        return `
            <button
                data-action="${action}"
                data-id="${stack.id}"
                class="table-action-btn ${action === 'update' ? 'primary' : 'ghost'}"
                title="${label} ${stack.name}"
                aria-label="${label} ${stack.name}"
            >
                <i data-lucide="${icon}"></i>
                <span>${label}</span>
            </button>
        `;
    }

    /**
     * Update a single table row
     * @param {Object} stackData
     */
    updateRow(stackData) {
        const row = this.tbody?.querySelector(`tr[data-stack-id="${stackData.id}"]`);
        if (!row) return;

        const indicatorCell = row.querySelector('[data-col="indicator"]');
        if (indicatorCell && stackData.image_status) {
            indicatorCell.innerHTML = this.renderBadge(stackData.image_status);
        }

        const lastCheckedCell = row.querySelector('[data-col="lastChecked"]');
        if (lastCheckedCell && stackData.image_last_checked) {
            lastCheckedCell.textContent = formatDate(stackData.image_last_checked);
        }

        const lastUpdatedCell = row.querySelector('[data-col="lastUpdated"]');
        if (lastUpdatedCell && stackData.last_updated_at) {
            lastUpdatedCell.textContent = formatDate(stackData.last_updated_at);
        }

        this.refreshIcons();
    }

    /**
     * Convenience helper to grab a table row
     * @param {number} stackId
     * @returns {HTMLTableRowElement | null}
     */
    getRowElement(stackId) {
        return this.tbody?.querySelector(`tr[data-stack-id="${stackId}"]`) || null;
    }

    /**
     * Render a status badge
     * @param {string} status
     * @returns {string}
     */
    renderBadge(status) {
        const statusClass = getStatusClass(status);
        const icon = getStatusIcon(statusClass);
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
     * Human readable status label
     * @param {string} status
     * @returns {string}
     */
    getStatusLabel(status) {
        if (!status) return 'Unknown';
        return status.charAt(0).toUpperCase() + status.slice(1).toLowerCase();
    }

    refreshIcons() {
        refreshIcons();
    }
}
