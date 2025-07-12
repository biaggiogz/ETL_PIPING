import perspective from "@finos/perspective";
import WebSocket from "ws";

// --- WebSocket constants ---
const WEBSOCKET_URL = "wss://icjs840cnh.execute-api.us-east-1.amazonaws.com/prod";
const PERSPECTIVE_TABLE_NAME = "sensor_data";
const DEVICE_IDS = Array.from({ length: 10 }, (_, i) => `device${i + 1}`); // device1 to device10

/**
 * WebSocket client to connect to AWS API Gateway
 */
class WebSocketClient {
    constructor(table) {
        this.table = table;
        this.ws = null;
    }

    connect() {
        console.log(`Attempting to connect to ${WEBSOCKET_URL}`);
        this.ws = new WebSocket(WEBSOCKET_URL);
        
        this.ws.on('open', () => {
            console.log(`✅ Connected to ${WEBSOCKET_URL}`);
            // Subscribe to all devices
            DEVICE_IDS.forEach(deviceId => {
                const subscribeMsg = { action: "subscribe", sensor_id: deviceId };
                this.ws.send(JSON.stringify(subscribeMsg));
                console.log(`📡 Subscribed to ${deviceId}`);
            });
        });

        this.ws.on('message', (data) => {
            console.log(`📨 Received message: ${data.toString()}`);
            this.handleMessage(data.toString());
        });

        this.ws.on('error', (error) => {
            console.error('❌ WebSocket error:', error);
        });

        this.ws.on('close', (code, reason) => {
            console.log(`🔌 WebSocket connection closed. Code: ${code}, Reason: ${reason}`);
        });
    }

    handleMessage(message) {
        try {
            const data = JSON.parse(message);
            console.log(`📊 Parsed data:`, data);
            
            if (data.type === "real_time_reading") {
                const formattedData = {
                    sensor_id: data.sensor_id,
                    temperature: data.temperature,
                    latitude: data.position.latitude,
                    longitude: data.position.longitude,
                    speed_kms: data.speed_kms,
                    connection_speed_mbps: data.connection_speed_mbps,
                    total_pipeline_us: data.total_pipeline_us,
                    timestamp: new Date(data.reading_timestamp_ms).toISOString()
                };
                console.log(`🔄 Updating table with:`, formattedData);
                this.table.update([formattedData]);
                console.log(`✅ Table updated successfully`);
            } else {
                console.log(`ℹ️ Received non-realtime message:`, data);
            }
        } catch (error) {
            console.error('❌ Error processing message:', error);
            console.error('Raw message was:', message);
        }
    }
}

/**
 * Create a Perspective table.
 */
async function createPerspectiveTable() {
    const schema = {
        sensor_id: "string",
        temperature: "float",
        latitude: "float",
        longitude: "float",
        speed_kms: "float",
        connection_speed_mbps: "float",
        total_pipeline_us: "integer",
        timestamp: "datetime"
    };
    const table = await perspective.table(schema, {
        name: PERSPECTIVE_TABLE_NAME,
        limit: 2500,
        format: "json"
    });
    console.log(`Created Perspective table: '${PERSPECTIVE_TABLE_NAME}'`);
    return table;
}

/**
 * Main function to initialize and run the Perspective server.
 */
async function main() {
    // Create a Perspective WebSocket server
    const server = new perspective.WebSocketServer({ port: 8081 });
    console.log("Perspective WebSocket server is running on ws://localhost:8081/websocket");

    // Create the Perspective table
    const table = await createPerspectiveTable();
    
    // Create and connect WebSocket client
    const wsClient = new WebSocketClient(table);
    wsClient.connect();
}

// Run the main function
main().catch(err => {
    console.error("Error starting the server:", err);
    process.exit(1);
});