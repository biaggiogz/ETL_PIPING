import { useState, useEffect, useMemo, memo } from 'react';
import {
  Box, Grid, VStack, HStack, Text, Input, Button, Select,
  Badge, Card, CardBody, Stat, StatLabel, StatNumber
} from '@chakra-ui/react';
import { useWebSocket } from '../hooks/useWebSocket';

const Dashboard = memo(() => {
  const [wsUrl, setWsUrl] = useState('wss://your-api-id.execute-api.region.amazonaws.com/prod');
  const [connectedUrl, setConnectedUrl] = useState('');
  const [selectedSensor, setSelectedSensor] = useState('');
  const { isConnected, sensorData, subscribedSensors, messageCount, sendMessage, subscribeToSensor } = useWebSocket(connectedUrl);

  useEffect(() => {
    const interval = setInterval(() => {
      if (isConnected) {
        sendMessage({ action: 'get_latest' });
      }
    }, 100); // Back to 100ms as requested
    return () => clearInterval(interval);
  }, [isConnected, sendMessage]);

  const handleConnect = () => {
    if (wsUrl) {
      console.log('Connecting to:', wsUrl);
      setConnectedUrl(wsUrl);
    }
  };

  const handleSubscribe = () => {
    if (selectedSensor) {
      subscribeToSensor(selectedSensor);
    }
  };

  const { temperatures, avgTemp, selectedSensorReading, sensorOptions } = useMemo(() => {
    const temps = Array.from(sensorData.values()).map(d => d.temperature).filter(t => t != null);
    const avg = temps.length > 0 ? temps.reduce((a, b) => a + b, 0) / temps.length : 0;
    const selected = sensorData.get(selectedSensor);
    const options = Array.from(sensorData.keys());
    return {
      temperatures: temps,
      avgTemp: avg,
      selectedSensorReading: selected,
      sensorOptions: options
    };
  }, [sensorData, selectedSensor]);

  return (
    <Grid templateColumns="300px 1fr" h="100vh" gap={4} p={4}>
      <VStack spacing={4} align="stretch">
        <Card>
          <CardBody>
            <VStack spacing={3}>
              <Badge colorScheme={isConnected ? 'green' : 'red'}>
                {isConnected ? '✅ Connected' : '❌ Disconnected'}
              </Badge>
              <Text fontSize="xs" color="gray.500">
                Sensors: {sensorData.size} | Messages: {messageCount}
              </Text>
              <Input
                placeholder="WebSocket URL"
                value={wsUrl}
                onChange={(e) => setWsUrl(e.target.value)}
              />
              <Button onClick={handleConnect} colorScheme="blue" w="full">
                Connect
              </Button>
            </VStack>
          </CardBody>
        </Card>

        <Card>
          <CardBody>
            <VStack spacing={3}>
              <Select
                placeholder="Select Sensor"
                value={selectedSensor}
                onChange={(e) => setSelectedSensor(e.target.value)}
              >
                {sensorOptions.map(sensorId => (
                  <option key={sensorId} value={sensorId}>
                    {sensorId}
                  </option>
                ))}
              </Select>
              <Button onClick={handleSubscribe} colorScheme="green" w="full" disabled={!isConnected}>
                Subscribe
              </Button>
            </VStack>
          </CardBody>
        </Card>

        <Card>
          <CardBody>
            <Text fontSize="md" fontWeight="bold" mb={3}>Sensor List</Text>
            {sensorData.size === 0 ? (
              <Text color="gray.500" textAlign="center" py={4}>No sensors detected</Text>
            ) : (
              <VStack spacing={2} align="stretch" maxH="200px" overflowY="auto">
                {Array.from(sensorData.entries()).map(([sensorId, data]) => (
                  <Box
                    key={sensorId}
                    p={3}
                    bg={subscribedSensors.has(sensorId) ? 'green.50' : 'gray.50'}
                    borderRadius="md"
                    borderLeft={subscribedSensors.has(sensorId) ? '4px solid' : 'none'}
                    borderLeftColor="green.400"
                    cursor="pointer"
                    onClick={() => subscribeToSensor(sensorId)}
                    _hover={{ bg: subscribedSensors.has(sensorId) ? 'green.100' : 'gray.100' }}
                  >
                    <Text fontWeight="bold">{sensorId}</Text>
                    <Text fontSize="sm">Temp: {data.temperature?.toFixed(1) || 'N/A'}°C</Text>
                    <Text fontSize="xs" color="gray.600">
                      Updated: {new Date(data.lastUpdated).toLocaleTimeString()}
                    </Text>
                    {subscribedSensors.has(sensorId) && (
                      <Badge colorScheme="green" size="sm">✓ Subscribed</Badge>
                    )}
                  </Box>
                ))}
              </VStack>
            )}
          </CardBody>
        </Card>
      </VStack>

      <VStack spacing={4} align="stretch">
        <Grid templateColumns="repeat(3, 1fr)" gap={4}>
          <Card>
            <CardBody>
              <Stat>
                <StatLabel>Active Sensors</StatLabel>
                <StatNumber>{sensorData.size}</StatNumber>
              </Stat>
            </CardBody>
          </Card>
          <Card>
            <CardBody>
              <Stat>
                <StatLabel>Avg Temperature</StatLabel>
                <StatNumber>{avgTemp.toFixed(1)}°C</StatNumber>
              </Stat>
            </CardBody>
          </Card>
          <Card>
            <CardBody>
              <Stat>
                <StatLabel>Messages</StatLabel>
                <StatNumber>{messageCount}</StatNumber>
              </Stat>
            </CardBody>
          </Card>
        </Grid>

        <Card>
          <CardBody>
            <Text fontSize="lg" fontWeight="bold" mb={4}>
              📈 Sensor Data
            </Text>
            {selectedSensorReading ? (
              <VStack align="start" spacing={2}>
                <Text><strong>Sensor:</strong> {selectedSensor}</Text>
                <Text><strong>Temperature:</strong> {selectedSensorReading.temperature?.toFixed(1)}°C</Text>
                <Text><strong>Position:</strong> {selectedSensorReading.position?.latitude?.toFixed(2)}, {selectedSensorReading.position?.longitude?.toFixed(2)}</Text>
                <Text><strong>Speed:</strong> {selectedSensorReading.speed_kms?.toFixed(1)} km/h</Text>
                <Text><strong>Connection:</strong> {selectedSensorReading.connection_speed_mbps?.toFixed(1)} Mbps</Text>
                <Text><strong>Last Updated:</strong> {new Date(selectedSensorReading.lastUpdated).toLocaleTimeString()}</Text>
                <Badge colorScheme={subscribedSensors.has(selectedSensor) ? 'green' : 'gray'}>
                  {subscribedSensors.has(selectedSensor) ? '✓ Subscribed' : 'Not Subscribed'}
                </Badge>
              </VStack>
            ) : (
              <Text color="gray.500">Select a sensor to view data</Text>
            )}
          </CardBody>
        </Card>
      </VStack>
    </Grid>
  );
});

export { Dashboard };