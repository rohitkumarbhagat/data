#!/usr/bin/env python3
"""
Extract statvar import configurations for VertexDB RAG application.

This script traverses the statvar_imports directory and extracts all relevant
file mappings, configurations, and metadata for each import.
"""

import os
import json
import glob
import re
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

class StatvarConfigExtractor:
    def __init__(self, base_path: str):
        self.base_path = Path(base_path)
        self.statvar_imports_path = self.base_path / "statvar_imports"
        self.configs = {}
        
    def extract_all_configs(self) -> Dict[str, Any]:
        """Extract configurations from all import directories."""
        print(f"Scanning statvar_imports directory: {self.statvar_imports_path}")
        
        # Get all subdirectories that could contain imports
        for provider_dir in self.statvar_imports_path.iterdir():
            if provider_dir.is_dir():
                print(f"\nProcessing provider: {provider_dir.name}")
                self._process_provider_directory(provider_dir)
        
        return {
            "extraction_timestamp": datetime.now().isoformat(),
            "total_imports": len(self.configs),
            "base_path": str(self.statvar_imports_path),
            "imports": self.configs
        }
    
    def _process_provider_directory(self, provider_dir: Path):
        """Process a provider directory that may contain one or more imports."""
        # Look for manifest.json files at various levels
        manifest_files = list(provider_dir.rglob("manifest.json"))
        
        if manifest_files:
            # Process directories with manifest files
            for manifest_file in manifest_files:
                import_dir = manifest_file.parent
                self._process_import_directory(import_dir, provider_dir)
        else:
            # Check if this directory itself contains import files (pvmap, metadata, etc.)
            if self._has_import_files(provider_dir):
                self._process_import_directory(provider_dir, provider_dir.parent)
            else:
                # Check subdirectories for import files
                for subdir in provider_dir.iterdir():
                    if subdir.is_dir() and self._has_import_files(subdir):
                        self._process_import_directory(subdir, provider_dir)
    
    def _has_import_files(self, directory: Path) -> bool:
        """Check if directory contains import-related files."""
        pvmap_files = list(directory.glob("*pvmap*.csv")) + list(directory.glob("*pv_map*.csv"))
        metadata_files = list(directory.glob("*metadata*.csv"))
        return len(pvmap_files) > 0 or len(metadata_files) > 0
    
    def _process_import_directory(self, import_dir: Path, provider_dir: Path):
        """Process a single import directory."""
        try:
            # Generate unique import ID
            relative_path = import_dir.relative_to(self.statvar_imports_path)
            import_id = str(relative_path).replace("/", "_").replace("\\", "_")
            
            print(f"  Processing import: {import_id}")
            
            # Initialize configuration
            config = {
                "import_id": import_id,
                "directory_path": str(relative_path),
                "provider": provider_dir.name,
                "files": {
                    "manifest": None,
                    "pvmap_files": [],
                    "metadata_files": [],
                    "places_resolved_files": [],
                    "test_inputs": [],
                    "test_outputs": {
                        "csv": [],
                        "tmcf": [],
                        "mcf": []
                    }
                },
                "import_configurations": [],
                "provenance": {}
            }
            
            # Process manifest.json if exists
            manifest_path = import_dir / "manifest.json"
            if manifest_path.exists():
                config = self._process_manifest(manifest_path, config)
            
            # Find all relevant files
            config = self._find_import_files(import_dir, config)
            
            # Process test data
            config = self._process_test_data(import_dir, config)
            
            # Store configuration
            self.configs[import_id] = config
            
        except Exception as e:
            print(f"    Error processing {import_dir}: {str(e)}")
    
    def _process_manifest(self, manifest_path: Path, config: Dict) -> Dict:
        """Process manifest.json file."""
        try:
            with open(manifest_path, 'r', encoding='utf-8') as f:
                manifest_data = json.load(f)
            
            config["files"]["manifest"] = str(manifest_path.relative_to(self.statvar_imports_path))
            
            # Extract import specifications
            if "import_specifications" in manifest_data:
                for spec in manifest_data["import_specifications"]:
                    config["import_name"] = spec.get("import_name", "")
                    config["provenance"]["url"] = spec.get("provenance_url", "")
                    config["provenance"]["description"] = spec.get("provenance_description", "")
                    config["cron_schedule"] = spec.get("cron_schedule", "")
                    
                    # Extract import inputs (expected outputs)
                    if "import_inputs" in spec:
                        config["import_configurations"] = spec["import_inputs"]
                    
                    # Extract scripts if available
                    if "scripts" in spec:
                        config["scripts"] = spec["scripts"]
                    
                    break  # Take first specification
            
        except Exception as e:
            print(f"    Error processing manifest {manifest_path}: {str(e)}")
        
        return config
    
    def _find_import_files(self, import_dir: Path, config: Dict) -> Dict:
        """Find all import-related files in the directory."""
        # Find pvmap files (including in subdirectories)
        pvmap_patterns = ["*pvmap*.csv", "*pv_map*.csv"]
        for pattern in pvmap_patterns:
            for pvmap_file in import_dir.rglob(pattern):
                rel_path = str(pvmap_file.relative_to(self.statvar_imports_path))
                if rel_path not in config["files"]["pvmap_files"]:
                    config["files"]["pvmap_files"].append(rel_path)
        
        # Find metadata files
        for metadata_file in import_dir.rglob("*metadata*.csv"):
            rel_path = str(metadata_file.relative_to(self.statvar_imports_path))
            if rel_path not in config["files"]["metadata_files"]:
                config["files"]["metadata_files"].append(rel_path)
        
        # Find places resolved files
        places_patterns = ["*places_resolved*.csv", "*place_map*.csv", "*places*.csv"]
        for pattern in places_patterns:
            for places_file in import_dir.rglob(pattern):
                # Exclude pvmap files that might match places pattern
                if "pvmap" not in places_file.name.lower() and "pv_map" not in places_file.name.lower():
                    rel_path = str(places_file.relative_to(self.statvar_imports_path))
                    if rel_path not in config["files"]["places_resolved_files"]:
                        config["files"]["places_resolved_files"].append(rel_path)
        
        return config
    
    def _process_test_data(self, import_dir: Path, config: Dict) -> Dict:
        """Process test data directories."""
        # Look for test data directories
        test_dirs = []
        for test_dir_name in ["test_data", "testdata"]:
            test_dir = import_dir / test_dir_name
            if test_dir.exists() and test_dir.is_dir():
                test_dirs.append(test_dir)
        
        # Also check for nested test directories
        for subdir in import_dir.rglob("test_data"):
            if subdir.is_dir():
                test_dirs.append(subdir)
        for subdir in import_dir.rglob("testdata"):
            if subdir.is_dir():
                test_dirs.append(subdir)
        
        # Process each test directory
        for test_dir in test_dirs:
            # Find input files (usually contain "input" in name or are in sample_input)
            for input_file in test_dir.rglob("*.csv"):
                # Check if it's clearly an output file first
                is_output = ("output" in input_file.name.lower() or 
                           "sample_output" in str(input_file.parent).lower())
                
                # Only consider as input if it's not an output and meets input criteria
                if (not is_output and 
                    ("input" in input_file.name.lower() or 
                     "sample_input" in str(input_file.parent).lower() or
                     not any(keyword in input_file.name.lower() for keyword in ["output", "stat_vars"]))):
                    rel_path = str(input_file.relative_to(self.statvar_imports_path))
                    if rel_path not in config["files"]["test_inputs"]:
                        config["files"]["test_inputs"].append(rel_path)
            
            # Find Excel input files
            for input_file in test_dir.rglob("*.xlsx"):
                rel_path = str(input_file.relative_to(self.statvar_imports_path))
                if rel_path not in config["files"]["test_inputs"]:
                    config["files"]["test_inputs"].append(rel_path)
            for input_file in test_dir.rglob("*.xls"):
                rel_path = str(input_file.relative_to(self.statvar_imports_path))
                if rel_path not in config["files"]["test_inputs"]:
                    config["files"]["test_inputs"].append(rel_path)
            
            # Find output files
            for output_file in test_dir.rglob("*.csv"):
                if ("output" in output_file.name.lower() or 
                    "sample_output" in str(output_file.parent).lower()) and "input" not in output_file.name.lower():
                    rel_path = str(output_file.relative_to(self.statvar_imports_path))
                    if rel_path not in config["files"]["test_outputs"]["csv"]:
                        config["files"]["test_outputs"]["csv"].append(rel_path)
            
            # Find TMCF files
            for tmcf_file in test_dir.rglob("*.tmcf"):
                rel_path = str(tmcf_file.relative_to(self.statvar_imports_path))
                if rel_path not in config["files"]["test_outputs"]["tmcf"]:
                    config["files"]["test_outputs"]["tmcf"].append(rel_path)
            
            # Find MCF files
            for mcf_file in test_dir.rglob("*.mcf"):
                rel_path = str(mcf_file.relative_to(self.statvar_imports_path))
                if rel_path not in config["files"]["test_outputs"]["mcf"]:
                    config["files"]["test_outputs"]["mcf"].append(rel_path)
        
        return config
    
    def save_to_file(self, output_file: str):
        """Save extracted configurations to JSON file."""
        config_data = self.extract_all_configs()
        
        output_path = self.base_path / output_file
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=2, ensure_ascii=False)
        
        print(f"\nConfiguration saved to: {output_path}")
        print(f"Total imports extracted: {config_data['total_imports']}")
        
        # Print summary statistics
        self._print_summary(config_data)
    
    def _print_summary(self, config_data: Dict):
        """Print summary statistics."""
        print(f"\n{'='*50}")
        print("EXTRACTION SUMMARY")
        print(f"{'='*50}")
        
        total_pvmaps = sum(len(imp["files"]["pvmap_files"]) for imp in config_data["imports"].values())
        total_metadata = sum(len(imp["files"]["metadata_files"]) for imp in config_data["imports"].values())
        total_places = sum(len(imp["files"]["places_resolved_files"]) for imp in config_data["imports"].values())
        total_test_inputs = sum(len(imp["files"]["test_inputs"]) for imp in config_data["imports"].values())
        total_test_outputs = sum(
            len(imp["files"]["test_outputs"]["csv"]) + 
            len(imp["files"]["test_outputs"]["tmcf"]) + 
            len(imp["files"]["test_outputs"]["mcf"])
            for imp in config_data["imports"].values()
        )
        
        print(f"Total Imports: {config_data['total_imports']}")
        print(f"Total PV Map Files: {total_pvmaps}")
        print(f"Total Metadata Files: {total_metadata}")
        print(f"Total Places Resolved Files: {total_places}")
        print(f"Total Test Input Files: {total_test_inputs}")
        print(f"Total Test Output Files: {total_test_outputs}")
        
        # List providers
        providers = set(imp.get("provider", "unknown") for imp in config_data["imports"].values())
        print(f"\nProviders: {', '.join(sorted(providers))}")


def main():
    """Main execution function."""
    # Get the current directory (should be the data repository root)
    current_dir = os.getcwd()
    print(f"Starting extraction from: {current_dir}")
    
    # Initialize extractor
    extractor = StatvarConfigExtractor(current_dir)
    
    # Extract and save configurations
    extractor.save_to_file("statvar_imports_config.json")
    
    print("\nExtraction completed successfully!")


if __name__ == "__main__":
    main()