//project_root/rust/src/validators/data_validator.rs
use pyo3::prelude::*;
use rayon::prelude::*;

pub fn validate_data(ages: Vec<i32>, incomes: Vec<f64>) -> PyResult<bool> {
    // Process validation in parallel chunks
    let chunk_size = 100_000;

    let ages_valid = ages.par_chunks(chunk_size)
        .all(|chunk| chunk.par_iter().all(|&age| age >= 1 && age <= 100));

    if !ages_valid {
        return Ok(false);
    }

    let incomes_valid = incomes.par_chunks(chunk_size)
        .all(|chunk| chunk.par_iter().all(|&income| !income.is_nan()));

    Ok(incomes_valid)
}