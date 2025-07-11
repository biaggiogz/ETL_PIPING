# SolidJS IoT Dashboard with DuckDB WASM

Production-grade real-time IoT dashboard built with SolidJS + WASM + DuckDB for high-performance sensor data visualization.

## Features

- **SolidJS Reactivity**: Fine-grained reactive updates, minimal re-renders
- **DuckDB WASM**: In-browser SQL analytics, columnar storage
- **Real-time WebSocket**: Live sensor data streaming
- **Performance Optimized**: Message batching, render throttling
- **Advanced Visualizations**: ECharts integration for interactive charts

## Quick Start

```bash
# Install dependencies
npm install

# Start development server
npm run dev

# Build for production
npm run build
```

## Architecture

- **SolidJS**: Reactive UI framework with minimal overhead
- **DuckDB WASM**: High-performance in-browser analytics database
- **ECharts**: Interactive data visualization
- **WebSocket**: Real-time data streaming
- **Vite**: Fast build tool with WASM support

## Performance Benefits

- **Fine-grained Reactivity**: Only updates changed components
- **WASM Performance**: Near-native speed for data processing
- **Columnar Storage**: Efficient data compression and querying
- **Message Batching**: Reduces processing overhead
- **Automatic Cleanup**: Prevents memory leaks

## Data Pipeline

```
WebSocket → Message Batching → DuckDB WASM → SolidJS Reactivity → UI Updates
```

## Usage

1. Enter WebSocket URL
2. Connect to real-time stream
3. Subscribe to sensor devices
4. View real-time metrics and latency tracking

The dashboard automatically stores data in DuckDB for fast querying and analytics.