"""
SDMX Metadata Generator Agent

Generates metadata.csv configuration for SDMX datasets.
Handles frequency-based date formatting, multi-dimensional headers, and aggregation rules.
"""

from __future__ import annotations

import pandas as pd
import csv
import logging
import json
from typing import Dict, Any, List, Optional
from pathlib import Path

from .sdmx_analyzer import SdmxAnalysisResult
from .metadata_generator import generate_metadata_config


# Frequency-based date format mappings
SDMX_DATE_FORMATS = {
    'A': '%Y',           # Annual
    'Q': '%Y-Q%q',       # Quarterly - will need post-processing
    'M': '%Y-%m',        # Monthly
    'W': '%Y-W%U',       # Weekly
    'D': '%Y-%m-%d',     # Daily
    'B': '%Y-%m-%d',     # Business daily
    'H': '%Y-%m-%d %H',  # Hourly
}

# Observation date formats for different frequencies
OBSERVATION_DATE_FORMATS = {
    'A': '%Y',
    'Q': '%Y-%m',        # Convert Q to month (end of quarter)
    'M': '%Y-%m',
    'W': '%Y-%m-%d',
    'D': '%Y-%m-%d',
    'B': '%Y-%m-%d',
    'H': '%Y-%m-%d'
}

# Quarter to month mapping for quarterly data
QUARTER_TO_MONTH = {
    'Q1': '03', 'Q2': '06', 'Q3': '09', 'Q4': '12'
}

# Default aggregation methods by data type
DEFAULT_AGGREGATIONS = {
    'sum': ['TOTAL', 'SUM', 'COUNT'],
    'mean': ['AVERAGE', 'MEAN', 'RATE', 'RATIO'],
    'last': ['INDEX', 'LEVEL', 'STATUS'],
    'first': ['STOCK', 'BALANCE']
}


def create_sdmx_metadata(analysis: SdmxAnalysisResult, data_shape: Dict[str, int],
                        output_path: str) -> Dict[str, Any]:
    """Create metadata.csv configuration for SDMX dataset.

    Args:
        analysis: SDMX analysis results
        data_shape: Shape of the data (rows, cols)
        output_path: Path to output metadata CSV file

    Returns:
        Dictionary with creation status and configuration
    """
    try:
        # Generate metadata configuration
        config = _generate_sdmx_metadata_config(analysis, data_shape)

        # Write metadata CSV
        result = _write_metadata_csv(config, output_path)

        if result["status"] == "success":
            result["configuration"] = config

        return result

    except Exception as e:
        logging.error(f"SDMX metadata generation failed: {str(e)}")
        return {"status": "error", "error_message": str(e)}


def _generate_sdmx_metadata_config(analysis: SdmxAnalysisResult,
                                  data_shape: Dict[str, int]) -> Dict[str, Any]:
    """Generate metadata configuration for SDMX dataset."""

    config = {
        # Header detection
        "header_rows": 1,  # SDMX typically has single header row
        "header_columns": 0,

        # Data area detection
        "mapped_rows": f"2:{data_shape['rows']}",  # Skip header
        "mapped_columns": f"1:{data_shape['cols']}",

        # Date configuration
        "date_format": _determine_date_format(analysis),
        "observation_date_format": _determine_observation_date_format(analysis),

        # Aggregation configuration
        "aggregation_method": _determine_aggregation_method(analysis),
        "duplicate_handling": "aggregate",

        # Place resolution
        "place_resolution": _configure_place_resolution(analysis),

        # Data processing
        "skip_empty_rows": True,
        "skip_empty_columns": True,
        "trim_whitespace": True,

        # SDMX-specific settings
        "sdmx_frequency": analysis.frequency,
        "time_dimension_column": _find_time_dimension_column(analysis),
        "area_dimension_column": _find_area_dimension_column(analysis),

        # Validation settings
        "validate_dates": True,
        "validate_places": True,
        "strict_mode": False  # Be flexible with SDMX data variations
    }

    # Add multi-dimensional header configuration if needed
    if _has_multi_dimensional_structure(analysis):
        config.update(_configure_multi_dimensional_headers(analysis))

    # Add frequency-specific configurations
    if analysis.frequency:
        config.update(_configure_frequency_specific_settings(analysis.frequency))

    return config


def _determine_date_format(analysis: SdmxAnalysisResult) -> str:
    """Determine date format based on SDMX frequency."""

    if analysis.frequency and analysis.frequency in SDMX_DATE_FORMATS:
        return SDMX_DATE_FORMATS[analysis.frequency]

    # Analyze TIME_PERIOD patterns if frequency not available
    for col, info in analysis.dimensions.items():
        if col.upper() == 'TIME_PERIOD':
            time_patterns = info.get("time_patterns", [])
            if "quarterly" in time_patterns:
                return SDMX_DATE_FORMATS['Q']
            elif "monthly" in time_patterns:
                return SDMX_DATE_FORMATS['M']
            elif "daily" in time_patterns:
                return SDMX_DATE_FORMATS['D']
            elif "annual" in time_patterns:
                return SDMX_DATE_FORMATS['A']

    return '%Y-%m-%d'  # Default


def _determine_observation_date_format(analysis: SdmxAnalysisResult) -> str:
    """Determine observation date format for output."""

    if analysis.frequency and analysis.frequency in OBSERVATION_DATE_FORMATS:
        return OBSERVATION_DATE_FORMATS[analysis.frequency]

    return '%Y-%m-%d'  # Default


def _determine_aggregation_method(analysis: SdmxAnalysisResult) -> str:
    """Determine appropriate aggregation method for the dataset."""

    # Check dimension and measure names for clues
    all_names = []

    # Collect names from dimensions
    for info in analysis.dimensions.values():
        sample_values = info.get("sample_values", [])
        all_names.extend([str(val).upper() for val in sample_values])

    # Check structure info
    if analysis.structure_info:
        dataflows = analysis.structure_info.get("dataflows", {})
        for df_info in dataflows.values():
            name = df_info.get("name", "").upper()
            all_names.append(name)

    # Determine aggregation based on content
    text_content = " ".join(all_names)

    for method, keywords in DEFAULT_AGGREGATIONS.items():
        if any(keyword in text_content for keyword in keywords):
            return method

    return "mean"  # Default for most statistical data


def _configure_place_resolution(analysis: SdmxAnalysisResult) -> Dict[str, Any]:
    """Configure place resolution settings."""

    config = {
        "enabled": True,
        "strict_matching": False,
        "allow_approximate": True
    }

    # Check if we have REF_AREA dimension
    for col, info in analysis.dimensions.items():
        if col.upper() == 'REF_AREA':
            area_codes = info.get("area_codes", {})
            likely_format = area_codes.get("likely_format", "custom")

            if likely_format in ["ISO-2", "ISO-3"]:
                config["country_code_format"] = likely_format
                config["strict_matching"] = True
            elif likely_format == "M49":
                config["country_code_format"] = "M49"
                config["convert_m49"] = True

            break

    return config


def _find_time_dimension_column(analysis: SdmxAnalysisResult) -> Optional[str]:
    """Find the time dimension column name."""

    for col, info in analysis.dimensions.items():
        if col.upper() in ['TIME_PERIOD', 'TIME', 'DATE']:
            return col

    return None


def _find_area_dimension_column(analysis: SdmxAnalysisResult) -> Optional[str]:
    """Find the area/geography dimension column name."""

    for col, info in analysis.dimensions.items():
        if col.upper() in ['REF_AREA', 'AREA', 'GEOGRAPHY', 'COUNTRY']:
            return col

    return None


def _has_multi_dimensional_structure(analysis: SdmxAnalysisResult) -> bool:
    """Check if dataset has multi-dimensional structure requiring special header handling."""

    # If more than 3 dimensions, likely multi-dimensional
    return len(analysis.dimensions) > 3


def _configure_multi_dimensional_headers(analysis: SdmxAnalysisResult) -> Dict[str, Any]:
    """Configure settings for multi-dimensional header structures."""

    return {
        "multi_dimensional": True,
        "dimension_header_detection": "auto",
        "pivot_detection": True,
        "cross_tabulation_handling": "auto"
    }


def _configure_frequency_specific_settings(frequency: str) -> Dict[str, Any]:
    """Configure frequency-specific processing settings."""

    config = {}

    if frequency == 'Q':  # Quarterly
        config.update({
            "quarterly_to_monthly": True,
            "quarter_end_months": True,
            "quarter_mapping": QUARTER_TO_MONTH
        })

    elif frequency == 'M':  # Monthly
        config.update({
            "monthly_aggregation": "end_of_month",
            "handle_incomplete_months": True
        })

    elif frequency == 'A':  # Annual
        config.update({
            "annual_aggregation": "calendar_year",
            "fiscal_year_handling": False
        })

    elif frequency == 'D':  # Daily
        config.update({
            "weekend_handling": "include",
            "holiday_handling": "include",
            "business_day_only": False
        })

    return config


def _write_metadata_csv(config: Dict[str, Any], output_path: str) -> Dict[str, Any]:
    """Write metadata configuration to CSV file."""

    try:
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)

            # Write header
            writer.writerow(['parameter', 'value'])

            # Write configuration parameters
            for key, value in config.items():
                if isinstance(value, dict):
                    # Convert nested dicts to JSON string
                    value_str = json.dumps(value, separators=(',', ':'))
                elif isinstance(value, (list, tuple)):
                    # Convert lists to comma-separated string
                    value_str = ','.join(str(v) for v in value)
                elif isinstance(value, bool):
                    # Convert boolean to string
                    value_str = 'true' if value else 'false'
                else:
                    value_str = str(value)

                writer.writerow([key, value_str])

        return {
            "status": "success",
            "file": output_path,
            "parameters_written": len(config)
        }

    except Exception as e:
        logging.error(f"Failed to write metadata CSV: {str(e)}")
        return {"status": "error", "error_message": str(e)}


def _detect_header_structure(df: pd.DataFrame, analysis: SdmxAnalysisResult) -> Dict[str, Any]:
    """Detect header structure in SDMX data."""

    header_info = {
        "header_rows": 1,
        "header_columns": 0,
        "has_multi_level": False,
        "pivot_structure": False
    }

    # Check for multi-level headers
    if len(df.columns) > 10 and any('.' in str(col) for col in df.columns):
        header_info["has_multi_level"] = True
        header_info["header_rows"] = 2

    # Check for pivot table structure
    if len(analysis.dimensions) > 3:
        header_info["pivot_structure"] = True

    return header_info


def _validate_metadata_config(config: Dict[str, Any], analysis: SdmxAnalysisResult) -> Dict[str, Any]:
    """Validate metadata configuration for consistency."""

    validation_result = {"status": "success", "warnings": []}

    # Check date format consistency
    if config.get("sdmx_frequency") and config.get("date_format"):
        expected_format = SDMX_DATE_FORMATS.get(config["sdmx_frequency"])
        if expected_format and config["date_format"] != expected_format:
            validation_result["warnings"].append(
                f"Date format mismatch: frequency {config['sdmx_frequency']} "
                f"expects {expected_format}, got {config['date_format']}"
            )

    # Check for missing required columns
    if not config.get("time_dimension_column"):
        validation_result["warnings"].append("No time dimension column found")

    if not config.get("area_dimension_column") and any(
        col.upper() == 'REF_AREA' for col in analysis.dimensions.keys()
    ):
        validation_result["warnings"].append("REF_AREA dimension found but not configured")

    return validation_result


# Tool function for ADK integration
def create_sdmx_metadata_from_analysis(analysis: SdmxAnalysisResult, data_shape: Dict[str, int],
                                      output_path: str = "metadata.csv") -> Dict[str, Any]:
    """Create SDMX metadata configuration from analysis results.

    Args:
        analysis: SDMX analysis results
        data_shape: Shape of the data
        output_path: Output path for metadata CSV

    Returns:
        Dictionary with creation status
    """
    try:
        result = create_sdmx_metadata(analysis, data_shape, output_path)

        if result["status"] == "success":
            # Add validation
            validation = _validate_metadata_config(result["configuration"], analysis)
            result["validation"] = validation

            # Add summary
            result["summary"] = {
                "frequency": analysis.frequency,
                "date_format": result["configuration"].get("date_format"),
                "aggregation_method": result["configuration"].get("aggregation_method"),
                "parameters_count": len(result["configuration"])
            }

        return result

    except Exception as e:
        logging.error(f"SDMX metadata creation failed: {str(e)}")
        return {"status": "error", "error_message": str(e)}


def create_sdmx_metadata_from_file(file_path: str, metadata_path: str = None,
                                  output_path: str = "metadata.csv") -> Dict[str, Any]:
    """Create SDMX metadata configuration from file analysis.

    Args:
        file_path: Path to SDMX file
        metadata_path: Optional metadata file path
        output_path: Output path for metadata CSV

    Returns:
        Dictionary with creation status
    """
    try:
        # Import here to avoid circular imports
        from .sdmx_analyzer import analyze_sdmx_structure

        # Analyze SDMX structure
        analysis_result = analyze_sdmx_structure(file_path, metadata_path)

        if analysis_result["status"] != "success":
            return analysis_result

        # Create metadata configuration
        analysis = analysis_result["analysis"]
        data_shape = analysis_result["data_shape"]

        result = create_sdmx_metadata_from_analysis(analysis, data_shape, output_path)

        return result

    except Exception as e:
        logging.error(f"SDMX metadata creation from file failed: {str(e)}")
        return {"status": "error", "error_message": str(e)}