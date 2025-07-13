use yew::prelude::*;
use wasm_bindgen::prelude::*;
use wasm_bindgen::JsCast;

use crate::types::LatencyMetrics;

#[wasm_bindgen]
extern "C" {
    #[wasm_bindgen(js_namespace = echarts)]
    fn init(dom: &web_sys::Element) -> JsValue;
}

#[derive(Properties, PartialEq)]
pub struct LatencyChartProps {
    pub history: Vec<LatencyMetrics>,
}

#[function_component(LatencyChart)]
pub fn latency_chart(props: &LatencyChartProps) -> Html {
    let history = &props.history;
    let chart_ref = use_node_ref();
    
    use_effect_with(
        history.len(),
        {
            let chart_ref = chart_ref.clone();
            let history = history.clone();
            move |_| {
                if let Some(element) = chart_ref.cast::<web_sys::Element>() {
                    render_chart(&element, &history);
                }
                || ()
            }
        },
    );
    
    if history.is_empty() {
        return html! {
            <div class="latency-chart">
                <p>{"No latency data available"}</p>
            </div>
        };
    }

    let avg_latency = history.iter()
        .map(|m| m.total_pipeline_us)
        .sum::<u64>() as f64 / history.len() as f64;

    html! {
        <div class="latency-chart">
            <div class="chart-stats">
                <div class="stat">
                    <span class="label">{"Current:"}</span>
                    <span class="value">{format!("{}μs", history.last().unwrap().total_pipeline_us)}</span>
                </div>
                <div class="stat">
                    <span class="label">{"Average:"}</span>
                    <span class="value">{format!("{:.0}μs", avg_latency)}</span>
                </div>
            </div>
            
            <div ref={chart_ref} id="latency-chart" style="width: 100%; height: 300px;"></div>
        </div>
    }
}

fn render_chart(element: &web_sys::Element, history: &[LatencyMetrics]) {
    if history.is_empty() { return; }
    
    let chart = init(element);
    
    let x_data: Vec<JsValue> = (0..history.len()).map(|i| JsValue::from(i)).collect();
    let total_data: Vec<JsValue> = history.iter().map(|m| JsValue::from(m.total_pipeline_us)).collect();
    let kinesis_data: Vec<JsValue> = history.iter().map(|m| JsValue::from(m.kinesis_to_lambda_us)).collect();
    let lambda_data: Vec<JsValue> = history.iter().map(|m| JsValue::from(m.lambda_processing_us)).collect();
    let cache_data: Vec<JsValue> = history.iter().map(|m| JsValue::from(m.cache_to_websocket_us)).collect();
    let ws_data: Vec<JsValue> = history.iter().map(|m| JsValue::from(m.websocket_to_frontend_us)).collect();
    
    let option = js_sys::Object::new();
    
    // Title
    let title = js_sys::Object::new();
    js_sys::Reflect::set(&option, &"title".into(), &title).unwrap();
    
    // Tooltip
    let tooltip = js_sys::Object::new();
    js_sys::Reflect::set(&tooltip, &"trigger".into(), &"axis".into()).unwrap();
    js_sys::Reflect::set(&option, &"tooltip".into(), &tooltip).unwrap();
    
    // Legend
    let legend = js_sys::Object::new();
    js_sys::Reflect::set(&option, &"legend".into(), &legend).unwrap();
    
    // X Axis
    let x_axis = js_sys::Object::new();
    js_sys::Reflect::set(&x_axis, &"type".into(), &"category".into()).unwrap();
    let x_array = js_sys::Array::new();
    for val in x_data { x_array.push(&val); }
    js_sys::Reflect::set(&x_axis, &"data".into(), &x_array).unwrap();
    js_sys::Reflect::set(&option, &"xAxis".into(), &x_axis).unwrap();
    
    // Y Axis
    let y_axis = js_sys::Object::new();
    js_sys::Reflect::set(&y_axis, &"type".into(), &"value".into()).unwrap();
    js_sys::Reflect::set(&y_axis, &"name".into(), &"Latency (μs)".into()).unwrap();
    js_sys::Reflect::set(&option, &"yAxis".into(), &y_axis).unwrap();
    
    // Series
    let series = js_sys::Array::new();
    
    let create_series = |name: &str, data: Vec<JsValue>, color: &str| {
        let s = js_sys::Object::new();
        js_sys::Reflect::set(&s, &"name".into(), &name.into()).unwrap();
        js_sys::Reflect::set(&s, &"type".into(), &"line".into()).unwrap();
        let data_array = js_sys::Array::new();
        for val in data { data_array.push(&val); }
        js_sys::Reflect::set(&s, &"data".into(), &data_array).unwrap();
        let line_style = js_sys::Object::new();
        js_sys::Reflect::set(&line_style, &"color".into(), &color.into()).unwrap();
        js_sys::Reflect::set(&s, &"lineStyle".into(), &line_style).unwrap();
        s
    };
    
    series.push(&create_series("Total", total_data, "#ff6b6b"));
    series.push(&create_series("Kinesis→Lambda", kinesis_data, "#4ecdc4"));
    series.push(&create_series("Lambda Processing", lambda_data, "#45b7d1"));
    series.push(&create_series("Cache→WebSocket", cache_data, "#96ceb4"));
    series.push(&create_series("WebSocket→Frontend", ws_data, "#feca57"));
    
    js_sys::Reflect::set(&option, &"series".into(), &series).unwrap();
    
    // Call setOption method on chart
    if let Ok(set_option) = js_sys::Reflect::get(&chart, &"setOption".into()) {
        if let Ok(func) = set_option.dyn_into::<js_sys::Function>() {
            let _ = func.call1(&chart, &option);
        }
    }
}