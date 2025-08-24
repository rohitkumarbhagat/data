# Data Commons Statistical Variable Hierarchy

This directory contains a complete extraction of the Data Commons statistical variable hierarchy, extracted directly from the Data Commons API.

## Files

### Core Data Files

- **`datacommons_statvar_hierarchy.json`** - Complete hierarchical data in JSON format with metadata
- **`datacommons_statvar_hierarchy.csv`** - Tabular format suitable for database import (311 entries)
- **`datacommons_statvar_hierarchy.txt`** - Human-readable text format with tree structure
- **`datacommons_statvar_mapping.json`** - Mapping file to connect categories with import types

### Scripts

- **`fetch_statvar_hierarchy.py`** - Original extraction script using Data Commons API
- **`create_csv_hierarchy.py`** - Script to generate CSV and mapping files from JSON data

## Hierarchy Overview

The Data Commons statistical variable hierarchy contains:

- **12 Main Categories** (Level 1)
- **298 Subcategories** (Level 2)
- **247,338 Total Statistical Variables**

### Main Categories

| Category | Variables | Key Subcategories |
|----------|-----------|-------------------|
| Agriculture | 441 | Person by Economic Sector, Farm, Farm Inventory |
| Demographics | 50,806 | Person by Age, Person by Gender, Person by Race |
| Economy | 122,095 | Employment and Business, Economic Activity, Currency |
| Education | 53,236 | Student, Educational Attainment, School |
| Energy | 9,779 | Electricity, Energy Consumption, Energy Efficiency |
| Environment | 3,647 | Air Quality, Climate, Water |
| Health | 51,805 | Disease, Medical Condition, Health Behavior |
| Housing | 4,906 | Housing Unit, Housing Cost, Housing Quality |
| Crime | 8,637 | Hate Crime Incidents, Prisoner Population |
| About Data Commons | 15 | Statistical Variable |
| 12 UN Data Thematic Areas | 21,471 | Poverty, Health, Education, Human Rights |
| Sustainable Development Goals | 4,625 | All 17 SDGs with detailed subcategories |

## Usage

### For VertexDB RAG Application

These files complement the `statvar_imports_config.json` by providing:

1. **Category Context**: Understanding which statistical variable categories exist
2. **Import Mapping**: Connecting data imports to relevant statistical variable categories
3. **Search Enhancement**: Improving RAG queries by understanding the hierarchy

### CSV Structure

The CSV file contains the following columns:
- `level`: Hierarchy level (0=Root, 1=Main Category, 2=Subcategory)
- `category_id`: Data Commons identifier (e.g., "dc/g/Agriculture")
- `category_name`: Human-readable name
- `parent_id`: Parent category identifier
- `parent_name`: Parent category name
- `variable_count`: Number of statistical variables in this category
- `path`: Full hierarchical path (e.g., "Root > Demographics > Person by Age")

### API Source

Data extracted from: `https://datacommons.org/api/variable-group/info`

**Extraction Date**: 2025-08-24  
**API Method**: Recursive traversal starting from `dc/g/Root`

## Integration with statvar_imports_config.json

The mapping file (`datacommons_statvar_mapping.json`) provides suggested connections between:
- Data import types (from statvar_imports_config.json)
- Statistical variable categories (from this hierarchy)

This enables the RAG application to:
- Recommend relevant imports based on statistical variable queries
- Understand context when users ask about specific data categories
- Provide comprehensive responses about available data and import patterns

## File Formats

- **JSON**: Structured data with metadata, suitable for programmatic access
- **CSV**: Flat table format, ideal for database imports and analysis
- **TXT**: Human-readable tree format for documentation and reference