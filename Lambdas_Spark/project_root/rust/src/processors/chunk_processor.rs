//project_root/rust/src/processors/chunk_processor.rs
use pyo3::prelude::*;
use rayon::prelude::*;

pub fn process_chunk(data: Vec<(i64, f64)>) -> PyResult<Vec<(i64, f64, String)>> {
    let mut processed = Vec::with_capacity(data.len()); // Pre-allocate vector
    data.par_iter()
        .map(|(id, rand_val)| {
            let age = id % 100 + 1;
            let income = *id as f64 * rand_val;
            let country = if id % 10 < 5 { "US" } else { "UK" };
            (*id, income, country.to_string())
        })
        .collect_into_vec(&mut processed); // Use collect_into_vec instead of collect

    Ok(processed)
}

