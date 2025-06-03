#!/bin/bash

# Navigate to project root
cd "$(dirname "$0")"  # assumes script is placed in project_root

# Clear output files if they exist

> rust.txt


echo "Extracting Rust files (excluding target/)..."
find src -name "*.rs" -not -path "src/target/*" | while read filepath; do
    echo "##### FILE: $filepath #####" >> rust.txt
    cat "$filepath" >> rust.txt
    echo -e "\n\n" >> rust.txt
done

echo "Extraction complete: python.txt and rust.txt created."
