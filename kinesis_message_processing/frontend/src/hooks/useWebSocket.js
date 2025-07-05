import { useState, useEffect, useRef } from 'react';

export const useWebSocket = (url) => {
  const [isConnected, setIsConnected] = useState(false);
  const [sensorData, setSensorData] = useState(new Map());
  const [subscribedSensors, setSubscribedSensors] = useState(new Set());
  const [messageCount, setMessageCount] = useState(0);
  const ws = useRef(null);

  useEffect(() => {
    if (!url) return;

    ws.current = new WebSocket(url);
    
    ws.current.onopen = () => {
      setIsConnected(true);
      console.log('Connected to WebSocket');
    };

    ws.current.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        handleMessage(data);
      } catch (error) {
        console.error('Message parsing error:', error);
      }
    };

    ws.current.onclose = () => {
      setIsConnected(false);
      console.log('WebSocket disconnected');
    };

    ws.current.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    return () => ws.current?.close();
  }, [url]);

  const handleMessage = (data) => {
    setMessageCount(prev => prev + 1);
    
    switch (data.type) {
      case 'real_time_reading':
        setSensorData(prev => {
          const newData = new Map(prev);
          newData.set(data.sensor_id, {
            ...data,
            lastUpdated: Date.now()
          });
          return newData;
        });
        break;
      case 'latest_readings':
        if (data.readings && data.readings.length > 0) {
          setSensorData(prev => {
            const newData = new Map(prev);
            const latest = data.readings[0];
            newData.set(data.sensor_id, {
              ...latest,
              lastUpdated: Date.now()
            });
            return newData;
          });
        }
        break;
      case 'all_latest_readings':
        setSensorData(prev => {
          const newData = new Map(prev);
          for (const [sensorId, readings] of Object.entries(data.sensors)) {
            if (readings && readings.length > 0) {
              const latest = readings[0];
              newData.set(sensorId, {
                ...latest,
                lastUpdated: Date.now()
              });
            }
          }
          return newData;
        });
        break;
      case 'error':
        console.error('Server error:', data.message);
        break;
      case 'success':
        console.log('Server success:', data.message);
        break;
      default:
        console.log('Unknown message type:', data);
    }
  };

  const sendMessage = (message) => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify(message));
    }
  };

  const subscribeToSensor = (sensorId) => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify({
        action: 'subscribe',
        sensor_id: sensorId
      }));
      setSubscribedSensors(prev => new Set([...prev, sensorId]));
    }
  };

  return { 
    isConnected, 
    sensorData, 
    subscribedSensors, 
    messageCount, 
    sendMessage, 
    subscribeToSensor 
  };
};
