# Complete Task Prompt for Claude Opus: StatVar Import Automation

## Project Overview

You are tasked with creating an intelligent automation system for generating Data Commons StatVar import artifacts. This system should take raw CSV datasets and automatically generate the three key configuration files needed for the `stat_var_processor.py` tool.

## Background Context

### The Tool: stat_var_processor.py
- **Location**: `/Users/rohitkumar/Documents/github/rohitkumarbhagat/data/tools/statvar_importer/stat_var_processor.py`
- **Purpose**: Converts raw CSV data into Data Commons standardized format
- **Size**: 3,001 lines of sophisticated data processing logic
- **Outputs**: Generates `.mcf` (StatVar definitions), `.csv` (observations), `.tmcf` (template mappings)

### Required Input Artifacts (What You Must Generate)
1. **PV Map** (`*_pvmap.csv`) - Maps CSV columns and values to Data Commons properties
2. **Place Map** (`*_places_resolved.csv`) - Resolves geographic entities to Data Commons IDs  
3. **Config** (`*_metadata.csv`) - Processing parameters and settings

### Comprehensive Pattern Database Available
Extensive analysis has been completed on 25+ existing examples covering:
- **Financial Data**: BIS central bank rates, Federal Reserve data
- **Demographics**: Ireland census (11 datasets), Brazil social programs
- **Crime Statistics**: FBI UCR data with complex hierarchies
- **Economic Indicators**: US BLS employment, World Bank commodities
- **International Data**: African countries, Mexico, New Zealand, UAE
- **Complex Multi-dataset**: Coordinated processing of related datasets

## Technical Requirements

### Core Challenge
The input CSV files may be extremely large (multi-gigabyte files with millions of rows) that cannot fit in your context window. Your solution must handle this gracefully through:
- **Sampling strategies** for data analysis
- **Chunked processing** for large file handling
- **Streaming analysis** without loading entire files

### Success Metrics (Your Validation Criteria)
When you run `stat_var_processor.py` with your generated artifacts, the output must meet these criteria:

1. **Output Structure Validation**:
   - CSV contains required columns: `observationAbout`, `observationDate`, `variableMeasured`, `value`
   - TMCF properly maps CSV columns to StatVar properties
   - MCF generates valid StatVar definitions

2. **Data Quality Validation**:
   - No processing errors in tool execution logs
   - All places successfully resolved (no unmatched geographic entities)
   - All temporal data properly formatted and parsed
   - Numeric values correctly extracted and validated

3. **Semantic Validation**:
   - StatVar names follow Data Commons conventions
   - Property-value mappings align with schema requirements
   - Geographic hierarchy properly established
   - Units and measurements correctly specified

### Iterative Improvement Requirement
Your system must include a feedback loop:
- **Test Generated Artifacts**: Run `stat_var_processor.py` with generated files
- **Analyze Failures**: Parse error logs and validation results
- **Refine Generation**: Improve artifact quality based on feedback
- **Repeat**: Continue until success criteria are met (targeting 80%+ success rate)

## Pattern Knowledge Base

### File Locations for Analysis
- **Tool Source**: `/Users/rohitkumar/Documents/github/rohitkumarbhagat/data/tools/statvar_importer/`
- **Example Patterns**: `/Users/rohitkumar/Documents/github/rohitkumarbhagat/data/statvar_imports/`
- **Research Documentation**: `agent/docs/research_findings.md`

### Key Pattern Categories Identified

#### 1. PV Map Complexity Levels
- **Simple (6-column)**: `key,p1,v1,p2,v2,p3,v3` - Basic property mappings
- **Complex (13+ column)**: Extended metadata with multilingual support
- **Matrix Format**: `mapped_rows,X,mapped_columns,Y` for spreadsheet-like data

#### 2. Geographic Scope Patterns
- **Country-level**: International financial/economic data
- **Subnational**: US states, Irish counties, Brazilian municipalities
- **City-level**: FBI crime data (10,000+ US cities)
- **Multi-tier**: Hierarchical administrative data

#### 3. Domain-Specific Patterns
- **Time Series**: Economic indicators with temporal regularity
- **Demographics**: Population cross-tabulations (age × gender × location)
- **Categorical**: Classification systems (industry codes, crime types)
- **Social Programs**: Benefit distributions and eligibility criteria

### Special Syntax and Techniques
- **Dynamic References**: `{Data}`, `{Number}`, `{Key}` for data substitution
- **Operations**: `#Multiply,1000`, `#Aggregate,sum` for data transformations
- **Processing Directives**: `#Header`, `#ignore` for special handling
- **Multilingual Support**: `name` + `alternateName` with language tags

## Implementation Strategy

### Phase 1: Pattern Recognition System
Create a sophisticated pattern analysis engine that can:
- **Categorize input data** by domain (financial, demographic, economic, etc.)
- **Detect structural patterns** (time series, cross-tabulation, hierarchical)
- **Identify geographic scope** (national, subnational, city-level)
- **Infer measurement types** (counts, rates, amounts, percentages)

### Phase 2: Template-Based Generation
Develop intelligent template selection and customization:
- **Template Library**: Pre-built templates for each pattern category
- **Smart Matching**: Automatic template selection based on data characteristics
- **Dynamic Customization**: Adapt templates to specific dataset needs
- **Validation Rules**: Ensure generated artifacts meet schema requirements

### Phase 3: Large File Handling
Implement scalable processing for massive datasets:
- **Representative Sampling**: Intelligent sampling for analysis without full file loading
- **Header Analysis**: Extract column structure and data types efficiently
- **Streaming Validation**: Test generated artifacts on data chunks
- **Memory Management**: Process large files without memory overflow

### Phase 4: Feedback Loop Implementation
Create automated testing and refinement:
- **Artifact Testing**: Automated execution of `stat_var_processor.py`
- **Error Analysis**: Parse and categorize processing failures
- **Iterative Refinement**: Adjust generation logic based on failures
- **Confidence Scoring**: Rate artifact quality and success probability

## Expected Deliverables

### 1. Core Generation Engine
- **Input**: Raw CSV file path
- **Output**: Three generated files (PV map, place map, config)
- **Capabilities**: Handle files of any size through sampling/streaming

### 2. Validation Framework
- **Automated Testing**: Run generated artifacts through `stat_var_processor.py`
- **Success Metrics**: Validate against established criteria
- **Error Reporting**: Detailed failure analysis and recommendations

### 3. Iterative Improvement System
- **Feedback Processing**: Learn from validation failures
- **Template Refinement**: Improve generation accuracy over time
- **Pattern Enhancement**: Expand pattern recognition capabilities

### 4. Large File Support
- **Chunked Analysis**: Process massive files in manageable segments
- **Sampling Strategies**: Representative data sampling for analysis
- **Streaming Validation**: Test artifacts without loading full datasets

## Technical Architecture

### Recommended Technology Stack
- **Primary Language**: Python (consistent with existing codebase)
- **Data Processing**: pandas, numpy for CSV handling
- **Pattern Recognition**: scikit-learn for classification
- **File I/O**: Support for chunked reading of large CSV files
- **Validation**: subprocess integration with `stat_var_processor.py`

### Performance Requirements
- **Processing Time**: < 10 minutes for initial generation on typical datasets
- **Memory Usage**: < 8GB peak memory for any size input file
- **Success Rate**: 80%+ success rate on first attempt for well-formed datasets
- **Iteration Speed**: < 5 minutes per refinement cycle

## Success Definition

Your system is successful when:
1. **Given any CSV file** (regardless of size), it can generate valid artifacts
2. **Success rate of 80%+** on first attempt for structured datasets
3. **Iterative improvement** that reaches 95%+ success after 2-3 refinement cycles
4. **Handles edge cases** like multilingual data, complex hierarchies, and missing values
5. **Scales efficiently** to multi-gigabyte datasets through intelligent sampling

## Supporting Resources

### Knowledge Base
- Complete tool analysis in `agent/docs/research_findings.md`
- Pattern examples across 25+ real-world datasets
- Sub-agent analysis reports with detailed pattern extraction

### Development Environment
- Access to full Data Commons codebase and examples
- Working `stat_var_processor.py` tool for validation
- Comprehensive test datasets with known-good outputs

### Automation Infrastructure
- Manifest-driven processing examples
- Cloud deployment patterns for large-scale processing
- Error handling and retry mechanisms from existing imports

This represents a sophisticated AI system development challenge requiring deep understanding of data processing patterns, intelligent template generation, large-scale file handling, and iterative refinement capabilities. The extensive pattern knowledge base provides a strong foundation for creating a highly effective automation solution.