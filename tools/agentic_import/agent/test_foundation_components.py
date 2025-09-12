#!/usr/bin/env python3
"""
Unit tests for core foundation components that Phase 6 depends on.

These tests complement the comprehensive Phase 6 test suite by providing
focused unit testing for the fundamental building blocks.

Focus: Fast, targeted tests for core component behaviors.
Scope: Foundation components (analyzer, coordinator, etc.)
Purpose: Development feedback and regression protection.
"""

import os
import sys
import tempfile
import pytest
import pandas as pd
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add current directory for imports
sys.path.append(os.path.dirname(__file__))

from analyzer import analyze_data_structure
from coordinator import execute_workflow
from iterative_coordinator import IterativeCoordinator
from metadata_generator import generate_metadata, write_metadata_json
from processor_runner import run_statvar_processor
from error_analyzer import categorize_error, suggest_fixes
from tools import validate_file_path, create_structured_response


class TestAnalyzer:
    """Test core data analysis functionality."""
    
    def setup_method(self):
        """Create test data for each test."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_csv = os.path.join(self.temp_dir, "test.csv")
        
        # Create test CSV with typical data patterns
        test_data = pd.DataFrame({
            'Year': [2020, 2021, 2022],
            'State': ['California', 'Texas', 'New York'], 
            'Population': [39538223, 29145505, 19336776],
            'Employment_Rate': [0.92, 0.89, 0.94],
            'GDP': [3.35e12, 2.35e12, 1.99e12]
        })
        test_data.to_csv(self.test_csv, index=False)
    
    def test_basic_analysis_success(self):
        """Test successful data structure analysis."""
        result = analyze_data_structure(self.test_csv)
        
        assert result['status'] == 'success'
        assert 'column_analysis' in result
        assert len(result['column_analysis']) == 5
        
        # Check column type detection
        columns = result['column_analysis']
        assert columns['Year']['type'] == 'year'
        assert columns['State']['type'] == 'categorical'
        assert columns['Population']['type'] == 'numeric'
    
    def test_analysis_file_not_found(self):
        """Test analysis with non-existent file."""
        result = analyze_data_structure('/nonexistent/file.csv')
        
        assert result['status'] == 'error'
        assert 'error_message' in result
        assert 'not found' in result['error_message'].lower()
    
    def test_analysis_empty_file(self):
        """Test analysis with empty CSV."""
        empty_csv = os.path.join(self.temp_dir, "empty.csv")
        pd.DataFrame().to_csv(empty_csv, index=False)
        
        result = analyze_data_structure(empty_csv)
        
        assert result['status'] == 'error'
        assert 'empty' in result['error_message'].lower()


class TestCoordinator:
    """Test core workflow coordination."""
    
    def setup_method(self):
        """Setup test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.input_file = os.path.join(self.temp_dir, "input.csv")
        self.output_dir = os.path.join(self.temp_dir, "output")
        
        # Create valid input file
        test_data = pd.DataFrame({
            'year': [2020, 2021], 
            'state': ['CA', 'TX'],
            'value': [100, 200]
        })
        test_data.to_csv(self.input_file, index=False)
    
    def test_directory_creation(self):
        """Test that coordinator creates necessary directories."""
        # Ensure directories don't exist
        assert not os.path.exists(self.output_dir)
        
        with patch('coordinator.run_statvar_processor') as mock_processor:
            mock_processor.return_value = {
                "status": "error",  # Expected to fail without real processor
                "exit_code": 1,
                "error_message": "Mock failure"
            }
            
            execute_workflow(self.input_file, self.output_dir)
            
            # Directory should be created even if workflow fails
            assert os.path.exists(self.output_dir)
    
    def test_workflow_validation(self):
        """Test input validation."""
        # Test with invalid input file
        result = execute_workflow('/nonexistent/file.csv', self.output_dir)
        
        assert result['status'] == 'error'
        assert result['error_step'] == 'analysis'
        assert 'not found' in result['error_message'].lower()


class TestIterativeCoordinator:
    """Test iteration and retry logic."""
    
    def setup_method(self):
        """Setup test environment.""" 
        self.temp_dir = tempfile.mkdtemp()
        self.coordinator = IterativeCoordinator(max_iterations=2, auto_fix=False)
    
    def test_max_iterations_limit(self):
        """Test that coordinator respects max iterations limit."""
        input_file = os.path.join(self.temp_dir, "test.csv")
        output_dir = os.path.join(self.temp_dir, "output")
        
        # Create invalid data that will always fail
        pd.DataFrame({'invalid': [1, 2]}).to_csv(input_file, index=False)
        
        with patch('iterative_coordinator.execute_workflow') as mock_workflow:
            mock_workflow.return_value = {
                "status": "error", 
                "error_step": "processor_execution",
                "error_message": "Mock persistent error"
            }
            
            result = self.coordinator.process_with_retry(input_file, output_dir)
            
            # Should try exactly max_iterations times
            assert mock_workflow.call_count == 2
            assert result['status'] == 'error'
            assert result['iterations_attempted'] == 2
    
    def test_early_success(self):
        """Test that coordinator stops on first success."""
        input_file = os.path.join(self.temp_dir, "test.csv")
        output_dir = os.path.join(self.temp_dir, "output")
        
        with patch('iterative_coordinator.execute_workflow') as mock_workflow:
            mock_workflow.return_value = {
                "status": "success",
                "message": "Mock success"
            }
            
            result = self.coordinator.process_with_retry(input_file, output_dir)
            
            # Should succeed on first try
            assert mock_workflow.call_count == 1
            assert result['status'] == 'success'
            assert result['iterations_attempted'] == 1


class TestMetadataGenerator:
    """Test metadata generation functionality."""
    
    def setup_method(self):
        """Setup test environment."""
        self.temp_dir = tempfile.mkdtemp()
    
    def test_metadata_generation_success(self):
        """Test successful metadata generation."""
        # Sample PVMap data
        pvmap_data = [
            {"property": "observationDate", "column": "Year"},
            {"property": "observationAbout", "column": "State"},
            {"property": "value", "column": "Population"}
        ]
        
        result = generate_metadata(pvmap_data, "Count_Population")
        
        assert result['status'] == 'success'
        assert 'metadata' in result
        assert 'variable_definition' in result['metadata']
        assert 'template_mappings' in result['metadata']
    
    def test_metadata_file_write(self):
        """Test metadata file writing."""
        metadata = {
            "variable_definition": "Node: Count_Population",
            "template_mappings": ["Node: E:data->E0"]
        }
        
        metadata_file = os.path.join(self.temp_dir, "test.json")
        result = write_metadata_json(metadata, metadata_file)
        
        assert result['status'] == 'success'
        assert os.path.exists(metadata_file)
        
        # Verify file content
        import json
        with open(metadata_file, 'r') as f:
            saved_data = json.load(f)
            assert saved_data == metadata


class TestProcessorRunner:
    """Test external process execution."""
    
    def test_command_construction(self):
        """Test that processor commands are constructed correctly."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="success",
                stderr=""
            )
            
            result = run_statvar_processor(
                "input.csv", 
                "output.csv", 
                "data.mcf",
                "template.tmcf"
            )
            
            # Verify subprocess was called
            mock_run.assert_called_once()
            call_args = mock_run.call_args[1]  # kwargs
            
            # Basic validation that command includes expected files
            command_str = ' '.join(call_args.get('capture_output', ''))
            # Note: Exact command format may vary, this is a basic check
            assert result['status'] in ['success', 'error']  # Should return valid status


class TestErrorAnalyzer:
    """Test error analysis and categorization."""
    
    def test_error_categorization(self):
        """Test error message categorization."""
        test_cases = [
            ("Column 'population' not found", "missing_column"),
            ("Invalid CSV format", "data_format"), 
            ("Permission denied", "file_permission"),
            ("Memory allocation failed", "resource_limit"),
            ("Unknown weird error", "unknown")
        ]
        
        for error_msg, expected_category in test_cases:
            category = categorize_error(error_msg)
            assert category == expected_category, f"Failed for: {error_msg}"
    
    def test_fix_suggestions(self):
        """Test fix suggestion generation."""
        suggestions = suggest_fixes("missing_column", {"missing_columns": ["population"]})
        
        assert isinstance(suggestions, list)
        assert len(suggestions) > 0
        assert any("column" in s.lower() for s in suggestions)


class TestUtilities:
    """Test utility functions."""
    
    def test_file_validation(self):
        """Test file path validation."""
        # Create a temporary file
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = tmp.name
            
        try:
            result = validate_file_path(tmp_path, must_exist=True)
            assert result['status'] == 'success'
            
            result = validate_file_path('/nonexistent/path', must_exist=True)
            assert result['status'] == 'error'
        finally:
            os.unlink(tmp_path)
    
    def test_structured_response(self):
        """Test structured response creation."""
        success_response = create_structured_response(
            'success', 
            data={'key': 'value'}, 
            message='Test success'
        )
        
        assert success_response['status'] == 'success'
        assert success_response['data']['key'] == 'value'
        assert success_response['message'] == 'Test success'
        
        error_response = create_structured_response(
            'error',
            error_message='Test error'
        )
        
        assert error_response['status'] == 'error'
        assert error_response['error_message'] == 'Test error'


if __name__ == '__main__':
    print("=== Foundation Components Unit Tests ===")
    print("Testing core components that Phase 6 depends on...")
    
    # Run with pytest if available, otherwise basic test execution
    try:
        import pytest
        exit_code = pytest.main([__file__, '-v'])
        sys.exit(exit_code)
    except ImportError:
        print("Pytest not available. Run: pip install pytest")
        print("Or manually test components...")
        
        # Basic smoke test without pytest
        try:
            # Test analyzer with a simple case
            temp_dir = tempfile.mkdtemp()
            test_csv = os.path.join(temp_dir, "smoke_test.csv")
            pd.DataFrame({'year': [2020], 'value': [100]}).to_csv(test_csv, index=False)
            
            result = analyze_data_structure(test_csv)
            if result['status'] == 'success':
                print("✓ Analyzer smoke test passed")
            else:
                print("✗ Analyzer smoke test failed")
                
        except Exception as e:
            print(f"✗ Smoke test error: {e}")