# ADK Migration Plan for PVMap Generator - Simplified & Incremental

## Executive Summary
This document outlines a **simplified, incremental migration plan** from the current Gemini CLI-based system to Google's ADK (Agent Development Kit). The implementation will be done in small, testable phases within the existing `/tools/agentic_import/` directory structure.

## Current System Context

### What We're Migrating From
- **Tool**: `/tools/agentic_import/pvmap_generator.py`
- **Purpose**: Converts input data (CSV/SDMX) to Data Commons format using statvar processor
- **Current Flow**: 
  1. Creates prompt from template (`generate_pvmap_prompt.j2`)
  2. Runs Gemini CLI with 25K+ token prompt
  3. Gemini autonomously executes workflow

### Key Problems to Solve
1. **Lack of Control**: Gemini CLI operates autonomously
2. **Monolithic Prompt**: 25K+ tokens, hard to debug
3. **Limited Visibility**: Can't monitor individual steps

## Implementation Location
All new code will be added to: **`/tools/agentic_import/agent/`**

This keeps the ADK implementation alongside the existing system, allowing parallel operation and gradual migration.

### Directory Structure (Simplified)
```
tools/agentic_import/
├── pvmap_generator.py         # Existing Gemini CLI version
├── templates/                  # Existing templates
├── agent/                      # NEW: ADK implementation
│   ├── __init__.py
│   ├── simple_agent.py         # Phase 1: Basic agent
│   ├── tools.py                # Shared tools
│   ├── pvmap_agent.py          # Phase 2: PVMap creation
│   ├── processor_agent.py      # Phase 3: Processor runner
│   └── main.py                 # Entry point
└── tests/                      # Tests for both versions
```

## Incremental Implementation Phases

---

## PHASE 1: Basic Setup & File Reading (Day 1-2)

### Goal
Set up ADK environment and create a simple agent that can read CSV files.

### Files to Create
1. `/tools/agentic_import/agent/__init__.py`
2. `/tools/agentic_import/agent/simple_agent.py`

### Implementation
```python
# agent/simple_agent.py
from google.adk.agents import LlmAgent
import pandas as pd

def read_csv_sample(file_path: str, rows: int = 20) -> dict:
    """Read first N rows of CSV"""
    try:
        df = pd.read_csv(file_path, nrows=rows)
        return {
            "status": "success",
            "columns": df.columns.tolist(),
            "sample": df.head(5).to_dict('records')
        }
    except Exception as e:
        return {"status": "error", "error_message": str(e)}

# Create simple agent
data_reader = LlmAgent(
    name="data_reader",
    model="gemini-2.0-flash",
    description="Reads and analyzes CSV files",
    instruction="Read the CSV file and describe its structure",
    tools=[read_csv_sample]
)
```

### Test
```bash
# Test with sample data
python -c "
from agent.simple_agent import data_reader
result = data_reader.run('Read testdata/sample.csv')
print(result)
"
```

### Success Criteria
- [ ] ADK installed and working
- [ ] Agent can read CSV files
- [ ] Returns structured data about the file

---

## PHASE 2: Data Analysis Agent (Day 3-4)

### Goal
Create an agent that analyzes data structure and identifies column types.

### Files to Create
1. `/tools/agentic_import/agent/analyzer.py`

### Implementation
```python
# agent/analyzer.py
from google.adk.agents import LlmAgent
from .simple_agent import read_csv_sample

analyzer = LlmAgent(
    name="data_analyzer",
    model="gemini-2.0-flash",
    description="Analyzes CSV data structure",
    instruction="""
    Analyze the CSV data and identify:
    1. Column types (numeric, date, text, categorical)
    2. Data patterns
    3. Potential Data Commons properties
    """,
    tools=[read_csv_sample]
)

# Test function
def analyze_file(file_path: str):
    result = analyzer.run(f"Analyze {file_path}")
    return result
```

### Success Criteria
- [ ] Identifies column types correctly
- [ ] Suggests potential DC properties
- [ ] Works with existing test data

---

## PHASE 3: PVMap Creator Agent (Day 5-7)

### Goal  
Create agent that generates pvmap.csv based on analysis.

### Files to Create
1. `/tools/agentic_import/agent/pvmap_creator.py`

### Implementation
```python
# agent/pvmap_creator.py
from google.adk.agents import LlmAgent
import csv

def write_pvmap(mappings: dict, output_path: str) -> dict:
    """Write PV mappings to CSV"""
    try:
        with open(output_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['input', 'property', 'value'])
            writer.writeheader()
            for input_str, pvs in mappings.items():
                for prop, val in pvs.items():
                    writer.writerow({
                        'input': input_str,
                        'property': prop,
                        'value': val
                    })
        return {"status": "success", "file": output_path}
    except Exception as e:
        return {"status": "error", "error_message": str(e)}

pvmap_creator = LlmAgent(
    name="pvmap_creator",
    model="gemini-2.0-flash",
    description="Creates PV mappings for Data Commons",
    instruction="""
    Create property-value mappings for Data Commons.
    Map column headers to populationType, measuredProperty, etc.
    Use Data Commons schema conventions.
    """,
    tools=[write_pvmap]
)
```

### Success Criteria
- [ ] Generates valid pvmap.csv
- [ ] Mappings follow DC conventions
- [ ] Compatible with statvar_processor

---

## PHASE 4: Processor Runner Agent (Day 8-10)

### Goal
Create agent that runs statvar_processor with generated configs.

### Files to Create
1. `/tools/agentic_import/agent/processor_runner.py`

### Implementation  
```python
# agent/processor_runner.py
from google.adk.agents import LlmAgent
import subprocess
import os

def run_processor(input_data: str, pvmap_path: str, metadata_path: str) -> dict:
    """Run statvar_processor"""
    cmd = [
        sys.executable,
        "../statvar_importer/stat_var_processor.py",
        f"--input_data={input_data}",
        f"--pv_map={pvmap_path}",
        f"--config_file={metadata_path}",
        "--output_path=output/output"
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    return {
        "status": "success" if result.returncode == 0 else "error",
        "exit_code": result.returncode,
        "stdout": result.stdout[:1000],  # Truncate for safety
        "stderr": result.stderr[:1000]
    }

processor_runner = LlmAgent(
    name="processor_runner",
    model="gemini-2.0-flash",
    description="Runs statvar processor",
    instruction="Execute the processor and handle results",
    tools=[run_processor]
)
```

### Success Criteria
- [ ] Successfully runs statvar_processor
- [ ] Handles errors gracefully
- [ ] Returns structured results

---

## PHASE 5: Simple Coordinator (Day 11-12)

### Goal
Create basic coordinator that chains agents together.

### Files to Create
1. `/tools/agentic_import/agent/coordinator.py`

### Implementation
```python
# agent/coordinator.py
from google.adk.agents import LlmAgent
from .analyzer import analyzer
from .pvmap_creator import pvmap_creator
from .processor_runner import processor_runner

coordinator = LlmAgent(
    name="coordinator",
    model="gemini-2.0-flash",
    description="Coordinates PVMap generation workflow",
    sub_agents=[analyzer, pvmap_creator, processor_runner],
    instruction="""
    Coordinate the workflow:
    1. Use analyzer to understand the data
    2. Use pvmap_creator to generate mappings
    3. Use processor_runner to execute
    """
)

def process_data(input_file: str):
    """Simple workflow execution"""
    result = coordinator.run(f"Process {input_file}")
    return result
```

### Success Criteria
- [ ] Chains agents in correct order
- [ ] Produces valid output files
- [ ] Works end-to-end on simple CSV

---

## PHASE 6: Add Iteration Logic (Day 13-15)

### Goal
Add retry logic for failed processing attempts.

### Files to Update
1. `/tools/agentic_import/agent/coordinator.py`

### Implementation
```python
# agent/coordinator.py (updated)
class IterativeCoordinator:
    def __init__(self, max_iterations=3):
        self.max_iterations = max_iterations
        self.coordinator = coordinator
        
    def process_with_retry(self, input_file: str):
        for attempt in range(1, self.max_iterations + 1):
            print(f"Attempt {attempt} of {self.max_iterations}")
            
            result = self.coordinator.run(f"Process {input_file}")
            
            if result.get('status') == 'success':
                print(f"✅ Success on attempt {attempt}")
                return result
                
            if attempt < self.max_iterations:
                print(f"❌ Attempt {attempt} failed, retrying...")
                # Analyze error and adjust
            else:
                print(f"⛔ Failed after {self.max_iterations} attempts")
                return result
```

### Success Criteria
- [ ] Retries on failure
- [ ] Stops after max_iterations
- [ ] Logs attempt numbers

---

## PHASE 7: Integration & Testing (Day 16-20)

### Goal
Integrate with existing pvmap_generator.py as alternative backend.

### Files to Create/Update
1. `/tools/agentic_import/agent/main.py`
2. `/tools/agentic_import/pvmap_generator.py` (add ADK option)

### Implementation
```python
# agent/main.py
from absl import app, flags
from .coordinator import IterativeCoordinator
import json

FLAGS = flags.FLAGS
flags.DEFINE_string('data_config', None, 'Path to config')
flags.DEFINE_integer('max_iterations', 10, 'Max attempts')

def main(argv):
    # Load config
    with open(FLAGS.data_config) as f:
        config = json.load(f)
    
    # Run coordinator
    coordinator = IterativeCoordinator(FLAGS.max_iterations)
    result = coordinator.process_with_retry(config['input_data'][0])
    
    return 0 if result['status'] == 'success' else 1

if __name__ == '__main__':
    app.run(main)
```

### Success Criteria  
- [ ] Can be called from command line
- [ ] Uses same config format as Gemini version
- [ ] Produces identical output files

---

## PHASE 8: Gradual Migration (Week 4+)

### Goal
Gradually migrate functionality and improve agents.

### Tasks
1. **Week 4**: Add metadata.csv generation
2. **Week 5**: Improve error analysis and recovery
3. **Week 6**: Add SDMX support
4. **Week 7**: Performance optimization
5. **Week 8**: Full feature parity

### Migration Strategy
- Run both systems in parallel
- Compare outputs
- Switch datasets one by one
- Monitor success rates

---

## Testing Strategy

### Unit Tests (Each Phase)
```python
# tests/test_phase1.py
def test_csv_reader():
    from agent.simple_agent import read_csv_sample
    result = read_csv_sample('testdata/sample.csv')
    assert result['status'] == 'success'
    assert 'columns' in result
```

### Integration Tests (Phase 5+)
```python
# tests/test_integration.py
def test_end_to_end():
    from agent.coordinator import process_data
    result = process_data('testdata/simple.csv')
    assert os.path.exists('output/output.csv')
```

### Comparison Tests (Phase 7+)
```python
# tests/test_comparison.py
def test_output_compatibility():
    # Run Gemini version
    gemini_output = run_gemini_version()
    
    # Run ADK version
    adk_output = run_adk_version()
    
    # Compare outputs
    assert_files_equivalent(gemini_output, adk_output)
```

---

## Key Principles

1. **Keep It Simple**: Start with minimal functionality
2. **Incremental Progress**: Each phase builds on previous
3. **Maintain Compatibility**: Same inputs/outputs as Gemini version
4. **Test Everything**: Unit test each component
5. **Parallel Operation**: Keep both systems running

## Success Metrics

- **Phase 1-2**: Basic functionality works
- **Phase 3-4**: Can generate valid configs
- **Phase 5-6**: End-to-end processing works
- **Phase 7-8**: Feature parity with Gemini version

## Risk Mitigation

- **Small Steps**: Each phase is 1-2 days
- **Rollback Plan**: Keep Gemini version as fallback
- **Continuous Testing**: Test after each phase
- **Early Validation**: Compare outputs frequently
```python
class PVMapCreator(LlmAgent):
    """Creates property-value mappings for Data Commons"""
    
    def __init__(self):
        super().__init__(
            name="pvmap_creator",
            model="gemini-2.0-flash",  # or gemini-pro for complex mappings
            description="Creates PV mappings for Data Commons",
            instruction=self._load_instruction(),
            tools=[
                lookup_dc_property,
                create_pv_mapping,
                validate_mapping,
                write_pvmap_csv
            ]
        )
```

**Key Responsibilities**:
- Map column headers to DC properties
- Handle special mappings (#Eval, #Filter, #Format, #Regex)
- Create constraint properties
- Generate proper StatVar structure

### 2.3 Metadata Generator Agent
```python
class MetadataGenerator(LlmAgent):
    """Generates processor configuration"""
    
    def __init__(self):
        super().__init__(
            name="metadata_generator",
            model="gemini-2.0-flash",
            description="Creates metadata.csv configuration",
            tools=[
                determine_header_rows,
                configure_date_formats,
                set_aggregation_rules,
                write_metadata_csv
            ]
        )
```

**Configuration Parameters to Generate**:
- header_rows, header_columns
- mapped_rows, mapped_columns
- date_format, observation_date_format
- aggregation settings
- place resolution settings

### 2.4 Processor Runner Agent
```python
class ProcessorRunner(LlmAgent):
    """Executes statvar_processor and handles results"""
    
    def __init__(self):
        super().__init__(
            name="processor_runner",
            model="gemini-2.0-flash",
            description="Runs statvar processor",
            tools=[
                run_statvar_processor,
                check_exit_code,
                parse_error_logs,
                validate_outputs
            ]
        )
```

### 2.5 Coordinator Agent
```python
class CoordinatorAgent(LlmAgent):
    """Orchestrates the entire workflow with iteration control"""
    
    def __init__(self, max_iterations=10):
        self.max_iterations = max_iterations
        super().__init__(
            name="coordinator",
            model="gemini-2.0-flash",
            description="Coordinates PVMap generation workflow",
            sub_agents=[
                DataAnalyzer(),
                PVMapCreator(),
                MetadataGenerator(),
                ProcessorRunner()
            ],
            instruction=self._load_instruction()
        )
```

## Phase 3: Tool Implementation Details

### 3.1 File Tools
```python
def read_csv_sample(file_path: str, rows: int = 20) -> dict:
    """Read first N rows of CSV"""
    try:
        df = pd.read_csv(file_path, nrows=rows)
        return {
            "status": "success",
            "columns": df.columns.tolist(),
            "sample_data": df.to_dict('records'),
            "shape": {"rows": len(df), "cols": len(df.columns)}
        }
    except Exception as e:
        return {"status": "error", "error_message": str(e)}

def write_pvmap(mappings: dict, output_path: str) -> dict:
    """Write PV mappings to CSV"""
    # Implementation details...
```

### 3.2 Validation Tools
```python
def validate_output_csv(file_path: str) -> dict:
    """Validate generated output.csv"""
    required_columns = [
        'observationAbout',
        'observationDate', 
        'variableMeasured',
        'value'
    ]
    # Check for required columns
    # Validate data types
    # Check for duplicates
    # Return validation report
```

### 3.3 Processor Tools
```python
def run_statvar_processor(config: dict) -> dict:
    """Execute statvar_processor.py with given configuration"""
    cmd = [
        config['python_interpreter'],
        config['processor_path'],
        f"--input_data={config['input_data']}",
        f"--pv_map={config['pv_map']}",
        f"--config_file={config['metadata']}",
        f"--output_path={config['output_path']}"
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    return {
        "status": "success" if result.returncode == 0 else "error",
        "exit_code": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "log_path": config.get('log_path')
    }
```

## Phase 4: Workflow Implementation

### 4.1 Main Workflow with Iteration Control
```python
from google.adk.agents.workflow import BaseWorkflow

class PVMapWorkflow(BaseWorkflow):
    """Main workflow with iteration control"""
    
    def __init__(self, config: dict):
        self.config = config
        self.max_iterations = config.get('max_iterations', 10)
        self.current_attempt = 0
        self.coordinator = CoordinatorAgent(self.max_iterations)
        
    def execute(self):
        """Execute workflow with retry logic"""
        while self.current_attempt < self.max_iterations:
            self.current_attempt += 1
            
            # Log attempt
            print(f"ATTEMPT {self.current_attempt} of {self.max_iterations}")
            
            # Run workflow
            result = self._run_single_iteration()
            
            if result['status'] == 'success':
                print(f"✅ SUCCESS on attempt {self.current_attempt}")
                self._backup_results()
                return result
            
            # Analyze failure
            if self.current_attempt < self.max_iterations:
                print(f"❌ Attempt {self.current_attempt} failed")
                self._analyze_and_fix_errors(result)
            else:
                print(f"⛔ FAILED after {self.max_iterations} attempts")
                return result
                
    def _run_single_iteration(self):
        """Single iteration of the workflow"""
        # 1. Analyze data
        analysis = self.coordinator.delegate_to_agent(
            "data_analyzer",
            f"Analyze {self.config['input_data']}"
        )
        
        # 2. Create PVMap
        pvmap = self.coordinator.delegate_to_agent(
            "pvmap_creator",
            f"Create mappings based on: {analysis}"
        )
        
        # 3. Generate metadata
        metadata = self.coordinator.delegate_to_agent(
            "metadata_generator",
            f"Generate config for: {analysis}"
        )
        
        # 4. Run processor
        result = self.coordinator.delegate_to_agent(
            "processor_runner",
            "Execute statvar processor"
        )
        
        # 5. Validate outputs
        if result['status'] == 'success':
            validation = self._validate_all_outputs()
            if not validation['passed']:
                result['status'] = 'validation_failed'
                result['errors'] = validation['errors']
                
        return result
```

### 4.2 Error Recovery Logic
```python
def _analyze_and_fix_errors(self, result: dict):
    """Analyze errors and fix mappings"""
    
    error_type = self._classify_error(result)
    
    if error_type == 'missing_property':
        # Add missing properties to pvmap
        self._fix_missing_properties(result['errors'])
        
    elif error_type == 'invalid_date_format':
        # Fix date formatting in metadata
        self._fix_date_formats(result['errors'])
        
    elif error_type == 'duplicate_observations':
        # Add aggregation rules
        self._fix_duplicates(result['errors'])
        
    # Log fixes applied
    print(f"Applied fixes for: {error_type}")
```

## Phase 5: Migration Execution Plan

### 5.1 Development Phases

**Phase A: Core Infrastructure (Week 1-2)**
- Set up ADK environment
- Create project structure
- Implement basic tools
- Set up logging and monitoring

**Phase B: Agent Development (Week 3-4)**
- Implement individual agents
- Create agent-specific prompts
- Test agents in isolation
- Integrate with tools

**Phase C: Workflow Integration (Week 5-6)**
- Implement workflow controller
- Add iteration logic
- Implement error recovery
- Test end-to-end flow

**Phase D: Validation & Testing (Week 7-8)**
- Test with production datasets
- Compare outputs with Gemini CLI version
- Performance benchmarking
- Documentation

### 5.2 Testing Strategy

**Unit Tests**:
```python
def test_data_analyzer():
    analyzer = DataAnalyzer()
    result = analyzer.analyze("test_data.csv")
    assert result['status'] == 'success'
    assert 'columns' in result

def test_pvmap_creator():
    creator = PVMapCreator()
    mappings = creator.create_mappings(sample_analysis)
    assert len(mappings) > 0
```

**Integration Tests**:
- Test complete workflow with sample datasets
- Verify iteration control
- Test error recovery mechanisms

**Validation Tests**:
- Compare outputs with Gemini CLI results
- Ensure backward compatibility
- Verify all file formats match

## Quick Reference

### Command to Run ADK Version
```bash
# From tools/agentic_import/ directory
python -m agent.main --data_config=config.json --max_iterations=10
```

### Directory Map
```
/tools/agentic_import/
├── agent/                    # ADK implementation
│   ├── simple_agent.py      # Phase 1
│   ├── analyzer.py          # Phase 2
│   ├── pvmap_creator.py     # Phase 3
│   ├── processor_runner.py  # Phase 4
│   ├── coordinator.py       # Phase 5-6
│   └── main.py             # Phase 7
├── pvmap_generator.py       # Original Gemini version
└── templates/               # Existing templates
```

### Phase Timeline
- **Phase 1-2**: Basic functionality (Days 1-4)
- **Phase 3-4**: Core processing (Days 5-10)
- **Phase 5-6**: Coordination & retry (Days 11-15)
- **Phase 7**: Integration (Days 16-20)
- **Phase 8**: Gradual migration (Week 4+)

## Resources

- **ADK Documentation**: https://google.github.io/adk-docs/
- **ADK GitHub**: https://github.com/google/adk-python
- **Data Commons**: https://datacommons.org/
- **Current Tool**: `/tools/agentic_import/pvmap_generator.py`
- **ADK Reference**: `/ADK_COMPREHENSIVE_GUIDE.md`
- **System Analysis**: `/ADK_MIGRATION_ANALYSIS.md`

---
Document Version: 2.0 (Simplified)
Last Updated: 2025-01-11
Approach: Incremental, Simple, Focused