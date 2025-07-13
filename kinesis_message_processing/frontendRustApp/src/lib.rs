use yew::prelude::*;
use wasm_bindgen::prelude::*;

mod components;
mod websocket;
mod types;

use components::Dashboard;
use types::RealTimeReading;

#[wasm_bindgen]
extern "C" {
    #[wasm_bindgen(js_namespace = console)]
    fn log(s: &str);
}

#[wasm_bindgen]
pub fn parse_sensor_messages(json_strings: &js_sys::Array) -> js_sys::Array {
    let results = js_sys::Array::new();
    
    for i in 0..json_strings.length() {
        if let Ok(json_str) = json_strings.get(i).dyn_into::<js_sys::JsString>() {
            let json_string: String = json_str.into();
            
            match serde_json::from_str::<RealTimeReading>(&json_string) {
                Ok(mut reading) => {
                    // Calculate frontend timestamp in WASM
                    let frontend_timestamp_ns = (js_sys::Date::now() * 1_000_000.0) as u128;
                    reading.websocket_to_frontend_us = 
                        frontend_timestamp_ns.saturating_sub(reading.notification_timestamp_ns) as u64 / 1000;
                    
                    // Serialize back to JS object
                    if let Ok(js_value) = serde_wasm_bindgen::to_value(&reading) {
                        results.push(&js_value);
                    }
                }
                Err(_) => {
                    // Skip invalid JSON
                    continue;
                }
            }
        }
    }
    
    results
}

#[function_component(App)]
fn app() -> Html {
    html! {
        <div class="app">
            <Dashboard />
        </div>
    }
}

#[wasm_bindgen(start)]
pub fn main() {
    yew::Renderer::<App>::new().render();
}