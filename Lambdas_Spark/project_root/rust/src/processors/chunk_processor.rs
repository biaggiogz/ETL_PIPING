//project_root/rust/src/processors/chunk_processor.rs
use pyo3::prelude::*;
use rayon::prelude::*;

pub fn process_chunk(data: Vec<(i64, f64)>) -> PyResult<Vec<(i64, f64, String)>> {
    // Increase initial capacity allocation
    let mut processed = Vec::with_capacity(data.len());

    // Process in parallel chunks of 100k records
    let chunk_size = 100_000;
    processed = data.par_chunks(chunk_size)
        .flat_map(|chunk| {
            chunk.par_iter().map(|(id, rand_val)| {
                let age = id % 100 + 1;
                // Optimize math operations
                let income = (*id as f64).mul_add(1.0, *rand_val);
                let country = if id % 10 < 5 { "US" } else { "UK" };
                (*id, income, country.to_string())
            }).collect::<Vec<_>>()
        })
        .collect();

    Ok(processed)
}

# project_root/lambda_pyspark/src/processing/data_processing.py
import data_processor
import numpy as np
from typing import Tuple, List

def process_data_chunk(
        chunk_data: List[Tuple[int, float]]
) -> List[Tuple[int, float, str]]:
    """
    Process data chunk using Rust implementation
    """
    return data_processor.process_chunk_wrapper(chunk_data)

def validate_chunk_data(
        ages: np.ndarray,
        incomes: np.ndarray
) -> bool:
    """
    Validate data using Rust implementation
    """
    return data_processor.validate_data_wrapper(ages.tolist(), incomes.tolist())

