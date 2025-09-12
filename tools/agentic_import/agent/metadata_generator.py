from __future__ import annotations

import csv
import os
import pandas as pd
from typing import Dict, Any, List

import logging

try:
    from google.adk.agents import LlmAgent
    from absl import logging
    ADK_AVAILABLE = True
except ImportError:
    import logging
    ADK_AVAILABLE = False


def detect_file_structure(file_path: str) -> Dict[str, Any]:
    """Detect CSV file structure for metadata configuration.
    
    Args:
        file_path: Path to CSV file
        
    Returns:
        Dictionary with file structure information
    """
    try:
        # Read first few rows to detect structure
        df = pd.read_csv(file_path, nrows=10)
        
        # Detect header rows (assume 1 for now - could be enhanced)
        header_rows = 1
        
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
            "mapped_columns": total_columns
        }
        
    except Exception as e:
        logging.error(f"File structure detection failed: {str(e)}")
        return {"status": "error", "error_message": str(e)}


def generate_metadata_config(file_path: str, analysis_result: Dict[str, Any] = None) -> Dict[str, Any]:
    """Generate metadata configuration from file analysis.
    
    Args:
        file_path: Path to CSV file
        analysis_result: Optional analysis result from analyzer.py
        
    Returns:
        Dictionary with metadata configuration
    """
    try:
        # Detect file structure
        structure = detect_file_structure(file_path)
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


def validate_metadata_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Validate metadata configuration for completeness.
    
    Args:
        config: Configuration dictionary
        
    Returns:
        Validation results
    """
    try:
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
            "parameter_count": len(config)
        }
        
    except Exception as e:
        logging.error(f"Metadata config validation failed: {str(e)}")
        return {"status": "error", "error_message": str(e)}


# Metadata Generator Agent (only if ADK is available)
if ADK_AVAILABLE:
    metadata_generator = LlmAgent(
        name="metadata_generator",
        model="gemini-2.0-flash",
        description="Generates metadata.csv configuration for statvar processor",
        instruction=(
            "Generate metadata configuration for Data Commons processing. "
            "Use detect_file_structure to analyze the CSV file structure. "
            "Use generate_metadata_config to create processor configuration. "
            "Use validate_metadata_config to check configuration completeness. "
            "Use write_metadata_csv to save configuration to file."
        ),
        tools=[detect_file_structure, generate_metadata_config, validate_metadata_config, write_metadata_csv]
    )
else:
    metadata_generator = None