"""
SDMX Analyzer Agent

Analyzes SDMX data structures and maps to Data Commons properties.
Handles dimensions, measures, attributes, and codelists.
"""

from __future__ import annotations

import pandas as pd
import logging
import re
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass

from .sdmx_reader import read_sdmx_file, SdmxStructure
from .analyzer import analyze_column_types, suggest_dc_mappings

# Standard SDMX dimensions and their DC mappings
SDMX_DIMENSION_MAPPINGS = {
    'REF_AREA': {
        'dc_property': 'observationAbout',
        'transform': 'country_code',
        'description': 'Reference area (countries, regions)'
    },
    'TIME_PERIOD': {
        'dc_property': 'observationDate',
        'transform': 'date_format',
        'description': 'Time period of observation'
    },
    'FREQ': {
        'dc_property': None,  # Used for date formatting
        'transform': 'frequency_metadata',
        'description': 'Frequency of data'
    },
    'INDICATOR': {
        'dc_property': 'measuredProperty',
        'transform': 'statvar_component',
        'description': 'Statistical indicator'
    },
    'SERIES': {
        'dc_property': 'measuredProperty',
        'transform': 'statvar_component',
        'description': 'Data series identifier'
    },
    'MEASURE': {
        'dc_property': 'measuredProperty',
        'transform': 'statvar_component',
        'description': 'Statistical measure'
    }
}

# Standard SDMX attributes and their DC mappings
SDMX_ATTRIBUTE_MAPPINGS = {
    'UNIT_MEASURE': {
        'dc_property': 'unit',
        'transform': 'unit_conversion',
        'description': 'Unit of measurement'
    },
    'OBS_STATUS': {
        'dc_property': 'measurementMethod',
        'transform': 'observation_status',
        'description': 'Observation status'
    },
    'CONF_STATUS': {
        'dc_property': 'footnote',
        'transform': 'confidentiality_status',
        'description': 'Confidentiality status'
    },
    'TIME_FORMAT': {
        'dc_property': None,  # Used for date parsing
        'transform': 'date_format_hint',
        'description': 'Time period format'
    }
}

# SDMX unit conversions to DC units
SDMX_UNIT_CONVERSIONS = {
    'USD': 'USDollar',
    'EUR': 'Euro',
    'GBP': 'PoundSterling',
    'JPY': 'JapaneseYen',
    'PERCENT': 'Percent',
    'PC': 'Percent',
    'RATIO': 'Ratio',
    'INDEX': 'Index',
    'PERSONS': 'Number',
    'THOUSANDS_PERSONS': 'Number',
    'MILLIONS_PERSONS': 'Number',
    'YEARS': 'Year',
    'MONTHS': 'Month',
    'DAYS': 'Day'
}

# SDMX missing value codes
SDMX_MISSING_VALUES = ['M', 'NA', ':', '-', '..', 'NaN', 'NULL']

@dataclass
class SdmxAnalysisResult:
    """Results of SDMX structure analysis"""
    dimensions: Dict[str, Any]
    measures: Dict[str, Any]
    attributes: Dict[str, Any]
    codelists: Dict[str, Dict[str, str]]
    frequency: Optional[str]
    time_format: Optional[str]
    dc_mappings: Dict[str, Any]
    structure_info: Optional[Dict[str, Any]] = None


def analyze_sdmx_structure(file_path: str, metadata_path: Optional[str] = None) -> Dict[str, Any]:
    """Analyze SDMX data structure and create DC mappings.

    Args:
        file_path: Path to SDMX data file
        metadata_path: Optional path to SDMX metadata file

    Returns:
        Dictionary with SDMX analysis results
    """
    try:
        # Read SDMX file
        sdmx_data = read_sdmx_file(file_path, metadata_path)

        if sdmx_data["status"] != "success":
            return sdmx_data

        # Analyze structure
        if "data" in sdmx_data and isinstance(sdmx_data["data"], pd.DataFrame):
            return _analyze_sdmx_data_structure(sdmx_data)
        else:
            return {"status": "error", "error_message": "No data found in SDMX file"}

    except Exception as e:
        logging.error(f"SDMX structure analysis failed: {str(e)}")
        return {"status": "error", "error_message": str(e)}


def _analyze_sdmx_data_structure(sdmx_data: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze the structure of SDMX data."""

    df = sdmx_data["data"]
    structure_info = sdmx_data.get("structure_info", {})

    # Identify columns by type
    dimensions = {}
    measures = {}
    attributes = {}

    for col in df.columns:
        col_upper = col.upper()

        # Check if it's a standard SDMX dimension
        if col_upper in SDMX_DIMENSION_MAPPINGS:
            dimensions[col] = _analyze_dimension(col, df[col], structure_info)
        # Check if it's a measure (numeric values)
        elif col_upper in ['OBS_VALUE', 'VALUE'] or _is_numeric_column(df[col]):
            measures[col] = _analyze_measure(col, df[col], structure_info)
        # Check if it's an attribute
        elif col_upper in SDMX_ATTRIBUTE_MAPPINGS:
            attributes[col] = _analyze_attribute(col, df[col], structure_info)
        else:
            # Use heuristics to classify
            if _looks_like_dimension(col, df[col]):
                dimensions[col] = _analyze_dimension(col, df[col], structure_info)
            elif _is_numeric_column(df[col]):
                measures[col] = _analyze_measure(col, df[col], structure_info)
            else:
                attributes[col] = _analyze_attribute(col, df[col], structure_info)

    # Extract frequency and time format
    frequency = _detect_frequency(df, dimensions)
    time_format = _determine_time_format(df, dimensions, frequency)

    # Extract codelists from structure info
    codelists = structure_info.get("codelists", {})

    # Generate DC mappings
    dc_mappings = _generate_dc_mappings(dimensions, measures, attributes, frequency, time_format)

    return {
        "status": "success",
        "analysis": SdmxAnalysisResult(
            dimensions=dimensions,
            measures=measures,
            attributes=attributes,
            codelists=codelists,
            frequency=frequency,
            time_format=time_format,
            dc_mappings=dc_mappings,
            structure_info=structure_info
        ),
        "data_shape": {"rows": len(df), "cols": len(df.columns)}
    }


def _analyze_dimension(col: str, series: pd.Series, structure_info: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze a dimension column."""

    col_upper = col.upper()
    unique_values = series.dropna().unique()

    analysis = {
        "column": col,
        "type": "dimension",
        "unique_count": len(unique_values),
        "sample_values": list(unique_values[:10]),
        "dc_property": None,
        "transform": None
    }

    # Apply standard mappings
    if col_upper in SDMX_DIMENSION_MAPPINGS:
        mapping = SDMX_DIMENSION_MAPPINGS[col_upper]
        analysis.update({
            "dc_property": mapping["dc_property"],
            "transform": mapping["transform"],
            "description": mapping["description"]
        })

    # Special handling for specific dimensions
    if col_upper == 'REF_AREA':
        analysis["area_codes"] = _analyze_area_codes(series)
    elif col_upper == 'TIME_PERIOD':
        analysis["time_patterns"] = _analyze_time_patterns(series)
    elif col_upper == 'FREQ':
        analysis["frequencies"] = list(unique_values)

    return analysis


def _analyze_measure(col: str, series: pd.Series, structure_info: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze a measure column."""

    numeric_series = pd.to_numeric(series, errors='coerce')

    return {
        "column": col,
        "type": "measure",
        "numeric_count": numeric_series.notna().sum(),
        "total_count": len(series),
        "min_value": float(numeric_series.min()) if not numeric_series.empty else None,
        "max_value": float(numeric_series.max()) if not numeric_series.empty else None,
        "dc_property": "value",
        "transform": "numeric"
    }


def _analyze_attribute(col: str, series: pd.Series, structure_info: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze an attribute column."""

    col_upper = col.upper()
    unique_values = series.dropna().unique()

    analysis = {
        "column": col,
        "type": "attribute",
        "unique_count": len(unique_values),
        "sample_values": list(unique_values[:10]),
        "dc_property": None,
        "transform": None
    }

    # Apply standard mappings
    if col_upper in SDMX_ATTRIBUTE_MAPPINGS:
        mapping = SDMX_ATTRIBUTE_MAPPINGS[col_upper]
        analysis.update({
            "dc_property": mapping["dc_property"],
            "transform": mapping["transform"],
            "description": mapping["description"]
        })

    return analysis


def _is_numeric_column(series: pd.Series) -> bool:
    """Check if column contains numeric data."""
    numeric_ratio = pd.to_numeric(series, errors='coerce').notna().sum() / len(series)
    return numeric_ratio > 0.8


def _looks_like_dimension(col: str, series: pd.Series) -> bool:
    """Heuristic to identify dimension columns."""
    unique_count = len(series.dropna().unique())
    total_count = len(series)

    # If less than 50% unique values, likely a dimension
    return unique_count < (total_count * 0.5) and unique_count > 1


def _detect_frequency(df: pd.DataFrame, dimensions: Dict[str, Any]) -> Optional[str]:
    """Detect data frequency from TIME_PERIOD or FREQ columns."""

    # Check for FREQ column first
    for col, info in dimensions.items():
        if col.upper() == 'FREQ' and "sample_values" in info:
            freq_values = info["sample_values"]
            if freq_values:
                return str(freq_values[0])  # Take first frequency

    # Analyze TIME_PERIOD patterns
    for col, info in dimensions.items():
        if col.upper() == 'TIME_PERIOD' and "time_patterns" in info:
            patterns = info["time_patterns"]
            if "annual" in patterns:
                return "A"
            elif "quarterly" in patterns:
                return "Q"
            elif "monthly" in patterns:
                return "M"
            elif "daily" in patterns:
                return "D"

    return None


def _determine_time_format(df: pd.DataFrame, dimensions: Dict[str, Any], frequency: Optional[str]) -> Optional[str]:
    """Determine appropriate time format based on frequency."""

    freq_formats = {
        "A": "%Y",           # Annual
        "Q": "%Y-Q%q",       # Quarterly
        "M": "%Y-%m",        # Monthly
        "D": "%Y-%m-%d",     # Daily
        "W": "%Y-W%U"        # Weekly
    }

    return freq_formats.get(frequency, "%Y-%m-%d")


def _analyze_area_codes(series: pd.Series) -> Dict[str, Any]:
    """Analyze reference area codes."""
    unique_areas = series.dropna().unique()

    analysis = {
        "total_areas": len(unique_areas),
        "iso_2_count": sum(1 for code in unique_areas if len(str(code)) == 2 and str(code).isalpha()),
        "iso_3_count": sum(1 for code in unique_areas if len(str(code)) == 3 and str(code).isalpha()),
        "numeric_count": sum(1 for code in unique_areas if str(code).isdigit())
    }

    # Determine likely format
    if analysis["iso_2_count"] > analysis["iso_3_count"]:
        analysis["likely_format"] = "ISO-2"
    elif analysis["iso_3_count"] > 0:
        analysis["likely_format"] = "ISO-3"
    elif analysis["numeric_count"] > 0:
        analysis["likely_format"] = "M49"
    else:
        analysis["likely_format"] = "custom"

    return analysis


def _analyze_time_patterns(series: pd.Series) -> List[str]:
    """Analyze time period patterns."""
    patterns = []
    sample_values = series.dropna().unique()[:20]

    for value in sample_values:
        str_value = str(value)

        if re.match(r'^\d{4}$', str_value):
            patterns.append("annual")
        elif re.match(r'^\d{4}-Q[1-4]$', str_value):
            patterns.append("quarterly")
        elif re.match(r'^\d{4}-\d{2}$', str_value):
            patterns.append("monthly")
        elif re.match(r'^\d{4}-\d{2}-\d{2}$', str_value):
            patterns.append("daily")

    return list(set(patterns))


def _generate_dc_mappings(dimensions: Dict[str, Any], measures: Dict[str, Any],
                         attributes: Dict[str, Any], frequency: Optional[str],
                         time_format: Optional[str]) -> Dict[str, Any]:
    """Generate Data Commons property mappings."""

    mappings = {
        "dimensions": {},
        "measures": {},
        "attributes": {},
        "missing_values": SDMX_MISSING_VALUES,
        "frequency": frequency,
        "time_format": time_format
    }

    # Map dimensions
    for col, info in dimensions.items():
        if info.get("dc_property"):
            mappings["dimensions"][col] = {
                "property": info["dc_property"],
                "transform": info.get("transform"),
                "description": info.get("description", "")
            }

    # Map measures
    for col, info in measures.items():
        mappings["measures"][col] = {
            "property": "value",
            "transform": "numeric"
        }

    # Map attributes
    for col, info in attributes.items():
        if info.get("dc_property"):
            mappings["attributes"][col] = {
                "property": info["dc_property"],
                "transform": info.get("transform"),
                "description": info.get("description", "")
            }

    return mappings


# Tool function for ADK integration
def analyze_sdmx_sample(file_path: str, metadata_path: str = None) -> Dict[str, Any]:
    """Analyze SDMX file sample for mapping generation.

    Args:
        file_path: Path to SDMX file
        metadata_path: Optional metadata file path

    Returns:
        Dictionary with SDMX analysis results
    """
    try:
        result = analyze_sdmx_structure(file_path, metadata_path)

        if result["status"] != "success":
            return result

        # Add summary information for agent consumption
        analysis = result["analysis"]
        result["summary"] = {
            "dimension_count": len(analysis.dimensions),
            "measure_count": len(analysis.measures),
            "attribute_count": len(analysis.attributes),
            "frequency": analysis.frequency,
            "time_format": analysis.time_format,
            "has_codelists": len(analysis.codelists) > 0
        }

        return result

    except Exception as e:
        logging.error(f"SDMX sample analysis failed: {str(e)}")
        return {"status": "error", "error_message": str(e)}