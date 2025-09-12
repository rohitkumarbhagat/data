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

"""Enhanced Iterative Coordinator with Advanced Fix Strategies - Phase 6

This module extends the Phase 5 iterative coordinator with sophisticated
error recovery capabilities including predictive analysis, semantic matching,
and adaptive learning from historical patterns.

Key Features:
- Proactive error prediction before processing begins
- Semantic column mapping with NLP techniques  
- Adaptive fix selection based on historical success
- Learning from outcomes to improve future performance
- Advanced risk assessment and mitigation
- Comprehensive reporting and analytics

Usage:
    coordinator = EnhancedIterativeCoordinator(max_iterations=3, use_advanced_fixes=True)
    result = coordinator.process_with_advanced_retry(input_file, output_dir, working_dir)
"""

import os
import logging
import json
import copy
import pandas as pd
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

# Import existing workflow components
from .coordinator import execute_workflow, get_workflow_summary
from .iterative_coordinator import IterativeCoordinator, IterationState, ErrorAnalyzer, FixStrategies
from .advanced_fixes import AdvancedFixStrategies, ErrorPrediction, ColumnMapping


class EnhancedIterationState(IterationState):
    """Extended state tracking with advanced fix capabilities."""
    
    def __init__(self, input_file: str, output_dir: str, working_dir: str, use_advanced_fixes: bool = True):
        super().__init__(input_file, output_dir, working_dir)
        self.use_advanced_fixes = use_advanced_fixes
        self.proactive_predictions: List[ErrorPrediction] = []
        self.column_mappings: List[ColumnMapping] = []
        self.advanced_fixes_applied: List[str] = []
        self.learning_outcomes: List[Dict[str, Any]] = []
        self.risk_assessment: Dict[str, Any] = {}
        
    def add_proactive_analysis(self, predictions: List[ErrorPrediction], 
                              mappings: List[ColumnMapping], risk_assessment: Dict[str, Any]):
        """Add proactive analysis results."""
        self.proactive_predictions = predictions
        self.column_mappings = mappings 
        self.risk_assessment = risk_assessment
        
    def add_advanced_fix(self, fix_name: str, outcome: str, confidence: float):
        """Record advanced fix application."""
        self.advanced_fixes_applied.append(fix_name)
        self.learning_outcomes.append({
            "fix_name": fix_name,
            "outcome": outcome,
            "confidence": confidence,
            "timestamp": datetime.now().isoformat()
        })
        
    def get_enhanced_summary(self) -> Dict[str, Any]:
        """Get enhanced summary including advanced fix information."""
        base_summary = self.get_summary()
        
        enhanced_summary = {
            **base_summary,
            "proactive_predictions": len(self.proactive_predictions),
            "column_mappings_found": len(self.column_mappings),
            "advanced_fixes_attempted": len(self.advanced_fixes_applied),
            "learning_outcomes": self.learning_outcomes,
            "risk_assessment": self.risk_assessment,
            "prediction_accuracy": self._calculate_prediction_accuracy()
        }
        
        return enhanced_summary
        
    def _calculate_prediction_accuracy(self) -> Dict[str, float]:
        """Calculate how accurate proactive predictions were."""
        if not self.proactive_predictions or not self.iteration_history:
            return {"accuracy": 0.0, "sample_size": 0}
            
        correct_predictions = 0
        total_predictions = len(self.proactive_predictions)
        
        # Check if predicted errors actually occurred
        actual_errors = set()
        for iteration in self.iteration_history:
            if iteration.get("error_step"):
                actual_errors.add(iteration["error_step"])
                
        predicted_errors = set(pred.error_type for pred in self.proactive_predictions)
        correct_predictions = len(predicted_errors & actual_errors)
        
        accuracy = correct_predictions / total_predictions if total_predictions > 0 else 0.0
        
        return {
            "accuracy": accuracy,
            "sample_size": total_predictions,
            "correct_predictions": correct_predictions
        }


class EnhancedIterativeCoordinator:
    """Enhanced coordinator with advanced fix strategies and learning."""
    
    def __init__(self, max_iterations: int = 3, auto_fix: bool = True, 
                 use_advanced_fixes: bool = True, learning_dir: str = None):
        """Initialize enhanced coordinator.
        
        Args:
            max_iterations: Maximum number of retry attempts
            auto_fix: Enable automatic fixing
            use_advanced_fixes: Enable advanced fix strategies
            learning_dir: Directory for storing learning data
        """
        self.max_iterations = max_iterations
        self.auto_fix = auto_fix
        self.use_advanced_fixes = use_advanced_fixes
        self.learning_dir = learning_dir
        
        # Initialize basic components (fallback to Phase 5 behavior)
        self.basic_error_analyzer = ErrorAnalyzer()
        self.basic_fix_strategies = FixStrategies()
        
        # Initialize advanced components if enabled
        if self.use_advanced_fixes:
            self.advanced_fixes = AdvancedFixStrategies(learning_dir)
            logging.info("Enhanced coordinator initialized with advanced fix strategies")
        else:
            self.advanced_fixes = None
            logging.info("Enhanced coordinator initialized in basic mode")
            
    def process_with_advanced_retry(self, input_file: str, output_dir: str, 
                                  working_dir: str = None) -> Dict[str, Any]:
        """Execute workflow with advanced retry logic and learning.
        
        Args:
            input_file: Path to input CSV file
            output_dir: Directory for output files  
            working_dir: Working directory (defaults to output_dir)
            
        Returns:
            Dictionary with comprehensive workflow results
        """
        if working_dir is None:
            working_dir = output_dir
            
        # Initialize enhanced state tracking
        state = EnhancedIterationState(input_file, output_dir, working_dir, self.use_advanced_fixes)
        
        logging.info(f"Starting enhanced iterative workflow (max_iterations={self.max_iterations})")
        logging.info(f"Input: {input_file}")
        logging.info(f"Advanced fixes enabled: {self.use_advanced_fixes}")
        
        try:
            # Phase 1: Proactive Analysis (if advanced fixes enabled)
            if self.use_advanced_fixes:
                proactive_results = self._perform_proactive_analysis(input_file, working_dir, state)
                if proactive_results.get("critical_issues"):
                    logging.warning("Critical issues detected in proactive analysis")
                    for issue in proactive_results["critical_issues"]:
                        logging.warning(f"  • {issue}")
                        
            # Phase 2: Iterative Execution with Enhanced Error Recovery
            final_result = self._execute_enhanced_iterations(input_file, output_dir, working_dir, state)
            
            # Phase 3: Learning and Analysis
            if self.use_advanced_fixes:
                self._perform_learning_analysis(state, final_result)
                
            # Compile final results
            enhanced_result = {
                **final_result,
                "enhanced_summary": state.get_enhanced_summary(),
                "proactive_analysis": proactive_results if self.use_advanced_fixes else None,
                "learning_insights": self._generate_learning_insights(state) if self.use_advanced_fixes else None
            }
            
            return enhanced_result
            
        except Exception as e:
            logging.error(f"Enhanced iterative workflow failed: {str(e)}")
            # Return basic result with error info
            return {
                "status": "error",
                "error_message": str(e),
                "enhanced_summary": state.get_enhanced_summary()
            }
            
    def _perform_proactive_analysis(self, input_file: str, working_dir: str, 
                                  state: EnhancedIterationState) -> Dict[str, Any]:
        """Perform proactive analysis before workflow execution."""
        logging.info("🔍 Performing proactive error analysis...")
        
        try:
            # Check for existing PVMap to analyze compatibility
            pvmap_data = None
            pvmap_path = os.path.join(working_dir, "pvmap.csv")
            if os.path.exists(pvmap_path):
                pvmap_data = pd.read_csv(pvmap_path)
                
            # Get proactive recommendations
            recommendations = self.advanced_fixes.get_proactive_recommendations(input_file, pvmap_data)
            
            # Parse recommendations
            predictions = []
            if "predictions" in recommendations:
                for pred_dict in recommendations["predictions"]:
                    pred = ErrorPrediction(**pred_dict)
                    predictions.append(pred)
                    
            mappings = []
            if "column_mappings" in recommendations:
                for map_dict in recommendations["column_mappings"]:
                    mapping = ColumnMapping(**map_dict)
                    mappings.append(mapping)
                    
            risk_assessment = recommendations.get("risk_assessment", {})
            
            # Update state with analysis results
            state.add_proactive_analysis(predictions, mappings, risk_assessment)
            
            # Generate user-friendly summary
            analysis_summary = {
                "total_predictions": len(predictions),
                "risk_level": risk_assessment.get("overall_risk", "unknown"),
                "column_mappings": len(mappings),
                "recommended_actions": recommendations.get("recommended_actions", []),
                "critical_issues": [
                    pred.description for pred in predictions 
                    if pred.risk_level == "critical"
                ],
                "proactive_fixes_available": len(recommendations.get("proactive_fixes", []))
            }
            
            # Log key findings
            if analysis_summary["critical_issues"]:
                logging.warning(f"Found {len(analysis_summary['critical_issues'])} critical issues")
            if analysis_summary["risk_level"] in ["high", "critical"]:
                logging.warning(f"Overall risk level: {analysis_summary['risk_level']}")
            if analysis_summary["column_mappings"] > 0:
                logging.info(f"Found {analysis_summary['column_mappings']} semantic column mappings")
                
            return analysis_summary
            
        except Exception as e:
            logging.error(f"Proactive analysis failed: {e}")
            return {"error": str(e)}
            
    def _execute_enhanced_iterations(self, input_file: str, output_dir: str, 
                                   working_dir: str, state: EnhancedIterationState) -> Dict[str, Any]:
        """Execute workflow iterations with enhanced error recovery."""
        
        for attempt in range(1, self.max_iterations + 1):
            logging.info(f"\n🔄 ENHANCED ITERATION {attempt}/{self.max_iterations}")
            
            # Execute the core workflow
            result = execute_workflow(input_file, output_dir, working_dir)
            
            # Check if successful
            if result.get("status") == "success":
                logging.info(f"✅ SUCCESS on enhanced iteration {attempt}!")
                state.add_iteration(attempt, result)
                return result
                
            # We have a failure - perform enhanced error analysis
            logging.info(f"❌ Enhanced iteration {attempt} failed at step: {result.get('error_step')}")
            
            # Analyze error with both basic and advanced methods
            fixes_applied = []
            
            # Basic error analysis (fallback)
            basic_analysis = self.basic_error_analyzer.analyze_failure(result)
            
            # Advanced error analysis (if available)
            if self.use_advanced_fixes and self.auto_fix and attempt < self.max_iterations:
                advanced_fixes_applied = self._apply_advanced_fixes(
                    result, working_dir, state, basic_analysis
                )
                fixes_applied.extend(advanced_fixes_applied)
            
            # Apply basic fixes if no advanced fixes or as supplement
            if self.auto_fix and attempt < self.max_iterations:
                basic_fixes_applied = self._apply_basic_fixes(result, working_dir, basic_analysis)
                fixes_applied.extend(basic_fixes_applied)
                
            # Record this iteration
            state.add_iteration(attempt, result, fixes_applied)
            
            # If we're at max iterations or no fixes were applied, stop
            if attempt == self.max_iterations or not fixes_applied:
                if attempt == self.max_iterations:
                    logging.error(f"⛔ FAILED after {self.max_iterations} enhanced iterations")
                else:
                    logging.error("⛔ No applicable fixes found, stopping iterations")
                    
                return result
                
            logging.info(f"Retrying with applied fixes: {', '.join(fixes_applied)}")
            
        # Should never reach here
        return {"status": "error", "error_message": "Unexpected iteration termination"}
        
    def _apply_advanced_fixes(self, result: Dict[str, Any], working_dir: str, 
                            state: EnhancedIterationState, basic_analysis: Dict[str, Any]) -> List[str]:
        """Apply advanced fix strategies."""
        fixes_applied = []
        
        try:
            error_type = result.get("error_step", "unknown")
            error_context = {
                "working_dir": working_dir,
                "error_step": error_type,
                "iteration": len(state.iteration_history) + 1,
                "previous_fixes": state.applied_fixes
            }
            
            # Get best fixes from adaptive selector
            best_fixes = self.advanced_fixes.adaptive_selector.get_best_fixes(
                error_type, error_context
            )
            
            logging.info(f"Advanced analysis suggests {len(best_fixes)} potential fixes")
            
            for fix_name, confidence in best_fixes[:2]:  # Try top 2 fixes
                logging.info(f"  🔧 Applying advanced fix: {fix_name} (confidence: {confidence:.2f})")
                
                try:
                    # Apply the fix (delegating to appropriate fix strategy)
                    fix_result = self._apply_specific_advanced_fix(
                        fix_name, working_dir, result, state
                    )
                    
                    if fix_result.get("success"):
                        fixes_applied.append(f"advanced_{fix_name}")
                        state.add_advanced_fix(fix_name, "success", confidence)
                        logging.info(f"  ✅ Advanced fix applied: {fix_result.get('message', fix_name)}")
                    else:
                        state.add_advanced_fix(fix_name, "failed", confidence)
                        logging.info(f"  ❌ Advanced fix failed: {fix_result.get('message', 'Unknown error')}")
                        
                except Exception as e:
                    logging.error(f"  ❌ Advanced fix {fix_name} failed with exception: {e}")
                    state.add_advanced_fix(fix_name, "exception", confidence)
                    
        except Exception as e:
            logging.error(f"Advanced fix application failed: {e}")
            
        return fixes_applied
        
    def _apply_specific_advanced_fix(self, fix_name: str, working_dir: str, 
                                   result: Dict[str, Any], state: EnhancedIterationState) -> Dict[str, Any]:
        """Apply a specific advanced fix strategy."""
        
        # For now, delegate to the comprehensive fix strategies from Phase 5
        # In a full implementation, this would include more sophisticated fixes
        
        try:
            from .fix_strategies import ComprehensiveFixStrategies
            
            comprehensive_fixes = ComprehensiveFixStrategies()
            error_details = result.get("steps", {}).get(result.get("error_step"), {})
            
            # Map advanced fix names to comprehensive fix methods
            fix_mapping = {
                "fix_missing_columns": "fix_missing_columns",
                "fix_date_formats": "fix_date_formats", 
                "add_aggregation_rules": "add_aggregation_rules",
                "add_constraint_properties": "add_constraint_properties",
                "fix_property_values": "fix_property_values"
            }
            
            if fix_name in fix_mapping:
                comprehensive_fix_name = fix_mapping[fix_name]
                fix_result = comprehensive_fixes.apply_fix(
                    comprehensive_fix_name, working_dir, error_details, state.input_file
                )
                return fix_result.to_dict()
            else:
                return {"success": False, "message": f"Advanced fix {fix_name} not implemented"}
                
        except Exception as e:
            return {"success": False, "message": f"Fix application failed: {e}"}
            
    def _apply_basic_fixes(self, result: Dict[str, Any], working_dir: str, 
                         basic_analysis: Dict[str, Any]) -> List[str]:
        """Apply basic fix strategies as fallback."""
        fixes_applied = []
        
        if basic_analysis.get("fixable", False):
            for fix_name in basic_analysis.get("suggested_fixes", []):
                if hasattr(self.basic_fix_strategies, fix_name):
                    try:
                        fix_func = getattr(self.basic_fix_strategies, fix_name)
                        fix_result = fix_func(working_dir, basic_analysis.get("error_details", {}))
                        
                        if fix_result.get("status") == "success":
                            fixes_applied.append(f"basic_{fix_name}")
                            logging.info(f"  ✅ Basic fix applied: {fix_result.get('message', fix_name)}")
                        else:
                            logging.info(f"  ❌ Basic fix failed: {fix_result.get('message', 'Unknown error')}")
                            
                    except Exception as e:
                        logging.error(f"  ❌ Basic fix {fix_name} failed with exception: {e}")
                        
        return fixes_applied
        
    def _perform_learning_analysis(self, state: EnhancedIterationState, final_result: Dict[str, Any]):
        """Perform learning analysis and record outcomes."""
        
        try:
            # Record outcomes for each advanced fix attempted
            for outcome in state.learning_outcomes:
                error_type = final_result.get("error_step", "unknown")
                success = outcome["outcome"] == "success"
                
                # Create context for learning
                context = {
                    "input_file_size": os.path.getsize(state.input_file) if os.path.exists(state.input_file) else 0,
                    "total_iterations": len(state.iteration_history),
                    "final_success": final_result.get("status") == "success"
                }
                
                # Record for learning
                self.advanced_fixes.record_workflow_outcome(
                    error_type, outcome["fix_name"], success, context
                )
                
            logging.info("Learning analysis completed and recorded")
            
        except Exception as e:
            logging.error(f"Learning analysis failed: {e}")
            
    def _generate_learning_insights(self, state: EnhancedIterationState) -> Dict[str, Any]:
        """Generate insights from the workflow execution."""
        
        try:
            insights = {
                "prediction_accuracy": state._calculate_prediction_accuracy(),
                "fix_effectiveness": {},
                "recommendations": []
            }
            
            # Analyze fix effectiveness
            for outcome in state.learning_outcomes:
                fix_name = outcome["fix_name"]
                if fix_name not in insights["fix_effectiveness"]:
                    insights["fix_effectiveness"][fix_name] = {
                        "attempts": 0,
                        "successes": 0
                    }
                insights["fix_effectiveness"][fix_name]["attempts"] += 1
                if outcome["outcome"] == "success":
                    insights["fix_effectiveness"][fix_name]["successes"] += 1
                    
            # Generate recommendations
            if state.risk_assessment.get("overall_risk") == "high":
                insights["recommendations"].append("Consider data preprocessing to address quality issues")
                
            if len(state.proactive_predictions) > 5:
                insights["recommendations"].append("Dataset shows multiple quality issues - manual review recommended")
                
            prediction_accuracy = insights["prediction_accuracy"].get("accuracy", 0)
            if prediction_accuracy > 0.8:
                insights["recommendations"].append("Proactive analysis was highly accurate - trust future predictions")
            elif prediction_accuracy < 0.3:
                insights["recommendations"].append("Proactive analysis needs improvement - consider manual validation")
                
            return insights
            
        except Exception as e:
            logging.error(f"Learning insights generation failed: {e}")
            return {"error": str(e)}


def create_enhanced_coordinator(max_iterations: int = 3, auto_fix: bool = True, 
                              use_advanced_fixes: bool = True, 
                              learning_dir: str = None) -> EnhancedIterativeCoordinator:
    """Factory function to create EnhancedIterativeCoordinator."""
    return EnhancedIterativeCoordinator(
        max_iterations=max_iterations,
        auto_fix=auto_fix,
        use_advanced_fixes=use_advanced_fixes,
        learning_dir=learning_dir
    )