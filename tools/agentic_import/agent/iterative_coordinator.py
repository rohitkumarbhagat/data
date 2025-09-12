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

"""Iterative Coordinator for ADK PVMap Generation - Phase 5

This module implements intelligent retry logic around the existing Phase 4 workflow.
It analyzes failures and applies targeted fixes to improve success rates through
multiple iterations rather than single-shot execution.

Key Features:
- Non-intrusive wrapper around existing execute_workflow()
- Intelligent error analysis and categorization
- Targeted fix strategies for common failure patterns
- Iteration tracking and state management
- Bounded retry logic to prevent infinite loops

Usage:
    coordinator = IterativeCoordinator(max_iterations=3)
    result = coordinator.process_with_retry(input_file, output_dir, working_dir)
"""

import os
import logging
import json
import copy
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

# Import existing workflow components
from .coordinator import execute_workflow, get_workflow_summary


class IterationState:
    """Tracks state across workflow iterations."""
    
    def __init__(self, input_file: str, output_dir: str, working_dir: str):
        self.input_file = input_file
        self.output_dir = output_dir
        self.working_dir = working_dir
        self.iteration_history: List[Dict[str, Any]] = []
        self.applied_fixes: List[str] = []
        self.error_patterns: Dict[str, int] = {}
        self.start_time = datetime.now()
        
    def add_iteration(self, attempt: int, result: Dict[str, Any], fixes_applied: List[str] = None):
        """Record results of an iteration."""
        iteration_record = {
            "attempt": attempt,
            "timestamp": datetime.now().isoformat(),
            "status": result.get("status"),
            "error_step": result.get("error_step"),
            "error_message": result.get("error_message"),
            "fixes_applied": fixes_applied or [],
            "steps_completed": len([k for k, v in result.get("steps", {}).items() 
                                 if v.get("status") == "success"])
        }
        self.iteration_history.append(iteration_record)
        
        if fixes_applied:
            self.applied_fixes.extend(fixes_applied)
            
        # Track error patterns
        if result.get("status") == "error":
            error_step = result.get("error_step", "unknown")
            self.error_patterns[error_step] = self.error_patterns.get(error_step, 0) + 1
            
    def get_summary(self) -> Dict[str, Any]:
        """Generate iteration summary."""
        total_time = (datetime.now() - self.start_time).total_seconds()
        
        return {
            "total_iterations": len(self.iteration_history),
            "total_time_seconds": round(total_time, 2),
            "final_status": self.iteration_history[-1]["status"] if self.iteration_history else "unknown",
            "error_patterns": dict(self.error_patterns),
            "unique_fixes_applied": list(set(self.applied_fixes)),
            "iteration_progress": [(i["attempt"], i["status"], i["steps_completed"]) 
                                 for i in self.iteration_history]
        }


class ErrorAnalyzer:
    """Analyzes workflow failures and suggests fixes."""
    
    @staticmethod
    def analyze_failure(result: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze workflow failure and categorize error type.
        
        Args:
            result: Workflow execution result with error information
            
        Returns:
            Dictionary with error analysis and suggested fixes
        """
        if result.get("status") != "error":
            return {"fixable": False, "reason": "No error to analyze"}
            
        error_step = result.get("error_step", "unknown")
        error_message = result.get("error_message", "").lower()
        
        analysis = {
            "error_step": error_step,
            "error_category": "unknown",
            "fixable": False,
            "confidence": 0.0,
            "suggested_fixes": [],
            "error_details": {}
        }
        
        # Analyze processor execution errors (most common fixable errors)
        if error_step == "processor_execution":
            processor_result = result.get("steps", {}).get("processor_execution", {})
            stderr = processor_result.get("stderr", "").lower()
            
            if "keyerror" in stderr or "missing column" in stderr:
                analysis.update({
                    "error_category": "missing_column",
                    "fixable": True,
                    "confidence": 0.8,
                    "suggested_fixes": ["fix_pvmap_column_mappings", "validate_column_existence"],
                    "error_details": {"stderr_excerpt": stderr[:200]}
                })
                
            elif "valueerror" in stderr and ("date" in stderr or "format" in stderr):
                analysis.update({
                    "error_category": "date_format_error", 
                    "fixable": True,
                    "confidence": 0.7,
                    "suggested_fixes": ["fix_date_formats", "adjust_metadata_config"],
                    "error_details": {"stderr_excerpt": stderr[:200]}
                })
                
            elif "duplicate" in stderr or "aggregat" in stderr:
                analysis.update({
                    "error_category": "duplicate_observations",
                    "fixable": True, 
                    "confidence": 0.6,
                    "suggested_fixes": ["add_aggregation_rules", "fix_constraint_properties"],
                    "error_details": {"stderr_excerpt": stderr[:200]}
                })
                
        # Analyze validation errors
        elif error_step in ["pvmap_validation", "metadata_validation"]:
            validation_issues = []
            
            if error_step == "pvmap_validation":
                pvmap_validation = result.get("steps", {}).get("pvmap_validation", {})
                validation_issues = pvmap_validation.get("issues", [])
                
            elif error_step == "metadata_validation":
                metadata_validation = result.get("steps", {}).get("metadata_validation", {})
                validation_issues = metadata_validation.get("issues", [])
                
            analysis.update({
                "error_category": "validation_error",
                "fixable": True,
                "confidence": 0.5,
                "suggested_fixes": ["fix_validation_issues"],
                "error_details": {"validation_issues": validation_issues}
            })
            
        return analysis


class FixStrategies:
    """Implements fix strategies for different error types."""
    
    @staticmethod
    def fix_pvmap_column_mappings(working_dir: str, error_details: Dict[str, Any]) -> Dict[str, Any]:
        """Fix PVMap by removing/correcting invalid column mappings.
        
        Args:
            working_dir: Directory containing pvmap.csv
            error_details: Error analysis details
            
        Returns:
            Dictionary with fix results
        """
        try:
            pvmap_path = os.path.join(working_dir, "pvmap.csv")
            if not os.path.exists(pvmap_path):
                return {"status": "error", "message": "PVMap file not found"}
                
            # Read current PVMap
            import pandas as pd
            df = pd.read_csv(pvmap_path)
            
            # Extract column names from error message if possible
            stderr = error_details.get("stderr_excerpt", "")
            original_count = len(df)
            
            # Remove mappings that reference clearly invalid columns
            # This is a simple heuristic - in practice, we'd need more sophisticated analysis
            invalid_patterns = ["unnamed:", "column_", "index_"]
            df_filtered = df[~df['input'].str.lower().str.contains('|'.join(invalid_patterns), na=False)]
            
            removed_count = original_count - len(df_filtered)
            
            if removed_count > 0:
                # Write back the filtered PVMap
                df_filtered.to_csv(pvmap_path, index=False)
                return {
                    "status": "success",
                    "fix_applied": "fix_pvmap_column_mappings",
                    "message": f"Removed {removed_count} potentially invalid column mappings",
                    "details": {"original_count": original_count, "final_count": len(df_filtered)}
                }
            else:
                return {
                    "status": "no_change",
                    "message": "No obvious invalid column mappings found to fix"
                }
                
        except Exception as e:
            logging.error(f"PVMap column fix failed: {str(e)}")
            return {"status": "error", "message": f"Fix failed: {str(e)}"}
            
    @staticmethod  
    def fix_date_formats(working_dir: str, error_details: Dict[str, Any]) -> Dict[str, Any]:
        """Fix metadata configuration for date format issues.
        
        Args:
            working_dir: Directory containing metadata.csv
            error_details: Error analysis details
            
        Returns:
            Dictionary with fix results
        """
        try:
            metadata_path = os.path.join(working_dir, "metadata.csv")
            if not os.path.exists(metadata_path):
                return {"status": "error", "message": "Metadata file not found"}
                
            # Read current metadata
            import pandas as pd
            df = pd.read_csv(metadata_path)
            
            fixes_applied = []
            
            # Try common date format fixes
            if 'date_format' in df.columns:
                # Change to more flexible date format
                df.loc[df['Property'] == 'date_format', 'Value'] = '%Y-%m-%d'
                fixes_applied.append("standardized_date_format")
                
            if 'observation_date_format' in df.columns:
                df.loc[df['Property'] == 'observation_date_format', 'Value'] = '%Y-%m-%d'
                fixes_applied.append("standardized_observation_date_format")
                
            if fixes_applied:
                df.to_csv(metadata_path, index=False)
                return {
                    "status": "success",
                    "fix_applied": "fix_date_formats",
                    "message": f"Applied date format fixes: {', '.join(fixes_applied)}",
                    "details": {"fixes": fixes_applied}
                }
            else:
                return {
                    "status": "no_change",
                    "message": "No date format configurations found to fix"
                }
                
        except Exception as e:
            logging.error(f"Date format fix failed: {str(e)}")
            return {"status": "error", "message": f"Fix failed: {str(e)}"}


class IterativeCoordinator:
    """Coordinates workflow execution with intelligent retry logic."""
    
    def __init__(self, max_iterations: int = 3, auto_fix: bool = True):
        """Initialize iterative coordinator.
        
        Args:
            max_iterations: Maximum number of retry attempts
            auto_fix: Whether to automatically apply fixes
        """
        self.max_iterations = max_iterations
        self.auto_fix = auto_fix
        self.error_analyzer = ErrorAnalyzer()
        self.fix_strategies = FixStrategies()
        
    def process_with_retry(self, input_file: str, output_dir: str, working_dir: str = None) -> Dict[str, Any]:
        """Execute workflow with intelligent retry logic.
        
        Args:
            input_file: Path to input CSV file
            output_dir: Directory for output files  
            working_dir: Working directory (defaults to output_dir)
            
        Returns:
            Dictionary with final workflow results including iteration history
        """
        if working_dir is None:
            working_dir = output_dir
            
        # Initialize state tracking
        state = IterationState(input_file, output_dir, working_dir)
        
        logging.info(f"Starting iterative workflow (max_iterations={self.max_iterations})")
        logging.info(f"Input: {input_file}")
        logging.info(f"Auto-fix enabled: {self.auto_fix}")
        
        for attempt in range(1, self.max_iterations + 1):
            logging.info(f"\n🔄 ITERATION {attempt}/{self.max_iterations}")
            
            # Execute the core workflow
            result = execute_workflow(input_file, output_dir, working_dir)
            
            # Check if successful
            if result.get("status") == "success":
                logging.info(f"✅ SUCCESS on iteration {attempt}!")
                state.add_iteration(attempt, result)
                
                # Add iteration summary to final result
                final_result = copy.deepcopy(result)
                final_result["iteration_summary"] = state.get_summary()
                return final_result
                
            # We have a failure - analyze and potentially fix
            logging.info(f"❌ Iteration {attempt} failed at step: {result.get('error_step')}")
            
            # Analyze the error
            error_analysis = self.error_analyzer.analyze_failure(result)
            logging.info(f"Error analysis: {error_analysis['error_category']} (confidence: {error_analysis['confidence']:.1f})")
            
            fixes_applied = []
            
            # Apply fixes if possible and enabled
            if self.auto_fix and error_analysis.get("fixable", False) and attempt < self.max_iterations:
                logging.info("Attempting to apply fixes...")
                
                for fix_name in error_analysis.get("suggested_fixes", []):
                    # Apply the specific fix strategy
                    if hasattr(self.fix_strategies, fix_name):
                        fix_func = getattr(self.fix_strategies, fix_name)
                        fix_result = fix_func(working_dir, error_analysis.get("error_details", {}))
                        
                        if fix_result.get("status") == "success":
                            logging.info(f"  ✅ Applied fix: {fix_result.get('message', fix_name)}")
                            fixes_applied.append(fix_name)
                        else:
                            logging.info(f"  ❌ Fix failed: {fix_result.get('message', 'Unknown error')}")
                            
            # Record this iteration
            state.add_iteration(attempt, result, fixes_applied)
            
            # If we're at max iterations or no fixes were applied, stop
            if attempt == self.max_iterations or not fixes_applied:
                if attempt == self.max_iterations:
                    logging.error(f"⛔ FAILED after {self.max_iterations} iterations")
                else:
                    logging.error("⛔ No applicable fixes found, stopping iterations")
                    
                # Return final failure result with iteration history
                final_result = copy.deepcopy(result)
                final_result["iteration_summary"] = state.get_summary()
                return final_result
                
            logging.info(f"Retrying with applied fixes: {', '.join(fixes_applied)}")
            
        # Should never reach here, but just in case
        final_result = {"status": "error", "error_message": "Unexpected iteration loop termination"}
        final_result["iteration_summary"] = state.get_summary()
        return final_result