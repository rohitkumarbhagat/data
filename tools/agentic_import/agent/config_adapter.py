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

"""Configuration Adapter for pvmap_generator Compatibility

This module provides seamless compatibility between the existing pvmap_generator
configuration format and the new ADK-based agent system. It handles:

- Loading and validating data_config.json files
- Path resolution and security validation  
- Template variable preparation for backward compatibility
- Directory structure management (.datacommons/runs/*)
- Multi-file input support (both data and metadata)
- SDMX vs CSV dataset type handling

Key Features:
- 100% backward compatibility with existing configs
- Enhanced error handling and validation
- Support for relative and absolute paths
- Secure path validation (prevents directory traversal)
- Comprehensive logging and debugging support
- Template variable generation for Jinja2 compatibility

Usage:
    adapter = ConfigAdapter(data_config_path, working_dir)
    adk_config = adapter.to_adk_config()
    template_vars = adapter.get_template_variables()
    run_dir = adapter.get_run_directory()
"""

import os
import sys
import json
import copy
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field


@dataclass
class DataConfig:
    """Data configuration matching pvmap_generator format."""
    input_data: List[str]
    input_metadata: List[str] = field(default_factory=list)
    is_sdmx_dataset: bool = False


@dataclass
class LegacyConfig:
    """Complete configuration matching pvmap_generator."""
    data_config: DataConfig
    dry_run: bool = False
    maps_api_key: Optional[str] = None
    dc_api_key: Optional[str] = None
    max_iterations: int = 10
    skip_confirmation: bool = False
    enable_sandboxing: bool = False
    working_dir: str = ""
    run_id: str = ""


@dataclass 
class ADKConfig:
    """ADK agent system configuration."""
    input_file: str                    # Primary input CSV file
    output_dir: str                   # Output directory for results
    working_dir: str                  # Working directory for intermediate files
    input_metadata: List[str]         # List of metadata files
    dataset_type: str                 # 'csv' or 'sdmx'
    max_iterations: int               # Maximum retry attempts
    auto_fix: bool                    # Enable automatic error fixes
    python_interpreter: str           # Python executable path
    template_variables: Dict[str, Any] # Variables for template compatibility


class ConfigAdapterError(Exception):
    """Raised when configuration adaptation fails."""
    pass


class ConfigAdapter:
    """Adapts pvmap_generator configurations for ADK agent system."""
    
    def __init__(self, data_config_path: str, working_dir: Optional[str] = None, 
                 max_iterations: int = 10, auto_fix: bool = True):
        """Initialize configuration adapter.
        
        Args:
            data_config_path: Path to data_config.json file
            working_dir: Working directory (defaults to current directory)
            max_iterations: Maximum retry iterations for ADK system
            auto_fix: Enable automatic error correction
            
        Raises:
            ConfigAdapterError: If configuration loading or validation fails
        """
        self.data_config_path = os.path.abspath(data_config_path)
        self.working_dir = os.path.abspath(working_dir or os.getcwd())
        self.max_iterations = max_iterations
        self.auto_fix = auto_fix
        
        # Generate run ID with timestamp (matching pvmap_generator pattern)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.run_id = f"adk_{timestamp}"
        
        # Load and validate configuration
        self.legacy_config = self._load_and_validate_config()
        
        # Set up directory structure
        self.datacommons_dir = self._initialize_datacommons_dir()
        self.run_dir = self._initialize_run_dir()
        
        logging.info(f"ConfigAdapter initialized:")
        logging.info(f"  Data config: {self.data_config_path}")
        logging.info(f"  Working dir: {self.working_dir}")
        logging.info(f"  Run ID: {self.run_id}")
        logging.info(f"  Run dir: {self.run_dir}")

    def _load_and_validate_config(self) -> LegacyConfig:
        """Load and validate data configuration file.
        
        Returns:
            Validated LegacyConfig object
            
        Raises:
            ConfigAdapterError: If loading or validation fails
        """
        try:
            # Load JSON configuration
            if not os.path.exists(self.data_config_path):
                raise ConfigAdapterError(f"Config file not found: {self.data_config_path}")
                
            with open(self.data_config_path, 'r') as f:
                config_data = json.load(f)
                
            # Validate required fields
            if 'input_data' not in config_data:
                raise ConfigAdapterError("Missing required field: 'input_data'")
                
            if not config_data['input_data'] or not isinstance(config_data['input_data'], list):
                raise ConfigAdapterError("'input_data' must be a non-empty list")
                
            # Create DataConfig object
            data_config = DataConfig(
                input_data=config_data['input_data'],
                input_metadata=config_data.get('input_metadata', []),
                is_sdmx_dataset=config_data.get('is_sdmx_dataset', False)
            )
            
            # Validate and convert paths
            data_config.input_data = [
                self._validate_and_convert_path(path) for path in data_config.input_data
            ]
            
            if data_config.input_metadata:
                data_config.input_metadata = [
                    self._validate_and_convert_path(path) for path in data_config.input_metadata
                ]
            
            # Create complete legacy config
            legacy_config = LegacyConfig(
                data_config=data_config,
                max_iterations=self.max_iterations,
                working_dir=self.working_dir,
                run_id=self.run_id
            )
            
            logging.info(f"Loaded configuration:")
            logging.info(f"  Input data files: {len(data_config.input_data)}")
            logging.info(f"  Input metadata files: {len(data_config.input_metadata)}")
            logging.info(f"  Dataset type: {'SDMX' if data_config.is_sdmx_dataset else 'CSV'}")
            
            return legacy_config
            
        except json.JSONDecodeError as e:
            raise ConfigAdapterError(f"Invalid JSON in config file: {e}")
        except Exception as e:
            raise ConfigAdapterError(f"Failed to load configuration: {e}")

    def _validate_and_convert_path(self, path: str) -> str:
        """Validate and convert path to absolute, ensuring security.
        
        Args:
            path: Input path (relative or absolute)
            
        Returns:
            Validated absolute path
            
        Raises:
            ConfigAdapterError: If path is invalid or outside working directory
        """
        try:
            # Handle both relative and absolute paths
            if os.path.isabs(path):
                abs_path = os.path.abspath(path)
            else:
                # Relative paths are relative to the working directory
                abs_path = os.path.abspath(os.path.join(self.working_dir, path))
                
            # Security check: ensure path is within working directory
            real_path = os.path.realpath(abs_path)
            real_working_dir = os.path.realpath(self.working_dir)
            
            if not real_path.startswith(real_working_dir):
                raise ConfigAdapterError(
                    f"Path '{path}' resolves to '{real_path}' which is outside "
                    f"working directory '{real_working_dir}'"
                )
                
            # Check if file exists
            if not os.path.exists(real_path):
                logging.warning(f"Path does not exist (yet): {real_path}")
                
            return real_path
            
        except Exception as e:
            raise ConfigAdapterError(f"Invalid path '{path}': {e}")

    def _initialize_datacommons_dir(self) -> str:
        """Initialize .datacommons directory structure.
        
        Returns:
            Path to .datacommons directory
        """
        dc_dir = os.path.join(self.working_dir, '.datacommons')
        os.makedirs(dc_dir, exist_ok=True)
        
        # Also create runs subdirectory
        runs_dir = os.path.join(dc_dir, 'runs')
        os.makedirs(runs_dir, exist_ok=True)
        
        return dc_dir

    def _initialize_run_dir(self) -> str:
        """Initialize run-specific directory.
        
        Returns:
            Path to run directory
        """
        run_dir = os.path.join(self.datacommons_dir, 'runs', self.run_id)
        os.makedirs(run_dir, exist_ok=True)
        
        # Create subdirectories for organization
        for subdir in ['input', 'output', 'working', 'logs']:
            os.makedirs(os.path.join(run_dir, subdir), exist_ok=True)
            
        return run_dir

    def to_adk_config(self) -> ADKConfig:
        """Convert legacy configuration to ADK format.
        
        Returns:
            ADKConfig object ready for ADK agent system
        """
        data_config = self.legacy_config.data_config
        
        # Primary input file (first in list, as per pvmap_generator behavior)
        primary_input = data_config.input_data[0] if data_config.input_data else ""
        
        # Determine dataset type
        dataset_type = 'sdmx' if data_config.is_sdmx_dataset else 'csv'
        
        # Set up directories
        output_dir = os.path.join(self.run_dir, 'output')
        working_dir = os.path.join(self.run_dir, 'working')
        
        # Generate template variables for compatibility
        template_vars = self.get_template_variables()
        
        adk_config = ADKConfig(
            input_file=primary_input,
            output_dir=output_dir,
            working_dir=working_dir,
            input_metadata=data_config.input_metadata,
            dataset_type=dataset_type,
            max_iterations=self.max_iterations,
            auto_fix=self.auto_fix,
            python_interpreter=sys.executable,
            template_variables=template_vars
        )
        
        logging.info(f"Generated ADK configuration:")
        logging.info(f"  Input file: {primary_input}")
        logging.info(f"  Output dir: {output_dir}")
        logging.info(f"  Working dir: {working_dir}")
        logging.info(f"  Dataset type: {dataset_type}")
        logging.info(f"  Max iterations: {self.max_iterations}")
        
        return adk_config

    def get_template_variables(self) -> Dict[str, Any]:
        """Generate template variables for Jinja2 compatibility.
        
        Returns:
            Dictionary of template variables matching pvmap_generator format
        """
        data_config = self.legacy_config.data_config
        
        # Calculate tools directory (parent of agentic_import)
        script_dir = os.path.dirname(os.path.abspath(__file__))
        agentic_import_dir = os.path.dirname(script_dir)
        tools_dir = os.path.dirname(agentic_import_dir)
        
        template_vars = {
            'working_dir': self.working_dir,
            'python_interpreter': sys.executable,
            'script_dir': tools_dir,
            'input_data': data_config.input_data[0] if data_config.input_data else "",
            'input_metadata': data_config.input_metadata or [],
            'dataset_type': 'sdmx' if data_config.is_sdmx_dataset else 'csv',
            'max_iterations': self.legacy_config.max_iterations,
            'gemini_run_id': self.run_id,  # For backward compatibility
            'adk_run_id': self.run_id,     # ADK-specific identifier
            'run_dir': self.run_dir,       # ADK-specific run directory
        }
        
        return template_vars

    def get_run_directory(self) -> str:
        """Get the run-specific directory path.
        
        Returns:
            Path to run directory
        """
        return self.run_dir

    def get_output_directory(self) -> str:
        """Get the output directory path.
        
        Returns:
            Path to output directory
        """
        return os.path.join(self.run_dir, 'output')

    def get_working_directory(self) -> str:
        """Get the working directory path.
        
        Returns:
            Path to working directory for intermediate files
        """
        return os.path.join(self.run_dir, 'working')

    def get_input_files(self) -> List[str]:
        """Get list of all input data files.
        
        Returns:
            List of absolute paths to input data files
        """
        return copy.deepcopy(self.legacy_config.data_config.input_data)

    def get_metadata_files(self) -> List[str]:
        """Get list of all metadata files.
        
        Returns:
            List of absolute paths to metadata files
        """
        return copy.deepcopy(self.legacy_config.data_config.input_metadata)

    def is_sdmx_dataset(self) -> bool:
        """Check if this is an SDMX dataset.
        
        Returns:
            True if SDMX dataset, False if CSV
        """
        return self.legacy_config.data_config.is_sdmx_dataset

    def supports_multiple_files(self) -> bool:
        """Check if configuration has multiple input files.
        
        Returns:
            True if multiple input data files are specified
        """
        return len(self.legacy_config.data_config.input_data) > 1

    def save_run_metadata(self) -> str:
        """Save run metadata for debugging and tracking.
        
        Returns:
            Path to saved metadata file
        """
        metadata = {
            'run_id': self.run_id,
            'timestamp': datetime.now().isoformat(),
            'working_dir': self.working_dir,
            'data_config_path': self.data_config_path,
            'input_files': self.get_input_files(),
            'metadata_files': self.get_metadata_files(),
            'dataset_type': 'sdmx' if self.is_sdmx_dataset() else 'csv',
            'max_iterations': self.max_iterations,
            'auto_fix_enabled': self.auto_fix,
            'template_variables': self.get_template_variables()
        }
        
        metadata_file = os.path.join(self.run_dir, 'run_metadata.json')
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)
            
        logging.info(f"Run metadata saved to: {metadata_file}")
        return metadata_file

    def validate_input_files(self) -> Dict[str, Any]:
        """Validate that all input files exist and are readable.
        
        Returns:
            Validation results dictionary
        """
        results = {
            'valid': True,
            'errors': [],
            'warnings': [],
            'file_info': {}
        }
        
        # Check input data files
        for file_path in self.get_input_files():
            file_info = {'exists': False, 'readable': False, 'size_bytes': 0}
            
            if os.path.exists(file_path):
                file_info['exists'] = True
                try:
                    file_info['size_bytes'] = os.path.getsize(file_path)
                    # Test readability
                    with open(file_path, 'r') as f:
                        f.read(1)  # Read first byte
                    file_info['readable'] = True
                except Exception as e:
                    results['errors'].append(f"Cannot read input file {file_path}: {e}")
                    results['valid'] = False
            else:
                results['errors'].append(f"Input file does not exist: {file_path}")
                results['valid'] = False
                
            results['file_info'][file_path] = file_info
        
        # Check metadata files
        for file_path in self.get_metadata_files():
            if not os.path.exists(file_path):
                results['warnings'].append(f"Metadata file does not exist: {file_path}")
                
        return results


def load_config_from_file(data_config_path: str, **kwargs) -> ConfigAdapter:
    """Convenience function to load configuration from file.
    
    Args:
        data_config_path: Path to data_config.json file
        **kwargs: Additional arguments for ConfigAdapter
        
    Returns:
        Configured ConfigAdapter instance
        
    Raises:
        ConfigAdapterError: If loading fails
    """
    return ConfigAdapter(data_config_path, **kwargs)


def migrate_legacy_config(old_config_path: str, new_config_path: str) -> str:
    """Migrate old configuration format to current format.
    
    This function handles any future configuration format changes.
    
    Args:
        old_config_path: Path to old configuration file
        new_config_path: Path for new configuration file
        
    Returns:
        Path to migrated configuration file
        
    Raises:
        ConfigAdapterError: If migration fails
    """
    # For now, just copy the file as the format is stable
    # In future versions, this could handle format upgrades
    
    try:
        import shutil
        shutil.copy2(old_config_path, new_config_path)
        logging.info(f"Configuration migrated: {old_config_path} -> {new_config_path}")
        return new_config_path
    except Exception as e:
        raise ConfigAdapterError(f"Migration failed: {e}")