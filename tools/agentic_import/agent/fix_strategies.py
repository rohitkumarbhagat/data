#!/usr/bin/env python3

# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Comprehensive Fix Strategies for ADK PVMap Generation

This module implements sophisticated fix strategies for common workflow errors.
Each strategy can make targeted modifications to configuration files based on
specific error analysis results.

Key Features:
- Targeted fixes based on extracted error details
- Safe file modification with backup and validation
- Intelligent property mapping adjustments
- Date format standardization
- Constraint property generation
- Aggregation rule configuration
"""

import os
import shutil
import logging
import pandas as pd
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Set
import csv
import re


class FixStrategyResult:
    """Represents the result of applying a fix strategy."""
    
    def __init__(self, success: bool, message: str, details: Dict[str, Any] = None):
        self.success = success
        self.message = message  
        self.details = details or {}
        self.timestamp = datetime.now().isoformat()
        
    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": "success" if self.success else "error",
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp
        }


class PVMapFixStrategies:
    """Fix strategies for PVMap-related errors."""
    
    @staticmethod
    def fix_missing_columns(working_dir: str, error_details: Dict[str, Any]) -> FixStrategyResult:
        """Fix PVMap entries that reference missing columns.
        
        Args:
            working_dir: Directory containing pvmap.csv
            error_details: Details from error analysis including missing column names
            
        Returns:
            FixStrategyResult with operation results
        """
        try:
            pvmap_path = os.path.join(working_dir, "pvmap.csv")
            if not os.path.exists(pvmap_path):
                return FixStrategyResult(False, "PVMap file not found")
                
            # Create backup
            backup_path = f"{pvmap_path}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            shutil.copy2(pvmap_path, backup_path)
            
            # Read current PVMap
            df = pd.read_csv(pvmap_path)
            original_count = len(df)
            
            # Get missing columns from error details
            missing_columns = []
            if "extracted_details" in error_details:
                # From regex extraction
                missing_columns.extend(error_details["extracted_details"])
            if "details" in error_details and "missing_columns" in error_details["details"]:
                # From specific error analysis
                missing_columns.extend(error_details["details"]["missing_columns"])
                
            # Also check for obvious invalid patterns
            invalid_patterns = ["unnamed:", "column_", "index_", "nan", "null", "none"]
            
            # Remove entries that reference missing or invalid columns
            removed_entries = []
            for missing_col in missing_columns:
                mask = df['input'].str.contains(re.escape(str(missing_col)), case=False, na=False)
                removed_entries.extend(df[mask]['input'].tolist())
                df = df[~mask]
                
            # Remove entries with invalid patterns
            for pattern in invalid_patterns:
                mask = df['input'].str.contains(pattern, case=False, na=False)
                removed_entries.extend(df[mask]['input'].tolist())
                df = df[~mask]
                
            removed_count = original_count - len(df)
            
            if removed_count > 0:
                # Write the cleaned PVMap
                df.to_csv(pvmap_path, index=False)
                
                return FixStrategyResult(
                    True, 
                    f"Removed {removed_count} entries with missing/invalid column references",
                    {
                        "backup_path": backup_path,
                        "original_count": original_count,
                        "final_count": len(df),
                        "removed_entries": removed_entries[:10],  # Show first 10
                        "total_removed": len(removed_entries)
                    }
                )
            else:
                return FixStrategyResult(
                    False,
                    "No entries found that reference the missing columns",
                    {"missing_columns_checked": missing_columns}
                )
                
        except Exception as e:
            logging.error(f"Fix missing columns failed: {str(e)}")
            return FixStrategyResult(False, f"Fix failed: {str(e)}")
            
    @staticmethod
    def validate_column_mappings(working_dir: str, input_file: str) -> FixStrategyResult:
        """Validate that all PVMap entries reference existing columns.
        
        Args:
            working_dir: Directory containing pvmap.csv
            input_file: Path to input CSV to validate against
            
        Returns:
            FixStrategyResult with validation results
        """
        try:
            pvmap_path = os.path.join(working_dir, "pvmap.csv")
            if not os.path.exists(pvmap_path):
                return FixStrategyResult(False, "PVMap file not found")
                
            # Get actual CSV columns
            try:
                input_df = pd.read_csv(input_file, nrows=1)
                actual_columns = set(input_df.columns)
            except Exception as e:
                return FixStrategyResult(False, f"Cannot read input CSV: {str(e)}")
                
            # Read PVMap
            pvmap_df = pd.read_csv(pvmap_path)
            
            # Extract column references from PVMap
            referenced_columns = set()
            invalid_entries = []
            
            for _, row in pvmap_df.iterrows():
                input_ref = str(row['input'])
                
                # Skip special entries (those starting with #)
                if input_ref.startswith('#'):
                    continue
                    
                # Extract column name (handle various formats)
                if ':' in input_ref:
                    col_name = input_ref.split(':')[0].strip()
                else:
                    col_name = input_ref.strip()
                    
                referenced_columns.add(col_name)
                
                if col_name not in actual_columns:
                    invalid_entries.append({
                        "input_ref": input_ref,
                        "column": col_name,
                        "property": row.get('property', ''),
                        "value": row.get('value', '')
                    })
                    
            validation_result = {
                "total_mappings": len(pvmap_df),
                "unique_columns_referenced": len(referenced_columns),
                "actual_columns_available": len(actual_columns),
                "invalid_entries": invalid_entries,
                "missing_columns": list(referenced_columns - actual_columns),
                "unused_columns": list(actual_columns - referenced_columns)
            }
            
            if invalid_entries:
                return FixStrategyResult(
                    False,
                    f"Found {len(invalid_entries)} invalid column references",
                    validation_result
                )
            else:
                return FixStrategyResult(
                    True,
                    "All column references are valid",
                    validation_result
                )
                
        except Exception as e:
            logging.error(f"Column validation failed: {str(e)}")
            return FixStrategyResult(False, f"Validation failed: {str(e)}")


class MetadataFixStrategies:
    """Fix strategies for metadata configuration errors."""
    
    @staticmethod
    def fix_date_formats(working_dir: str, error_details: Dict[str, Any]) -> FixStrategyResult:
        """Fix date format configurations in metadata.
        
        Args:
            working_dir: Directory containing metadata.csv
            error_details: Details from error analysis including date format info
            
        Returns:
            FixStrategyResult with operation results
        """
        try:
            metadata_path = os.path.join(working_dir, "metadata.csv")
            if not os.path.exists(metadata_path):
                return FixStrategyResult(False, "Metadata file not found")
                
            # Create backup
            backup_path = f"{metadata_path}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            shutil.copy2(metadata_path, backup_path)
            
            # Read metadata
            df = pd.read_csv(metadata_path)
            fixes_applied = []
            
            # Extract expected format from error details if available
            expected_format = None
            if "details" in error_details and "expected_format" in error_details["details"]:
                expected_format = error_details["details"]["expected_format"]
                
            # Common date format fixes
            date_format_fixes = [
                ("%Y-%m-%d", "Standard ISO date format"),
                ("%m/%d/%Y", "US date format"),
                ("%d/%m/%Y", "European date format"),
                ("%Y", "Year only format"),
                ("%Y-%m", "Year-month format")
            ]
            
            # If we have a specific expected format, try it first
            if expected_format:
                date_format_fixes.insert(0, (expected_format, "Error-specified format"))
                
            # Apply date format fixes
            for format_str, description in date_format_fixes:
                updated = False
                
                # Update date_format
                date_format_mask = df['Property'] == 'date_format'
                if date_format_mask.any():
                    df.loc[date_format_mask, 'Value'] = format_str
                    fixes_applied.append(f"Set date_format to {format_str}")
                    updated = True
                    
                # Update observation_date_format
                obs_date_mask = df['Property'] == 'observation_date_format'
                if obs_date_mask.any():
                    df.loc[obs_date_mask, 'Value'] = format_str
                    fixes_applied.append(f"Set observation_date_format to {format_str}")
                    updated = True
                    
                if updated:
                    break  # Only apply one format fix at a time
                    
            # If no existing date format properties, add them
            if not fixes_applied:
                new_rows = [
                    {'Property': 'date_format', 'Value': '%Y-%m-%d'},
                    {'Property': 'observation_date_format', 'Value': '%Y-%m-%d'}
                ]
                
                for new_row in new_rows:
                    if new_row['Property'] not in df['Property'].values:
                        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                        fixes_applied.append(f"Added {new_row['Property']} = {new_row['Value']}")
                        
            if fixes_applied:
                df.to_csv(metadata_path, index=False)
                return FixStrategyResult(
                    True,
                    f"Applied date format fixes: {'; '.join(fixes_applied)}",
                    {
                        "backup_path": backup_path,
                        "fixes": fixes_applied,
                        "expected_format": expected_format
                    }
                )
            else:
                return FixStrategyResult(
                    False,
                    "No date format properties found to fix"
                )
                
        except Exception as e:
            logging.error(f"Date format fix failed: {str(e)}")
            return FixStrategyResult(False, f"Fix failed: {str(e)}")
            
    @staticmethod
    def add_aggregation_rules(working_dir: str, error_details: Dict[str, Any]) -> FixStrategyResult:
        """Add aggregation rules to handle duplicate observations.
        
        Args:
            working_dir: Directory containing metadata.csv
            error_details: Details from error analysis about duplication
            
        Returns:
            FixStrategyResult with operation results
        """
        try:
            metadata_path = os.path.join(working_dir, "metadata.csv")
            if not os.path.exists(metadata_path):
                return FixStrategyResult(False, "Metadata file not found")
                
            # Create backup
            backup_path = f"{metadata_path}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            shutil.copy2(metadata_path, backup_path)
            
            # Read metadata
            df = pd.read_csv(metadata_path)
            fixes_applied = []
            
            # Common aggregation rules for duplicate handling
            aggregation_configs = [
                {'Property': 'aggregation_method', 'Value': 'sum'},
                {'Property': 'duplicate_handling', 'Value': 'aggregate'},
                {'Property': 'aggregation_group_by', 'Value': 'observationAbout,variableMeasured,observationDate'}
            ]
            
            # Add aggregation configurations if not present
            for config in aggregation_configs:
                if config['Property'] not in df['Property'].values:
                    df = pd.concat([df, pd.DataFrame([config])], ignore_index=True)
                    fixes_applied.append(f"Added {config['Property']} = {config['Value']}")
                else:
                    # Update existing value
                    df.loc[df['Property'] == config['Property'], 'Value'] = config['Value']
                    fixes_applied.append(f"Updated {config['Property']} = {config['Value']}")
                    
            if fixes_applied:
                df.to_csv(metadata_path, index=False)
                return FixStrategyResult(
                    True,
                    f"Added aggregation rules: {'; '.join(fixes_applied)}",
                    {
                        "backup_path": backup_path,
                        "fixes": fixes_applied
                    }
                )
            else:
                return FixStrategyResult(
                    False,
                    "Aggregation rules already configured"
                )
                
        except Exception as e:
            logging.error(f"Aggregation rules fix failed: {str(e)}")
            return FixStrategyResult(False, f"Fix failed: {str(e)}")


class PropertyFixStrategies:
    """Fix strategies for Data Commons property-related errors."""
    
    @staticmethod
    def add_constraint_properties(working_dir: str, error_details: Dict[str, Any]) -> FixStrategyResult:
        """Add missing constraint properties to PVMap.
        
        Args:
            working_dir: Directory containing pvmap.csv
            error_details: Details about missing constraint properties
            
        Returns:
            FixStrategyResult with operation results
        """
        try:
            pvmap_path = os.path.join(working_dir, "pvmap.csv")
            if not os.path.exists(pvmap_path):
                return FixStrategyResult(False, "PVMap file not found")
                
            # Create backup
            backup_path = f"{pvmap_path}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            shutil.copy2(pvmap_path, backup_path)
            
            # Read PVMap
            df = pd.read_csv(pvmap_path)
            
            # Common constraint properties that are often missing
            common_constraints = [
                {'input': '#constraint:gender', 'property': 'constraintProperties', 'value': 'gender'},
                {'input': '#constraint:age', 'property': 'constraintProperties', 'value': 'age'},
                {'input': '#constraint:race', 'property': 'constraintProperties', 'value': 'race'},
                {'input': '#constraint:income', 'property': 'constraintProperties', 'value': 'income'},
                {'input': '#constraint:education', 'property': 'constraintProperties', 'value': 'educationalAttainment'}
            ]
            
            added_constraints = []
            existing_constraints = set(df['input'].values)
            
            for constraint in common_constraints:
                if constraint['input'] not in existing_constraints:
                    df = pd.concat([df, pd.DataFrame([constraint])], ignore_index=True)
                    added_constraints.append(constraint['value'])
                    
            if added_constraints:
                df.to_csv(pvmap_path, index=False)
                return FixStrategyResult(
                    True,
                    f"Added constraint properties: {', '.join(added_constraints)}",
                    {
                        "backup_path": backup_path,
                        "added_constraints": added_constraints
                    }
                )
            else:
                return FixStrategyResult(
                    False,
                    "No additional constraint properties needed"
                )
                
        except Exception as e:
            logging.error(f"Constraint properties fix failed: {str(e)}")
            return FixStrategyResult(False, f"Fix failed: {str(e)}")
            
    @staticmethod
    def fix_property_values(working_dir: str, error_details: Dict[str, Any]) -> FixStrategyResult:
        """Fix invalid property values in PVMap.
        
        Args:
            working_dir: Directory containing pvmap.csv
            error_details: Details about invalid property values
            
        Returns:
            FixStrategyResult with operation results
        """
        try:
            pvmap_path = os.path.join(working_dir, "pvmap.csv")
            if not os.path.exists(pvmap_path):
                return FixStrategyResult(False, "PVMap file not found")
                
            # Create backup
            backup_path = f"{pvmap_path}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            shutil.copy2(pvmap_path, backup_path)
            
            # Read PVMap  
            df = pd.read_csv(pvmap_path)
            
            fixes_applied = []
            
            # Extract invalid property info from error details
            if "details" in error_details:
                property_name = error_details["details"].get("property_name")
                invalid_value = error_details["details"].get("invalid_value")
                
                if property_name and invalid_value:
                    # Try to fix the specific invalid value
                    mask = (df['property'] == property_name) & (df['value'] == invalid_value)
                    
                    if mask.any():
                        # Common property value corrections
                        corrections = {
                            "count": "Count",
                            "person": "Person", 
                            "household": "Household",
                            "year": "Year",
                            "month": "Month",
                            "day": "Day"
                        }
                        
                        corrected_value = corrections.get(invalid_value.lower(), invalid_value.title())
                        df.loc[mask, 'value'] = corrected_value
                        fixes_applied.append(f"Corrected {property_name}:{invalid_value} to {corrected_value}")
                        
            # General property value standardization
            # Standardize common property values
            standardizations = {
                'populationType': {
                    'person': 'Person',
                    'people': 'Person', 
                    'individual': 'Person',
                    'household': 'Household',
                    'house': 'Household'
                },
                'measuredProperty': {
                    'count': 'Count',
                    'number': 'Count',
                    'total': 'Count'
                }
            }
            
            for prop, value_map in standardizations.items():
                mask = df['property'] == prop
                if mask.any():
                    for old_val, new_val in value_map.items():
                        val_mask = mask & (df['value'].str.lower() == old_val.lower())
                        if val_mask.any():
                            df.loc[val_mask, 'value'] = new_val
                            fixes_applied.append(f"Standardized {prop}:{old_val} to {new_val}")
                            
            if fixes_applied:
                df.to_csv(pvmap_path, index=False)
                return FixStrategyResult(
                    True,
                    f"Fixed property values: {'; '.join(fixes_applied)}",
                    {
                        "backup_path": backup_path,
                        "fixes": fixes_applied
                    }
                )
            else:
                return FixStrategyResult(
                    False,
                    "No property value fixes needed"
                )
                
        except Exception as e:
            logging.error(f"Property value fix failed: {str(e)}")
            return FixStrategyResult(False, f"Fix failed: {str(e)}")


class ComprehensiveFixStrategies:
    """Main fix strategies coordinator that combines all fix types."""
    
    def __init__(self):
        """Initialize with all fix strategy modules."""
        self.pvmap_fixes = PVMapFixStrategies()
        self.metadata_fixes = MetadataFixStrategies()
        self.property_fixes = PropertyFixStrategies()
        
    def apply_fix(self, fix_name: str, working_dir: str, error_details: Dict[str, Any], 
                  input_file: str = None) -> FixStrategyResult:
        """Apply a specific fix strategy.
        
        Args:
            fix_name: Name of the fix strategy to apply
            working_dir: Directory containing configuration files
            error_details: Detailed error analysis results
            input_file: Path to input CSV (for validation fixes)
            
        Returns:
            FixStrategyResult with application results
        """
        try:
            # Map fix names to methods
            fix_methods = {
                # PVMap fixes
                "fix_missing_columns": self.pvmap_fixes.fix_missing_columns,
                "validate_column_mappings": lambda wd, ed: self.pvmap_fixes.validate_column_mappings(wd, input_file) if input_file else FixStrategyResult(False, "Input file required for validation"),
                
                # Metadata fixes  
                "fix_date_formats": self.metadata_fixes.fix_date_formats,
                "add_aggregation_rules": self.metadata_fixes.add_aggregation_rules,
                "adjust_date_parsing": self.metadata_fixes.fix_date_formats,  # Alias
                
                # Property fixes
                "add_constraint_properties": self.property_fixes.add_constraint_properties,
                "fix_property_values": self.property_fixes.fix_property_values,
                "validate_dc_properties": self.property_fixes.fix_property_values,  # Alias
                "fix_statvar_structure": self.property_fixes.add_constraint_properties,  # Alias
            }
            
            if fix_name in fix_methods:
                logging.info(f"Applying fix strategy: {fix_name}")
                result = fix_methods[fix_name](working_dir, error_details)
                logging.info(f"Fix result: {result.message}")
                return result
            else:
                return FixStrategyResult(
                    False, 
                    f"Unknown fix strategy: {fix_name}",
                    {"available_fixes": list(fix_methods.keys())}
                )
                
        except Exception as e:
            logging.error(f"Fix strategy {fix_name} failed: {str(e)}")
            return FixStrategyResult(False, f"Fix strategy failed: {str(e)}")
            
    def get_available_fixes(self) -> List[str]:
        """Get list of all available fix strategies.
        
        Returns:
            List of fix strategy names
        """
        return [
            "fix_missing_columns",
            "validate_column_mappings", 
            "fix_date_formats",
            "add_aggregation_rules",
            "add_constraint_properties",
            "fix_property_values"
        ]
        
    def backup_files(self, working_dir: str) -> Dict[str, str]:
        """Create backups of all configuration files.
        
        Args:
            working_dir: Directory containing files to backup
            
        Returns:
            Dictionary mapping file names to backup paths
        """
        backups = {}
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        for filename in ["pvmap.csv", "metadata.csv"]:
            file_path = os.path.join(working_dir, filename)
            if os.path.exists(file_path):
                backup_path = f"{file_path}.backup.{timestamp}"
                shutil.copy2(file_path, backup_path)
                backups[filename] = backup_path
                
        return backups