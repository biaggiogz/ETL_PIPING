use yew::prelude::*;
use wasm_bindgen::prelude::*;
use crate::types::RealTimeReading;
use std::collections::HashMap;

#[wasm_bindgen]
extern "C" {
    #[wasm_bindgen(js_name = initSpeedRacingChart)]
    fn init_speed_racing_chart(element_id: &str) -> JsValue;
    
    #[wasm_bindgen(js_name = updateSpeedRacingChart)]
    fn update_speed_racing_chart(chart: &JsValue, devices: &js_sys::Array, speeds: &js_sys::Array);
}

#[derive(Properties, PartialEq)]
pub struct SpeedRacingProps {
    pub readings: HashMap<String, RealTimeReading>,
}

pub struct SpeedRacing {
    chart_ref: NodeRef,
    chart_instance: Option<JsValue>,
}

pub enum SpeedRacingMsg {
    InitChart,
    UpdateChart,
}

impl Component for SpeedRacing {
    type Message = SpeedRacingMsg;
    type Properties = SpeedRacingProps;

    fn create(_ctx: &Context<Self>) -> Self {
        Self {
            chart_ref: NodeRef::default(),
            chart_instance: None,
        }
    }

    fn update(&mut self, _ctx: &Context<Self>, msg: Self::Message) -> bool {
        match msg {
            SpeedRacingMsg::InitChart => {
                self.chart_instance = Some(init_speed_racing_chart("speedRacingChart"));
                false
            }
            SpeedRacingMsg::UpdateChart => {
                self.update_chart_data(_ctx);
                false
            }
        }
    }

    fn view(&self, ctx: &Context<Self>) -> Html {
        let init_chart = ctx.link().callback(|_| SpeedRacingMsg::InitChart);
        
        html! {
            <div class="speed-racing-section">
                <h2>{"Device Speed Racing"}</h2>
                <div 
                    id="speedRacingChart" 
                    ref={self.chart_ref.clone()}
                    onload={init_chart}
                >
                </div>
            </div>
        }
    }

    fn rendered(&mut self, ctx: &Context<Self>, first_render: bool) {
        if first_render {
            ctx.link().send_message(SpeedRacingMsg::InitChart);
        }
        ctx.link().send_message(SpeedRacingMsg::UpdateChart);
    }
}

impl SpeedRacing {
    fn update_chart_data(&self, ctx: &Context<Self>) {
        if let Some(chart) = &self.chart_instance {
            let readings = &ctx.props().readings;
            
            let mut paired: Vec<_> = readings.iter().collect();
            paired.sort_by(|a, b| b.1.speed_kms.partial_cmp(&a.1.speed_kms).unwrap_or(std::cmp::Ordering::Equal));
            
            let devices_array = js_sys::Array::new();
            let speeds_array = js_sys::Array::new();
            
            for (sensor_id, reading) in paired {
                devices_array.push(&sensor_id.as_str().into());
                speeds_array.push(&(reading.speed_kms as f64).into());
            }
            
            update_speed_racing_chart(chart, &devices_array, &speeds_array);
        }
    }
}