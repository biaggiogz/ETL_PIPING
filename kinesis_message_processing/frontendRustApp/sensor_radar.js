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
        if (sensorsArray.length === 0) return;
        
        const colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#F9713C', '#FECA57', '#96CEB4', '#9B59B6', '#E67E22', '#2ECC71', '#3498DB', '#E74C3C', '#F39C12'];
        const legendData = [];
        const series = [];
        
        // Process pre-calculated data from WASM
        for (let i = 0; i < sensorsArray.length; i++) {
            const sensor = sensorsArray[i];
            
            legendData.push(sensor.sensor_id);
            
            series.push({
                name: sensor.sensor_id,
                type: 'radar',
                lineStyle: {
                    width: 2,
                    opacity: 0.8
                },
                data: [sensor.values],
                symbol: 'none', // Remove symbols for better performance
                itemStyle: {
                    color: colors[i % colors.length]
                },
                areaStyle: {
                    opacity: 0.1
                },
                animation: false // Disable animations for better performance
            });
        }
        
        // Use notMerge: false for better performance
        chart.setOption({
            legend: {
                data: legendData
            },
            series: series
        }, false, false);
        
    } catch (error) {
        console.error('Error updating sensor radar chart:', error);
    }
};