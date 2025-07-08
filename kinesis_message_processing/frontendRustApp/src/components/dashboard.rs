use std::collections::HashMap;
use yew::prelude::*;
use gloo::timers::callback::Interval;

use crate::types::{RealTimeReading, LatencyMetrics};
use crate::websocket::WebSocketService;
use super::{SensorCard, LatencyChart, SpeedRacing};

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
}

impl Component for Dashboard {
    type Message = DashboardMsg;
    type Properties = DashboardProps;

    fn create(_ctx: &Context<Self>) -> Self {
        Self {
            ws_service: None,
            connected: false,
            sensor_data: HashMap::new(),
            latency_history: Vec::new(),
            ws_url: "wss://your-websocket-endpoint.execute-api.region.amazonaws.com/prod".to_string(),
            selected_sensor: "device1".to_string(),
            _interval: None,
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
                    let _ = service.subscribe(&self.selected_sensor);
                }
                false
            }
            DashboardMsg::WebSocketMessage(reading) => {
                // Store latency metrics
                let latency = LatencyMetrics {
                    kinesis_to_lambda_us: reading.kinesis_to_lambda_us,
                    lambda_processing_us: reading.lambda_processing_us,
                    cache_to_websocket_us: reading.cache_to_websocket_us,
                    websocket_to_frontend_us: reading.websocket_to_frontend_us,
                    total_pipeline_us: reading.kinesis_to_lambda_us + reading.lambda_processing_us + 
                                      reading.cache_to_websocket_us + reading.websocket_to_frontend_us,
                    timestamp: js_sys::Date::now(),
                };
                
                self.latency_history.push(latency);
                if self.latency_history.len() > 100 {
                    self.latency_history.remove(0);
                }

                self.sensor_data.insert(reading.sensor_id.clone(), reading);
                true
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
                            {"Subscribe"}
                        </button>
                    </div>
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
                </div>
            </div>
        }
    }
}