// project_root/rust/src/processors/mod.rs
pub mod chunk_processor;

use chunk_processor::process_chunk;
use pyo3::prelude::*;

#[pyclass]
#[derive(Clone)]
pub struct Processed {
    #[pyo3(get)]
    pub id: i64,
    #[pyo3(get)]
    pub income: f64,
    #[pyo3(get)]
    pub country: String,
}

#[pyfunction]
pub fn process_chunk_wrapper(data: Vec<(i64, f64)>) -> PyResult<Vec<(i64, f64, String)>> {
    process_chunk(data)
}
