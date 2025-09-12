#!/usr/bin/env python3
"""
Unit tests for Phase 2 analyzer functionality.

Tests column analysis, DC property mapping, and utility functions.
"""

import os
import pandas as pd
import pytest

from ..analyzer import analyze_column_types, suggest_dc_mappings
from ..tools import (
    detect_column_data_type,
    is_date_column, 
    get_dc_property_suggestions
)


class TestColumnAnalysis:
    """Test column analysis functions."""
    
    @pytest.fixture
    def sample_csv_path(self):
        """Path to the test CSV file."""
        return os.path.join(os.path.dirname(__file__), '..', 'testdata', 'sample.csv')
    
    def test_analyze_column_types_success(self, sample_csv_path):
        """Test successful column type analysis."""
        result = analyze_column_types(sample_csv_path, sample_rows=10)
        
        assert result['status'] == 'success'
        assert 'column_analysis' in result
        
        analysis = result['column_analysis']
        assert 'Year' in analysis
        assert 'Location' in analysis
        assert 'Population' in analysis
        
        # Check specific column types
        assert analysis['Year']['type'] == 'year'
        assert analysis['Location']['type'] == 'categorical'
        assert analysis['Population']['type'] == 'numeric'
    
    def test_analyze_column_types_file_not_found(self):
        """Test column analysis with non-existent file."""
        result = analyze_column_types('/path/that/does/not/exist.csv')
        
        assert result['status'] == 'error'
        assert 'error_message' in result
    
    def test_suggest_dc_mappings_success(self, sample_csv_path):
        """Test DC mapping suggestions."""
        analysis_result = analyze_column_types(sample_csv_path, sample_rows=10)
        mapping_result = suggest_dc_mappings(analysis_result)
        
        assert mapping_result['status'] == 'success'
        assert 'mappings' in mapping_result
        
        mappings = mapping_result['mappings']
        assert mappings['populationType'] == 'Person'
        assert mappings['statType'] == 'measuredValue'
        assert isinstance(mappings['constraintProperties'], list)
        assert isinstance(mappings['measuredProperties'], list)


class TestUtilityFunctions:
    """Test utility functions in tools.py."""
    
    def test_detect_column_data_type_numeric(self):
        """Test numeric column detection."""
        numeric_series = pd.Series([1, 2, 3, 4, 5])
        result = detect_column_data_type(numeric_series)
        assert result == 'numeric'
    
    def test_detect_column_data_type_categorical(self):
        """Test categorical column detection."""
        categorical_series = pd.Series(['A', 'B', 'A', 'C', 'B'])
        result = detect_column_data_type(categorical_series)
        assert result == 'categorical'
    
    def test_detect_column_data_type_text(self):
        """Test text column detection."""
        text_series = pd.Series([f'text_{i}' for i in range(100)])
        result = detect_column_data_type(text_series)
        assert result == 'text'
    
    def test_is_date_column_year(self):
        """Test year column detection."""
        year_series = pd.Series(['2020', '2021', '2022'])
        result = is_date_column('Year', year_series)
        assert result == True
    
    def test_is_date_column_not_date(self):
        """Test non-date column detection."""
        text_series = pd.Series(['California', 'Texas', 'Florida'])
        result = is_date_column('Location', text_series)
        assert result == False
    
    def test_get_dc_property_suggestions_year(self):
        """Test DC property suggestion for year column."""
        result = get_dc_property_suggestions('Year', 'numeric')
        assert result == 'observationDate'
    
    def test_get_dc_property_suggestions_location(self):
        """Test DC property suggestion for location column.""" 
        result = get_dc_property_suggestions('Location', 'categorical')
        assert result == 'geoId'
    
    def test_get_dc_property_suggestions_numeric(self):
        """Test DC property suggestion for numeric column."""
        result = get_dc_property_suggestions('Population', 'numeric')
        assert result == 'measuredProperty'


class TestIntegration:
    """Integration tests for analyzer functionality."""
    
    def test_full_analysis_workflow(self):
        """Test complete analysis workflow."""
        sample_csv_path = os.path.join(
            os.path.dirname(__file__), '..', 'testdata', 'sample.csv'
        )
        
        # Run column analysis
        analysis_result = analyze_column_types(sample_csv_path)
        assert analysis_result['status'] == 'success'
        
        # Generate DC mappings
        mapping_result = suggest_dc_mappings(analysis_result)
        assert mapping_result['status'] == 'success'
        
        # Verify expected structure
        mappings = mapping_result['mappings']
        assert 'populationType' in mappings
        assert 'statType' in mappings
        assert 'constraintProperties' in mappings
        assert 'measuredProperties' in mappings


if __name__ == '__main__':
    pytest.main([__file__, '-v'])