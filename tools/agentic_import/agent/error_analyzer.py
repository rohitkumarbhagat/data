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

"""Advanced Error Analysis for ADK PVMap Generation

This module provides sophisticated error analysis capabilities for the iterative
workflow coordinator. It can parse complex error messages, extract specific 
details, and suggest targeted fixes.

Key Features:
- Regex-based error pattern matching
- Extraction of specific error details (column names, expected formats, etc.)
- Confidence scoring for fix strategies
- Learning from historical error patterns
- Support for multiple error types within single failures
"""

import re
import os
import logging
from typing import Dict, Any, List, Optional, Tuple
from collections import defaultdict


class ProcessorErrorAnalyzer:
    """Advanced analyzer for statvar processor errors."""
    
    def __init__(self):
        """Initialize error analyzer with pattern database."""
        self.error_patterns = self._build_error_patterns()
        self.error_history: Dict[str, int] = defaultdict(int)
        
    def _build_error_patterns(self) -> Dict[str, Dict[str, Any]]:
        """Build comprehensive error pattern database.
        
        Returns:
            Dictionary mapping error types to pattern information
        """
        return {
            "missing_column": {
                "patterns": [
                    r"KeyError:\s*['\"]([^'\"]+)['\"]",
                    r"Column\s*['\"]([^'\"]+)['\"]\s*not found",
                    r"Missing column[s]?:\s*([^\n]+)",
                    r"Column\s*([^\s]+)\s*does not exist",
                    r"No such column[s]?:\s*([^\n]+)"
                ],
                "extract_details": True,
                "confidence_base": 0.9,
                "fix_strategies": ["fix_missing_columns", "validate_column_mappings"],
                "description": "Referenced columns don't exist in the input data"
            },
            
            "date_format_error": {
                "patterns": [
                    r"ValueError.*time data\s*['\"]([^'\"]*)['\"].*format\s*['\"]([^'\"]*)['\"]",
                    r"Invalid date format.*expected\s*([^\s,]+).*got\s*([^\s,]+)",
                    r"strptime.*does not match format",
                    r"time data.*does not match.*%[YmdHMS-]+",
                    r"Unable to parse date.*([^\n]+)"
                ],
                "extract_details": True,
                "confidence_base": 0.8,
                "fix_strategies": ["fix_date_formats", "adjust_date_parsing"],
                "description": "Date values don't match expected format"
            },
            
            "duplicate_observations": {
                "patterns": [
                    r"Duplicate observations.*([^\n]+)",
                    r"Multiple values for same.*([^\n]+)",
                    r"Aggregation required.*([^\n]+)",
                    r"Non-unique.*combination.*([^\n]+)"
                ],
                "extract_details": True,
                "confidence_base": 0.7,
                "fix_strategies": ["add_aggregation_rules", "fix_constraint_properties"],
                "description": "Multiple values for same observation key"
            },
            
            "invalid_property_value": {
                "patterns": [
                    r"Invalid value.*property\s*['\"]([^'\"]+)['\"].*value\s*['\"]([^'\"]+)['\"]",
                    r"Property\s*([^\s]+)\s*cannot have value\s*([^\s]+)",
                    r"Validation failed.*property.*([^\n]+)",
                    r"Unknown property.*([^\n]+)"
                ],
                "extract_details": True,
                "confidence_base": 0.6,
                "fix_strategies": ["fix_property_values", "validate_dc_properties"],
                "description": "Property values don't conform to Data Commons schema"
            },
            
            "place_resolution_error": {
                "patterns": [
                    r"Cannot resolve place.*([^\n]+)",
                    r"Unknown place.*([^\n]+)",
                    r"Place resolution failed.*([^\n]+)",
                    r"Invalid place identifier.*([^\n]+)"
                ],
                "extract_details": True,
                "confidence_base": 0.5,
                "fix_strategies": ["fix_place_mappings", "adjust_place_resolution"],
                "description": "Geographic places cannot be resolved"
            },
            
            "constraint_property_error": {
                "patterns": [
                    r"Missing constraint.*property.*([^\n]+)",
                    r"Constraint.*required.*([^\n]+)",
                    r"StatVar.*missing.*constraint.*([^\n]+)"
                ],
                "extract_details": True,
                "confidence_base": 0.6,
                "fix_strategies": ["add_constraint_properties", "fix_statvar_structure"],
                "description": "Statistical variables missing required constraint properties"
            },
            
            "file_processing_error": {
                "patterns": [
                    r"FileNotFoundError.*([^\n]+)",
                    r"PermissionError.*([^\n]+)",
                    r"IOError.*([^\n]+)",
                    r"Cannot read.*file.*([^\n]+)"
                ],
                "extract_details": True,
                "confidence_base": 0.9,
                "fix_strategies": ["check_file_paths", "fix_permissions"],
                "description": "Issues with file access or permissions"
            },
            
            "memory_resource_error": {
                "patterns": [
                    r"MemoryError",
                    r"Out of memory",
                    r"Cannot allocate.*memory",
                    r"Resource temporarily unavailable"
                ],
                "extract_details": False,
                "confidence_base": 0.4,  # Lower confidence as harder to fix automatically
                "fix_strategies": ["optimize_memory_usage", "process_in_chunks"],
                "description": "Insufficient memory or system resources"
            },
            
            "data_type_error": {
                "patterns": [
                    r"TypeError.*expected.*([^\n]+)",
                    r"Cannot convert.*to.*([^\n]+)",
                    r"Invalid data type.*([^\n]+)",
                    r"Type mismatch.*([^\n]+)"
                ],
                "extract_details": True,
                "confidence_base": 0.7,
                "fix_strategies": ["fix_data_types", "add_type_conversion"],
                "description": "Data type mismatches in processing"
            }
        }
        
    def analyze_workflow_failure(self, workflow_result: Dict[str, Any]) -> Dict[str, Any]:
        """Perform comprehensive analysis of workflow failure.
        
        Args:
            workflow_result: Complete workflow execution result
            
        Returns:
            Detailed analysis with categorized errors and suggested fixes
        """
        if workflow_result.get("status") != "error":
            return {"status": "no_error", "analysis": None}
            
        analysis = {
            "status": "analyzed",
            "primary_error": None,
            "secondary_errors": [],
            "error_step": workflow_result.get("error_step"),
            "fixable_errors": [],
            "unfixable_reasons": [],
            "confidence_score": 0.0,
            "suggested_fixes": [],
            "detailed_findings": {}
        }
        
        # Focus analysis based on where the failure occurred
        if workflow_result.get("error_step") == "processor_execution":
            analysis.update(self._analyze_processor_errors(workflow_result))
        elif workflow_result.get("error_step") in ["pvmap_validation", "metadata_validation"]:
            analysis.update(self._analyze_validation_errors(workflow_result))
        elif workflow_result.get("error_step") in ["pvmap_write", "metadata_write"]:
            analysis.update(self._analyze_file_errors(workflow_result))
        else:
            analysis.update(self._analyze_generic_error(workflow_result))
            
        # Calculate overall confidence and fix recommendations
        analysis["confidence_score"] = self._calculate_confidence_score(analysis)
        analysis["suggested_fixes"] = self._prioritize_fixes(analysis)
        
        # Update error history for learning
        if analysis["primary_error"]:
            self.error_history[analysis["primary_error"]["category"]] += 1
            
        return analysis
        
    def _analyze_processor_errors(self, workflow_result: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze errors from statvar processor execution.
        
        Args:
            workflow_result: Workflow result containing processor error info
            
        Returns:
            Analysis specific to processor errors
        """
        processor_step = workflow_result.get("steps", {}).get("processor_execution", {})
        stderr = processor_step.get("stderr", "")
        stdout = processor_step.get("stdout", "")
        exit_code = processor_step.get("exit_code", -1)
        
        analysis = {
            "error_source": "processor_execution",
            "exit_code": exit_code,
            "stderr_length": len(stderr),
            "stdout_length": len(stdout)
        }
        
        # Find all matching error patterns
        detected_errors = []
        
        for error_type, pattern_info in self.error_patterns.items():
            for pattern in pattern_info["patterns"]:
                matches = re.finditer(pattern, stderr, re.IGNORECASE | re.MULTILINE)
                
                for match in matches:
                    error_details = {
                        "category": error_type,
                        "pattern_matched": pattern,
                        "confidence": pattern_info["confidence_base"],
                        "description": pattern_info["description"],
                        "fix_strategies": pattern_info["fix_strategies"].copy()
                    }
                    
                    # Extract specific details if pattern captures groups
                    if pattern_info["extract_details"] and match.groups():
                        error_details["extracted_details"] = list(match.groups())
                        error_details["match_text"] = match.group(0)
                        # Boost confidence if we extracted specific details
                        error_details["confidence"] = min(1.0, error_details["confidence"] + 0.1)
                        
                    detected_errors.append(error_details)
                    
        # Prioritize errors by confidence and frequency
        detected_errors.sort(key=lambda x: (-x["confidence"], -self.error_history.get(x["category"], 0)))
        
        if detected_errors:
            analysis["primary_error"] = detected_errors[0]
            analysis["secondary_errors"] = detected_errors[1:5]  # Top 5 additional errors
            
            # Categorize as fixable/unfixable
            for error in detected_errors:
                if error["confidence"] >= 0.5:
                    analysis.setdefault("fixable_errors", []).append(error)
                else:
                    analysis.setdefault("unfixable_reasons", []).append(
                        f"Low confidence for {error['category']} ({error['confidence']:.1f})"
                    )
        else:
            # No patterns matched - generic processor error
            analysis["primary_error"] = {
                "category": "unknown_processor_error",
                "confidence": 0.3,
                "description": "Processor failed with unrecognized error pattern",
                "fix_strategies": ["manual_investigation_required"]
            }
            analysis["unfixable_reasons"] = ["Unknown error pattern - manual investigation needed"]
            
        return analysis
        
    def _analyze_validation_errors(self, workflow_result: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze validation step errors.
        
        Args:
            workflow_result: Workflow result containing validation error info
            
        Returns:
            Analysis specific to validation errors  
        """
        error_step = workflow_result.get("error_step")
        steps = workflow_result.get("steps", {})
        
        validation_step = steps.get(error_step, {})
        issues = validation_step.get("issues", [])
        
        analysis = {
            "error_source": error_step,
            "validation_issues": issues,
            "issue_count": len(issues)
        }
        
        # Analyze validation issues to determine fixability
        fixable_issues = []
        unfixable_issues = []
        
        for issue in issues:
            issue_lower = issue.lower()
            
            if any(keyword in issue_lower for keyword in ["missing", "required", "empty"]):
                fixable_issues.append({
                    "issue": issue,
                    "category": "missing_required_field",
                    "confidence": 0.7,
                    "fix_strategies": ["add_missing_fields", "fix_validation_requirements"]
                })
            elif any(keyword in issue_lower for keyword in ["invalid", "format", "type"]):
                fixable_issues.append({
                    "issue": issue,
                    "category": "invalid_format",
                    "confidence": 0.6,
                    "fix_strategies": ["fix_format_issues", "correct_data_types"]
                })
            else:
                unfixable_issues.append({
                    "issue": issue,
                    "category": "complex_validation_error",
                    "reason": "Requires manual investigation"
                })
                
        if fixable_issues:
            analysis["primary_error"] = fixable_issues[0]
            analysis["fixable_errors"] = fixable_issues
            
        if unfixable_issues:
            analysis["unfixable_reasons"] = [item["reason"] for item in unfixable_issues]
            
        return analysis
        
    def _analyze_file_errors(self, workflow_result: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze file operation errors.
        
        Args:
            workflow_result: Workflow result containing file error info
            
        Returns:
            Analysis specific to file operation errors
        """
        error_message = workflow_result.get("error_message", "").lower()
        
        analysis = {"error_source": "file_operations"}
        
        if "permission" in error_message:
            analysis["primary_error"] = {
                "category": "permission_error",
                "confidence": 0.8,
                "description": "File permission issues",
                "fix_strategies": ["fix_file_permissions", "check_directory_access"]
            }
        elif "not found" in error_message or "no such file" in error_message:
            analysis["primary_error"] = {
                "category": "file_not_found",
                "confidence": 0.9,
                "description": "Required files are missing",
                "fix_strategies": ["verify_file_paths", "create_missing_files"]
            }
        else:
            analysis["primary_error"] = {
                "category": "generic_file_error",
                "confidence": 0.4,
                "description": "File operation failed",
                "fix_strategies": ["investigate_file_issues"]
            }
            
        return analysis
        
    def _analyze_generic_error(self, workflow_result: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze errors that don't fit specific categories.
        
        Args:
            workflow_result: Workflow result containing generic error info
            
        Returns:
            Generic error analysis
        """
        return {
            "error_source": "generic",
            "primary_error": {
                "category": "unknown_error",
                "confidence": 0.2,
                "description": f"Error in step: {workflow_result.get('error_step', 'unknown')}",
                "fix_strategies": ["manual_investigation_required"]
            },
            "unfixable_reasons": ["Unknown error type - requires manual investigation"]
        }
        
    def _calculate_confidence_score(self, analysis: Dict[str, Any]) -> float:
        """Calculate overall confidence score for the analysis.
        
        Args:
            analysis: Analysis results
            
        Returns:
            Confidence score between 0.0 and 1.0
        """
        if not analysis.get("primary_error"):
            return 0.0
            
        primary_confidence = analysis["primary_error"].get("confidence", 0.0)
        
        # Boost confidence if we have multiple supporting errors
        secondary_boost = min(0.2, len(analysis.get("secondary_errors", [])) * 0.05)
        
        # Reduce confidence if we have unfixable errors
        unfixable_penalty = min(0.3, len(analysis.get("unfixable_reasons", [])) * 0.1)
        
        # Historical success boost
        category = analysis["primary_error"].get("category", "")
        history_boost = min(0.1, self.error_history.get(category, 0) * 0.02)
        
        final_confidence = primary_confidence + secondary_boost - unfixable_penalty + history_boost
        return max(0.0, min(1.0, final_confidence))
        
    def _prioritize_fixes(self, analysis: Dict[str, Any]) -> List[str]:
        """Prioritize fix strategies based on analysis.
        
        Args:
            analysis: Analysis results
            
        Returns:
            Prioritized list of fix strategy names
        """
        if not analysis.get("primary_error"):
            return []
            
        # Start with primary error fixes
        fixes = analysis["primary_error"].get("fix_strategies", []).copy()
        
        # Add secondary error fixes if they're different
        for secondary_error in analysis.get("secondary_errors", []):
            for fix in secondary_error.get("fix_strategies", []):
                if fix not in fixes:
                    fixes.append(fix)
                    
        # Limit to most promising fixes
        return fixes[:3]
        
    def extract_error_specifics(self, error_category: str, extracted_details: List[str]) -> Dict[str, Any]:
        """Extract specific actionable details from error matches.
        
        Args:
            error_category: Category of error
            extracted_details: Details extracted from regex groups
            
        Returns:
            Specific error details for targeted fixing
        """
        specifics = {"category": error_category, "details": {}}
        
        if error_category == "missing_column" and extracted_details:
            # First group usually contains the missing column name
            specifics["details"]["missing_columns"] = [extracted_details[0]]
            
        elif error_category == "date_format_error" and len(extracted_details) >= 2:
            # Usually contains actual value and expected format
            specifics["details"]["actual_value"] = extracted_details[0]
            specifics["details"]["expected_format"] = extracted_details[1]
            
        elif error_category == "duplicate_observations" and extracted_details:
            # Contains details about what's duplicated
            specifics["details"]["duplication_info"] = extracted_details[0]
            
        elif error_category == "invalid_property_value" and len(extracted_details) >= 2:
            # Contains property name and invalid value
            specifics["details"]["property_name"] = extracted_details[0]
            specifics["details"]["invalid_value"] = extracted_details[1]
            
        return specifics