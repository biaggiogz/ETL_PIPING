// Temperature Radial Chart Integration with Perspective
let perspectiveWorker = null;
let perspectiveTable = null;
let perspectiveViewer = null;

window.initPerspectiveTable = async function(elementId) {
    try {
        console.log('Initializing Perspective table for element:', elementId);
        
        if (!window.perspective) {
            console.error('Perspective not loaded');
            return null;
        }
        
        perspectiveWorker = await perspective.worker();
        console.log('Perspective worker created');
        
        perspectiveViewer = document.getElementById(elementId);
        
        if (!perspectiveViewer) {
            console.error('Perspective viewer element not found:', elementId);
            return null;
        }
        
        console.log('Perspective viewer element found');
        
        // Create initial table with sample data to establish schema
        const initialData = [{
            sensor_id: "sample",
            temperature: 25.0,
            temp_band: "25°C-30°C",
            latitude: 40.7128,
            longitude: -74.0060,
            speed_kms: 50.0
        }];
        
        perspectiveTable = await perspectiveWorker.table(initialData, {
            limit: 1000
        });
        console.log('Perspective table created');

        await perspectiveViewer.load(perspectiveTable);
        console.log('Table loaded into viewer');
        
        // Configure for temperature band aggregation - use restore() like streaming example
        perspectiveViewer.restore({
            plugin: "Datagrid",
            group_by: ["temp_band"],
            aggregates: {
                temperature: "avg",
                sensor_id: "count distinct",
                speed_kms: "avg"
            },
            sort: [["temp_band", "asc"]],
            plugin_config: {
                scroll_lock: true
            },
            settings: true
        });
        console.log('Viewer configuration applied');
        
        // Clear the initial sample data
        await perspectiveTable.clear();
        console.log('Initial sample data cleared');
        
        return perspectiveTable;
    } catch (error) {
        console.error('Error initializing Perspective table:', error);
        return null;
    }
};

window.updatePerspectiveTable = async function(table, dataArray) {
    if (!table || !dataArray) {
        console.log('Update called but table or data missing:', !!table, !!dataArray);
        return;
    }
    
    try {
        const data = [];
        for (let i = 0; i < dataArray.length; i++) {
            const item = JSON.parse(dataArray[i]);
            data.push(item);
        }
        
        console.log('Updating Perspective table with', data.length, 'records');
        console.log('Sample data:', data[0]);
        
        if (data.length > 0) {
            // Use update() for streaming like the example, not replace()
            await table.update(data);
            console.log('Table updated successfully');
        }
    } catch (error) {
        console.error('Error updating Perspective table:', error);
    }
};

window.initTemperatureRadialChart = function(elementId) {
    const element = document.getElementById(elementId);
    if (!element || !window.echarts) {
        console.error('ECharts not loaded or element not found');
        return null;
    }
    
    const chart = echarts.init(element);
    
    const option = {
        title: {
            text: 'Temperature Distribution by 5°C Bands',
            left: 'center',
            top: 20
        },
        tooltip: {
            trigger: 'item',
            formatter: function(params) {
                return `${params.data.name}<br/>Devices: ${params.data.value}<br/>Temperature: ${params.data.temp_range}`;
            }
        },
        polar: {
            center: ['50%', '55%'],
            radius: ['20%', '80%']
        },
        angleAxis: {
            type: 'category',
            data: [],
            boundaryGap: false,
            splitLine: {
                show: true,
                lineStyle: {
                    color: '#ddd',
                    type: 'dashed'
                }
            },
            axisLabel: {
                show: true,
                color: '#666'
            }
        },
        radiusAxis: {
            type: 'value',
            min: 0,
            axisLabel: {
                show: true,
                formatter: '{value} devices'
            },
            splitLine: {
                show: true,
                lineStyle: {
                    color: '#eee'
                }
            }
        },
        series: [{
            name: 'Temperature Bands',
            type: 'bar',
            data: [],
            coordinateSystem: 'polar',
            itemStyle: {
                color: function(params) {
                    // Color gradient from blue (cold) to red (hot)
                    const tempBand = params.data.temp_band || 0;
                    const hue = Math.max(0, 240 - (tempBand * 6)); // Blue to Red
                    return `hsl(${hue}, 70%, 60%)`;
                }
            },
            emphasis: {
                itemStyle: {
                    shadowBlur: 10,
                    shadowColor: 'rgba(0, 0, 0, 0.5)'
                }
            },
            animationDuration: 1000,
            animationEasing: 'elasticOut'
        }]
    };
    
    chart.setOption(option);
    return chart;
};

window.updateTemperatureRadialChart = function(chart, bandsArray) {
    if (!chart || !bandsArray) return;
    
    try {
        const categories = [];
        const data = [];
        
        // Sort bands by temperature
        const bands = [];
        for (let i = 0; i < bandsArray.length; i++) {
            bands.push(bandsArray[i]);
        }
        bands.sort((a, b) => a.temp_band - b.temp_band);
        
        bands.forEach(band => {
            const tempRange = `${band.temp_band}°C - ${band.temp_band + 5}°C`;
            categories.push(tempRange);
            
            data.push({
                name: tempRange,
                value: band.device_count,
                temp_band: band.temp_band,
                temp_range: tempRange,
                devices: band.devices
            });
        });
        
        chart.setOption({
            angleAxis: {
                data: categories
            },
            series: [{
                data: data
            }]
        });
    } catch (error) {
        console.error('Error updating temperature radial chart:', error);
    }
};