use yew::prelude::*;
use wasm_bindgen::prelude::*;
use crate::types::RealTimeReading;
use std::collections::HashMap;
use gloo::timers::callback::Timeout;
use web_sys::window;

#[wasm_bindgen]
extern "C" {
    #[wasm_bindgen(js_name = initSensorRadarChart)]
    fn init_sensor_radar_chart(element_id: &str) -> JsValue;
    
    #[wasm_bindgen(js_name = updateSensorRadarChart)]
    fn update_sensor_radar_chart(chart: &JsValue, sensors: &js_sys::Array);
}

#[derive(Properties, PartialEq)]
pub struct TemperatureRadialProps {
    pub readings: HashMap<String, RealTimeReading>,
}

pub struct TemperatureRadial {
    radar_chart: Option<JsValue>,
    last_update: f64,
    update_throttle_ms: f64,
}

pub enum TemperatureRadialMsg {
    InitComponents,
    UpdateData,
}

impl Component for TemperatureRadial {
    type Message = TemperatureRadialMsg;
    type Properties = TemperatureRadialProps;

    fn create(_ctx: &Context<Self>) -> Self {
        Self {
            radar_chart: None,
            last_update: 0.0,
            update_throttle_ms: 100.0, // Update max every 100ms
        }
    }

    fn update(&mut self, ctx: &Context<Self>, msg: Self::Message) -> bool {
        match msg {
            TemperatureRadialMsg::InitComponents => {
                self.radar_chart = Some(init_sensor_radar_chart("sensorRadarChart"));
                
                if !ctx.props().readings.is_empty() {
                    let link = ctx.link().clone();
                    Timeout::new(100, move || {
                        link.send_message(TemperatureRadialMsg::UpdateData);
                    }).forget();
                }
                false
            }
            TemperatureRadialMsg::UpdateData => {
                self.update_charts(ctx);
                false
            }
        }
    }

    fn view(&self, ctx: &Context<Self>) -> Html {
        let init_components = ctx.link().callback(|_| TemperatureRadialMsg::InitComponents);
        
        html! {
            <div class="temperature-radial-section">
                <h2>{"Sensor Multi-Dimensional Analysis"}</h2>
                
                <div class="radar-full-container">
                    <h3>{"Sensor Metrics Radar"}</h3>
                    <div 
                        id="sensorRadarChart"
                        onload={init_components}
                    >
                    </div>
                </div>
            </div>
        }
    }

    fn rendered(&mut self, ctx: &Context<Self>, first_render: bool) {
        if first_render {
            let link = ctx.link().clone();
            Timeout::new(500, move || {
                link.send_message(TemperatureRadialMsg::InitComponents);
            }).forget();
        } else {
            ctx.link().send_message(TemperatureRadialMsg::UpdateData);
        }
    }
}

impl TemperatureRadial {
    fn update_charts(&mut self, ctx: &Context<Self>) {
        let readings = &ctx.props().readings;
        
        if readings.is_empty() {
            return;
        }
        
        // Throttle updates to reduce rendering overhead
        let now = window().unwrap().performance().unwrap().now();
        if now - self.last_update < self.update_throttle_ms {
            return;
        }
        self.last_update = now;
        
        if let Some(chart) = &self.radar_chart {
            // Process data in WASM for better performance
            let processed_data = self.process_sensor_data_wasm(readings);
            update_sensor_radar_chart(chart, &processed_data);
        }
    }
    
    fn process_sensor_data_wasm(&self, readings: &HashMap<String, RealTimeReading>) -> js_sys::Array {
        let sensor_data = js_sys::Array::new();
        
        // Limit to max 10 sensors for performance
        let mut sorted_readings: Vec<_> = readings.iter().collect();
        sorted_readings.sort_by_key(|(id, _)| *id);
        
        for (sensor_id, reading) in sorted_readings.into_iter().take(10) {
            // Pre-calculate values in Rust (faster than JS)
            let total_latency = reading.kinesis_to_lambda_us + 
                               reading.lambda_processing_us + 
                               reading.cache_to_websocket_us + 
                               reading.websocket_to_frontend_us;
            
            // Create minimal data structure
            let radar_values = js_sys::Array::new();
            radar_values.push(&reading.temperature.into());
            radar_values.push(&reading.speed_kms.into());
            radar_values.push(&reading.connection_speed_mbps.into());
            radar_values.push(&((total_latency / 100) as f32).into()); // Scale down
            radar_values.push(&reading.position.latitude.abs().into());
            radar_values.push(&reading.position.longitude.abs().into());
            
            let sensor_obj = js_sys::Object::new();
            js_sys::Reflect::set(&sensor_obj, &"sensor_id".into(), &sensor_id.as_str().into()).unwrap();
            js_sys::Reflect::set(&sensor_obj, &"values".into(), &radar_values).unwrap();
            
            sensor_data.push(&sensor_obj);
        }
        
        sensor_data
    }
}