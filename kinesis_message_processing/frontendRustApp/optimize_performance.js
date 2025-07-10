// Performance optimization script for the Rust WebAssembly dashboard
// Add this to your index.html to monitor and optimize performance

class PerformanceMonitor {
    constructor() {
        this.metrics = {
            renderTimes: [],
            messageProcessingTimes: [],
            memoryUsage: [],
            frameDrops: 0,
            lastFrameTime: performance.now()
        };
        
        this.startMonitoring();
    }
    
    startMonitoring() {
        // Monitor frame rate
        const checkFrameRate = () => {
            const now = performance.now();
            const frameDelta = now - this.metrics.lastFrameTime;
            
            // Detect frame drops (>20ms = <50fps)
            if (frameDelta > 20) {
                this.metrics.frameDrops++;
            }
            
            this.metrics.lastFrameTime = now;
            requestAnimationFrame(checkFrameRate);
        };
        requestAnimationFrame(checkFrameRate);
        
        // Monitor memory usage every 5 seconds
        setInterval(() => {
            if (performance.memory) {
                this.metrics.memoryUsage.push({
                    used: performance.memory.usedJSHeapSize,
                    total: performance.memory.totalJSHeapSize,
                    timestamp: Date.now()
                });
                
                // Keep only last 100 measurements
                if (this.metrics.memoryUsage.length > 100) {
                    this.metrics.memoryUsage.shift();
                }
            }
        }, 5000);
        
        // Log performance summary every 30 seconds
        setInterval(() => {
            this.logPerformanceSummary();
        }, 30000);
    }
    
    measureRenderTime(renderFunction) {
        const start = performance.now();
        const result = renderFunction();
        const end = performance.now();
        
        this.metrics.renderTimes.push(end - start);
        if (this.metrics.renderTimes.length > 100) {
            this.metrics.renderTimes.shift();
        }
        
        return result;
    }
    
    measureMessageProcessing(processingFunction) {
        const start = performance.now();
        const result = processingFunction();
        const end = performance.now();
        
        this.metrics.messageProcessingTimes.push(end - start);
        if (this.metrics.messageProcessingTimes.length > 100) {
            this.metrics.messageProcessingTimes.shift();
        }
        
        return result;
    }
    
    logPerformanceSummary() {
        const avgRenderTime = this.metrics.renderTimes.length > 0 
            ? this.metrics.renderTimes.reduce((a, b) => a + b, 0) / this.metrics.renderTimes.length 
            : 0;
            
        const avgMessageTime = this.metrics.messageProcessingTimes.length > 0
            ? this.metrics.messageProcessingTimes.reduce((a, b) => a + b, 0) / this.metrics.messageProcessingTimes.length
            : 0;
            
        const currentMemory = this.metrics.memoryUsage.length > 0 
            ? this.metrics.memoryUsage[this.metrics.memoryUsage.length - 1]
            : null;
        
        console.log('🔍 Performance Summary:', {
            avgRenderTime: `${avgRenderTime.toFixed(2)}ms`,
            avgMessageProcessingTime: `${avgMessageTime.toFixed(2)}ms`,
            frameDrops: this.metrics.frameDrops,
            memoryUsage: currentMemory ? `${(currentMemory.used / 1024 / 1024).toFixed(2)}MB` : 'N/A',
            recommendations: this.getRecommendations(avgRenderTime, avgMessageTime)
        });
        
        // Reset frame drops counter
        this.metrics.frameDrops = 0;
    }
    
    getRecommendations(avgRenderTime, avgMessageTime) {
        const recommendations = [];
        
        if (avgRenderTime > 16) {
            recommendations.push('Consider reducing chart complexity or update frequency');
        }
        
        if (avgMessageTime > 5) {
            recommendations.push('Optimize message processing - consider batching');
        }
        
        if (this.metrics.frameDrops > 10) {
            recommendations.push('High frame drops detected - reduce rendering frequency');
        }
        
        const currentMemory = this.metrics.memoryUsage.length > 0 
            ? this.metrics.memoryUsage[this.metrics.memoryUsage.length - 1]
            : null;
            
        if (currentMemory && currentMemory.used > 100 * 1024 * 1024) {
            recommendations.push('High memory usage - implement data cleanup');
        }
        
        return recommendations.length > 0 ? recommendations : ['Performance looks good!'];
    }
}

// WebSocket message batching utility
class MessageBatcher {
    constructor(batchSize = 10, flushInterval = 16) {
        this.batch = [];
        this.batchSize = batchSize;
        this.flushInterval = flushInterval;
        this.lastFlush = performance.now();
        this.callbacks = [];
    }
    
    addMessage(message) {
        this.batch.push(message);
        
        const now = performance.now();
        const shouldFlush = this.batch.length >= this.batchSize || 
                           (now - this.lastFlush) >= this.flushInterval;
        
        if (shouldFlush) {
            this.flush();
        }
    }
    
    flush() {
        if (this.batch.length === 0) return;
        
        const messages = [...this.batch];
        this.batch = [];
        this.lastFlush = performance.now();
        
        this.callbacks.forEach(callback => {
            try {
                callback(messages);
            } catch (error) {
                console.error('Error in batch callback:', error);
            }
        });
    }
    
    onBatch(callback) {
        this.callbacks.push(callback);
    }
}

// Initialize performance monitoring
window.performanceMonitor = new PerformanceMonitor();
window.messageBatcher = new MessageBatcher();

// Optimization utilities
window.optimizationUtils = {
    // Throttle function calls
    throttle: (func, limit) => {
        let inThrottle;
        return function() {
            const args = arguments;
            const context = this;
            if (!inThrottle) {
                func.apply(context, args);
                inThrottle = true;
                setTimeout(() => inThrottle = false, limit);
            }
        }
    },
    
    // Debounce function calls
    debounce: (func, delay) => {
        let timeoutId;
        return function() {
            const args = arguments;
            const context = this;
            clearTimeout(timeoutId);
            timeoutId = setTimeout(() => func.apply(context, args), delay);
        }
    },
    
    // Efficient array operations
    efficientArrayOps: {
        // Remove old items efficiently
        trimArray: (arr, maxLength) => {
            if (arr.length > maxLength) {
                const removeCount = arr.length - maxLength;
                arr.splice(0, removeCount);
            }
            return arr;
        },
        
        // Batch array updates
        batchUpdate: (arr, newItems, maxLength) => {
            arr.push(...newItems);
            return window.optimizationUtils.efficientArrayOps.trimArray(arr, maxLength);
        }
    }
};

console.log('🚀 Performance monitoring and optimization utilities loaded');