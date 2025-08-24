# StatVar Import Automation Agent

## Overview

This agent system automates the generation of Data Commons StatVar import artifacts. Given a raw CSV dataset, it intelligently generates the three required configuration files needed for the `stat_var_processor.py` tool.

## What This Agent Does

### Input
- **Raw CSV file** (any size, including multi-gigabyte files)

### Output  
- **PV Map** (`*_pvmap.csv`) - Property-value mappings for Data Commons schema
- **Place Map** (`*_places_resolved.csv`) - Geographic entity resolution to DCIDs  
- **Config** (`*_metadata.csv`) - Processing parameters and settings

### Key Capabilities
- **Large File Handling**: Processes files of any size through intelligent sampling
- **Pattern Recognition**: Analyzes 25+ established patterns across multiple domains
- **Iterative Refinement**: Self-improves through validation feedback loops
- **Sub-Agent Architecture**: Distributed processing for scalability and specialization

## Project Structure

```
agent/
├── docs/                           # Documentation and knowledge base
│   ├── research_findings.md        # Comprehensive tool and pattern analysis
│   ├── knowledge_base_refresh.md   # Quick context rebuild protocol
│   ├── full_task_prompt.md        # Complete task specification for development
│   └── implementation_plan.md      # Detailed development roadmap
├── src/                           # Implementation code (to be developed)
│   ├── analyzers/                 # Data analysis sub-agents
│   ├── generators/                # Artifact generation sub-agents
│   └── validators/                # Validation and refinement sub-agents
└── README.md                      # This file
```

## Key Research Findings

### Pattern Categories Identified
- **Financial Data**: Central bank rates, exchange rates, economic indicators
- **Demographics**: Population statistics, census data, employment data  
- **Crime Statistics**: FBI UCR data with hierarchical crime classifications
- **Social Programs**: Benefit distributions, program eligibility
- **International Data**: Multi-country datasets with localization needs

### Complexity Levels
- **Simple (BIS-style)**: Basic 6-column PV maps for straightforward data
- **Complex (Brazil-style)**: Extended 13+ column maps with multilingual support
- **Multi-Dataset (Ireland-style)**: Coordinated processing of 11 related datasets

### Success Metrics
1. **Output Structure**: Correct CSV columns and TMCF mappings
2. **Processing Success**: No errors in `stat_var_processor.py` execution
3. **Place Resolution**: All geographic entities successfully resolved
4. **Schema Compliance**: Valid StatVar definitions meeting DC standards

## Documentation Guide

### For Quick Context Rebuilding
Read `docs/knowledge_base_refresh.md` - provides a structured 25-minute protocol to rebuild full understanding of the StatVar processor tool using sub-agent analysis.

### For Deep Understanding  
Read `docs/research_findings.md` - comprehensive analysis of the tool architecture and 25+ real-world patterns across multiple domains and complexity levels.

### For Development Planning
Read `docs/implementation_plan.md` - detailed 12-week development roadmap with sub-agent architecture, technical specifications, and risk mitigation strategies.

### For External Development
Use `docs/full_task_prompt.md` - complete task specification that can be provided to other Claude instances (like Claude Opus) for independent development.

## Sub-Agent Architecture

### Analysis Agents (5)
- **Structure Analyzer**: CSV structure, headers, data types
- **Content Analyzer**: Value patterns, quality assessment
- **Geographic Detector**: Place name detection and scope analysis  
- **Temporal Analyzer**: Date patterns, time series characteristics
- **Domain Classifier**: Data domain identification (economic, demographic, etc.)

### Pattern Matching Agents (6)
- **Simple Pattern Matcher**: Basic mapping patterns
- **Complex Pattern Matcher**: Extended mapping patterns
- **US Federal Matcher**: Government data patterns
- **International Matcher**: Multi-country patterns
- **Multi-Dataset Matcher**: Coordinated dataset patterns
- **Custom Pattern Generator**: Novel pattern creation

### Generation Agents (3)
- **PV Map Generator**: Property-value mapping creation
- **Place Map Generator**: Geographic entity resolution
- **Config Generator**: Metadata and processing parameters

### Validation Agents (4)
- **Syntax Validator**: File format validation
- **Semantic Validator**: Schema compliance checking
- **Tool Executor**: Run stat_var_processor.py validation
- **Error Analyzer**: Parse failures and suggest improvements

## Target Performance

### Success Rates
- **80%+ first-attempt success** for well-formed datasets
- **95%+ success within 3 refinement cycles**

### Performance Targets
- **< 10 minutes** initial generation time
- **< 8GB peak memory** usage regardless of input file size
- **< 5 minutes** per refinement cycle

### Scalability
- **Any file size** through intelligent sampling and streaming
- **Parallel processing** through sub-agent coordination
- **Iterative improvement** through automated feedback loops

## Current Status

**Phase**: Documentation and Research Complete
**Next**: Implementation Development (12-week roadmap available)

The comprehensive research phase has been completed with detailed analysis of the StatVar processor tool and extensive pattern extraction from 25+ real-world examples. The implementation plan provides a clear roadmap for building the automation system using advanced sub-agent architecture.

## Usage (Future)

Once implemented, the system will provide a simple interface:

```python
from agent.core import StatVarArtifactGenerator

generator = StatVarArtifactGenerator()
artifacts = generator.generate_artifacts("path/to/input.csv")

# Returns:
# {
#   "pv_map": "generated_pvmap.csv",
#   "place_map": "generated_places.csv", 
#   "config": "generated_metadata.csv",
#   "confidence_score": 0.87,
#   "validation_results": {...}
# }
```

## Contributing

This project uses a research-driven approach with extensive pattern analysis and sub-agent coordination. See the implementation plan for detailed development guidelines and architectural decisions.

## Related Resources

- **StatVar Processor Tool**: `/tools/statvar_importer/stat_var_processor.py`
- **Example Patterns**: `/statvar_imports/` (25+ real-world examples)
- **Data Commons Documentation**: https://docs.datacommons.org/