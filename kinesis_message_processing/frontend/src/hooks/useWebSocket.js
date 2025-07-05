import { useState, useEffect, useRef, useCallback } from 'react';

export const useWebSocket = (url) => {
  const [isConnected, setIsConnected] = useState(false);
  const [sensorData, setSensorData] = useState(new Map());
  const [subscribedSensors, setSubscribedSensors] = useState(new Set());
  const [messageCount, setMessageCount] = useState(0);
  const ws = useRef(null);
  const sensorDataRef = useRef(new Map());
  const subscribedSensorsRef = useRef(new Set());

  const handleMessage = useCallback((data) => {
    setMessageCount(prev => prev + 1);
    
    switch (data.type) {
      case 'real_time_reading':
        sensorDataRef.current.set(data.sensor_id, {
          ...data,
          lastUpdated: Date.now()
        });
        setSensorData(new Map(sensorDataRef.current));
        break;
      case 'latest_readings':
        if (data.readings && data.readings.length > 0) {
          const latest = data.readings[0];
          sensorDataRef.current.set(data.sensor_id, {
            ...latest,
            lastUpdated: Date.now()
          });
          setSensorData(new Map(sensorDataRef.current));
        }
        break;
      case 'all_latest_readings':
        for (const [sensorId, readings] of Object.entries(data.sensors)) {
          if (readings && readings.length > 0) {
            const latest = readings[0];
            sensorDataRef.current.set(sensorId, {
              ...latest,
              lastUpdated: Date.now()
            });
          }
        }
        setSensorData(new Map(sensorDataRef.current));
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
  }, []);

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
  }, [url, handleMessage]);

  const sendMessage = useCallback((message) => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify(message));
    }
  }, []);

  const subscribeToSensor = useCallback((sensorId) => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify({
        action: 'subscribe',
        sensor_id: sensorId
      }));
      subscribedSensorsRef.current.add(sensorId);
      setSubscribedSensors(new Set(subscribedSensorsRef.current));
    }
  }, []);

  return { 
    isConnected, 
    sensorData, 
    subscribedSensors, 
    messageCount, 
    sendMessage, 
    subscribeToSensor 
  };
};
