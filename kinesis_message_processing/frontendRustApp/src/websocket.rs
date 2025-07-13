
use wasm_bindgen::prelude::*;
use wasm_bindgen::JsCast;
use web_sys::{ErrorEvent, MessageEvent, WebSocket};
use yew::prelude::*;
use gloo::timers::callback::Timeout;

use crate::types::{RealTimeReading, WebSocketMessage};

#[wasm_bindgen]
extern "C" {
    #[wasm_bindgen(js_name = parseSensorMessages)]
    fn parse_sensor_messages(json_strings: &js_sys::Array) -> js_sys::Array;
}

pub enum WebSocketAction {
    Connect(String),
    Disconnect,
    Subscribe(String),
    Unsubscribe(String),
    SendMessage(String),
}

pub struct WebSocketService {
    ws: Option<WebSocket>,
    onmessage_callback: Callback<RealTimeReading>,
    onerror_callback: Callback<String>,
    onopen_callback: Callback<()>,
    onclose_callback: Callback<()>,
    message_batch: Vec<String>,
    batch_timeout: Option<Timeout>,
}

impl WebSocketService {
    pub fn new(
        onmessage: Callback<RealTimeReading>,
        onerror: Callback<String>,
        onopen: Callback<()>,
        onclose: Callback<()>,
    ) -> Self {
        Self {
            ws: None,
            onmessage_callback: onmessage,
            onerror_callback: onerror,
            onopen_callback: onopen,
            onclose_callback: onclose,
            message_batch: Vec::new(),
            batch_timeout: None,
        }
    }

    pub fn connect(&mut self, url: &str) -> Result<(), JsValue> {
        let ws = WebSocket::new(url)?;
        
        let onmessage_callback = self.onmessage_callback.clone();
        let onmessage_closure = Closure::wrap(Box::new(move |e: MessageEvent| {
            if let Ok(txt) = e.data().dyn_into::<js_sys::JsString>() {
                let data = String::from(txt);
                
                // Batch messages for WASM processing
                let batch = js_sys::Array::new();
                batch.push(&data.into());
                
                // Parse in WASM
                let parsed_results = crate::parse_sensor_messages(&batch);
                
                // Process results
                for i in 0..parsed_results.length() {
                    if let Ok(reading_value) = parsed_results.get(i).dyn_into::<js_sys::Object>() {
                        if let Ok(reading) = serde_wasm_bindgen::from_value::<RealTimeReading>(reading_value.into()) {
                            onmessage_callback.emit(reading);
                        }
                    }
                }
            }
        }) as Box<dyn FnMut(MessageEvent)>);
        ws.set_onmessage(Some(onmessage_closure.as_ref().unchecked_ref()));
        onmessage_closure.forget();

        let onopen_callback = self.onopen_callback.clone();
        let onopen_closure = Closure::wrap(Box::new(move |_| {
            onopen_callback.emit(());
        }) as Box<dyn FnMut(JsValue)>);
        ws.set_onopen(Some(onopen_closure.as_ref().unchecked_ref()));
        onopen_closure.forget();

        let onclose_callback = self.onclose_callback.clone();
        let onclose_closure = Closure::wrap(Box::new(move |_| {
            onclose_callback.emit(());
        }) as Box<dyn FnMut(JsValue)>);
        ws.set_onclose(Some(onclose_closure.as_ref().unchecked_ref()));
        onclose_closure.forget();

        let onerror_callback = self.onerror_callback.clone();
        let onerror_closure = Closure::wrap(Box::new(move |e: ErrorEvent| {
            onerror_callback.emit(format!("WebSocket error: {:?}", e));
        }) as Box<dyn FnMut(ErrorEvent)>);
        ws.set_onerror(Some(onerror_closure.as_ref().unchecked_ref()));
        onerror_closure.forget();

        self.ws = Some(ws);
        Ok(())
    }

    pub fn send_message(&self, message: &WebSocketMessage) -> Result<(), JsValue> {
        if let Some(ws) = &self.ws {
            let json = serde_json::to_string(message).unwrap();
            ws.send_with_str(&json)?;
        }
        Ok(())
    }

    pub fn subscribe(&self, sensor_id: &str) -> Result<(), JsValue> {
        let message = WebSocketMessage {
            action: "subscribe".to_string(),
            sensor_id: Some(sensor_id.to_string()),
        };
        self.send_message(&message)
    }

    pub fn disconnect(&mut self) {
        if let Some(ws) = &self.ws {
            let _ = ws.close();
        }
        self.ws = None;
    }
}