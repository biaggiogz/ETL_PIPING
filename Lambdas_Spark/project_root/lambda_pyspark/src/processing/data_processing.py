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
