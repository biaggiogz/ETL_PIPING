use yew::prelude::*;
use crate::types::LatencyMetrics;

#[derive(Properties, PartialEq)]
pub struct LatencyChartProps {
    pub history: Vec<LatencyMetrics>,
}

#[function_component(LatencyChart)]
pub fn latency_chart(props: &LatencyChartProps) -> Html {
    let history = &props.history;
    
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

    let chart_height = 200.0;
    let chart_width = 600.0;
    let points_count = history.len().min(50);
    let recent_history = &history[history.len().saturating_sub(points_count)..];

    let path_data = recent_history
        .iter()
        .enumerate()
        .map(|(i, metrics)| {
            let x = (i as f64 / (points_count - 1) as f64) * chart_width;
            let y = chart_height - (metrics.total_pipeline_us as f64 / max_latency * chart_height);
            if i == 0 {
                format!("M {} {}", x, y)
            } else {
                format!("L {} {}", x, y)
            }
        })
        .collect::<Vec<_>>()
        .join(" ");

    let avg_latency = recent_history.iter()
        .map(|m| m.total_pipeline_us)
        .sum::<u64>() as f64 / recent_history.len() as f64;

    html! {
        <div class="latency-chart">
            <div class="chart-stats">
                <div class="stat">
                    <span class="label">{"Current:"}</span>
                    <span class="value">{format!("{}μs", recent_history.last().unwrap().total_pipeline_us)}</span>
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
            
            <svg width={chart_width.to_string()} height={chart_height.to_string()} class="chart-svg">
                <defs>
                    <linearGradient id="gradient" x1="0%" y1="0%" x2="0%" y2="100%">
                        <stop offset="0%" style="stop-color:#4CAF50;stop-opacity:0.8" />
                        <stop offset="100%" style="stop-color:#4CAF50;stop-opacity:0.1" />
                    </linearGradient>
                </defs>
                
                // Grid lines
                {for (0..5).map(|i| {
                    let y = (i as f64 / 4.0) * chart_height;
                    let latency_value = max_latency * (1.0 - i as f64 / 4.0);
                    html! {
                        <g key={i}>
                            <line x1="0" y1={y.to_string()} x2={chart_width.to_string()} y2={y.to_string()} 
                                  stroke="#e0e0e0" stroke-width="1" />
                            <text x="5" y={(y - 5.0).to_string()} fill="#666" font-size="12">
                                {format!("{:.0}μs", latency_value)}
                            </text>
                        </g>
                    }
                })}
                
                // Latency line
                <path d={path_data} stroke="#4CAF50" stroke-width="2" fill="none" />
                
                // Data points
                {for recent_history.iter().enumerate().map(|(i, metrics)| {
                    let x = (i as f64 / (points_count - 1) as f64) * chart_width;
                    let y = chart_height - (metrics.total_pipeline_us as f64 / max_latency * chart_height);
                    html! {
                        <circle cx={x.to_string()} cy={y.to_string()} r="3" fill="#4CAF50" key={i}>
                            <title>{format!("Total: {}μs\nKinesis→Lambda: {}μs\nLambda: {}μs\nCache→WS: {}μs\nWS→Frontend: {}μs", 
                                metrics.total_pipeline_us,
                                metrics.kinesis_to_lambda_us,
                                metrics.lambda_processing_us,
                                metrics.cache_to_websocket_us,
                                metrics.websocket_to_frontend_us
                            )}</title>
                        </circle>
                    }
                })}
            </svg>
        </div>
    }
}