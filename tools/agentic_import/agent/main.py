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
import copy
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List

from absl import app
from absl import flags
from absl import logging

# Add current directory to path for imports
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(_SCRIPT_DIR)

# Import workflow coordinators (Phase 4 & Phase 5)
from coordinator import execute_workflow, get_workflow_summary
from iterative_coordinator import IterativeCoordinator
from error_analyzer import ProcessorErrorAnalyzer
from fix_strategies import ComprehensiveFixStrategies
from workflow_state import WorkflowState
# Import Phase 6 configuration adapter
from config_adapter import ConfigAdapter, ConfigAdapterError, load_config_from_file
# Import Phase 6 enhanced coordinator
from enhanced_coordinator import EnhancedIterativeCoordinator

FLAGS = flags.FLAGS

# Input mode flags (mutually exclusive)
flags.DEFINE_string('input_data', None,
                    'Path to input CSV file (for direct mode)')

flags.DEFINE_string('output_dir', None,
                    'Directory for output files (for direct mode)')

flags.DEFINE_string('data_config', None,
                    'Path to data_config.json file (for compatibility mode)')

# At least one input mode must be specified
flags.register_multi_flags_validator(
    ['input_data', 'data_config'],
    lambda flag_dict: bool(flag_dict.get('input_data')) or bool(flag_dict.get('data_config')),
    message='Either --input_data or --data_config must be specified'
)

# If using direct mode, output_dir is required
flags.register_validator(
    'output_dir',
    lambda value: not FLAGS.input_data or bool(value),
    message='--output_dir is required when using --input_data'
)

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

# Phase 6 compatibility flags
flags.DEFINE_boolean('fallback_to_gemini', False,
                     'Fallback to original Gemini CLI on ADK failure (requires gemini in PATH)')

flags.DEFINE_boolean('batch_mode', False,
                     'Process multiple input files if specified in config (default: process first file only)')

flags.DEFINE_boolean('skip_confirmation', False,
                     'Skip user confirmation before processing (matches pvmap_generator behavior)')

flags.DEFINE_string('maps_api_key', None,
                    'Google Maps API key (for compatibility - passed to fallback)')

flags.DEFINE_string('dc_api_key', None,
                    'Data Commons API key (for compatibility - passed to fallback)')

flags.DEFINE_boolean('use_enhanced_coordinator', True,
                     'Use enhanced coordinator with advanced fix strategies (Phase 6)')


def validate_inputs() -> Dict[str, Any]:
    """Validate command line inputs for both direct and config modes.
    
    Returns:
        Dictionary with validation results
    """
    issues = []
    
    # Direct mode validation (--input_data specified)
    if FLAGS.input_data:
        if not os.path.exists(FLAGS.input_data):
            issues.append(f"Input file not found: {FLAGS.input_data}")
        elif not FLAGS.input_data.endswith('.csv'):
            issues.append(f"Input file must be CSV format: {FLAGS.input_data}")
            
        # Check output directory is valid
        try:
            Path(FLAGS.output_dir).mkdir(parents=True, exist_ok=True)
        except Exception as e:
            issues.append(f"Cannot create output directory {FLAGS.output_dir}: {str(e)}")
            
    # Config mode validation (--data_config specified)  
    elif FLAGS.data_config:
        if not os.path.exists(FLAGS.data_config):
            issues.append(f"Config file not found: {FLAGS.data_config}")
        elif not FLAGS.data_config.endswith('.json'):
            issues.append(f"Config file must be JSON format: {FLAGS.data_config}")
            
        # Try to load config to validate format
        try:
            config_adapter = load_config_from_file(
                FLAGS.data_config,
                max_iterations=FLAGS.max_iterations,
                auto_fix=FLAGS.auto_fix
            )
            
            # Validate input files exist
            validation = config_adapter.validate_input_files()
            if not validation['valid']:
                issues.extend(validation['errors'])
                
        except ConfigAdapterError as e:
            issues.append(f"Invalid configuration: {e}")
        except Exception as e:
            issues.append(f"Failed to load configuration: {e}")
            
    # Check working directory if specified
    if FLAGS.working_dir:
        try:
            Path(FLAGS.working_dir).mkdir(parents=True, exist_ok=True)
        except Exception as e:
            issues.append(f"Cannot create working directory {FLAGS.working_dir}: {str(e)}")
    
    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "mode": "direct" if FLAGS.input_data else "config"
    }


def run_single_pass_workflow() -> int:
    """Execute single-pass workflow (Phase 4 compatibility).
    
    Returns:
        Exit code (0 for success, 1 for error)
    """
    try:
        # Direct mode - use existing logic
        if FLAGS.input_data:
            working_dir = FLAGS.working_dir or FLAGS.output_dir
            
            logging.info("Running single-pass workflow (Phase 4 mode) - Direct Input")
            
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
                
        # Config mode - use ConfigAdapter
        else:
            return run_config_based_workflow(single_pass=True)
            
    except Exception as e:
        logging.error(f"Single-pass workflow failed: {str(e)}")
        return 1


def run_iterative_workflow() -> int:
    """Execute iterative workflow with retry logic (Phase 5).
    
    Returns:
        Exit code (0 for success, 1 for error)
    """
    try:
        # Direct mode - use existing logic
        if FLAGS.input_data:
            working_dir = FLAGS.working_dir or FLAGS.output_dir
            
            logging.info("🔄 Starting iterative workflow (Phase 5 mode) - Direct Input")
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
                    
            # Initialize coordinator (enhanced or basic)
            if FLAGS.use_enhanced_coordinator:
                coordinator = EnhancedIterativeCoordinator(
                    max_iterations=FLAGS.max_iterations,
                    auto_fix=FLAGS.auto_fix,
                    use_advanced_fixes=True,
                    learning_dir=FLAGS.state_dir
                )
                # Execute with advanced retry logic
                result = coordinator.process_with_advanced_retry(
                    input_file=FLAGS.input_data,
                    output_dir=FLAGS.output_dir,
                    working_dir=working_dir
                )
            else:
                coordinator = IterativeCoordinator(
                    max_iterations=FLAGS.max_iterations,
                    auto_fix=FLAGS.auto_fix
                )
                # Execute with basic retry logic
                result = coordinator.process_with_retry(
                    input_file=FLAGS.input_data,
                    output_dir=FLAGS.output_dir,
                    working_dir=working_dir
                )
            
            return _handle_iterative_result(result)
            
        # Config mode - use ConfigAdapter
        else:
            return run_config_based_workflow(single_pass=False)
            
    except Exception as e:
        logging.error(f"Iterative workflow failed: {str(e)}")
        return 1


def _handle_iterative_result(result: Dict[str, Any]) -> int:
    """Handle iterative workflow results and reporting.
    
    Args:
        result: Result from iterative coordinator
        
    Returns:
        Exit code (0 for success, 1 for error)
    """
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


def run_config_based_workflow(single_pass: bool = False) -> int:
    """Execute workflow using data_config.json configuration.
    
    Args:
        single_pass: If True, run single-pass workflow; otherwise iterative
        
    Returns:
        Exit code (0 for success, 1 for error)
    """
    try:
        # Load configuration
        config_adapter = load_config_from_file(
            FLAGS.data_config,
            working_dir=FLAGS.working_dir,
            max_iterations=FLAGS.max_iterations,
            auto_fix=FLAGS.auto_fix
        )
        
        # Get ADK configuration
        adk_config = config_adapter.to_adk_config()
        
        # Save run metadata for debugging
        config_adapter.save_run_metadata()
        
        # Get list of input files for processing
        input_files = config_adapter.get_input_files()
        
        # Determine processing mode
        if FLAGS.batch_mode and len(input_files) > 1:
            return _run_batch_processing(config_adapter, adk_config, input_files, single_pass)
        else:
            return _run_single_file_processing(config_adapter, adk_config, single_pass)
            
    except ConfigAdapterError as e:
        logging.error(f"Configuration error: {e}")
        if FLAGS.fallback_to_gemini:
            logging.info("Attempting fallback to Gemini CLI...")
            return _fallback_to_gemini_cli()
        return 1
    except Exception as e:
        logging.error(f"Config-based workflow failed: {e}")
        if FLAGS.fallback_to_gemini:
            logging.info("Attempting fallback to Gemini CLI...")
            return _fallback_to_gemini_cli()
        return 1


def _run_single_file_processing(config_adapter: ConfigAdapter, adk_config, single_pass: bool) -> int:
    """Process single file using ADK workflow.
    
    Args:
        config_adapter: Configured ConfigAdapter
        adk_config: ADK configuration
        single_pass: Single-pass vs iterative mode
        
    Returns:
        Exit code (0 for success, 1 for error)
    """
    try:
        logging.info(f"📄 Processing single file: {adk_config.input_file}")
        logging.info(f"Dataset type: {adk_config.dataset_type.upper()}")
        logging.info(f"Output directory: {adk_config.output_dir}")
        
        if single_pass:
            logging.info("Running single-pass workflow (Phase 4 mode) - Config Input")
            result = execute_workflow(
                input_file=adk_config.input_file,
                output_dir=adk_config.output_dir,
                working_dir=adk_config.working_dir
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
                
                if FLAGS.fallback_to_gemini:
                    logging.info("Attempting fallback to Gemini CLI...")
                    return _fallback_to_gemini_cli()
                return 1
                
        else:
            logging.info("🔄 Starting iterative workflow (Phase 5 mode) - Config Input")
            logging.info(f"Max iterations: {FLAGS.max_iterations}")
            logging.info(f"Auto-fix enabled: {FLAGS.auto_fix}")
            
            # Initialize coordinator (enhanced or basic)
            if FLAGS.use_enhanced_coordinator:
                coordinator = EnhancedIterativeCoordinator(
                    max_iterations=FLAGS.max_iterations,
                    auto_fix=FLAGS.auto_fix,
                    use_advanced_fixes=True,
                    learning_dir=FLAGS.state_dir
                )
                # Execute with advanced retry logic
                result = coordinator.process_with_advanced_retry(
                    input_file=adk_config.input_file,
                    output_dir=adk_config.output_dir,
                    working_dir=adk_config.working_dir
                )
            else:
                coordinator = IterativeCoordinator(
                    max_iterations=FLAGS.max_iterations,
                    auto_fix=FLAGS.auto_fix
                )
                # Execute with basic retry logic
                result = coordinator.process_with_retry(
                    input_file=adk_config.input_file,
                    output_dir=adk_config.output_dir,
                    working_dir=adk_config.working_dir
                )
            
            exit_code = _handle_iterative_result(result)
            
            if exit_code != 0 and FLAGS.fallback_to_gemini:
                logging.info("Attempting fallback to Gemini CLI...")
                return _fallback_to_gemini_cli()
                
            return exit_code
            
    except Exception as e:
        logging.error(f"Single file processing failed: {e}")
        if FLAGS.fallback_to_gemini:
            logging.info("Attempting fallback to Gemini CLI...")
            return _fallback_to_gemini_cli()
        return 1


def _run_batch_processing(config_adapter: ConfigAdapter, adk_config, input_files: List[str], single_pass: bool) -> int:
    """Process multiple files in batch mode.
    
    Args:
        config_adapter: Configured ConfigAdapter
        adk_config: ADK configuration
        input_files: List of input files to process
        single_pass: Single-pass vs iterative mode
        
    Returns:
        Exit code (0 for success, 1+ for errors)
    """
    logging.info(f"📋 Batch processing mode: {len(input_files)} files")
    
    results = []
    total_errors = 0
    
    for i, input_file in enumerate(input_files, 1):
        logging.info(f"\n=== Processing file {i}/{len(input_files)}: {input_file} ===")
        
        try:
            # Create file-specific configuration
            file_adk_config = copy.deepcopy(adk_config)
            file_adk_config.input_file = input_file
            
            # Create file-specific output directory
            file_basename = os.path.splitext(os.path.basename(input_file))[0]
            file_output_dir = os.path.join(adk_config.output_dir, f"file_{i}_{file_basename}")
            file_working_dir = os.path.join(adk_config.working_dir, f"file_{i}_{file_basename}")
            
            os.makedirs(file_output_dir, exist_ok=True)
            os.makedirs(file_working_dir, exist_ok=True)
            
            file_adk_config.output_dir = file_output_dir
            file_adk_config.working_dir = file_working_dir
            
            # Process this file
            if single_pass:
                result = execute_workflow(
                    input_file=file_adk_config.input_file,
                    output_dir=file_adk_config.output_dir,
                    working_dir=file_adk_config.working_dir
                )
                success = result["status"] == "success"
            else:
                if FLAGS.use_enhanced_coordinator:
                    coordinator = EnhancedIterativeCoordinator(
                        max_iterations=FLAGS.max_iterations,
                        auto_fix=FLAGS.auto_fix,
                        use_advanced_fixes=True,
                        learning_dir=FLAGS.state_dir
                    )
                    result = coordinator.process_with_advanced_retry(
                        input_file=file_adk_config.input_file,
                        output_dir=file_adk_config.output_dir,
                        working_dir=file_adk_config.working_dir
                    )
                else:
                    coordinator = IterativeCoordinator(
                        max_iterations=FLAGS.max_iterations,
                        auto_fix=FLAGS.auto_fix
                    )
                    result = coordinator.process_with_retry(
                        input_file=file_adk_config.input_file,
                        output_dir=file_adk_config.output_dir,
                        working_dir=file_adk_config.working_dir
                    )
                success = result.get("status") == "success"
                
            results.append({
                "file": input_file,
                "success": success,
                "result": result
            })
            
            if success:
                logging.info(f"✅ File {i} completed successfully")
            else:
                logging.error(f"❌ File {i} failed")
                total_errors += 1
                
        except Exception as e:
            logging.error(f"❌ File {i} failed with exception: {e}")
            total_errors += 1
            results.append({
                "file": input_file,
                "success": False,
                "error": str(e)
            })
            
    # Summary report
    logging.info(f"\n=== Batch Processing Summary ===")
    logging.info(f"Total files: {len(input_files)}")
    logging.info(f"Successful: {len(input_files) - total_errors}")
    logging.info(f"Failed: {total_errors}")
    
    for result in results:
        status_icon = "✅" if result["success"] else "❌"
        logging.info(f"  {status_icon} {result['file']}")
        
    return total_errors  # Return number of failures


def _fallback_to_gemini_cli() -> int:
    """Fallback to original Gemini CLI pvmap_generator.
    
    Returns:
        Exit code from Gemini CLI execution
    """
    try:
        import subprocess
        import shutil
        
        # Check if gemini CLI is available
        if not shutil.which('gemini'):
            logging.error("Gemini CLI not found in PATH - fallback not possible")
            return 1
            
        # Build command to run original pvmap_generator
        script_dir = os.path.dirname(os.path.abspath(__file__))
        pvmap_generator_path = os.path.join(os.path.dirname(script_dir), 'pvmap_generator.py')
        
        if not os.path.exists(pvmap_generator_path):
            logging.error(f"Original pvmap_generator.py not found at {pvmap_generator_path}")
            return 1
            
        # Build command
        cmd = [sys.executable, pvmap_generator_path, f'--data_config={FLAGS.data_config}']
        
        # Add optional flags
        if FLAGS.maps_api_key:
            cmd.append(f'--maps_api_key={FLAGS.maps_api_key}')
        if FLAGS.dc_api_key:
            cmd.append(f'--dc_api_key={FLAGS.dc_api_key}')
        if FLAGS.skip_confirmation:
            cmd.append('--skip_confirmation')
        if FLAGS.max_iterations != 10:  # Only add if different from default
            cmd.append(f'--max_iterations={FLAGS.max_iterations}')
            
        logging.info(f"Executing Gemini CLI fallback: {' '.join(cmd)}")
        
        # Execute with real-time output
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1
        )
        
        # Stream output
        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                print(output.rstrip())
                
        return process.wait()
        
    except Exception as e:
        logging.error(f"Gemini CLI fallback failed: {e}")
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
    # User confirmation for config mode (matching pvmap_generator behavior)
    if FLAGS.data_config and not FLAGS.skip_confirmation:
        if not _get_user_confirmation():
            logging.info("Processing cancelled by user.")
            return 1
            
    # Determine which workflow mode to use
    if FLAGS.max_iterations > 1 or FLAGS.auto_fix or FLAGS.resume:
        return run_iterative_workflow()
    else:
        return run_single_pass_workflow()


def _get_user_confirmation() -> bool:
    """Get user confirmation before processing (matches pvmap_generator behavior).
    
    Returns:
        True if user confirms, False otherwise
    """
    try:
        # Load config for display
        config_adapter = load_config_from_file(FLAGS.data_config)
        input_files = config_adapter.get_input_files()
        
        print("\n" + "=" * 60)
        print("ADK PVMAP GENERATION SUMMARY (Phase 6)")
        print("=" * 60)
        print(f"Configuration file: {FLAGS.data_config}")
        print(f"Input data files: {len(input_files)}")
        for i, file_path in enumerate(input_files, 1):
            print(f"  {i}. {file_path}")
        print(f"Dataset type: {config_adapter.is_sdmx_dataset() and 'SDMX' or 'CSV'}")
        print(f"Processing mode: {'Batch' if FLAGS.batch_mode and len(input_files) > 1 else 'Single'}")
        print(f"Max iterations: {FLAGS.max_iterations}")
        print(f"Auto-fix enabled: {FLAGS.auto_fix}")
        print(f"Fallback to Gemini: {FLAGS.fallback_to_gemini}")
        print(f"Working directory: {config_adapter.working_dir}")
        print(f"Run directory: {config_adapter.get_run_directory()}")
        print("=" * 60)
        
        response = input("\nProceed with PVMap generation? [y/N]: ").strip().lower()
        return response in ['y', 'yes']
        
    except Exception as e:
        logging.error(f"Failed to display confirmation: {e}")
        return False


def print_usage_info():
    """Print helpful usage information."""
    print("\n=== ADK PVMap Generator (Phase 6) ===")
    print("Full integration with config compatibility and Gemini fallback")
    
    # Determine input mode
    input_mode = "Config" if FLAGS.data_config else "Direct"
    print(f"Input mode: {input_mode}")
    
    # Determine processing mode
    if FLAGS.max_iterations > 1 or FLAGS.auto_fix or FLAGS.resume:
        print("🔄 Running in ITERATIVE MODE (Phase 5+)")
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
        
    if FLAGS.data_config:
        print("\nPhase 6 features (Config mode):")
        print("  • Full pvmap_generator.py compatibility")
        print("  • SDMX and CSV dataset support")
        print("  • Multiple input file handling")
        print("  • Batch processing mode")
        if FLAGS.fallback_to_gemini:
            print("  • Automatic Gemini CLI fallback on failure")
            
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
        
    logging.info(f"Running in {validation['mode']} mode")
    
    # Execute workflow
    return run_workflow()


if __name__ == '__main__':
    app.run(main)