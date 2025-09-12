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

"""Advanced Error Recovery Strategies for ADK PVMap Generation

This module implements sophisticated error recovery and prediction strategies
that learn from patterns and use advanced techniques to improve success rates.

Key Features:
- Semantic column name matching using fuzzy logic and NLP
- Predictive error analysis to prevent issues before they occur  
- Adaptive fix strategies that learn from success patterns
- Advanced constraint property inference using data analysis
- Data quality assessment and proactive fixes
- Historical pattern learning and optimization

Advanced Strategies:
1. SemanticColumnMatcher - NLP-based column name mapping
2. PredictiveErrorAnalyzer - Predict errors before they happen
3. AdaptiveFixSelector - Learn optimal fix strategies
4. SmartPropertyInferrer - Advanced property inference
5. DataQualityAssessor - Proactive data quality analysis
6. HistoricalPatternLearner - Learn from past successes/failures

Usage:
    advanced_fixes = AdvancedFixStrategies()
    predictions = advanced_fixes.predict_potential_errors(input_file, pvmap_data)
    fixes = advanced_fixes.get_adaptive_fixes(error_history)
    quality_issues = advanced_fixes.assess_data_quality(input_file)
"""

import os
import re
import json
import logging
import pandas as pd
import numpy as np
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Set
from collections import defaultdict, Counter
from dataclasses import dataclass, field
import difflib

# For fuzzy string matching
try:
    from fuzzywuzzy import fuzz, process
except ImportError:
    logging.warning("fuzzywuzzy not available - using basic string matching")
    fuzz = None
    process = None


@dataclass
class ErrorPrediction:
    """Represents a predicted error with confidence and prevention strategy."""
    error_type: str
    confidence: float
    description: str
    prevention_strategy: str
    affected_columns: List[str] = field(default_factory=list)
    suggested_fixes: List[str] = field(default_factory=list)
    risk_level: str = "medium"  # low, medium, high, critical


@dataclass  
class QualityIssue:
    """Represents a data quality issue with severity and remedy."""
    issue_type: str
    severity: str  # low, medium, high, critical
    description: str
    affected_data: Dict[str, Any] = field(default_factory=dict)
    recommended_action: str = ""
    auto_fixable: bool = False


@dataclass
class ColumnMapping:
    """Represents a semantic column mapping with confidence."""
    source_column: str
    target_property: str
    confidence: float
    mapping_method: str  # exact, fuzzy, semantic, inferred
    alternatives: List[Tuple[str, float]] = field(default_factory=list)


class SemanticColumnMatcher:
    """Advanced column name matching using NLP and fuzzy logic."""
    
    def __init__(self):
        """Initialize with Data Commons property vocabulary."""
        self.dc_properties = self._load_dc_property_vocabulary()
        self.common_patterns = self._build_common_patterns()
        self.semantic_mappings = self._build_semantic_mappings()
        
    def _load_dc_property_vocabulary(self) -> Dict[str, List[str]]:
        """Load Data Commons property vocabulary and synonyms."""
        # Core Data Commons properties with common variants
        return {
            "populationType": [
                "population", "pop", "people", "persons", "individuals", 
                "demographic", "cohort", "group", "category"
            ],
            "measuredProperty": [
                "measure", "measurement", "metric", "value", "amount",
                "count", "total", "sum", "average", "rate", "percentage"
            ],
            "observationAbout": [
                "location", "place", "geo", "geography", "region", "area",
                "country", "state", "city", "county", "district", "locality"
            ],
            "observationDate": [
                "date", "time", "year", "month", "period", "timestamp", 
                "when", "temporal", "time_period"
            ],
            "constraintProperties": [
                "constraint", "filter", "condition", "criteria", "where",
                "qualifier", "attribute", "dimension"
            ],
            "gender": [
                "sex", "gender", "male", "female", "man", "woman"
            ],
            "age": [
                "age", "years", "old", "young", "adult", "child", "senior"
            ],
            "race": [
                "race", "ethnicity", "ethnic", "ancestry", "origin"
            ],
            "income": [
                "income", "salary", "wage", "earnings", "pay", "money", "financial"
            ],
            "education": [
                "education", "school", "degree", "diploma", "academic",
                "learning", "qualification", "attainment"
            ]
        }
        
    def _build_common_patterns(self) -> List[Tuple[str, str, float]]:
        """Build common column name patterns with DC property mappings."""
        return [
            # (pattern, dc_property, confidence)
            (r".*pop(ulation)?.*count.*", "measuredProperty", 0.9),
            (r".*total.*pop(ulation)?.*", "measuredProperty", 0.9),
            (r".*(male|female).*count.*", "measuredProperty", 0.8),
            (r".*year.*", "observationDate", 0.8),
            (r".*date.*", "observationDate", 0.9),
            (r".*state.*", "observationAbout", 0.7),
            (r".*country.*", "observationAbout", 0.8),
            (r".*county.*", "observationAbout", 0.8),
            (r".*city.*", "observationAbout", 0.7),
            (r".*region.*", "observationAbout", 0.7),
            (r".*geo.*", "observationAbout", 0.8),
            (r".*location.*", "observationAbout", 0.8),
        ]
        
    def _build_semantic_mappings(self) -> Dict[str, str]:
        """Build semantic word mappings for better understanding."""
        return {
            # Population types
            "inhabitants": "populationType",
            "residents": "populationType", 
            "citizens": "populationType",
            "households": "populationType",
            "families": "populationType",
            
            # Measurements  
            "quantity": "measuredProperty",
            "number": "measuredProperty",
            "figure": "measuredProperty",
            "statistic": "measuredProperty",
            "data": "measuredProperty",
            
            # Geographic
            "territory": "observationAbout",
            "jurisdiction": "observationAbout",
            "administrative": "observationAbout",
            "postal": "observationAbout",
        }
        
    def find_best_matches(self, column_names: List[str], 
                         threshold: float = 0.6) -> List[ColumnMapping]:
        """Find best Data Commons property matches for column names.
        
        Args:
            column_names: List of column names to match
            threshold: Minimum confidence threshold for matches
            
        Returns:
            List of ColumnMapping objects with confidence scores
        """
        mappings = []
        
        for column in column_names:
            column_lower = column.lower().strip()
            best_matches = []
            
            # 1. Exact matches
            for dc_prop, synonyms in self.dc_properties.items():
                if column_lower in [s.lower() for s in synonyms]:
                    best_matches.append((dc_prop, 1.0, "exact"))
                    
            # 2. Pattern matches  
            if not best_matches:
                for pattern, dc_prop, confidence in self.common_patterns:
                    if re.match(pattern, column_lower):
                        best_matches.append((dc_prop, confidence, "pattern"))
                        
            # 3. Fuzzy matches (if fuzzywuzzy available)
            if not best_matches and fuzz:
                for dc_prop, synonyms in self.dc_properties.items():
                    for synonym in synonyms:
                        fuzzy_score = fuzz.ratio(column_lower, synonym.lower()) / 100.0
                        if fuzzy_score >= threshold:
                            best_matches.append((dc_prop, fuzzy_score, "fuzzy"))
                            
            # 4. Semantic word matches
            if not best_matches:
                words = re.findall(r'\w+', column_lower)
                for word in words:
                    if word in self.semantic_mappings:
                        dc_prop = self.semantic_mappings[word]
                        confidence = 0.7  # Moderate confidence for semantic matches
                        best_matches.append((dc_prop, confidence, "semantic"))
                        
            # Create mapping for best match
            if best_matches:
                # Sort by confidence and take best
                best_matches.sort(key=lambda x: x[1], reverse=True)
                best_match = best_matches[0]
                
                mapping = ColumnMapping(
                    source_column=column,
                    target_property=best_match[0],
                    confidence=best_match[1],
                    mapping_method=best_match[2],
                    alternatives=[(m[0], m[1]) for m in best_matches[1:5]]  # Top 5 alternatives
                )
                mappings.append(mapping)
                
        return mappings


class PredictiveErrorAnalyzer:
    """Analyze data patterns to predict potential errors before they occur."""
    
    def __init__(self):
        """Initialize predictive analyzer."""
        self.error_patterns = self._load_error_patterns()
        self.data_quality_thresholds = self._define_quality_thresholds()
        
    def _load_error_patterns(self) -> Dict[str, Dict[str, Any]]:
        """Load patterns that typically lead to errors."""
        return {
            "high_null_percentage": {
                "threshold": 0.3,  # 30% nulls
                "error_type": "missing_data_error",
                "confidence": 0.8,
                "description": "High percentage of null values may cause processing errors"
            },
            "inconsistent_date_formats": {
                "indicators": [r"\d{4}-\d{2}-\d{2}", r"\d{2}/\d{2}/\d{4}", r"\d{2}-\d{2}-\d{4}"],
                "error_type": "date_format_error", 
                "confidence": 0.9,
                "description": "Mixed date formats will cause parsing errors"
            },
            "duplicate_observation_keys": {
                "threshold": 0.05,  # 5% duplicates
                "error_type": "duplicate_observations",
                "confidence": 0.85,
                "description": "Duplicate observation keys require aggregation"
            },
            "unusual_column_names": {
                "indicators": ["unnamed:", "column_", "index_", ".1", ".2"],
                "error_type": "missing_column",
                "confidence": 0.7,
                "description": "Auto-generated column names often cause mapping errors"
            },
            "numeric_in_text_columns": {
                "threshold": 0.8,  # 80% numeric in text column
                "error_type": "data_type_mismatch",
                "confidence": 0.6,
                "description": "Numeric data in text columns may indicate type issues"
            }
        }
        
    def _define_quality_thresholds(self) -> Dict[str, float]:
        """Define data quality thresholds for analysis."""
        return {
            "max_null_percentage": 0.25,
            "min_unique_values": 2,
            "max_duplicate_percentage": 0.1,
            "min_data_consistency": 0.8,
            "max_outlier_percentage": 0.05
        }
        
    def predict_errors(self, input_file: str, pvmap_data: Optional[pd.DataFrame] = None) -> List[ErrorPrediction]:
        """Predict potential errors by analyzing input data patterns.
        
        Args:
            input_file: Path to input CSV file
            pvmap_data: Optional existing PVMap data for context
            
        Returns:
            List of ErrorPrediction objects
        """
        predictions = []
        
        try:
            # Read sample of input data
            df = pd.read_csv(input_file, nrows=1000)  # Sample for analysis
            
            # Analyze each column
            for column in df.columns:
                column_predictions = self._analyze_column(df, column)
                predictions.extend(column_predictions)
                
            # Analyze overall data patterns
            overall_predictions = self._analyze_overall_patterns(df)
            predictions.extend(overall_predictions)
            
            # Analyze PVMap compatibility if available
            if pvmap_data is not None:
                compatibility_predictions = self._analyze_pvmap_compatibility(df, pvmap_data)
                predictions.extend(compatibility_predictions)
                
        except Exception as e:
            logging.error(f"Error in predictive analysis: {e}")
            
        return predictions
        
    def _analyze_column(self, df: pd.DataFrame, column: str) -> List[ErrorPrediction]:
        """Analyze individual column for potential issues."""
        predictions = []
        series = df[column]
        
        # Check null percentage
        null_pct = series.isnull().sum() / len(series)
        if null_pct > self.error_patterns["high_null_percentage"]["threshold"]:
            predictions.append(ErrorPrediction(
                error_type="missing_data_error",
                confidence=self.error_patterns["high_null_percentage"]["confidence"],
                description=f"Column '{column}' has {null_pct:.1%} null values",
                prevention_strategy="add_null_value_handling",
                affected_columns=[column],
                suggested_fixes=["remove_null_rows", "fill_null_values", "mark_as_optional"],
                risk_level="high" if null_pct > 0.5 else "medium"
            ))
            
        # Check for unusual column names
        for indicator in self.error_patterns["unusual_column_names"]["indicators"]:
            if indicator in column.lower():
                predictions.append(ErrorPrediction(
                    error_type="missing_column",
                    confidence=self.error_patterns["unusual_column_names"]["confidence"],
                    description=f"Column '{column}' has auto-generated name",
                    prevention_strategy="rename_column",
                    affected_columns=[column],
                    suggested_fixes=["manual_column_rename", "skip_auto_columns"],
                    risk_level="medium"
                ))
                break
                
        # Check date format consistency
        if any(date_keyword in column.lower() for date_keyword in ["date", "time", "year"]):
            date_formats = self._detect_date_formats(series.dropna())
            if len(date_formats) > 1:
                predictions.append(ErrorPrediction(
                    error_type="date_format_error",
                    confidence=self.error_patterns["inconsistent_date_formats"]["confidence"],
                    description=f"Column '{column}' has mixed date formats: {date_formats}",
                    prevention_strategy="standardize_date_format",
                    affected_columns=[column],
                    suggested_fixes=["convert_to_iso_date", "set_explicit_date_format"],
                    risk_level="high"
                ))
                
        return predictions
        
    def _analyze_overall_patterns(self, df: pd.DataFrame) -> List[ErrorPrediction]:
        """Analyze overall data patterns for potential issues."""
        predictions = []
        
        # Check for duplicate rows that could cause observation key conflicts
        duplicate_pct = df.duplicated().sum() / len(df)
        if duplicate_pct > self.error_patterns["duplicate_observation_keys"]["threshold"]:
            predictions.append(ErrorPrediction(
                error_type="duplicate_observations",
                confidence=self.error_patterns["duplicate_observation_keys"]["confidence"],
                description=f"Data has {duplicate_pct:.1%} duplicate rows",
                prevention_strategy="add_aggregation_rules",
                affected_columns=[],
                suggested_fixes=["remove_duplicates", "add_aggregation_config", "add_constraint_properties"],
                risk_level="high"
            ))
            
        # Check data shape and consistency
        if len(df.columns) < 3:
            predictions.append(ErrorPrediction(
                error_type="insufficient_data_structure",
                confidence=0.8,
                description=f"Dataset has only {len(df.columns)} columns - may lack required structure",
                prevention_strategy="validate_data_structure",
                affected_columns=[],
                suggested_fixes=["add_required_columns", "restructure_data"],
                risk_level="medium"
            ))
            
        return predictions
        
    def _analyze_pvmap_compatibility(self, df: pd.DataFrame, pvmap_data: pd.DataFrame) -> List[ErrorPrediction]:
        """Analyze compatibility between data and existing PVMap."""
        predictions = []
        
        try:
            # Check if PVMap references columns that don't exist
            referenced_columns = set()
            for _, row in pvmap_data.iterrows():
                input_ref = str(row.get('input', ''))
                if not input_ref.startswith('#'):
                    # Extract column name
                    col_name = input_ref.split(':')[0].strip()
                    referenced_columns.add(col_name)
                    
            actual_columns = set(df.columns)
            missing_columns = referenced_columns - actual_columns
            
            if missing_columns:
                predictions.append(ErrorPrediction(
                    error_type="missing_column",
                    confidence=0.95,
                    description=f"PVMap references missing columns: {list(missing_columns)}",
                    prevention_strategy="fix_column_references",
                    affected_columns=list(missing_columns),
                    suggested_fixes=["remove_invalid_pvmap_entries", "rename_columns", "add_missing_columns"],
                    risk_level="critical"
                ))
                
        except Exception as e:
            logging.error(f"PVMap compatibility analysis failed: {e}")
            
        return predictions
        
    def _detect_date_formats(self, series: pd.Series) -> List[str]:
        """Detect different date formats in a series."""
        formats = set()
        sample = series.sample(min(100, len(series)))
        
        for value in sample:
            str_val = str(value).strip()
            if re.match(r'\d{4}-\d{2}-\d{2}', str_val):
                formats.add("YYYY-MM-DD")
            elif re.match(r'\d{2}/\d{2}/\d{4}', str_val):
                formats.add("MM/DD/YYYY") 
            elif re.match(r'\d{2}-\d{2}-\d{4}', str_val):
                formats.add("MM-DD-YYYY")
            elif re.match(r'\d{4}', str_val):
                formats.add("YYYY")
                
        return list(formats)


class AdaptiveFixSelector:
    """Learn optimal fix strategies from historical success patterns."""
    
    def __init__(self, history_file: str = None):
        """Initialize with optional history file."""
        self.history_file = history_file or ".datacommons/fix_history.json"
        self.success_patterns = self._load_success_patterns()
        self.fix_effectiveness = defaultdict(lambda: {"successes": 0, "attempts": 0})
        
    def _load_success_patterns(self) -> Dict[str, Dict[str, Any]]:
        """Load historical success patterns."""
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logging.warning(f"Could not load fix history: {e}")
            
        return {}
        
    def save_success_patterns(self):
        """Save success patterns to history file."""
        try:
            os.makedirs(os.path.dirname(self.history_file), exist_ok=True)
            with open(self.history_file, 'w') as f:
                json.dump(self.success_patterns, f, indent=2)
        except Exception as e:
            logging.error(f"Could not save fix history: {e}")
            
    def record_fix_attempt(self, error_type: str, fix_strategy: str, success: bool, 
                          context: Dict[str, Any] = None):
        """Record the outcome of a fix attempt for learning.
        
        Args:
            error_type: Type of error that was fixed
            fix_strategy: Strategy that was applied
            success: Whether the fix was successful
            context: Additional context about the fix
        """
        # Update fix effectiveness tracking
        self.fix_effectiveness[fix_strategy]["attempts"] += 1
        if success:
            self.fix_effectiveness[fix_strategy]["successes"] += 1
            
        # Update success patterns
        pattern_key = f"{error_type}:{fix_strategy}"
        if pattern_key not in self.success_patterns:
            self.success_patterns[pattern_key] = {
                "successes": 0,
                "attempts": 0,
                "contexts": []
            }
            
        self.success_patterns[pattern_key]["attempts"] += 1
        if success:
            self.success_patterns[pattern_key]["successes"] += 1
            
        # Store context for pattern analysis
        if context and success:
            self.success_patterns[pattern_key]["contexts"].append({
                "timestamp": datetime.now().isoformat(),
                "context": context
            })
            
        # Limit stored contexts to prevent unbounded growth
        if len(self.success_patterns[pattern_key]["contexts"]) > 50:
            self.success_patterns[pattern_key]["contexts"] = \
                self.success_patterns[pattern_key]["contexts"][-50:]
                
    def get_best_fixes(self, error_type: str, context: Dict[str, Any] = None) -> List[Tuple[str, float]]:
        """Get best fix strategies for an error type based on historical success.
        
        Args:
            error_type: Type of error to fix
            context: Current context for contextual matching
            
        Returns:
            List of (fix_strategy, confidence) tuples sorted by effectiveness
        """
        candidates = []
        
        # Find all fixes that have been tried for this error type
        for pattern_key, data in self.success_patterns.items():
            if pattern_key.startswith(f"{error_type}:"):
                fix_strategy = pattern_key.split(":", 1)[1]
                
                # Calculate success rate
                if data["attempts"] > 0:
                    success_rate = data["successes"] / data["attempts"]
                    
                    # Boost confidence based on number of attempts (more data = more confidence)
                    confidence = success_rate * min(1.0, data["attempts"] / 10.0)
                    
                    # Contextual matching bonus
                    if context and self._matches_context(data.get("contexts", []), context):
                        confidence *= 1.2  # 20% bonus for contextual match
                        
                    candidates.append((fix_strategy, confidence))
                    
        # Sort by confidence and return top candidates
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[:5]  # Top 5 candidates
        
    def _matches_context(self, stored_contexts: List[Dict[str, Any]], current_context: Dict[str, Any]) -> bool:
        """Check if current context matches stored successful contexts."""
        if not stored_contexts or not current_context:
            return False
            
        # Simple context matching - can be enhanced with more sophisticated algorithms
        for stored in stored_contexts[-10:]:  # Check recent contexts
            stored_ctx = stored.get("context", {})
            
            # Check for common patterns
            common_keys = set(stored_ctx.keys()) & set(current_context.keys())
            if not common_keys:
                continue
                
            matches = 0
            for key in common_keys:
                if stored_ctx[key] == current_context[key]:
                    matches += 1
                    
            if matches / len(common_keys) >= 0.5:  # 50% match threshold
                return True
                
        return False
        
    def get_fix_effectiveness_report(self) -> Dict[str, Dict[str, Any]]:
        """Generate report of fix strategy effectiveness."""
        report = {}
        
        for fix_strategy, stats in self.fix_effectiveness.items():
            if stats["attempts"] > 0:
                success_rate = stats["successes"] / stats["attempts"]
                report[fix_strategy] = {
                    "success_rate": success_rate,
                    "total_attempts": stats["attempts"],
                    "total_successes": stats["successes"],
                    "confidence_level": "high" if stats["attempts"] >= 10 else "medium" if stats["attempts"] >= 3 else "low"
                }
                
        return report


class AdvancedFixStrategies:
    """Main coordinator for advanced fix strategies."""
    
    def __init__(self, history_dir: str = None):
        """Initialize advanced fix strategies.
        
        Args:
            history_dir: Directory for storing learning history
        """
        self.history_dir = history_dir or ".datacommons"
        os.makedirs(self.history_dir, exist_ok=True)
        
        # Initialize components
        self.semantic_matcher = SemanticColumnMatcher()
        self.predictive_analyzer = PredictiveErrorAnalyzer()
        self.adaptive_selector = AdaptiveFixSelector(
            os.path.join(self.history_dir, "fix_history.json")
        )
        
        logging.info("Advanced fix strategies initialized")
        
    def get_proactive_recommendations(self, input_file: str, pvmap_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """Get proactive recommendations before processing starts.
        
        Args:
            input_file: Path to input CSV file
            pvmap_data: Optional existing PVMap data
            
        Returns:
            Dictionary with recommendations and predictions
        """
        try:
            # Predict potential errors
            predictions = self.predictive_analyzer.predict_errors(input_file, pvmap_data)
            
            # Get semantic column mappings
            df = pd.read_csv(input_file, nrows=1)
            column_mappings = self.semantic_matcher.find_best_matches(df.columns.tolist())
            
            # Compile recommendations
            recommendations = {
                "predictions": [pred.__dict__ for pred in predictions],
                "column_mappings": [mapping.__dict__ for mapping in column_mappings],
                "proactive_fixes": [],
                "risk_assessment": self._assess_overall_risk(predictions),
                "recommended_actions": []
            }
            
            # Generate proactive fix suggestions
            for pred in predictions:
                if pred.confidence > 0.7:
                    best_fixes = self.adaptive_selector.get_best_fixes(pred.error_type)
                    recommendations["proactive_fixes"].extend([
                        {
                            "error_type": pred.error_type,
                            "fix_strategy": fix,
                            "confidence": conf,
                            "description": pred.description
                        }
                        for fix, conf in best_fixes[:2]  # Top 2 fixes
                    ])
                    
            # Generate recommended actions
            recommendations["recommended_actions"] = self._generate_action_plan(predictions, column_mappings)
            
            return recommendations
            
        except Exception as e:
            logging.error(f"Proactive recommendations failed: {e}")
            return {"error": str(e)}
            
    def _assess_overall_risk(self, predictions: List[ErrorPrediction]) -> Dict[str, Any]:
        """Assess overall risk level based on predictions."""
        risk_counts = Counter(pred.risk_level for pred in predictions)
        total_predictions = len(predictions)
        
        if risk_counts["critical"] > 0:
            overall_risk = "critical"
        elif risk_counts["high"] > 0:
            overall_risk = "high"
        elif risk_counts["medium"] > total_predictions * 0.3:
            overall_risk = "medium"
        else:
            overall_risk = "low"
            
        return {
            "overall_risk": overall_risk,
            "risk_distribution": dict(risk_counts),
            "total_issues": total_predictions,
            "recommended_max_iterations": max(3, min(10, total_predictions))
        }
        
    def _generate_action_plan(self, predictions: List[ErrorPrediction], 
                            mappings: List[ColumnMapping]) -> List[str]:
        """Generate actionable recommendations."""
        actions = []
        
        # High-priority actions from critical predictions
        critical_preds = [p for p in predictions if p.risk_level == "critical"]
        for pred in critical_preds:
            actions.append(f"CRITICAL: {pred.description} - {pred.prevention_strategy}")
            
        # Column mapping suggestions
        low_confidence_mappings = [m for m in mappings if m.confidence < 0.7]
        if low_confidence_mappings:
            actions.append(f"Review {len(low_confidence_mappings)} uncertain column mappings")
            
        # Data quality recommendations
        high_risk_preds = [p for p in predictions if p.risk_level == "high"]
        if len(high_risk_preds) > 3:
            actions.append("Consider data preprocessing to address quality issues")
            
        # Iteration recommendations
        total_issues = len(predictions)
        if total_issues > 5:
            actions.append(f"Enable iterative mode with max_iterations >= {min(10, total_issues)}")
            
        return actions
        
    def record_workflow_outcome(self, error_type: str, fix_applied: str, 
                              success: bool, context: Dict[str, Any] = None):
        """Record workflow outcome for learning."""
        self.adaptive_selector.record_fix_attempt(error_type, fix_applied, success, context)
        self.adaptive_selector.save_success_patterns()
        
    def get_learning_summary(self) -> Dict[str, Any]:
        """Get summary of learning progress and fix effectiveness."""
        return {
            "fix_effectiveness": self.adaptive_selector.get_fix_effectiveness_report(),
            "total_patterns": len(self.adaptive_selector.success_patterns),
            "history_file": self.adaptive_selector.history_file
        }


def create_advanced_fixes_instance(config_dir: str = None) -> AdvancedFixStrategies:
    """Factory function to create AdvancedFixStrategies instance."""
    return AdvancedFixStrategies(config_dir)