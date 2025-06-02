//project_root/rust/src/processors/chunk_processor.rs
use pyo3::prelude::*;
use rayon::prelude::*;

pub fn process_chunk(data: Vec<(i64, f64)>) -> PyResult<Vec<(i64, f64, String)>> {
    let processed: Vec<_> = data.par_iter()
        .map(|(id, rand_val)| {
            let age = id % 100 + 1;
            let income = *id as f64 * rand_val;
            let country = if id % 10 < 5 { "US" } else { "UK" };
            (*id,income, country.to_string())
        })
        .collect();

    Ok(processed)
}
