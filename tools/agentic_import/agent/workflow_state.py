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

"""Comprehensive Workflow State Management for ADK PVMap Generation

This module provides sophisticated state tracking and persistence capabilities
for the iterative workflow coordinator. It tracks iteration history, fix
effectiveness, performance metrics, and enables workflow resumption.

Key Features:
- Persistent state storage with JSON serialization
- Fix effectiveness tracking and learning
- Performance analytics and metrics
- Workflow resumption capabilities
- Error pattern analysis over time
- Success rate optimization
"""

import os
import json
import logging
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from collections import defaultdict, Counter
import statistics


class WorkflowMetrics:
    """Tracks performance metrics for workflow executions."""
    
    def __init__(self):
        """Initialize metrics tracking."""
        self.execution_times: List[float] = []
        self.iteration_counts: List[int] = []
        self.success_rates: Dict[str, List[bool]] = defaultdict(list)  # By error type
        self.fix_effectiveness: Dict[str, Dict[str, List[bool]]] = defaultdict(lambda: defaultdict(list))
        self.error_frequencies: Counter = Counter()
        self.fix_frequencies: Counter = Counter()
        
    def record_execution(self, duration: float, iterations: int, success: bool, 
                        error_types: List[str], fixes_applied: List[str]):
        """Record metrics for a workflow execution.
        
        Args:
            duration: Total execution time in seconds
            iterations: Number of iterations required
            success: Whether the workflow ultimately succeeded
            error_types: Types of errors encountered
            fixes_applied: Fix strategies that were applied
        """
        self.execution_times.append(duration)
        self.iteration_counts.append(iterations)
        
        # Track success rates by error type
        for error_type in error_types:
            self.success_rates[error_type].append(success)
            self.error_frequencies[error_type] += 1
            
        # Track fix effectiveness
        for fix in fixes_applied:
            self.fix_frequencies[fix] += 1
            for error_type in error_types:
                self.fix_effectiveness[error_type][fix].append(success)
                
    def get_summary(self) -> Dict[str, Any]:
        """Generate metrics summary.
        
        Returns:
            Dictionary with comprehensive metrics summary
        """
        total_executions = len(self.execution_times)
        
        if total_executions == 0:
            return {"total_executions": 0}
            
        # Calculate basic statistics
        avg_duration = statistics.mean(self.execution_times)
        avg_iterations = statistics.mean(self.iteration_counts)
        overall_success_rate = sum(1 for i in self.iteration_counts if i > 0) / total_executions
        
        # Calculate success rates by error type
        error_success_rates = {}
        for error_type, results in self.success_rates.items():
            error_success_rates[error_type] = {
                "success_rate": sum(results) / len(results) if results else 0.0,
                "occurrences": len(results)
            }
            
        # Calculate fix effectiveness
        fix_effectiveness = {}
        for error_type, fixes in self.fix_effectiveness.items():
            fix_effectiveness[error_type] = {}
            for fix, results in fixes.items():
                fix_effectiveness[error_type][fix] = {
                    "success_rate": sum(results) / len(results) if results else 0.0,
                    "applications": len(results)
                }
                
        return {
            "total_executions": total_executions,
            "average_duration_seconds": round(avg_duration, 2),
            "average_iterations": round(avg_iterations, 1),
            "overall_success_rate": round(overall_success_rate, 3),
            "most_common_errors": dict(self.error_frequencies.most_common(5)),
            "most_used_fixes": dict(self.fix_frequencies.most_common(5)),
            "error_success_rates": error_success_rates,
            "fix_effectiveness": fix_effectiveness
        }


class IterationRecord:
    """Represents a single iteration in the workflow."""
    
    def __init__(self, attempt: int, timestamp: str = None):
        """Initialize iteration record.
        
        Args:
            attempt: Iteration attempt number
            timestamp: ISO timestamp (defaults to current time)
        """
        self.attempt = attempt
        self.timestamp = timestamp or datetime.now().isoformat()
        self.status: Optional[str] = None
        self.error_step: Optional[str] = None
        self.error_message: Optional[str] = None
        self.error_analysis: Optional[Dict[str, Any]] = None
        self.fixes_attempted: List[str] = []
        self.fixes_successful: List[str] = []
        self.fixes_failed: List[str] = []
        self.duration_seconds: Optional[float] = None
        self.steps_completed: int = 0
        self.files_modified: List[str] = []
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "attempt": self.attempt,
            "timestamp": self.timestamp,
            "status": self.status,
            "error_step": self.error_step,
            "error_message": self.error_message,
            "error_analysis": self.error_analysis,
            "fixes_attempted": self.fixes_attempted,
            "fixes_successful": self.fixes_successful,
            "fixes_failed": self.fixes_failed,
            "duration_seconds": self.duration_seconds,
            "steps_completed": self.steps_completed,
            "files_modified": self.files_modified
        }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'IterationRecord':
        """Create from dictionary."""
        record = cls(data["attempt"], data.get("timestamp"))
        record.status = data.get("status")
        record.error_step = data.get("error_step")
        record.error_message = data.get("error_message")
        record.error_analysis = data.get("error_analysis")
        record.fixes_attempted = data.get("fixes_attempted", [])
        record.fixes_successful = data.get("fixes_successful", [])
        record.fixes_failed = data.get("fixes_failed", [])
        record.duration_seconds = data.get("duration_seconds")
        record.steps_completed = data.get("steps_completed", 0)
        record.files_modified = data.get("files_modified", [])
        return record


class WorkflowState:
    """Comprehensive state tracking for iterative workflows."""
    
    def __init__(self, input_file: str, output_dir: str, working_dir: str,
                 state_dir: str = None):
        """Initialize workflow state.
        
        Args:
            input_file: Path to input CSV file
            output_dir: Output directory path
            working_dir: Working directory path  
            state_dir: Directory for state persistence (defaults to working_dir/.datacommons)
        """
        self.input_file = input_file
        self.output_dir = output_dir
        self.working_dir = working_dir
        self.state_dir = state_dir or os.path.join(working_dir, ".datacommons")
        
        # Ensure state directory exists
        Path(self.state_dir).mkdir(parents=True, exist_ok=True)
        
        # Generate unique workflow ID based on inputs
        self.workflow_id = self._generate_workflow_id()
        self.state_file = os.path.join(self.state_dir, f"workflow_state_{self.workflow_id}.json")
        
        # Initialize state
        self.start_time = datetime.now()
        self.end_time: Optional[datetime] = None
        self.iterations: List[IterationRecord] = []
        self.max_iterations: int = 3
        self.current_iteration: int = 0
        self.final_status: Optional[str] = None
        self.error_patterns: Counter = Counter()
        self.fix_patterns: Counter = Counter()
        self.configuration_snapshots: Dict[int, Dict[str, str]] = {}  # iteration -> file hashes
        
        # Try to load existing state
        self._load_state()
        
    def _generate_workflow_id(self) -> str:
        """Generate unique workflow ID based on inputs.
        
        Returns:
            Unique workflow identifier
        """
        identifier_string = f"{self.input_file}:{self.output_dir}:{self.working_dir}"
        return hashlib.md5(identifier_string.encode()).hexdigest()[:12]
        
    def _load_state(self):
        """Load existing state from disk if available."""
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r') as f:
                    data = json.load(f)
                    
                # Restore state
                self.start_time = datetime.fromisoformat(data.get("start_time", self.start_time.isoformat()))
                if data.get("end_time"):
                    self.end_time = datetime.fromisoformat(data["end_time"])
                self.max_iterations = data.get("max_iterations", 3)
                self.current_iteration = data.get("current_iteration", 0)
                self.final_status = data.get("final_status")
                self.error_patterns = Counter(data.get("error_patterns", {}))
                self.fix_patterns = Counter(data.get("fix_patterns", {}))
                self.configuration_snapshots = data.get("configuration_snapshots", {})
                
                # Restore iterations
                self.iterations = [
                    IterationRecord.from_dict(iter_data) 
                    for iter_data in data.get("iterations", [])
                ]
                
                logging.info(f"Loaded existing workflow state with {len(self.iterations)} iterations")
                
        except Exception as e:
            logging.warning(f"Failed to load workflow state: {str(e)}")
            
    def _save_state(self):
        """Save current state to disk."""
        try:
            state_data = {
                "workflow_id": self.workflow_id,
                "input_file": self.input_file,
                "output_dir": self.output_dir,
                "working_dir": self.working_dir,
                "start_time": self.start_time.isoformat(),
                "end_time": self.end_time.isoformat() if self.end_time else None,
                "max_iterations": self.max_iterations,
                "current_iteration": self.current_iteration,
                "final_status": self.final_status,
                "error_patterns": dict(self.error_patterns),
                "fix_patterns": dict(self.fix_patterns),
                "configuration_snapshots": self.configuration_snapshots,
                "iterations": [iter_record.to_dict() for iter_record in self.iterations]
            }
            
            with open(self.state_file, 'w') as f:
                json.dump(state_data, f, indent=2)
                
        except Exception as e:
            logging.error(f"Failed to save workflow state: {str(e)}")
            
    def start_iteration(self, attempt: int) -> IterationRecord:
        """Start a new iteration.
        
        Args:
            attempt: Iteration attempt number
            
        Returns:
            New iteration record
        """
        iteration = IterationRecord(attempt)
        self.iterations.append(iteration)
        self.current_iteration = attempt
        
        # Capture configuration snapshot
        self._capture_configuration_snapshot(attempt)
        
        self._save_state()
        return iteration
        
    def complete_iteration(self, iteration: IterationRecord, workflow_result: Dict[str, Any],
                          fixes_applied: List[Tuple[str, bool]], duration: float):
        """Complete an iteration with results.
        
        Args:
            iteration: Iteration record to complete
            workflow_result: Results from workflow execution
            fixes_applied: List of (fix_name, success) tuples
            duration: Iteration duration in seconds
        """
        # Update iteration record
        iteration.status = workflow_result.get("status")
        iteration.error_step = workflow_result.get("error_step")
        iteration.error_message = workflow_result.get("error_message")
        iteration.duration_seconds = duration
        iteration.steps_completed = len([
            k for k, v in workflow_result.get("steps", {}).items() 
            if v.get("status") == "success"
        ])
        
        # Record fixes
        for fix_name, success in fixes_applied:
            iteration.fixes_attempted.append(fix_name)
            if success:
                iteration.fixes_successful.append(fix_name)
                self.fix_patterns[f"{fix_name}:success"] += 1
            else:
                iteration.fixes_failed.append(fix_name)
                self.fix_patterns[f"{fix_name}:failure"] += 1
                
        # Track error patterns
        if iteration.error_step:
            error_key = f"{iteration.error_step}:{iteration.status}"
            self.error_patterns[error_key] += 1
            
        self._save_state()
        
    def complete_workflow(self, final_status: str):
        """Mark workflow as completed.
        
        Args:
            final_status: Final workflow status ('success' or 'error')
        """
        self.end_time = datetime.now()
        self.final_status = final_status
        self._save_state()
        
    def _capture_configuration_snapshot(self, iteration: int):
        """Capture configuration file hashes for this iteration.
        
        Args:
            iteration: Iteration number
        """
        snapshot = {}
        
        config_files = ["pvmap.csv", "metadata.csv"]
        for filename in config_files:
            file_path = os.path.join(self.working_dir, filename)
            if os.path.exists(file_path):
                with open(file_path, 'rb') as f:
                    file_hash = hashlib.md5(f.read()).hexdigest()
                snapshot[filename] = file_hash
                
        self.configuration_snapshots[str(iteration)] = snapshot
        
    def can_resume(self) -> bool:
        """Check if workflow can be resumed.
        
        Returns:
            True if workflow can be resumed from previous state
        """
        return (
            len(self.iterations) > 0 and 
            self.final_status is None and
            self.current_iteration < self.max_iterations
        )
        
    def get_resume_info(self) -> Dict[str, Any]:
        """Get information for resuming workflow.
        
        Returns:
            Dictionary with resume information
        """
        if not self.can_resume():
            return {"can_resume": False}
            
        last_iteration = self.iterations[-1]
        return {
            "can_resume": True,
            "workflow_id": self.workflow_id,
            "current_iteration": self.current_iteration,
            "max_iterations": self.max_iterations,
            "last_status": last_iteration.status,
            "last_error_step": last_iteration.error_step,
            "fixes_tried": list(set(
                fix for iteration in self.iterations 
                for fix in iteration.fixes_attempted
            )),
            "elapsed_time": (datetime.now() - self.start_time).total_seconds()
        }
        
    def get_iteration_summary(self) -> Dict[str, Any]:
        """Get comprehensive iteration summary.
        
        Returns:
            Dictionary with detailed iteration summary
        """
        if not self.iterations:
            return {"total_iterations": 0}
            
        total_time = (self.end_time or datetime.now()) - self.start_time
        
        # Calculate success progression
        success_progression = []
        for iteration in self.iterations:
            success_progression.append({
                "attempt": iteration.attempt,
                "status": iteration.status,
                "steps_completed": iteration.steps_completed,
                "fixes_applied": len(iteration.fixes_successful),
                "duration": iteration.duration_seconds
            })
            
        # Analyze error patterns
        error_evolution = []
        for iteration in self.iterations:
            if iteration.error_step:
                error_evolution.append({
                    "attempt": iteration.attempt,
                    "error_step": iteration.error_step,
                    "error_category": iteration.error_analysis.get("primary_error", {}).get("category") if iteration.error_analysis else "unknown"
                })
                
        # Fix effectiveness analysis
        fix_effectiveness = {}
        for iteration in self.iterations:
            for fix in iteration.fixes_successful:
                next_iteration = None
                next_idx = self.iterations.index(iteration) + 1
                if next_idx < len(self.iterations):
                    next_iteration = self.iterations[next_idx]
                    
                if fix not in fix_effectiveness:
                    fix_effectiveness[fix] = {"applications": 0, "helped": 0}
                    
                fix_effectiveness[fix]["applications"] += 1
                
                # Check if this fix helped (next iteration progressed further)
                if (next_iteration and 
                    next_iteration.steps_completed > iteration.steps_completed):
                    fix_effectiveness[fix]["helped"] += 1
                    
        return {
            "workflow_id": self.workflow_id,
            "total_iterations": len(self.iterations),
            "final_status": self.final_status,
            "total_time_seconds": total_time.total_seconds(),
            "average_iteration_time": statistics.mean([
                i.duration_seconds for i in self.iterations 
                if i.duration_seconds is not None
            ]) if any(i.duration_seconds for i in self.iterations) else 0,
            "success_progression": success_progression,
            "error_evolution": error_evolution,
            "fix_effectiveness": {
                fix: {
                    "success_rate": data["helped"] / data["applications"] if data["applications"] > 0 else 0,
                    "applications": data["applications"]
                }
                for fix, data in fix_effectiveness.items()
            },
            "most_common_errors": dict(self.error_patterns.most_common(3)),
            "most_effective_fixes": dict(self.fix_patterns.most_common(3)),
            "configuration_changes": len(self.configuration_snapshots)
        }
        
    def cleanup_old_states(self, days: int = 7):
        """Clean up old state files.
        
        Args:
            days: Number of days to keep state files
        """
        try:
            cutoff_time = datetime.now() - timedelta(days=days)
            
            for file_path in Path(self.state_dir).glob("workflow_state_*.json"):
                if file_path.stat().st_mtime < cutoff_time.timestamp():
                    file_path.unlink()
                    logging.info(f"Cleaned up old state file: {file_path}")
                    
        except Exception as e:
            logging.warning(f"Failed to cleanup old state files: {str(e)}")