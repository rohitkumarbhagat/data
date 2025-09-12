# ADK Implementation for PVMap Generator

This directory contains the ADK (Agent Development Kit) based implementation of the PVMap generator, migrating from the Gemini CLI approach to a more modular and controllable agent system.

## Overview

The ADK implementation provides a systematic approach to converting input data (CSV/SDMX) to Data Commons format using specialized agents instead of a monolithic Gemini CLI prompt.

### Migration Phases

- **Phase 1** (Complete): Basic Setup & File Reading ✅
  - Simple CSV reading agent
  - Basic data analysis tools
  - Foundation for incremental migration

- **Phase 2** (Complete): Data Analysis Agent ✅
  - Column type identification (numeric, year, categorical, text)
  - Pattern recognition and data structure analysis
  - Data Commons property suggestions
  - Integration with Phase 1 components

- **Phase 3** (Complete): PVMap Creation Agent ✅
  - Property-value mapping generation
  - Special mapping handling (#Format, constraint properties)
  - Data Commons schema validation
  - CSV output generation

- **Phase 4** (Complete): Processor Runner & Basic Coordination ✅
  - Metadata configuration generation
  - Statvar processor execution with error handling
  - Output file validation
  - Complete end-to-end workflow coordination

- **Phase 5+** (Future): Advanced Features
  - Iteration control and retry logic
  - Advanced error analysis and automatic fixes
  - Complete replacement of Gemini CLI approach

## Current Implementation (Phases 1-4)

### Files

- `simple_agent.py`: Basic agent with CSV reading capability (Phase 1)
- `analyzer.py`: Data analysis agent with DC property mapping (Phase 2)
- `pvmap_creator.py`: Property-value mapping generation (Phase 3)
- `metadata_generator.py`: Processor configuration generation (Phase 4)
- `processor_runner.py`: Statvar processor execution (Phase 4)
- `coordinator.py`: End-to-end workflow orchestration (Phase 4)
- `main.py`: Command-line interface (Phase 4)
- `tools.py`: Shared utility functions for data analysis
- `tests/`: Comprehensive test suite (46 tests total)
- `requirements.txt`: ADK-specific dependencies
- `README.md`: This documentation

### Features

#### Core Data Processing
- **CSV Reading**: Read and analyze CSV file structure
- **Column Analysis**: Detect column types (numeric, year, categorical, text)
- **DC Property Mapping**: Suggest Data Commons properties for columns
- **Pattern Recognition**: Identify date formats and data patterns

#### PVMap Generation (Phase 3)
- **Property-Value Mappings**: Generate DC-compliant pvmap.csv files
- **Special Mappings**: Handle #Format transformations (YYYY, text_to_place)
- **Constraint Properties**: Map categorical columns to constraint properties
- **Schema Validation**: Validate mappings against DC requirements

#### Complete Workflow (Phase 4)
- **Metadata Generation**: Create processor configuration files
- **Processor Execution**: Run statvar_processor with error handling
- **Output Validation**: Verify generated CSV/MCF/TMCF files
- **End-to-End Coordination**: Complete workflow from CSV to DC format
- **Command-Line Interface**: Easy-to-use CLI with absl.flags

#### Quality & Reliability
- **Error Handling**: Graceful handling of missing files/dependencies
- **Structured Output**: Consistent response format across all components
- **Type Safety**: Comprehensive type hints and validation
- **Test Coverage**: 46+ passing tests across all phases

## Setup

### Prerequisites

Ensure you're using the project's Python environment (`.env` folder at project root).

### Installation

```bash
# From the tools/agentic_import/agent directory
pip install -r requirements.txt
```

### Authentication (for ADK agent usage)

Choose one authentication method:

```bash
# Option 1: Google AI Studio (Simplest)
export GOOGLE_API_KEY='your-api-key'

# Option 2: Vertex AI (Enterprise)
export GOOGLE_CLOUD_PROJECT='your-project-id'
# Requires gcloud auth or service account

# Option 3: LiteLLM (Multi-provider)
export ANTHROPIC_API_KEY='your-key'  # For Anthropic
export OPENAI_API_KEY='your-key'     # For OpenAI
```

## Usage

### Command-Line Interface (Phase 4 - Recommended)

```bash
# Complete end-to-end workflow
python -m agent.main --input_data=testdata/sample.csv --output_dir=output/

# With custom working directory
python -m agent.main --input_data=data.csv --output_dir=output/ --working_dir=temp/

# Verbose logging
python -m agent.main --input_data=data.csv --output_dir=output/ --verbose
```

Expected output:
```
=== ADK PVMap Generator ===
Phase 4 implementation using Agent Development Kit

✅ Workflow completed successfully!
Generated files: pvmap, metadata, output_csv, output_mcf, output_tmcf
Output file details:
  CSV: output/output.csv (2048 bytes)
  MCF: output/output.mcf (1024 bytes)
  TMCF: output/output.tmcf (512 bytes)
```

### Basic CSV Reading (Tool Function)

```python
from agent.simple_agent import read_csv_sample

# Read CSV without agent (tool function only)
result = read_csv_sample('path/to/data.csv', rows=20)
print(result)
```

### Data Analysis (Phase 2 Features)

```python
from agent.analyzer import analyze_column_types, suggest_dc_mappings

# Analyze column types and patterns
analysis = analyze_column_types('testdata/sample.csv', sample_rows=50)
print(analysis)

# Get Data Commons property suggestions
mappings = suggest_dc_mappings(analysis)
print(mappings)
```

Expected output:
```python
# Column Analysis
{
    'status': 'success',
    'column_analysis': {
        'Year': {'type': 'year', 'dc_suggestion': 'observationDate'},
        'Location': {'type': 'categorical', 'dc_suggestion': 'geoId'},
        'Population': {'type': 'numeric', 'dc_suggestion': 'measuredProperty'},
        'Education_Level': {'type': 'categorical', 'dc_suggestion': 'constraint'}
    }
}

# DC Mappings
{
    'status': 'success',
    'mappings': {
        'populationType': 'Person',
        'statType': 'measuredValue',
        'constraintProperties': ['Location', 'Education_Level'],
        'measuredProperties': ['Population', 'Employment_Rate', 'Median_Income']
    }
}
```

### Phase 4 Workflow Components

```python
from agent.coordinator import execute_workflow, get_workflow_summary

# Execute complete workflow programmatically
result = execute_workflow(
    input_file='testdata/sample.csv',
    output_dir='output/',
    working_dir='temp/'
)

# Get workflow summary
summary = get_workflow_summary(result)
print(f"Status: {summary['status']}")
print(f"Files generated: {summary['files_generated']}")
```

### Individual Component Usage

```python
# Phase 3: PVMap Generation
from agent.pvmap_creator import create_pv_mappings, write_pvmap_csv
from agent.analyzer import analyze_column_types

# Analyze data and create mappings
analysis = analyze_column_types('data.csv')
mappings = create_pv_mappings(analysis)
write_pvmap_csv(mappings['mappings'], 'pvmap.csv')

# Phase 4: Metadata Generation
from agent.metadata_generator import generate_metadata_config, write_metadata_csv

config_result = generate_metadata_config('data.csv', analysis)
write_metadata_csv(config_result['config'], 'metadata.csv')
```

### Agent Usage (Requires ADK + API Key)

```python
from agent.simple_agent import data_reader
from agent.analyzer import data_analyzer
from agent.coordinator import coordinator

# Use coordinated workflow via ADK agent
result = coordinator.run('Process testdata/sample.csv and generate DC import files')
print(result)
```

## Testing

### Test Data

Use existing test files from the `testdata/` directory or create new ones for specific scenarios.

### Running Tests

```bash
# From tools/agentic_import/agent directory (with .env activated)

# Individual component tests
python tests/test_agent.py              # Phase 1 tests (10 tests)
python tests/test_analyzer.py           # Phase 2 tests (12 tests)
python tests/test_metadata_generator.py # Phase 4 metadata tests (5 tests)
python tests/test_processor_runner.py   # Phase 4 processor tests (8 tests)
python tests/test_coordinator.py        # Phase 4 workflow tests (7 tests)

# End-to-end integration test
python test_end_to_end.py               # Complete workflow validation

# All tests with pytest (if available)
pytest tests/ -v                        # All 46+ tests
```

## Integration with Existing System

### Compatibility

- Uses same Python environment (`.env` folder)
- Follows absl logging conventions
- Compatible with existing file paths and data formats
- Parallel operation with existing Gemini CLI version

### File Structure

```
tools/agentic_import/
├── pvmap_generator.py         # Existing Gemini CLI version
├── agent/                      # NEW: ADK implementation (Phase 1-4 complete)
│   ├── simple_agent.py        # Phase 1: Basic CSV reading
│   ├── analyzer.py            # Phase 2: Data analysis & DC mapping
│   ├── pvmap_creator.py       # Phase 3: PV mapping generation
│   ├── metadata_generator.py  # Phase 4: Processor configuration
│   ├── processor_runner.py    # Phase 4: Statvar processor execution
│   ├── coordinator.py         # Phase 4: End-to-end workflow
│   ├── main.py                # Phase 4: CLI interface
│   ├── tools.py               # Shared utility functions
│   ├── tests/                 # Test suite (46+ tests)
│   │   ├── test_agent.py          # Phase 1 tests (10 tests)
│   │   ├── test_analyzer.py       # Phase 2 tests (12 tests)
│   │   ├── test_metadata_generator.py # Phase 4 tests (5 tests)
│   │   ├── test_processor_runner.py   # Phase 4 tests (8 tests)
│   │   └── test_coordinator.py    # Phase 4 tests (7 tests)
│   ├── testdata/              # Sample CSV for testing
│   ├── test_end_to_end.py     # Integration test
│   ├── README.md              # This file
│   └── requirements.txt       # Dependencies
├── testdata/                  # Additional test CSV files
└── templates/                 # Existing Jinja2 templates
```

## Error Handling

The implementation includes robust error handling:

- **Missing Dependencies**: Graceful degradation when pandas/ADK not installed
- **File Not Found**: Clear error messages for invalid paths
- **CSV Parsing Errors**: Detailed error information for malformed files
- **API Errors**: Proper handling of authentication/rate limit issues

## Logging

Follows project conventions:
- Uses `absl` logging for consistency with existing tools
- Structured log messages for debugging
- Error tracking for troubleshooting

## Development Guidelines

### Code Style

- Follow existing project patterns from `pvmap_generator.py`
- Use type hints for better code maintainability
- Include comprehensive error handling
- Return structured dictionary responses

### Testing

- Unit tests for all tool functions
- Integration tests for agent workflows
- Validation against existing system outputs

## Next Steps

### Phase 5: Iteration Control & Error Recovery (Next Priority)
- Add retry logic with configurable max_iterations
- Automatic error analysis and mapping fixes
- Enhanced error categorization and suggestions
- Intelligent recovery from processor failures

### Phase 6: Advanced Features (Future)
- SDMX format support (beyond CSV)
- Advanced date format detection and conversion
- Complex constraint property handling
- Integration with Data Commons API for validation

### Phase 7: Production Integration
- Performance optimization and memory management
- Full feature parity with existing Gemini CLI version
- Comprehensive benchmarking and validation
- Production deployment and gradual migration

### Phase 8: Migration Completion
- Complete replacement of Gemini CLI approach
- Legacy system deprecation
- Documentation and training materials
- Long-term maintenance and enhancement plan

## Migration Progress

- ✅ **Phase 1**: CSV reading and basic tools (COMPLETE)
- ✅ **Phase 2**: Data analysis and DC property mapping (COMPLETE)
- ✅ **Phase 3**: PVMap creation with DC mappings (COMPLETE)
- ✅ **Phase 4**: Processor execution & workflow coordination (COMPLETE)
- 🔄 **Phase 5**: Iteration control and error recovery (NEXT)
- ⏳ **Phase 6+**: Advanced features and production deployment

### Current Capabilities (Phase 4)

**✅ End-to-End Workflow:** Complete CSV-to-DC processing pipeline
**✅ Command-Line Tool:** Ready-to-use CLI with proper argument handling
**✅ Error Handling:** Comprehensive error detection and reporting
**✅ File Generation:** Creates all required DC import files (CSV, MCF, TMCF)
**✅ Validation:** Validates input data, mappings, and output files
**✅ Test Coverage:** 46+ tests ensuring reliability and correctness

## Troubleshooting

### Common Issues

1. **Import Error**: Ensure dependencies installed: `pip install -r requirements.txt`
2. **Authentication Error**: Set appropriate API keys (see Setup section) - only needed for ADK agents
3. **CSV Reading Error**: Check file path and format
4. **Processor Execution Error**: Verify statvar_processor.py is accessible
5. **Permission Error**: Ensure write access to output directories
6. **Path Resolution Error**: Run from correct directory (`tools/agentic_import/agent/`)

### Phase 4 Specific

- **Missing Output Files**: Check processor execution logs in `.datacommons/processor.log`
- **Invalid Mappings**: Review generated `pvmap.csv` for correct DC property names
- **Configuration Issues**: Validate `metadata.csv` parameters match your data structure

### Getting Help

- **Run End-to-End Test**: Execute `python test_end_to_end.py` to verify system health
- **Check System Logs**: Look in `.datacommons/` directory for processor logs
- **Compare with Gemini CLI**: Run both versions and compare generated files
- **Review ADK Documentation**: https://google.github.io/adk-docs/
- **Test Individual Components**: Run specific test files to isolate issues

## Resources

- **ADK Documentation**: https://google.github.io/adk-docs/
- **ADK GitHub**: https://github.com/google/adk-python
- **Data Commons**: https://datacommons.org/
- **Current Implementation**: `../pvmap_generator.py`