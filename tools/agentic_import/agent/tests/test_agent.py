#!/usr/bin/env python3
"""
Unit tests for ADK agent Phase 1 implementation.

Tests the essential CSV reading functionality and core utilities.
"""

import os
import tempfile
import pytest

from ..simple_agent import read_csv_sample
from ..tools import (
    create_structured_response,
    validate_file_path,
    validate_csv_structure
)


class TestCSVReading:
    """Test core CSV reading functionality."""
    
    @pytest.fixture
    def sample_csv_path(self):
        """Path to the test CSV file."""
        return os.path.join(os.path.dirname(__file__), '..', 'testdata', 'sample.csv')
    
    def test_read_csv_success(self, sample_csv_path):
        """Test successful CSV reading."""
        result = read_csv_sample(sample_csv_path, rows=5)
        
        assert result['status'] == 'success'
        assert 'columns' in result
        assert 'sample' in result
        assert 'shape' in result
        
        # Check expected structure
        expected_columns = ['Year', 'Location', 'Population', 'Employment_Rate', 'Median_Income', 'Education_Level']
        assert result['columns'] == expected_columns
        assert len(result['sample']) > 0
        assert result['shape']['cols'] == len(expected_columns)
    
    def test_read_csv_file_not_found(self):
        """Test CSV reading with non-existent file."""
        result = read_csv_sample('/path/that/does/not/exist.csv')
        
        assert result['status'] == 'error'
        assert 'error_message' in result
    
    def test_read_csv_empty_path(self):
        """Test CSV reading with empty path."""
        result = read_csv_sample('')
        
        assert result['status'] == 'error'
        assert 'error_message' in result


class TestUtilities:
    """Test essential utility functions."""
    
    def test_create_structured_response_success(self):
        """Test structured response creation for success."""
        result = create_structured_response(
            'success', 
            data={'key': 'value'}, 
            message='Operation successful'
        )
        
        assert result['status'] == 'success'
        assert result['data'] == {'key': 'value'}
        assert result['message'] == 'Operation successful'
    
    def test_create_structured_response_error(self):
        """Test structured response creation for errors."""
        result = create_structured_response(
            'error',
            error_message='Something went wrong'
        )
        
        assert result['status'] == 'error'
        assert result['error_message'] == 'Something went wrong'
    
    def test_validate_file_path_success(self):
        """Test file path validation with existing file."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = tmp.name
        
        try:
            result = validate_file_path(tmp_path, must_exist=True)
            assert result['status'] == 'success'
            assert result['data']['exists'] == True
        finally:
            os.unlink(tmp_path)
    
    def test_validate_file_path_not_exist(self):
        """Test file path validation for non-existent file."""
        result = validate_file_path('/path/that/does/not/exist', must_exist=True)
        assert result['status'] == 'error'


class TestCSVValidation:
    """Test CSV validation functionality."""
    
    @pytest.fixture
    def sample_csv_path(self):
        """Path to the test CSV file."""
        return os.path.join(os.path.dirname(__file__), '..', 'testdata', 'sample.csv')
    
    def test_validate_csv_structure_success(self, sample_csv_path):
        """Test successful CSV validation."""
        result = validate_csv_structure(sample_csv_path)
        
        assert result['status'] == 'success'
        assert result['data']['valid'] == True
        assert result['data']['column_count'] == 6
        assert len(result['data']['issues']) == 0
    
    def test_validate_csv_structure_required_columns(self, sample_csv_path):
        """Test CSV validation with required columns."""
        # Test with existing columns
        result = validate_csv_structure(
            sample_csv_path, 
            required_columns=['Year', 'Location']
        )
        assert result['status'] == 'success'
        assert result['data']['valid'] == True
        
        # Test with non-existent columns
        result = validate_csv_structure(
            sample_csv_path, 
            required_columns=['NonExistentColumn']
        )
        assert result['status'] == 'success'
        assert result['data']['valid'] == False
        assert len(result['data']['issues']) > 0


class TestIntegration:
    """Integration test for core workflow."""
    
    def test_core_workflow(self):
        """Test complete workflow using core functions."""
        sample_csv_path = os.path.join(
            os.path.dirname(__file__), '..', 'testdata', 'sample.csv'
        )
        
        # Validate file path
        path_result = validate_file_path(sample_csv_path, must_exist=True)
        assert path_result['status'] == 'success'
        
        # Validate CSV structure
        structure_result = validate_csv_structure(sample_csv_path)
        assert structure_result['status'] == 'success'
        
        # Read CSV sample
        read_result = read_csv_sample(sample_csv_path, rows=3)
        assert read_result['status'] == 'success'
        assert len(read_result['columns']) == 6


if __name__ == '__main__':
    pytest.main([__file__, '-v'])