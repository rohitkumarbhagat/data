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

import copy
import csv
import hashlib
import os
import platform
import random
import shutil
import subprocess
import sys
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from absl import app
from absl import flags
from absl import logging
from jinja2 import Environment, FileSystemLoader

_FLAGS = flags.FLAGS
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def _define_flags():
    try:
        flags.DEFINE_list('input_data', None,
                          'List of input data file paths (required)')
        flags.mark_flag_as_required('input_data')

        flags.DEFINE_list('input_metadata', [],
                          'List of input metadata file paths (optional)')

        flags.DEFINE_boolean(
            'sdmx_dataset', False,
            'Whether the dataset is in SDMX format (default: False)')

        flags.DEFINE_boolean('dry_run', False,
                             'Generate prompt only without calling Gemini CLI')

        flags.DEFINE_string('maps_api_key', None,
                            'Google Maps API key (optional)')

        flags.DEFINE_string('dc_api_key', None,
                            'Data Commons API key (optional)')

        flags.DEFINE_integer(
            'max_iterations', 10,
            'Maximum number of attempts for statvar processor.')

        flags.DEFINE_boolean(
            'skip_confirmation', False,
            'Skip user confirmation before starting PV map generation')

        flags.DEFINE_boolean(
            'enable_sandboxing',
            platform.system() == 'Darwin',
            'Enable sandboxing for Gemini CLI (default: True on macOS, False elsewhere)'
        )

        flags.DEFINE_string(
            'output_path', 'output/output',
            'Output path prefix for all generated files (default: output/output)'
        )

        flags.DEFINE_string(
            'gemini_cli', 'gemini',
            'Custom path or command to invoke Gemini CLI. '
            'Example: "/usr/local/bin/gemini". '
            'WARNING: This value is executed in a shell - use only with trusted input.'
        )

        flags.DEFINE_string(
            'working_dir', None,
            'Working directory for the generator (default: current directory)')

        flags.DEFINE_list(
            'reviewed_pv_map_files', [],
            'Optional reviewed PV map files to enforce as locked overrides. '
            'Entries may be "<path>" or "namespace:<path>".')

        flags.DEFINE_string(
            'feedback_report_path', None,
            'Optional output path for feedback report CSV. '
            'Defaults to .datacommons/runs/<run_id>/feedback_report.csv')

        flags.DEFINE_string(
            'mapping_instructions_file', None,
            'Optional markdown/text file with project-specific mapping '
            'instructions to embed in the Gemini prompt.')
    except flags.DuplicateFlagError:
        pass


@dataclass
class DataConfig:
    input_data: List[str]
    input_metadata: List[str]
    # JSON boolean values (true/false) are case-sensitive and auto-converted to Python bool
    is_sdmx_dataset: bool = False


@dataclass
class Config:
    data_config: DataConfig
    dry_run: bool = False
    maps_api_key: str = None
    dc_api_key: str = None
    max_iterations: int = 10
    skip_confirmation: bool = False
    enable_sandboxing: bool = False
    output_path: str = 'output/output'
    gemini_cli: Optional[str] = None
    working_dir: Optional[str] = None
    reviewed_pv_map_files: Optional[List[str]] = None
    feedback_report_path: Optional[str] = None
    mapping_instructions_file: Optional[str] = None


@dataclass
class GenerationResult:
    run_id: str
    run_dir: Path
    prompt_path: Path
    gemini_log_path: Path
    gemini_command: str
    sandbox_enabled: bool
    feedback_report_path: Optional[Path] = None


@dataclass(frozen=True)
class ReviewedPVMapFile:
    namespace: Optional[str]
    path: Path

    def cli_value(self) -> str:
        if self.namespace:
            return f'{self.namespace}:{self.path}'
        return str(self.path)


class PVMapGenerator:
    """Generator for PV maps from import configuration."""

    def __init__(self, config: Config):
        # Define working directory once for consistent path resolution
        self._working_dir = Path(
            config.working_dir).resolve() if config.working_dir else Path.cwd()
        if self._working_dir.exists() and not self._working_dir.is_dir():
            raise ValueError(
                f"working_dir is not a directory: {self._working_dir}")
        self._working_dir.mkdir(parents=True, exist_ok=True)

        # Copy config to avoid modifying the original
        self._config = copy.deepcopy(config)

        # Convert input_data paths to absolute
        if self._config.data_config.input_data:
            self._config.data_config.input_data = [
                self._validate_and_convert_path(path)
                for path in self._config.data_config.input_data
            ]

        # Convert input_metadata paths to absolute
        if self._config.data_config.input_metadata:
            self._config.data_config.input_metadata = [
                self._validate_and_convert_path(path)
                for path in self._config.data_config.input_metadata
            ]

        # Parse and validate reviewed PV map files.
        self._reviewed_pv_map_files = self._parse_reviewed_pv_map_files(
            self._config.reviewed_pv_map_files or [])
        self._config.reviewed_pv_map_files = [
            pv_map.cli_value() for pv_map in self._reviewed_pv_map_files
        ]

        # Parse and validate mapping instruction file if provided.
        self._mapping_instructions_path = self._parse_mapping_instructions_path(
            self._config.mapping_instructions_file)
        self._config.mapping_instructions_file = (
            str(self._mapping_instructions_path)
            if self._mapping_instructions_path else None)

        # Parse output_path into absolute path, handling relative paths and ~ expansion
        output_path_raw = self._config.output_path
        if not output_path_raw or not output_path_raw.strip():
            raise ValueError(
                "output_path must be a non-empty string in <dir>/<prefix> format"
            )
        output_path = Path(output_path_raw).expanduser()
        if len(output_path.parts) < 2:
            # Require a directory component so paths look like <dir>/<prefix>.
            raise ValueError("output_path must include a directory and prefix")
        if not output_path.is_absolute():
            output_path = self._working_dir / output_path
        self._output_path_abs = output_path.resolve()

        self._output_dir_abs = self._output_path_abs.parent
        self._output_basename = self._output_path_abs.name
        self._config.output_path = str(self._output_path_abs)

        # Create output directory if it doesn't exist
        self._output_dir_abs.mkdir(parents=True, exist_ok=True)

        self._datacommons_dir = self._initialize_datacommons_dir()

        # Generate gemini_run_id with timestamp and a random suffix to avoid collisions
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._gemini_run_id = (
            f"{self._output_basename}_gemini_{timestamp}_{random.randint(1, 10000)}"
        )

        # Create run directory structure
        self._run_dir = self._datacommons_dir / 'runs' / self._gemini_run_id
        self._run_dir.mkdir(parents=True, exist_ok=True)

        if self._config.feedback_report_path:
            feedback_report_path = self._validate_and_convert_path(
                self._config.feedback_report_path)
        else:
            feedback_report_path = self._run_dir / 'feedback_report.csv'
        feedback_report_path.parent.mkdir(parents=True, exist_ok=True)
        self._feedback_report_path = feedback_report_path
        self._config.feedback_report_path = str(self._feedback_report_path)

    def _validate_and_convert_path(self, path: str) -> Path:
        """Convert path to absolute and validate it's within working directory."""
        p = Path(path).expanduser()
        if not p.is_absolute():
            p = self._working_dir / p
        real_path = p.resolve()
        working_dir = self._working_dir.resolve()
        try:
            real_path.relative_to(working_dir)
        except ValueError:
            raise ValueError(
                f"Path '{path}' is outside working directory '{working_dir}'")
        return real_path

    def _parse_reviewed_pv_map_file(self, entry: str) -> ReviewedPVMapFile:
        entry = (entry or '').strip()
        if not entry:
            raise ValueError('reviewed PV map file entries cannot be empty')

        namespace = None
        path_string = entry
        if ':' in entry:
            namespace, path_string = entry.split(':', 1)
            if not namespace or not path_string:
                raise ValueError(
                    f"Invalid reviewed PV map entry '{entry}'. Expected "
                    "'<path>' or 'namespace:<path>'.")

        path = self._validate_and_convert_path(path_string)
        if not path.is_file():
            raise ValueError(f"Reviewed PV map file not found: {path}")
        return ReviewedPVMapFile(namespace=namespace, path=path)

    def _parse_reviewed_pv_map_files(
            self, entries: List[str]) -> List[ReviewedPVMapFile]:
        return [self._parse_reviewed_pv_map_file(entry) for entry in entries]

    def _parse_mapping_instructions_path(self, path: Optional[str]
                                        ) -> Optional[Path]:
        if not path:
            return None
        resolved_path = self._validate_and_convert_path(path)
        if not resolved_path.is_file():
            raise ValueError(
                f"Mapping instructions file not found: {resolved_path}")
        return resolved_path

    def _initialize_datacommons_dir(self) -> Path:
        """Initialize and return the .datacommons directory path."""
        dc_dir = self._working_dir / '.datacommons'
        dc_dir.mkdir(parents=True, exist_ok=True)
        return dc_dir

    def _get_user_confirmation(self, prompt_file: Path) -> bool:
        """Ask user for confirmation before starting PV map generation.
        
        Args:
            prompt_file: Path to the generated prompt file
            
        Returns:
            True if user confirms, False otherwise
        """
        print("\n" + "=" * 60)
        print("PV MAP GENERATION SUMMARY")
        print("=" * 60)
        print(f"Input data file: {self._config.data_config.input_data[0]}")
        print(
            f"Dataset type: {'SDMX' if self._config.data_config.is_sdmx_dataset else 'CSV'}"
        )
        print(f"Generated prompt: {prompt_file}")
        print(f"Working directory: {self._working_dir}")
        print(f"Output path: {self._config.output_path}")
        print(f"Output directory: {self._output_dir_abs}")
        print(f"Output basename: {self._output_basename}")
        if self._reviewed_pv_map_files:
            print("Reviewed PV map files (locked overrides):")
            for pv_map in self._reviewed_pv_map_files:
                print(f"  - {pv_map.cli_value()}")
        if self._mapping_instructions_path:
            print(
                "Project-specific mapping instructions: "
                f"{self._mapping_instructions_path}")
        print(f"Feedback report path: {self._feedback_report_path}")
        print(
            f"Sandboxing: {'Enabled' if self._config.enable_sandboxing else 'Disabled'}"
        )
        if not self._config.enable_sandboxing:
            print(
                "WARNING: Sandboxing is disabled. Gemini will run without safety restrictions."
            )
        print("=" * 60)

        while True:
            try:
                response = input("Ready to start PV map generation? (y/n): "
                                ).strip().lower()
                if response in ['y', 'yes']:
                    return True
                elif response in ['n', 'no']:
                    print("PV map generation cancelled by user.")
                    return False
                else:
                    print("Please enter 'y' or 'n'.")
            except KeyboardInterrupt:
                print("\nPV map generation cancelled by user.")
                return False

    def generate(self):
        """Generate PV map from import configuration."""
        # Set environment variables if API keys are provided in config
        if self._config.maps_api_key:
            os.environ['MAPS_API_KEY'] = self._config.maps_api_key
        if self._config.dc_api_key:
            os.environ['DC_API_KEY'] = self._config.dc_api_key

        if not self._config.data_config.input_data:
            raise ValueError(
                "Import configuration must have at least one input data entry")

        # Validate single CSV file input
        if len(self._config.data_config.input_data) != 1:
            raise ValueError(
                f"Currently only single CSV file is supported. "
                f"Found {len(self._config.data_config.input_data)} files in input_data."
            )

        # Generate the prompt as the first step
        prompt_file = self._generate_prompt()
        gemini_log_file = self._run_dir / 'gemini_cli.log'
        gemini_command = self._build_gemini_command(prompt_file,
                                                    gemini_log_file)

        result = GenerationResult(
            run_id=self._gemini_run_id,
            run_dir=self._run_dir,
            prompt_path=prompt_file,
            gemini_log_path=gemini_log_file,
            gemini_command=gemini_command,
            sandbox_enabled=self._config.enable_sandboxing,
            feedback_report_path=(self._feedback_report_path
                                  if self._reviewed_pv_map_files else None))

        # Check if we're in dry run mode
        if self._config.dry_run:
            logging.info(
                "Dry run mode: Prompt file generated at %s. "
                "Skipping generation execution.", prompt_file)
            return result

        # Get user confirmation before proceeding (unless skipped)
        if not self._config.skip_confirmation:
            if not self._get_user_confirmation(prompt_file):
                logging.info("PV map generation cancelled by user.")
                return result

        # Check if Gemini CLI is available (warning only for aliases)
        if not self._check_gemini_cli_available():
            logging.warning(
                "Gemini CLI not found in PATH. Will attempt to run anyway (may work if aliased)."
            )

        logging.info(
            f"Launching gemini (cwd: {self._working_dir}): {gemini_command} ")
        logging.info(f"Gemini output will be saved to: {gemini_log_file}")

        exit_code = self._run_subprocess(gemini_command)
        if exit_code == 0:
            self._generate_feedback_report()
            logging.info("Gemini CLI completed successfully")
            return result

        logging.error("Gemini CLI failed with exit code: %d", exit_code)
        raise RuntimeError(
            f"Gemini CLI execution failed with exit code {exit_code}")

    def _check_gemini_cli_available(self) -> bool:
        """Check if Gemini CLI is available in PATH or a custom command is provided."""
        # Skip check if custom command provided
        if self._config.gemini_cli:
            return True
        return shutil.which('gemini') is not None

    def _build_gemini_command(self, prompt_file: Path, log_file: Path) -> str:
        """Build the gemini CLI command with appropriate flags.
        
        Uses cat to pipe prompt file to gemini CLI with:
        - Optional --sandbox flag (enabled by default on macOS)
        - -y flag for automatic confirmation
        - stderr redirected to stdout (2>&1)
        - tee to output to both file and terminal
        
        Args:
            prompt_file: Path to the prompt file
            log_file: Path to the log file for gemini output
            
        Returns:
            Complete gemini command string
        """
        prompt_path = prompt_file.resolve()
        log_path = log_file.resolve()
        gemini_cmd = self._config.gemini_cli or 'gemini'
        sandbox_flag = "--sandbox" if self._config.enable_sandboxing else ""
        return (
            f"cat '{prompt_path}' | {gemini_cmd} {sandbox_flag} -y 2>&1 | tee '{log_path}'"
        )

    def _run_subprocess(self, command: str) -> int:
        """Run a subprocess command with real-time output streaming."""
        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # Combine stderr with stdout
                shell=True,  # Using shell to support pipe operations
                cwd=self._working_dir,  # Run in the specified working directory
                encoding='utf-8',
                errors='replace',
                bufsize=1,  # Line buffered
                universal_newlines=True)

            # Stream output in real-time
            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    print(output.rstrip())  # Print without extra newline

            # Wait for process to complete and get return code
            return_code = process.wait()
            return return_code

        except Exception as e:
            logging.error("Error running subprocess: %s", str(e))
            return 1

    def _generate_prompt(self) -> Path:
        """Generate prompt from Jinja2 template using import configuration.
        
        Returns:
            Path to the generated prompt file.
        """
        # Load and render the Jinja2 template
        template_dir = os.path.join(_SCRIPT_DIR, 'templates')

        env = Environment(loader=FileSystemLoader(template_dir))
        template = env.get_template('generate_pvmap_prompt.j2')

        # Calculate paths and prepare template variables
        working_dir = str(self._working_dir)  # Absolute working directory
        # Point to tools/ directory (parent of agentic_import)
        tools_dir = os.path.abspath(os.path.join(_SCRIPT_DIR, '..'))  # Absolute

        mapping_instructions_context = self._prepare_mapping_instructions_context(
        )
        reviewed_pv_map_context = self._prepare_reviewed_pv_map_context()

        template_vars = {
            'working_dir_abs':
                working_dir,
            'python_interpreter':
                sys.executable,
            'script_dir_abs':
                tools_dir,
            'input_data_abs':
                str(self._config.data_config.input_data[0])
                if self._config.data_config.input_data else "",
            'input_metadata_abs': [
                str(path) for path in self._config.data_config.input_metadata
            ] if self._config.data_config.input_metadata else [],
            'dataset_type':
                'sdmx' if self._config.data_config.is_sdmx_dataset else 'csv',
            'max_iterations':
                self._config.max_iterations,
            'gemini_run_id':
                self.
                _gemini_run_id,  # Pass the gemini run ID for backup tracking
            'output_path_abs':
                str(self._output_path_abs),  # Absolute path prefix for outputs
            'output_dir_abs':
                str(self._output_dir_abs),  # Directory for pvmap/metadata files
            'output_basename':
                self._output_basename,  # Base name for pvmap/metadata files
            'run_dir_abs':
                str(self._run_dir),
            'reviewed_pv_map_files':
                reviewed_pv_map_context,
            'reviewed_pv_map_files_csv':
                ','.join(
                    [item['cli_value'] for item in reviewed_pv_map_context]),
            'mapping_instructions_file_abs':
                mapping_instructions_context['source_path'],
            'mapping_instructions_text':
                mapping_instructions_context['content'],
            'mapping_instructions_sha256':
                mapping_instructions_context['sha256'],
            'mapping_instructions_snapshot_abs':
                mapping_instructions_context['snapshot_path'],
        }

        # Render template with these variables
        rendered_prompt = template.render(**template_vars)

        # Write rendered prompt to run directory
        output_file = self._run_dir / 'generate_pvmap_prompt.md'
        with open(output_file, 'w') as f:
            f.write(rendered_prompt)

        logging.info("Generated prompt written to: %s", output_file)
        return output_file

    def _prepare_reviewed_pv_map_context(self) -> List[dict]:
        """Collect reviewed PV map metadata and persist an artifact in run dir."""
        context: List[dict] = []
        if not self._reviewed_pv_map_files:
            return context

        manifest_path = self._run_dir / 'reviewed_pv_maps.csv'
        with open(manifest_path, 'w', newline='', encoding='utf-8') as output:
            writer = csv.writer(output)
            writer.writerow(['namespace', 'path', 'sha256', 'cli_value'])
            for reviewed_pv_map in self._reviewed_pv_map_files:
                checksum = self._sha256_file(reviewed_pv_map.path)
                cli_value = reviewed_pv_map.cli_value()
                namespace_value = reviewed_pv_map.namespace or ''
                writer.writerow(
                    [namespace_value,
                     str(reviewed_pv_map.path), checksum, cli_value])
                context.append({
                    'namespace': reviewed_pv_map.namespace,
                    'path': str(reviewed_pv_map.path),
                    'sha256': checksum,
                    'cli_value': cli_value,
                })
        return context

    def _prepare_mapping_instructions_context(self) -> dict:
        """Copy mapping instructions into run artifacts and return metadata."""
        if not self._mapping_instructions_path:
            return {
                'source_path': '',
                'content': '',
                'sha256': '',
                'snapshot_path': '',
            }

        content = self._mapping_instructions_path.read_text(encoding='utf-8')
        checksum = hashlib.sha256(content.encode('utf-8')).hexdigest()
        snapshot_path = self._run_dir / 'mapping_instructions.md'
        sha_path = self._run_dir / 'mapping_instructions.sha256'
        snapshot_path.write_text(content, encoding='utf-8')
        sha_path.write_text(f'{checksum}\n', encoding='utf-8')

        return {
            'source_path': str(self._mapping_instructions_path),
            'content': content,
            'sha256': checksum,
            'snapshot_path': str(snapshot_path),
        }

    def _parse_pv_map_rows(self, path: Path,
                           namespace: Optional[str]) -> List[dict]:
        """Parses PV map CSV rows into key/property/value entries."""
        rows: List[dict] = []
        if not path.is_file():
            return rows

        with open(path, newline='', encoding='utf-8') as csv_file:
            reader = csv.reader(csv_file)
            for row_number, row in enumerate(reader, start=1):
                if not row:
                    continue
                columns = [column.strip() for column in row]
                if not any(columns):
                    continue
                key = columns[0]
                if not key or key.startswith('#') or key.lower() == 'key':
                    continue
                for i in range(1, len(columns), 2):
                    if i + 1 >= len(columns):
                        continue
                    prop = columns[i]
                    value = columns[i + 1]
                    if not prop:
                        continue
                    rows.append({
                        'namespace': namespace,
                        'key': key,
                        'property': prop,
                        'value': value,
                        'source_file': str(path),
                        'row_number': row_number,
                    })
        return rows

    def _pvmap_lookup(self, rows: List[dict]) -> dict:
        """Builds a lookup map keyed by namespace/key/property."""
        lookup = {}
        for row in rows:
            lookup[(row['namespace'], row['key'], row['property'])] = row['value']
        return lookup

    def _generate_feedback_report(self) -> None:
        """Generates feedback report comparing generated and reviewed mappings."""
        if not self._reviewed_pv_map_files:
            return

        generated_pvmap_path = Path(f'{self._output_path_abs}_pvmap.csv')
        generated_rows = self._parse_pv_map_rows(generated_pvmap_path, None)
        generated_lookup = self._pvmap_lookup(generated_rows)

        reviewed_rows: List[dict] = []
        for reviewed_pv_map in self._reviewed_pv_map_files:
            reviewed_rows.extend(
                self._parse_pv_map_rows(reviewed_pv_map.path,
                                        reviewed_pv_map.namespace))

        effective_lookup = dict(generated_lookup)
        for row in reviewed_rows:
            effective_lookup[(row['namespace'], row['key'],
                              row['property'])] = row['value']

        self._feedback_report_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._feedback_report_path,
                  'w',
                  newline='',
                  encoding='utf-8') as csv_file:
            writer = csv.DictWriter(
                csv_file,
                fieldnames=[
                    'status',
                    'namespace',
                    'key',
                    'property',
                    'candidate_value',
                    'reviewed_value',
                    'effective_value',
                    'reviewed_map_file',
                    'row_number',
                ])
            writer.writeheader()
            for row in reviewed_rows:
                namespace = row['namespace']
                key = row['key']
                prop = row['property']
                reviewed_value = row['value']
                candidate_value = generated_lookup.get((None, key, prop))
                if candidate_value is None:
                    status = 'missing_in_candidate'
                    candidate_value = ''
                elif candidate_value == reviewed_value:
                    status = 'matched'
                else:
                    status = 'conflict'
                effective_value = effective_lookup.get((namespace, key, prop),
                                                       '')
                writer.writerow({
                    'status': status,
                    'namespace': namespace or 'GLOBAL',
                    'key': key,
                    'property': prop,
                    'candidate_value': candidate_value,
                    'reviewed_value': reviewed_value,
                    'effective_value': effective_value,
                    'reviewed_map_file': row['source_file'],
                    'row_number': row['row_number'],
                })

        logging.info("Feedback report written to: %s", self._feedback_report_path)

    def _sha256_file(self, path: Path) -> str:
        hasher = hashlib.sha256()
        with open(path, 'rb') as file_obj:
            while True:
                chunk = file_obj.read(1024 * 1024)
                if not chunk:
                    break
                hasher.update(chunk)
        return hasher.hexdigest()


def prepare_config() -> Config:
    """Prepare comprehensive configuration from individual flags."""
    data_config = DataConfig(input_data=_FLAGS.input_data or [],
                             input_metadata=_FLAGS.input_metadata or [],
                             is_sdmx_dataset=_FLAGS.sdmx_dataset)

    return Config(data_config=data_config,
                  dry_run=_FLAGS.dry_run,
                  maps_api_key=_FLAGS.maps_api_key,
                  dc_api_key=_FLAGS.dc_api_key,
                  max_iterations=_FLAGS.max_iterations,
                  skip_confirmation=_FLAGS.skip_confirmation,
                  enable_sandboxing=_FLAGS.enable_sandboxing,
                  output_path=_FLAGS.output_path,
                  gemini_cli=_FLAGS.gemini_cli,
                  working_dir=_FLAGS.working_dir,
                  reviewed_pv_map_files=_FLAGS.reviewed_pv_map_files,
                  feedback_report_path=_FLAGS.feedback_report_path,
                  mapping_instructions_file=_FLAGS.mapping_instructions_file)


def main(_):
    """Main function for PV Map generator."""
    config = prepare_config()
    logging.info("Loaded config with %d data files and %d metadata files",
                 len(config.data_config.input_data),
                 len(config.data_config.input_metadata))

    generator = PVMapGenerator(config)
    generator.generate()

    logging.info("PV Map generation completed.")
    return 0


if __name__ == '__main__':
    _define_flags()
    app.run(main)
