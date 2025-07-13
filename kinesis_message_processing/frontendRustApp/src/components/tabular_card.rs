use yew::prelude::*;
use crate::types::RealTimeReading;
use std::collections::HashMap;

#[derive(Properties, PartialEq)]
pub struct TabularCardProps {
    pub readings: HashMap<String, RealTimeReading>,
}

#[function_component(TabularCard)]
pub fn tabular_card(props: &TabularCardProps) -> Html {
    let readings = &props.readings;
    
    if readings.is_empty() {
        return html! {
            <div class="tabular-card">
                <h3>{"No sensor data available"}</h3>
            </div>
        };
    }

    html! {
        <div class="tabular-card">
            <h3>{"All Devices - Real-time Data"}</h3>
            <div class="table-container">
                <table class="sensor-table">
                    <thead>
                        <tr>
                            <th>{"Sensor ID"}</th>
                            <th>{"Temperature (°C)"}</th>
                            <th>{"Position"}</th>
                            <th>{"Speed (km/h)"}</th>
                            <th>{"Connection (Mbps)"}</th>
                            <th>{"Total Latency (μs)"}</th>
                        </tr>
                    </thead>
                    <tbody>
                        {for readings.values().map(|reading| {
                            let total_latency = reading.kinesis_to_lambda_us + 
                                               reading.lambda_processing_us + 
                                               reading.cache_to_websocket_us + 
                                               reading.websocket_to_frontend_us;
                            html! {
                                <tr>
                                    <td class="sensor-id">{&reading.sensor_id}</td>
                                    <td>{format!("{:.1}", reading.temperature)}</td>
                                    <td>{format!("{:.4}, {:.4}", reading.position.latitude, reading.position.longitude)}</td>
                                    <td>{format!("{:.1}", reading.speed_kms)}</td>
                                    <td>{format!("{:.1}", reading.connection_speed_mbps)}</td>
                                    <td class="latency">{total_latency}</td>
                                </tr>
                            }
                        })}
                    </tbody>
                </table>
            </div>
        </div>
    }
}