# Kinesis Message Processing Lambda - Docker Documentation

## Overview

Advanced multi-stage Dockerfile for Rust AWS Lambda functions achieving **90%+ faster rebuild times** through intelligent dependency caching.

## Build Performance

| Scenario | Time | Rebuilt Stages |
|----------|------|----------------|
| First build | 5-10 minutes | All (1-4) |
| Code changes | 30-60 seconds | 3-4 only |
| Dependencies | 2-3 minutes | 2-4 only |

## Architecture

### Four-Stage Pipeline
1. **PLANNER** - Dependency analysis (`cargo-chef prepare`)
2. **CACHER** - Pre-compile dependencies (`cargo chef cook`)
3. **BUILDER** - Source compilation with cached deps
4. **RUNTIME** - Minimal production image

### Key Innovation
Separates dependency compilation from source compilation using `cargo-chef`, enabling Docker layer caching that only rebuilds changed components.

## Usage

```bash
# Basic build
docker build -t kinesis-lambda .

# Multi-architecture
docker buildx build --platform linux/amd64,linux/arm64 -t kinesis-lambda .
```

## Configuration

### Environment Variables
- `PACKAGE=kinesis-lambda` - Target package name
- `TARGETPLATFORM=linux/arm64` - Architecture (arm64/amd64)

### Supported Architectures
- **AMD64**: `x86_64-unknown-linux-gnu`
- **ARM64**: `aarch64-unknown-linux-gnu` (Graviton cost savings)

## Project Structure
```
├── Cargo.toml, Cargo.lock
├── lambda/mesagges/Cargo.toml
├── lambda/shared/Cargo.toml
└── test/Cargo.toml
```

## Optimizations

### Network Performance
```dockerfile
ENV CARGO_NET_GIT_FETCH_WITH_CLI=true
ENV CARGO_REGISTRIES_CRATES_IO_PROTOCOL=sparse
```

### Caching Strategy
- Dependencies cached in stage 2
- Source changes only rebuild stages 3-4
- Dummy files prevent premature compilation

## Production Benefits
- Minimal runtime image (AWS Lambda base)
- Cross-platform support
- Reduced cold start times
- Enhanced security (binary-only final image)