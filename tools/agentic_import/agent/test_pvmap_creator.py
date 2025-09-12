#!/usr/bin/env python3
"""Minimal test for Phase 3 PVMap Creator functionality."""

import os
import sys
import tempfile

# Add current directory for imports
sys.path.append(os.path.dirname(__file__))

from pvmap_creator import create_pv_mappings, write_pvmap_csv


def test_basic_pvmap_creation():
    """Test core PVMap creation functionality."""
    print("Testing basic PVMap creation...")
    
    # Sample analysis result (what Phase 2 would produce)
    analysis_input = {
        "status": "success",
        "column_analysis": {
            "Year": {"type": "year", "dc_suggestion": "observationDate"},
            "State": {"type": "categorical", "dc_suggestion": "geoId"},
            "Employment_Count": {"type": "numeric", "dc_suggestion": "measuredProperty"}
        }
    }
    
    # Test mapping creation
    result = create_pv_mappings(analysis_input)
    
    assert result["status"] == "success", f"Mapping creation failed: {result.get('error_message')}"
    assert "mappings" in result, "No mappings returned"
    assert len(result["mappings"]) >= 3, f"Expected at least 3 mappings, got {len(result['mappings'])}"
    
    mappings = result["mappings"]
    
    # Check for required mappings
    properties = [m["property"] for m in mappings]
    assert "observationDate" in properties, "Missing observationDate mapping"
    assert "measuredProperty" in properties, "Missing measuredProperty mapping"
    assert "populationType" in properties, "Missing populationType mapping"
    
    print(f"✓ Created {len(mappings)} mappings successfully")
    return mappings


def test_csv_output():
    """Test CSV file generation."""
    print("Testing CSV output...")
    
    sample_mappings = [
        {"input": "Year", "property": "observationDate", "value": "#Format:{$col|YYYY}"},
        {"input": "Employment_Count", "property": "measuredProperty", "value": "Count_EmploymentCount"},
        {"input": "*", "property": "populationType", "value": "Person"}
    ]
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as tmp_file:
        output_path = tmp_file.name
    
    result = write_pvmap_csv(sample_mappings, output_path)
    
    assert result["status"] == "success", f"CSV writing failed: {result.get('error_message')}"
    assert os.path.exists(output_path), "Output file not created"
    assert result["count"] == 3, f"Expected 3 mappings written, got {result['count']}"
    
    # Verify file content
    with open(output_path, 'r') as f:
        lines = f.readlines()
        assert len(lines) == 4, f"Expected 4 lines (header + 3 data), got {len(lines)}"  # header + 3 rows
        assert "input,property,value" in lines[0], "Missing or incorrect header"
    
    os.unlink(output_path)
    print("✓ CSV output generated successfully")


if __name__ == "__main__":
    print("=== Phase 3 PVMap Creator Tests ===")
    
    try:
        mappings = test_basic_pvmap_creation()
        test_csv_output()
        print("\n✓ All tests passed!")
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        sys.exit(1)