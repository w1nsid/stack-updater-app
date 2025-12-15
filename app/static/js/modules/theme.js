/**
 * Theme Manager Module
 * 
 * Handles theme switching (light/dark) with:
 * - localStorage persistence
 * - System preference detection
 * - Smooth transitions
 */

import { refreshIcons } from './utils.js';

const STORAGE_KEY = 'stackUpdaterTheme';

export class ThemeManager {
    constructor() {
        this.root = document.documentElement;
        this.currentTheme = 'dark';
    }

    /**
     * Initialize theme from storage or system preference
     */
    init() {
        const stored = localStorage.getItem(STORAGE_KEY);

        if (stored) {
            this.apply(stored);
        } else {
            const prefersLight = window.matchMedia('(prefers-color-scheme: light)').matches;
            this.apply(prefersLight ? 'light' : 'dark');
        }

        // Listen for system preference changes
        window.matchMedia('(prefers-color-scheme: light)').addEventListener('change', (e) => {
            const stored = localStorage.getItem(STORAGE_KEY);
            if (!stored) {
                this.apply(e.matches ? 'light' : 'dark');
            }
        });
    }

    /**
     * Apply a theme
     * @param {string} theme - 'light' or 'dark'
     */
    apply(theme) {
        if (theme !== 'light' && theme !== 'dark') {
            theme = 'dark';
        }

        this.currentTheme = theme;

        if (theme === 'light') {
            this.root.setAttribute('data-theme', 'light');
        } else {
            this.root.removeAttribute('data-theme');
        }

        localStorage.setItem(STORAGE_KEY, theme);
        this.updateIcon();
    }

    /**
     * Toggle between light and dark themes
     */
    toggle() {
        const newTheme = this.currentTheme === 'light' ? 'dark' : 'light';
        this.apply(newTheme);
    }

    /**
     * Update the theme toggle button icon
     */
    updateIcon() {
        const toggle = document.getElementById('themeToggle');
        if (!toggle) {
            return;
        }

        const nextTheme = this.currentTheme === 'dark' ? 'light' : 'dark';
        toggle.dataset.themeState = this.currentTheme;
        toggle.setAttribute('role', 'switch');
        toggle.setAttribute('aria-checked', String(this.currentTheme === 'light'));
        toggle.setAttribute('aria-label', `Switch to ${nextTheme} mode`);
        toggle.setAttribute('title', `Switch to ${nextTheme} mode`);

        refreshIcons();
    }

    /**
     * Get current theme
     * @returns {string}
     */
    get() {
        return this.currentTheme;
    }
}
