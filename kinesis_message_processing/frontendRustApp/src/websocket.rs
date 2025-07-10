use serde_json::Value;
use wasm_bindgen::prelude::*;
use wasm_bindgen::JsCast;
use web_sys::{ErrorEvent, MessageEvent, WebSocket};
use yew::prelude::*;

use crate::types::{RealTimeReading, WebSocketMessage};

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
        }
    }

    pub fn connect(&mut self, url: &str) -> Result<(), JsValue> {
        let ws = WebSocket::new(url)?;
        
        let onmessage_callback = self.onmessage_callback.clone();
        let onmessage_closure = Closure::wrap(Box::new(move |e: MessageEvent| {
            if let Ok(txt) = e.data().dyn_into::<js_sys::JsString>() {
                let data = String::from(txt);
                if let Ok(mut reading) = serde_json::from_str::<RealTimeReading>(&data) {
                    // Calculate frontend receive timestamp more efficiently
                    let frontend_timestamp_ns = (js_sys::Date::now() * 1000.0) as u128 * 1_000;
                    reading.websocket_to_frontend_us = 
                        ((frontend_timestamp_ns.saturating_sub(reading.notification_timestamp_ns)) / 1000) as u64;
                    onmessage_callback.emit(reading);
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