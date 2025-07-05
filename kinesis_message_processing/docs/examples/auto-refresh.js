// Auto-refresh function for WebSocket visualizations
function startAutoRefresh() {
    setInterval(() => {
        if (typeof isConnected !== 'undefined' && isConnected && typeof getAllLatest === 'function') {
            getAllLatest();
        }
    }, 500); // Poll every 500ms
}

// Start auto-refresh when page loads
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', startAutoRefresh);
} else {
    startAutoRefresh();
}