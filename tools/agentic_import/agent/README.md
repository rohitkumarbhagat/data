# ADK Implementation for PVMap Generator

This directory contains the ADK (Agent Development Kit) based implementation of the PVMap generator, migrating from the Gemini CLI approach to a more modular and controllable agent system.

## Overview

The ADK implementation provides a systematic approach to converting input data (CSV/SDMX) to Data Commons format using specialized agents instead of a monolithic Gemini CLI prompt.

### Migration Phases

- **Phase 1** (Current): Basic Setup & File Reading ✅
  - Simple CSV reading agent
  - Basic data analysis tools
  - Foundation for incremental migration

- **Phase 2** (Planned): Data Analysis Agent
  - Column type identification
  - Pattern recognition
  - Data Commons property suggestions

- **Phase 3+** (Future): Full workflow agents
  - PVMap creation
  - Metadata generation
  - Processor execution with iteration control

## Current Implementation (Phase 1)

### Files

- `simple_agent.py`: Basic agent with CSV reading capability
- `tools.py`: Shared utility functions (planned)
- `requirements.txt`: ADK-specific dependencies
- `README.md`: This documentation

### Features

- **CSV Reading**: Read and analyze CSV file structure
- **Error Handling**: Graceful handling of missing files/dependencies
- **Structured Output**: Consistent response format
- **Type Safety**: Optional type hints and validation

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

### Agent Usage (Requires ADK + API Key)

```python
from agent.simple_agent import data_reader

# Use agent for intelligent analysis
result = data_reader.run('Read and analyze testdata/sample.csv')
print(result)
```

## Testing

### Test Data

Use existing test files from the `testdata/` directory or create new ones for specific scenarios.

### Running Tests

```bash
# From tools/agentic_import directory
pytest tests/test_phase1.py -v
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
│   ├── simple_agent.py        # Phase 1 implementation
│   ├── tools.py               # Shared utilities (planned)
│   ├── README.md              # This file
│   └── requirements.txt       # Dependencies
├── testdata/                  # Test CSV files
└── tests/                     # Unit tests
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

## Future Phases

### Phase 2: Data Analysis
- Column type detection
- Pattern recognition
- Data Commons property suggestions

### Phase 3: PVMap Creation
- Property-value mapping generation
- Special mapping handling (#Eval, #Filter, #Format)
- Validation against DC schema

### Phase 4+: Full Migration
- Metadata generation
- Processor execution
- Iteration control and error recovery
- Complete replacement of Gemini CLI approach

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