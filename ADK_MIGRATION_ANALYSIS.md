# Current System Analysis: PVMap Generator with Gemini CLI

## System Architecture Overview

### Current Implementation Components

1. **pvmap_generator.py**: Main orchestrator script
   - Loads data configuration (input CSV/SDMX files)
   - Generates Jinja2-based prompt from template
   - Invokes Gemini CLI with generated prompt
   - Manages working directories and logging
   - Handles sandboxing and execution parameters

2. **generate_pvmap_prompt.j2**: Massive prompt template (25K+ tokens)
   - Contains detailed instructions for Data Commons mapping
   - Defines workflow with iteration control (max_iterations)
   - Includes comprehensive PV mapping rules
   - Specifies validation checklists
   - Enforces strict iteration limits

3. **run_statvar_processor.sh**: Execution wrapper
   - Runs the actual stat_var_processor.py
   - Manages logging separation
   - Handles backup operations
   - Returns appropriate exit codes

4. **backup_processor_run.py**: Backup utility
   - Archives successful/failed runs
   - Preserves pvmap.csv, metadata.csv, outputs

## Current Workflow

### Phase 1: Setup
1. User provides data_config.json with input files
2. PVMapGenerator validates paths and creates working directories
3. System generates timestamped run directory in .datacommons/runs/

### Phase 2: Prompt Generation
1. Template variables populated:
   - working_dir, python_interpreter, script_dir
   - input_data, input_metadata, dataset_type
   - max_iterations, gemini_run_id
2. Prompt rendered to markdown file (~25K tokens)

### Phase 3: Gemini CLI Execution
1. Gemini CLI launched with:
   - Optional sandboxing (--sandbox flag)
   - Auto-confirmation (-y flag)
   - Piped prompt input
   - Real-time output streaming
2. Gemini agent autonomously:
   - Analyzes input data/metadata
   - Creates pvmap.csv (property-value mappings)
   - Creates metadata.csv (processor configuration)
   - Runs statvar_processor iteratively
   - Validates outputs
   - Retries on failure (up to max_iterations)

### Phase 4: Iteration Loop (Inside Gemini)
The Gemini agent follows this logic:
```
FOR attempt = 1 TO max_iterations:
    - Create/modify pvmap.csv and metadata.csv
    - Run statvar_processor via run_statvar_processor.sh
    - Check exit code and validate output
    - IF success: STOP
    - ELIF attempt < max_iterations: Fix errors and retry
    - ELSE: Report failure and STOP
```

## Key Challenges with Current System

1. **Lack of Control**: Gemini CLI operates autonomously
   - Hard to interrupt or modify mid-execution
   - Limited visibility into decision-making
   - "Mind of its own" in YOLO/headless mode

2. **Prompt Size**: 25K+ token prompt is unwieldy
   - Difficult to debug
   - Context window limitations
   - Hard to maintain and update

3. **Error Recovery**: Limited programmatic error handling
   - Relies on Gemini's interpretation of errors
   - No structured error recovery mechanisms

4. **Monitoring**: Limited real-time monitoring capabilities
   - Output streamed but not structured
   - Hard to track iteration progress programmatically

5. **Testing**: Difficult to unit test components
   - Entire workflow runs as monolithic Gemini session
   - No modular testing of individual steps

## Data Flow

```
Input Files (CSV/SDMX)
    ↓
Data Config JSON
    ↓
PVMapGenerator
    ↓
Jinja2 Template → Prompt (25K tokens)
    ↓
Gemini CLI (Autonomous Loop)
    ├── Analyze Data
    ├── Create pvmap.csv
    ├── Create metadata.csv
    ├── Run statvar_processor (iterative)
    └── Validate & Retry
    ↓
Output Files
    ├── output.csv (observations)
    ├── output.tmcf (template)
    └── output_stat_vars.mcf (variables)
```

## Key Files Generated

1. **pvmap.csv**: Maps input strings to DC properties
   - Column headers → populationType, measuredProperty
   - Cell values → constraint properties
   - Special mappings (#Eval, #Filter, #Format)

2. **metadata.csv**: Processor configuration
   - header_rows, mapped_columns
   - date formats, aggregation rules
   - output specifications

3. **Output files**:
   - output.csv: Statistical observations
   - output.tmcf: Template mapping
   - output_stat_vars.mcf: Variable definitions

## Critical Success Factors for Migration

1. **Preserve Iteration Logic**: Max attempts control
2. **Maintain Validation**: All checklist items must pass
3. **Keep Error Recovery**: Analyze logs, fix mappings, retry
4. **Preserve File Structure**: Same inputs/outputs
5. **Maintain Compatibility**: Work with existing stat_var_processor

## Migration Opportunities with ADK

1. **Modular Agents**: Break monolithic prompt into specialized agents
2. **Structured Workflows**: Use ADK's workflow patterns
3. **Better Error Handling**: Programmatic error recovery
4. **Enhanced Monitoring**: Real-time agent state tracking
5. **Improved Testing**: Unit test individual agents
6. **Tool Integration**: Leverage ADK's tool ecosystem
7. **Multi-Model Support**: Use different models for different tasks