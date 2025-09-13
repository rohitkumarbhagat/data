"""
Aggregation analysis module for ADK Phase 8.

This module detects duplicate observations and generates intelligent aggregation rules
to prevent processing errors and ensure data quality.
"""

from __future__ import annotations

import pandas as pd
import numpy as np
import re
from typing import Dict, Any, List, Tuple, Optional, Set
import logging

class AggregationAnalyzer:
    """Analyzer for detecting duplicates and generating aggregation strategies."""

    def __init__(self):
        """Initialize aggregation analyzer with predefined patterns."""
        self.measure_patterns = self._initialize_measure_patterns()
        self.aggregation_methods = self._initialize_aggregation_methods()

    def _initialize_measure_patterns(self) -> Dict[str, List[str]]:
        """Initialize patterns for different types of measures."""
        return {
            'additive': [
                r'(?i)(count|total|sum|number|amount|volume|quantity)',
                r'(?i)(population|people|individuals|persons)',
                r'(?i)(revenue|income|sales|earnings|expenditure)',
                r'(?i)(area|size|length|width|height|distance)',
                r'(?i)(weight|mass|tons|kg|pounds)',
                r'(?i)(frequency|occurrences|instances)'
            ],
            'intensive': [
                r'(?i)(rate|ratio|percent|percentage|proportion)',
                r'(?i)(average|mean|median|per|density)',
                r'(?i)(index|score|ranking|grade)',
                r'(?i)(price|cost|value_per|unit)',
                r'(?i)(temperature|degrees|celsius|fahrenheit)',
                r'(?i)(speed|velocity|acceleration)'
            ],
            'categorical': [
                r'(?i)(status|state|type|category|class)',
                r'(?i)(name|title|description|label)',
                r'(?i)(code|id|identifier|key)',
                r'(?i)(gender|sex|race|ethnicity)',
                r'(?i)(yes|no|true|false|boolean)',
                r'(?i)(level|grade|tier|rank)'
            ],
            'temporal_point': [
                r'(?i)(latest|current|as_of|snapshot)',
                r'(?i)(balance|stock|inventory|outstanding)',
                r'(?i)(position|status_at|value_at)'
            ]
        }

    def _initialize_aggregation_methods(self) -> Dict[str, Dict[str, Any]]:
        """Initialize aggregation methods for different measure types."""
        return {
            'sum': {
                'description': 'Sum values (for additive measures)',
                'applicable_to': ['additive'],
                'pandas_method': 'sum',
                'handles_nulls': True
            },
            'mean': {
                'description': 'Average values (for intensive measures)',
                'applicable_to': ['intensive'],
                'pandas_method': 'mean',
                'handles_nulls': True
            },
            'last': {
                'description': 'Take last/most recent value',
                'applicable_to': ['temporal_point', 'categorical'],
                'pandas_method': 'last',
                'handles_nulls': False
            },
            'first': {
                'description': 'Take first value',
                'applicable_to': ['categorical'],
                'pandas_method': 'first',
                'handles_nulls': False
            },
            'max': {
                'description': 'Maximum value',
                'applicable_to': ['additive', 'intensive'],
                'pandas_method': 'max',
                'handles_nulls': True
            },
            'min': {
                'description': 'Minimum value',
                'applicable_to': ['additive', 'intensive'],
                'pandas_method': 'min',
                'handles_nulls': True
            },
            'count': {
                'description': 'Count non-null values',
                'applicable_to': ['categorical'],
                'pandas_method': 'count',
                'handles_nulls': False
            }
        }

    def analyze_duplicates(self, file_path: str, pvmap_data: Optional[Dict[str, Any]] = None,
                          header_rows: int = 1, sample_size: int = 1000) -> Dict[str, Any]:
        """
        Analyze file for duplicate observations and aggregation needs.

        Args:
            file_path: Path to CSV file
            pvmap_data: Optional PVMap analysis results
            header_rows: Number of header rows
            sample_size: Number of rows to analyze

        Returns:
            Complete duplicate analysis and aggregation recommendations
        """
        try:
            # Read data
            df = pd.read_csv(file_path, header=list(range(header_rows)), nrows=sample_size)

            if header_rows > 1:
                # Flatten multi-level headers
                df.columns = [' '.join(col).strip() if isinstance(col, tuple) else str(col)
                             for col in df.columns]

            # Identify key columns (dimensions) and measure columns
            column_analysis = self._classify_columns(df, pvmap_data)

            # Detect duplicates
            duplicate_analysis = self._detect_duplicates(df, column_analysis)

            # Generate aggregation strategies
            aggregation_strategy = self._generate_aggregation_strategy(
                df, column_analysis, duplicate_analysis
            )

            # Validate strategy
            validation_result = self._validate_aggregation_strategy(
                df, aggregation_strategy
            )

            return {
                "status": "success",
                "file_path": file_path,
                "total_rows_analyzed": len(df),
                "column_classification": column_analysis,
                "duplicate_analysis": duplicate_analysis,
                "aggregation_strategy": aggregation_strategy,
                "validation": validation_result,
                "needs_aggregation": duplicate_analysis["has_duplicates"],
                "recommended_config": self._generate_metadata_config(aggregation_strategy)
            }

        except Exception as e:
            logging.error(f"Aggregation analysis failed: {str(e)}")
            return {"status": "error", "error_message": str(e)}

    def _classify_columns(self, df: pd.DataFrame, pvmap_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Classify columns into dimensions and measures."""
        column_classification = {
            "dimensions": [],
            "measures": [],
            "temporal": [],
            "geographic": [],
            "categorical": [],
            "unknown": []
        }

        for col in df.columns:
            col_info = self._analyze_column_for_aggregation(df[col], str(col), pvmap_data)

            # Classify based on analysis
            if col_info["is_temporal"]:
                column_classification["temporal"].append(col)
                column_classification["dimensions"].append(col)
            elif col_info["is_geographic"]:
                column_classification["geographic"].append(col)
                column_classification["dimensions"].append(col)
            elif col_info["measure_type"] == "categorical":
                column_classification["categorical"].append(col)
                column_classification["dimensions"].append(col)
            elif col_info["measure_type"] in ["additive", "intensive", "temporal_point"]:
                column_classification["measures"].append(col)
            else:
                column_classification["unknown"].append(col)

        return column_classification

    def _analyze_column_for_aggregation(self, column_data: pd.Series, column_name: str,
                                      pvmap_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Analyze individual column for aggregation purposes."""
        # Basic statistics
        non_null_data = column_data.dropna()
        if len(non_null_data) == 0:
            return {"measure_type": "unknown", "is_temporal": False, "is_geographic": False}

        # Check if numeric
        numeric_data = pd.to_numeric(non_null_data, errors='coerce')
        is_numeric = numeric_data.notna().sum() / len(non_null_data) > 0.8

        # Check for temporal patterns
        is_temporal = self._is_temporal_column(column_name, non_null_data)

        # Check for geographic patterns
        is_geographic = self._is_geographic_column(column_name, non_null_data)

        # Determine measure type
        measure_type = self._determine_measure_type(column_name, non_null_data, is_numeric)

        # Check uniqueness (high uniqueness suggests dimension)
        unique_ratio = len(non_null_data.unique()) / len(non_null_data)

        return {
            "measure_type": measure_type,
            "is_numeric": is_numeric,
            "is_temporal": is_temporal,
            "is_geographic": is_geographic,
            "unique_ratio": unique_ratio,
            "total_values": len(non_null_data),
            "null_values": len(column_data) - len(non_null_data)
        }

    def _is_temporal_column(self, column_name: str, data: pd.Series) -> bool:
        """Check if column represents temporal data."""
        temporal_patterns = [
            r'(?i)(date|time|year|month|day|period|quarter|fiscal|academic|week)',
            r'(?i)(when|as_of|effective|timestamp)'
        ]

        # Check column name
        for pattern in temporal_patterns:
            if re.search(pattern, column_name):
                return True

        # Check data patterns (sample first few values)
        sample_values = data.head(10).astype(str)
        date_like_count = 0

        for value in sample_values:
            # Basic date pattern check
            if re.match(r'^\d{4}', value) or re.search(r'\d{4}', value):
                date_like_count += 1

        return date_like_count / len(sample_values) > 0.5

    def _is_geographic_column(self, column_name: str, data: pd.Series) -> bool:
        """Check if column represents geographic data."""
        geo_patterns = [
            r'(?i)(country|region|state|city|location|place|geo)',
            r'(?i)(county|province|territory|district|zip|postal)',
            r'(?i)(latitude|longitude|lat|lng|coord)'
        ]

        # Check column name
        for pattern in geo_patterns:
            if re.search(pattern, column_name):
                return True

        # Check for common geographic values
        sample_values = data.head(20).astype(str).str.upper()
        geo_indicators = ['USA', 'US', 'UNITED STATES', 'COUNTRY', 'STATE', 'CITY']

        geo_count = 0
        for value in sample_values:
            for indicator in geo_indicators:
                if indicator in value:
                    geo_count += 1
                    break

        return geo_count / len(sample_values) > 0.2

    def _determine_measure_type(self, column_name: str, data: pd.Series, is_numeric: bool) -> str:
        """Determine the measure type of a column."""
        if not is_numeric:
            return "categorical"

        # Check column name against patterns
        for measure_type, patterns in self.measure_patterns.items():
            for pattern in patterns:
                if re.search(pattern, column_name):
                    return measure_type

        # Additional numeric analysis
        numeric_data = pd.to_numeric(data, errors='coerce').dropna()

        if len(numeric_data) > 0:
            # Check value ranges and distributions
            min_val = numeric_data.min()
            max_val = numeric_data.max()

            # Percentage-like values
            if 0 <= min_val and max_val <= 100 and len(numeric_data.unique()) > 5:
                return "intensive"

            # Binary-like values
            if set(numeric_data.unique()).issubset({0, 1}):
                return "categorical"

            # Count-like values (integers starting from 0 or 1)
            if numeric_data.dtype in ['int64', 'int32'] and min_val >= 0:
                return "additive"

        return "unknown"

    def _detect_duplicates(self, df: pd.DataFrame, column_classification: Dict[str, Any]) -> Dict[str, Any]:
        """Detect duplicate key combinations."""
        dimensions = column_classification["dimensions"]

        if not dimensions:
            return {
                "has_duplicates": False,
                "duplicate_count": 0,
                "total_rows": len(df),
                "key_columns": []
            }

        # Check for duplicates using dimension columns
        duplicate_mask = df.duplicated(subset=dimensions, keep=False)
        duplicate_count = duplicate_mask.sum()

        # Analyze duplicate patterns
        duplicate_groups = []
        if duplicate_count > 0:
            duplicated_data = df[duplicate_mask]
            grouped = duplicated_data.groupby(dimensions)

            for key, group in grouped:
                if len(group) > 1:
                    duplicate_groups.append({
                        "key": key if isinstance(key, tuple) else (key,),
                        "count": len(group),
                        "affected_measures": [col for col in group.columns
                                            if col in column_classification["measures"]]
                    })

        return {
            "has_duplicates": duplicate_count > 0,
            "duplicate_count": duplicate_count,
            "total_rows": len(df),
            "unique_combinations": len(df.drop_duplicates(subset=dimensions)),
            "key_columns": dimensions,
            "duplicate_groups": duplicate_groups[:10],  # First 10 examples
            "duplicate_ratio": duplicate_count / len(df) if len(df) > 0 else 0
        }

    def _generate_aggregation_strategy(self, df: pd.DataFrame,
                                     column_classification: Dict[str, Any],
                                     duplicate_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Generate aggregation strategy based on analysis."""
        if not duplicate_analysis["has_duplicates"]:
            return {
                "aggregation_needed": False,
                "reason": "No duplicates detected"
            }

        measures = column_classification["measures"]
        dimensions = column_classification["dimensions"]

        if not measures:
            return {
                "aggregation_needed": False,
                "reason": "No measures identified for aggregation"
            }

        # Determine aggregation method for each measure
        measure_strategies = {}

        for measure in measures:
            col_data = df[measure].dropna()
            if len(col_data) == 0:
                continue

            # Analyze measure characteristics
            measure_info = self._analyze_column_for_aggregation(col_data, measure)
            measure_type = measure_info["measure_type"]

            # Choose appropriate aggregation method
            if measure_type == "additive":
                method = "sum"
            elif measure_type == "intensive":
                method = "mean"
            elif measure_type == "temporal_point":
                method = "last"
            elif measure_type == "categorical":
                method = "first"
            else:
                # Default based on data characteristics
                if measure_info["is_numeric"]:
                    method = "sum"  # Default for numeric
                else:
                    method = "first"  # Default for non-numeric

            measure_strategies[measure] = {
                "method": method,
                "measure_type": measure_type,
                "confidence": self._calculate_method_confidence(col_data, method, measure_type)
            }

        return {
            "aggregation_needed": True,
            "group_by_columns": dimensions,
            "measure_strategies": measure_strategies,
            "total_measures": len(measures),
            "total_dimensions": len(dimensions)
        }

    def _calculate_method_confidence(self, data: pd.Series, method: str, measure_type: str) -> float:
        """Calculate confidence score for aggregation method choice."""
        base_confidence = 0.6

        # Boost confidence for clear measure types
        if measure_type in ["additive", "intensive", "categorical"]:
            base_confidence += 0.2

        # Boost for appropriate method-type combinations
        method_type_mapping = {
            ("sum", "additive"): 0.2,
            ("mean", "intensive"): 0.2,
            ("last", "temporal_point"): 0.2,
            ("first", "categorical"): 0.1
        }

        confidence_boost = method_type_mapping.get((method, measure_type), 0)

        return min(base_confidence + confidence_boost, 1.0)

    def _validate_aggregation_strategy(self, df: pd.DataFrame,
                                     aggregation_strategy: Dict[str, Any]) -> Dict[str, Any]:
        """Validate the proposed aggregation strategy."""
        if not aggregation_strategy.get("aggregation_needed", False):
            return {"status": "success", "validation": "no_aggregation_needed"}

        try:
            group_by_cols = aggregation_strategy["group_by_columns"]
            measure_strategies = aggregation_strategy["measure_strategies"]

            # Test aggregation on sample
            sample_df = df.head(100)

            # Build aggregation dictionary
            agg_dict = {}
            for measure, strategy in measure_strategies.items():
                if measure in sample_df.columns:
                    agg_dict[measure] = strategy["method"]

            if not agg_dict:
                return {"status": "error", "error_message": "No valid measures found for aggregation"}

            # Test aggregation
            result = sample_df.groupby(group_by_cols).agg(agg_dict)

            # Validate results
            original_rows = len(sample_df)
            aggregated_rows = len(result)
            reduction_ratio = 1 - (aggregated_rows / original_rows)

            return {
                "status": "success",
                "validation": "successful",
                "original_rows": original_rows,
                "aggregated_rows": aggregated_rows,
                "reduction_ratio": reduction_ratio,
                "measures_aggregated": len(agg_dict)
            }

        except Exception as e:
            return {
                "status": "error",
                "error_message": f"Aggregation validation failed: {str(e)}"
            }

    def _generate_metadata_config(self, aggregation_strategy: Dict[str, Any]) -> Dict[str, str]:
        """Generate metadata configuration parameters for aggregation."""
        if not aggregation_strategy.get("aggregation_needed", False):
            return {}

        config = {}

        # Basic aggregation parameters
        group_by_cols = aggregation_strategy["group_by_columns"]
        config["aggregation_needed"] = "true"
        config["group_by_columns"] = ",".join(group_by_cols)

        # Determine primary aggregation method
        measure_strategies = aggregation_strategy["measure_strategies"]
        methods = [strategy["method"] for strategy in measure_strategies.values()]
        primary_method = max(set(methods), key=methods.count)  # Most common method

        config["aggregation_method"] = primary_method

        # List all measures that need aggregation
        measures = list(measure_strategies.keys())
        config["aggregation_columns"] = ",".join(measures)

        # Add method-specific configurations
        if primary_method in ["mean", "sum"]:
            config["handle_nulls"] = "true"
        else:
            config["handle_nulls"] = "false"

        return config


def detect_aggregation_needs(file_path: str, pvmap_data: Optional[Dict[str, Any]] = None,
                           header_rows: int = 1) -> Dict[str, Any]:
    """
    Convenience function to detect aggregation needs for a CSV file.

    Args:
        file_path: Path to CSV file
        pvmap_data: Optional PVMap analysis results
        header_rows: Number of header rows

    Returns:
        Complete aggregation analysis and recommendations
    """
    analyzer = AggregationAnalyzer()
    return analyzer.analyze_duplicates(file_path, pvmap_data, header_rows)


def generate_aggregation_config(aggregation_analysis: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate aggregation configuration from analysis results.

    Args:
        aggregation_analysis: Results from detect_aggregation_needs

    Returns:
        Configuration parameters for metadata
    """
    if aggregation_analysis.get("status") != "success":
        return {"status": "error", "error_message": "Invalid aggregation analysis"}

    strategy = aggregation_analysis.get("aggregation_strategy", {})

    if not strategy.get("aggregation_needed", False):
        return {
            "status": "success",
            "aggregation_needed": False,
            "config": {}
        }

    config = aggregation_analysis.get("recommended_config", {})

    return {
        "status": "success",
        "aggregation_needed": True,
        "config": config,
        "validation": aggregation_analysis.get("validation", {}),
        "measures_count": strategy.get("total_measures", 0),
        "dimensions_count": strategy.get("total_dimensions", 0)
    }