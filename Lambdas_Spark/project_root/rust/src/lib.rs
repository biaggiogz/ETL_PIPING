// project_root/rust/src/lib.rs

use pyo3::prelude::*;

mod processors;
mod validators;

use processors::process_chunk_wrapper;
use validators::validate_data_wrapper;

#[pymodule]
fn data_processor(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(process_chunk_wrapper, m)?)?;
    m.add_function(wrap_pyfunction!(validate_data_wrapper, m)?)?;
    Ok(())
}
