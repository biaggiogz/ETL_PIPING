// Sensor Radar Chart Integration
window.initSensorRadarChart = function(elementId) {
    const element = document.getElementById(elementId);
    if (!element || !window.echarts) {
        console.error('ECharts not loaded or element not found');
        return null;
    }
    
    const chart = echarts.init(element);
    
    const option = {
        backgroundColor: '#161627',
        title: {
            text: 'Sensor Metrics - Radar',
            left: 'center',
            textStyle: {
                color: '#eee'
            }
        },
        legend: {
            bottom: 5,
            data: [],
            itemGap: 20,
            textStyle: {
                color: '#fff',
                fontSize: 14
            },
            selectedMode: 'multiple'
        },
        radar: {
            indicator: [
                { name: 'Temperature', max: 50 },
                { name: 'Speed', max: 100 },
                { name: 'Connection', max: 100 },
                { name: 'Latency', max: 10000 },
                { name: 'Position Lat', max: 90 },
                { name: 'Position Lng', max: 180 }
            ],
            shape: 'circle',
            splitNumber: 5,
            axisName: {
                color: 'rgb(238, 197, 102)'
            },
            splitLine: {
                lineStyle: {
                    color: [
                        'rgba(238, 197, 102, 0.1)',
                        'rgba(238, 197, 102, 0.2)',
                        'rgba(238, 197, 102, 0.4)',
                        'rgba(238, 197, 102, 0.6)',
                        'rgba(238, 197, 102, 0.8)',
                        'rgba(238, 197, 102, 1)'
                    ].reverse()
                }
            },
            splitArea: {
                show: false
            },
            axisLine: {
                lineStyle: {
                    color: 'rgba(238, 197, 102, 0.5)'
                }
            }
        },
        series: []
    };
    
    chart.setOption(option);
    return chart;
};

window.updateSensorRadarChart = function(chart, sensorsArray) {
    if (!chart || !sensorsArray) return;
    
    try {
        const sensors = [];
        for (let i = 0; i < sensorsArray.length; i++) {
            sensors.push(JSON.parse(sensorsArray[i]));
        }
        
        if (sensors.length === 0) return;
        
        const colors = ['#F9713C', '#B3E4A1', 'rgb(238, 197, 102)', '#4ECDC4', '#45B7D1', '#96CEB4', '#FECA57', '#FF6B6B'];
        const legendData = [];
        const series = [];
        
        sensors.forEach((sensor, index) => {
            const total_latency = sensor.kinesis_to_lambda_us + sensor.lambda_processing_us + 
                                 sensor.cache_to_websocket_us + sensor.websocket_to_frontend_us;
            
            const data = [
                sensor.temperature,
                sensor.speed_kms,
                sensor.connection_speed_mbps,
                total_latency / 100, // Scale down latency for visualization
                Math.abs(sensor.position.latitude),
                Math.abs(sensor.position.longitude)
            ];
            
            legendData.push(sensor.sensor_id);
            
            series.push({
                name: sensor.sensor_id,
                type: 'radar',
                lineStyle: {
                    width: 2,
                    opacity: 0.8
                },
                data: [data],
                symbol: 'circle',
                symbolSize: 4,
                itemStyle: {
                    color: colors[index % colors.length]
                },
                areaStyle: {
                    opacity: 0.1
                }
            });
        });
        
        chart.setOption({
            legend: {
                data: legendData
            },
            series: series
        });
        
    } catch (error) {
        console.error('Error updating sensor radar chart:', error);
    }
};