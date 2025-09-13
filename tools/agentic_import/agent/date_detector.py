"""
Date format detection module for ADK Phase 8.

This module provides automatic detection of date formats and patterns in CSV files,
supporting various international formats, periods, quarters, and fiscal years.
"""

from __future__ import annotations

import pandas as pd
import numpy as np
import re
from typing import Dict, Any, List, Tuple, Optional, Union
from datetime import datetime
import logging

class DateFormatDetector:
    """Comprehensive date format detection for CSV files."""

    def __init__(self):
        """Initialize date format detector with predefined patterns."""
        self.date_patterns = self._initialize_date_patterns()
        self.period_patterns = self._initialize_period_patterns()

    def _initialize_date_patterns(self) -> List[Dict[str, Any]]:
        """Initialize common date format patterns."""
        return [
            # ISO Formats
            {'pattern': r'^\d{4}-\d{2}-\d{2}$', 'format': '%Y-%m-%d', 'type': 'iso_date', 'example': '2024-01-15'},
            {'pattern': r'^\d{4}-\d{1,2}-\d{1,2}$', 'format': '%Y-%m-%d', 'type': 'iso_date_short', 'example': '2024-1-15'},
            {'pattern': r'^\d{8}$', 'format': '%Y%m%d', 'type': 'iso_compact', 'example': '20240115'},

            # US Formats
            {'pattern': r'^\d{1,2}/\d{1,2}/\d{4}$', 'format': '%m/%d/%Y', 'type': 'us_date', 'example': '1/15/2024'},
            {'pattern': r'^\d{2}/\d{2}/\d{4}$', 'format': '%m/%d/%Y', 'type': 'us_date_padded', 'example': '01/15/2024'},
            {'pattern': r'^\d{1,2}/\d{1,2}/\d{2}$', 'format': '%m/%d/%y', 'type': 'us_date_short', 'example': '1/15/24'},
            {'pattern': r'^\d{2}/\d{2}/\d{2}$', 'format': '%m/%d/%y', 'type': 'us_date_short_padded', 'example': '01/15/24'},

            # European Formats
            {'pattern': r'^\d{1,2}/\d{1,2}/\d{4}$', 'format': '%d/%m/%Y', 'type': 'eu_date', 'example': '15/1/2024'},
            {'pattern': r'^\d{2}/\d{2}/\d{4}$', 'format': '%d/%m/%Y', 'type': 'eu_date_padded', 'example': '15/01/2024'},
            {'pattern': r'^\d{1,2}\.\d{1,2}\.\d{4}$', 'format': '%d.%m.%Y', 'type': 'eu_dot', 'example': '15.1.2024'},
            {'pattern': r'^\d{2}\.\d{2}\.\d{4}$', 'format': '%d.%m.%Y', 'type': 'eu_dot_padded', 'example': '15.01.2024'},

            # Text-based Formats
            {'pattern': r'^\w{3}\s+\d{1,2},?\s+\d{4}$', 'format': '%b %d, %Y', 'type': 'text_month_us', 'example': 'Jan 15, 2024'},
            {'pattern': r'^\w{3}-\d{4}$', 'format': '%b-%Y', 'type': 'month_year', 'example': 'Jan-2024'},
            {'pattern': r'^\w{3}\s+\d{4}$', 'format': '%b %Y', 'type': 'month_year_space', 'example': 'Jan 2024'},
            {'pattern': r'^\d{1,2}\s+\w{3}\s+\d{4}$', 'format': '%d %b %Y', 'type': 'text_month_eu', 'example': '15 Jan 2024'},

            # Year-only and simple periods
            {'pattern': r'^\d{4}$', 'format': '%Y', 'type': 'year_only', 'example': '2024'}
        ]

    def _initialize_period_patterns(self) -> List[Dict[str, Any]]:
        """Initialize period and fiscal year patterns."""
        return [
            # Quarters
            {'pattern': r'^\d{4}[Qq][1-4]$', 'format': 'quarter', 'type': 'quarter', 'example': '2024Q1'},
            {'pattern': r'^\d{4}-[Qq][1-4]$', 'format': 'quarter', 'type': 'quarter_dash', 'example': '2024-Q1'},
            {'pattern': r'^[Qq][1-4]\s+\d{4}$', 'format': 'quarter', 'type': 'quarter_space', 'example': 'Q1 2024'},

            # Fiscal Years
            {'pattern': r'^[Ff][Yy]\d{4}$', 'format': 'fiscal_year', 'type': 'fiscal_year', 'example': 'FY2024'},
            {'pattern': r'^[Ff][Yy]\s+\d{4}$', 'format': 'fiscal_year', 'type': 'fiscal_year_space', 'example': 'FY 2024'},
            {'pattern': r'^\d{4}-\d{2}$', 'format': 'fiscal_year_range', 'type': 'fiscal_year_range', 'example': '2023-24'},

            # Academic Years
            {'pattern': r'^[Aa][Yy]\d{4}-\d{2}$', 'format': 'academic_year', 'type': 'academic_year', 'example': 'AY2023-24'},

            # Weekly
            {'pattern': r'^\d{4}[Ww]\d{1,2}$', 'format': 'week', 'type': 'iso_week', 'example': '2024W01'},
            {'pattern': r'^\d{4}-[Ww]\d{1,2}$', 'format': 'week', 'type': 'iso_week_dash', 'example': '2024-W01'},

            # Monthly periods
            {'pattern': r'^\d{4}-\d{2}$', 'format': '%Y-%m', 'type': 'year_month', 'example': '2024-01'},
            {'pattern': r'^\d{6}$', 'format': '%Y%m', 'type': 'year_month_compact', 'example': '202401'}
        ]

    def detect_date_columns(self, file_path: str, header_rows: int = 1, sample_size: int = 100) -> Dict[str, Any]:
        """
        Detect date columns and their formats in a CSV file.

        Args:
            file_path: Path to CSV file
            header_rows: Number of header rows
            sample_size: Number of rows to sample for analysis

        Returns:
            Dict with date column analysis
        """
        try:
            # Read sample data
            df = pd.read_csv(file_path, header=list(range(header_rows)), nrows=sample_size)

            if header_rows > 1:
                # Flatten multi-level headers
                df.columns = [' '.join(col).strip() if isinstance(col, tuple) else str(col)
                             for col in df.columns]

            date_columns = {}
            primary_date_column = None
            best_confidence = 0.0

            # Analyze each column
            for col in df.columns:
                col_analysis = self._analyze_date_column(df[col], str(col))

                if col_analysis['is_date_column']:
                    date_columns[col] = col_analysis

                    # Track best candidate for primary date column
                    if col_analysis['confidence'] > best_confidence:
                        best_confidence = col_analysis['confidence']
                        primary_date_column = col

            return {
                "status": "success",
                "date_columns": date_columns,
                "primary_date_column": primary_date_column,
                "total_columns_analyzed": len(df.columns),
                "date_columns_found": len(date_columns)
            }

        except Exception as e:
            logging.error(f"Date column detection failed: {str(e)}")
            return {"status": "error", "error_message": str(e)}

    def _analyze_date_column(self, column_data: pd.Series, column_name: str) -> Dict[str, Any]:
        """
        Analyze a single column for date patterns.

        Args:
            column_data: Column data to analyze
            column_name: Name of the column

        Returns:
            Dict with date analysis results
        """
        # Clean and prepare data
        clean_data = column_data.dropna().astype(str).str.strip()

        if len(clean_data) == 0:
            return {'is_date_column': False, 'confidence': 0.0}

        # Check column name for date indicators
        name_score = self._score_column_name(column_name)

        # Test each date pattern
        pattern_results = []

        for pattern_set in [self.date_patterns, self.period_patterns]:
            for pattern_info in pattern_set:
                match_result = self._test_pattern(clean_data, pattern_info)
                if match_result['match_ratio'] > 0:
                    pattern_results.append({
                        **pattern_info,
                        **match_result
                    })

        # Find best matching pattern
        if not pattern_results:
            return {
                'is_date_column': False,
                'confidence': 0.0,
                'column_name': column_name,
                'name_score': name_score
            }

        best_pattern = max(pattern_results, key=lambda x: x['match_ratio'])

        # Calculate overall confidence
        confidence = self._calculate_confidence(best_pattern, name_score, len(clean_data))

        # Determine if this is a date column (threshold-based)
        is_date_column = confidence > 0.7 or (confidence > 0.5 and name_score > 0.5)

        return {
            'is_date_column': is_date_column,
            'confidence': confidence,
            'detected_format': best_pattern['format'],
            'format_type': best_pattern['type'],
            'match_ratio': best_pattern['match_ratio'],
            'sample_values': clean_data.head(5).tolist(),
            'column_name': column_name,
            'name_score': name_score,
            'total_values': len(clean_data),
            'all_patterns_tested': len(pattern_results)
        }

    def _test_pattern(self, data: pd.Series, pattern_info: Dict[str, Any]) -> Dict[str, float]:
        """Test a specific pattern against column data."""
        pattern = pattern_info['pattern']
        matches = 0
        total = len(data)

        for value in data:
            if re.match(pattern, str(value)):
                matches += 1

        match_ratio = matches / total if total > 0 else 0.0

        return {'match_ratio': match_ratio, 'matches': matches, 'total': total}

    def _score_column_name(self, column_name: str) -> float:
        """Score column name for date-related terms."""
        date_indicators = [
            r'(?i)date',
            r'(?i)time',
            r'(?i)year',
            r'(?i)month',
            r'(?i)day',
            r'(?i)period',
            r'(?i)quarter',
            r'(?i)fiscal',
            r'(?i)academic',
            r'(?i)week',
            r'(?i)timestamp',
            r'(?i)when',
            r'(?i)as_of',
            r'(?i)effective',
        ]

        score = 0.0
        for indicator in date_indicators:
            if re.search(indicator, column_name):
                score += 1.0

        # Normalize score
        return min(score / len(date_indicators), 1.0)

    def _calculate_confidence(self, best_pattern: Dict[str, Any], name_score: float, data_size: int) -> float:
        """Calculate overall confidence score for date detection."""
        pattern_score = best_pattern['match_ratio']

        # Adjust for data size (more data = higher confidence)
        size_factor = min(data_size / 50.0, 1.0)  # Cap at 50 samples

        # Weighted combination
        confidence = (
            pattern_score * 0.6 +  # Pattern matching is most important
            name_score * 0.3 +     # Column name helps
            size_factor * 0.1      # More data increases confidence
        )

        return min(confidence, 1.0)

    def generate_date_configuration(self, date_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate date-related configuration for metadata.

        Args:
            date_analysis: Results from detect_date_columns

        Returns:
            Dict with date configuration parameters
        """
        if date_analysis.get("status") != "success":
            return {"status": "error", "error_message": "Invalid date analysis input"}

        config = {}
        date_columns = date_analysis.get("date_columns", {})
        primary_date = date_analysis.get("primary_date_column")

        if not date_columns:
            return {
                "status": "success",
                "has_date_columns": False,
                "config": {}
            }

        # Primary date column configuration
        if primary_date and primary_date in date_columns:
            primary_info = date_columns[primary_date]
            config["observation_date_column"] = primary_date
            config["date_format"] = primary_info["detected_format"]
            config["date_format_type"] = primary_info["format_type"]

        # Multiple date columns handling
        if len(date_columns) > 1:
            config["multiple_date_columns"] = True
            config["date_columns_info"] = {
                col: {
                    "format": info["detected_format"],
                    "type": info["format_type"],
                    "confidence": info["confidence"]
                }
                for col, info in date_columns.items()
            }
        else:
            config["multiple_date_columns"] = False

        # Period-specific configurations
        primary_type = date_columns.get(primary_date, {}).get("format_type", "")

        if "quarter" in primary_type:
            config["observation_period"] = "quarter"
            config["period_aggregation"] = True
        elif "fiscal" in primary_type:
            config["observation_period"] = "fiscal_year"
            config["period_aggregation"] = True
        elif "year" in primary_type:
            config["observation_period"] = "year"
            config["period_aggregation"] = True
        elif "month" in primary_type:
            config["observation_period"] = "month"
        elif "week" in primary_type:
            config["observation_period"] = "week"
        else:
            config["observation_period"] = "point"

        return {
            "status": "success",
            "has_date_columns": True,
            "config": config,
            "date_columns_detected": len(date_columns),
            "primary_date_confidence": date_columns.get(primary_date, {}).get("confidence", 0.0)
        }


def detect_date_formats(file_path: str, header_rows: int = 1) -> Dict[str, Any]:
    """
    Convenience function to detect date formats in a CSV file.

    Args:
        file_path: Path to CSV file
        header_rows: Number of header rows

    Returns:
        Complete date format analysis and configuration
    """
    detector = DateFormatDetector()

    # Detect date columns
    date_analysis = detector.detect_date_columns(file_path, header_rows)

    if date_analysis.get("status") != "success":
        return date_analysis

    # Generate configuration
    config_result = detector.generate_date_configuration(date_analysis)

    return {
        "status": "success",
        "analysis": date_analysis,
        "configuration": config_result,
        "recommended_metadata_params": config_result.get("config", {})
    }


def validate_date_detection(file_path: str, detected_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate detected date configuration by attempting to parse dates.

    Args:
        file_path: Path to CSV file
        detected_config: Detected date configuration

    Returns:
        Validation results
    """
    try:
        if not detected_config.get("has_date_columns", False):
            return {"status": "success", "validation": "no_dates", "message": "No date columns detected"}

        config = detected_config.get("config", {})
        date_column = config.get("observation_date_column")
        date_format = config.get("date_format")

        if not date_column or not date_format:
            return {"status": "error", "error_message": "Missing date column or format information"}

        # Read sample data
        df_sample = pd.read_csv(file_path, nrows=50)

        if date_column not in df_sample.columns:
            return {"status": "error", "error_message": f"Date column '{date_column}' not found in file"}

        # Attempt to parse dates
        date_data = df_sample[date_column].dropna()
        parse_success = 0
        parse_errors = []

        for value in date_data.head(20):  # Test first 20 values
            try:
                if date_format == 'quarter' or date_format == 'fiscal_year':
                    # Special handling for periods
                    parse_success += 1
                else:
                    pd.to_datetime(str(value), format=date_format)
                    parse_success += 1
            except Exception as e:
                parse_errors.append(f"Failed to parse '{value}': {str(e)}")

        success_rate = parse_success / len(date_data.head(20)) if len(date_data) > 0 else 0

        return {
            "status": "success",
            "validation": "successful" if success_rate > 0.8 else "partial" if success_rate > 0.5 else "failed",
            "success_rate": success_rate,
            "parse_errors": parse_errors[:5],  # Return first 5 errors
            "samples_tested": min(20, len(date_data)),
            "date_column": date_column,
            "detected_format": date_format
        }

    except Exception as e:
        logging.error(f"Date detection validation failed: {str(e)}")
        return {"status": "error", "error_message": str(e)}