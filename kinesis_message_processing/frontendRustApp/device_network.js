// Device Network Visualization with Perlin Noise
let deviceNetworkChart = null;
let noiseHelper = null;

window.initDeviceNetworkChart = function(elementId) {
    const element = document.getElementById(elementId);
    if (!element || !window.echarts) {
        console.error('ECharts not loaded or element not found');
        return null;
    }
    
    deviceNetworkChart = echarts.init(element);
    noiseHelper = getNoiseHelper();
    noiseHelper.seed(Math.random());
    
    const option = {
        title: {
            text: 'Real-time Device Network (Lat/Lng)',
            left: 'center',
            top: 20
        },
        backgroundColor: '#f8f9fa',
        graphic: {
            elements: []
        }
    };
    
    deviceNetworkChart.setOption(option);
    return deviceNetworkChart;
};

window.updateDeviceNetworkChart = function(chart, devicesArray) {
    if (!chart || !devicesArray || !noiseHelper) return;
    
    try {
        const devices = [];
        for (let i = 0; i < devicesArray.length; i++) {
            devices.push(JSON.parse(devicesArray[i]));
        }
        
        if (devices.length === 0) return;
        
        const elements = [];
        const width = chart.getWidth() || 800;
        const height = chart.getHeight() || 400;
        const currentTime = Date.now();
        
        // Get device timestamps for animation timing
        const deviceTimestamps = devices.map(d => d.reading_timestamp_ms || currentTime);
        const avgTimestamp = deviceTimestamps.reduce((a, b) => a + b, 0) / deviceTimestamps.length;
        const timestampVariance = Math.max(...deviceTimestamps) - Math.min(...deviceTimestamps);
        
        // Create animated background circles with device-driven timing
        for (let x = 30; x < width; x += 60) {
            for (let y = 30; y < height; y += 60) {
                const rand = noiseHelper.perlin2(x / 200 + avgTimestamp / 1000000, y / 200);
                const timestampNoise = (avgTimestamp % 10000) / 10000;
                
                elements.push({
                    type: 'circle',
                    x: x,
                    y: y,
                    style: { fill: '#ffffff', stroke: 'none' },
                    shape: { r: 12 + rand * 6 },
                    keyframeAnimation: {
                        duration: 4000 + (timestampVariance % 2000),
                        loop: true,
                        delay: (rand + timestampNoise) * 3000,
                        easing: 'sinusoidalInOut',
                        keyframes: [
                            {
                                percent: 0,
                                style: { fill: '#ffffff' },
                                scaleX: 0.4,
                                scaleY: 0.4
                            },
                            {
                                percent: 0.5,
                                easing: 'sinusoidalInOut',
                                style: { fill: '#000000' },
                                scaleX: 1.2,
                                scaleY: 1.2
                            },
                            {
                                percent: 1,
                                easing: 'sinusoidalInOut',
                                style: { fill: '#ffffff' },
                                scaleX: 0.4,
                                scaleY: 0.4
                            }
                        ]
                    }
                });
            }
        }
        
        // Convert lat/lng to canvas coordinates
        const latRange = { min: Math.min(...devices.map(d => d.latitude)), max: Math.max(...devices.map(d => d.latitude)) };
        const lngRange = { min: Math.min(...devices.map(d => d.longitude)), max: Math.max(...devices.map(d => d.longitude)) };
        
        const devicePositions = devices.map(device => ({
            ...device,
            x: ((device.longitude - lngRange.min) / (lngRange.max - lngRange.min)) * (width - 100) + 50,
            y: ((latRange.max - device.latitude) / (latRange.max - latRange.min)) * (height - 100) + 50
        }));
        
        // Calculate 3 nearest neighbors for each device
        devicePositions.forEach(device => {
            const distances = devicePositions
                .filter(d => d.sensor_id !== device.sensor_id)
                .map(d => ({
                    device: d,
                    distance: Math.sqrt(Math.pow(d.x - device.x, 2) + Math.pow(d.y - device.y, 2))
                }))
                .sort((a, b) => a.distance - b.distance)
                .slice(0, 3);
            
            device.neighbors = distances.map(d => d.device);
        });
        
        // Add animated purple connection elements
        devicePositions.forEach((device, deviceIndex) => {
            device.neighbors.forEach((neighbor, neighborIndex) => {
                const midX = (device.x + neighbor.x) / 2;
                const midY = (device.y + neighbor.y) / 2;
                const connectionTime = ((device.reading_timestamp_ms || currentTime) + 
                                      (neighbor.reading_timestamp_ms || currentTime)) / 2;
                const connectionNoise = (connectionTime % 3000) / 3000;
                
                // Animated connection circle
                elements.push({
                    type: 'circle',
                    x: midX,
                    y: midY,
                    style: { fill: '#9a60b4', opacity: 0.8 },
                    shape: { r: 6 },
                    keyframeAnimation: {
                        duration: 2500 + (deviceIndex * 100),
                        loop: true,
                        delay: connectionNoise * 2000,
                        easing: 'sinusoidalInOut',
                        keyframes: [
                            {
                                percent: 0,
                                scaleX: 0.3,
                                scaleY: 0.3,
                                style: { opacity: 0.4 }
                            },
                            {
                                percent: 0.5,
                                easing: 'sinusoidalInOut',
                                scaleX: 1.5,
                                scaleY: 1.5,
                                style: { opacity: 0.9 }
                            },
                            {
                                percent: 1,
                                easing: 'sinusoidalInOut',
                                scaleX: 0.3,
                                scaleY: 0.3,
                                style: { opacity: 0.4 }
                            }
                        ]
                    }
                });
                
                // Animated connection line
                elements.push({
                    type: 'line',
                    shape: {
                        x1: device.x, y1: device.y,
                        x2: neighbor.x, y2: neighbor.y
                    },
                    style: { stroke: '#9a60b4', lineWidth: 2, opacity: 0.5 },
                    keyframeAnimation: {
                        duration: 3000,
                        loop: true,
                        delay: connectionNoise * 1500,
                        easing: 'sinusoidalInOut',
                        keyframes: [
                            { percent: 0, style: { opacity: 0.2, lineWidth: 1 } },
                            { percent: 0.5, style: { opacity: 0.8, lineWidth: 3 } },
                            { percent: 1, style: { opacity: 0.2, lineWidth: 1 } }
                        ]
                    }
                });
            });
        });
        
        // Add animated device circles integrated with organic flow
        devicePositions.forEach((device, index) => {
            const deviceTime = device.reading_timestamp_ms || currentTime;
            const timeNoise = (deviceTime % 5000) / 5000;
            const positionNoise = noiseHelper.perlin2(device.x / 300, device.y / 300);
            
            elements.push({
                type: 'circle',
                x: device.x,
                y: device.y,
                style: { 
                    fill: '#000000', 
                    stroke: '#ffffff',
                    lineWidth: 3
                },
                shape: { r: 12 },
                keyframeAnimation: {
                    duration: 3000 + (index * 200),
                    loop: true,
                    delay: timeNoise * 2000 + positionNoise * 1000,
                    easing: 'sinusoidalInOut',
                    keyframes: [
                        {
                            percent: 0,
                            scaleX: 0.8,
                            scaleY: 0.8,
                            style: { stroke: '#ffffff' }
                        },
                        {
                            percent: 0.5,
                            easing: 'sinusoidalInOut',
                            scaleX: 1.3,
                            scaleY: 1.3,
                            style: { stroke: '#9a60b4' }
                        },
                        {
                            percent: 1,
                            easing: 'sinusoidalInOut',
                            scaleX: 0.8,
                            scaleY: 0.8,
                            style: { stroke: '#ffffff' }
                        }
                    ]
                }
            });
            
            // Animated device label
            elements.push({
                type: 'text',
                x: device.x,
                y: device.y - 20,
                style: {
                    text: device.sensor_id,
                    fill: '#333',
                    fontSize: 11,
                    fontWeight: 'bold',
                    textAlign: 'center'
                },
                keyframeAnimation: {
                    duration: 2000,
                    loop: true,
                    delay: timeNoise * 1500,
                    easing: 'sinusoidalInOut',
                    keyframes: [
                        { percent: 0, style: { opacity: 0.7 } },
                        { percent: 0.5, style: { opacity: 1.0 } },
                        { percent: 1, style: { opacity: 0.7 } }
                    ]
                }
            });
        });
        
        chart.setOption({
            graphic: { elements: elements }
        });
        
    } catch (error) {
        console.error('Error updating device network chart:', error);
    }
};

// Perlin noise helper (simplified version)
function getNoiseHelper() {
    const p = [151,160,137,91,90,15,131,13,201,95,96,53,194,233,7,225,140,36,103,30,69,142,8,99,37,240,21,10,23,190,6,148,247,120,234,75,0,26,197,62,94,252,219,203,117,35,11,32,57,177,33,88,237,149,56,87,174,20,125,136,171,168,68,175,74,165,71,134,139,48,27,166,77,146,158,231,83,111,229,122,60,211,133,230,220,105,92,41,55,46,245,40,244,102,143,54,65,25,63,161,1,216,80,73,209,76,132,187,208,89,18,169,200,196,135,130,116,188,159,86,164,100,109,198,173,186,3,64,52,217,226,250,124,123,5,202,38,147,118,126,255,82,85,212,207,206,59,227,47,16,58,17,182,189,28,42,223,183,170,213,119,248,152,2,44,154,163,70,221,153,101,155,167,43,172,9,129,22,39,253,19,98,108,110,79,113,224,232,178,185,112,104,218,246,97,228,251,34,242,193,238,210,144,12,191,179,162,241,81,51,145,235,249,14,239,107,49,192,214,31,181,199,106,157,184,84,204,176,115,121,50,45,127,4,150,254,138,236,205,93,222,114,67,29,24,72,243,141,128,195,78,66,215,61,156,180];
    let perm = new Array(512);
    
    function seed(seed) {
        if (seed > 0 && seed < 1) seed *= 65536;
        seed = Math.floor(seed);
        if (seed < 256) seed |= seed << 8;
        for (let i = 0; i < 256; i++) {
            let v = (i & 1) ? p[i] ^ (seed & 255) : p[i] ^ ((seed >> 8) & 255);
            perm[i] = perm[i + 256] = v;
        }
    }
    
    function fade(t) { return t * t * t * (t * (t * 6 - 15) + 10); }
    function lerp(a, b, t) { return (1 - t) * a + t * b; }
    
    function perlin2(x, y) {
        let X = Math.floor(x) & 255, Y = Math.floor(y) & 255;
        x -= Math.floor(x); y -= Math.floor(y);
        let u = fade(x), v = fade(y);
        let A = perm[X] + Y, B = perm[X + 1] + Y;
        return lerp(lerp(perm[A] / 255, perm[B] / 255, u), lerp(perm[A + 1] / 255, perm[B + 1] / 255, u), v);
    }
    
    seed(0);
    return { seed, perlin2 };
}