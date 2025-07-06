import React, { useState, useEffect } from 'react';
import {
  ChakraProvider, Box, Grid, GridItem, VStack, HStack, Text, Button, Input, Select,
  Badge, Card, CardBody, Stat, StatLabel, StatNumber, useColorModeValue
} from '@chakra-ui/react';
import * as d3 from 'd3';

function App() {
  const [websocket, setWebsocket] = useState(null);
  const [isConnected, setIsConnected] = useState(false);
  const [websocketUrl, setWebsocketUrl] = useState('wss://your-api-id.execute-api.region.amazonaws.com/prod');
  const [selectedSensor, setSelectedSensor] = useState('');
  const [sensorData, setSensorData] = useState(new Map());
  const [subscribedSensors, setSubscribedSensors] = useState(new Set());
  const [messageCount, setMessageCount] = useState(0);
  const [latencySum, setLatencySum] = useState(0);
  const [messageTimestamps, setMessageTimestamps] = useState([]);

  useEffect(() => {
    const interval = setInterval(() => {
      if (isConnected && websocket) {
        websocket.send(JSON.stringify({ action: 'get_latest' }));
      }
    }, 500);
    return () => clearInterval(interval);
  }, [isConnected, websocket]);

  const toggleConnection = () => {
    if (isConnected) {
      disconnect();
    } else {
      connect();
    }
  };

  const connect = () => {
    if (!websocketUrl) {
      alert('Please enter WebSocket URL');
      return;
    }

    const ws = new WebSocket(websocketUrl);
    
    ws.onopen = () => {
      setIsConnected(true);
      setWebsocket(ws);
      console.log('Connected to WebSocket');
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        handleMessage(data);
      } catch (error) {
        console.error('Message parsing error:', error);
      }
    };

    ws.onclose = () => {
      setIsConnected(false);
      setWebsocket(null);
      console.log('WebSocket disconnected');
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };
  };

  const disconnect = () => {
    if (websocket) {
      websocket.close();
    }
  };

  const parseDynamoDBItem = (item) => {
    const parsed = {};
    for (const [key, value] of Object.entries(item)) {
      if (value.S) parsed[key] = value.S;
      else if (value.N) parsed[key] = parseFloat(value.N);
      else if (value.BOOL) parsed[key] = value.BOOL;
      else if (value.SS) parsed[key] = value.SS;
      else if (value.NS) parsed[key] = value.NS.map(n => parseFloat(n));
      else if (value.L) parsed[key] = value.L;
      else if (value.M) parsed[key] = parseDynamoDBItem(value.M);
    }
    return parsed;
  };

  const handleMessage = (data) => {
    setMessageCount(prev => prev + 1);
    const now = performance.now();
    setMessageTimestamps(prev => {
      const updated = [...prev, now];
      const tenSecondsAgo = now - 10000;
      return updated.filter(t => t > tenSecondsAgo);
    });

    // Handle raw DynamoDB format or processed data
    if (data.sensor_id) {
      const parsedData = data.sensor_id.S ? parseDynamoDBItem(data) : data;
      console.log('Parsed sensor data:', parsedData);
      handleSensorReading(parsedData);
    } else {
      switch (data.type) {
        case 'real_time_reading':
          handleRealTimeReading(data);
          break;
        case 'latest_readings':
          handleLatestReadings(data);
          break;
        case 'all_latest_readings':
          handleAllLatestReadings(data);
          break;
        default:
          console.log('Unknown message:', data);
      }
    }
  };

  const handleSensorReading = (data) => {
    setSensorData(prev => {
      const newData = new Map(prev);
      newData.set(data.sensor_id, {
        ...data,
        lastUpdated: Date.now()
      });
      return newData;
    });
  };

  const handleRealTimeReading = (data) => {
    const latencyUs = data.cache_to_notification_latency_us || 0;
    setLatencySum(prev => prev + latencyUs);
    
    setSensorData(prev => {
      const newData = new Map(prev);
      newData.set(data.sensor_id, {
        ...data,
        lastUpdated: Date.now()
      });
      return newData;
    });
  };

  const handleLatestReadings = (data) => {
    if (data.readings && data.readings.length > 0) {
      const latest = data.readings[0];
      setSensorData(prev => {
        const newData = new Map(prev);
        newData.set(data.sensor_id, {
          ...latest,
          lastUpdated: Date.now()
        });
        return newData;
      });
    }
  };

  const handleAllLatestReadings = (data) => {
    setSensorData(prev => {
      const newData = new Map(prev);
      for (const [sensorId, readings] of Object.entries(data.sensors)) {
        if (readings && readings.length > 0) {
          const latest = readings[0];
          newData.set(sensorId, {
            ...latest,
            lastUpdated: Date.now()
          });
        }
      }
      return newData;
    });
  };

  const getAllLatest = () => {
    if (websocket && isConnected) {
      websocket.send(JSON.stringify({ action: 'get_latest' }));
    }
  };

  const subscribeToSelected = () => {
    if (!selectedSensor) {
      alert('Please select a sensor');
      return;
    }
    subscribeToSensor(selectedSensor);
  };

  const subscribeToSensor = (sensorId) => {
    if (websocket && isConnected) {
      websocket.send(JSON.stringify({
        action: 'subscribe',
        sensor_id: sensorId
      }));
      setSubscribedSensors(prev => new Set([...prev, sensorId]));
    }
  };

  const toggleSensorSubscription = (sensorId) => {
    if (subscribedSensors.has(sensorId)) {
      unsubscribeFromSensor(sensorId);
    } else {
      subscribeToSensor(sensorId);
    }
  };

  const unsubscribeFromSensor = (sensorId) => {
    if (websocket && isConnected) {
      websocket.send(JSON.stringify({
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

  const getMetrics = () => {
    const totalSensors = sensorData.size;
    const values = Array.from(sensorData.values());
    
    const temperatures = values.map(d => d.temperature).filter(t => t != null);
    const avgTemp = temperatures.length > 0 ? temperatures.reduce((a, b) => a + b, 0) / temperatures.length : 0;
    
    const speeds = values.map(d => d.speed_kms).filter(s => s != null);
    const avgSpeed = speeds.length > 0 ? speeds.reduce((a, b) => a + b, 0) / speeds.length : 0;
    
    const connectionSpeeds = values.map(d => d.connection_speed_mbps).filter(c => c != null);
    const avgConnectionSpeed = connectionSpeeds.length > 0 ? connectionSpeeds.reduce((a, b) => a + b, 0) / connectionSpeeds.length : 0;
    
    const avgLatency = messageCount > 0 ? Math.round(latencySum / messageCount) : 0;
    const messagesPerSecond = (messageTimestamps.length / 10).toFixed(1);
    
    return { totalSensors, avgTemp, avgSpeed, avgConnectionSpeed, avgLatency, messagesPerSecond };
  };

  const metrics = getMetrics();
  const availableSensors = Array.from(sensorData.keys());

  const bgGradient = useColorModeValue('linear(135deg, blue.400, purple.500)', 'linear(135deg, blue.600, purple.700)');
  const cardBg = useColorModeValue('whiteAlpha.900', 'gray.800');

  return (
    <ChakraProvider>
      <Box minH="100vh" bgGradient={bgGradient}>
        <Grid templateColumns="300px 1fr" h="100vh">
          <GridItem bg={cardBg} p={5} backdropFilter="blur(10px)">
            <VStack spacing={4} align="stretch">
              <Text fontSize="xl" fontWeight="bold">🚀 Sensor Control</Text>
              
              <Badge 
                colorScheme={isConnected ? 'green' : 'red'} 
                p={3} 
                borderRadius="md" 
                textAlign="center"
              >
                {isConnected ? '✅ Connected' : '❌ Disconnected'}
              </Badge>

              <VStack spacing={2}>
                <Input 
                  placeholder="WebSocket URL" 
                  value={websocketUrl}
                  onChange={(e) => setWebsocketUrl(e.target.value)}
                />
                <Button onClick={toggleConnection} colorScheme="blue" w="full">
                  {isConnected ? 'Disconnect' : 'Connect'}
                </Button>
                <Button onClick={getAllLatest} isDisabled={!isConnected} w="full">
                  Get All Latest
                </Button>
                
                <Select 
                  value={selectedSensor} 
                  onChange={(e) => setSelectedSensor(e.target.value)}
                >
                  <option value="">Select Sensor</option>
                  {availableSensors.map(sensor => (
                    <option key={sensor} value={sensor}>{sensor}</option>
                  ))}
                </Select>
                <Button onClick={subscribeToSelected} isDisabled={!isConnected} w="full">
                  Subscribe
                </Button>
              </VStack>

              <Box maxH="300px" overflowY="auto">
                {Array.from(sensorData.entries()).map(([sensorId, data]) => (
                  <Card 
                    key={sensorId}
                    mb={2} 
                    cursor="pointer"
                    onClick={() => toggleSensorSubscription(sensorId)}
                    bg={subscribedSensors.has(sensorId) ? 'green.50' : 'gray.50'}
                    borderLeft={subscribedSensors.has(sensorId) ? '4px solid' : 'none'}
                    borderColor="green.400"
                  >
                    <CardBody p={3}>
                      <Text fontWeight="bold">{sensorId}</Text>
                      <Text fontSize="sm">Temp: {data.temperature?.toFixed(1) || 'N/A'}°C</Text>
                      <Text fontSize="sm">Speed: {data.speed_kms?.toFixed(1) || 'N/A'} km/h</Text>
                      <Text fontSize="sm">Connection: {data.connection_speed_mbps?.toFixed(1) || 'N/A'} Mbps</Text>
                      <Text fontSize="sm">Location: {data.latitude?.toFixed(4) || 'N/A'}, {data.longitude?.toFixed(4) || 'N/A'}</Text>
                      <Text fontSize="xs">Reading: {data.reading_timestamp ? new Date(parseInt(data.reading_timestamp)).toLocaleString() : 'N/A'}</Text>
                      <Text fontSize="xs">Updated: {new Date(data.lastUpdated).toLocaleTimeString()}</Text>
                      {subscribedSensors.has(sensorId) && (
                        <Badge colorScheme="green" size="sm">✓ Subscribed</Badge>
                      )}
                    </CardBody>
                  </Card>
                ))}
                {sensorData.size === 0 && (
                  <Text textAlign="center" color="gray.500" p={5}>
                    No sensors detected
                  </Text>
                )}
              </Box>
            </VStack>
          </GridItem>

          <GridItem p={5} overflowY="auto">
            <VStack spacing={5} align="stretch">
              <Grid templateColumns="repeat(4, 1fr)" gap={4}>
                <Card bg={cardBg}>
                  <CardBody>
                    <Stat>
                      <StatLabel>Active Sensors</StatLabel>
                      <StatNumber>{metrics.totalSensors}</StatNumber>
                    </Stat>
                  </CardBody>
                </Card>
                <Card bg={cardBg}>
                  <CardBody>
                    <Stat>
                      <StatLabel>Avg Temperature</StatLabel>
                      <StatNumber>{metrics.avgTemp.toFixed(1)}°C</StatNumber>
                    </Stat>
                  </CardBody>
                </Card>
                <Card bg={cardBg}>
                  <CardBody>
                    <Stat>
                      <StatLabel>Avg Latency</StatLabel>
                      <StatNumber>{metrics.avgLatency}μs</StatNumber>
                    </Stat>
                  </CardBody>
                </Card>
                <Card bg={cardBg}>
                  <CardBody>
                    <Stat>
                      <StatLabel>Messages/Second</StatLabel>
                      <StatNumber>{metrics.messagesPerSecond}</StatNumber>
                    </Stat>
                  </CardBody>
                </Card>
              </Grid>

              <Card bg={cardBg}>
                <CardBody>
                  <Text fontSize="lg" fontWeight="bold" mb={3}>📈 Real-Time Data</Text>
                  <Text>{isConnected ? 'Waiting for data...' : 'Connect to see real-time data'}</Text>
                </CardBody>
              </Card>

              <HStack spacing={5}>
                <Card bg={cardBg} flex={1}>
                  <CardBody>
                    <Text fontSize="lg" fontWeight="bold" mb={3}>⚡ Latency</Text>
                    <Text>No data available</Text>
                  </CardBody>
                </Card>
                
                <Card bg={cardBg} flex={1}>
                  <CardBody>
                    <Text fontSize="lg" fontWeight="bold" mb={3}>🗺️ Sensor Map</Text>
                    <Text>No data available</Text>
                  </CardBody>
                </Card>
              </HStack>
            </VStack>
          </GridItem>
        </Grid>
      </Box>
    </ChakraProvider>
  );
}

export default App;