/**
 * API Client Module
 * 
 * Handles all HTTP communication with the backend API.
 * Provides typed methods for each endpoint.
 */

export class ApiClient {
    constructor(baseUrl = '') {
        this.baseUrl = baseUrl;
    }

    /**
     * Make an HTTP request
     * @param {string} endpoint 
     * @param {Object} options 
     * @returns {Promise<any>}
     */
    async request(endpoint, options = {}) {
        const url = `${this.baseUrl}${endpoint}`;

        const response = await fetch(url, {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        });

        if (!response.ok) {
            const error = new Error(`API Error: ${response.status}`);
            error.status = response.status;
            try {
                error.data = await response.json();
            } catch {
                error.data = null;
            }
            throw error;
        }

        return response.json();
    }

    // =========================================================================
    // Stack Endpoints
    // =========================================================================

    /**
     * Get all stacks from database
     * @returns {Promise<Array>}
     */
    async getStacks() {
        return this.request('/api/stacks');
    }

    /**
     * Import stacks from Portainer
     * @returns {Promise<{imported: number}>}
     */
    async importStacks() {
        return this.request('/api/stacks/import');
    }

    // =========================================================================
    // Indicator Endpoints
    // =========================================================================

    /**
     * Get image indicator for a stack
     * @param {number} stackId 
     * @param {boolean} refresh - Force Portainer to re-check images
     * @returns {Promise<{id: number, status: string, message: string, last_checked: string}>}
     */
    async getIndicator(stackId, refresh = false) {
        return this.request(`/api/stacks/${stackId}/indicator?refresh=${refresh}`);
    }

    /**
     * Refresh all stack indicators
     * @param {boolean} force 
     * @returns {Promise<{total: number, success: number, errors: number}>}
     */
    async refreshAll(force = true) {
        return this.request(`/api/stacks/refresh-all?force=${force}`, {
            method: 'POST'
        });
    }

    // =========================================================================
    // Update Endpoints
    // =========================================================================

    /**
     * Trigger a stack update via webhook
     * @param {number} stackId 
     * @returns {Promise<{updated: boolean, stack: Object}>}
     */
    async updateStack(stackId) {
        return this.request(`/api/stacks/${stackId}/update`, {
            method: 'POST'
        });
    }

}
