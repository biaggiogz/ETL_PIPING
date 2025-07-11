import { Component, onMount, createEffect } from 'solid-js';
import * as echarts from 'echarts';
import { LatencyMetrics } from '../types';

interface LatencyChartProps {
  metrics: LatencyMetrics[];
}

const LatencyChart: Component<LatencyChartProps> = (props) => {
  let chartRef: HTMLDivElement;
  let chart: echarts.ECharts;

  let lastUpdateTime = 0;
  const UPDATE_THROTTLE = 1000;

  onMount(() => {
    chart = echarts.init(chartRef, null, { renderer: 'canvas' });
    
    chart.setOption({
      animation: false,
      tooltip: { trigger: 'axis' },
      legend: { data: ['Kinesis→Lambda', 'Lambda Processing', 'Cache→WebSocket', 'WebSocket→Frontend'] },
      xAxis: { type: 'time' },
      yAxis: { type: 'value', name: 'Latency (μs)' },
      series: [
        { name: 'Kinesis→Lambda', type: 'line', data: [], symbol: 'none' },
        { name: 'Lambda Processing', type: 'line', data: [], symbol: 'none' },
        { name: 'Cache→WebSocket', type: 'line', data: [], symbol: 'none' },
        { name: 'WebSocket→Frontend', type: 'line', data: [], symbol: 'none' }
      ]
    });
  });

  createEffect(() => {
    if (!chart || !props.metrics.length) return;

    const data = props.metrics.slice(-30).map(m => ({
      timestamp: m.timestamp,
      kinesis: m.kinesis_to_lambda_us,
      lambda: m.lambda_processing_us,
      cache: m.cache_to_websocket_us,
      websocket: m.websocket_to_frontend_us
    }));

    chart.setOption({
      series: [
        { data: data.map(d => [d.timestamp, d.kinesis]) },
        { data: data.map(d => [d.timestamp, d.lambda]) },
        { data: data.map(d => [d.timestamp, d.cache]) },
        { data: data.map(d => [d.timestamp, d.websocket]) }
      ]
    });
  });

  return <div ref={chartRef!} style={{ width: '100%', height: '400px' }} />;
};

export default LatencyChart;