use yew::prelude::*;
use crate::types::RealTimeReading;

#[derive(Properties, PartialEq)]
pub struct SensorCardProps {
    pub reading: RealTimeReading,
}

#[function_component(SensorCard)]
pub fn sensor_card(props: &SensorCardProps) -> Html {
    let reading = &props.reading;
    
    let total_latency = reading.kinesis_to_lambda_us + 
                       reading.lambda_processing_us + 
                       reading.cache_to_websocket_us + 
                       reading.websocket_to_frontend_us;

    html! {
        <div class="sensor-card">
            <div class="sensor-header">
                <h3>{&reading.sensor_id}</h3>
                <span class="timestamp">
                    {format!("{}ms", reading.reading_timestamp_ms)}
                </span>
            </div>
            
            <div class="sensor-data">
                <div class="data-row">
                    <span class="label">{"Temperature:"}</span>
                    <span class="value">{format!("{:.1}°C", reading.temperature)}</span>
                </div>
                
                <div class="data-row">
                    <span class="label">{"Position:"}</span>
                    <span class="value">
                        {format!("{:.4}, {:.4}", reading.position.latitude, reading.position.longitude)}
                    </span>
                </div>
                
                <div class="data-row">
                    <span class="label">{"Speed:"}</span>
                    <span class="value">{format!("{:.1} km/h", reading.speed_kms)}</span>
                </div>
                
                <div class="data-row">
                    <span class="label">{"Connection:"}</span>
                    <span class="value">{format!("{:.1} Mbps", reading.connection_speed_mbps)}</span>
                </div>
            </div>

            <div class="latency-metrics">
                <h4>{"Pipeline Latency (μs)"}</h4>
                <div class="latency-breakdown">
                    <div class="latency-item">
                        <span class="stage">{"Kinesis→Lambda:"}</span>
                        <span class="time">{reading.kinesis_to_lambda_us}</span>
                    </div>
                    <div class="latency-item">
                        <span class="stage">{"Lambda Processing:"}</span>
                        <span class="time">{reading.lambda_processing_us}</span>
                    </div>
                    <div class="latency-item">
                        <span class="stage">{"Cache→WebSocket:"}</span>
                        <span class="time">{reading.cache_to_websocket_us}</span>
                    </div>
                    <div class="latency-item">
                        <span class="stage">{"WebSocket→Frontend:"}</span>
                        <span class="time">{reading.websocket_to_frontend_us}</span>
                    </div>
                    <div class="latency-item total">
                        <span class="stage">{"Total Pipeline:"}</span>
                        <span class="time">{total_latency}</span>
                    </div>
                </div>
            </div>
        </div>
    }
}