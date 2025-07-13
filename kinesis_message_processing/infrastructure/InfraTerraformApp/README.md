# On-Demand Perspective Server Infrastructure

Cost-effective architecture for real-time Kinesis data visualization using ECS Fargate and CloudFront.

## Architecture

- **CloudFront + S3**: Frontend control panel
- **API Gateway + Lambda**: ECS task management
- **ECS Fargate**: On-demand Perspective server
- **ALB**: Load balancing for WebSocket connections

## Quick Deploy

```bash
```

## Manual Steps

### 1. Deploy Infrastructure
```bash
cd infrastructure
terraform init
terraform apply
```

### 2. Build & Push Docker Image
```bash
cd perspective_server/node
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <ECR_URL>
docker build -t perspective-server .
docker tag perspective-server:latest <ECR_URL>:latest
docker push <ECR_URL>:latest
```

### 3. Update Frontend URLs
```bash
cd frontend
# Replace placeholders with actual URLs from terraform output
sed -i 's/API_GATEWAY_URL_PLACEHOLDER/<actual_api_url>/g' index.html
sed -i 's/LOAD_BALANCER_URL_PLACEHOLDER/<actual_lb_dns>/g' index.html
```

### 4. Upload Frontend
```bash
aws s3 cp frontend/index.html s3://<bucket_name>/
```

## Usage

1. Visit CloudFront URL
2. Click "Start Analysis Server" → ECS task launches
3. Wait for "RUNNING" status
4. Click "Open Perspective Dashboard" → Real-time data visualization
5. Click "Stop Server" when done → Saves costs

## Cost Optimization

- **ECS Fargate**: Pay only when running (~$0.05/hour)
- **CloudFront**: Static hosting (~$0.01/month)
- **Lambda**: Serverless control plane (~$0.00/month)
- **API Gateway**: Per-request pricing (~$0.00/month)

Total cost: **~$0.05/hour when active, ~$0.01/month when idle**