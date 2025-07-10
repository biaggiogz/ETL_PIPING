use yew::prelude::*;
use web_sys::{HtmlCanvasElement, CanvasRenderingContext2d};
use wasm_bindgen::JsCast;
use crate::types::LatencyMetrics;

#[derive(Properties, PartialEq)]
pub struct LatencyChartProps {
    pub history: Vec<LatencyMetrics>,
}

#[function_component(LatencyChart)]
pub fn latency_chart(props: &LatencyChartProps) -> Html {
    let history = &props.history;
    let canvas_ref = use_node_ref();
    
    // Use effect to draw on canvas when data changes
    {
        let canvas_ref = canvas_ref.clone();
        let history = history.clone();
        use_effect_with(
            history.len(), // Only redraw when length changes
            move |_| {
                if let Some(canvas) = canvas_ref.cast::<HtmlCanvasElement>() {
                    draw_chart(&canvas, &history);
                }
                || ()
            },
        );
    }
    
    if history.is_empty() {
        return html! {
            <div class="latency-chart">
                <p>{"No latency data available"}</p>
            </div>
        };
    }

    let max_latency = history.iter()
        .map(|m| m.total_pipeline_us)
        .max()
        .unwrap_or(1000) as f64;

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
                <div class="stat">
                    <span class="label">{"Max:"}</span>
                    <span class="value">{format!("{}μs", max_latency as u64)}</span>
                </div>
            </div>
            
            <canvas 
                ref={canvas_ref}
                width="600" 
                height="200" 
                style="border: 1px solid #e0e0e0; background: white;"
            />
        </div>
    }
}

fn draw_chart(canvas: &HtmlCanvasElement, history: &[LatencyMetrics]) {
    if history.is_empty() {
        return;
    }
    
    let context = canvas
        .get_context("2d")
        .unwrap()
        .unwrap()
        .dyn_into::<CanvasRenderingContext2d>()
        .unwrap();
    
    let width = 600.0;
    let height = 200.0;
    
    // Clear canvas
    context.clear_rect(0.0, 0.0, width, height);
    
    let max_latency = history.iter()
        .map(|m| m.total_pipeline_us)
        .max()
        .unwrap_or(1000) as f64;
    
    // Draw grid
    context.set_stroke_style(&"#e0e0e0".into());
    context.set_line_width(1.0);
    for i in 0..5 {
        let y = (i as f64 / 4.0) * height;
        context.begin_path();
        context.move_to(0.0, y);
        context.line_to(width, y);
        context.stroke();
    }
    
    // Draw latency line
    if history.len() > 1 {
        context.set_stroke_style(&"#4CAF50".into());
        context.set_line_width(2.0);
        context.begin_path();
        
        for (i, metrics) in history.iter().enumerate() {
            let x = (i as f64 / (history.len() - 1) as f64) * width;
            let y = height - (metrics.total_pipeline_us as f64 / max_latency * height);
            
            if i == 0 {
                context.move_to(x, y);
            } else {
                context.line_to(x, y);
            }
        }
        
        context.stroke();
    }
}