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

"""ADK-based PVMap Generator - Main Entry Point

This is the Phase 4 implementation of the PVMap generator using Google ADK agents
instead of the monolithic Gemini CLI approach. It provides a command-line interface
for running the complete workflow.

Usage:
    python -m agent.main --input_data=/path/to/data.csv --output_dir=/path/to/output

The workflow includes:
1. Data analysis and column type detection
2. Property-value mapping generation  
3. Metadata configuration creation
4. Statvar processor execution
5. Output validation

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

# Import our workflow coordinator
from .coordinator import execute_workflow, get_workflow_summary

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


def run_workflow() -> int:
    """Execute the ADK workflow.
    
    Returns:
        Exit code (0 for success, 1 for error)
    """
    try:
        # Set up directories
        working_dir = FLAGS.working_dir or FLAGS.output_dir
        
        logging.info("Starting ADK-based PVMap generation workflow")
        logging.info(f"Input: {FLAGS.input_data}")
        logging.info(f"Output: {FLAGS.output_dir}")
        logging.info(f"Working: {working_dir}")
        
        # Execute the workflow
        if FLAGS.dry_run:
            logging.info("DRY RUN MODE: Will stop before processor execution")
            
        result = execute_workflow(
            input_file=FLAGS.input_data,
            output_dir=FLAGS.output_dir,
            working_dir=working_dir
        )
        
        # Generate summary
        summary = get_workflow_summary(result)
        
        # Report results
        if result["status"] == "success":
            logging.info("✅ Workflow completed successfully!")
            logging.info(f"Generated files: {', '.join(summary['files_generated'])}")
            
            if "output_files" in summary:
                logging.info("Output file details:")
                for file_type, info in summary["output_files"].items():
                    if info.get("exists"):
                        logging.info(f"  {file_type.upper()}: {info['path']} ({info.get('size_bytes', 0)} bytes)")
                        
            return 0
            
        else:
            logging.error("❌ Workflow failed!")
            logging.error(f"Failed at step: {summary.get('error_step', 'unknown')}")
            logging.error(f"Error: {summary.get('error_message', 'Unknown error')}")
            
            if "suggestions" in summary:
                logging.info("Suggestions:")
                for suggestion in summary["suggestions"]:
                    logging.info(f"  • {suggestion}")
                    
            return 1
            
    except Exception as e:
        logging.error(f"Workflow execution failed: {str(e)}")
        return 1


def print_usage_info():
    """Print helpful usage information."""
    print("\n=== ADK PVMap Generator ===")
    print("Phase 4 implementation using Agent Development Kit")
    print("\nThis tool processes CSV data for Data Commons import using:")
    print("  • Data analysis agent (column type detection)")
    print("  • PVMap creator agent (property-value mapping)")  
    print("  • Metadata generator agent (processor configuration)")
    print("  • Processor runner agent (statvar processor execution)")
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