use yew::prelude::*;
use wasm_bindgen::prelude::*;
use crate::types::RealTimeReading;
use std::collections::HashMap;
use gloo::timers::callback::Timeout;

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
    fn update_charts(&self, ctx: &Context<Self>) {
        let readings = &ctx.props().readings;
        
        if readings.is_empty() {
            return;
        }
        
        if let Some(chart) = &self.radar_chart {
            let sensor_data = js_sys::Array::new();
            for (sensor_id, reading) in readings {
                let data = serde_json::json!({
                    "sensor_id": sensor_id,
                    "temperature": reading.temperature,
                    "speed_kms": reading.speed_kms,
                    "connection_speed_mbps": reading.connection_speed_mbps,
                    "position": {
                        "latitude": reading.position.latitude,
                        "longitude": reading.position.longitude
                    },
                    "kinesis_to_lambda_us": reading.kinesis_to_lambda_us,
                    "lambda_processing_us": reading.lambda_processing_us,
                    "cache_to_websocket_us": reading.cache_to_websocket_us,
                    "websocket_to_frontend_us": reading.websocket_to_frontend_us
                });
                sensor_data.push(&JsValue::from_str(&data.to_string()));
            }
            update_sensor_radar_chart(chart, &sensor_data);
        }
    }
}