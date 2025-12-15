/**
 * Stack Updater App - Main Application Entry Point
 * 
 * This is the main orchestrator that initializes all modules
 * and wires them together.
 */

import { ThemeManager } from './modules/theme.js';
import { StackStore } from './modules/store.js';
import { ApiClient } from './modules/api.js';
import { TableRenderer } from './modules/table.js';
import { StatsRenderer } from './modules/stats.js';
import { Announcer } from './modules/accessibility.js';
import { ButtonController } from './modules/buttons.js';
import { refreshIcons } from './modules/utils.js';

class StackUpdaterApp {
    constructor() {
        // Core modules
        this.announcer = new Announcer();
        this.theme = new ThemeManager();
        this.api = new ApiClient();
        this.store = new StackStore();

        // UI modules
        this.stats = new StatsRenderer();
        this.table = new TableRenderer(this.store, this.handleAction.bind(this));
        this.buttons = new ButtonController(this.api, this.store, this.announcer);
    }

    /**
     * Initialize the application
     */
    async init() {
        console.log('[App] Initializing Stack Updater...');

        // Initialize theme
        this.theme.init();

        // Set up event listeners
        this.setupEventListeners();

        // Load initial data
        await this.loadStacks();

        console.log('[App] Initialization complete');
    }

    /**
     * Set up all event listeners
     */
    setupEventListeners() {
        // Theme toggle
        const themeBtn = document.getElementById('themeToggle');
        if (themeBtn) {
            themeBtn.addEventListener('click', () => this.theme.toggle());
        }

        // Import button
        const importBtn = document.getElementById('importBtn');
        if (importBtn) {
            importBtn.addEventListener('click', () => this.handleImport());
        }

        // Refresh all button
        const refreshBtn = document.getElementById('refreshAllBtn');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => this.handleRefreshAll());
        }

        // Search filter
        const searchInput = document.getElementById('filterSearch');
        if (searchInput) {
            searchInput.addEventListener('input', (e) => {
                this.store.setFilter('text', e.target.value.toLowerCase());
                this.render();
            });
        }

        // Status filter
        const statusSelect = document.getElementById('filterStatus');
        if (statusSelect) {
            statusSelect.addEventListener('change', (e) => {
                this.store.setFilter('status', e.target.value);
                this.render();
            });
        }

        // Table header sorting
        document.querySelectorAll('thead th[data-key]').forEach(th => {
            th.addEventListener('click', () => this.handleSort(th.dataset.key));
            th.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    this.handleSort(th.dataset.key);
                }
            });
        });

        // Table row actions (delegated)
        const tbody = document.getElementById('stackTableBody');
        if (tbody) {
            tbody.addEventListener('click', (e) => this.handleTableClick(e));
        }
    }

    /**
     * Load stacks from API
     */
    async loadStacks() {
        try {
            const stacks = await this.api.getStacks();
            this.store.setStacks(stacks);
            this.render();
            this.announcer.announce(`Loaded ${stacks.length} stacks`);
        } catch (error) {
            console.error('[App] Failed to load stacks:', error);
            this.announcer.announce('Failed to load stacks');
        }
    }

    /**
     * Render all UI components
     */
    render() {
        const stacks = this.store.getFilteredAndSorted();
        this.table.render(stacks);
        this.stats.update(stacks);
    }

    /**
     * Handle sorting
     */
    handleSort(key) {
        if (!key) return;
        this.store.toggleSort(key);
        this.render();
        this.announcer.announce(`Sorted by ${key} ${this.store.sortDir}`);
    }

    /**
     * Handle table row button clicks
     */
    handleTableClick(event) {
        const btn = event.target.closest('button[data-action]');
        if (!btn) return;

        const action = btn.dataset.action;
        const stackId = parseInt(btn.dataset.id, 10);

        this.handleAction(action, stackId, btn);
    }

    /**
     * Handle stack actions (check, update)
     */
    async handleAction(action, stackId, buttonEl) {
        const row = buttonEl?.closest('tr');
        const indicatorCell = row?.querySelector('[data-col="indicator"]');

        // Disable button and add spin animation
        if (buttonEl) {
            buttonEl.disabled = true;
            const icon = buttonEl.querySelector('i, svg');
            if (icon) {
                icon.classList.add('spin');
            }
        }

        try {
            // Show processing state in indicator
            if (indicatorCell) {
                indicatorCell.innerHTML = this.table.renderBadge('processing');
                refreshIcons();
            }

            let result;
            switch (action) {
                case 'check':
                    result = await this.api.getIndicator(stackId, true);
                    break;
                case 'update':
                    const updateResponse = await this.api.updateStack(stackId);
                    // Use the full stack data from update response
                    if (updateResponse.stack) {
                        result = {
                            id: updateResponse.stack.id,
                            status: updateResponse.stack.image_status,
                            last_checked: updateResponse.stack.image_last_checked,
                            last_updated_at: updateResponse.stack.last_updated_at
                        };
                    }
                    break;
                default:
                    console.warn('[App] Unknown action:', action);
                    return;
            }

            // Update store and row only
            if (result) {
                const updatedData = {
                    id: result.id,
                    image_status: result.status,
                    image_last_checked: result.last_checked,
                    last_updated_at: result.last_updated_at
                };
                this.store.updateStack(result.id, updatedData);
                this.table.updateRow(updatedData);
                this.stats.update(this.store.getFilteredAndSorted());
            }

            this.announcer.announce(`${action} completed`);

        } catch (error) {
            console.error(`[App] Action ${action} failed:`, error);

            if (indicatorCell) {
                indicatorCell.innerHTML = this.table.renderBadge('error');
                refreshIcons();
            }

            // Re-enable button on error
            if (buttonEl) {
                buttonEl.disabled = false;
                const icon = buttonEl.querySelector('i, svg');
                if (icon) {
                    icon.classList.remove('spin');
                }
            }

            this.announcer.announce(`${action} failed`);
        }
    }

    /**
     * Handle import button click
     */
    async handleImport() {
        const btn = document.getElementById('importBtn');
        await this.buttons.withLoading(btn, 'Importing...', async () => {
            const result = await this.api.importStacks();
            await this.loadStacks();
            this.announcer.announce(`Import completed: ${result.imported} new stacks`);
        });
    }

    /**
     * Handle refresh all button click
     */
    async handleRefreshAll() {
        const btn = document.getElementById('refreshAllBtn');
        await this.buttons.withLoading(btn, 'Refreshing...', async () => {
            await this.api.refreshAll();
            await this.loadStacks();
            this.announcer.announce('Bulk refresh complete');
        });
    }
}

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.app = new StackUpdaterApp();
    window.app.init();
});
