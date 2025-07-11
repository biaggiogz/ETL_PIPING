import { Component, createSignal, onMount, createEffect, For } from 'solid-js';
import { wsService, connected, sensorData } from '../services/websocket';
import { duckDBService } from '../services/duckdb';
import { LatencyMetrics } from '../types';
import SensorCard from './SensorCard';
import LatencyChart from './LatencyChart';
import SpeedRacing from './SpeedRacing';

const Dashboard: Component = () => {
  const [wsUrl, setWsUrl] = createSignal('wss://icjs840cnh.execute-api.us-east-1.amazonaws.com/prod');
  const [sensorId, setSensorId] = createSignal('device1');
  const [deviceCount, setDeviceCount] = createSignal(10);
  const [latencyMetrics, setLatencyMetrics] = createSignal<LatencyMetrics[]>([]);

  onMount(async () => {
    await duckDBService.init();
    
    // Cleanup old data every 5 minutes
    setInterval(() => duckDBService.cleanup(), 5 * 60 * 1000);

    // Update latency metrics every second
    setInterval(async () => {
      const metrics = await duckDBService.getLatencyMetrics();
      setLatencyMetrics(metrics);
    }, 1000);
  });

  createEffect(() => {
    const data = sensorData();
    console.log('Dashboard effect triggered, sensor count:', data.size);

    // Store new readings in DuckDB
    data.forEach(async (reading) => {
      await duckDBService.insertReading(reading);
    });
  });

  const connect = () => {
    console.log('Connecting to:', wsUrl());
    wsService.connect(wsUrl());
  };

  const disconnect = () => wsService.disconnect();

  const subscribe = () => {
    console.log('Subscribing to', deviceCount(), 'devices');
    for (let i = 1; i <= deviceCount(); i++) {
      const deviceId = `device${i}`;
      console.log('Subscribing to:', deviceId);
      wsService.subscribe(deviceId);
    }
  };

  return (
    <div class="dashboard">
      <header class="dashboard-header">
        <h1>SolidJS IoT Dashboard - Real-time Latency Tracking</h1>
        <div class="connection-status">
          <span class={connected() ? "status connected" : "status disconnected"}>
            {connected() ? "🟢 Connected" : "🔴 Disconnected"}
          </span>
        </div>
      </header>

      <div class="controls">
        <div class="control-group">
          <label>WebSocket URL:</label>
          <input 
            type="text" 
            value={wsUrl()} 
            onInput={(e) => setWsUrl(e.currentTarget.value)}
            placeholder="wss://your-endpoint.amazonaws.com/prod"
          />
        </div>
        
        <div class="control-group">
          <label>Number of Devices:</label>
          <input 
            type="number" 
            value={deviceCount()} 
            onInput={(e) => setDeviceCount(parseInt(e.currentTarget.value) || 1)}
            placeholder="10"
            min="1"
            max="100"
          />
        </div>

        <div class="button-group">
          <button onClick={connect} disabled={connected()}>Connect</button>
          <button onClick={disconnect} disabled={!connected()}>Disconnect</button>
          <button onClick={subscribe} disabled={!connected()}>Subscribe {deviceCount()} Devices</button>
        </div>
      </div>

      <div class="content">
        <div class="sensors-grid">
          {sensorData().size === 0 ? (
            <div style="grid-column: 1 / -1; text-align: center; padding: 40px; color: #666;">
              {connected() ? 'Connected - Waiting for sensor data...' : 'Not connected'}
            </div>
          ) : (
            <For each={Array.from(sensorData().values())}>
              {(reading) => <SensorCard reading={reading} />}
            </For>
          )}
        </div>

        <div class="latency-section">
          <h2>Pipeline Latency Metrics</h2>
          <LatencyChart metrics={latencyMetrics()} />
        </div>

        <SpeedRacing readings={sensorData()} />
      </div>
    </div>
  );
};

export default Dashboard;