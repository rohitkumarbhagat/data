#!/usr/bin/env python3
"""
Create CSV version of Data Commons Statistical Variable Hierarchy
"""

import json
import csv
from datetime import datetime

def create_csv_hierarchy():
    """Convert JSON hierarchy to CSV format"""
    
    # Load the JSON data
    with open('datacommons_statvar_hierarchy.json', 'r') as f:
        hierarchy = json.load(f)
    
    # Prepare CSV data
    csv_data = []
    
    # Add root level
    csv_data.append({
        'level': 0,
        'category_id': 'dc/g/Root',
        'category_name': 'Data Commons Variables',
        'parent_id': None,
        'parent_name': None,
        'variable_count': 247338,
        'path': 'Root'
    })
    
    # Process main categories (level 1)
    for category in hierarchy['root']['categories']:
        csv_data.append({
            'level': 1,
            'category_id': category['id'],
            'category_name': category['name'],
            'parent_id': 'dc/g/Root',
            'parent_name': 'Data Commons Variables',
            'variable_count': category['count'],
            'path': f"Root > {category['name']}"
        })
        
        # Process subcategories (level 2)
        for subcat in category['subcategories']:
            csv_data.append({
                'level': 2,
                'category_id': subcat['id'],
                'category_name': subcat['name'],
                'parent_id': category['id'],
                'parent_name': category['name'],
                'variable_count': subcat['count'],
                'path': f"Root > {category['name']} > {subcat['name']}"
            })
    
    # Write to CSV
    fieldnames = ['level', 'category_id', 'category_name', 'parent_id', 'parent_name', 'variable_count', 'path']
    
    with open('datacommons_statvar_hierarchy.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(csv_data)
    
    print(f"Created CSV with {len(csv_data)} entries")
    return csv_data

def create_mapping_file():
    """Create mapping file to connect with statvar imports"""
    
    # Load the JSON data
    with open('datacommons_statvar_hierarchy.json', 'r') as f:
        hierarchy = json.load(f)
    
    # Create mapping structure
    mapping = {
        "metadata": {
            "created_at": datetime.now().isoformat(),
            "description": "Mapping between Data Commons statistical variable categories and import types",
            "version": "1.0"
        },
        "category_mappings": {},
        "import_to_category_suggestions": {
            "demographics": ["dc/g/Demographics"],
            "population": ["dc/g/Demographics"],
            "census": ["dc/g/Demographics"],
            "health": ["dc/g/Health"],
            "economic": ["dc/g/Economy"],
            "employment": ["dc/g/Economy"],
            "education": ["dc/g/Education"],
            "agriculture": ["dc/g/Agriculture"],
            "energy": ["dc/g/Energy"],
            "environment": ["dc/g/Environment"],
            "housing": ["dc/g/Housing"],
            "crime": ["dc/g/Crime"]
        }
    }
    
    # Add all categories to mapping
    for category in hierarchy['root']['categories']:
        mapping["category_mappings"][category['id']] = {
            "name": category['name'],
            "count": category['count'],
            "subcategories": {subcat['id']: subcat['name'] for subcat in category['subcategories']}
        }
    
    # Save mapping file
    with open('datacommons_statvar_mapping.json', 'w') as f:
        json.dump(mapping, f, indent=2)
    
    print("Created mapping file: datacommons_statvar_mapping.json")

def update_json_with_metadata():
    """Add metadata to the JSON file"""
    
    with open('datacommons_statvar_hierarchy.json', 'r') as f:
        hierarchy = json.load(f)
    
    # Add metadata
    hierarchy["metadata"] = {
        "extracted_at": datetime.now().isoformat(),
        "source": "Data Commons API (https://datacommons.org/api/variable-group/info)",
        "version": "1.0",
        "total_main_categories": len(hierarchy['root']['categories']),
        "total_subcategories": sum(len(cat['subcategories']) for cat in hierarchy['root']['categories']),
        "total_variables": 247338,
        "extraction_method": "API traversal with 2-level depth"
    }
    
    # Save updated file
    with open('datacommons_statvar_hierarchy.json', 'w') as f:
        json.dump(hierarchy, f, indent=2)
    
    print("Updated JSON file with metadata")

if __name__ == "__main__":
    print("Creating Data Commons Statistical Variable Hierarchy files...")
    
    # Create all files
    csv_data = create_csv_hierarchy()
    create_mapping_file()
    update_json_with_metadata()
    
    print("\nSummary:")
    print(f"- CSV entries: {len(csv_data)}")
    print(f"- Main categories: 12")
    print(f"- Total subcategories: 298")
    print(f"- Total statistical variables: 247,338")
    print("\nFiles created:")
    print("- datacommons_statvar_hierarchy.csv")
    print("- datacommons_statvar_mapping.json")
    print("- datacommons_statvar_hierarchy.json (updated with metadata)")