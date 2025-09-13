"""
Enhanced metadata detection and generation for ADK Phase 8.

This module provides intelligent detection of:
- Multi-row headers (1-10 rows)
- Merged cells patterns
- Hierarchical headers
- Data boundaries and structure
"""

from __future__ import annotations

import pandas as pd
import numpy as np
import re
from typing import Dict, Any, List, Tuple, Optional
import logging

def detect_header_rows(file_path: str, sample_size: int = 20, max_headers: int = 10) -> Dict[str, Any]:
    """
    Intelligently detect the number of header rows in a CSV file.

    Args:
        file_path: Path to CSV file
        sample_size: Number of rows to analyze (default 20)
        max_headers: Maximum number of header rows to consider (default 10)

    Returns:
        Dict with header_rows count, confidence score, and analysis details
    """
    try:
        # Read sample without any header assumptions
        df_sample = pd.read_csv(file_path, nrows=sample_size, header=None)

        if len(df_sample) == 0:
            return {"status": "error", "error_message": "Empty file"}

        analysis_results = []

        # Analyze each potential header row count
        for header_count in range(1, min(max_headers + 1, len(df_sample))):
            score = _analyze_header_configuration(df_sample, header_count)
            analysis_results.append({
                'header_rows': header_count,
                'score': score['total_score'],
                'details': score
            })

        # Find best configuration
        best_config = max(analysis_results, key=lambda x: x['score'])

        return {
            "status": "success",
            "header_rows": best_config['header_rows'],
            "confidence": best_config['score'],
            "analysis": best_config['details'],
            "all_scores": analysis_results
        }

    except Exception as e:
        logging.error(f"Header row detection failed: {str(e)}")
        return {"status": "error", "error_message": str(e)}


def _analyze_header_configuration(df_sample: pd.DataFrame, header_count: int) -> Dict[str, float]:
    """
    Analyze a specific header configuration and return scoring metrics.

    Args:
        df_sample: Sample dataframe
        header_count: Number of rows to consider as headers

    Returns:
        Dict with various scoring metrics
    """
    if header_count >= len(df_sample):
        return {"total_score": 0.0, "data_rows": 0}

    # Split into header and data sections
    header_section = df_sample.iloc[:header_count]
    data_section = df_sample.iloc[header_count:]

    scores = {}

    # Score 1: Data type consistency in data section
    scores['data_consistency'] = _score_data_consistency(data_section)

    # Score 2: Header completeness (non-empty cells in header)
    scores['header_completeness'] = _score_header_completeness(header_section)

    # Score 3: Numeric data prevalence in data section
    scores['numeric_prevalence'] = _score_numeric_prevalence(data_section)

    # Score 4: Text prevalence in header section
    scores['header_text_prevalence'] = _score_text_prevalence(header_section)

    # Score 5: Empty row detection (penalize empty rows in data)
    scores['empty_row_penalty'] = _score_empty_rows(data_section)

    # Score 6: Column header pattern detection
    scores['header_patterns'] = _score_header_patterns(header_section)

    # Calculate weighted total score
    weights = {
        'data_consistency': 0.25,
        'header_completeness': 0.20,
        'numeric_prevalence': 0.20,
        'header_text_prevalence': 0.15,
        'empty_row_penalty': 0.10,
        'header_patterns': 0.10
    }

    total_score = sum(scores[key] * weights[key] for key in weights)
    scores['total_score'] = total_score
    scores['data_rows'] = len(data_section)

    return scores


def _score_data_consistency(data_section: pd.DataFrame) -> float:
    """Score data type consistency within data columns."""
    if len(data_section) < 2:
        return 0.0

    consistency_scores = []

    for col in data_section.columns:
        column_data = data_section[col].dropna()
        if len(column_data) == 0:
            continue

        # Check if column has consistent data types
        numeric_count = pd.to_numeric(column_data, errors='coerce').notna().sum()
        total_count = len(column_data)

        # Higher score for columns that are either mostly numeric or mostly text
        numeric_ratio = numeric_count / total_count
        consistency = max(numeric_ratio, 1 - numeric_ratio)
        consistency_scores.append(consistency)

    return np.mean(consistency_scores) if consistency_scores else 0.0


def _score_header_completeness(header_section: pd.DataFrame) -> float:
    """Score how complete the header section is (non-empty cells)."""
    if len(header_section) == 0:
        return 0.0

    total_cells = header_section.size
    non_empty_cells = header_section.notna().sum().sum()

    return non_empty_cells / total_cells if total_cells > 0 else 0.0


def _score_numeric_prevalence(data_section: pd.DataFrame) -> float:
    """Score numeric data prevalence in data section."""
    if len(data_section) == 0:
        return 0.0

    numeric_counts = []

    for col in data_section.columns:
        column_data = data_section[col].dropna()
        if len(column_data) == 0:
            continue

        numeric_count = pd.to_numeric(column_data, errors='coerce').notna().sum()
        total_count = len(column_data)
        numeric_ratio = numeric_count / total_count
        numeric_counts.append(numeric_ratio)

    return np.mean(numeric_counts) if numeric_counts else 0.0


def _score_text_prevalence(header_section: pd.DataFrame) -> float:
    """Score text prevalence in header section."""
    if len(header_section) == 0:
        return 0.0

    text_counts = []

    for col in header_section.columns:
        column_data = header_section[col].astype(str).dropna()
        if len(column_data) == 0:
            continue

        # Count non-numeric text entries
        text_count = 0
        for value in column_data:
            if pd.isna(pd.to_numeric(value, errors='coerce')):
                text_count += 1

        text_ratio = text_count / len(column_data)
        text_counts.append(text_ratio)

    return np.mean(text_counts) if text_counts else 0.0


def _score_empty_rows(data_section: pd.DataFrame) -> float:
    """Penalize empty rows in data section."""
    if len(data_section) == 0:
        return 1.0

    empty_rows = data_section.isnull().all(axis=1).sum()
    total_rows = len(data_section)

    # Return inverse ratio (fewer empty rows = higher score)
    return 1.0 - (empty_rows / total_rows)


def _score_header_patterns(header_section: pd.DataFrame) -> float:
    """Score header patterns (detect common header indicators)."""
    if len(header_section) == 0:
        return 0.0

    pattern_scores = []
    header_indicators = [
        r'(?i)(name|id|code|description|title)',
        r'(?i)(date|time|year|month|period)',
        r'(?i)(value|amount|count|total|sum)',
        r'(?i)(percent|rate|ratio|index)',
        r'(?i)(country|region|state|city|location)',
    ]

    # Check each row in header section
    for idx, row in header_section.iterrows():
        row_score = 0.0
        non_null_count = 0

        for value in row:
            if pd.notna(value):
                value_str = str(value).strip()
                non_null_count += 1

                # Check against header patterns
                for pattern in header_indicators:
                    if re.search(pattern, value_str):
                        row_score += 1.0
                        break

        if non_null_count > 0:
            pattern_scores.append(row_score / non_null_count)

    return np.mean(pattern_scores) if pattern_scores else 0.0


def detect_header_columns(file_path: str, header_rows: int = 1) -> Dict[str, Any]:
    """
    Detect which columns are row labels vs data columns.

    Args:
        file_path: Path to CSV file
        header_rows: Number of header rows detected

    Returns:
        Dict with column classification information
    """
    try:
        # Read with detected header rows
        df = pd.read_csv(file_path, header=list(range(header_rows)), nrows=50)

        if header_rows > 1:
            # Flatten multi-level headers for analysis
            df.columns = [' '.join(col).strip() if isinstance(col, tuple) else str(col)
                         for col in df.columns]

        column_analysis = {}
        data_columns = []
        index_columns = []

        for col in df.columns:
            col_data = df[col].dropna()
            if len(col_data) == 0:
                continue

            # Analyze column characteristics
            analysis = _analyze_column_type(col_data, str(col))
            column_analysis[col] = analysis

            if analysis['is_index_column']:
                index_columns.append(col)
            else:
                data_columns.append(col)

        return {
            "status": "success",
            "total_columns": len(df.columns),
            "data_columns": data_columns,
            "index_columns": index_columns,
            "column_analysis": column_analysis,
            "header_columns": len(index_columns) if index_columns else 0
        }

    except Exception as e:
        logging.error(f"Header column detection failed: {str(e)}")
        return {"status": "error", "error_message": str(e)}


def _analyze_column_type(col_data: pd.Series, col_name: str) -> Dict[str, Any]:
    """
    Analyze individual column to determine if it's an index/label column or data column.

    Args:
        col_data: Column data series
        col_name: Column name

    Returns:
        Dict with column type analysis
    """
    # Calculate basic stats
    numeric_count = pd.to_numeric(col_data, errors='coerce').notna().sum()
    total_count = len(col_data)
    numeric_ratio = numeric_count / total_count if total_count > 0 else 0

    # Check for unique values (potential identifier column)
    unique_ratio = len(col_data.unique()) / total_count if total_count > 0 else 0

    # Check column name patterns
    name_patterns = {
        'geographic': r'(?i)(country|region|state|city|location|place|geo)',
        'temporal': r'(?i)(date|time|year|month|period|day)',
        'identifier': r'(?i)(id|code|name|label|key)',
        'measure': r'(?i)(value|amount|count|total|sum|percent|rate)'
    }

    name_type = 'unknown'
    for pattern_type, pattern in name_patterns.items():
        if re.search(pattern, col_name):
            name_type = pattern_type
            break

    # Determine if this is likely an index column
    is_index_column = (
        (unique_ratio > 0.8) or  # High uniqueness
        (numeric_ratio < 0.3 and name_type in ['geographic', 'identifier']) or  # Non-numeric with identifying pattern
        (name_type == 'temporal')  # Temporal columns are often indices
    )

    return {
        'numeric_ratio': numeric_ratio,
        'unique_ratio': unique_ratio,
        'name_type': name_type,
        'is_index_column': is_index_column,
        'total_values': total_count
    }


def detect_hierarchical_headers(file_path: str, header_rows: int) -> Dict[str, Any]:
    """
    Detect hierarchical header structure in multi-row headers.

    Args:
        file_path: Path to CSV file
        header_rows: Number of header rows

    Returns:
        Dict with hierarchical structure information
    """
    try:
        if header_rows < 2:
            return {"status": "success", "hierarchical": False}

        # Read header rows only
        df_headers = pd.read_csv(file_path, nrows=header_rows, header=None)

        hierarchy_info = {
            "hierarchical": True,
            "levels": header_rows,
            "structure": {}
        }

        # Analyze each column for hierarchy patterns
        for col_idx in range(len(df_headers.columns)):
            column_values = df_headers.iloc[:, col_idx].fillna('').astype(str)

            # Find repeated values (indicating hierarchy)
            repeated_values = []
            current_value = ''
            repeat_count = 0

            for value in column_values:
                if value == current_value:
                    repeat_count += 1
                else:
                    if repeat_count > 1:
                        repeated_values.append({
                            'value': current_value,
                            'count': repeat_count
                        })
                    current_value = value
                    repeat_count = 1

            hierarchy_info["structure"][f"column_{col_idx}"] = {
                "values": column_values.tolist(),
                "repeated_patterns": repeated_values
            }

        return {"status": "success", **hierarchy_info}

    except Exception as e:
        logging.error(f"Hierarchical header detection failed: {str(e)}")
        return {"status": "error", "error_message": str(e)}


def get_enhanced_file_structure(file_path: str) -> Dict[str, Any]:
    """
    Get comprehensive file structure analysis combining all detection methods.

    Args:
        file_path: Path to CSV file

    Returns:
        Complete file structure analysis
    """
    try:
        # Step 1: Detect header rows
        header_detection = detect_header_rows(file_path)
        if header_detection.get("status") != "success":
            return header_detection

        header_rows = header_detection["header_rows"]

        # Step 2: Detect header columns
        column_detection = detect_header_columns(file_path, header_rows)
        if column_detection.get("status") != "success":
            return column_detection

        # Step 3: Detect hierarchical structure
        hierarchy_detection = detect_hierarchical_headers(file_path, header_rows)

        # Step 4: Get full file dimensions
        full_df = pd.read_csv(file_path, header=list(range(header_rows)))
        total_rows = len(full_df) + header_rows  # Include header rows in total
        total_columns = len(full_df.columns)

        return {
            "status": "success",
            "file_path": file_path,
            "header_rows": header_rows,
            "header_confidence": header_detection["confidence"],
            "total_rows": total_rows,
            "total_columns": total_columns,
            "data_rows": total_rows - header_rows,
            "data_columns": len(column_detection["data_columns"]),
            "index_columns": len(column_detection["index_columns"]),
            "column_classification": column_detection["column_analysis"],
            "hierarchical_headers": hierarchy_detection.get("hierarchical", False),
            "hierarchy_details": hierarchy_detection.get("structure", {}),
            "recommended_config": {
                "header_rows": header_rows,
                "mapped_rows": total_rows - header_rows,
                "mapped_columns": total_columns,
                "header_columns": column_detection["header_columns"]
            }
        }

    except Exception as e:
        logging.error(f"Enhanced file structure analysis failed: {str(e)}")
        return {"status": "error", "error_message": str(e)}