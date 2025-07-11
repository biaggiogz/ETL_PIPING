import { Component, onMount, createEffect } from 'solid-js';
import * as echarts from 'echarts';
import { RealTimeReading } from '../types';

interface SpeedRacingProps {
  readings: Map<string, RealTimeReading>;
}

const SpeedRacing: Component<SpeedRacingProps> = (props) => {
  let chartRef: HTMLDivElement;
  let chart: echarts.ECharts;

  let lastUpdateTime = 0;
  const UPDATE_THROTTLE = 500;

  onMount(() => {
    chart = echarts.init(chartRef, null, { renderer: 'canvas' });
    
    chart.setOption({
      animation: false,
      title: { text: 'Real-time Device Speed Racing', left: 'center' },
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
      grid: { left: '15%', right: '10%', top: '15%', bottom: '10%' },
      xAxis: { type: 'value', name: 'Speed (km/h)', max: 100 },
      yAxis: { type: 'category', data: [] },
      series: [{
        name: 'Speed',
        type: 'bar',
        data: [],
        itemStyle: {
          color: (params: any) => {
            const speed = params.value;
            if (speed < 20) return '#91cc75';
            if (speed < 50) return '#fac858';
            if (speed < 80) return '#ee6666';
            return '#9a60b4';
          }
        },
        label: { show: true, position: 'right', formatter: '{c} km/h' }
      }]
    });
  });

  createEffect(() => {
    if (!chart || !props.readings.size) return;

    const sorted = Array.from(props.readings.values())
      .sort((a, b) => b.speed_kms - a.speed_kms);

    chart.setOption({
      yAxis: { data: sorted.map(r => r.sensor_id) },
      series: [{ data: sorted.map(r => r.speed_kms) }]
    });
  });

  return (
    <div class="speed-racing-section">
      <h2>Device Speed Racing</h2>
      <div ref={chartRef!} style={{ width: '100%', height: '400px' }} />
    </div>
  );
};

export default SpeedRacing;