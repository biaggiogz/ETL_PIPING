#!/bin/bash

# Get current directory
DIR=$(pwd)
echo "Current directory: $DIR"

# Prompt user to enter folder name(s) to avoid (e.g. target or target logs etc.)
read -p "Enter folder name(s) to avoid anywhere inside this directory (separate multiple names by spaces): " -a exclude_folders

# Check if input is empty
if [ ${#exclude_folders[@]} -eq 0 ]; then
    echo "No folders specified to avoid. Exiting."
    exit 1
fi

# Show folders to avoid and confirm
echo "You want to exclude all folders named:"
for f in "${exclude_folders[@]}"; do
    echo "  - $f"
done

while true; do
    read -p "Confirm exclusion? (y/n): " confirm
    case "$confirm" in
        [Yy]* ) break ;;
        [Nn]* ) echo "Operation cancelled."; exit 0 ;;
        * ) echo "Please answer y or n." ;;
    esac
done

# Build pattern for tree -I option (folders separated by |)
pattern=$(IFS="|"; echo "${exclude_folders[*]}")

echo "Printing tree excluding all folders named: $pattern"
tree -I "$pattern"
