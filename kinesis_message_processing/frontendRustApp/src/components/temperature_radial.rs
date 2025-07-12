use yew::prelude::*;
use wasm_bindgen::prelude::*;
use crate::types::RealTimeReading;
use std::collections::HashMap;
use gloo::timers::callback::Timeout;

#[wasm_bindgen]
extern "C" {
    #[wasm_bindgen(js_name = initTemperatureRadialChart)]
    fn init_temperature_radial_chart(element_id: &str) -> JsValue;
    
    #[wasm_bindgen(js_name = updateTemperatureRadialChart)]
    fn update_temperature_radial_chart(chart: &JsValue, bands: &js_sys::Array);

    #[wasm_bindgen(js_name = initDeviceNetworkChart)]
    fn init_device_network_chart(element_id: &str) -> JsValue;
    
    #[wasm_bindgen(js_name = updateDeviceNetworkChart)]
    fn update_device_network_chart(chart: &JsValue, devices: &js_sys::Array);
}

#[derive(Properties, PartialEq)]
pub struct TemperatureRadialProps {
    pub readings: HashMap<String, RealTimeReading>,
}

pub struct TemperatureRadial {
    chart_instance: Option<JsValue>,
    network_chart: Option<JsValue>,
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
            chart_instance: None,
            network_chart: None,
        }
    }

    fn update(&mut self, ctx: &Context<Self>, msg: Self::Message) -> bool {
        match msg {
            TemperatureRadialMsg::InitComponents => {
                self.chart_instance = Some(init_temperature_radial_chart("temperatureRadialChart"));
                self.network_chart = Some(init_device_network_chart("deviceNetworkChart"));
                
                // After initialization, update with current data if available
                if !ctx.props().readings.is_empty() {
                    let link = ctx.link().clone();
                    Timeout::new(100, move || {
                        link.send_message(TemperatureRadialMsg::UpdateData);
                    }).forget();
                }
                false
            }
            TemperatureRadialMsg::UpdateData => {
                if self.network_chart.is_some() || self.chart_instance.is_some() {
                    self.update_components(ctx);
                }
                false
            }
        }
    }

    fn view(&self, ctx: &Context<Self>) -> Html {
        let init_components = ctx.link().callback(|_| TemperatureRadialMsg::InitComponents);
        
        html! {
            <div class="temperature-radial-section">
                <h2>{"Temperature Distribution Dashboard"}</h2>
                
                <div class="radial-container">
                    <div class="network-panel">
                        <h3>{"Device Network (Lat/Lng + Neighbors)"}</h3>
                        <div 
                            id="deviceNetworkChart"
                            onload={init_components}
                        >
                        </div>
                    </div>
                    
                    <div class="radial-chart-panel">
                        <h3>{"Temperature Radial Visualization"}</h3>
                        <div 
                            id="temperatureRadialChart"
                        >
                        </div>
                    </div>
                </div>
            </div>
        }
    }

    fn rendered(&mut self, ctx: &Context<Self>, first_render: bool) {
        if first_render {
            // Delay initialization to ensure DOM and scripts are ready
            let link = ctx.link().clone();
            Timeout::new(500, move || {
                link.send_message(TemperatureRadialMsg::InitComponents);
            }).forget();
        } else {
            // Always try to update data when component re-renders
            ctx.link().send_message(TemperatureRadialMsg::UpdateData);
        }
    }
}

impl TemperatureRadial {
    fn update_components(&self, ctx: &Context<Self>) {
        let readings = &ctx.props().readings;
        
        if readings.is_empty() {
            return;
        }
        
        // Prepare device data for network visualization
        let mut device_data = Vec::new();
        let mut bands: HashMap<i32, Vec<String>> = HashMap::new();
        
        for (sensor_id, reading) in readings {
            let temp_band = ((reading.temperature / 5.0).floor() as i32) * 5;
            bands.entry(temp_band).or_insert_with(Vec::new).push(sensor_id.clone());
            
            device_data.push(serde_json::json!({
                "sensor_id": sensor_id,
                "latitude": reading.position.latitude,
                "longitude": reading.position.longitude,
                "temperature": reading.temperature
            }));
        }
        
        // Update device network chart
        if let Some(chart) = &self.network_chart {
            let data_array = js_sys::Array::new();
            for item in device_data {
                data_array.push(&JsValue::from_str(&item.to_string()));
            }
            update_device_network_chart(chart, &data_array);
        }
        
        // Update temperature radial chart
        if let Some(chart) = &self.chart_instance {
            let bands_array = js_sys::Array::new();
            
            for (temp_band, devices) in bands {
                let band_data = js_sys::Object::new();
                js_sys::Reflect::set(&band_data, &"temp_band".into(), &temp_band.into()).unwrap();
                js_sys::Reflect::set(&band_data, &"device_count".into(), &devices.len().into()).unwrap();
                js_sys::Reflect::set(&band_data, &"devices".into(), &{
                    let devices_array = js_sys::Array::new();
                    for device in devices {
                        devices_array.push(&device.into());
                    }
                    devices_array.into()
                }).unwrap();
                bands_array.push(&band_data);
            }
            
            update_temperature_radial_chart(chart, &bands_array);
        }
    }
}