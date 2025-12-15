/**
 * Stats Renderer Module
 * 
 * Updates the statistics cards in the dashboard.
 */

import { getStatusClass } from './utils.js';

export class StatsRenderer {
    constructor() {
        this.elements = {
            total: document.getElementById('statTotal'),
            updated: document.getElementById('statUpdated'),
            outdated: document.getElementById('statOutdated'),
            errors: document.getElementById('statErrors')
        };
    }

    /**
     * Update stats display
     * @param {Array} stacks 
     */
    update(stacks) {
        const stats = this.calculate(stacks);

        this.setValue('total', stats.total);
        this.setValue('updated', stats.updated);
        this.setValue('outdated', stats.outdated);
        this.setValue('errors', stats.errors);
    }

    /**
     * Calculate statistics from stacks
     * @param {Array} stacks 
     * @returns {Object}
     */
    calculate(stacks) {
        return {
            total: stacks.length,
            updated: stacks.filter(s => getStatusClass(s.image_status) === 'ok').length,
            outdated: stacks.filter(s => getStatusClass(s.image_status) === 'warn').length,
            errors: stacks.filter(s => getStatusClass(s.image_status) === 'error').length
        };
    }

    /**
     * Set a stat value with animation
     * @param {string} key 
     * @param {number} value 
     */
    setValue(key, value) {
        const el = this.elements[key];
        if (!el) return;

        const currentValue = parseInt(el.textContent, 10) || 0;

        if (currentValue !== value) {
            // Add pulse animation on change
            el.classList.add('stat-changed');
            el.textContent = value;

            setTimeout(() => {
                el.classList.remove('stat-changed');
            }, 300);
        }
    }
}
