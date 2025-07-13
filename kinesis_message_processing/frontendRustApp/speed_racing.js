// Speed Racing Chart Integration
window.initSpeedRacingChart = function(elementId) {
    const element = document.getElementById(elementId);
    if (!element || !window.echarts) {
        console.error('ECharts not loaded or element not found');
        return null;
    }
    
    const chart = echarts.init(element);
    
    const option = {
        title: {
            text: 'Real-time Device Speed Racing',
            left: 'center'
        },
        tooltip: {
            trigger: 'axis',
            axisPointer: { type: 'shadow' }
        },
        grid: {
            left: '15%',
            right: '10%',
            top: '15%',
            bottom: '10%'
        },
        xAxis: {
            type: 'value',
            name: 'Speed (km/h)',
            max: 100,
            axisLabel: { formatter: '{value} km/h' }
        },
        yAxis: {
            type: 'category',
            data: [],
            axisLabel: { interval: 0 }
        },
        series: [{
            name: 'Speed',
            type: 'bar',
            data: [],
            itemStyle: {
                color: function(params) {
                    const speed = params.value;
                    if (speed < 20) return '#91cc75';      // Green
                    if (speed < 50) return '#fac858';      // Yellow
                    if (speed < 80) return '#ee6666';      // Red
                    return '#9a60b4';                      // Purple
                }
            },
            label: {
                show: true,
                position: 'right',
                formatter: function(params) {
                    return parseFloat(params.value).toFixed(1) + ' km/h';
                }
            },
            animationDuration: 1000,
            animationEasing: 'elasticOut'
        }]
    };
    
    chart.setOption(option);
    return chart;
};

window.updateSpeedRacingChart = function(chart, devices, speeds) {
    if (!chart) return;
    
    // Round speeds to 1 decimal place
    const roundedSpeeds = speeds.map(speed => parseFloat(speed).toFixed(1));
    
    chart.setOption({
        yAxis: { data: devices },
        series: [{ data: roundedSpeeds }]
    });
};