#!/usr/bin/env python3
"""Tests for coordinator.py - Phase 4 ADK implementation."""

import os
import sys
import tempfile
import csv
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add parent directory for imports
sys.path.append(str(Path(__file__).parent.parent))

from coordinator import execute_workflow, get_workflow_summary


def create_test_csv(file_path: str):
    """Helper to create a test CSV file."""
    test_data = [
        ['Year', 'State', 'Population', 'Employment_Rate'],
        ['2020', 'California', '39538223', '0.92'],
        ['2020', 'Texas', '29145505', '0.89'],
        ['2021', 'California', '39237836', '0.94']
    ]
    
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        for row in test_data:
            writer.writerow(row)


def create_mock_output_files(base_path: str):
    """Helper to create mock output files."""
    files = {
        f"{base_path}.csv": [
            ["observationAbout", "observationDate", "value", "variableMeasured"],
            ["geoId/06", "2020", "39538223", "Count_Population"]
        ],
        f"{base_path}.mcf": ["Node: Count_Population", "typeOf: StatisticalVariable"],
        f"{base_path}.tmcf": ["Node: E:output->E0", "typeOf: StatVarObservation"]
    }
    
    for file_path, content in files.items():
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'w', newline='', encoding='utf-8') as f:
            if file_path.endswith('.csv'):
                writer = csv.writer(f)
                for row in content:
                    writer.writerow(row)
            else:
                f.write('\n'.join(content))


@patch('coordinator.run_statvar_processor')
def test_execute_workflow_success(mock_processor):
    """Test successful end-to-end workflow execution."""
    print("Testing successful workflow execution...")
    
    # Mock successful processor execution
    mock_processor.return_value = {
        "status": "success",
        "exit_code": 0,
        "stdout": "Processing completed",
        "stderr": "",
        "log_path": "/tmp/processor.log"
    }
    
    with tempfile.TemporaryDirectory() as temp_dir:
        input_file = os.path.join(temp_dir, "input.csv")
        output_dir = os.path.join(temp_dir, "output")
        working_dir = os.path.join(temp_dir, "working")
        
        # Create test input file
        create_test_csv(input_file)
        
        # Mock the output files that processor would create
        output_path = os.path.join(output_dir, "output")
        create_mock_output_files(output_path)
        
        result = execute_workflow(input_file, output_dir, working_dir)
        
        assert result["status"] == "success", f"Workflow failed: {result.get('error_message', 'Unknown error')}"
        assert "steps" in result, "Missing workflow steps"
        assert "files_generated" in result, "Missing files_generated"
        
        # Check that all expected steps were executed
        steps = result["steps"]
        expected_steps = [
            "analysis", "pvmap_creation", "pvmap_validation", "pvmap_write",
            "metadata_generation", "metadata_validation", "metadata_write",
            "processor_execution", "output_validation"
        ]
        
        for step in expected_steps:
            assert step in steps, f"Missing workflow step: {step}"
            if step != "processor_execution":  # Mocked step
                assert steps[step].get("status") == "success", f"Step {step} failed: {steps[step]}"
        
        # Check generated files
        files_generated = result["files_generated"]
        expected_files = ["pvmap", "metadata", "output_csv", "output_mcf", "output_tmcf"]
        for file_type in expected_files:
            assert file_type in files_generated, f"Missing file: {file_type}"
            
        # Verify intermediate files were created
        assert os.path.exists(files_generated["pvmap"]), "PVMap file not created"
        assert os.path.exists(files_generated["metadata"]), "Metadata file not created"
        
    print("✓ Successful workflow execution works correctly")


def test_execute_workflow_analysis_failure():
    """Test workflow failure at analysis step."""
    print("Testing workflow failure at analysis step...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        input_file = os.path.join(temp_dir, "nonexistent.csv")  # File doesn't exist
        output_dir = os.path.join(temp_dir, "output")
        
        result = execute_workflow(input_file, output_dir)
        
        assert result["status"] == "error", "Should fail for non-existent file"
        assert result["error_step"] == "analysis", f"Expected analysis failure, got: {result.get('error_step')}"
        assert "error_message" in result, "Missing error message"
        
    print("✓ Analysis failure handling works correctly")


@patch('coordinator.run_statvar_processor')
def test_execute_workflow_processor_failure(mock_processor):
    """Test workflow failure at processor step.""" 
    print("Testing workflow failure at processor step...")
    
    # Mock failed processor execution
    mock_processor.return_value = {
        "status": "error",
        "exit_code": 1,
        "stdout": "Processing started",
        "stderr": "ERROR: Missing column 'Population'",
        "error_message": "Processor execution failed"
    }
    
    with tempfile.TemporaryDirectory() as temp_dir:
        input_file = os.path.join(temp_dir, "input.csv")
        output_dir = os.path.join(temp_dir, "output")
        
        # Create test input file
        create_test_csv(input_file)
        
        result = execute_workflow(input_file, output_dir)
        
        assert result["status"] == "error", "Should fail when processor fails"
        assert result["error_step"] == "processor_execution", f"Expected processor failure, got: {result.get('error_step')}"
        assert "error_analysis" in result["steps"], "Should include error analysis"
        
    print("✓ Processor failure handling works correctly")


@patch('coordinator.run_statvar_processor')  
def test_execute_workflow_output_validation_failure(mock_processor):
    """Test workflow failure at output validation step."""
    print("Testing workflow failure at output validation step...")
    
    # Mock successful processor execution
    mock_processor.return_value = {
        "status": "success",
        "exit_code": 0,
        "stdout": "Processing completed",
        "stderr": ""
    }
    
    with tempfile.TemporaryDirectory() as temp_dir:
        input_file = os.path.join(temp_dir, "input.csv")
        output_dir = os.path.join(temp_dir, "output")
        
        # Create test input file
        create_test_csv(input_file)
        # Don't create output files - this will cause validation failure
        
        result = execute_workflow(input_file, output_dir)
        
        assert result["status"] == "error", "Should fail when output validation fails"
        assert result["error_step"] == "output_validation", f"Expected output validation failure, got: {result.get('error_step')}"
        
    print("✓ Output validation failure handling works correctly")


def test_get_workflow_summary():
    """Test workflow summary generation."""
    print("Testing workflow summary generation...")
    
    # Test successful workflow summary
    successful_result = {
        "status": "success",
        "input_file": "test.csv",
        "steps": {
            "analysis": {"status": "success"},
            "pvmap_creation": {"status": "success"},
            "output_validation": {
                "status": "success",
                "files": {
                    "csv": {"exists": True, "path": "output.csv", "size_bytes": 1024},
                    "mcf": {"exists": True, "path": "output.mcf", "size_bytes": 512}
                }
            }
        },
        "files_generated": {"pvmap": "pvmap.csv", "output_csv": "output.csv"}
    }
    
    summary = get_workflow_summary(successful_result)
    
    assert summary["status"] == "success", f"Summary status incorrect: {summary}"
    assert summary["input_file"] == "test.csv", "Input file not in summary"
    assert summary["total_steps"] == 3, f"Expected 3 steps, got {summary['total_steps']}"
    assert "output_files" in summary, "Missing output files in summary"
    assert len(summary["files_generated"]) == 2, "Files generated count incorrect"
    
    # Test failed workflow summary
    failed_result = {
        "status": "error",
        "input_file": "test.csv", 
        "error_step": "processor_execution",
        "error_message": "Processing failed",
        "steps": {
            "analysis": {"status": "success"},
            "error_analysis": {
                "error_category": "missing_column",
                "suggestions": ["Check PVMap mappings"]
            }
        }
    }
    
    failed_summary = get_workflow_summary(failed_result)
    
    assert failed_summary["status"] == "error", "Failed summary status incorrect"
    assert failed_summary["error_step"] == "processor_execution", "Error step not in summary"
    assert failed_summary["error_message"] == "Processing failed", "Error message not in summary"
    assert "error_category" in failed_summary, "Error category not in summary"
    assert len(failed_summary["suggestions"]) > 0, "Suggestions not in summary"
    
    print("✓ Workflow summary generation works correctly")


def test_workflow_error_handling():
    """Test workflow error handling for edge cases."""
    print("Testing workflow error handling...")
    
    # Test with invalid input parameters
    result = execute_workflow("", "")
    assert result["status"] == "error", "Should fail for empty inputs"
    
    # Test summary with malformed result
    malformed_result = {"invalid": "data"}
    summary = get_workflow_summary(malformed_result)
    assert "status" in summary, "Summary should handle malformed input"
    
    print("✓ Workflow error handling works correctly")


def test_workflow_directory_creation():
    """Test that workflow creates necessary directories."""
    print("Testing workflow directory creation...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        input_file = os.path.join(temp_dir, "input.csv")
        output_dir = os.path.join(temp_dir, "nonexistent_output")
        working_dir = os.path.join(temp_dir, "nonexistent_working")
        
        # Create test input file
        create_test_csv(input_file)
        
        # Directories don't exist yet
        assert not os.path.exists(output_dir), "Output directory should not exist yet"
        assert not os.path.exists(working_dir), "Working directory should not exist yet"
        
        # Execute workflow (will fail at processor step, but directories should be created)
        result = execute_workflow(input_file, output_dir, working_dir)
        
        # Check directories were created
        assert os.path.exists(output_dir), "Output directory not created"
        assert os.path.exists(working_dir), "Working directory not created"
        
    print("✓ Directory creation works correctly")


if __name__ == "__main__":
    print("=== Coordinator Tests (Phase 4) ===")
    
    try:
        test_execute_workflow_success()
        test_execute_workflow_analysis_failure()
        test_execute_workflow_processor_failure()
        test_execute_workflow_output_validation_failure()
        test_get_workflow_summary()
        test_workflow_error_handling()
        test_workflow_directory_creation()
        print("\n✅ All coordinator tests passed!")
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)