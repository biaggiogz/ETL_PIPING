// project_root/rust/src/processors/mod.rs
pub mod data_validator;

use data_validator::validate_data;
use pyo3::prelude::*;

#[pyfunction]
pub fn validate_data_wrapper(ages: Vec<i32>, incomes: Vec<f64>) -> PyResult<bool> {
    validate_data(ages, incomes)
}
