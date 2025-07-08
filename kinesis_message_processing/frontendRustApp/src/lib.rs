use yew::prelude::*;
use wasm_bindgen::prelude::*;

mod components;
mod websocket;
mod types;

use components::Dashboard;

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