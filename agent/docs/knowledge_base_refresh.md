# Knowledge Base Refresh Protocol for StatVar Processor Expert

## Quick Context Rebuild Prompt

When you need to rapidly rebuild deep understanding of the Data Commons StatVar Processor tool, use this structured approach:

### Phase 1: Core Tool Understanding (5 minutes)
```
Read and analyze the main tool:
- /Users/rohitkumar/Documents/github/rohitkumarbhagat/data/tools/statvar_importer/stat_var_processor.py

Focus on:
1. Command-line interface and main() function
2. StatVarsMap class architecture
3. PropertyValueMapper integration
4. Input/output file processing flow
5. Core processing pipeline (lines 2800-3000)
```

### Phase 2: Configuration System Analysis (3 minutes)
```
Read configuration framework:
- /Users/rohitkumar/Documents/github/rohitkumarbhagat/data/tools/statvar_importer/config_flags.py
- /Users/rohitkumar/Documents/github/rohitkumarbhagat/data/tools/statvar_importer/property_value_mapper.py

Focus on:
1. Flag definitions and parameter handling
2. PV map loading and processing logic
3. Configuration validation patterns
```

### Phase 3: Pattern Examples Deep Dive (10 minutes)

Deploy these sub-agent analysis tasks in parallel:

#### Sub-Agent 1: Simple Pattern Analysis
```
Analyze these simple examples for baseline patterns:
- /Users/rohitkumar/Documents/github/rohitkumarbhagat/data/statvar_imports/bis/bis_central_bank_policy_rate/
  
Extract:
- Basic PV map structure (6-column format)
- Simple place resolution patterns
- Minimal metadata configuration
- Input/output transformation example
```

#### Sub-Agent 2: Complex Pattern Analysis  
```
Analyze these complex examples for advanced patterns:
- /Users/rohitkumar/Documents/github/rohitkumarbhagat/data/statvar_imports/brazil_visdata/FoodBasketDistribution/
- /Users/rohitkumar/Documents/github/rohitkumarbhagat/data/statvar_imports/ireland_census/

Extract:
- Extended PV map formats (13+ columns)
- Multi-dataset coordination patterns
- Multilingual support mechanisms
- Complex preprocessing workflows
```

#### Sub-Agent 3: US Federal Data Patterns
```
Analyze US-specific patterns:
- /Users/rohitkumar/Documents/github/rohitkumarbhagat/data/statvar_imports/us_bls/bls_ces/
- /Users/rohitkumar/Documents/github/rohitkumarbhagat/data/statvar_imports/fbi/fbigovcrime/

Extract:
- NAICS industry classification patterns
- Seasonal adjustment handling
- Economic time series processing
- Federal data source integration
```

### Phase 4: Success Criteria and Validation (5 minutes)
```
Examine successful outputs to understand quality metrics:

Read these output examples:
- Any test_data/*_output.csv files
- Any test_data/*_output.tmcf files  
- Any manifest.json files

Extract:
1. Required output CSV column structure
2. TMCF template mapping patterns
3. StatVar DCID generation rules
4. Processing success indicators
```

## Rapid Knowledge Validation Checklist

After completing the refresh, verify understanding with these questions:

### Tool Architecture
- [ ] Can you explain the 3 output files generated (.mcf, .csv, .tmcf)?
- [ ] Do you understand the PropertyValueMapper class functionality?
- [ ] Can you describe the place resolution mechanism?

### Input Requirements  
- [ ] Can you list the 3 mandatory input file types?
- [ ] Do you understand PV map syntax ({Data}, {Number}, #Multiply)?
- [ ] Can you explain the difference between simple vs complex PV map formats?

### Processing Patterns
- [ ] Can you identify 5+ example pattern categories (financial, demographic, crime, etc.)?
- [ ] Do you understand multilingual support mechanisms?
- [ ] Can you explain temporal data handling patterns?

### Success Criteria
- [ ] Can you list 5 key success validation metrics?
- [ ] Do you understand common failure modes?
- [ ] Can you identify automation opportunities?

## Common Concepts Quick Reference

### Key Terminology
- **StatVar**: Statistical Variable - a measurable property of a population
- **DCID**: Data Commons Identifier - unique ID for entities
- **PV Map**: Property-Value mapping file
- **TMCF**: Template MCF - maps CSV columns to StatVar properties
- **MCF**: Meta Content Framework - Data Commons schema format

### Essential File Patterns
- `*_pvmap.csv` or `*_pv_map.csv` - Property-value mappings
- `*_places_resolved*.csv` - Geographic entity resolution
- `*_metadata.csv` - Configuration parameters
- `manifest.json` - Import automation definition

### Critical Command Pattern
```bash
python3 stat_var_processor.py \
  --input_data=<source-csv> \
  --pv_map=<mapping-file> \
  --config_file=<metadata> \
  --places_resolved_csv=<places> \
  --output_path=<output-prefix>
```

### StatVar Naming Pattern
`[Qualifier_]MeasuredProperty_PopulationType[_Constraints]`

Examples:
- `Monthly_InterestRate_FinancialInstrument_CountryCentralBankPolicyRate`
- `Count_Person_Male_Age0To14Years`
- `Amount_Household_BrazilRuralDevelopmentProgram_FinancialBenefit`

## Sub-Agent Task Templates

### Template 1: Pattern Extraction
```
Analyze directory: <path>
Extract:
1. PV map structure and complexity
2. Place resolution scope and patterns  
3. Configuration parameters used
4. Input data characteristics
5. Output format and quality
6. Unique processing techniques
7. Automation potential assessment
```

### Template 2: Workflow Analysis
```
Analyze import workflow: <path>
Document:
1. Complete processing pipeline
2. Data acquisition method
3. Preprocessing requirements
4. Tool invocation parameters
5. Error handling approach
6. Scheduling and automation
7. Resource requirements
```

### Template 3: Comparison Analysis
```
Compare patterns between: <path1> and <path2>
Identify:
1. Structural similarities and differences
2. Complexity variations
3. Shared vs unique techniques
4. Scalability implications
5. Reusability potential
6. Best practices demonstrated
```

## Quick Access File Locations

### Core Tool Files
- Main processor: `/tools/statvar_importer/stat_var_processor.py`
- Configuration: `/tools/statvar_importer/config_flags.py`
- Property mapper: `/tools/statvar_importer/property_value_mapper.py`

### Example Directories
- Simple patterns: `/statvar_imports/bis/`
- Complex patterns: `/statvar_imports/brazil_visdata/`, `/statvar_imports/ireland_census/`
- US federal: `/statvar_imports/us_bls/`, `/statvar_imports/fbi/`
- International: `/statvar_imports/opendataforafrica/`, `/statvar_imports/world_bank/`

### Key Reference Files
- Research findings: `agent/docs/research_findings.md`
- Implementation plan: `agent/docs/implementation_plan.md` (when created)

This refresh protocol should restore full working knowledge of the StatVar Processor tool and patterns within 25-30 minutes using sub-agent parallel analysis.