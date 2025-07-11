import { createSignal, batch } from 'solid-js';
import { RealTimeReading } from '../types';

export const [connected, setConnected] = createSignal(false);
export const [sensorData, setSensorData] = createSignal<Map<string, RealTimeReading>>(new Map());

class WebSocketService {
  private ws: WebSocket | null = null;
  private messageQueue: RealTimeReading[] = [];
  private batchTimeout: number | null = null;
  private lastUpdate = 0;
  private readonly BATCH_SIZE = 10;
  private readonly THROTTLE_MS = 100;

  connect(url: string) {
    this.ws = new WebSocket(url);
    
    this.ws.onopen = () => {
      setConnected(true);
    };
    
    this.ws.onclose = () => {
      setConnected(false);
    };
    
    this.ws.onerror = () => {};
    
    this.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        
        if (data.type === 'real_time_reading') {
          const reading: RealTimeReading = {
            ...data,
            reading_timestamp_ns: BigInt(data.reading_timestamp_ns || Date.now() * 1000000),
            cache_timestamp_ns: BigInt(data.cache_timestamp_ns || 0),
            notification_timestamp_ns: BigInt(data.notification_timestamp_ns || Date.now() * 1000000),
            websocket_to_frontend_us: data.notification_timestamp_ns ? 
              Math.floor(((Date.now() * 1000.0) * 1000 - Number(data.notification_timestamp_ns)) / 1000) : 0
          };
          
          this.queueMessage(reading);
        }
      } catch (error) {
        console.error('Parse error:', error);
      }
    };
  }

  private queueMessage(reading: RealTimeReading) {
    this.messageQueue.push(reading);
    
    if (this.messageQueue.length >= this.BATCH_SIZE || Date.now() - this.lastUpdate > this.THROTTLE_MS) {
      this.processBatch();
    } else if (!this.batchTimeout) {
      this.batchTimeout = window.setTimeout(() => this.processBatch(), this.THROTTLE_MS);
    }
  }

  private processBatch() {
    if (this.messageQueue.length === 0) return;
    
    const messages = this.messageQueue.splice(0);
    this.lastUpdate = Date.now();
    
    if (this.batchTimeout) {
      clearTimeout(this.batchTimeout);
      this.batchTimeout = null;
    }

    batch(() => {
      setSensorData(prev => {
        const newMap = new Map(prev);
        messages.forEach(reading => {
          newMap.set(reading.sensor_id, reading);
        });
        return newMap;
      });
    });
  }

  subscribe(sensorId: string) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ action: 'subscribe', sensor_id: sensorId }));
    }
  }

  disconnect() {
    this.ws?.close();
    this.ws = null;
  }
}

export const wsService = new WebSocketService();