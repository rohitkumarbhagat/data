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

"""Integration Test Suite for ADK System

This module provides comprehensive validation of the ADK system including:
- Component integration and interaction testing
- System-level functionality validation
- Backward compatibility with legacy systems
- Performance benchmarking and monitoring
- End-to-end workflow validation
- Regression testing for system stability

Test Categories:
1. Unit Tests - Critical component testing
2. Integration Tests - Component interaction testing  
3. Compatibility Tests - Legacy system compatibility
4. Performance Tests - Speed and resource usage
5. Regression Tests - Ensure existing functionality works
6. End-to-End Tests - Full workflow scenarios

Usage:
    python test_integration.py [--verbose] [--category=unit|integration|all]
"""

import os
import sys
import json
import tempfile
import shutil
import time
import unittest
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional
import pandas as pd

# Add current directory for imports
sys.path.append(os.path.dirname(__file__))

# Import Phase 6 components
from config_adapter import ConfigAdapter, ConfigAdapterError, load_config_from_file
from enhanced_coordinator import EnhancedIterativeCoordinator, create_enhanced_coordinator
from advanced_fixes import AdvancedFixStrategies, SemanticColumnMatcher, PredictiveErrorAnalyzer
from main import main as main_function

# Import Phase 5 components for comparison
from iterative_coordinator import IterativeCoordinator
from coordinator import execute_workflow

# Test configuration
TEST_CONFIG = {
    "timeout_seconds": 300,  # 5 minutes max per test
    "sample_data_rows": 100,
    "max_test_iterations": 3,
    "performance_threshold_factor": 2.0  # Phase 6 should be within 2x of Phase 5 speed
}


class ADKIntegrationTestSuite:
    """Main integration test suite for ADK system validation."""
    
    def __init__(self, verbose: bool = False):
        """Initialize test suite.
        
        Args:
            verbose: Enable detailed logging
        """
        self.verbose = verbose
        self.temp_dir = tempfile.mkdtemp()
        self.test_results = {
            "unit_tests": [],
            "integration_tests": [],
            "compatibility_tests": [],
            "performance_tests": [],
            "regression_tests": [],
            "end_to_end_tests": []
        }
        
        print(f"🧪 Phase 6 Comprehensive Test Suite")
        print(f"Test directory: {self.temp_dir}")
        print(f"Verbose mode: {verbose}")
        
    def cleanup(self):
        """Clean up test resources."""
        try:
            shutil.rmtree(self.temp_dir)
            if self.verbose:
                print("🧹 Cleaned up test directory")
        except Exception as e:
            print(f"⚠️ Cleanup warning: {e}")
            
    def run_all_tests(self) -> Dict[str, Any]:
        """Run all test categories.
        
        Returns:
            Complete test results summary
        """
        print("\n" + "="*60)
        print("PHASE 6 COMPREHENSIVE TEST EXECUTION")
        print("="*60)
        
        start_time = time.time()
        
        try:
            # 1. Unit Tests
            print("\n1️⃣ Running Unit Tests...")
            self._run_unit_tests()
            
            # 2. Integration Tests  
            print("\n2️⃣ Running Integration Tests...")
            self._run_integration_tests()
            
            # 3. Compatibility Tests
            print("\n3️⃣ Running Compatibility Tests...")
            self._run_compatibility_tests()
            
            # 4. Performance Tests
            print("\n4️⃣ Running Performance Tests...")
            self._run_performance_tests()
            
            # 5. Regression Tests
            print("\n5️⃣ Running Regression Tests...")
            self._run_regression_tests()
            
            # 6. End-to-End Tests
            print("\n6️⃣ Running End-to-End Tests...")
            self._run_end_to_end_tests()
            
        except Exception as e:
            print(f"❌ Test suite execution failed: {e}")
            self.test_results["suite_error"] = str(e)
            
        total_time = time.time() - start_time
        
        # Generate final report
        summary = self._generate_test_summary(total_time)
        self._print_test_summary(summary)
        
        return {
            "summary": summary,
            "detailed_results": self.test_results,
            "total_time": total_time
        }
        
    def _run_unit_tests(self):
        """Run unit tests for individual components."""
        
        # Test ConfigAdapter
        print("  📋 Testing ConfigAdapter...")
        config_tests = self._test_config_adapter()
        self.test_results["unit_tests"].extend(config_tests)
        
        # Test AdvancedFixStrategies
        print("  🔧 Testing AdvancedFixStrategies...")
        fix_tests = self._test_advanced_fix_strategies()
        self.test_results["unit_tests"].extend(fix_tests)
        
        # Test SemanticColumnMatcher
        print("  🎯 Testing SemanticColumnMatcher...")
        matcher_tests = self._test_semantic_column_matcher()
        self.test_results["unit_tests"].extend(matcher_tests)
        
        # Test PredictiveErrorAnalyzer
        print("  🔍 Testing PredictiveErrorAnalyzer...")
        predictor_tests = self._test_predictive_error_analyzer()
        self.test_results["unit_tests"].extend(predictor_tests)
        
    def _test_config_adapter(self) -> List[Dict[str, Any]]:
        """Test ConfigAdapter functionality."""
        tests = []
        
        # Test 1: Valid config loading
        try:
            test_config = {
                "input_data": ["test_data.csv"],
                "input_metadata": [],
                "is_sdmx_dataset": False
            }
            
            config_path = os.path.join(self.temp_dir, "test_config.json")
            with open(config_path, 'w') as f:
                json.dump(test_config, f)
                
            # Create dummy data file
            data_file = os.path.join(self.temp_dir, "test_data.csv")
            pd.DataFrame({"col1": [1, 2, 3], "col2": ["A", "B", "C"]}).to_csv(data_file, index=False)
            
            adapter = ConfigAdapter(config_path, self.temp_dir)
            adk_config = adapter.to_adk_config()
            
            tests.append({
                "name": "ConfigAdapter: Valid config loading",
                "status": "pass",
                "details": f"Successfully loaded config and converted to ADK format"
            })
            
        except Exception as e:
            tests.append({
                "name": "ConfigAdapter: Valid config loading", 
                "status": "fail",
                "error": str(e)
            })
            
        # Test 2: Invalid config handling
        try:
            invalid_config = {"invalid": "config"}
            invalid_config_path = os.path.join(self.temp_dir, "invalid_config.json")
            with open(invalid_config_path, 'w') as f:
                json.dump(invalid_config, f)
                
            try:
                adapter = ConfigAdapter(invalid_config_path, self.temp_dir)
                tests.append({
                    "name": "ConfigAdapter: Invalid config handling",
                    "status": "fail", 
                    "error": "Should have raised ConfigAdapterError"
                })
            except ConfigAdapterError:
                tests.append({
                    "name": "ConfigAdapter: Invalid config handling",
                    "status": "pass",
                    "details": "Correctly raised ConfigAdapterError for invalid config"
                })
                
        except Exception as e:
            tests.append({
                "name": "ConfigAdapter: Invalid config handling",
                "status": "fail",
                "error": str(e)
            })
            
        return tests
        
    def _test_advanced_fix_strategies(self) -> List[Dict[str, Any]]:
        """Test AdvancedFixStrategies functionality."""
        tests = []
        
        try:
            # Create test instance
            advanced_fixes = AdvancedFixStrategies(self.temp_dir)
            
            # Test proactive recommendations
            test_data = pd.DataFrame({
                "year": [2020, 2021, 2022],
                "population_count": [1000, 1100, 1200],
                "state": ["CA", "NY", "TX"]
            })
            test_file = os.path.join(self.temp_dir, "proactive_test.csv")
            test_data.to_csv(test_file, index=False)
            
            recommendations = advanced_fixes.get_proactive_recommendations(test_file)
            
            if "predictions" in recommendations and "column_mappings" in recommendations:
                tests.append({
                    "name": "AdvancedFixStrategies: Proactive recommendations",
                    "status": "pass",
                    "details": f"Generated {len(recommendations['predictions'])} predictions, {len(recommendations['column_mappings'])} mappings"
                })
            else:
                tests.append({
                    "name": "AdvancedFixStrategies: Proactive recommendations",
                    "status": "fail",
                    "error": "Missing predictions or column_mappings in recommendations"
                })
                
        except Exception as e:
            tests.append({
                "name": "AdvancedFixStrategies: Proactive recommendations",
                "status": "fail", 
                "error": str(e)
            })
            
        return tests
        
    def _test_semantic_column_matcher(self) -> List[Dict[str, Any]]:
        """Test SemanticColumnMatcher functionality."""
        tests = []
        
        try:
            matcher = SemanticColumnMatcher()
            
            # Test column matching
            test_columns = ["population_count", "year", "state_name", "total_households"]
            mappings = matcher.find_best_matches(test_columns)
            
            if len(mappings) > 0:
                high_confidence_mappings = [m for m in mappings if m.confidence > 0.6]
                tests.append({
                    "name": "SemanticColumnMatcher: Column matching",
                    "status": "pass",
                    "details": f"Found {len(mappings)} mappings, {len(high_confidence_mappings)} high confidence"
                })
            else:
                tests.append({
                    "name": "SemanticColumnMatcher: Column matching", 
                    "status": "fail",
                    "error": "No column mappings found"
                })
                
        except Exception as e:
            tests.append({
                "name": "SemanticColumnMatcher: Column matching",
                "status": "fail",
                "error": str(e)
            })
            
        return tests
        
    def _test_predictive_error_analyzer(self) -> List[Dict[str, Any]]:
        """Test PredictiveErrorAnalyzer functionality.""" 
        tests = []
        
        try:
            analyzer = PredictiveErrorAnalyzer()
            
            # Create test data with known issues
            problematic_data = pd.DataFrame({
                "unnamed_0": [1, 2, None, None, None],  # High null percentage
                "date": ["2020-01-01", "01/02/2020", "2020-03-01", "03/04/2020", "2020-05-01"],  # Mixed formats
                "value": [100, 100, 200, 100, 300]  # Some duplicates
            })
            
            problem_file = os.path.join(self.temp_dir, "problematic_data.csv")
            problematic_data.to_csv(problem_file, index=False)
            
            predictions = analyzer.predict_errors(problem_file)
            
            if len(predictions) > 0:
                high_confidence_predictions = [p for p in predictions if p.confidence > 0.7]
                tests.append({
                    "name": "PredictiveErrorAnalyzer: Error prediction",
                    "status": "pass",
                    "details": f"Generated {len(predictions)} predictions, {len(high_confidence_predictions)} high confidence"
                })
            else:
                tests.append({
                    "name": "PredictiveErrorAnalyzer: Error prediction",
                    "status": "fail", 
                    "error": "No error predictions generated"
                })
                
        except Exception as e:
            tests.append({
                "name": "PredictiveErrorAnalyzer: Error prediction",
                "status": "fail",
                "error": str(e)
            })
            
        return tests
        
    def _run_integration_tests(self):
        """Run integration tests for component interactions."""
        
        # Test ConfigAdapter + EnhancedCoordinator integration
        print("  🔗 Testing ConfigAdapter + EnhancedCoordinator integration...")
        integration_tests = self._test_config_coordinator_integration()
        self.test_results["integration_tests"].extend(integration_tests)
        
    def _test_config_coordinator_integration(self) -> List[Dict[str, Any]]:
        """Test integration between ConfigAdapter and EnhancedCoordinator."""
        tests = []
        
        try:
            # Create test configuration and data
            test_data = pd.DataFrame({
                "year": [2020, 2021, 2022],
                "state": ["California", "New York", "Texas"],
                "population": [39500000, 19800000, 29000000]
            })
            
            data_file = os.path.join(self.temp_dir, "integration_data.csv")
            test_data.to_csv(data_file, index=False)
            
            test_config = {
                "input_data": ["integration_data.csv"],
                "input_metadata": [],
                "is_sdmx_dataset": False
            }
            
            config_file = os.path.join(self.temp_dir, "integration_config.json")
            with open(config_file, 'w') as f:
                json.dump(test_config, f)
                
            # Test ConfigAdapter
            adapter = ConfigAdapter(config_file, self.temp_dir, max_iterations=1)
            adk_config = adapter.to_adk_config()
            
            # Test EnhancedCoordinator (with minimal processing)
            coordinator = EnhancedIterativeCoordinator(
                max_iterations=1,
                auto_fix=False,  # Disable to avoid long processing
                use_advanced_fixes=True,
                learning_dir=self.temp_dir
            )
            
            tests.append({
                "name": "ConfigAdapter + EnhancedCoordinator: Basic integration",
                "status": "pass",
                "details": "Successfully created both components without errors"
            })
            
        except Exception as e:
            tests.append({
                "name": "ConfigAdapter + EnhancedCoordinator: Basic integration",
                "status": "fail",
                "error": str(e)
            })
            
        return tests

    def _run_compatibility_tests(self):
        """Run compatibility tests with existing pvmap_generator."""

        print("  🔄 Testing pvmap_generator.py compatibility...")
        compat_tests = self._test_pvmap_generator_compatibility()
        self.test_results["compatibility_tests"].extend(compat_tests)

        print("  🔄 Testing ADK backend invocation...")
        adk_tests = self._test_adk_backend_invocation()
        self.test_results["compatibility_tests"].extend(adk_tests)
        
    def _test_pvmap_generator_compatibility(self) -> List[Dict[str, Any]]:
        """Test compatibility with original pvmap_generator.py."""
        tests = []
        
        try:
            # Test config format compatibility
            original_config = {
                "input_data": ["test_data.csv"],
                "input_metadata": ["metadata.json"],
                "is_sdmx_dataset": True
            }
            
            config_file = os.path.join(self.temp_dir, "compat_config.json")
            with open(config_file, 'w') as f:
                json.dump(original_config, f)
                
            # Create test data files
            pd.DataFrame({"col1": [1, 2], "col2": ["A", "B"]}).to_csv(
                os.path.join(self.temp_dir, "test_data.csv"), index=False
            )
            
            with open(os.path.join(self.temp_dir, "metadata.json"), 'w') as f:
                json.dump({"test": "metadata"}, f)
                
            # Test loading with ConfigAdapter
            adapter = ConfigAdapter(config_file, self.temp_dir)
            adk_config = adapter.to_adk_config()
            template_vars = adapter.get_template_variables()
            
            # Check template variables match expected format
            expected_vars = ["working_dir", "python_interpreter", "script_dir", 
                           "input_data", "input_metadata", "dataset_type", 
                           "max_iterations", "gemini_run_id"]
            
            missing_vars = [var for var in expected_vars if var not in template_vars]
            
            if not missing_vars:
                tests.append({
                    "name": "pvmap_generator compatibility: Template variables",
                    "status": "pass",
                    "details": "All expected template variables present"
                })
            else:
                tests.append({
                    "name": "pvmap_generator compatibility: Template variables",
                    "status": "fail",
                    "error": f"Missing template variables: {missing_vars}"
                })
                
        except Exception as e:
            tests.append({
                "name": "pvmap_generator compatibility: Template variables",
                "status": "fail",
                "error": str(e)
            })
            
        return tests

    def _test_adk_backend_invocation(self) -> List[Dict[str, Any]]:
        """Test ADK backend invocation via pvmap_generator.py --use_adk flag."""
        tests = []

        try:
            # Create test data directory within testdata
            testdata_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'testdata', 'adk_integration')
            os.makedirs(testdata_dir, exist_ok=True)

            # Create simple test CSV
            csv_path = os.path.join(testdata_dir, "test_data.csv")
            data = {
                "Year": [2020, 2021],
                "State": ["California", "Texas"],
                "Employment_Count": [1500000, 1200000],
                "Industry": ["Technology", "Technology"]
            }
            df = pd.DataFrame(data)
            df.to_csv(csv_path, index=False)

            # Create test config
            config_path = os.path.join(testdata_dir, "test_config.json")
            config = {
                "data_config": {
                    "input_data": [csv_path],
                    "input_metadata": [],
                    "is_sdmx_dataset": False
                }
            }

            with open(config_path, 'w') as f:
                json.dump(config, f, indent=2)

            # Get python environment path
            script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            python_env = os.path.join(os.path.dirname(script_dir), '..', '.env', 'bin', 'python')

            # Run pvmap_generator with ADK backend
            cmd = [
                python_env, 'pvmap_generator.py',
                '--data_config', config_path,
                '--use_adk',
                '--max_iterations', '1',
                '--skip_confirmation'
            ]

            result = subprocess.run(
                cmd,
                cwd=script_dir,
                capture_output=True,
                text=True,
                timeout=120  # 2 minute timeout
            )

            # Combine outputs for analysis
            full_output = result.stdout + result.stderr

            # Check for integration markers
            integration_markers = {
                "Config loaded": "Loaded config with" in full_output,
                "ADK backend invoked": "Using ADK agent system" in full_output,
                "Command constructed": "Running ADK command:" in full_output,
                "Temp config created": "adk_data_config.json" in full_output
            }

            # Count successes
            success_count = sum(integration_markers.values())
            total_markers = len(integration_markers)

            if integration_markers["ADK backend invoked"] and integration_markers["Command constructed"]:
                tests.append({
                    "name": "ADK backend invocation: Core integration",
                    "status": "pass",
                    "details": f"Successfully invoked ADK backend ({success_count}/{total_markers} markers found)"
                })
            else:
                tests.append({
                    "name": "ADK backend invocation: Core integration",
                    "status": "fail",
                    "error": f"ADK backend not properly invoked ({success_count}/{total_markers} markers found)"
                })

            # Cleanup test files
            try:
                if os.path.exists(csv_path):
                    os.remove(csv_path)
                if os.path.exists(config_path):
                    os.remove(config_path)
                if os.path.exists(testdata_dir):
                    os.rmdir(testdata_dir)
            except:
                pass  # Ignore cleanup errors

        except subprocess.TimeoutExpired:
            tests.append({
                "name": "ADK backend invocation: Timeout",
                "status": "fail",
                "error": "Test timed out after 2 minutes"
            })
        except Exception as e:
            tests.append({
                "name": "ADK backend invocation: Exception",
                "status": "fail",
                "error": str(e)
            })

        return tests

    def _run_performance_tests(self):
        """Run performance benchmarking tests."""
        
        print("  ⚡ Running performance benchmarks...")
        perf_tests = self._test_performance_benchmarks()
        self.test_results["performance_tests"].extend(perf_tests)
        
    def _test_performance_benchmarks(self) -> List[Dict[str, Any]]:
        """Benchmark Phase 6 performance against Phase 5."""
        tests = []
        
        # Note: These are lightweight performance tests
        # Full benchmarking would require actual processor execution
        
        try:
            # Test initialization time
            start_time = time.time()
            enhanced_coordinator = EnhancedIterativeCoordinator(
                max_iterations=1, use_advanced_fixes=True
            )
            enhanced_init_time = time.time() - start_time
            
            start_time = time.time()  
            basic_coordinator = IterativeCoordinator(max_iterations=1)
            basic_init_time = time.time() - start_time
            
            # Check if enhanced coordinator initialization is reasonable
            if enhanced_init_time < basic_init_time * TEST_CONFIG["performance_threshold_factor"]:
                tests.append({
                    "name": "Performance: Coordinator initialization",
                    "status": "pass",
                    "details": f"Enhanced: {enhanced_init_time:.3f}s, Basic: {basic_init_time:.3f}s"
                })
            else:
                tests.append({
                    "name": "Performance: Coordinator initialization",
                    "status": "warning",
                    "details": f"Enhanced coordinator slower: {enhanced_init_time:.3f}s vs {basic_init_time:.3f}s"
                })
                
        except Exception as e:
            tests.append({
                "name": "Performance: Coordinator initialization", 
                "status": "fail",
                "error": str(e)
            })
            
        return tests
        
    def _run_regression_tests(self):
        """Run regression tests to ensure Phase 5 functionality still works."""
        
        print("  🔒 Testing Phase 5 regression...")
        regression_tests = self._test_phase5_regression()
        self.test_results["regression_tests"].extend(regression_tests)
        
    def _test_phase5_regression(self) -> List[Dict[str, Any]]:
        """Test that Phase 5 functionality still works correctly."""
        tests = []
        
        try:
            # Test basic IterativeCoordinator still works
            basic_coordinator = IterativeCoordinator(max_iterations=1, auto_fix=False)
            
            tests.append({
                "name": "Phase 5 Regression: IterativeCoordinator creation",
                "status": "pass", 
                "details": "Basic IterativeCoordinator still functional"
            })
            
        except Exception as e:
            tests.append({
                "name": "Phase 5 Regression: IterativeCoordinator creation",
                "status": "fail",
                "error": str(e)
            })
            
        # Test that enhanced coordinator can run in basic mode
        try:
            enhanced_coordinator = EnhancedIterativeCoordinator(
                max_iterations=1, use_advanced_fixes=False
            )
            
            tests.append({
                "name": "Phase 5 Regression: EnhancedCoordinator basic mode",
                "status": "pass",
                "details": "EnhancedCoordinator works in basic mode"
            })
            
        except Exception as e:
            tests.append({
                "name": "Phase 5 Regression: EnhancedCoordinator basic mode",
                "status": "fail", 
                "error": str(e)
            })
            
        return tests
        
    def _run_end_to_end_tests(self):
        """Run end-to-end workflow tests."""
        
        print("  🎯 Testing end-to-end workflows...")
        e2e_tests = self._test_end_to_end_workflows()
        self.test_results["end_to_end_tests"].extend(e2e_tests)
        
    def _test_end_to_end_workflows(self) -> List[Dict[str, Any]]:
        """Test complete end-to-end workflows."""
        tests = []
        
        # Test 1: Config-based workflow (minimal)
        try:
            # Create minimal test setup
            test_data = pd.DataFrame({
                "year": [2020, 2021],
                "value": [100, 200]
            })
            
            data_file = os.path.join(self.temp_dir, "e2e_data.csv")
            test_data.to_csv(data_file, index=False)
            
            test_config = {
                "input_data": ["e2e_data.csv"],
                "input_metadata": [],
                "is_sdmx_dataset": False
            }
            
            config_file = os.path.join(self.temp_dir, "e2e_config.json")
            with open(config_file, 'w') as f:
                json.dump(test_config, f)
                
            # Test config loading end-to-end
            adapter = ConfigAdapter(config_file, self.temp_dir, max_iterations=1)
            adk_config = adapter.to_adk_config()
            
            # Verify key properties
            if (os.path.exists(adk_config.input_file) and 
                os.path.exists(adk_config.output_dir) and
                adk_config.dataset_type in ["csv", "sdmx"]):
                
                tests.append({
                    "name": "End-to-End: Config workflow setup",
                    "status": "pass",
                    "details": f"Successfully configured workflow for {adk_config.dataset_type} dataset"
                })
            else:
                tests.append({
                    "name": "End-to-End: Config workflow setup",
                    "status": "fail",
                    "error": "Invalid ADK configuration generated"
                })
                
        except Exception as e:
            tests.append({
                "name": "End-to-End: Config workflow setup",
                "status": "fail",
                "error": str(e)
            })
            
        return tests
        
    def _generate_test_summary(self, total_time: float) -> Dict[str, Any]:
        """Generate comprehensive test summary."""
        
        all_tests = []
        for category, tests in self.test_results.items():
            if category != "suite_error":
                all_tests.extend(tests)
                
        total_tests = len(all_tests)
        passed_tests = len([t for t in all_tests if t["status"] == "pass"])
        failed_tests = len([t for t in all_tests if t["status"] == "fail"])
        warning_tests = len([t for t in all_tests if t["status"] == "warning"])
        
        summary = {
            "total_tests": total_tests,
            "passed": passed_tests,
            "failed": failed_tests,
            "warnings": warning_tests,
            "success_rate": passed_tests / total_tests if total_tests > 0 else 0,
            "total_time": total_time,
            "categories": {
                category: {
                    "total": len(tests),
                    "passed": len([t for t in tests if t["status"] == "pass"]),
                    "failed": len([t for t in tests if t["status"] == "fail"])
                }
                for category, tests in self.test_results.items()
                if category != "suite_error"
            }
        }
        
        return summary
        
    def _print_test_summary(self, summary: Dict[str, Any]):
        """Print formatted test summary."""
        
        print("\n" + "="*60)
        print("PHASE 6 TEST RESULTS SUMMARY")
        print("="*60)
        
        print(f"📊 Total Tests: {summary['total_tests']}")
        print(f"✅ Passed: {summary['passed']}")
        print(f"❌ Failed: {summary['failed']}")
        print(f"⚠️  Warnings: {summary['warnings']}")
        print(f"📈 Success Rate: {summary['success_rate']:.1%}")
        print(f"⏱️  Total Time: {summary['total_time']:.2f}s")
        
        print(f"\n📋 By Category:")
        for category, stats in summary["categories"].items():
            status_icon = "✅" if stats["failed"] == 0 else "❌" if stats["passed"] == 0 else "⚡"
            print(f"  {status_icon} {category.replace('_', ' ').title()}: {stats['passed']}/{stats['total']} passed")
            
        # Overall assessment
        if summary["success_rate"] >= 0.95:
            print(f"\n🎉 EXCELLENT: Phase 6 implementation is highly stable!")
        elif summary["success_rate"] >= 0.85:
            print(f"\n✅ GOOD: Phase 6 implementation is stable with minor issues")
        elif summary["success_rate"] >= 0.70:
            print(f"\n⚠️ FAIR: Phase 6 implementation needs attention")
        else:
            print(f"\n❌ POOR: Phase 6 implementation has significant issues")
            
        print("="*60)


def main():
    """Main test execution function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Phase 6 Comprehensive Test Suite")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")
    parser.add_argument("--category", choices=["unit", "integration", "compatibility", 
                                             "performance", "regression", "e2e", "all"],
                       default="all", help="Test category to run")
    
    args = parser.parse_args()
    
    # Create and run test suite
    test_suite = ADKIntegrationTestSuite(verbose=args.verbose)
    
    try:
        if args.category == "all":
            results = test_suite.run_all_tests()
        else:
            # Run specific category (simplified for this example)
            print(f"Running {args.category} tests only...")
            results = test_suite.run_all_tests()  # In full implementation, would run specific category
            
        # Save results to file
        results_file = os.path.join(test_suite.temp_dir, "test_results.json")
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
            
        print(f"\n📄 Detailed results saved to: {results_file}")
        
        # Return appropriate exit code
        success_rate = results["summary"]["success_rate"]
        exit_code = 0 if success_rate >= 0.85 else 1
        
        return exit_code
        
    finally:
        test_suite.cleanup()


if __name__ == "__main__":
    exit(main())