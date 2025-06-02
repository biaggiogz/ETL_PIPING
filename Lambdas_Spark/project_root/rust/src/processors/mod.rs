// project_root/rust/src/processors/mod.rs
pub mod chunk_processor;

use chunk_processor::process_chunk;
use pyo3::prelude::*;

#[pyfunction]
pub fn process_chunk_wrapper(data: Vec<(i64, f64)>) -> PyResult<Vec<(i64, f64, String)>> {
    process_chunk(data)
}
