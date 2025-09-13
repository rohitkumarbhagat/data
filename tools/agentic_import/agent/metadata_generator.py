from __future__ import annotations

import csv
import os
import pandas as pd
from typing import Dict, Any, List, Optional

import logging

try:
    from google.adk.agents import LlmAgent
    from absl import logging
    ADK_AVAILABLE = True
except ImportError:
    import logging
    ADK_AVAILABLE = False

# Import enhanced modules
try:
    from enhanced_metadata import get_enhanced_file_structure, detect_header_rows
    from date_detector import detect_date_formats
    from aggregation_analyzer import detect_aggregation_needs
    from metadata_validator import validate_metadata_comprehensive, infer_metadata_parameters
    ENHANCED_MODULES_AVAILABLE = True
except ImportError:
    ENHANCED_MODULES_AVAILABLE = False
    logging.warning("Enhanced metadata modules not available, using basic functionality")


def detect_file_structure(file_path: str, use_enhanced: bool = True) -> Dict[str, Any]:
    """Detect CSV file structure for metadata configuration.

    Args:
        file_path: Path to CSV file
        use_enhanced: Whether to use enhanced detection (default: True)

    Returns:
        Dictionary with file structure information
    """
    try:
        # Use enhanced detection if available and requested
        if use_enhanced and ENHANCED_MODULES_AVAILABLE:
            enhanced_result = get_enhanced_file_structure(file_path)
            if enhanced_result.get("status") == "success":
                return enhanced_result

        # Fallback to basic detection
        # Read first few rows to detect structure
        df = pd.read_csv(file_path, nrows=10)

        # Detect header rows (basic method)
        header_rows = 1
        if ENHANCED_MODULES_AVAILABLE:
            try:
                header_detection = detect_header_rows(file_path)
                if header_detection.get("status") == "success":
                    header_rows = header_detection["header_rows"]
            except Exception:
                pass  # Fall back to default

        # Get total rows and columns
        full_df = pd.read_csv(file_path)
        total_rows = len(full_df)
        total_columns = len(full_df.columns)

        return {
            "status": "success",
            "header_rows": header_rows,
            "total_rows": total_rows,
            "total_columns": total_columns,
            "mapped_rows": total_rows - header_rows,
            "mapped_columns": total_columns,
            "enhanced_detection_used": use_enhanced and ENHANCED_MODULES_AVAILABLE
        }

    except Exception as e:
        logging.error(f"File structure detection failed: {str(e)}")
        return {"status": "error", "error_message": str(e)}


def generate_metadata_config(file_path: str, analysis_result: Dict[str, Any] = None,
                          pvmap_result: Dict[str, Any] = None, use_enhanced: bool = True) -> Dict[str, Any]:
    """Generate metadata configuration from file analysis.

    Args:
        file_path: Path to CSV file
        analysis_result: Optional analysis result from analyzer.py
        pvmap_result: Optional PVMap analysis result
        use_enhanced: Whether to use enhanced generation (default: True)

    Returns:
        Dictionary with metadata configuration
    """
    try:
        # Use enhanced generation if available
        if use_enhanced and ENHANCED_MODULES_AVAILABLE:
            return generate_enhanced_metadata_config(file_path, analysis_result, pvmap_result)

        # Fallback to basic generation
        # Detect file structure
        structure = detect_file_structure(file_path, use_enhanced=False)
        if structure.get("status") != "success":
            return structure

        # Default output columns for Data Commons
        output_columns = [
            "observationAbout",
            "observationDate",
            "value",
            "variableMeasured",
            "unit",
            "scalingFactor"
        ]

        # Create metadata configuration
        config = {
            "header_rows": structure["header_rows"],
            "mapped_rows": structure["mapped_rows"],
            "mapped_columns": structure["mapped_columns"],
            "output_columns": ",".join(output_columns)
        }

        # Add optional parameters based on analysis
        if analysis_result and analysis_result.get("status") == "success":
            column_analysis = analysis_result.get("column_analysis", {})

            # Check if we have location data
            has_location = any(info.get("dc_suggestion") == "geoId"
                             for info in column_analysis.values())
            if has_location:
                config["places_within"] = "country/USA"  # Default assumption

        return {"status": "success", "config": config}

    except Exception as e:
        logging.error(f"Metadata config generation failed: {str(e)}")
        return {"status": "error", "error_message": str(e)}


def write_metadata_csv(config: Dict[str, Any], output_path: str) -> Dict[str, Any]:
    """Write metadata configuration to CSV file.
    
    Args:
        config: Configuration dictionary
        output_path: Path to output metadata.csv file
        
    Returns:
        Dictionary with success/error status
    """
    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # Write header
            writer.writerow(['parameter', 'value'])
            
            # Write configuration parameters
            for param, value in config.items():
                writer.writerow([param, value])
        
        return {
            "status": "success",
            "file": output_path,
            "parameters": len(config)
        }
        
    except Exception as e:
        logging.error(f"Metadata CSV writing failed: {str(e)}")
        return {"status": "error", "error_message": str(e)}


def validate_metadata_config(config: Dict[str, Any], file_path: Optional[str] = None,
                          pvmap_path: Optional[str] = None, use_enhanced: bool = True) -> Dict[str, Any]:
    """Validate metadata configuration for completeness.

    Args:
        config: Configuration dictionary
        file_path: Optional path to input file for validation
        pvmap_path: Optional path to PVMap file for validation
        use_enhanced: Whether to use enhanced validation (default: True)

    Returns:
        Validation results
    """
    try:
        # Use enhanced validation if available
        if use_enhanced and ENHANCED_MODULES_AVAILABLE:
            return validate_metadata_comprehensive(config, file_path, pvmap_path)

        # Fallback to basic validation
        required_params = ["output_columns"]
        issues = []

        for param in required_params:
            if param not in config or not config[param]:
                issues.append(f"Missing required parameter: {param}")

        # Validate output_columns format
        if "output_columns" in config:
            columns = config["output_columns"].split(",")
            if len(columns) < 3:
                issues.append("output_columns should have at least 3 columns")

        return {
            "status": "success",
            "valid": len(issues) == 0,
            "issues": issues,
            "warnings": [],
            "suggestions": [],
            "parameter_count": len(config),
            "enhanced_validation_used": False
        }

    except Exception as e:
        logging.error(f"Metadata config validation failed: {str(e)}")
        return {"status": "error", "error_message": str(e)}


# Enhanced metadata generation functions (only available if enhanced modules are loaded)
def generate_enhanced_metadata_config(file_path: str, analysis_result: Dict[str, Any] = None,
                                   pvmap_result: Dict[str, Any] = None) -> Dict[str, Any]:
    """Generate enhanced metadata configuration using all available modules.

    Args:
        file_path: Path to CSV file
        analysis_result: Optional analysis result from analyzer.py
        pvmap_result: Optional PVMap analysis result

    Returns:
        Dictionary with enhanced metadata configuration
    """
    if not ENHANCED_MODULES_AVAILABLE:
        return {"status": "error", "error_message": "Enhanced modules not available"}

    try:
        # Step 1: Enhanced file structure analysis
        structure_result = get_enhanced_file_structure(file_path)
        if structure_result.get("status") != "success":
            return structure_result

        # Step 2: Date format detection
        date_result = detect_date_formats(file_path, structure_result["header_rows"])

        # Step 3: Aggregation analysis
        aggregation_result = detect_aggregation_needs(file_path, pvmap_result, structure_result["header_rows"])

        # Step 4: Infer additional parameters
        inference_result = infer_metadata_parameters(file_path, structure_result, pvmap_result)
        if inference_result.get("status") != "success":
            return inference_result

        # Step 5: Build comprehensive configuration
        config = inference_result["inferred_config"].copy()

        # Add date configuration
        if date_result.get("status") == "success" and date_result.get("configuration", {}).get("has_date_columns"):
            date_config = date_result["configuration"]["config"]
            config.update(date_config)

        # Add aggregation configuration
        if aggregation_result.get("status") == "success" and aggregation_result.get("needs_aggregation"):
            agg_config = aggregation_result["recommended_config"]
            config.update(agg_config)

        return {
            "status": "success",
            "config": config,
            "analysis_details": {
                "structure_analysis": structure_result,
                "date_analysis": date_result,
                "aggregation_analysis": aggregation_result,
                "inference_confidence": inference_result.get("confidence", 0.0)
            },
            "enhanced_features_used": True
        }

    except Exception as e:
        logging.error(f"Enhanced metadata config generation failed: {str(e)}")
        return {"status": "error", "error_message": str(e)}


def analyze_csv_comprehensively(file_path: str, pvmap_path: Optional[str] = None) -> Dict[str, Any]:
    """Perform comprehensive CSV analysis using all available enhanced modules.

    Args:
        file_path: Path to CSV file
        pvmap_path: Optional path to PVMap file

    Returns:
        Complete analysis results
    """
    if not ENHANCED_MODULES_AVAILABLE:
        return {"status": "error", "error_message": "Enhanced modules not available"}

    try:
        analysis_results = {}

        # File structure analysis
        analysis_results["structure"] = get_enhanced_file_structure(file_path)

        header_rows = 1
        if analysis_results["structure"].get("status") == "success":
            header_rows = analysis_results["structure"]["header_rows"]

        # Date format analysis
        analysis_results["dates"] = detect_date_formats(file_path, header_rows)

        # Aggregation analysis
        pvmap_data = None
        if pvmap_path:
            try:
                pvmap_df = pd.read_csv(pvmap_path)
                pvmap_data = {"pvmap_df": pvmap_df}
            except Exception:
                pass

        analysis_results["aggregation"] = detect_aggregation_needs(file_path, pvmap_data, header_rows)

        # Parameter inference
        analysis_results["inference"] = infer_metadata_parameters(
            file_path, analysis_results["structure"], pvmap_data
        )

        return {
            "status": "success",
            "file_path": file_path,
            "analysis_results": analysis_results,
            "summary": {
                "header_rows": header_rows,
                "has_date_columns": analysis_results["dates"].get("analysis", {}).get("date_columns_found", 0) > 0,
                "needs_aggregation": analysis_results["aggregation"].get("needs_aggregation", False),
                "inference_confidence": analysis_results["inference"].get("confidence", 0.0)
            }
        }

    except Exception as e:
        logging.error(f"Comprehensive CSV analysis failed: {str(e)}")
        return {"status": "error", "error_message": str(e)}


# Metadata Generator Agent (only if ADK is available)
if ADK_AVAILABLE:
    # Build tool list based on available modules
    base_tools = [detect_file_structure, generate_metadata_config, validate_metadata_config, write_metadata_csv]

    if ENHANCED_MODULES_AVAILABLE:
        enhanced_tools = [generate_enhanced_metadata_config, analyze_csv_comprehensively]
        all_tools = base_tools + enhanced_tools

        instruction = (
            "Generate enhanced metadata configuration for Data Commons processing. "
            "Use analyze_csv_comprehensively for complete file analysis. "
            "Use generate_enhanced_metadata_config for intelligent configuration generation with date detection, aggregation rules, and parameter inference. "
            "Use validate_metadata_config for comprehensive validation with file and PVMap checking. "
            "Use write_metadata_csv to save configuration to file. "
            "Fall back to basic functions (detect_file_structure, generate_metadata_config) if enhanced analysis fails."
        )
    else:
        all_tools = base_tools
        instruction = (
            "Generate metadata configuration for Data Commons processing. "
            "Use detect_file_structure to analyze the CSV file structure. "
            "Use generate_metadata_config to create processor configuration. "
            "Use validate_metadata_config to check configuration completeness. "
            "Use write_metadata_csv to save configuration to file."
        )

    metadata_generator = LlmAgent(
        name="metadata_generator",
        model="gemini-2.0-flash",
        description="Generates metadata.csv configuration for statvar processor with enhanced capabilities",
        instruction=instruction,
        tools=all_tools
    )
else:
    metadata_generator = None