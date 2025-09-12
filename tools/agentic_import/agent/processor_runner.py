from __future__ import annotations

import os
import sys
import subprocess
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


def run_statvar_processor(config: Dict[str, str]) -> Dict[str, Any]:
    """Execute statvar_processor.py with given configuration.
    
    Args:
        config: Dictionary with processor configuration
               Required keys: input_data, pv_map, metadata, output_path
               Optional keys: python_interpreter, working_dir
        
    Returns:
        Dictionary with execution results
    """
    try:
        # Validate required parameters
        required_keys = ["input_data", "pv_map", "metadata", "output_path"]
        for key in required_keys:
            if key not in config or not config[key]:
                return {"status": "error", "error_message": f"Missing required parameter: {key}"}
        
        # Set defaults
        python_interpreter = config.get("python_interpreter", sys.executable)
        working_dir = config.get("working_dir", os.getcwd())
        
        # Find processor script relative to current location
        # From agent/ go up to agentic_import/, then to tools/, then to statvar_importer/
        current_dir = Path(__file__).parent.parent  # Go up from agent/ to agentic_import/
        processor_path = current_dir.parent / "statvar_importer" / "stat_var_processor.py"
        
        if not processor_path.exists():
            return {
                "status": "error", 
                "error_message": f"Processor script not found at: {processor_path}"
            }
        
        # Create output directory
        output_dir = Path(config["output_path"]).parent
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Create .datacommons directory for logs
        datacommons_dir = Path(working_dir) / ".datacommons"
        datacommons_dir.mkdir(exist_ok=True)
        processor_log = datacommons_dir / "processor.log"
        
        # Build command
        cmd = [
            python_interpreter,
            str(processor_path),
            f"--input_data={config['input_data']}",
            f"--pv_map={config['pv_map']}",
            f"--config_file={config['metadata']}",
            f"--output_path={config['output_path']}"
        ]
        
        logging.info(f"Running processor: {' '.join(cmd)}")
        
        # Execute processor
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True,
            cwd=working_dir,
            timeout=300  # 5 minute timeout
        )
        
        # Write logs to persistent file (like existing script)
        with open(processor_log, 'w') as f:
            f.write(f"Command: {' '.join(cmd)}\n")
            f.write(f"Exit Code: {result.returncode}\n")
            f.write(f"STDOUT:\n{result.stdout}\n")
            f.write(f"STDERR:\n{result.stderr}\n")
        
        return {
            "status": "success" if result.returncode == 0 else "error",
            "exit_code": result.returncode,
            "stdout": result.stdout[:1000],  # Truncate for safety
            "stderr": result.stderr[:1000],
            "log_path": str(processor_log),
            "command": ' '.join(cmd)
        }
        
    except subprocess.TimeoutExpired:
        return {"status": "error", "error_message": "Processor execution timed out after 5 minutes"}
    except Exception as e:
        logging.error(f"Processor execution failed: {str(e)}")
        return {"status": "error", "error_message": str(e)}


def validate_processor_output(output_path: str) -> Dict[str, Any]:
    """Validate generated output files from statvar processor.
    
    Args:
        output_path: Base path for output files (without extension)
        
    Returns:
        Dictionary with validation results
    """
    try:
        expected_files = {
            "csv": f"{output_path}.csv",
            "mcf": f"{output_path}.mcf", 
            "tmcf": f"{output_path}.tmcf"
        }
        
        results = {"status": "success", "files": {}}
        issues = []
        
        for file_type, file_path in expected_files.items():
            if os.path.exists(file_path):
                file_size = os.path.getsize(file_path)
                results["files"][file_type] = {
                    "exists": True,
                    "path": file_path,
                    "size_bytes": file_size
                }
                
                # Basic validation
                if file_size == 0:
                    issues.append(f"{file_type.upper()} file is empty: {file_path}")
                    
            else:
                results["files"][file_type] = {"exists": False, "path": file_path}
                issues.append(f"Missing {file_type.upper()} file: {file_path}")
        
        # Validate CSV structure if it exists
        csv_path = expected_files["csv"]
        if os.path.exists(csv_path):
            try:
                import pandas as pd
                df = pd.read_csv(csv_path, nrows=5)  # Just check first few rows
                
                required_columns = ["observationAbout", "observationDate", "value", "variableMeasured"]
                missing_columns = [col for col in required_columns if col not in df.columns]
                
                if missing_columns:
                    issues.append(f"CSV missing required columns: {missing_columns}")
                else:
                    results["files"]["csv"]["row_count"] = len(pd.read_csv(csv_path))
                    results["files"]["csv"]["columns"] = df.columns.tolist()
                    
            except Exception as e:
                issues.append(f"CSV validation error: {str(e)}")
        
        results["valid"] = len(issues) == 0
        results["issues"] = issues
        
        return results
        
    except Exception as e:
        logging.error(f"Output validation failed: {str(e)}")
        return {"status": "error", "error_message": str(e)}


def parse_processor_errors(stderr: str, exit_code: int) -> Dict[str, Any]:
    """Parse and categorize processor error messages.
    
    Args:
        stderr: Standard error output from processor
        exit_code: Process exit code
        
    Returns:
        Dictionary with error analysis
    """
    try:
        if exit_code == 0:
            return {"status": "success", "error_category": None, "suggestions": []}
            
        error_analysis = {
            "status": "success",
            "error_category": "unknown",
            "suggestions": [],
            "stderr_lines": stderr.split('\n')[:10]  # First 10 lines
        }
        
        stderr_lower = stderr.lower()
        
        # Categorize common errors
        if "file not found" in stderr_lower or "no such file" in stderr_lower:
            error_analysis["error_category"] = "file_not_found"
            error_analysis["suggestions"].append("Check that input files exist and paths are correct")
            
        elif "permission denied" in stderr_lower:
            error_analysis["error_category"] = "permission_error"
            error_analysis["suggestions"].append("Check file permissions and directory access")
            
        elif "keyerror" in stderr_lower or "missing column" in stderr_lower:
            error_analysis["error_category"] = "missing_column"
            error_analysis["suggestions"].append("Check PVMap mappings match actual CSV columns")
            
        elif "valueerror" in stderr_lower or "invalid" in stderr_lower:
            error_analysis["error_category"] = "data_format_error"
            error_analysis["suggestions"].append("Check data format and metadata configuration")
            
        elif "memoryerror" in stderr_lower or "out of memory" in stderr_lower:
            error_analysis["error_category"] = "memory_error"
            error_analysis["suggestions"].append("Try processing smaller data chunks or increase memory")
            
        return error_analysis
        
    except Exception as e:
        logging.error(f"Error parsing failed: {str(e)}")
        return {"status": "error", "error_message": str(e)}


# Processor Runner Agent (only if ADK is available)
if ADK_AVAILABLE:
    processor_runner = LlmAgent(
        name="processor_runner",
        model="gemini-2.0-flash",
        description="Executes statvar_processor and handles results",
        instruction=(
            "Execute the Data Commons statvar processor and validate results. "
            "Use run_statvar_processor to execute the processor with configuration. "
            "Use validate_processor_output to check generated files. "
            "Use parse_processor_errors to analyze any execution errors. "
            "Report success/failure and provide actionable error information."
        ),
        tools=[run_statvar_processor, validate_processor_output, parse_processor_errors]
    )
else:
    processor_runner = None