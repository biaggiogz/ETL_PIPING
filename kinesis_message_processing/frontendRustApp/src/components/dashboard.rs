use std::collections::HashMap;
use yew::prelude::*;
use gloo::timers::callback::Interval;
use web_sys::window;

use crate::types::{RealTimeReading, LatencyMetrics};
use crate::websocket::WebSocketService;
use super::{SensorCard, LatencyChart, SpeedRacing, TemperatureRadial};

#[derive(Properties, PartialEq)]
pub struct DashboardProps {}

pub struct Dashboard {
    ws_service: Option<WebSocketService>,
    connected: bool,
    sensor_data: HashMap<String, RealTimeReading>,
    latency_history: Vec<LatencyMetrics>,
    ws_url: String,
    selected_sensor: String,
    _interval: Option<Interval>,
    pending_updates: Vec<RealTimeReading>,
    last_render: f64,
    render_throttle_ms: f64,
}

pub enum DashboardMsg {
    Connect,
    Disconnect,
    Subscribe,
    WebSocketMessage(RealTimeReading),
    WebSocketError(String),
    WebSocketOpen,
    WebSocketClose,
    UpdateSensorId(String),
    UpdateWsUrl(String),
    ProcessPendingUpdates,
}

impl Component for Dashboard {
    type Message = DashboardMsg;
    type Properties = DashboardProps;

    fn create(ctx: &Context<Self>) -> Self {
        // Set up render throttling interval
        let link = ctx.link().clone();
        let interval = Interval::new(16, move || { // ~60fps
            link.send_message(DashboardMsg::ProcessPendingUpdates);
        });
        
        Self {
            ws_service: None,
            connected: false,
            sensor_data: HashMap::new(),
            latency_history: Vec::new(),
            ws_url: "wss://icjs840cnh.execute-api.us-east-1.amazonaws.com/prod".to_string(),
            selected_sensor: "device1".to_string(),
            _interval: Some(interval),
            pending_updates: Vec::new(),
            last_render: 0.0,
            render_throttle_ms: 16.0, // 60fps
        }
    }

    fn update(&mut self, ctx: &Context<Self>, msg: Self::Message) -> bool {
        match msg {
            DashboardMsg::Connect => {
                let onmessage = ctx.link().callback(DashboardMsg::WebSocketMessage);
                let onerror = ctx.link().callback(DashboardMsg::WebSocketError);
                let onopen = ctx.link().callback(|_| DashboardMsg::WebSocketOpen);
                let onclose = ctx.link().callback(|_| DashboardMsg::WebSocketClose);

                let mut service = WebSocketService::new(onmessage, onerror, onopen, onclose);
                if service.connect(&self.ws_url).is_ok() {
                    self.ws_service = Some(service);
                }
                true
            }
            DashboardMsg::Disconnect => {
                if let Some(mut service) = self.ws_service.take() {
                    service.disconnect();
                }
                self.connected = false;
                true
            }
            DashboardMsg::Subscribe => {
                if let Some(service) = &self.ws_service {
                    // Subscribe to common device IDs from your test
                    let device_ids = ["device1", "device2", "device3", "device4", "device5", 
                                     "device6", "device7", "device8", "device9", "device10"];
                    for device_id in &device_ids {
                        let _ = service.subscribe(device_id);
                    }
                    // Also subscribe to the manually entered sensor
                    let _ = service.subscribe(&self.selected_sensor);
                }
                false
            }
            DashboardMsg::WebSocketMessage(reading) => {
                // Auto-subscribe to new devices
                if !self.sensor_data.contains_key(&reading.sensor_id) {
                    if let Some(service) = &self.ws_service {
                        let _ = service.subscribe(&reading.sensor_id);
                    }
                }
                
                // Add to pending updates instead of immediate processing
                self.pending_updates.push(reading);
                
                // Limit pending updates to prevent memory issues
                if self.pending_updates.len() > 1000 {
                    self.pending_updates.drain(0..500); // Keep only latest 500
                }
                
                false // Don't trigger re-render yet
            }
            DashboardMsg::ProcessPendingUpdates => {
                if self.pending_updates.is_empty() {
                    return false;
                }
                
                let now = window().unwrap().performance().unwrap().now();
                if now - self.last_render < self.render_throttle_ms {
                    return false; // Skip this update cycle
                }
                
                // Process all pending updates in batch
                let mut should_render = false;
                for reading in self.pending_updates.drain(..) {
                    // Store latency metrics (only keep recent ones)
                    let latency = LatencyMetrics {
                        kinesis_to_lambda_us: reading.kinesis_to_lambda_us,
                        lambda_processing_us: reading.lambda_processing_us,
                        cache_to_websocket_us: reading.cache_to_websocket_us,
                        websocket_to_frontend_us: reading.websocket_to_frontend_us,
                        total_pipeline_us: reading.kinesis_to_lambda_us + reading.lambda_processing_us + 
                                          reading.cache_to_websocket_us + reading.websocket_to_frontend_us,
                        timestamp: now,
                    };
                    
                    self.latency_history.push(latency);
                    self.sensor_data.insert(reading.sensor_id.clone(), reading);
                    should_render = true;
                }
                
                // Cleanup old latency history more aggressively
                if self.latency_history.len() > 50 {
                    let keep_count = 30;
                    self.latency_history.drain(0..self.latency_history.len() - keep_count);
                }
                
                if should_render {
                    self.last_render = now;
                }
                
                should_render
            }
            DashboardMsg::WebSocketError(error) => {
                web_sys::console::error_1(&error.into());
                true
            }
            DashboardMsg::WebSocketOpen => {
                self.connected = true;
                true
            }
            DashboardMsg::WebSocketClose => {
                self.connected = false;
                true
            }
            DashboardMsg::UpdateSensorId(sensor_id) => {
                self.selected_sensor = sensor_id;
                true
            }
            DashboardMsg::UpdateWsUrl(url) => {
                self.ws_url = url;
                true
            }
        }
    }

    fn view(&self, ctx: &Context<Self>) -> Html {
        let connect_onclick = ctx.link().callback(|_| DashboardMsg::Connect);
        let disconnect_onclick = ctx.link().callback(|_| DashboardMsg::Disconnect);
        let subscribe_onclick = ctx.link().callback(|_| DashboardMsg::Subscribe);
        
        let sensor_input = ctx.link().callback(|e: InputEvent| {
            let input: web_sys::HtmlInputElement = e.target_unchecked_into();
            DashboardMsg::UpdateSensorId(input.value())
        });

        let ws_url_input = ctx.link().callback(|e: InputEvent| {
            let input: web_sys::HtmlInputElement = e.target_unchecked_into();
            DashboardMsg::UpdateWsUrl(input.value())
        });

        html! {
            <div class="dashboard">
                <header class="dashboard-header">
                    <h1>{"Sensor Dashboard - Real-time Latency Tracking"}</h1>
                    <div class="connection-status">
                        <span class={if self.connected { "status connected" } else { "status disconnected" }}>
                            {if self.connected { "🟢 Connected" } else { "🔴 Disconnected" }}
                        </span>
                    </div>
                </header>

                <div class="controls">
                    <div class="control-group">
                        <label>{"WebSocket URL:"}</label>
                        <input 
                            type="text" 
                            value={self.ws_url.clone()} 
                            oninput={ws_url_input}
                            placeholder="wss://your-endpoint.amazonaws.com/prod"
                        />
                    </div>
                    
                    <div class="control-group">
                        <label>{"Sensor ID:"}</label>
                        <input 
                            type="text" 
                            value={self.selected_sensor.clone()} 
                            oninput={sensor_input}
                            placeholder="device1"
                        />
                    </div>

                    <div class="button-group">
                        <button onclick={connect_onclick} disabled={self.connected}>
                            {"Connect"}
                        </button>
                        <button onclick={disconnect_onclick} disabled={!self.connected}>
                            {"Disconnect"}
                        </button>
                        <button onclick={subscribe_onclick} disabled={!self.connected}>
                            {"Subscribe All Devices"}
                        </button>
                    </div>
                    <p><small>{"Note: New devices are automatically subscribed when they send data"}</small></p>
                </div>

                <div class="content">
                    <div class="sensors-grid">
                        {for self.sensor_data.values().map(|reading| {
                            html! {
                                <SensorCard reading={reading.clone()} />
                            }
                        })}
                    </div>

                    <div class="latency-section">
                        <h2>{"Pipeline Latency Metrics"}</h2>
                        <LatencyChart history={self.latency_history.clone()} />
                    </div>

                    <SpeedRacing readings={self.sensor_data.clone()} />

                    <TemperatureRadial readings={self.sensor_data.clone()} />
                </div>
            </div>
        }
    }
}