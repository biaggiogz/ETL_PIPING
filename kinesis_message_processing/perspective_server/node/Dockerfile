FROM node:18-alpine

WORKDIR /app

COPY package*.json ./
RUN npm ci --only=production

COPY . .

# Set environment variable for WebSocket URL
ARG ENVIRONMENT=production
ENV ENVIRONMENT=${ENVIRONMENT}

# Replace WebSocket URL based on environment
RUN if [ "$ENVIRONMENT" = "local" ]; then \
        sed -i 's|`ws://\${window.location.hostname}:8081/websocket`|"ws://localhost:8081/websocket"|g' index.html; \
    fi

EXPOSE 8081 5173

CMD ["npm", "run", "prsp-server"]