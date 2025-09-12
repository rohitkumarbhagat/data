"""
Shared utility functions for ADK-based PVMap generator.

This module provides common tools and utilities that can be used across
different agents in the PVMap generation workflow.
"""

from __future__ import annotations

import os
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List, Union

import pandas as pd
from absl import logging


def create_structured_response(
    status: str,
    data: Any = None,
    message: str = "",
    error_message: str = ""
) -> Dict[str, Any]:
    """
    Create a structured response dictionary following ADK conventions.
    
    Args:
        status: "success" or "error"
        data: Result data (optional)
        message: Success message
        error_message: Error details if status is "error"
    
    Returns:
        Structured response dictionary
    """
    response = {"status": status}
    
    if data is not None:
        response["data"] = data
        
    if status == "success" and message:
        response["message"] = message
    elif status == "error" and error_message:
        response["error_message"] = error_message
        
    return response


def validate_file_path(
    file_path: str,
    working_dir: Optional[str] = None,
    must_exist: bool = True
) -> Dict[str, Any]:
    """
    Validate and normalize a file path.
    
    Args:
        file_path: Path to validate
        working_dir: Optional working directory for security check
        must_exist: Whether file must exist
    
    Returns:
        Structured response with validated path or error
    """
    try:
        if not file_path:
            return create_structured_response(
                "error", error_message="File path cannot be empty"
            )
            
        # Convert to absolute path
        abs_path = os.path.abspath(file_path)
        
        # Security check: ensure path is within working directory
        if working_dir:
            real_path = os.path.realpath(abs_path)
            real_working_dir = os.path.realpath(working_dir)
            if not real_path.startswith(real_working_dir):
                return create_structured_response(
                    "error",
                    error_message=f"Path '{file_path}' is outside working directory"
                )
        
        # Check existence if required
        if must_exist and not os.path.exists(abs_path):
            return create_structured_response(
                "error", error_message=f"File not found: {abs_path}"
            )
            
        return create_structured_response(
            "success",
            data={"path": abs_path, "exists": os.path.exists(abs_path)},
            message=f"Path validated: {abs_path}"
        )
        
    except Exception as e:
        return create_structured_response(
            "error", error_message=f"Path validation error: {str(e)}"
        )


def ensure_directory(dir_path: str) -> Dict[str, Any]:
    """
    Ensure directory exists, creating if necessary.
    
    Args:
        dir_path: Directory path to create
    
    Returns:
        Structured response indicating success or failure
    """
    try:
        os.makedirs(dir_path, exist_ok=True)
        return create_structured_response(
            "success",
            data={"path": os.path.abspath(dir_path)},
            message=f"Directory ensured: {dir_path}"
        )
    except Exception as e:
        return create_structured_response(
            "error", error_message=f"Failed to create directory: {str(e)}"
        )


def generate_run_id(prefix: str = "adk") -> str:
    """
    Generate a timestamped run ID.
    
    Args:
        prefix: Prefix for the run ID
    
    Returns:
        Timestamped run ID string
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{timestamp}"


def load_json_config(config_path: str) -> Dict[str, Any]:
    """
    Load and validate JSON configuration file.
    
    Args:
        config_path: Path to JSON configuration file
    
    Returns:
        Structured response with loaded config or error
    """
    try:
        if not os.path.exists(config_path):
            return create_structured_response(
                "error", error_message=f"Config file not found: {config_path}"
            )
            
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
            
        return create_structured_response(
            "success",
            data=config,
            message=f"Configuration loaded from {config_path}"
        )
        
    except json.JSONDecodeError as e:
        return create_structured_response(
            "error", error_message=f"Invalid JSON in {config_path}: {str(e)}"
        )
    except Exception as e:
        return create_structured_response(
            "error", error_message=f"Failed to load config: {str(e)}"
        )


def detect_file_encoding(file_path: str) -> str:
    """
    Detect file encoding, with fallback to utf-8.
    
    Args:
        file_path: Path to file
    
    Returns:
        Detected encoding string
    """
    try:
        import chardet
        with open(file_path, 'rb') as f:
            raw_data = f.read(10000)  # Read first 10KB
            result = chardet.detect(raw_data)
            return result.get('encoding', 'utf-8') or 'utf-8'
    except ImportError:
        # Fallback if chardet not available
        return 'utf-8'
    except Exception:
        return 'utf-8'


def safe_file_read(file_path: str, encoding: Optional[str] = None) -> Dict[str, Any]:
    """
    Safely read text file with encoding detection.
    
    Args:
        file_path: Path to file
        encoding: Optional encoding (auto-detect if not provided)
    
    Returns:
        Structured response with file content or error
    """
    try:
        if not os.path.exists(file_path):
            return create_structured_response(
                "error", error_message=f"File not found: {file_path}"
            )
            
        if encoding is None:
            encoding = detect_file_encoding(file_path)
            
        with open(file_path, 'r', encoding=encoding) as f:
            content = f.read()
            
        return create_structured_response(
            "success",
            data={"content": content, "encoding": encoding},
            message=f"File read successfully: {file_path}"
        )
        
    except Exception as e:
        return create_structured_response(
            "error", error_message=f"Failed to read file: {str(e)}"
        )


def log_agent_action(agent_name: str, action: str, details: Optional[str] = None):
    """
    Log agent actions using absl logging format.
    
    Args:
        agent_name: Name of the agent performing action
        action: Description of the action
        details: Optional additional details
    """
    message = f"[{agent_name}] {action}"
    if details:
        message += f" - {details}"
    logging.info(message)


def validate_csv_structure(file_path: str, required_columns: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Validate CSV file structure and columns.
    
    Args:
        file_path: Path to CSV file
        required_columns: Optional list of required column names
    
    Returns:
        Structured response with validation results
    """
    try:
        # Read just the header to check structure
        df = pd.read_csv(file_path, nrows=0)
        columns = df.columns.tolist()
        
        validation_result = {
            "columns": columns,
            "column_count": len(columns),
            "valid": True,
            "issues": []
        }
        
        # Check for required columns
        if required_columns:
            missing_columns = [col for col in required_columns if col not in columns]
            if missing_columns:
                validation_result["valid"] = False
                validation_result["issues"].append(
                    f"Missing required columns: {missing_columns}"
                )
        
        # Check for duplicate columns
        duplicate_columns = [col for col in columns if columns.count(col) > 1]
        if duplicate_columns:
            validation_result["valid"] = False
            validation_result["issues"].append(
                f"Duplicate columns found: {duplicate_columns}"
            )
        
        # Check for empty column names
        empty_columns = [i for i, col in enumerate(columns) if not str(col).strip()]
        if empty_columns:
            validation_result["valid"] = False
            validation_result["issues"].append(
                f"Empty column names at positions: {empty_columns}"
            )
        
        return create_structured_response(
            "success",
            data=validation_result,
            message=f"CSV structure validated: {file_path}"
        )
        
    except Exception as e:
        return create_structured_response(
            "error", error_message=f"CSV validation failed: {str(e)}"
        )


# Utility functions for future phases
def format_error_for_retry(error_output: str, attempt: int, max_attempts: int) -> str:
    """
    Format error output for retry analysis.
    
    Args:
        error_output: Raw error output from processor
        attempt: Current attempt number
        max_attempts: Maximum attempts allowed
    
    Returns:
        Formatted error message for agent analysis
    """
    return f"""
ATTEMPT {attempt}/{max_attempts} FAILED

Error Output:
{error_output}

Please analyze this error and suggest fixes for the next attempt.
Focus on common issues like:
- Missing property mappings
- Invalid date formats
- Duplicate observations
- Incorrect constraint properties
"""


def extract_processor_errors(log_content: str) -> List[str]:
    """
    Extract specific error messages from processor log output.
    
    Args:
        log_content: Raw log content from processor
    
    Returns:
        List of extracted error messages
    """
    errors = []
    
    # Common error patterns to look for
    error_patterns = [
        "ERROR:",
        "FAILED:",
        "KeyError:",
        "ValueError:",
        "FileNotFoundError:",
        "Missing required",
        "Invalid format",
        "Duplicate observation"
    ]
    
    for line in log_content.split('\n'):
        for pattern in error_patterns:
            if pattern in line:
                errors.append(line.strip())
                break
    
    return errors