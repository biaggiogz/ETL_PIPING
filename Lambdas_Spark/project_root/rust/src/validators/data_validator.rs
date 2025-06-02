//project_root/rust/src/validators/data_validator.rs
use pyo3::prelude::*;
use rayon::prelude::*;

pub fn validate_data(ages: Vec<i32>, incomes: Vec<f64>) -> PyResult<bool> {
    let age_valid = ages.par_iter()
        .all(|&age| age >= 1 && age <= 100);

    let income_valid = incomes.par_iter()
        .all(|&income| !income.is_nan());

    Ok(age_valid && income_valid)
}
