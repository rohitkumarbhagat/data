from __future__ import annotations

import pandas as pd
from google.adk.agents import LlmAgent
from absl import logging
from typing import Dict, Any, List

from .simple_agent import read_csv_sample


def analyze_column_types(file_path: str, sample_rows: int = 50) -> Dict[str, Any]:
    """Analyze column types in CSV file.
    
    Args:
        file_path: Path to CSV file
        sample_rows: Number of rows to analyze
        
    Returns:
        Dictionary with column analysis results
    """
    try:
        df = pd.read_csv(file_path, nrows=sample_rows)
        analysis = {}
        
        for col in df.columns:
            col_data = df[col].dropna()
            if len(col_data) == 0:
                analysis[col] = {"type": "empty", "dc_suggestion": None}
                continue
                
            # Check for year pattern first (before numeric)
            if col.lower() in ['year', 'date'] and col_data.astype(str).str.match(r'^\d{4}$').any():
                analysis[col] = {"type": "year", "dc_suggestion": "observationDate"}
                continue
                
            # Check for numeric
            numeric_count = pd.to_numeric(col_data, errors='coerce').notna().sum()
            if numeric_count / len(col_data) > 0.9:
                analysis[col] = {"type": "numeric", "dc_suggestion": "measuredProperty"}
                continue
                
            # Check for categorical (less than 50 unique values)
            if len(col_data.unique()) < 50:
                # Location columns
                if any(term in col.lower() for term in ['location', 'place', 'state', 'country']):
                    analysis[col] = {"type": "categorical", "dc_suggestion": "geoId"}
                else:
                    analysis[col] = {"type": "categorical", "dc_suggestion": "constraint"}
            else:
                analysis[col] = {"type": "text", "dc_suggestion": None}
                
        return {"status": "success", "column_analysis": analysis}
        
    except Exception as e:
        logging.error(f"Column analysis failed: {str(e)}")
        return {"status": "error", "error_message": str(e)}


def suggest_dc_mappings(column_analysis: Dict[str, Any]) -> Dict[str, Any]:
    """Suggest Data Commons property mappings based on column analysis.
    
    Args:
        column_analysis: Results from analyze_column_types
        
    Returns:
        Dictionary with suggested DC mappings
    """
    try:
        analysis = column_analysis.get("column_analysis", {})
        
        # Find potential population type
        population_type = "Person"  # Default
        for col, info in analysis.items():
            if "population" in col.lower() or "employment" in col.lower():
                population_type = "Person"
                break
                
        # Find constraint properties
        constraint_props = []
        for col, info in analysis.items():
            if info.get("dc_suggestion") == "constraint":
                constraint_props.append(col)
                
        # Find measured properties
        measured_props = []
        for col, info in analysis.items():
            if info.get("dc_suggestion") == "measuredProperty":
                measured_props.append(col)
                
        mappings = {
            "populationType": population_type,
            "statType": "measuredValue",
            "constraintProperties": constraint_props,
            "measuredProperties": measured_props
        }
        
        return {"status": "success", "mappings": mappings}
        
    except Exception as e:
        logging.error(f"DC mapping suggestion failed: {str(e)}")
        return {"status": "error", "error_message": str(e)}


# Data Analyzer Agent
data_analyzer = LlmAgent(
    name="data_analyzer",
    model="gemini-2.0-flash", 
    description="Analyzes CSV data structure and suggests Data Commons mappings",
    instruction=(
        "Analyze the CSV file structure and content. "
        "Use analyze_column_types to understand column types and patterns. "
        "Use suggest_dc_mappings to recommend Data Commons property mappings. "
        "Return structured analysis suitable for PVMap generation."
    ),
    tools=[read_csv_sample, analyze_column_types, suggest_dc_mappings]
)