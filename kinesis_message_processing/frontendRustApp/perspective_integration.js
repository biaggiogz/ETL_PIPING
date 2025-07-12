// Perspective integration for WebSocket data streaming
class PerspectiveManager {
    constructor() {
        this.table = null;
        this.viewer = null;
        this.dataBuffer = [];
    }

    async initialize() {
        // Create Perspective table with sensor schema
        this.table = await perspective.table({
            sensor_id: 'string',
            temperature: 'float',
            latitude: 'float',
            longitude: 'float', 
            speed_kms: 'float',
            connection_speed_mbps: 'float',
            total_pipeline_us: 'integer',
            timestamp: 'datetime'
        });

        // Get viewer element and load table
        this.viewer = document.getElementById('sensor-viewer');
        if (this.viewer) {
            await this.viewer.load(this.table);
            
            // Configure interactive grid settings
            await this.viewer.restore({
                plugin: 'Datagrid',
                columns: ['sensor_id', 'temperature', 'latitude', 'longitude', 'speed_kms', 'total_pipeline_us'],
                aggregates: {
                    temperature: 'avg',
                    speed_kms: 'avg', 
                    total_pipeline_us: 'avg'
                },
                'group-by': ['sensor_id'],
                sort: [['timestamp', 'desc']]
            });
        }
    }

    updateData(reading) {
        if (!this.table) return;
        
        // Handle both direct objects and JSON strings
        const data = typeof reading === 'string' ? JSON.parse(reading) : reading;
        
        const row = {
            sensor_id: data.sensor_id,
            temperature: data.temperature,
            latitude: data.position ? data.position.latitude : data.latitude,
            longitude: data.position ? data.position.longitude : data.longitude,
            speed_kms: data.speed_kms,
            connection_speed_mbps: data.connection_speed_mbps,
            total_pipeline_us: data.total_pipeline_us,
            timestamp: new Date(data.reading_timestamp_ms)
        };

        this.table.update([row]);
    }

    batchUpdate(readings) {
        if (!this.table || !readings.length) return;
        
        const rows = readings.map(reading => ({
            sensor_id: reading.sensor_id,
            temperature: reading.temperature,
            latitude: reading.position.latitude,
            longitude: reading.position.longitude,
            speed_kms: reading.speed_kms,
            connection_speed_mbps: reading.connection_speed_mbps,
            total_pipeline_us: reading.total_pipeline_us,
            timestamp: new Date(reading.reading_timestamp_ms)
        }));

        this.table.update(rows);
    }
}

// Global instance
window.perspectiveManager = new PerspectiveManager();

// Auto-connect to existing WebSocket
function hookIntoExistingWebSocket() {
    // Listen for custom sensor data events
    window.addEventListener('sensorData', (event) => {
        if (window.perspectiveManager && event.detail) {
            try {
                window.perspectiveManager.updateData(event.detail);
            } catch (e) {
                console.error('Error updating Perspective:', e);
            }
        }
    });
    
    console.log('Perspective WebSocket integration ready');
}

// Export for WASM integration
window.updatePerspectiveData = function(viewer, readings) {
    if (window.perspectiveManager && readings.length > 0) {
        window.perspectiveManager.batchUpdate(readings);
    }
};

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', async () => {
    await window.perspectiveManager.initialize();
    hookIntoExistingWebSocket();
});

// Also try to initialize after a delay for dynamic content
setTimeout(async () => {
    if (!window.perspectiveManager.table) {
        await window.perspectiveManager.initialize();
    }
}, 1000);