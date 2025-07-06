import React, { useState, useEffect, useRef } from 'react';
import * as d3 from 'd3';
import './App.css';

function App() {
  const [websocket, setWebsocket] = useState(null);
  const [isConnected, setIsConnected] = useState(false);
  const [websocketUrl, setWebsocketUrl] = useState('wss://your-api-id.execute-api.region.amazonaws.com/prod');
  const [selectedSensor, setSelectedSensor] = useState('');
  const [sensorData, setSensorData] = useState(new Map());
  const [subscribedSensors, setSubscribedSensors] = useState(new Set());
  const [messageCount, setMessageCount] = useState(0);
  const [latencySum, setLatencySum] = useState(0);
  const [messageTimestamps, setMessageTimestamps] = useState([]);

  useEffect(() => {
    const interval = setInterval(() => {
      if (isConnected && websocket) {
        websocket.send(JSON.stringify({ action: 'get_latest' }));
      }
    }, 500);
    return () => clearInterval(interval);
  }, [isConnected, websocket]);

  const toggleConnection = () => {
    if (isConnected) {
      disconnect();
    } else {
      connect();
    }
  };

  const connect = () => {
    if (!websocketUrl) {
      alert('Please enter WebSocket URL');
      return;
    }

    const ws = new WebSocket(websocketUrl);
    
    ws.onopen = () => {
      setIsConnected(true);
      setWebsocket(ws);
      console.log('Connected to WebSocket');
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        handleMessage(data);
      } catch (error) {
        console.error('Message parsing error:', error);
      }
    };

    ws.onclose = () => {
      setIsConnected(false);
      setWebsocket(null);
      console.log('WebSocket disconnected');
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };
  };

  const disconnect = () => {
    if (websocket) {
      websocket.close();
    }
  };

  const handleMessage = (data) => {
    setMessageCount(prev => prev + 1);
    const now = performance.now();
    setMessageTimestamps(prev => {
      const updated = [...prev, now];
      const tenSecondsAgo = now - 10000;
      return updated.filter(t => t > tenSecondsAgo);
    });

    switch (data.type) {
      case 'real_time_reading':
        handleRealTimeReading(data);
        break;
      case 'latest_readings':
        handleLatestReadings(data);
        break;
      case 'all_latest_readings':
        handleAllLatestReadings(data);
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

  const handleRealTimeReading = (data) => {
    const latencyUs = data.cache_to_notification_latency_us || 0;
    setLatencySum(prev => prev + latencyUs);
    
    setSensorData(prev => {
      const newData = new Map(prev);
      newData.set(data.sensor_id, {
        ...data,
        lastUpdated: Date.now()
      });
      return newData;
    });
  };

  const handleLatestReadings = (data) => {
    if (data.readings && data.readings.length > 0) {
      const latest = data.readings[0];
      setSensorData(prev => {
        const newData = new Map(prev);
        newData.set(data.sensor_id, {
          ...latest,
          lastUpdated: Date.now()
        });
        return newData;
      });
    }
  };

  const handleAllLatestReadings = (data) => {
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
  };

  const getAllLatest = () => {
    if (websocket && isConnected) {
      websocket.send(JSON.stringify({ action: 'get_latest' }));
    }
  };

  const subscribeToSelected = () => {
    if (!selectedSensor) {
      alert('Please select a sensor');
      return;
    }
    subscribeToSensor(selectedSensor);
  };

  const subscribeToSensor = (sensorId) => {
    if (websocket && isConnected) {
      websocket.send(JSON.stringify({
        action: 'subscribe',
        sensor_id: sensorId
      }));
      setSubscribedSensors(prev => new Set([...prev, sensorId]));
    }
  };

  const toggleSensorSubscription = (sensorId) => {
    if (subscribedSensors.has(sensorId)) {
      unsubscribeFromSensor(sensorId);
    } else {
      subscribeToSensor(sensorId);
    }
  };

  const unsubscribeFromSensor = (sensorId) => {
    if (websocket && isConnected) {
      websocket.send(JSON.stringify({
        action: 'unsubscribe',
        sensor_id: sensorId
      }));
      setSubscribedSensors(prev => {
        const newSet = new Set(prev);
        newSet.delete(sensorId);
        return newSet;
      });
    }
  };

  const getMetrics = () => {
    const totalSensors = sensorData.size;
    const temperatures = Array.from(sensorData.values()).map(d => d.temperature).filter(t => t != null);
    const avgTemp = temperatures.length > 0 ? temperatures.reduce((a, b) => a + b, 0) / temperatures.length : 0;
    const avgLatency = messageCount > 0 ? Math.round(latencySum / messageCount) : 0;
    const messagesPerSecond = (messageTimestamps.length / 10).toFixed(1);
    
    return { totalSensors, avgTemp, avgLatency, messagesPerSecond };
  };

  const metrics = getMetrics();
  const availableSensors = Array.from(sensorData.keys());

  return (
    <div className="dashboard">
      <div className="sidebar">
        <h2>🚀 Sensor Control</h2>
        
        <div className={`connection-status ${isConnected ? 'connected' : 'disconnected'}`}>
          {isConnected ? '✅ Connected' : '❌ Disconnected'}
          {isConnected && <span className="real-time-indicator"></span>}
        </div>

        <div className="controls">
          <input 
            type="text" 
            placeholder="WebSocket URL" 
            value={websocketUrl}
            onChange={(e) => setWebsocketUrl(e.target.value)}
          />
          <button onClick={toggleConnection}>
            {isConnected ? 'Disconnect' : 'Connect'}
          </button>
          <button onClick={getAllLatest} disabled={!isConnected}>
            Get All Latest
          </button>
          
          <select 
            value={selectedSensor} 
            onChange={(e) => setSelectedSensor(e.target.value)}
          >
            <option value="">Select Sensor</option>
            {availableSensors.map(sensor => (
              <option key={sensor} value={sensor}>{sensor}</option>
            ))}
          </select>
          <button onClick={subscribeToSelected} disabled={!isConnected}>
            Subscribe
          </button>
        </div>

        <div className="sensor-list">
          {Array.from(sensorData.entries()).map(([sensorId, data]) => (
            <div 
              key={sensorId}
              className={`sensor-item ${subscribedSensors.has(sensorId) ? 'subscribed' : ''}`}
              onClick={() => toggleSensorSubscription(sensorId)}
            >
              <strong>{sensorId}</strong><br/>
              <small>Temp: {data.temperature?.toFixed(1) || 'N/A'}°C</small><br/>
              <small>Updated: {new Date(data.lastUpdated).toLocaleTimeString()}</small>
              {subscribedSensors.has(sensorId) && <br/>}
              {subscribedSensors.has(sensorId) && <small style={{color: '#28a745'}}>✓ Subscribed</small>}
            </div>
          ))}
          {sensorData.size === 0 && (
            <div style={{textAlign: 'center', color: '#666', padding: '20px'}}>
              No sensors detected
            </div>
          )}
        </div>
      </div>

      <div className="main-content">
        <div className="metrics-grid">
          <div className="metric-card">
            <div className="metric-value">{metrics.totalSensors}</div>
            <div className="metric-label">Active Sensors</div>
          </div>
          <div className="metric-card">
            <div className="metric-value">{metrics.avgTemp.toFixed(1)}°C</div>
            <div className="metric-label">Avg Temperature</div>
          </div>
          <div className="metric-card">
            <div className="metric-value">{metrics.avgLatency}μs</div>
            <div className="metric-label">Avg Latency</div>
          </div>
          <div className="metric-card">
            <div className="metric-value">{metrics.messagesPerSecond}</div>
            <div className="metric-label">Messages/Second</div>
          </div>
        </div>

        <div className="chart-container">
          <div className="chart-title">📈 Real-Time Temperature Timeline</div>
          <div>
            {isConnected ? 'Waiting for data...' : 'Connect to see real-time data'}
          </div>
        </div>

        <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px'}}>
          <div className="chart-container">
            <div className="chart-title">⚡ Latency Distribution</div>
            <div>No data available</div>
          </div>
          
          <div className="chart-container">
            <div className="chart-title">🗺️ Sensor Heatmap</div>
            <div>No data available</div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;