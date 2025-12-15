/**
 * Table Renderer Module
 * 
 * Handles rendering and updating the stacks table.
 */

import { getStatusClass, getStatusIcon, refreshIcons, escapeHtml, formatDate } from './utils.js';

export class TableRenderer {
    constructor(store, onAction) {
        this.store = store;
        this.onAction = onAction;
        this.tbody = document.getElementById('stackTableBody');
        this.tableWrapper = document.querySelector('.table-wrapper');
        this.actionPanel = document.getElementById('rowActionPanel');
        this.actionNameEl = this.actionPanel?.querySelector('[data-role="action-name"]');
        this.actionButtonsEl = this.actionPanel?.querySelector('[data-role="action-buttons"]');
        this.activePanelId = null;
        this.hidePanelTimeout = null;
        this.bindPanelHoverEvents();
    }

    /**
     * Render the entire table
     * @param {Array} stacks 
     */
    render(stacks) {
        if (!this.tbody) return;

        this.tbody.innerHTML = '';
        this.hideActionPanel(true);

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
            <td colspan="4" class="empty-state">
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
        `;

        this.attachRowInteractions(tr, stack);
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
            lastCheckedCell.textContent = formatDate(stackData.image_last_checked);
        }

        // Update last updated
        const lastUpdatedCell = row.querySelector('[data-col="lastUpdated"]');
        if (lastUpdatedCell && stackData.last_updated_at) {
            lastUpdatedCell.textContent = formatDate(stackData.last_updated_at);
        }

        this.refreshIcons();
    }

    /**
     * Attach hover/focus events to table rows to manage the action slider
     * @param {HTMLTableRowElement} row 
     * @param {Object} stack 
     */
    attachRowInteractions(row, stack) {
        if (!this.actionPanel) return;

        const show = () => {
            this.cancelActionPanelHide();
            this.showActionPanel(stack);
        };

        row.addEventListener('mouseenter', show);
        row.addEventListener('focus', show);
        row.addEventListener('mouseleave', () => this.hideActionPanel());
        row.addEventListener('blur', (event) => {
            if (this.actionPanel?.contains(event.relatedTarget)) {
                return;
            }
            this.hideActionPanel();
        });
    }

    /**
     * Initialize hover handling for the action panel itself
     */
    bindPanelHoverEvents() {
        if (!this.actionPanel) return;
        this.actionPanel.addEventListener('mouseenter', () => this.cancelActionPanelHide());
        this.actionPanel.addEventListener('mouseleave', () => this.hideActionPanel());
        this.actionPanel.addEventListener('focusin', () => this.cancelActionPanelHide());
        this.actionPanel.addEventListener('focusout', (event) => {
            if (this.actionPanel.contains(event.relatedTarget)) {
                return;
            }
            this.hideActionPanel();
        });
    }

    /**
     * Show the action slider with buttons for a stack
     * @param {Object} stack 
     */
    showActionPanel(stack) {
        if (!this.actionPanel) return;

        const isDifferentStack = this.activePanelId !== stack.id;

        if (isDifferentStack || !this.actionPanel.classList.contains('visible')) {
            if (this.actionNameEl) {
                this.actionNameEl.textContent = stack.name;
            }

            if (this.actionButtonsEl) {
                this.actionButtonsEl.innerHTML = this.renderActionButtons(stack);
                this.refreshIcons();
            }
        }

        this.actionPanel.dataset.activeId = stack.id;
        this.actionPanel.setAttribute('aria-hidden', 'false');
        this.actionPanel.classList.add('visible');
        this.activePanelId = stack.id;
        this.tableWrapper?.classList.add('actions-visible');
    }

    /**
     * Hide the action slider, optionally immediately
     * @param {boolean} immediate 
     */
    hideActionPanel(immediate = false) {
        if (!this.actionPanel) return;

        this.cancelActionPanelHide();

        const performHide = () => {
            this.actionPanel.classList.remove('visible');
            this.actionPanel.setAttribute('aria-hidden', 'true');
            this.activePanelId = null;
            this.tableWrapper?.classList.remove('actions-visible');
        };

        if (immediate) {
            performHide();
            return;
        }

        this.hidePanelTimeout = window.setTimeout(performHide, 180);
    }

    /**
     * Cancel any hide timer
     */
    cancelActionPanelHide() {
        if (this.hidePanelTimeout) {
            window.clearTimeout(this.hidePanelTimeout);
            this.hidePanelTimeout = null;
        }
    }

    /**
     * Render HTML for the action buttons inside the slider
     * @param {Object} stack 
     * @returns {string}
     */
    renderActionButtons(stack) {
        return `
            <button 
                data-action="check" 
                data-id="${stack.id}" 
                class="action-btn ghost"
                title="Check for updates"
                aria-label="Check updates for ${stack.name}"
            >
                <i data-lucide="refresh-cw"></i>
                <span>Check</span>
            </button>
            <button 
                data-action="update" 
                data-id="${stack.id}" 
                class="action-btn primary"
                title="Pull and redeploy"
                aria-label="Update ${stack.name}"
            >
                <i data-lucide="download"></i>
                <span>Update</span>
            </button>
        `;
    }

    /**
     * Get a row by stack id
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
     * Get human-readable status label
     * @param {string} status 
     * @returns {string}
     */
    getStatusLabel(status) {
        if (!status) return 'Unknown';
        return status.charAt(0).toUpperCase() + status.slice(1).toLowerCase();
    }

    /**
     * Refresh Lucide icons
     */
    refreshIcons() {
        refreshIcons();
    }
}
