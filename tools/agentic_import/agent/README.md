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

- **Phase 3** (Next): PVMap Creation Agent
  - Property-value mapping generation
  - Special mapping handling (#Eval, #Filter, #Format)
  - Validation against DC schema

- **Phase 4+** (Future): Full workflow agents
  - Metadata generation
  - Processor execution with iteration control
  - Complete replacement of Gemini CLI approach

## Current Implementation (Phases 1-2)

### Files

- `simple_agent.py`: Basic agent with CSV reading capability (Phase 1)
- `analyzer.py`: Data analysis agent with DC property mapping (Phase 2)
- `tools.py`: Shared utility functions for data analysis
- `tests/`: Comprehensive test suite (22 tests)
- `requirements.txt`: ADK-specific dependencies
- `README.md`: This documentation

### Features

- **CSV Reading**: Read and analyze CSV file structure
- **Column Analysis**: Detect column types (numeric, year, categorical, text)
- **DC Property Mapping**: Suggest Data Commons properties for columns
- **Pattern Recognition**: Identify date formats and data patterns
- **Error Handling**: Graceful handling of missing files/dependencies
- **Structured Output**: Consistent response format
- **Type Safety**: Optional type hints and validation
- **Test Coverage**: 22 passing tests across both phases

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

### Basic CSV Reading (Tool Function)

```python
from agent.simple_agent import read_csv_sample

# Read CSV without agent (tool function only)
result = read_csv_sample('path/to/data.csv', rows=20)
print(result)
```

Expected output:
```python
{
    'status': 'success',
    'columns': ['col1', 'col2', 'col3'],
    'sample': [{'col1': 'val1', 'col2': 'val2'}, ...],
    'shape': {'rows': 20, 'cols': 3},
    'message': 'Read 5 sample rows from path/to/data.csv'
}
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

### Agent Usage (Requires ADK + API Key)

```python
from agent.simple_agent import data_reader
from agent.analyzer import data_analyzer

# Use Phase 1 agent for basic CSV reading
result = data_reader.run('Read and analyze testdata/sample.csv')

# Use Phase 2 agent for advanced analysis
analysis = data_analyzer.run('Analyze the structure and suggest DC mappings for testdata/sample.csv')
print(analysis)
```

## Testing

### Test Data

Use existing test files from the `testdata/` directory or create new ones for specific scenarios.

### Running Tests

```bash
# From tools/agentic_import directory (with .env activated)
pytest agent/tests/test_agent.py -v      # Phase 1 tests (10 tests)
pytest agent/tests/test_analyzer.py -v   # Phase 2 tests (12 tests)

# Run all tests
pytest agent/tests/ -v                   # All 22 tests
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
├── agent/                      # NEW: ADK implementation
│   ├── simple_agent.py        # Phase 1: Basic CSV reading
│   ├── analyzer.py            # Phase 2: Data analysis & DC mapping
│   ├── tools.py               # Shared utility functions
│   ├── tests/                 # Test suite (22 tests)
│   │   ├── test_agent.py      # Phase 1 tests (10 tests)
│   │   └── test_analyzer.py   # Phase 2 tests (12 tests)
│   ├── testdata/              # Sample CSV for testing
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

## Next Phase

### Phase 3: PVMap Creation Agent (Next)
- Property-value mapping generation based on Phase 2 analysis
- Special mapping handling (#Eval, #Filter, #Format, #Regex)
- Constraint property creation
- StatVar structure generation
- Validation against DC schema

### Phase 4+: Full Migration (Future)
- Metadata configuration generation
- Processor execution with structured error handling
- Iteration control and error recovery
- Complete replacement of Gemini CLI approach

## Migration Progress

- ✅ **Phase 1**: CSV reading and basic tools
- ✅ **Phase 2**: Data analysis and DC property mapping  
- 🔄 **Phase 3**: PVMap creation (next milestone)
- ⏳ **Phase 4+**: Full workflow integration

## Troubleshooting

### Common Issues

1. **Import Error**: Ensure ADK is installed: `pip install google-adk`
2. **Authentication Error**: Set appropriate API keys (see Setup section)
3. **CSV Reading Error**: Check file path and format
4. **Agent Not Working**: Verify API key and internet connection

### Getting Help

- Check existing system logs in `.datacommons/runs/`
- Compare with Gemini CLI version behavior
- Review ADK documentation: https://google.github.io/adk-docs/

## Resources

- **ADK Documentation**: https://google.github.io/adk-docs/
- **ADK GitHub**: https://github.com/google/adk-python
- **Data Commons**: https://datacommons.org/
- **Current Implementation**: `../pvmap_generator.py`