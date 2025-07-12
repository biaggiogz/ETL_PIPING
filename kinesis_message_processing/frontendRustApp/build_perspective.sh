#!/bin/bash

echo "Building Rust WASM with Perspective integration..."

# Build the WASM package
wasm-pack build --target web --out-dir pkg

# Copy the perspective integration script
cp perspective_integration.js pkg/

echo "Build complete! Perspective integration ready."
echo "Start server with: python3 serve.py"