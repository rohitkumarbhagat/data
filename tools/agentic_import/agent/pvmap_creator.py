from __future__ import annotations

import csv
import os
from typing import Dict, Any, List

import logging

try:
    from google.adk.agents import LlmAgent
    from absl import logging
    ADK_AVAILABLE = True
except ImportError:
    import logging
    ADK_AVAILABLE = False


def create_pv_mappings(analysis_result: Dict[str, Any]) -> Dict[str, Any]:
    """Create property-value mappings from column analysis.
    
    Args:
        analysis_result: Result from analyzer.py column analysis
        
    Returns:
        Dictionary with PV mappings
    """
    try:
        if analysis_result.get("status") != "success":
            return {"status": "error", "error_message": "Invalid analysis input"}
            
        column_analysis = analysis_result.get("column_analysis", {})
        mappings = []
        
        for column, info in column_analysis.items():
            dc_suggestion = info.get("dc_suggestion")
            col_type = info.get("type")
            
            if dc_suggestion == "observationDate":
                mappings.append({
                    "input": column,
                    "property": "observationDate", 
                    "value": f"#Format:{{$col|YYYY}}"
                })
            elif dc_suggestion == "geoId":
                mappings.append({
                    "input": column,
                    "property": "geoId",
                    "value": f"#Format:{{$col|text_to_place}}"
                })
            elif dc_suggestion == "measuredProperty":
                # Generate StatVar name from column
                statvar_name = f"Count_{column.replace(' ', '').replace('_', '')}"
                mappings.append({
                    "input": column,
                    "property": "measuredProperty",
                    "value": statvar_name
                })
            elif dc_suggestion == "constraint":
                # Use column name as constraint property
                constraint_prop = column.lower().replace(' ', '').replace('_', '')
                mappings.append({
                    "input": column,
                    "property": "constraintProperty",
                    "value": constraint_prop
                })
        
        # Add default population type
        mappings.append({
            "input": "*",
            "property": "populationType", 
            "value": "Person"
        })
        
        # Add default stat type
        mappings.append({
            "input": "*",
            "property": "statType",
            "value": "measuredValue"
        })
        
        return {"status": "success", "mappings": mappings}
        
    except Exception as e:
        logging.error(f"PV mapping creation failed: {str(e)}")
        return {"status": "error", "error_message": str(e)}


def write_pvmap_csv(mappings: List[Dict[str, str]], output_path: str) -> Dict[str, Any]:
    """Write PV mappings to CSV file.
    
    Args:
        mappings: List of mapping dictionaries with input/property/value
        output_path: Path to output CSV file
        
    Returns:
        Dictionary with success/error status
    """
    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            fieldnames = ['input', 'property', 'value']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for mapping in mappings:
                writer.writerow(mapping)
        
        return {"status": "success", "file": output_path, "count": len(mappings)}
        
    except Exception as e:
        logging.error(f"PVMap CSV writing failed: {str(e)}")
        return {"status": "error", "error_message": str(e)}


def validate_pvmap_structure(mappings: List[Dict[str, str]]) -> Dict[str, Any]:
    """Validate PVMap structure for Data Commons compatibility.
    
    Args:
        mappings: List of mapping dictionaries
        
    Returns:
        Validation results
    """
    try:
        required_fields = ["input", "property", "value"]
        issues = []
        
        for i, mapping in enumerate(mappings):
            for field in required_fields:
                if field not in mapping or not mapping[field]:
                    issues.append(f"Row {i+1}: Missing or empty '{field}'")
        
        # Check for required properties
        properties = [m.get("property") for m in mappings]
        if "populationType" not in properties:
            issues.append("Missing required populationType mapping")
        if "statType" not in properties:
            issues.append("Missing required statType mapping")
            
        return {
            "status": "success",
            "valid": len(issues) == 0,
            "issues": issues,
            "mapping_count": len(mappings)
        }
        
    except Exception as e:
        logging.error(f"PVMap validation failed: {str(e)}")
        return {"status": "error", "error_message": str(e)}


# PVMap Creator Agent (only if ADK is available)
if ADK_AVAILABLE:
    pvmap_creator = LlmAgent(
        name="pvmap_creator",
        model="gemini-2.0-flash",
        description="Creates property-value mappings for Data Commons from column analysis",
        instruction=(
            "Create PV mappings for Data Commons processing. "
            "Use create_pv_mappings to generate mappings from column analysis. "
            "Use validate_pvmap_structure to check mapping validity. "
            "Use write_pvmap_csv to save mappings to file. "
            "Follow Data Commons schema conventions for property naming."
        ),
        tools=[create_pv_mappings, write_pvmap_csv, validate_pvmap_structure]
    )
else:
    pvmap_creator = None