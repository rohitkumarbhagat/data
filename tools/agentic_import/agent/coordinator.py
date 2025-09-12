from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Dict, Any, List

import logging

try:
    from google.adk.agents import LlmAgent
    from absl import logging
    ADK_AVAILABLE = True
except ImportError:
    import logging
    ADK_AVAILABLE = False

# Import all the component agents and tools
try:
    from .analyzer import analyze_column_types, suggest_dc_mappings
    from .pvmap_creator import create_pv_mappings, write_pvmap_csv, validate_pvmap_structure
    from .metadata_generator import generate_metadata_config, write_metadata_csv, validate_metadata_config
    from .processor_runner import run_statvar_processor, validate_processor_output, parse_processor_errors
except ImportError:
    # Fallback for direct execution
    from analyzer import analyze_column_types, suggest_dc_mappings
    from pvmap_creator import create_pv_mappings, write_pvmap_csv, validate_pvmap_structure
    from metadata_generator import generate_metadata_config, write_metadata_csv, validate_metadata_config
    from processor_runner import run_statvar_processor, validate_processor_output, parse_processor_errors


def execute_workflow(input_file: str, output_dir: str, working_dir: str = None) -> Dict[str, Any]:
    """Execute complete PVMap generation workflow.
    
    Args:
        input_file: Path to input CSV file
        output_dir: Directory for output files
        working_dir: Working directory (defaults to output_dir)
        
    Returns:
        Dictionary with workflow execution results
    """
    try:
        # Set up directories
        if working_dir is None:
            working_dir = output_dir
            
        os.makedirs(output_dir, exist_ok=True)
        os.makedirs(working_dir, exist_ok=True)
        
        workflow_result = {
            "status": "in_progress",
            "steps": {},
            "files_generated": {},
            "input_file": input_file,
            "output_dir": output_dir,
            "working_dir": working_dir
        }
        
        logging.info(f"Starting workflow for: {input_file}")
        
        # Step 1: Analyze data structure
        logging.info("Step 1: Analyzing data structure...")
        analysis_result = analyze_column_types(input_file, sample_rows=50)
        workflow_result["steps"]["analysis"] = analysis_result
        
        if analysis_result.get("status") != "success":
            workflow_result["status"] = "error"
            workflow_result["error_step"] = "analysis" 
            workflow_result["error_message"] = analysis_result.get("error_message", "Analysis failed")
            return workflow_result
            
        # Step 2: Create PV mappings
        logging.info("Step 2: Creating PV mappings...")
        pvmap_result = create_pv_mappings(analysis_result)
        workflow_result["steps"]["pvmap_creation"] = pvmap_result
        
        if pvmap_result.get("status") != "success":
            workflow_result["status"] = "error"
            workflow_result["error_step"] = "pvmap_creation"
            workflow_result["error_message"] = pvmap_result.get("error_message", "PV mapping failed")
            return workflow_result
            
        # Validate mappings
        mappings = pvmap_result["mappings"]
        validation_result = validate_pvmap_structure(mappings)
        workflow_result["steps"]["pvmap_validation"] = validation_result
        
        if not validation_result.get("valid", False):
            workflow_result["status"] = "error"
            workflow_result["error_step"] = "pvmap_validation"
            workflow_result["error_message"] = f"Invalid PV mappings: {validation_result.get('issues', [])}"
            return workflow_result
            
        # Write PVMap to file
        pvmap_path = os.path.join(working_dir, "pvmap.csv")
        write_result = write_pvmap_csv(mappings, pvmap_path)
        workflow_result["steps"]["pvmap_write"] = write_result
        workflow_result["files_generated"]["pvmap"] = pvmap_path
        
        if write_result.get("status") != "success":
            workflow_result["status"] = "error"
            workflow_result["error_step"] = "pvmap_write"
            workflow_result["error_message"] = write_result.get("error_message", "Failed to write PV map")
            return workflow_result
            
        # Step 3: Generate metadata configuration
        logging.info("Step 3: Generating metadata configuration...")
        metadata_result = generate_metadata_config(input_file, analysis_result)
        workflow_result["steps"]["metadata_generation"] = metadata_result
        
        if metadata_result.get("status") != "success":
            workflow_result["status"] = "error"
            workflow_result["error_step"] = "metadata_generation"
            workflow_result["error_message"] = metadata_result.get("error_message", "Metadata generation failed")
            return workflow_result
            
        # Validate metadata config
        config = metadata_result["config"]
        metadata_validation = validate_metadata_config(config)
        workflow_result["steps"]["metadata_validation"] = metadata_validation
        
        if not metadata_validation.get("valid", False):
            workflow_result["status"] = "error"
            workflow_result["error_step"] = "metadata_validation"
            workflow_result["error_message"] = f"Invalid metadata: {metadata_validation.get('issues', [])}"
            return workflow_result
            
        # Write metadata to file
        metadata_path = os.path.join(working_dir, "metadata.csv")
        metadata_write_result = write_metadata_csv(config, metadata_path)
        workflow_result["steps"]["metadata_write"] = metadata_write_result
        workflow_result["files_generated"]["metadata"] = metadata_path
        
        if metadata_write_result.get("status") != "success":
            workflow_result["status"] = "error"
            workflow_result["error_step"] = "metadata_write"
            workflow_result["error_message"] = metadata_write_result.get("error_message", "Failed to write metadata")
            return workflow_result
            
        # Step 4: Run statvar processor
        logging.info("Step 4: Running statvar processor...")
        output_path = os.path.join(output_dir, "output")
        
        processor_config = {
            "input_data": input_file,
            "pv_map": pvmap_path,
            "metadata": metadata_path,
            "output_path": output_path,
            "working_dir": working_dir
        }
        
        processor_result = run_statvar_processor(processor_config)
        workflow_result["steps"]["processor_execution"] = processor_result
        
        if processor_result.get("status") != "success":
            # Parse errors for better diagnostics
            error_analysis = parse_processor_errors(
                processor_result.get("stderr", ""),
                processor_result.get("exit_code", -1)
            )
            workflow_result["steps"]["error_analysis"] = error_analysis
            workflow_result["status"] = "error"
            workflow_result["error_step"] = "processor_execution"
            workflow_result["error_message"] = processor_result.get("error_message", "Processor execution failed")
            return workflow_result
            
        # Step 5: Validate output files
        logging.info("Step 5: Validating output files...")
        output_validation = validate_processor_output(output_path)
        workflow_result["steps"]["output_validation"] = output_validation
        
        if not output_validation.get("valid", False):
            workflow_result["status"] = "error"
            workflow_result["error_step"] = "output_validation"
            workflow_result["error_message"] = f"Invalid output files: {output_validation.get('issues', [])}"
            return workflow_result
            
        # Success!
        workflow_result["status"] = "success"
        workflow_result["files_generated"]["output_csv"] = f"{output_path}.csv"
        workflow_result["files_generated"]["output_mcf"] = f"{output_path}.mcf"
        workflow_result["files_generated"]["output_tmcf"] = f"{output_path}.tmcf"
        
        logging.info("Workflow completed successfully!")
        return workflow_result
        
    except Exception as e:
        logging.error(f"Workflow execution failed: {str(e)}")
        return {
            "status": "error",
            "error_step": "workflow_exception",
            "error_message": str(e),
            "input_file": input_file,
            "output_dir": output_dir
        }


def get_workflow_summary(result: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a summary of workflow execution.
    
    Args:
        result: Result from execute_workflow
        
    Returns:
        Dictionary with workflow summary
    """
    try:
        summary = {
            "status": result.get("status", "unknown"),
            "input_file": result.get("input_file", "unknown"),
            "total_steps": len(result.get("steps", {})),
            "files_generated": list(result.get("files_generated", {}).keys())
        }
        
        if result.get("status") == "error":
            summary["error_step"] = result.get("error_step", "unknown")
            summary["error_message"] = result.get("error_message", "Unknown error")
            
            # Add suggestions if available
            if "error_analysis" in result.get("steps", {}):
                error_analysis = result["steps"]["error_analysis"]
                summary["error_category"] = error_analysis.get("error_category")
                summary["suggestions"] = error_analysis.get("suggestions", [])
                
        elif result.get("status") == "success":
            # Add success metrics
            steps = result.get("steps", {})
            if "output_validation" in steps:
                validation = steps["output_validation"]
                summary["output_files"] = validation.get("files", {})
                
        return summary
        
    except Exception as e:
        logging.error(f"Summary generation failed: {str(e)}")
        return {"status": "error", "error_message": f"Summary generation failed: {str(e)}"}


# Coordinator Agent (only if ADK is available)  
if ADK_AVAILABLE:
    coordinator = LlmAgent(
        name="coordinator",
        model="gemini-2.0-flash",
        description="Coordinates complete PVMap generation workflow",
        instruction=(
            "Coordinate the complete Data Commons import workflow. "
            "Use execute_workflow to run all steps: analysis, PV mapping, metadata generation, and processor execution. "
            "Use get_workflow_summary to provide clear results summary. "
            "Handle errors gracefully and provide actionable feedback for failures."
        ),
        tools=[execute_workflow, get_workflow_summary]
    )
else:
    coordinator = None