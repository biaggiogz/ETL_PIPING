#!/bin/bash

# Install wasm-pack if not already installed
if ! command -v wasm-pack &> /dev/null; then
    echo "Installing wasm-pack..."
    curl https://rustwasm.github.io/wasm-pack/installer/init.sh -sSf | sh
fi

# Build the WebAssembly package with optimizations
echo "Building optimized WebAssembly package..."
export RUSTFLAGS="-C opt-level=3"
wasm-pack build --target web --out-dir pkg --release

# Optimize the wasm binary if wasm-opt is available
if command -v wasm-opt &> /dev/null; then
    echo "Optimizing WASM binary for size and speed..."
    wasm-opt -Oz --enable-simd pkg/sensor_dashboard_bg.wasm -o pkg/sensor_dashboard_bg.wasm
    echo "✅ WASM binary optimized!"
else
    echo "⚠️  wasm-opt not found. Install binaryen for better optimization."
fi

# Create a simple HTTP server script
cat > serve.py << 'EOF'
#!/usr/bin/env python3
import http.server
import socketserver
import os

PORT = 8000

class MyHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Cross-Origin-Embedder-Policy', 'require-corp')
        self.send_header('Cross-Origin-Opener-Policy', 'same-origin')
        super().end_headers()

os.chdir(os.path.dirname(os.path.abspath(__file__)))

with socketserver.TCPServer(("", PORT), MyHTTPRequestHandler) as httpd:
    print(f"Serving at http://localhost:{PORT}")
    print("Open your browser and navigate to the URL above")
    httpd.serve_forever()
EOF

chmod +x serve.py

echo "Build complete!"
echo "To serve the application:"
echo "  ./serve.py"
echo "Then open http://localhost:8000 in your browser"