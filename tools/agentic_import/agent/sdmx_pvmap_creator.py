"""
SDMX PVMap Creator Agent

Creates property-value mappings specifically for SDMX datasets.
Handles standard SDMX dimensions, measures, and attributes mapping to Data Commons properties.
"""

from __future__ import annotations

import os
import sys
import pandas as pd
import csv
import logging
import re
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path

# Add current directory to path for imports
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(_SCRIPT_DIR)

from sdmx_analyzer import SdmxAnalysisResult, SDMX_UNIT_CONVERSIONS, SDMX_MISSING_VALUES
from pvmap_creator import create_pv_mappings, write_pvmap_csv

# Country code mappings for REF_AREA
ISO_COUNTRY_MAPPINGS = {
    # ISO-2 to ISO-3 mappings (sample - would need full mapping)
    'US': 'USA', 'GB': 'GBR', 'FR': 'FRA', 'DE': 'DEU', 'JP': 'JPN',
    'CN': 'CHN', 'IN': 'IND', 'BR': 'BRA', 'RU': 'RUS', 'CA': 'CAN'
}

# Statistical type mappings for common SDMX indicators
STATISTICAL_TYPE_MAPPINGS = {
    'GROWTH': 'growthRate',
    'RATE': 'growthRate',
    'CHANGE': 'growthRate',
    'INDEX': 'indexedValue',
    'RATIO': 'ratio',
    'PERCENT': 'percent',
    'SHARE': 'percent',
    'TOTAL': 'cumulativeValue',
    'SUM': 'cumulativeValue',
    'AVERAGE': 'meanValue',
    'MEAN': 'meanValue',
    'MEDIAN': 'medianValue'
}

# Common economic/social domains for populationType
POPULATION_TYPE_MAPPINGS = {
    'GDP': 'EconomicActivity',
    'POPULATION': 'Person',
    'EMPLOYMENT': 'Person',
    'EDUCATION': 'Person',
    'HEALTH': 'Person',
    'TRADE': 'EconomicActivity',
    'FINANCE': 'EconomicActivity',
    'ENERGY': 'EconomicActivity',
    'TRANSPORT': 'EconomicActivity',
    'ENVIRONMENT': 'EconomicActivity'
}


def create_sdmx_pvmap(analysis: SdmxAnalysisResult, output_path: str) -> Dict[str, Any]:
    """Create PVMap CSV for SDMX dataset.

    Args:
        analysis: SDMX analysis results
        output_path: Path to output PVMap CSV file

    Returns:
        Dictionary with creation status and mappings
    """
    try:
        mappings = []

        # Process dimensions
        dimension_mappings = _create_dimension_mappings(analysis)
        mappings.extend(dimension_mappings)

        # Process measures
        measure_mappings = _create_measure_mappings(analysis)
        mappings.extend(measure_mappings)

        # Process attributes
        attribute_mappings = _create_attribute_mappings(analysis)
        mappings.extend(attribute_mappings)

        # Add missing value mappings
        missing_value_mappings = _create_missing_value_mappings(analysis)
        mappings.extend(missing_value_mappings)

        # Add StatVar construction mappings
        statvar_mappings = _create_statvar_mappings(analysis)
        mappings.extend(statvar_mappings)

        # Write to CSV
        result = _write_sdmx_pvmap_csv(mappings, output_path)

        if result["status"] == "success":
            result["mapping_count"] = len(mappings)
            result["mapping_types"] = {
                "dimensions": len(dimension_mappings),
                "measures": len(measure_mappings),
                "attributes": len(attribute_mappings),
                "missing_values": len(missing_value_mappings),
                "statvars": len(statvar_mappings)
            }

        return result

    except Exception as e:
        logging.error(f"SDMX PVMap creation failed: {str(e)}")
        return {"status": "error", "error_message": str(e)}


def _create_dimension_mappings(analysis: SdmxAnalysisResult) -> List[Dict[str, str]]:
    """Create mappings for SDMX dimensions."""
    mappings = []

    for col, info in analysis.dimensions.items():
        col_upper = col.upper()

        if col_upper == 'REF_AREA':
            mappings.extend(_map_ref_area(col, info))
        elif col_upper == 'TIME_PERIOD':
            mappings.extend(_map_time_period(col, info, analysis.time_format))
        elif col_upper == 'FREQ':
            # FREQ is used for metadata configuration, not direct mapping
            continue
        elif col_upper in ['INDICATOR', 'SERIES', 'MEASURE']:
            mappings.extend(_map_indicator_series(col, info))
        else:
            # Generic dimension mapping - likely constraint property
            mappings.extend(_map_generic_dimension(col, info))

    return mappings


def _map_ref_area(col: str, info: Dict[str, Any]) -> List[Dict[str, str]]:
    """Map REF_AREA dimension to observationAbout."""
    mappings = []

    area_codes = info.get("area_codes", {})
    likely_format = area_codes.get("likely_format", "custom")

    # Standard mapping for most area codes
    if likely_format in ["ISO-2", "ISO-3"]:
        mappings.append({
            "input": col,
            "property": "observationAbout",
            "value": "country/{" + col + "}"
        })
    elif likely_format == "M49":
        # M49 codes need conversion to ISO
        mappings.append({
            "input": col,
            "property": "observationAbout",
            "value": "#Eval:country_m49_to_iso({" + col + "})"
        })
    else:
        # Custom area codes - may need manual mapping
        mappings.append({
            "input": col,
            "property": "observationAbout",
            "value": "#{" + col + "}"  # Use as-is, may need post-processing
        })

    return mappings


def _map_time_period(col: str, info: Dict[str, Any], time_format: Optional[str]) -> List[Dict[str, str]]:
    """Map TIME_PERIOD dimension to observationDate."""
    mappings = []

    if time_format:
        mappings.append({
            "input": col,
            "property": "observationDate",
            "value": "#{" + col + "}"
        })
    else:
        # Default date mapping
        mappings.append({
            "input": col,
            "property": "observationDate",
            "value": "#{" + col + "}"
        })

    return mappings


def _map_indicator_series(col: str, info: Dict[str, Any]) -> List[Dict[str, str]]:
    """Map INDICATOR/SERIES to measuredProperty and constraint properties."""
    mappings = []

    sample_values = info.get("sample_values", [])

    # If we have specific indicators, create targeted mappings
    if sample_values:
        for indicator in sample_values[:5]:  # Limit to first 5 for example
            # Determine statistical type from indicator name
            stat_type = _determine_statistical_type(str(indicator))
            population_type = _determine_population_type(str(indicator))

            if stat_type:
                mappings.append({
                    "input": str(indicator),
                    "property": "statType",
                    "value": stat_type
                })

            if population_type:
                mappings.append({
                    "input": str(indicator),
                    "property": "populationType",
                    "value": population_type
                })

            # Generic measured property mapping
            mappings.append({
                "input": str(indicator),
                "property": "measuredProperty",
                "value": f"#{_sanitize_property_name(str(indicator))}"
            })

    # Generic mapping for the column
    mappings.append({
        "input": col,
        "property": "measuredProperty",
        "value": "#{" + col + "}"
    })

    return mappings


def _map_generic_dimension(col: str, info: Dict[str, Any]) -> List[Dict[str, str]]:
    """Map generic dimension as constraint property."""
    mappings = []

    # Map as constraint property for StatVar
    property_name = _sanitize_property_name(col)

    mappings.append({
        "input": col,
        "property": property_name,
        "value": "#{" + col + "}"
    })

    return mappings


def _create_measure_mappings(analysis: SdmxAnalysisResult) -> List[Dict[str, str]]:
    """Create mappings for SDMX measures."""
    mappings = []

    for col, info in analysis.measures.items():
        col_upper = col.upper()

        if col_upper in ['OBS_VALUE', 'VALUE']:
            mappings.append({
                "input": col,
                "property": "value",
                "value": "{" + col + "}"
            })
        else:
            # Other numeric measures
            mappings.append({
                "input": col,
                "property": "value",
                "value": "{" + col + "}"
            })

    return mappings


def _create_attribute_mappings(analysis: SdmxAnalysisResult) -> List[Dict[str, str]]:
    """Create mappings for SDMX attributes."""
    mappings = []

    for col, info in analysis.attributes.items():
        col_upper = col.upper()

        if col_upper == 'UNIT_MEASURE':
            mappings.extend(_map_unit_measure(col, info))
        elif col_upper == 'OBS_STATUS':
            mappings.append({
                "input": col,
                "property": "measurementMethod",
                "value": "#{" + col + "}"
            })
        elif col_upper == 'CONF_STATUS':
            mappings.append({
                "input": col,
                "property": "footnote",
                "value": "#{" + col + "}"
            })
        else:
            # Generic attribute mapping
            property_name = _sanitize_property_name(col)
            mappings.append({
                "input": col,
                "property": property_name,
                "value": "#{" + col + "}"
            })

    return mappings


def _map_unit_measure(col: str, info: Dict[str, Any]) -> List[Dict[str, str]]:
    """Map UNIT_MEASURE attribute to unit property."""
    mappings = []

    sample_values = info.get("sample_values", [])

    # Create specific unit mappings
    for unit_code in sample_values:
        unit_str = str(unit_code)
        dc_unit = SDMX_UNIT_CONVERSIONS.get(unit_str, unit_str)

        mappings.append({
            "input": unit_str,
            "property": "unit",
            "value": dc_unit
        })

    # Generic unit mapping
    mappings.append({
        "input": col,
        "property": "unit",
        "value": "#{" + col + "}"
    })

    return mappings


def _create_missing_value_mappings(analysis: SdmxAnalysisResult) -> List[Dict[str, str]]:
    """Create mappings for SDMX missing value codes."""
    mappings = []

    for missing_code in SDMX_MISSING_VALUES:
        mappings.append({
            "input": missing_code,
            "property": "value",
            "value": "#ignore"
        })

    return mappings


def _create_statvar_mappings(analysis: SdmxAnalysisResult) -> List[Dict[str, str]]:
    """Create StatVar construction mappings."""
    mappings = []

    # Determine primary population type
    population_type = _determine_dataset_population_type(analysis)
    if population_type:
        mappings.append({
            "input": "populationType",
            "property": "populationType",
            "value": population_type
        })

    # Add default measured property if not specified
    has_measured_property = any(
        'measuredProperty' in info.get('dc_property', '')
        for info in analysis.dimensions.values()
    )

    if not has_measured_property and analysis.measures:
        # Use first measure as default measured property
        first_measure = next(iter(analysis.measures.keys()))
        sanitized_name = _sanitize_property_name(first_measure)
        mappings.append({
            "input": "measuredProperty",
            "property": "measuredProperty",
            "value": sanitized_name
        })

    return mappings


def _determine_statistical_type(indicator: str) -> Optional[str]:
    """Determine statistical type from indicator name."""
    indicator_upper = indicator.upper()

    for pattern, stat_type in STATISTICAL_TYPE_MAPPINGS.items():
        if pattern in indicator_upper:
            return stat_type

    return None


def _determine_population_type(indicator: str) -> Optional[str]:
    """Determine population type from indicator name."""
    indicator_upper = indicator.upper()

    for pattern, pop_type in POPULATION_TYPE_MAPPINGS.items():
        if pattern in indicator_upper:
            return pop_type

    return None


def _determine_dataset_population_type(analysis: SdmxAnalysisResult) -> Optional[str]:
    """Determine overall population type for the dataset."""

    # Check dataflow name/description
    if analysis.structure_info:
        dataflows = analysis.structure_info.get("dataflows", {})
        for df_info in dataflows.values():
            name = df_info.get("name", "").upper()
            for pattern, pop_type in POPULATION_TYPE_MAPPINGS.items():
                if pattern in name:
                    return pop_type

    # Check dimension values
    for dim_info in analysis.dimensions.values():
        sample_values = dim_info.get("sample_values", [])
        for value in sample_values:
            value_str = str(value).upper()
            for pattern, pop_type in POPULATION_TYPE_MAPPINGS.items():
                if pattern in value_str:
                    return pop_type

    return "Thing"  # Default fallback


def _sanitize_property_name(name: str) -> str:
    """Sanitize property name for Data Commons."""
    # Remove special characters and spaces
    sanitized = re.sub(r'[^a-zA-Z0-9_]', '', name)

    # Ensure it starts with lowercase letter
    if sanitized and sanitized[0].isupper():
        sanitized = sanitized[0].lower() + sanitized[1:]

    return sanitized or "property"


def _write_sdmx_pvmap_csv(mappings: List[Dict[str, str]], output_path: str) -> Dict[str, Any]:
    """Write SDMX PVMap to CSV file."""
    try:
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            fieldnames = ['input', 'property', 'value']
            writer = csv.DictWriter(f, fieldnames=fieldnames)

            writer.writeheader()
            for mapping in mappings:
                writer.writerow(mapping)

        return {
            "status": "success",
            "file": output_path,
            "mappings_written": len(mappings)
        }

    except Exception as e:
        logging.error(f"Failed to write SDMX PVMap CSV: {str(e)}")
        return {"status": "error", "error_message": str(e)}


# Tool function for ADK integration
def create_sdmx_pvmap_from_file(file_path: str, metadata_path: str = None,
                               output_path: str = "pvmap.csv") -> Dict[str, Any]:
    """Create SDMX PVMap from file analysis.

    Args:
        file_path: Path to SDMX file
        metadata_path: Optional metadata file path
        output_path: Output path for PVMap CSV

    Returns:
        Dictionary with creation status
    """
    try:
        # Import here to avoid circular imports
        from sdmx_analyzer import analyze_sdmx_structure

        # Analyze SDMX structure
        analysis_result = analyze_sdmx_structure(file_path, metadata_path)

        if analysis_result["status"] != "success":
            return analysis_result

        # Create PVMap
        analysis = analysis_result["analysis"]
        result = create_sdmx_pvmap(analysis, output_path)

        # Add analysis summary to result
        if result["status"] == "success":
            result["analysis_summary"] = {
                "dimensions": len(analysis.dimensions),
                "measures": len(analysis.measures),
                "attributes": len(analysis.attributes),
                "frequency": analysis.frequency,
                "time_format": analysis.time_format
            }

        return result

    except Exception as e:
        logging.error(f"SDMX PVMap creation from file failed: {str(e)}")
        return {"status": "error", "error_message": str(e)}