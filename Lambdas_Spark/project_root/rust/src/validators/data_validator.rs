//project_root/rust/src/validators/data_validator.rs
use pyo3::prelude::*;
use rayon::prelude::*;

pub fn validate_data(ages: Vec<i32>, incomes: Vec<f64>) -> PyResult<bool> {
    if ages.par_iter().any(|&age| age < 1 || age > 100) {
        return Ok(false);
    }

    if incomes.par_iter().any(|&income| income.is_nan()) {
        return Ok(false);
    }

    Ok(true)
}
