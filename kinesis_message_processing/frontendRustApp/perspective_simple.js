// Simple Perspective integration
let perspectiveTable = null;
let perspectiveViewer = null;

async function initPerspective() {
    try {
        console.log('Initializing Perspective...');
        
        // Get viewer element
        perspectiveViewer = document.getElementById('sensor-viewer');
        if (!perspectiveViewer) {
            console.error('Perspective viewer not found');
            return;
        }
        
        // Create table with schema
        perspectiveTable = await perspective.table({
            sensor_id: 'string',
            temperature: 'float',
            latitude: 'float',
            longitude: 'float', 
            speed_kms: 'float',
            connection_speed_mbps: 'float',
            total_pipeline_us: 'integer',
            timestamp: 'datetime'
        });
        
        // Load table into viewer
        await perspectiveViewer.load(perspectiveTable);
        
        // Configure viewer
        await perspectiveViewer.restore({
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
        
        console.log('Perspective initialized successfully');
        
        // Listen for sensor data events
        window.addEventListener('sensorData', (event) => {
            if (event.detail && perspectiveTable) {
                try {
                    const data = typeof event.detail === 'string' ? JSON.parse(event.detail) : event.detail;
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
                    perspectiveTable.update([row]);
                } catch (e) {
                    console.error('Error updating Perspective:', e);
                }
            }
        });
        
    } catch (error) {
        console.error('Error initializing Perspective:', error);
    }
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initPerspective);
} else {
    initPerspective();
}

// Also try after a delay
setTimeout(initPerspective, 2000);