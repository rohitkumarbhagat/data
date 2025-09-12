#!/usr/bin/env python3
"""Tests for processor_runner.py - Phase 4 ADK implementation."""

import os
import sys
import tempfile
import csv
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add parent directory for imports
sys.path.append(str(Path(__file__).parent.parent))

from processor_runner import (
    run_statvar_processor,
    validate_processor_output,
    parse_processor_errors
)


def create_test_output_files(base_path: str):
    """Helper to create test output files."""
    files = {
        f"{base_path}.csv": [
            ["observationAbout", "observationDate", "value", "variableMeasured"],
            ["geoId/06", "2020", "39538223", "Count_Population"],
            ["geoId/48", "2020", "29145505", "Count_Population"]
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


@patch('subprocess.run')
def test_run_statvar_processor_success(mock_subprocess):
    """Test successful processor execution."""
    print("Testing successful processor execution...")
    
    # Mock successful subprocess execution
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "Processing completed successfully"
    mock_result.stderr = ""
    mock_subprocess.return_value = mock_result
    
    with tempfile.TemporaryDirectory() as temp_dir:
        config = {
            "input_data": "test_input.csv",
            "pv_map": "test_pvmap.csv",
            "metadata": "test_metadata.csv",
            "output_path": os.path.join(temp_dir, "output"),
            "working_dir": temp_dir
        }
        
        result = run_statvar_processor(config)
        
        assert result["status"] == "success", f"Processor run failed: {result}"
        assert result["exit_code"] == 0, f"Expected exit code 0, got {result['exit_code']}"
        assert "stdout" in result, "Missing stdout in result"
        assert "stderr" in result, "Missing stderr in result"
        assert "command" in result, "Missing command in result"
        assert "log_path" in result, "Missing log_path in result"
        
        # Check that log file was created
        assert os.path.exists(result["log_path"]), "Log file not created"
        
        # Verify subprocess was called with correct arguments
        mock_subprocess.assert_called_once()
        call_args = mock_subprocess.call_args[0][0]  # First positional argument (command)
        command_str = ' '.join(call_args)
        assert "stat_var_processor.py" in command_str, "Processor script not in command"
        assert f"--input_data={config['input_data']}" in call_args, "Input data not in command"
        assert f"--pv_map={config['pv_map']}" in call_args, "PV map not in command"
        
    print("✓ Successful processor execution works correctly")


@patch('subprocess.run')
def test_run_statvar_processor_failure(mock_subprocess):
    """Test processor execution failure."""
    print("Testing processor execution failure...")
    
    # Mock failed subprocess execution
    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stdout = "Processing started"
    mock_result.stderr = "ERROR: File not found: test_input.csv"
    mock_subprocess.return_value = mock_result
    
    with tempfile.TemporaryDirectory() as temp_dir:
        config = {
            "input_data": "nonexistent.csv",
            "pv_map": "test_pvmap.csv", 
            "metadata": "test_metadata.csv",
            "output_path": os.path.join(temp_dir, "output"),
            "working_dir": temp_dir
        }
        
        result = run_statvar_processor(config)
        
        assert result["status"] == "error", f"Expected error status, got: {result['status']}"
        assert result["exit_code"] == 1, f"Expected exit code 1, got {result['exit_code']}"
        assert "File not found" in result["stderr"], "Error message not captured"
        
    print("✓ Processor execution failure handling works correctly")


def test_run_statvar_processor_missing_params():
    """Test processor execution with missing parameters."""
    print("Testing processor execution with missing parameters...")
    
    # Test with missing required parameter
    incomplete_config = {
        "input_data": "test.csv",
        "pv_map": "pvmap.csv"
        # Missing metadata and output_path
    }
    
    result = run_statvar_processor(incomplete_config)
    
    assert result["status"] == "error", "Should fail with missing parameters"
    assert "Missing required parameter" in result["error_message"], "Should indicate missing parameter"
    
    print("✓ Missing parameter handling works correctly")


def test_validate_processor_output_success():
    """Test output validation with valid files."""
    print("Testing output validation with valid files...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        base_path = os.path.join(temp_dir, "output")
        create_test_output_files(base_path)
        
        result = validate_processor_output(base_path)
        
        assert result["status"] == "success", f"Validation failed: {result}"
        assert result["valid"] == True, "Valid output marked as invalid"
        assert len(result["issues"]) == 0, f"Valid output has issues: {result['issues']}"
        
        # Check file information
        assert "files" in result, "Missing files information"
        files = result["files"]
        
        for file_type in ["csv", "mcf", "tmcf"]:
            assert file_type in files, f"Missing {file_type} file info"
            assert files[file_type]["exists"] == True, f"{file_type} file not detected"
            assert files[file_type]["size_bytes"] > 0, f"{file_type} file size not detected"
            
        # Check CSV-specific validation
        csv_info = files["csv"]
        assert "row_count" in csv_info, "CSV row count not detected"
        assert "columns" in csv_info, "CSV columns not detected"
        assert csv_info["row_count"] == 2, f"Expected 2 data rows, got {csv_info['row_count']}"
        
    print("✓ Output validation with valid files works correctly")


def test_validate_processor_output_missing_files():
    """Test output validation with missing files."""
    print("Testing output validation with missing files...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        base_path = os.path.join(temp_dir, "nonexistent")
        
        result = validate_processor_output(base_path)
        
        assert result["status"] == "success", f"Validation failed: {result}"
        assert result["valid"] == False, "Missing files marked as valid"
        assert len(result["issues"]) > 0, "Missing files have no issues"
        
        # Check that all files are marked as missing
        files = result["files"]
        for file_type in ["csv", "mcf", "tmcf"]:
            assert files[file_type]["exists"] == False, f"{file_type} should be missing"
            
        # Check that issues mention missing files
        issues_text = ' '.join(result["issues"])
        assert "Missing" in issues_text, "Should report missing files"
        
    print("✓ Output validation with missing files works correctly")


def test_validate_processor_output_empty_files():
    """Test output validation with empty files."""
    print("Testing output validation with empty files...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        base_path = os.path.join(temp_dir, "output")
        
        # Create empty files
        for ext in [".csv", ".mcf", ".tmcf"]:
            file_path = f"{base_path}{ext}"
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            Path(file_path).touch()  # Create empty file
            
        result = validate_processor_output(base_path)
        
        assert result["status"] == "success", f"Validation failed: {result}"
        assert result["valid"] == False, "Empty files marked as valid"
        assert len(result["issues"]) > 0, "Empty files have no issues"
        
        # Check that issues mention empty files
        issues_text = ' '.join(result["issues"])
        assert "empty" in issues_text.lower(), "Should report empty files"
        
    print("✓ Output validation with empty files works correctly")


def test_parse_processor_errors():
    """Test processor error parsing and categorization."""
    print("Testing processor error parsing...")
    
    # Test successful execution (no errors)
    result = parse_processor_errors("", 0)
    assert result["status"] == "success", "Should succeed for exit code 0"
    assert result["error_category"] is None, "Should have no error category for success"
    
    # Test file not found error
    stderr_file_not_found = "FileNotFoundError: [Errno 2] No such file or directory: 'missing.csv'"
    result = parse_processor_errors(stderr_file_not_found, 1)
    assert result["error_category"] == "file_not_found", f"Expected file_not_found, got {result['error_category']}"
    assert len(result["suggestions"]) > 0, "Should provide suggestions"
    
    # Test missing column error
    stderr_missing_column = "KeyError: 'Population' not found in columns"
    result = parse_processor_errors(stderr_missing_column, 1)
    assert result["error_category"] == "missing_column", f"Expected missing_column, got {result['error_category']}"
    
    # Test data format error
    stderr_format_error = "ValueError: invalid literal for int() with base 10: 'N/A'"
    result = parse_processor_errors(stderr_format_error, 1)
    assert result["error_category"] == "data_format_error", f"Expected data_format_error, got {result['error_category']}"
    
    # Test permission error
    stderr_permission = "PermissionError: [Errno 13] Permission denied: 'output.csv'"
    result = parse_processor_errors(stderr_permission, 1)
    assert result["error_category"] == "permission_error", f"Expected permission_error, got {result['error_category']}"
    
    # Test unknown error
    stderr_unknown = "Some random error message"
    result = parse_processor_errors(stderr_unknown, 1)
    assert result["error_category"] == "unknown", f"Expected unknown, got {result['error_category']}"
    
    print("✓ Processor error parsing works correctly")


def test_error_handling():
    """Test error handling for edge cases."""
    print("Testing error handling...")
    
    # Test output validation with invalid path
    result = validate_processor_output("")
    assert result["status"] == "success", "Should handle empty path gracefully"
    
    # Test error parsing with None inputs
    result = parse_processor_errors(None, None)
    assert result["status"] == "error", "Should handle None inputs"
    
    print("✓ Error handling works correctly")


if __name__ == "__main__":
    print("=== Processor Runner Tests (Phase 4) ===")
    
    try:
        test_run_statvar_processor_success()
        test_run_statvar_processor_failure()
        test_run_statvar_processor_missing_params()
        test_validate_processor_output_success()
        test_validate_processor_output_missing_files()
        test_validate_processor_output_empty_files()
        test_parse_processor_errors()
        test_error_handling()
        print("\n✅ All processor runner tests passed!")
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)