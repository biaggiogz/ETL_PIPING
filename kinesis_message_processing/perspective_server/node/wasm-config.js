// High-performance WASM configuration for fast Kinesis streams
export const WASM_CONFIG = {
    // Memory settings
    initial_memory: 256 * 1024 * 1024, // 256MB initial
    maximum_memory: 512 * 1024 * 1024, // 512MB max
    
    // Threading
    thread_count: Math.min(navigator.hardwareConcurrency || 4, 8),
    
    // Streaming optimizations
    streaming: {
        enabled: true,
        chunk_size: 1024 * 64, // 64KB chunks
        buffer_size: 1024 * 1024 * 2, // 2MB buffer
        flush_interval: 16 // ~60fps updates
    },
    
    // Arrow optimizations
    arrow: {
        batch_size: 1000,
        compression: false, // Disable for speed
        dictionary_encoding: true
    }
};

// Performance monitoring utilities
export class PerformanceMonitor {
    constructor() {
        this.metrics = {
            updates: 0,
            lastUpdate: Date.now(),
            avgLatency: 0,
            maxLatency: 0
        };
    }
    
    recordUpdate(latency = 0) {
        this.metrics.updates++;
        this.metrics.avgLatency = (this.metrics.avgLatency + latency) / 2;
        this.metrics.maxLatency = Math.max(this.metrics.maxLatency, latency);
        
        const now = Date.now();
        if (now - this.metrics.lastUpdate > 1000) {
            console.log(`Performance: ${this.metrics.updates} updates/sec, Avg: ${this.metrics.avgLatency.toFixed(2)}ms, Max: ${this.metrics.maxLatency}ms`);
            this.metrics.updates = 0;
            this.metrics.lastUpdate = now;
            this.metrics.maxLatency = 0;
        }
    }
}