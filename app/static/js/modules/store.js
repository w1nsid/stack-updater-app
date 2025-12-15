/**
 * Stack Store Module
 * 
 * Centralized state management for stacks data.
 * Handles filtering, sorting, and updates.
 */

export class StackStore {
    constructor() {
        this.stacks = [];
        this.sortKey = 'name';
        this.sortDir = 'asc';
        this.filters = {
            text: '',
            status: 'all'
        };
    }

    /**
     * Set all stacks (replaces existing)
     * @param {Array} stacks 
     */
    setStacks(stacks) {
        this.stacks = stacks || [];
    }

    /**
     * Get all stacks
     * @returns {Array}
     */
    getAll() {
        return this.stacks;
    }

    /**
     * Update a stack with partial data
     * @param {number} id 
     * @param {Object} patch 
     */
    updateStack(id, patch) {
        const index = this.stacks.findIndex(s => s.id == id);
        if (index >= 0) {
            this.stacks[index] = { ...this.stacks[index], ...patch };
        }
    }

    /**
     * Set a filter value
     * @param {string} key - 'text' or 'status'
     * @param {string} value 
     */
    setFilter(key, value) {
        this.filters[key] = value;
    }

    /**
     * Toggle sort direction or change sort key
     * @param {string} key 
     */
    toggleSort(key) {
        if (this.sortKey === key) {
            this.sortDir = this.sortDir === 'asc' ? 'desc' : 'asc';
        } else {
            this.sortKey = key;
            this.sortDir = 'asc';
        }
    }

    /**
     * Get filtered and sorted stacks
     * @returns {Array}
     */
    getFilteredAndSorted() {
        let result = this.applyFilters(this.stacks);
        result = this.applySort(result);
        return result;
    }

    /**
     * Apply filters to stacks
     * @param {Array} stacks 
     * @returns {Array}
     */
    applyFilters(stacks) {
        return stacks.filter(stack => {
            // Text filter
            const matchesText = !this.filters.text ||
                stack.name.toLowerCase().includes(this.filters.text);

            // Status filter
            const statusClass = this.getStatusClass(stack.image_status);
            const matchesStatus = this.filters.status === 'all' ||
                statusClass === this.filters.status;

            return matchesText && matchesStatus;
        });
    }

    /**
     * Apply sorting to stacks
     * @param {Array} stacks 
     * @returns {Array}
     */
    applySort(stacks) {
        return [...stacks].sort((a, b) => {
            let aVal = a[this.sortKey];
            let bVal = b[this.sortKey];

            // Handle null/undefined
            if (aVal == null) aVal = '';
            if (bVal == null) bVal = '';

            // Case-insensitive string comparison
            if (typeof aVal === 'string') aVal = aVal.toLowerCase();
            if (typeof bVal === 'string') bVal = bVal.toLowerCase();

            if (aVal < bVal) return this.sortDir === 'asc' ? -1 : 1;
            if (aVal > bVal) return this.sortDir === 'asc' ? 1 : -1;
            return 0;
        });
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
}
