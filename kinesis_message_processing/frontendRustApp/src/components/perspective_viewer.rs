use yew::prelude::*;

#[function_component(PerspectiveViewer)]
pub fn perspective_viewer() -> Html {
    html! {
        <div class="perspective-section">
            <h2>{"Interactive Sensor Grid"}</h2>
            <perspective-viewer 
                id="sensor-viewer"
                plugin="Datagrid"
                columns={r#"["sensor_id", "temperature", "latitude", "longitude", "speed_kms", "total_pipeline_us"]"#}
                aggregates={r#"{"temperature": "avg", "speed_kms": "avg", "total_pipeline_us": "avg"}"#}
                group-by={r#"["sensor_id"]"#}
                style="height: 500px; width: 100%;"
            />
        </div>
    }
}