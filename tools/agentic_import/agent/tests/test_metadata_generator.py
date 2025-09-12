#!/usr/bin/env python3
"""Tests for metadata_generator.py - Phase 4 ADK implementation."""

import os
import sys
import tempfile
import csv
import pandas as pd
from pathlib import Path

# Add parent directory for imports
sys.path.append(str(Path(__file__).parent.parent))

from metadata_generator import (
    detect_file_structure,
    generate_metadata_config,
    write_metadata_csv,
    validate_metadata_config
)


def create_test_csv(content: list, file_path: str):
    """Helper to create test CSV files."""
    with open(file_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        for row in content:
            writer.writerow(row)


def test_detect_file_structure():
    """Test CSV file structure detection."""
    print("Testing file structure detection...")
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as tmp_file:
        test_data = [
            ['Year', 'State', 'Population', 'Employment_Rate'],
            ['2020', 'California', '39538223', '0.92'],
            ['2020', 'Texas', '29145505', '0.89'],
            ['2021', 'California', '39237836', '0.94']
        ]
        
        create_test_csv(test_data, tmp_file.name)
        
        result = detect_file_structure(tmp_file.name)
        
        assert result["status"] == "success", f"Structure detection failed: {result}"
        assert result["header_rows"] == 1, f"Expected 1 header row, got {result['header_rows']}"
        assert result["total_rows"] == 3, f"Expected 3 data rows, got {result['total_rows']}"
        assert result["total_columns"] == 4, f"Expected 4 columns, got {result['total_columns']}"
        assert result["mapped_rows"] == 2, f"Expected 2 mapped rows, got {result['mapped_rows']}"
        
        os.unlink(tmp_file.name)
        print("✓ File structure detection works correctly")


def test_generate_metadata_config():
    """Test metadata configuration generation."""
    print("Testing metadata config generation...")
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as tmp_file:
        test_data = [
            ['Year', 'Location', 'Population'],
            ['2020', 'California', '39538223'],
            ['2020', 'Texas', '29145505']
        ]
        
        create_test_csv(test_data, tmp_file.name)
        
        # Test without analysis result
        result = generate_metadata_config(tmp_file.name)
        
        assert result["status"] == "success", f"Config generation failed: {result}"
        assert "config" in result, "No config returned"
        
        config = result["config"]
        assert "output_columns" in config, "Missing output_columns"
        assert "header_rows" in config, "Missing header_rows"
        assert "mapped_rows" in config, "Missing mapped_rows"
        
        # Test with analysis result (simulated)
        analysis_result = {
            "status": "success",
            "column_analysis": {
                "Year": {"type": "year", "dc_suggestion": "observationDate"},
                "Location": {"type": "categorical", "dc_suggestion": "geoId"},
                "Population": {"type": "numeric", "dc_suggestion": "measuredProperty"}
            }
        }
        
        result_with_analysis = generate_metadata_config(tmp_file.name, analysis_result)
        
        assert result_with_analysis["status"] == "success", f"Config with analysis failed: {result_with_analysis}"
        config_with_analysis = result_with_analysis["config"]
        assert "places_within" in config_with_analysis, "Should add places_within for location data"
        
        os.unlink(tmp_file.name)
        print("✓ Metadata config generation works correctly")


def test_write_metadata_csv():
    """Test writing metadata to CSV file."""
    print("Testing metadata CSV writing...")
    
    test_config = {
        "header_rows": 1,
        "mapped_rows": 100,
        "mapped_columns": 4,
        "output_columns": "observationAbout,observationDate,value,variableMeasured",
        "places_within": "country/USA"
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as tmp_file:
        output_path = tmp_file.name
    
    result = write_metadata_csv(test_config, output_path)
    
    assert result["status"] == "success", f"CSV writing failed: {result}"
    assert os.path.exists(output_path), "Output file not created"
    assert result["parameters"] == len(test_config), f"Expected {len(test_config)} parameters, got {result['parameters']}"
    
    # Verify file content
    with open(output_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        rows = list(reader)
        
        assert len(rows) == len(test_config) + 1, f"Expected {len(test_config) + 1} rows (header + data), got {len(rows)}"
        assert rows[0] == ['parameter', 'value'], f"Incorrect header: {rows[0]}"
        
        # Check that all config parameters are present
        written_params = {row[0] for row in rows[1:]}
        expected_params = set(test_config.keys())
        assert written_params == expected_params, f"Parameter mismatch: {written_params} vs {expected_params}"
    
    os.unlink(output_path)
    print("✓ Metadata CSV writing works correctly")


def test_validate_metadata_config():
    """Test metadata configuration validation."""
    print("Testing metadata config validation...")
    
    # Test valid configuration
    valid_config = {
        "output_columns": "observationAbout,observationDate,value,variableMeasured",
        "header_rows": 1,
        "mapped_rows": 100
    }
    
    result = validate_metadata_config(valid_config)
    
    assert result["status"] == "success", f"Validation failed: {result}"
    assert result["valid"] == True, "Valid config marked as invalid"
    assert len(result["issues"]) == 0, f"Valid config has issues: {result['issues']}"
    
    # Test invalid configuration (missing required parameter)
    invalid_config = {
        "header_rows": 1,
        "mapped_rows": 100
        # Missing output_columns
    }
    
    result_invalid = validate_metadata_config(invalid_config)
    
    assert result_invalid["status"] == "success", f"Validation failed: {result_invalid}"
    assert result_invalid["valid"] == False, "Invalid config marked as valid"
    assert len(result_invalid["issues"]) > 0, "Invalid config has no issues"
    assert "output_columns" in str(result_invalid["issues"]), "Should complain about missing output_columns"
    
    # Test invalid output_columns format
    bad_format_config = {
        "output_columns": "col1,col2"  # Too few columns
    }
    
    result_bad_format = validate_metadata_config(bad_format_config)
    
    assert result_bad_format["status"] == "success", f"Validation failed: {result_bad_format}"
    assert result_bad_format["valid"] == False, "Bad format config marked as valid"
    
    print("✓ Metadata config validation works correctly")


def test_error_handling():
    """Test error handling for edge cases."""
    print("Testing error handling...")
    
    # Test with non-existent file
    result = detect_file_structure("nonexistent_file.csv")
    assert result["status"] == "error", "Should fail for non-existent file"
    assert "error_message" in result, "Should include error message"
    
    # Test metadata generation with invalid file
    result = generate_metadata_config("nonexistent_file.csv")
    assert result["status"] == "error", "Should fail for non-existent file"
    
    # Test writing to invalid path
    result = write_metadata_csv({"test": "value"}, "/invalid/path/file.csv")
    assert result["status"] == "error", "Should fail for invalid path"
    
    print("✓ Error handling works correctly")


if __name__ == "__main__":
    print("=== Metadata Generator Tests (Phase 4) ===")
    
    try:
        test_detect_file_structure()
        test_generate_metadata_config()
        test_write_metadata_csv()
        test_validate_metadata_config()
        test_error_handling()
        print("\n✅ All metadata generator tests passed!")
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)