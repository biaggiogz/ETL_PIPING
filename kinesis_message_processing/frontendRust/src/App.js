import React, { useState, useEffect, useRef } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar } from 'recharts';
import './App.css';

const App = () => {
  const [ws, setWs] = useState(null);
  const [connected, setConnected] = useState(false);
  const [sensorData, setSensorData] = useState({});
  const [latencyData, setLatencyData] = useState([]);
  const [subscribedSensors, setSubscribedSensors] = useState(new Set());
  const wsRef = useRef(null);

  useEffect(() => {
    const websocketUrl = process.env.REACT_APP_WEBSOCKET_URL || 'wss://your-websocket-url';
    const socket = new WebSocket(websocketUrl);
    wsRef.current = socket;

    socket.onopen = () => {
      setConnected(true);
      setWs(socket);
    };

    socket.onmessage = (event) => {
      const data = JSON.parse(event.data);
      const frontendReceiveTime = performance.now() * 1000; // microseconds
      
      if (data.type === 'real_time_reading') {
        const sensorId = data.sensor_id;
        
        // Calculate frontend latency
        const websocketToFrontendUs = data.notification_timestamp_ns ? 
          Math.round((frontendReceiveTime - (data.notification_timestamp_ns / 1000)) / 1000) : 0;
        
        // Update sensor data
        setSensorData(prev => ({
          ...prev,
          [sensorId]: {
            ...data,
            websocket_to_frontend_us: websocketToFrontendUs,
            frontend_receive_time: frontendReceiveTime
          }
        }));

        // Update latency tracking
        if (data.pipeline_tracking) {
          const latencyMetrics = {
            timestamp: Date.now(),
            sensor_id: sensorId,
            kinesis_to_lambda: data.kinesis_to_lambda_us || 0,
            lambda_processing: data.lambda_processing_us || 0,
            cache_to_websocket: data.cache_to_websocket_us || 0,
            websocket_to_frontend: websocketToFrontendUs,
            total_pipeline: (data.kinesis_to_lambda_us || 0) + 
                           (data.lambda_processing_us || 0) + 
                           (data.cache_to_websocket_us || 0) + 
                           websocketToFrontendUs
          };
          
          setLatencyData(prev => [...prev.slice(-49), latencyMetrics]);
        }
      }
    };

    socket.onclose = () => {
      setConnected(false);
      setWs(null);
    };

    return () => {
      socket.close();
    };
  }, []);

  const subscribeTo = (sensorId) => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({
        action: 'subscribe',
        sensor_id: sensorId
      }));
      setSubscribedSensors(prev => new Set([...prev, sensorId]));
    }
  };

  const unsubscribeFrom = (sensorId) => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({
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

  const formatLatency = (us) => us < 1000 ? `${us}μs` : `${(us/1000).toFixed(1)}ms`;

  return (
    <div className="dashboard">
      <header className="header">
        <h1>Sensor Dashboard</h1>
        <div className={`status ${connected ? 'connected' : 'disconnected'}`}>
          {connected ? '🟢 Connected' : '🔴 Disconnected'}
        </div>
      </header>

      <div className="controls">
        <input 
          type="text" 
          placeholder="Sensor ID (e.g., device1)"
          onKeyPress={(e) => {
            if (e.key === 'Enter' && e.target.value) {
              subscribeTo(e.target.value);
              e.target.value = '';
            }
          }}
        />
        <div className="subscribed">
          {Array.from(subscribedSensors).map(sensorId => (
            <span key={sensorId} className="sensor-tag">
              {sensorId}
              <button onClick={() => unsubscribeFrom(sensorId)}>×</button>
            </span>
          ))}
        </div>
      </div>

      <div className="metrics-grid">
        {Object.entries(sensorData).map(([sensorId, data]) => (
          <div key={sensorId} className="sensor-card">
            <h3>{sensorId}</h3>
            <div className="sensor-metrics">
              <div className="metric">
                <span className="label">Temperature:</span>
                <span className="value">{data.temperature?.toFixed(1)}°C</span>
              </div>
              <div className="metric">
                <span className="label">Speed:</span>
                <span className="value">{data.speed_kms?.toFixed(1)} km/h</span>
              </div>
              <div className="metric">
                <span className="label">Connection:</span>
                <span className="value">{data.connection_speed_mbps?.toFixed(1)} Mbps</span>
              </div>
              <div className="metric">
                <span className="label">Position:</span>
                <span className="value">
                  {data.position?.latitude?.toFixed(4)}, {data.position?.longitude?.toFixed(4)}
                </span>
              </div>
            </div>
            
            <div className="latency-breakdown">
              <h4>Pipeline Latency</h4>
              <div className="latency-item">
                <span>Kinesis → Lambda:</span>
                <span>{formatLatency(data.kinesis_to_lambda_us || 0)}</span>
              </div>
              <div className="latency-item">
                <span>Lambda Processing:</span>
                <span>{formatLatency(data.lambda_processing_us || 0)}</span>
              </div>
              <div className="latency-item">
                <span>Cache → WebSocket:</span>
                <span>{formatLatency(data.cache_to_websocket_us || 0)}</span>
              </div>
              <div className="latency-item">
                <span>WebSocket → Frontend:</span>
                <span>{formatLatency(data.websocket_to_frontend_us || 0)}</span>
              </div>
              <div className="latency-item total">
                <span>Total Pipeline:</span>
                <span>{formatLatency(
                  (data.kinesis_to_lambda_us || 0) + 
                  (data.lambda_processing_us || 0) + 
                  (data.cache_to_websocket_us || 0) + 
                  (data.websocket_to_frontend_us || 0)
                )}</span>
              </div>
            </div>
          </div>
        ))}
      </div>

      {latencyData.length > 0 && (
        <div className="charts">
          <div className="chart-container">
            <h3>Pipeline Latency Over Time</h3>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={latencyData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="timestamp" tickFormatter={(ts) => new Date(ts).toLocaleTimeString()} />
                <YAxis label={{ value: 'Latency (μs)', angle: -90, position: 'insideLeft' }} />
                <Tooltip 
                  labelFormatter={(ts) => new Date(ts).toLocaleTimeString()}
                  formatter={(value, name) => [formatLatency(value), name]}
                />
                <Line type="monotone" dataKey="kinesis_to_lambda" stroke="#8884d8" name="Kinesis→Lambda" />
                <Line type="monotone" dataKey="lambda_processing" stroke="#82ca9d" name="Lambda Processing" />
                <Line type="monotone" dataKey="cache_to_websocket" stroke="#ffc658" name="Cache→WebSocket" />
                <Line type="monotone" dataKey="websocket_to_frontend" stroke="#ff7300" name="WebSocket→Frontend" />
                <Line type="monotone" dataKey="total_pipeline" stroke="#ff0000" strokeWidth={2} name="Total Pipeline" />
              </LineChart>
            </ResponsiveContainer>
          </div>

          <div className="chart-container">
            <h3>Latest Latency Breakdown</h3>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={latencyData.slice(-1)}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="sensor_id" />
                <YAxis label={{ value: 'Latency (μs)', angle: -90, position: 'insideLeft' }} />
                <Tooltip formatter={(value) => [formatLatency(value), 'Latency']} />
                <Bar dataKey="kinesis_to_lambda" stackId="a" fill="#8884d8" name="Kinesis→Lambda" />
                <Bar dataKey="lambda_processing" stackId="a" fill="#82ca9d" name="Lambda Processing" />
                <Bar dataKey="cache_to_websocket" stackId="a" fill="#ffc658" name="Cache→WebSocket" />
                <Bar dataKey="websocket_to_frontend" stackId="a" fill="#ff7300" name="WebSocket→Frontend" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </div>
  );
};

export default App;