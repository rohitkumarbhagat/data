#!/usr/bin/env python3
"""Comprehensive Test Suite for Phase 5 Iterative Coordinator

This module provides thorough testing of the iterative workflow coordinator,
error analysis, fix strategies, and state management components.

Test Categories:
- Unit tests for individual components
- Integration tests for coordinator logic  
- State persistence and resumption tests
- Fix strategy effectiveness tests
- Error analysis accuracy tests
- End-to-end scenario tests
"""

import os
import sys
import json
import tempfile
import shutil
import unittest
from unittest.mock import patch, MagicMock, call
from pathlib import Path
import pandas as pd

# Add current directory for imports
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from iterative_coordinator import IterativeCoordinator, IterationState
from error_analyzer import ProcessorErrorAnalyzer
from fix_strategies import ComprehensiveFixStrategies, FixStrategyResult
from workflow_state import WorkflowState, IterationRecord


class TestErrorAnalyzer(unittest.TestCase):
    """Test error analysis functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.analyzer = ProcessorErrorAnalyzer()
        
    def test_missing_column_detection(self):
        """Test detection of missing column errors."""
        workflow_result = {
            "status": "error",
            "error_step": "processor_execution",
            "steps": {
                "processor_execution": {
                    "stderr": "KeyError: 'population_count' not found in columns",
                    "exit_code": 1
                }
            }
        }
        
        analysis = self.analyzer.analyze_workflow_failure(workflow_result)
        
        self.assertEqual(analysis["status"], "analyzed")
        self.assertIsNotNone(analysis["primary_error"])
        self.assertEqual(analysis["primary_error"]["category"], "missing_column")
        self.assertGreater(analysis["confidence_score"], 0.8)
        self.assertIn("fix_missing_columns", analysis["suggested_fixes"])
        
    def test_date_format_error_detection(self):
        """Test detection of date format errors."""
        workflow_result = {
            "status": "error",
            "error_step": "processor_execution", 
            "steps": {
                "processor_execution": {
                    "stderr": "ValueError: time data '2023-01-01' does not match format '%m/%d/%Y'",
                    "exit_code": 1
                }
            }
        }
        
        analysis = self.analyzer.analyze_workflow_failure(workflow_result)
        
        self.assertEqual(analysis["primary_error"]["category"], "date_format_error")
        self.assertIn("fix_date_formats", analysis["suggested_fixes"])
        self.assertIn("extracted_details", analysis["primary_error"])
        
    def test_duplicate_observations_detection(self):
        """Test detection of duplicate observation errors."""
        workflow_result = {
            "status": "error",
            "error_step": "processor_execution",
            "steps": {
                "processor_execution": {
                    "stderr": "Duplicate observations found for observation key: USA:2023:Count",
                    "exit_code": 1
                }
            }
        }
        
        analysis = self.analyzer.analyze_workflow_failure(workflow_result)
        
        self.assertEqual(analysis["primary_error"]["category"], "duplicate_observations")
        self.assertIn("add_aggregation_rules", analysis["suggested_fixes"])
        
    def test_validation_error_analysis(self):
        """Test analysis of validation step errors."""
        workflow_result = {
            "status": "error",
            "error_step": "pvmap_validation",
            "steps": {
                "pvmap_validation": {
                    "issues": ["Missing required property: populationType", "Empty value for measuredProperty"]
                }
            }
        }
        
        analysis = self.analyzer.analyze_workflow_failure(workflow_result)
        
        self.assertEqual(analysis["error_source"], "pvmap_validation")
        self.assertGreater(len(analysis["fixable_errors"]), 0)
        
    def test_no_error_analysis(self):
        """Test analysis when no error is present."""
        workflow_result = {"status": "success"}
        
        analysis = self.analyzer.analyze_workflow_failure(workflow_result)
        
        self.assertEqual(analysis["status"], "no_error")
        self.assertIsNone(analysis["analysis"])


class TestFixStrategies(unittest.TestCase):
    """Test fix strategy implementations."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.fix_strategies = ComprehensiveFixStrategies()
        
        # Create sample files for testing
        self.pvmap_path = os.path.join(self.temp_dir, "pvmap.csv")
        self.metadata_path = os.path.join(self.temp_dir, "metadata.csv")
        
        # Sample PVMap
        pvmap_data = {
            "input": ["population_count", "invalid_column_123", "year"],
            "property": ["measuredProperty", "populationType", "observationDate"],
            "value": ["Count", "Person", "year"]
        }
        pd.DataFrame(pvmap_data).to_csv(self.pvmap_path, index=False)
        
        # Sample metadata
        metadata_data = {
            "Property": ["date_format", "header_rows"],
            "Value": ["%Y", "1"]
        }
        pd.DataFrame(metadata_data).to_csv(self.metadata_path, index=False)
        
    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir)
        
    def test_fix_missing_columns(self):
        """Test fixing missing column references."""
        error_details = {
            "extracted_details": ["invalid_column_123"],
            "details": {"missing_columns": ["invalid_column_123"]}
        }
        
        result = self.fix_strategies.apply_fix(
            "fix_missing_columns", self.temp_dir, error_details
        )
        
        self.assertTrue(result.success)
        self.assertIn("Removed", result.message)
        
        # Verify the invalid column was removed
        updated_df = pd.read_csv(self.pvmap_path)
        self.assertNotIn("invalid_column_123", updated_df["input"].values)
        self.assertIn("population_count", updated_df["input"].values)
        
    def test_fix_date_formats(self):
        """Test fixing date format configurations."""
        error_details = {
            "details": {"expected_format": "%Y-%m-%d"}
        }
        
        result = self.fix_strategies.apply_fix(
            "fix_date_formats", self.temp_dir, error_details
        )
        
        self.assertTrue(result.success)
        
        # Verify date format was updated
        updated_df = pd.read_csv(self.metadata_path)
        date_format_row = updated_df[updated_df["Property"] == "date_format"]
        self.assertEqual(date_format_row["Value"].iloc[0], "%Y-%m-%d")
        
    def test_add_aggregation_rules(self):
        """Test adding aggregation rules."""
        error_details = {"details": {"duplication_info": "Multiple values for same key"}}
        
        result = self.fix_strategies.apply_fix(
            "add_aggregation_rules", self.temp_dir, error_details
        )
        
        self.assertTrue(result.success)
        
        # Verify aggregation rules were added
        updated_df = pd.read_csv(self.metadata_path)
        self.assertIn("aggregation_method", updated_df["Property"].values)
        
    def test_add_constraint_properties(self):
        """Test adding constraint properties."""
        error_details = {"details": {"constraint_needed": "gender"}}
        
        result = self.fix_strategies.apply_fix(
            "add_constraint_properties", self.temp_dir, error_details
        )
        
        self.assertTrue(result.success)
        
        # Verify constraint properties were added
        updated_df = pd.read_csv(self.pvmap_path)
        constraint_entries = updated_df[updated_df["input"].str.contains("#constraint")]
        self.assertGreater(len(constraint_entries), 0)
        
    def test_unknown_fix_strategy(self):
        """Test handling of unknown fix strategies."""
        result = self.fix_strategies.apply_fix(
            "unknown_fix", self.temp_dir, {}
        )
        
        self.assertFalse(result.success)
        self.assertIn("Unknown fix strategy", result.message)


class TestWorkflowState(unittest.TestCase):
    """Test workflow state management."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.input_file = "test_input.csv"
        self.output_dir = os.path.join(self.temp_dir, "output")
        self.working_dir = os.path.join(self.temp_dir, "working")
        
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.working_dir, exist_ok=True)
        
        self.state = WorkflowState(
            self.input_file, self.output_dir, self.working_dir
        )
        
    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir)
        
    def test_iteration_tracking(self):
        """Test iteration record creation and tracking."""
        iteration = self.state.start_iteration(1)
        
        self.assertEqual(iteration.attempt, 1)
        self.assertEqual(len(self.state.iterations), 1)
        
        # Complete the iteration
        workflow_result = {
            "status": "error",
            "error_step": "processor_execution",
            "steps": {"analysis": {"status": "success"}}
        }
        fixes_applied = [("fix_missing_columns", True), ("fix_date_formats", False)]
        
        self.state.complete_iteration(iteration, workflow_result, fixes_applied, 10.5)
        
        self.assertEqual(iteration.status, "error")
        self.assertEqual(iteration.duration_seconds, 10.5)
        self.assertIn("fix_missing_columns", iteration.fixes_successful)
        self.assertIn("fix_date_formats", iteration.fixes_failed)
        
    def test_state_persistence(self):
        """Test saving and loading workflow state."""
        # Create some state
        iteration = self.state.start_iteration(1)
        workflow_result = {"status": "success"}
        self.state.complete_iteration(iteration, workflow_result, [], 5.0)
        self.state.complete_workflow("success")
        
        # Create new state instance and verify it loads the saved state
        new_state = WorkflowState(
            self.input_file, self.output_dir, self.working_dir
        )
        
        self.assertEqual(len(new_state.iterations), 1)
        self.assertEqual(new_state.final_status, "success")
        
    def test_resumption_capability(self):
        """Test workflow resumption logic."""
        # Create incomplete workflow
        iteration = self.state.start_iteration(1)
        workflow_result = {"status": "error", "error_step": "processor_execution"}
        self.state.complete_iteration(iteration, workflow_result, [], 3.0)
        
        self.assertTrue(self.state.can_resume())
        
        resume_info = self.state.get_resume_info()
        self.assertTrue(resume_info["can_resume"])
        self.assertEqual(resume_info["current_iteration"], 1)
        
        # Complete workflow
        self.state.complete_workflow("error")
        self.assertFalse(self.state.can_resume())
        
    def test_iteration_summary(self):
        """Test comprehensive iteration summary generation."""
        # Add multiple iterations with different outcomes
        for i in range(1, 4):
            iteration = self.state.start_iteration(i)
            status = "success" if i == 3 else "error"
            workflow_result = {
                "status": status,
                "error_step": "processor_execution" if status == "error" else None,
                "steps": {f"step_{j}": {"status": "success"} for j in range(i)}
            }
            
            fixes = [("fix_missing_columns", True)] if i > 1 else []
            self.state.complete_iteration(iteration, workflow_result, fixes, float(i))
            
        summary = self.state.get_iteration_summary()
        
        self.assertEqual(summary["total_iterations"], 3)
        self.assertEqual(summary["final_status"], None)  # Not completed yet
        self.assertEqual(len(summary["success_progression"]), 3)
        self.assertIn("fix_effectiveness", summary)


class TestIterativeCoordinator(unittest.TestCase):
    """Test iterative coordinator functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.input_file = "test_input.csv"
        self.output_dir = os.path.join(self.temp_dir, "output") 
        self.working_dir = os.path.join(self.temp_dir, "working")
        
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.working_dir, exist_ok=True)
        
        self.coordinator = IterativeCoordinator(max_iterations=3, auto_fix=True)
        
    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir)
        
    @patch('iterative_coordinator.execute_workflow')
    def test_successful_first_iteration(self, mock_execute):
        """Test successful workflow on first attempt."""
        mock_execute.return_value = {"status": "success", "steps": {}}
        
        result = self.coordinator.process_with_retry(
            self.input_file, self.output_dir, self.working_dir
        )
        
        self.assertEqual(result["status"], "success")
        self.assertEqual(mock_execute.call_count, 1)
        self.assertIn("iteration_summary", result)
        
    @patch('iterative_coordinator.execute_workflow')
    def test_retry_with_fix_success(self, mock_execute):
        """Test retry logic with successful fix application."""
        # First call fails, second succeeds
        mock_execute.side_effect = [
            {
                "status": "error",
                "error_step": "processor_execution", 
                "steps": {"processor_execution": {"stderr": "KeyError: 'missing_col'", "exit_code": 1}}
            },
            {"status": "success", "steps": {}}
        ]
        
        # Mock the fix strategies
        with patch.object(self.coordinator.fix_strategies, 'fix_missing_columns') as mock_fix:
            mock_fix.return_value = FixStrategyResult(True, "Fixed missing column")
            
            result = self.coordinator.process_with_retry(
                self.input_file, self.output_dir, self.working_dir
            )
            
        self.assertEqual(result["status"], "success")
        self.assertEqual(mock_execute.call_count, 2)
        mock_fix.assert_called_once()
        
    @patch('iterative_coordinator.execute_workflow')
    def test_max_iterations_reached(self, mock_execute):
        """Test behavior when max iterations is reached."""
        # Always return error
        mock_execute.return_value = {
            "status": "error",
            "error_step": "processor_execution",
            "steps": {"processor_execution": {"stderr": "Unfixable error", "exit_code": 1}}
        }
        
        result = self.coordinator.process_with_retry(
            self.input_file, self.output_dir, self.working_dir
        )
        
        self.assertEqual(result["status"], "error")
        self.assertEqual(mock_execute.call_count, 3)  # max_iterations
        
    @patch('iterative_coordinator.execute_workflow')
    def test_auto_fix_disabled(self, mock_execute):
        """Test behavior when auto-fix is disabled."""
        coordinator = IterativeCoordinator(max_iterations=3, auto_fix=False)
        
        mock_execute.return_value = {
            "status": "error",
            "error_step": "processor_execution"
        }
        
        result = coordinator.process_with_retry(
            self.input_file, self.output_dir, self.working_dir
        )
        
        # Should only try once since no fixes can be applied
        self.assertEqual(result["status"], "error")
        self.assertEqual(mock_execute.call_count, 1)


class TestEndToEndScenarios(unittest.TestCase):
    """Test realistic end-to-end error recovery scenarios."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.input_file = os.path.join(self.temp_dir, "test_data.csv")
        self.output_dir = os.path.join(self.temp_dir, "output")
        self.working_dir = os.path.join(self.temp_dir, "working")
        
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.working_dir, exist_ok=True)
        
        # Create sample input data
        sample_data = {
            "year": [2020, 2021, 2022],
            "state": ["CA", "NY", "TX"],
            "population": [39500000, 19800000, 29000000]
        }
        pd.DataFrame(sample_data).to_csv(self.input_file, index=False)
        
    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir)
        
    def test_missing_column_recovery_scenario(self):
        """Test complete recovery from missing column errors."""
        # Create PVMap with invalid column reference
        pvmap_data = {
            "input": ["population", "invalid_column", "year"],
            "property": ["measuredProperty", "populationType", "observationDate"],
            "value": ["Count", "Person", "year"]
        }
        pvmap_path = os.path.join(self.working_dir, "pvmap.csv")
        pd.DataFrame(pvmap_data).to_csv(pvmap_path, index=False)
        
        fix_strategies = ComprehensiveFixStrategies()
        error_details = {"extracted_details": ["invalid_column"]}
        
        result = fix_strategies.apply_fix("fix_missing_columns", self.working_dir, error_details)
        
        self.assertTrue(result.success)
        
        # Verify fix was applied
        updated_df = pd.read_csv(pvmap_path)
        self.assertNotIn("invalid_column", updated_df["input"].values)
        self.assertIn("population", updated_df["input"].values)
        
    def test_date_format_recovery_scenario(self):
        """Test complete recovery from date format errors."""
        metadata_data = {
            "Property": ["date_format", "header_rows"],
            "Value": ["%Y", "1"]
        }
        metadata_path = os.path.join(self.working_dir, "metadata.csv") 
        pd.DataFrame(metadata_data).to_csv(metadata_path, index=False)
        
        fix_strategies = ComprehensiveFixStrategies()
        error_details = {"details": {"expected_format": "%Y-%m-%d"}}
        
        result = fix_strategies.apply_fix("fix_date_formats", self.working_dir, error_details)
        
        self.assertTrue(result.success)
        
        # Verify fix was applied
        updated_df = pd.read_csv(metadata_path)
        date_format_row = updated_df[updated_df["Property"] == "date_format"]
        self.assertEqual(date_format_row["Value"].iloc[0], "%Y-%m-%d")


def create_test_suite():
    """Create comprehensive test suite for Phase 5 components."""
    suite = unittest.TestSuite()
    
    # Add test classes
    test_classes = [
        TestErrorAnalyzer,
        TestFixStrategies, 
        TestWorkflowState,
        TestIterativeCoordinator,
        TestEndToEndScenarios
    ]
    
    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        suite.addTests(tests)
        
    return suite


def run_tests():
    """Run all Phase 5 tests."""
    print("=== Running Phase 5 Iterative Coordinator Test Suite ===")
    
    suite = create_test_suite()
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    total_tests = result.testsRun
    failures = len(result.failures)
    errors = len(result.errors)
    
    print(f"\n=== Test Results ===")
    print(f"Total tests: {total_tests}")
    print(f"Passed: {total_tests - failures - errors}")
    print(f"Failed: {failures}")
    print(f"Errors: {errors}")
    
    if failures > 0:
        print(f"\nFailures:")
        for test, traceback in result.failures:
            print(f"  - {test}: {traceback.split('AssertionError:')[-1].strip()}")
            
    if errors > 0:
        print(f"\nErrors:")
        for test, traceback in result.errors:
            print(f"  - {test}: {traceback.split('\\n')[-2].strip()}")
            
    success = failures == 0 and errors == 0
    print(f"\n{'✅ ALL TESTS PASSED' if success else '❌ SOME TESTS FAILED'}")
    
    return success


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)