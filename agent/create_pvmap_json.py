#!/usr/bin/env python3
"""
Script to create JSON documents for each import in the configuration file.
Each JSON will contain sample data from the import files for vector database storage.
"""

import json
import csv
import os
from pathlib import Path

def read_csv_first_n_rows(file_path, n=10):
    """Read first n rows of CSV file and return as text string"""
    try:
        if not os.path.exists(file_path):
            return ""
        
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = []
            for i, line in enumerate(f):
                if i >= n:
                    break
                lines.append(line.rstrip())
            return '\n'.join(lines)
    except Exception as e:
        print(f"Error reading CSV {file_path}: {e}")
        return ""

def read_csv_all_rows(file_path):
    """Read entire CSV file and return as text string"""
    try:
        if not os.path.exists(file_path):
            return ""
        
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read().strip()
    except Exception as e:
        print(f"Error reading CSV {file_path}: {e}")
        return ""

def read_text_file(file_path):
    """Read entire text file content"""
    try:
        if not os.path.exists(file_path):
            return ""
        
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        print(f"Error reading file {file_path}: {e}")
        return ""

def process_import(import_id, import_config, base_path):
    """Process a single import and return JSON document"""
    
    # Get file paths
    files = import_config.get('files', {})
    
    # Build full paths
    def get_full_path(relative_path):
        if not relative_path:
            return ""
        return os.path.join(base_path, relative_path)
    
    # Extract data for each required field
    result = {
        "import_id": import_id,
        "input_data_csv": "",
        "pv_map_csv": "",
        "metadata_csv": "",
        "place_resolved_csv": "",
        "tmcf": "",
        "output_csv": "",
        "categories": import_config.get('categories', {}).get('main_categories', []),
        "subcategories": import_config.get('categories', {}).get('subcategories', [])
    }
    
    # Process input data CSV (first 10 rows)
    test_inputs = files.get('test_inputs', [])
    if test_inputs:
        input_path = get_full_path(test_inputs[0])
        result['input_data_csv'] = read_csv_first_n_rows(input_path, 10)
    
    # Process PV map CSV (all rows)
    pvmap_files = files.get('pvmap_files', [])
    if pvmap_files:
        pvmap_path = get_full_path(pvmap_files[0])
        result['pv_map_csv'] = read_csv_all_rows(pvmap_path)
    
    # Process metadata CSV (all rows)
    metadata_files = files.get('metadata_files', [])
    if metadata_files:
        metadata_path = get_full_path(metadata_files[0])
        result['metadata_csv'] = read_csv_all_rows(metadata_path)
    
    # Process places resolved CSV (first 10 rows)
    places_resolved_files = files.get('places_resolved_files', [])
    if places_resolved_files:
        places_path = get_full_path(places_resolved_files[0])
        result['place_resolved_csv'] = read_csv_first_n_rows(places_path, 10)
    
    # Process TMCF file
    test_outputs = files.get('test_outputs', {})
    tmcf_files = test_outputs.get('tmcf', [])
    if tmcf_files:
        tmcf_path = get_full_path(tmcf_files[0])
        result['tmcf'] = read_text_file(tmcf_path)
    
    # Process output CSV (first 10 rows)
    csv_files = test_outputs.get('csv', [])
    if csv_files:
        output_path = get_full_path(csv_files[0])
        result['output_csv'] = read_csv_first_n_rows(output_path, 10)
    
    return result

def main():
    # Load configuration
    config_path = '/home/rohitrkumar/Documents/dc/github/rohitkumarbhagat/data/statvar_imports_config_with_categories.json'
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    base_path = '/home/rohitrkumar/Documents/dc/github/rohitkumarbhagat/data/statvar_imports'
    output_dir = '/home/rohitrkumar/Documents/dc/github/rohitkumarbhagat/data/agent/pvmap_sample'
    
    # Process each import
    imports = config.get('imports', {})
    for import_id, import_config in imports.items():
        print(f"Processing {import_id}...")
        
        # Generate JSON document
        json_doc = process_import(import_id, import_config, base_path)
        
        # Write to file
        output_file = os.path.join(output_dir, f"{import_id}.json")
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(json_doc, f, indent=2, ensure_ascii=False)
        
        print(f"Created {output_file}")
    
    print(f"Processed {len(imports)} imports successfully!")

if __name__ == "__main__":
    main()