import json
import logging
from datetime import datetime
import tornado
import tornado.websocket
import perspective
import perspective.handlers.tornado


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__file__)

# --- WebSocket constants ---
WEBSOCKET_URL = "wss://icjs840cnh.execute-api.us-east-1.amazonaws.com/prod"
PERSPECTIVE_TABLE_NAME = "sensor_data"
DEVICE_IDS = [f"device{i}" for i in range(1, 11)]  # device1 to device10



class WebSocketClient:
    def __init__(self, table):
        self.table = table
        self.ws = None
    
    async def connect_and_subscribe(self):
        try:
            self.ws = await tornado.websocket.websocket_connect(WEBSOCKET_URL)
            logger.info(f"Connected to {WEBSOCKET_URL}")
            
            # Subscribe to all devices
            for device_id in DEVICE_IDS:
                subscribe_msg = {"action": "subscribe", "sensor_id": device_id}
                await self.ws.write_message(json.dumps(subscribe_msg))
                logger.info(f"Subscribed to {device_id}")
            
            # Listen for messages
            while True:
                msg = await self.ws.read_message()
                if msg is None:
                    break
                self.handle_message(msg)
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
    
    def handle_message(self, message):
        try:
            data = json.loads(message)
            if data.get("type") == "realtime_reading":
                formatted_data = {
                    "sensor_id": data["sensor_id"],
                    "temperature": data["temperature"],
                    "latitude": data["position"]["latitude"],
                    "longitude": data["position"]["longitude"],
                    "speed_kms": data["speed_kms"],
                    "connection_speed_mbps": data["connection_speed_mbps"],
                    "total_pipeline_us": data["total_pipeline_us"],
                    "timestamp": datetime.fromtimestamp(data["reading_timestamp_ms"] / 1000).isoformat()
                }
                self.table.update([formatted_data])
        except Exception as e:
            logger.error(f"Error processing message: {e}")


def create_perspective_table(perspective_server):
    client = perspective_server.new_local_client()
    table = client.table(
        {
            "sensor_id": "string",
            "temperature": "float",
            "latitude": "float",
            "longitude": "float",
            "speed_kms": "float",
            "connection_speed_mbps": "float",
            "total_pipeline_us": "integer",
            "timestamp": "datetime",
        },
        limit=2500,
        name=PERSPECTIVE_TABLE_NAME,
        format="json",
    )
    logger.info(f"Created Perspective table: '{PERSPECTIVE_TABLE_NAME}'")
    return table





def make_app(perspective_server):
    """
    Create a new Tornado application with a websocket handler that
    serves a Perspective table. PerspectiveTornadoHandler handles
    the websocket connection and streams the Perspective table changes 
    to the client.
    """
    return tornado.web.Application([
        (
            r"/websocket",                                              # websocket endpoint. Use this URL to configure the websocket client OR Prospective Server adapter
            perspective.handlers.tornado.PerspectiveTornadoHandler,     # PerspectiveTornadoHandler handles perspective table updates <-> websocket client
            {"perspective_server": perspective_server},                 # pass the perspective server to the handler
        ),
    ])


async def main():
    perspective_server = perspective.Server()
    app = make_app(perspective_server)
    app.listen(port=8080, address='0.0.0.0')
    logger.info("App Started - Listening on ws://localhost:8080/websocket")

    table = create_perspective_table(perspective_server)
    ws_client = WebSocketClient(table)
    
    try:
        await ws_client.connect_and_subscribe()
    except KeyboardInterrupt:
        logger.warning("Shutting down...")
        if ws_client.ws:
            ws_client.ws.close()


if __name__ == "__main__":
    tornado.ioloop.IOLoop.current().run_sync(main)    