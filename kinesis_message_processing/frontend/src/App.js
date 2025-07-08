import React, { useState, useEffect, useRef } from 'react';
import './App.css';

const App = () => {
  const [ws, setWs] = useState(null);
  const [connected, setConnected] = useState(false);
  const [sensorData, setSensorData] = useState({});
  const [latencyMetrics, setLatencyMetrics] = useState({});
  const [subscribedSensors, setSubscribedSensors] = useState(new Set());
  const wsRef = useRef(null);

  const WEBSOCKET_URL = process.env.REACT_APP_WEBSOCKET_URL || 'wss://your-websocket-url';

  useEffect(() => {
    connectWebSocket();
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, []);

  const connectWebSocket = () => {
    const websocket = new WebSocket(WEBSOCKET_URL);
    wsRef.current = websocket;

    websocket.onopen = () => {
      setConnected(true);
      setWs(websocket);
    };

    websocket.onmessage = (event) => {
      const data = JSON.parse(event.data);
      const frontendReceiveTime = performance.now() * 1000; // microseconds
      
      if (data.type === 'real_time_reading') {
        const sensorId = data.sensor_id;
        
        // Calculate frontend latency
        const websocketToFrontendUs = data.notification_timestamp_ns ? 
          Math.round((frontendReceiveTime * 1000 - data.notification_timestamp_ns) / 1000) : 0;
        
        const totalPipelineUs = data.kinesis_to_lambda_us + 
          data.lambda_processing_us + 
          data.cache_to_websocket_us + 
          websocketToFrontendUs;

        const latency = {
          kinesis_to_lambda_us: data.kinesis_to_lambda_us || 0,
          lambda_processing_us: data.lambda_processing_us || 0,
          cache_to_websocket_us: data.cache_to_websocket_us || 0,
          websocket_to_frontend_us: websocketToFrontendUs,
          total_pipeline_us: totalPipelineUs,
          timestamp: Date.now()
        };

        setSensorData(prev => ({
          ...prev,
          [sensorId]: {
            ...data,
            websocket_to_frontend_us: websocketToFrontendUs,
            total_pipeline_us: totalPipelineUs,
            lastUpdate: Date.now()
          }
        }));

        setLatencyMetrics(prev => ({
          ...prev,
          [sensorId]: latency
        }));
      }
    };

    websocket.onclose = () => {
      setConnected(false);
      setWs(null);
      setTimeout(connectWebSocket, 3000);
    };

    websocket.onerror = () => {
      setConnected(false);
    };
  };

  const subscribeTo = (sensorId) => {
    if (ws && !subscribedSensors.has(sensorId)) {
      ws.send(JSON.stringify({
        action: 'subscribe',
        sensor_id: sensorId
      }));
      setSubscribedSensors(prev => new Set([...prev, sensorId]));
    }
  };

  const unsubscribeFrom = (sensorId) => {
    if (ws && subscribedSensors.has(sensorId)) {
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

  const formatLatency = (us) => {
    if (us < 1000) return `${us}μs`;
    if (us < 1000000) return `${(us/1000).toFixed(1)}ms`;
    return `${(us/1000000).toFixed(2)}s`;
  };

  const getLatencyColor = (us) => {
    if (us < 1000) return '#4CAF50';
    if (us < 10000) return '#FF9800';
    return '#F44336';
  };

  return (
    <div className="app">
      <header className="header">
        <h1>🌡️ Sensor Dashboard</h1>
        <div className={`status ${connected ? 'connected' : 'disconnected'}`}>
          {connected ? '🟢 Connected' : '🔴 Disconnected'}
        </div>
      </header>

      <div className="controls">
        <input 
          type="text" 
          placeholder="Enter sensor ID (e.g., device1)"
          onKeyPress={(e) => {
            if (e.key === 'Enter' && e.target.value.trim()) {
              subscribeTo(e.target.value.trim());
              e.target.value = '';
            }
          }}
        />
        <div className="quick-subscribe">
          {['device1', 'device2', 'device3', 'device4', 'device5'].map(id => (
            <button 
              key={id}
              onClick={() => subscribeTo(id)}
              className={subscribedSensors.has(id) ? 'subscribed' : ''}
            >
              {id}
            </button>
          ))}
        </div>
      </div>

      <div className="dashboard">
        {Object.entries(sensorData).map(([sensorId, data]) => (
          <div key={sensorId} className="sensor-card">
            <div className="sensor-header">
              <h3>{sensorId}</h3>
              <button 
                onClick={() => unsubscribeFrom(sensorId)}
                className="unsubscribe-btn"
              >
                ✕
              </button>
            </div>
            
            <div className="sensor-data">
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

            {latencyMetrics[sensorId] && (
              <div className="latency-pipeline">
                <h4>📊 Pipeline Latency</h4>
                <div className="pipeline-stages">
                  <div className="stage">
                    <div className="stage-name">Kinesis→Lambda</div>
                    <div 
                      className="stage-value"
                      style={{color: getLatencyColor(latencyMetrics[sensorId].kinesis_to_lambda_us)}}
                    >
                      {formatLatency(latencyMetrics[sensorId].kinesis_to_lambda_us)}
                    </div>
                  </div>
                  <div className="stage">
                    <div className="stage-name">Lambda Processing</div>
                    <div 
                      className="stage-value"
                      style={{color: getLatencyColor(latencyMetrics[sensorId].lambda_processing_us)}}
                    >
                      {formatLatency(latencyMetrics[sensorId].lambda_processing_us)}
                    </div>
                  </div>
                  <div className="stage">
                    <div className="stage-name">Cache→WebSocket</div>
                    <div 
                      className="stage-value"
                      style={{color: getLatencyColor(latencyMetrics[sensorId].cache_to_websocket_us)}}
                    >
                      {formatLatency(latencyMetrics[sensorId].cache_to_websocket_us)}
                    </div>
                  </div>
                  <div className="stage">
                    <div className="stage-name">WebSocket→Frontend</div>
                    <div 
                      className="stage-value"
                      style={{color: getLatencyColor(latencyMetrics[sensorId].websocket_to_frontend_us)}}
                    >
                      {formatLatency(latencyMetrics[sensorId].websocket_to_frontend_us)}
                    </div>
                  </div>
                </div>
                <div className="total-latency">
                  <strong>Total: {formatLatency(latencyMetrics[sensorId].total_pipeline_us)}</strong>
                </div>
              </div>
            )}
            
            <div className="last-update">
              Last update: {new Date(data.lastUpdate).toLocaleTimeString()}
            </div>
          </div>
        ))}
      </div>

      {Object.keys(sensorData).length === 0 && (
        <div className="empty-state">
          <p>No sensors subscribed. Enter a sensor ID above to start monitoring.</p>
        </div>
      )}
    </div>
  );
};

export default App;