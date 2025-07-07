#!/bin/bash

# Pipeline Latency Analysis Script
# Analyzes CloudWatch logs to extract latency metrics

set -e

FUNCTION_NAME=${1:-"serverless-rust-KinesisProcessor"}
WEBSOCKET_FUNCTION_NAME=${2:-"websocket-realtime-sensor-data"}
REGION=${3:-"us-east-1"}
HOURS_BACK=${4:-1}

echo "🔍 Analyzing pipeline latency for the last $HOURS_BACK hours..."
echo "Lambda Function: $FUNCTION_NAME"
echo "WebSocket Function: $WEBSOCKET_FUNCTION_NAME"
echo "Region: $REGION"
echo ""

# Calculate time range
END_TIME=$(date +%s)000
START_TIME=$((END_TIME - HOURS_BACK * 3600 * 1000))

echo "📊 Extracting latency metrics from CloudWatch logs..."

# Extract pipeline latency metrics
aws logs filter-log-events \
    --log-group-name "/aws/lambda/$FUNCTION_NAME" \
    --start-time $START_TIME \
    --end-time $END_TIME \
    --filter-pattern "PIPELINE LATENCY" \
    --region $REGION \
    --query 'events[*].message' \
    --output text | \
    grep -E "PIPELINE LATENCY" | \
    sed -E 's/.*Kinesis→Lambda: ([0-9]+)μs.*Lambda Processing: ([0-9]+)μs.*Cache→WebSocket: ([0-9]+)μs.*WebSocket→Frontend: ([0-9]+)μs.*TOTAL: ([0-9]+)μs.*/\1,\2,\3,\4,\5/' > /tmp/pipeline_latencies.csv

if [ -s /tmp/pipeline_latencies.csv ]; then
    echo "📈 Pipeline Latency Analysis:"
    echo "Component,Min(μs),Max(μs),Avg(μs),Count"
    
    # Analyze each component
    for i in {1..5}; do
        case $i in
            1) component="Kinesis→Lambda" ;;
            2) component="Lambda Processing" ;;
            3) component="Cache→WebSocket" ;;
            4) component="WebSocket→Frontend" ;;
            5) component="Total Pipeline" ;;
        esac
        
        stats=$(cut -d',' -f$i /tmp/pipeline_latencies.csv | \
                awk '{
                    sum+=$1; 
                    if(NR==1){min=max=$1} 
                    if($1<min){min=$1} 
                    if($1>max){max=$1}
                } 
                END {
                    if(NR>0) printf "%d,%d,%.0f,%d", min, max, sum/NR, NR
                    else printf "0,0,0,0"
                }')
        
        echo "$component,$stats"
    done
    
    echo ""
    echo "🎯 Performance Summary:"
    total_samples=$(wc -l < /tmp/pipeline_latencies.csv)
    avg_total=$(cut -d',' -f5 /tmp/pipeline_latencies.csv | awk '{sum+=$1} END {if(NR>0) printf "%.3f", sum/NR/1000000; else printf "0"}')
    max_total=$(cut -d',' -f5 /tmp/pipeline_latencies.csv | awk 'BEGIN{max=0} {if($1>max) max=$1} END {printf "%.3f", max/1000000}')
    min_total=$(cut -d',' -f5 /tmp/pipeline_latencies.csv | awk 'BEGIN{min=999999999} {if($1<min) min=$1} END {printf "%.3f", min/1000000}')
    
    echo "Total Samples: $total_samples"
    echo "Average End-to-End Latency: ${avg_total}s"
    echo "Minimum End-to-End Latency: ${min_total}s"
    echo "Maximum End-to-End Latency: ${max_total}s"
    
    # Calculate percentiles
    echo ""
    echo "📊 Latency Percentiles (seconds):"
    cut -d',' -f5 /tmp/pipeline_latencies.csv | \
        sort -n | \
        awk '{
            values[NR] = $1/1000000
        } 
        END {
            if(NR > 0) {
                printf "P50: %.6f\n", values[int(NR*0.5)]
                printf "P90: %.6f\n", values[int(NR*0.9)]
                printf "P95: %.6f\n", values[int(NR*0.95)]
                printf "P99: %.6f\n", values[int(NR*0.99)]
            }
        }'
else
    echo "⚠️ No pipeline latency data found in the specified time range."
fi

echo ""
echo "🔍 Extracting cache operation metrics..."

# Extract cache operation latencies
aws logs filter-log-events \
    --log-group-name "/aws/lambda/$FUNCTION_NAME" \
    --start-time $START_TIME \
    --end-time $END_TIME \
    --filter-pattern "cache_operation" \
    --region $REGION \
    --query 'events[*].message' \
    --output text | \
    grep -E "cache_latency_ns" | \
    sed -E 's/.*cache_latency_ns=([0-9]+).*/\1/' > /tmp/cache_latencies.txt

if [ -s /tmp/cache_latencies.txt ]; then
    echo "💾 Cache Operation Analysis:"
    cache_stats=$(cat /tmp/cache_latencies.txt | \
                  awk '{
                      sum+=$1/1000; 
                      if(NR==1){min=max=$1/1000} 
                      if($1/1000<min){min=$1/1000} 
                      if($1/1000>max){max=$1/1000}
                  } 
                  END {
                      if(NR>0) printf "Min: %.0fμs, Max: %.0fμs, Avg: %.0fμs, Count: %d", min, max, sum/NR, NR
                      else printf "No data"
                  }')
    echo "$cache_stats"
else
    echo "⚠️ No cache operation data found."
fi

echo ""
echo "🌐 WebSocket notification analysis..."

# Extract WebSocket notification metrics
aws logs filter-log-events \
    --log-group-name "/aws/lambda/$WEBSOCKET_FUNCTION_NAME" \
    --start-time $START_TIME \
    --end-time $END_TIME \
    --filter-pattern "websocket_notification" \
    --region $REGION \
    --query 'events[*].message' \
    --output text | \
    grep -E "latency_us" | \
    sed -E 's/.*latency_us=([0-9]+).*/\1/' > /tmp/websocket_latencies.txt

if [ -s /tmp/websocket_latencies.txt ]; then
    echo "📡 WebSocket Notification Analysis:"
    ws_stats=$(cat /tmp/websocket_latencies.txt | \
               awk '{
                   sum+=$1; 
                   if(NR==1){min=max=$1} 
                   if($1<min){min=$1} 
                   if($1>max){max=$1}
               } 
               END {
                   if(NR>0) printf "Min: %.0fμs, Max: %.0fμs, Avg: %.0fμs, Count: %d", min, max, sum/NR, NR
                   else printf "No data"
               }')
    echo "$ws_stats"
else
    echo "⚠️ No WebSocket notification data found."
fi

echo ""
echo "🧹 Cleaning up temporary files..."
rm -f /tmp/pipeline_latencies.csv /tmp/cache_latencies.txt /tmp/websocket_latencies.txt

echo "✅ Analysis complete!"
echo ""
echo "💡 To run this analysis:"
echo "   ./latency-analysis.sh [function-name] [websocket-function-name] [region] [hours-back]"
echo "   Example: ./latency-analysis.sh my-kinesis-processor my-websocket-handler us-west-2 2"