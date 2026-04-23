/**
 * theme.js - Centralized theme management for Student Expense Tracker
 */

(function() {
    // 1. Immediate Theme Application (prevents flash)
    const savedTheme = localStorage.getItem('theme') || 'dark';
    document.documentElement.setAttribute('data-theme', savedTheme);

    // 2. Wait for DOM to set up toggle listeners
    document.addEventListener('DOMContentLoaded', () => {
        initThemeToggle();
    });

    function initThemeToggle() {
        const toggles = document.querySelectorAll('.theme-switch');
        toggles.forEach(toggle => {
            toggle.addEventListener('click', toggleTheme);
        });
    }

    function toggleTheme() {
        const current = document.documentElement.getAttribute('data-theme');
        const newTheme = current === 'dark' ? 'light' : 'dark';
        
        // Update preference
        document.documentElement.setAttribute('data-theme', newTheme);
        localStorage.setItem('theme', newTheme);
        
        // Update Chart.js if on dashboard
        if (window.myChart) {
            const textColor = newTheme === 'dark' ? '#94a3b8' : '#64748b';
            window.myChart.options.plugins.legend.labels.color = textColor;
            window.myChart.update();
        }
        
        // Trigger a custom event for other components if needed
        window.dispatchEvent(new CustomEvent('themechanged', { detail: { theme: newTheme } }));
    }
})();
