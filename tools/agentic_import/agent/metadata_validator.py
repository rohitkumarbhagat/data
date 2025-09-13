"""
Metadata validation and inference module for ADK Phase 8.

This module provides comprehensive validation and intelligent inference
of metadata parameters for Data Commons processing.
"""

from __future__ import annotations

import pandas as pd
import numpy as np
import re
import os
from typing import Dict, Any, List, Tuple, Optional, Set, Union
import logging

class MetadataValidator:
    """Comprehensive metadata validation and parameter inference."""

    def __init__(self):
        """Initialize validator with parameter definitions and rules."""
        self.required_parameters = self._define_required_parameters()
        self.optional_parameters = self._define_optional_parameters()
        self.parameter_rules = self._define_parameter_rules()
        self.default_values = self._define_default_values()

    def _define_required_parameters(self) -> Set[str]:
        """Define parameters that are required for processing."""
        return {
            "output_columns",
            "header_rows",
            "mapped_rows",
            "mapped_columns"
        }

    def _define_optional_parameters(self) -> Dict[str, Dict[str, Any]]:
        """Define optional parameters with their characteristics."""
        return {
            # File structure parameters
            "header_columns": {
                "type": "int",
                "description": "Number of columns that are row labels",
                "default": 0,
                "min": 0,
                "max": 20
            },
            "skip_rows": {
                "type": "int",
                "description": "Number of rows to skip before headers",
                "default": 0,
                "min": 0,
                "max": 100
            },

            # Date and time parameters
            "date_format": {
                "type": "str",
                "description": "Format string for parsing dates",
                "examples": ["%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y"]
            },
            "observation_date_format": {
                "type": "str",
                "description": "Format for observation dates in output",
                "examples": ["YYYY", "YYYY-MM", "YYYY-MM-DD"]
            },
            "observation_period": {
                "type": "str",
                "description": "Type of observation period",
                "allowed_values": ["point", "year", "month", "quarter", "week", "fiscal_year"]
            },

            # Geographic parameters
            "places_within": {
                "type": "str",
                "description": "Geographic containment (e.g., country/USA)",
                "examples": ["country/USA", "country/GBR", "Earth"]
            },
            "place_resolution": {
                "type": "str",
                "description": "Level of geographic detail",
                "allowed_values": ["country", "state", "county", "city", "custom"]
            },

            # Aggregation parameters
            "aggregation_method": {
                "type": "str",
                "description": "Method for aggregating duplicate observations",
                "allowed_values": ["sum", "mean", "max", "min", "last", "first", "count"]
            },
            "aggregation_columns": {
                "type": "str",
                "description": "Comma-separated list of columns to aggregate",
                "format": "comma_separated"
            },
            "group_by_columns": {
                "type": "str",
                "description": "Comma-separated list of grouping columns",
                "format": "comma_separated"
            },

            # Data processing parameters
            "unit_conversion": {
                "type": "str",
                "description": "Unit conversion specification",
                "examples": ["percent_to_decimal", "thousands_to_units", "custom"]
            },
            "scaling_factor": {
                "type": "float",
                "description": "Scaling factor for values",
                "default": 1.0,
                "min": 0.0001,
                "max": 1000000.0
            },
            "measurement_method": {
                "type": "str",
                "description": "Method used to collect the data",
                "examples": ["Survey", "Census", "Administrative", "Estimated"]
            },

            # Quality control parameters
            "drop_statvars_without_svobs": {
                "type": "int",
                "description": "Drop statistical variables without observations",
                "allowed_values": [0, 1],
                "default": 0
            },
            "input_rows": {
                "type": "int",
                "description": "Maximum number of input rows to process",
                "min": 1
            }
        }

    def _define_parameter_rules(self) -> List[Dict[str, Any]]:
        """Define validation rules and dependencies between parameters."""
        return [
            {
                "rule": "aggregation_dependency",
                "condition": "aggregation_method is set",
                "requires": ["aggregation_columns", "group_by_columns"],
                "message": "Aggregation method requires both aggregation_columns and group_by_columns"
            },
            {
                "rule": "date_format_consistency",
                "condition": "date_format is set",
                "validates": "observation_date_format should be compatible",
                "message": "observation_date_format should match or be simpler than date_format"
            },
            {
                "rule": "geographic_consistency",
                "condition": "places_within is set",
                "suggests": "place_resolution should be set",
                "message": "Consider setting place_resolution when places_within is specified"
            },
            {
                "rule": "file_dimensions",
                "condition": "always",
                "validates": "mapped_rows and mapped_columns should be positive",
                "message": "File dimensions must be positive integers"
            },
            {
                "rule": "output_columns_format",
                "condition": "always",
                "validates": "output_columns should contain required DC columns",
                "required_in_output": ["observationAbout", "observationDate", "value", "variableMeasured"],
                "message": "output_columns must include core Data Commons columns"
            }
        ]

    def _define_default_values(self) -> Dict[str, Any]:
        """Define smart default values for parameters."""
        return {
            "output_columns": "observationAbout,observationDate,value,variableMeasured,unit,scalingFactor",
            "header_rows": 1,
            "header_columns": 0,
            "scaling_factor": 1.0,
            "drop_statvars_without_svobs": 0,
            "observation_period": "point",
            "places_within": "Earth"  # Most general default
        }

    def validate_metadata_config(self, config: Dict[str, Any],
                                file_path: Optional[str] = None,
                                pvmap_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Comprehensive validation of metadata configuration.

        Args:
            config: Metadata configuration dictionary
            file_path: Optional path to input CSV file for validation
            pvmap_path: Optional path to PVMap file for validation

        Returns:
            Validation results with issues, warnings, and suggestions
        """
        validation_result = {
            "status": "success",
            "valid": True,
            "errors": [],
            "warnings": [],
            "suggestions": [],
            "enhanced_config": config.copy()
        }

        try:
            # 1. Check required parameters
            self._validate_required_parameters(config, validation_result)

            # 2. Validate parameter types and values
            self._validate_parameter_values(config, validation_result)

            # 3. Apply parameter rules
            self._apply_parameter_rules(config, validation_result)

            # 4. Validate against input file if provided
            if file_path and os.path.exists(file_path):
                self._validate_against_file(config, file_path, validation_result)

            # 5. Validate against PVMap if provided
            if pvmap_path and os.path.exists(pvmap_path):
                self._validate_against_pvmap(config, pvmap_path, validation_result)

            # 6. Add intelligent suggestions
            self._add_intelligent_suggestions(config, validation_result)

            # Set overall validity
            validation_result["valid"] = len(validation_result["errors"]) == 0

        except Exception as e:
            logging.error(f"Metadata validation failed: {str(e)}")
            validation_result.update({
                "status": "error",
                "valid": False,
                "error_message": str(e)
            })

        return validation_result

    def _validate_required_parameters(self, config: Dict[str, Any],
                                    validation_result: Dict[str, Any]) -> None:
        """Validate presence of required parameters."""
        for param in self.required_parameters:
            if param not in config or config[param] is None:
                validation_result["errors"].append(f"Missing required parameter: {param}")

    def _validate_parameter_values(self, config: Dict[str, Any],
                                 validation_result: Dict[str, Any]) -> None:
        """Validate parameter values against their definitions."""
        for param, value in config.items():
            if param in self.optional_parameters:
                param_def = self.optional_parameters[param]
                self._validate_single_parameter(param, value, param_def, validation_result)

    def _validate_single_parameter(self, param_name: str, value: Any,
                                 param_def: Dict[str, Any],
                                 validation_result: Dict[str, Any]) -> None:
        """Validate a single parameter against its definition."""
        # Type validation
        expected_type = param_def.get("type", "str")

        if expected_type == "int":
            try:
                int_value = int(value)
                # Range validation
                if "min" in param_def and int_value < param_def["min"]:
                    validation_result["errors"].append(
                        f"{param_name} value {int_value} is below minimum {param_def['min']}"
                    )
                if "max" in param_def and int_value > param_def["max"]:
                    validation_result["errors"].append(
                        f"{param_name} value {int_value} exceeds maximum {param_def['max']}"
                    )
            except ValueError:
                validation_result["errors"].append(f"{param_name} must be an integer, got: {value}")

        elif expected_type == "float":
            try:
                float_value = float(value)
                # Range validation
                if "min" in param_def and float_value < param_def["min"]:
                    validation_result["errors"].append(
                        f"{param_name} value {float_value} is below minimum {param_def['min']}"
                    )
                if "max" in param_def and float_value > param_def["max"]:
                    validation_result["errors"].append(
                        f"{param_name} value {float_value} exceeds maximum {param_def['max']}"
                    )
            except ValueError:
                validation_result["errors"].append(f"{param_name} must be a number, got: {value}")

        # Allowed values validation
        if "allowed_values" in param_def:
            if value not in param_def["allowed_values"]:
                validation_result["errors"].append(
                    f"{param_name} value '{value}' not in allowed values: {param_def['allowed_values']}"
                )

    def _apply_parameter_rules(self, config: Dict[str, Any],
                             validation_result: Dict[str, Any]) -> None:
        """Apply complex validation rules."""
        for rule in self.parameter_rules:
            self._apply_single_rule(rule, config, validation_result)

    def _apply_single_rule(self, rule: Dict[str, Any], config: Dict[str, Any],
                          validation_result: Dict[str, Any]) -> None:
        """Apply a single validation rule."""
        rule_type = rule["rule"]

        if rule_type == "aggregation_dependency":
            if "aggregation_method" in config:
                for required_param in rule["requires"]:
                    if required_param not in config:
                        validation_result["errors"].append(rule["message"])

        elif rule_type == "output_columns_format":
            if "output_columns" in config:
                output_cols = [col.strip() for col in config["output_columns"].split(",")]
                required_cols = rule["required_in_output"]
                missing_cols = [col for col in required_cols if col not in output_cols]
                if missing_cols:
                    validation_result["errors"].append(
                        f"output_columns missing required columns: {missing_cols}"
                    )

        elif rule_type == "file_dimensions":
            for dim_param in ["mapped_rows", "mapped_columns"]:
                if dim_param in config:
                    try:
                        dim_value = int(config[dim_param])
                        if dim_value <= 0:
                            validation_result["errors"].append(
                                f"{dim_param} must be positive, got: {dim_value}"
                            )
                    except ValueError:
                        validation_result["errors"].append(
                            f"{dim_param} must be an integer, got: {config[dim_param]}"
                        )

    def _validate_against_file(self, config: Dict[str, Any], file_path: str,
                             validation_result: Dict[str, Any]) -> None:
        """Validate configuration against actual file structure."""
        try:
            # Get file info
            header_rows = int(config.get("header_rows", 1))
            df = pd.read_csv(file_path, header=list(range(header_rows)), nrows=10)

            actual_columns = len(df.columns)
            actual_rows = len(pd.read_csv(file_path, header=list(range(header_rows))))

            # Validate mapped_columns
            if "mapped_columns" in config:
                configured_cols = int(config["mapped_columns"])
                if configured_cols != actual_columns:
                    validation_result["warnings"].append(
                        f"mapped_columns ({configured_cols}) doesn't match actual columns ({actual_columns})"
                    )

            # Validate mapped_rows
            if "mapped_rows" in config:
                configured_rows = int(config["mapped_rows"])
                if abs(configured_rows - actual_rows) > actual_rows * 0.1:  # Allow 10% difference
                    validation_result["warnings"].append(
                        f"mapped_rows ({configured_rows}) differs significantly from actual data rows (~{actual_rows})"
                    )

        except Exception as e:
            validation_result["warnings"].append(f"Could not validate against file: {str(e)}")

    def _validate_against_pvmap(self, config: Dict[str, Any], pvmap_path: str,
                              validation_result: Dict[str, Any]) -> None:
        """Validate configuration against PVMap file."""
        try:
            pvmap_df = pd.read_csv(pvmap_path)
            required_pvmap_columns = ["input", "property", "value"]

            missing_cols = [col for col in required_pvmap_columns if col not in pvmap_df.columns]
            if missing_cols:
                validation_result["warnings"].append(
                    f"PVMap file missing required columns: {missing_cols}"
                )

            # Check if output_columns are compatible with PVMap
            if "output_columns" in config:
                output_cols = [col.strip() for col in config["output_columns"].split(",")]
                pvmap_properties = set(pvmap_df["property"].unique())

                # Check for common Data Commons properties
                common_properties = {"observationAbout", "observationDate", "variableMeasured", "value"}
                missing_common = common_properties - pvmap_properties
                if missing_common:
                    validation_result["suggestions"].append(
                        f"Consider adding these common properties to PVMap: {missing_common}"
                    )

        except Exception as e:
            validation_result["warnings"].append(f"Could not validate against PVMap: {str(e)}")

    def _add_intelligent_suggestions(self, config: Dict[str, Any],
                                   validation_result: Dict[str, Any]) -> None:
        """Add intelligent suggestions for improvement."""
        # Suggest missing optional parameters
        if "date_format" not in config and "observation_date_format" not in config:
            validation_result["suggestions"].append(
                "Consider adding date format parameters if your data contains dates"
            )

        if "places_within" not in config:
            validation_result["suggestions"].append(
                "Consider specifying 'places_within' for geographic data (e.g., 'country/USA')"
            )

        if "measurement_method" not in config:
            validation_result["suggestions"].append(
                "Consider adding 'measurement_method' to describe how data was collected"
            )

        # Suggest aggregation if not specified but might be needed
        if "aggregation_method" not in config:
            validation_result["suggestions"].append(
                "If your data has duplicate observations, consider adding aggregation parameters"
            )

    def infer_metadata_parameters(self, file_path: str,
                                analysis_result: Optional[Dict[str, Any]] = None,
                                pvmap_result: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Intelligently infer metadata parameters from file analysis.

        Args:
            file_path: Path to CSV file
            analysis_result: Optional analysis from enhanced_metadata.py
            pvmap_result: Optional PVMap analysis results

        Returns:
            Inferred metadata configuration
        """
        try:
            config = self.default_values.copy()

            # Basic file structure inference
            if analysis_result and analysis_result.get("status") == "success":
                # Use enhanced analysis results
                recommended = analysis_result.get("recommended_config", {})
                config.update(recommended)

                # Infer additional parameters
                if analysis_result.get("hierarchical_headers", False):
                    config["header_columns"] = analysis_result.get("index_columns", 0)

            else:
                # Basic inference without enhanced analysis
                df_sample = pd.read_csv(file_path, nrows=10)
                config["mapped_columns"] = len(df_sample.columns)
                full_df_size = len(pd.read_csv(file_path))
                config["mapped_rows"] = full_df_size - config["header_rows"]

            # Geographic inference
            geo_indicators = self._detect_geographic_scope(file_path)
            if geo_indicators:
                config["places_within"] = geo_indicators["suggested_scope"]
                config["place_resolution"] = geo_indicators["resolution_level"]

            # Unit and scaling inference
            scaling_info = self._infer_scaling_and_units(file_path)
            if scaling_info:
                config.update(scaling_info)

            # Measurement method inference
            method_info = self._infer_measurement_method(file_path)
            if method_info:
                config["measurement_method"] = method_info

            return {
                "status": "success",
                "inferred_config": config,
                "confidence": self._calculate_inference_confidence(config),
                "inference_sources": {
                    "file_analysis": analysis_result is not None,
                    "pvmap_analysis": pvmap_result is not None,
                    "geographic_detection": geo_indicators is not None,
                    "scaling_detection": scaling_info is not None
                }
            }

        except Exception as e:
            logging.error(f"Parameter inference failed: {str(e)}")
            return {"status": "error", "error_message": str(e)}

    def _detect_geographic_scope(self, file_path: str) -> Optional[Dict[str, str]]:
        """Detect geographic scope from data."""
        try:
            df = pd.read_csv(file_path, nrows=50)

            # Look for geographic columns and their values
            geo_patterns = [r'(?i)(country|region|state|city|location)', r'(?i)(geo|place)']

            for col in df.columns:
                col_str = str(col)
                for pattern in geo_patterns:
                    if re.search(pattern, col_str):
                        # Analyze values in this column
                        unique_values = df[col].astype(str).str.upper().unique()

                        # Check for common patterns
                        if any("USA" in val or "UNITED STATES" in val for val in unique_values):
                            return {"suggested_scope": "country/USA", "resolution_level": "state"}
                        elif any("GBR" in val or "BRITAIN" in val or "UK" in val for val in unique_values):
                            return {"suggested_scope": "country/GBR", "resolution_level": "country"}

            return None

        except Exception:
            return None

    def _infer_scaling_and_units(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Infer scaling factors and unit conversions."""
        try:
            df = pd.read_csv(file_path, nrows=100)

            # Look for numeric columns and analyze their ranges
            numeric_cols = df.select_dtypes(include=[np.number]).columns

            for col in numeric_cols:
                col_data = df[col].dropna()
                if len(col_data) == 0:
                    continue

                max_val = col_data.max()
                col_name = str(col).lower()

                # Percentage detection
                if 0 <= col_data.min() and max_val <= 1 and any(
                    keyword in col_name for keyword in ['rate', 'ratio', 'percent', 'proportion']
                ):
                    return {"unit_conversion": "decimal_to_percent", "scaling_factor": 100.0}

                # Thousands/millions detection
                elif max_val > 100000 and any(
                    keyword in col_name for keyword in ['population', 'count', 'total', 'amount']
                ):
                    if max_val > 1000000:
                        return {"unit_conversion": "units_to_millions", "scaling_factor": 0.000001}
                    else:
                        return {"unit_conversion": "units_to_thousands", "scaling_factor": 0.001}

            return None

        except Exception:
            return None

    def _infer_measurement_method(self, file_path: str) -> Optional[str]:
        """Infer measurement method from file name and content."""
        try:
            file_name = os.path.basename(file_path).lower()

            # Check filename patterns
            if any(keyword in file_name for keyword in ['census', 'survey', 'poll']):
                return "Census" if 'census' in file_name else "Survey"
            elif any(keyword in file_name for keyword in ['admin', 'administrative', 'official']):
                return "Administrative"
            elif any(keyword in file_name for keyword in ['estimate', 'projected', 'forecast']):
                return "Estimated"

            return None

        except Exception:
            return None

    def _calculate_inference_confidence(self, config: Dict[str, Any]) -> float:
        """Calculate confidence score for inferred parameters."""
        total_params = len(config)
        default_params = sum(1 for k, v in config.items()
                           if k in self.default_values and v == self.default_values[k])

        # Higher confidence when fewer defaults are used (more specific inference)
        confidence = 1.0 - (default_params / total_params) if total_params > 0 else 0.0

        return min(max(confidence, 0.1), 0.9)  # Keep between 0.1 and 0.9


def validate_metadata_comprehensive(config: Dict[str, Any],
                                  file_path: Optional[str] = None,
                                  pvmap_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Convenience function for comprehensive metadata validation.

    Args:
        config: Metadata configuration to validate
        file_path: Optional input file path
        pvmap_path: Optional PVMap file path

    Returns:
        Comprehensive validation results
    """
    validator = MetadataValidator()
    return validator.validate_metadata_config(config, file_path, pvmap_path)


def infer_metadata_parameters(file_path: str,
                            analysis_result: Optional[Dict[str, Any]] = None,
                            pvmap_result: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Convenience function for metadata parameter inference.

    Args:
        file_path: Path to CSV file
        analysis_result: Optional enhanced analysis results
        pvmap_result: Optional PVMap analysis results

    Returns:
        Inferred metadata configuration
    """
    validator = MetadataValidator()
    return validator.infer_metadata_parameters(file_path, analysis_result, pvmap_result)