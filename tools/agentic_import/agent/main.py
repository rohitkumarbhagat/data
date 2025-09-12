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

"""ADK-based PVMap Generator - Main Entry Point (Phase 5)

This is the Phase 5 implementation of the PVMap generator using Google ADK agents
with intelligent retry logic and error recovery. It provides a command-line interface
for running the complete workflow with automatic fix strategies.

Usage:
    # Basic usage (single attempt)
    python -m agent.main --input_data=/path/to/data.csv --output_dir=/path/to/output
    
    # With iterative retry (recommended)
    python -m agent.main --input_data=/path/to/data.csv --output_dir=/path/to/output --max_iterations=3 --auto_fix
    
    # Resume interrupted workflow
    python -m agent.main --input_data=/path/to/data.csv --output_dir=/path/to/output --resume

The workflow includes:
1. Data analysis and column type detection
2. Property-value mapping generation  
3. Metadata configuration creation
4. Statvar processor execution
5. Output validation
6. Intelligent error analysis and recovery (Phase 5)
7. Iteration tracking and performance metrics (Phase 5)

For more details, see: /tools/agentic_import/agent/README.md
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

from absl import app
from absl import flags
from absl import logging

# Import workflow coordinators (Phase 4 & Phase 5)
from .coordinator import execute_workflow, get_workflow_summary
from .iterative_coordinator import IterativeCoordinator
from .error_analyzer import ProcessorErrorAnalyzer
from .fix_strategies import ComprehensiveFixStrategies
from .workflow_state import WorkflowState

FLAGS = flags.FLAGS

# Required flags
flags.DEFINE_string('input_data', None,
                    'Path to input CSV file (required)')
flags.mark_flag_as_required('input_data')

flags.DEFINE_string('output_dir', None,
                    'Directory for output files (required)')
flags.mark_flag_as_required('output_dir')

# Optional flags
flags.DEFINE_string('working_dir', None,
                    'Working directory for intermediate files (defaults to output_dir)')

flags.DEFINE_boolean('verbose', False,
                     'Enable verbose logging')

flags.DEFINE_boolean('dry_run', False,
                     'Analyze and generate configs only, do not run processor')

flags.DEFINE_string('python_interpreter', None,
                    'Python interpreter to use for processor (defaults to current python)')

# Phase 5 iteration control flags
flags.DEFINE_integer('max_iterations', 1,
                     'Maximum number of retry iterations (1 = single attempt, 3+ recommended for retry logic)')

flags.DEFINE_boolean('auto_fix', False,
                     'Enable automatic error fix strategies (recommended with max_iterations > 1)')

flags.DEFINE_boolean('resume', False,
                     'Resume interrupted workflow from previous state')

flags.DEFINE_boolean('show_iteration_details', False,
                     'Show detailed iteration progress and fix effectiveness')

flags.DEFINE_string('state_dir', None,
                    'Directory for iteration state persistence (defaults to working_dir/.datacommons)')


def validate_inputs() -> Dict[str, Any]:
    """Validate command line inputs.
    
    Returns:
        Dictionary with validation results
    """
    issues = []
    
    # Check input file exists
    if not os.path.exists(FLAGS.input_data):
        issues.append(f"Input file not found: {FLAGS.input_data}")
    elif not FLAGS.input_data.endswith('.csv'):
        issues.append(f"Input file must be CSV format: {FLAGS.input_data}")
        
    # Check output directory is valid
    try:
        Path(FLAGS.output_dir).mkdir(parents=True, exist_ok=True)
    except Exception as e:
        issues.append(f"Cannot create output directory {FLAGS.output_dir}: {str(e)}")
        
    # Check working directory if specified
    if FLAGS.working_dir:
        try:
            Path(FLAGS.working_dir).mkdir(parents=True, exist_ok=True)
        except Exception as e:
            issues.append(f"Cannot create working directory {FLAGS.working_dir}: {str(e)}")
    
    return {
        "valid": len(issues) == 0,
        "issues": issues
    }


def run_single_pass_workflow() -> int:
    """Execute single-pass workflow (Phase 4 compatibility).
    
    Returns:
        Exit code (0 for success, 1 for error)
    """
    try:
        working_dir = FLAGS.working_dir or FLAGS.output_dir
        
        logging.info("Running single-pass workflow (Phase 4 mode)")
        
        result = execute_workflow(
            input_file=FLAGS.input_data,
            output_dir=FLAGS.output_dir,
            working_dir=working_dir
        )
        
        summary = get_workflow_summary(result)
        
        if result["status"] == "success":
            logging.info("✅ Single-pass workflow completed successfully!")
            logging.info(f"Generated files: {', '.join(summary['files_generated'])}")
            return 0
        else:
            logging.error("❌ Single-pass workflow failed!")
            logging.error(f"Failed at step: {summary.get('error_step', 'unknown')}")
            logging.error(f"Error: {summary.get('error_message', 'Unknown error')}")
            return 1
            
    except Exception as e:
        logging.error(f"Single-pass workflow failed: {str(e)}")
        return 1


def run_iterative_workflow() -> int:
    """Execute iterative workflow with retry logic (Phase 5).
    
    Returns:
        Exit code (0 for success, 1 for error)
    """
    try:
        working_dir = FLAGS.working_dir or FLAGS.output_dir
        
        logging.info("🔄 Starting iterative workflow (Phase 5 mode)")
        logging.info(f"Max iterations: {FLAGS.max_iterations}")
        logging.info(f"Auto-fix enabled: {FLAGS.auto_fix}")
        
        # Check for resumable workflow
        if FLAGS.resume:
            state = WorkflowState(FLAGS.input_data, FLAGS.output_dir, working_dir, FLAGS.state_dir)
            resume_info = state.get_resume_info()
            
            if resume_info["can_resume"]:
                logging.info(f"📋 Resuming workflow from iteration {resume_info['current_iteration']}")
                logging.info(f"Previous fixes tried: {', '.join(resume_info['fixes_tried'])}")
            else:
                logging.info("No resumable workflow found, starting fresh")
                
        # Initialize iterative coordinator
        coordinator = IterativeCoordinator(
            max_iterations=FLAGS.max_iterations,
            auto_fix=FLAGS.auto_fix
        )
        
        # Execute with retry logic
        result = coordinator.process_with_retry(
            input_file=FLAGS.input_data,
            output_dir=FLAGS.output_dir,
            working_dir=working_dir
        )
        
        # Report results with iteration details
        iteration_summary = result.get("iteration_summary", {})
        
        if result.get("status") == "success":
            logging.info("🎉 Iterative workflow completed successfully!")
            logging.info(f"Total iterations: {iteration_summary.get('total_iterations', 'unknown')}")
            logging.info(f"Total time: {iteration_summary.get('total_time_seconds', 0):.1f}s")
            
            if FLAGS.show_iteration_details:
                _print_iteration_details(iteration_summary)
                
            return 0
            
        else:
            logging.error("❌ Iterative workflow failed after all attempts!")
            logging.error(f"Total iterations: {iteration_summary.get('total_iterations', 'unknown')}")
            logging.error(f"Final status: {iteration_summary.get('final_status', 'unknown')}")
            
            if FLAGS.show_iteration_details:
                _print_iteration_details(iteration_summary)
            else:
                logging.info("Use --show_iteration_details for detailed failure analysis")
                
            return 1
            
    except Exception as e:
        logging.error(f"Iterative workflow failed: {str(e)}")
        return 1


def _print_iteration_details(iteration_summary: Dict[str, Any]):
    """Print detailed iteration information.
    
    Args:
        iteration_summary: Summary from WorkflowState
    """
    logging.info("\n📊 Iteration Details:")
    
    # Progress over iterations
    if "success_progression" in iteration_summary:
        logging.info("\nProgress by iteration:")
        for progress in iteration_summary["success_progression"]:
            status_icon = "✅" if progress["status"] == "success" else "❌"
            logging.info(
                f"  {status_icon} Iteration {progress['attempt']}: "
                f"{progress['steps_completed']} steps completed, "
                f"{progress['fixes_applied']} fixes applied "
                f"({progress.get('duration', 0):.1f}s)"
            )
            
    # Fix effectiveness
    if "fix_effectiveness" in iteration_summary:
        logging.info("\nFix effectiveness:")
        for fix, stats in iteration_summary["fix_effectiveness"].items():
            success_rate = stats["success_rate"] * 100
            logging.info(
                f"  • {fix}: {success_rate:.0f}% success rate "
                f"({stats['applications']} applications)"
            )
            
    # Error patterns
    if "most_common_errors" in iteration_summary:
        logging.info(f"\nError patterns: {iteration_summary['most_common_errors']}")
        
    # Configuration changes
    config_changes = iteration_summary.get("configuration_changes", 0)
    if config_changes > 0:
        logging.info(f"Configuration files modified: {config_changes} times")


def run_workflow() -> int:
    """Execute the appropriate workflow based on flags.
    
    Returns:
        Exit code (0 for success, 1 for error)
    """
    # Determine which workflow mode to use
    if FLAGS.max_iterations > 1 or FLAGS.auto_fix or FLAGS.resume:
        return run_iterative_workflow()
    else:
        return run_single_pass_workflow()


def print_usage_info():
    """Print helpful usage information."""
    print("\n=== ADK PVMap Generator (Phase 5) ===")
    print("Enhanced implementation with intelligent retry logic")
    
    # Determine mode
    if FLAGS.max_iterations > 1 or FLAGS.auto_fix or FLAGS.resume:
        print("🔄 Running in ITERATIVE MODE (Phase 5)")
        print("\nThis mode includes:")
        print("  • Intelligent error analysis and recovery")
        print("  • Automatic fix strategies for common errors")
        print("  • Iteration tracking and performance metrics")
        print("  • Workflow resumption capabilities")
    else:
        print("📋 Running in SINGLE-PASS MODE (Phase 4 compatibility)")
        print("\nConsider using iterative mode for better success rates:")
        print("  --max_iterations=3 --auto_fix")
        
    print("\nCore workflow components:")
    print("  • Data analysis agent (column type detection)")
    print("  • PVMap creator agent (property-value mapping)")  
    print("  • Metadata generator agent (processor configuration)")
    print("  • Processor runner agent (statvar processor execution)")
    
    if FLAGS.max_iterations > 1:
        print("\nPhase 5 enhancements:")
        print("  • Error analyzer (intelligent failure categorization)")
        print("  • Fix strategies (automated error recovery)")
        print("  • State management (iteration tracking & resumption)")
        
    print("\nFor more information, see: tools/agentic_import/agent/README.md\n")


def main(argv):
    """Main entry point."""
    del argv  # Unused
    
    # Set up logging
    if FLAGS.verbose:
        logging.set_verbosity(logging.INFO)
    else:
        logging.set_verbosity(logging.WARNING)
        
    # Print usage info
    print_usage_info()
    
    # Validate inputs
    validation = validate_inputs()
    if not validation["valid"]:
        logging.error("Input validation failed:")
        for issue in validation["issues"]:
            logging.error(f"  • {issue}")
        return 1
        
    # Execute workflow
    return run_workflow()


if __name__ == '__main__':
    app.run(main)