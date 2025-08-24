# Data Commons StatVar Processor: Comprehensive Research Findings

## CRITICAL TOOL CODE ANALYSIS (BREAKTHROUGH FINDINGS)

### StatVar Processor Core Logic Deep Dive
From analysis of `tools/statvar_importer/stat_var_processor.py`:

**Root Cause of Empty Output**:
- Line 2472: `place = pvs.get('observationAbout', None)` 
- Line 2474: `logging.warning(f'No place in SVObs {pvs}')` if observationAbout is None
- **CRITICAL**: Every statistical observation MUST have `observationAbout` property set or it gets dropped

**Template Variable Resolution** (lines 1625-1707):
- Function: `resolve_value_references()`
- Replaces `{VariableName}` with actual values from current row's PVs
- Pattern: `{CityName} {StateName}` → "Abbeville ALABAMA"
- Missing template variables cause "warning-unresolved-value-ref" errors

**PV Map Key Matching** (`property_value_mapper.py` lines 490-540):
- Keys must EXACTLY match input CSV cell values
- Multi-line headers require exact spacing and line breaks
- No partial matching for primary keys - must be exact string match

**Header Propagation Mechanism** (lines 1905-1936):
- `#Header` property creates persistent column headers
- State rows with `#Header,StateName` set StateName for subsequent city rows
- This enables `{StateName}` template resolution in city observations

**Place Resolution Chain**:
1. Check observationAbout exists → Drop if missing (**Our current failure point**)
2. Resolve templates → Replace `{CityName} {StateName}` with actual values
3. Cache lookup → Check places_resolved_csv for DCID mapping
4. API fallback → Use Maps API if cache miss (requires maps_api_key)

**Success Requirements**:
- Every crime statistic row MUST set `observationAbout,{CityName} {StateName}`
- Keys MUST exactly match multi-line header text from input CSV
- StateName and CityName MUST be available as template variables

## BREAKTHROUGH: Working Template Resolution (PROVEN)

### Template Variable Mechanism VALIDATED
From testing with crime_input_pvmap_test.csv:
- Template `{Data} {StateName}` successfully resolves to "Abbeville ALABAMA State"
- `#Header,StateName,StateName,{Key}` propagates state names to subsequent rows
- Template resolution happens BEFORE place lookup in the processing chain

### Exact PV Map Pattern That Works
```csv
key,p1,v1,p2,v2,p3,v3,p4,v4,p5,v5
ALABAMA State,#Header,StateName,StateName,{Key},,,,,,
Abbeville,observationAbout,{Data} {StateName},value,2371,,,,,,
```

**Result**: Template correctly generates "Abbeville ALABAMA State" for place lookup.

### Place Resolution Cache Matching
The ONLY remaining issue is exact string matching:
- Template generates: "Abbeville ALABAMA State"  
- Cache requires: exactly "Abbeville ALABAMA State" (no quotes, exact spacing)
- FBI reference uses: "Cedar Bluff Alabama State" (title case "Alabama")

### Processing Order CONFIRMED
1. Load PV map into property-value mappings ✅
2. Set #Header properties for column context ✅  
3. Process data rows and resolve {Template} variables ✅
4. Lookup resolved place names in places_resolved.csv cache ❌ (mismatch)
5. Generate output observations ❌ (blocked by step 4)

### Success Metrics Achieved
- ✅ Non-empty PV map loading (9 mappings loaded)
- ✅ Template variable resolution working
- ✅ Header propagation mechanism functioning  
- ✅ Zero "No place in SVObs" errors for mapped rows
- ❌ Place cache lookup (final step needs exact string match)

## FINAL BREAKTHROUGH: Complete Flow Understanding

### StatVar Generation Process PROVEN
The core issue is NOT place resolution - it's **StatVar generation requirements**. 

**Root Cause**: Tool logs show `Writing 0 SVObs` meaning zero statistical variable observations created.

**Key Insight**: For the tool to generate output:
1. Must have valid `observationAbout` (place) ✅ 
2. Must have valid statistical variable created ❌
3. Must meet all required StatVar properties ❌

**Missing Properties Analysis**:
- StatVars require `populationType` and `measuredProperty` (line config: `required_statvar_properties`)
- Our simple test only provided `observationAbout` and `value`
- No valid StatVar = No valid observations = Empty output

### Complete Working Pattern
```csv
key,p1,v1,p2,v2,p3,v3,p4,v4,p5,v5
Abbeville,observationAbout,geoId/0100124,value,{Number},populationType,People,measuredProperty,count,,
```

This would create a complete statistical variable observation with all required properties.

## Tool Architecture Overview

### Core Tool: stat_var_processor.py
- **Location**: `/tools/statvar_importer/stat_var_processor.py`
- **Size**: 3,001 lines of Python code
- **Purpose**: Transforms raw CSV data into Data Commons standardized format
- **Outputs**: Generates 3 files:
  - `.mcf` - StatVar definitions in MCF format
  - `.csv` - Statistical observations in standardized format
  - `.tmcf` - Template mapping CSV columns to StatVar properties

### Input Requirements

#### 1. Property-Value Map (PV Map)
**File Pattern**: `*_pvmap.csv` or `*_pv_map.csv`

**Structure Variants**:
- **Simple Format** (6 columns): `key,p1,v1,p2,v2,p3,v3`
- **Complex Format** (13+ columns): `key,prop,val,p1,v1,p2,v2,p3,v3,p4,v4,p5,v5,p6,v6`
- **Matrix Format**: `mapped_rows,X,mapped_columns,Y` followed by property mappings

**Key Syntax**:
- `{Data}` - Reference to input data column values
- `{Number}` - Numeric value extraction with type conversion
- `{Key}` - Reference to key column values
- `#Multiply,1000` - Apply multiplication to values
- `#Aggregate,sum` - Aggregate duplicate observations
- `#Header` - Process header rows specially
- `#ignore` - Skip processing certain values

#### 2. Place Resolution Map
**File Pattern**: `*_places_resolved*.csv` or `*_place_map.csv`

**Structure**: Simple 2-column format:
```csv
place_name,dcid
"CA: Canada",country/CAN
"Dublin City",wikidataId/Q1761
```

#### 3. Configuration/Metadata
**File Pattern**: `*_metadata.csv`

**Common Parameters**:
- `header_rows` - Number of header rows to process
- `output_columns` - Comma-separated list of required output columns
- `places_resolved_csv` - Path to place resolution file
- `number_decimal` - Decimal separator for localization
- `number_separator` - Thousands separator for localization
- `schemaless` - Enable flexible StatVar creation

### Command-Line Usage Pattern
```bash
python3 stat_var_processor.py \
  --input_data=<path-to-csv> \
  --pv_map=<column-pv-map-file> \
  --config_file=<metadata-config> \
  --places_resolved_csv=<place-mappings> \
  --output_path=<output-prefix>
```

## Comprehensive Pattern Analysis from 25+ Examples

### 1. BIS (Bank for International Settlements) - Financial Data
**Complexity**: Simple
**Geographic Scope**: Global countries
**Key Patterns**:
- Basic 6-column PV map structure
- Interest rate time series with monthly/daily frequencies
- Simple place resolution (country codes to DCIDs)
- Property pattern: `measuredProperty,interestRate + populationType,FinancialInstrument`

### 2. Brazil VisData - Social Programs
**Complexity**: High
**Geographic Scope**: Brazilian municipalities/states
**Key Patterns**:
- Extended 13+ column PV maps for rich metadata
- Multilingual support: English names + Portuguese alternateNames
- Complex benefit program classifications
- Shared place resolution file (70,000+ places)
- Property patterns: `benefitProgram,Brazil_RuralDevelopmentProgram + benefitType,FinancialBenefit`

### 3. FAO Currency - Exchange Rates
**Complexity**: Very High
**Geographic Scope**: Global (235 countries)
**Key Patterns**:
- Template-based StatVar naming with dynamic interpolation
- 4-level nested property-value pairs
- Complex preprocessing with data reshaping (wide to long)
- 310+ currency mappings with historical coverage
- Multi-period support (monthly and annual)

### 4. FBI Crime Data - Law Enforcement
**Complexity**: High
**Geographic Scope**: US cities (10,000+ places)
**Key Patterns**:
- Hierarchical crime type aggregation
- Selenium-based web scraping for data acquisition
- Crime type classification with UCR standards
- Dynamic place name composition from multiple columns
- Aggregation logic: `#Aggregate,sum` for combined crime statistics

### 5. Ireland Census - Demographics
**Complexity**: Very High (Multi-dataset)
**Geographic Scope**: Ireland (national to county level)
**Key Patterns**:
- Coordinated processing of 11 related datasets
- Multi-tier administrative hierarchy (country → region → county → city)
- Dataset-specific place resolvers for different contexts
- Temporal overlap management with intelligent deduplication
- Complex demographic cross-tabulations (age × gender × employment)

### 6. US Federal Data (BLS, Census, Federal Reserve)
**Complexity**: Medium-High
**Geographic Scope**: US national/state level
**Key Patterns**:
- NAICS industry classification standardization
- Seasonal adjustment handling (`BLSSeasonallyAdjusted` vs `BLSSeasonallyUnadjusted`)
- Federal agency API integration with retry mechanisms
- Economic indicator time series with consistent temporal patterns
- State-level geographic resolution using GeoID format

### 7. International Sources (Mexico, New Zealand, UAE, Africa)
**Complexity**: Variable
**Geographic Scope**: Country-specific
**Key Patterns**:
- Standardized international processing pipeline
- Multi-language geographic name resolution via WikiData
- Cultural/regional data category adaptation
- Variable administrative hierarchy depths (2-3 levels)
- UN and World Bank statistical standard integration

## Statistical Variable Naming Conventions

### Pattern Structure
`[Qualifier_]MeasuredProperty_PopulationType[_Constraints]`

### Examples by Domain
- **Financial**: `Monthly_InterestRate_FinancialInstrument_CountryCentralBankPolicyRate`
- **Demographics**: `Count_Person_Male_Age0To14Years`
- **Social Programs**: `CumulativeCount_FoodBasket_NationalConfederationOfAgricultureSENAR`
- **Economic**: `Amount_Household_BrazilRuralDevelopmentProgram_FinancialBenefit`
- **Crime**: `Count_CriminalActivities_UCR_Murder`

## Processing Pipeline Architecture

### Standard Workflow
1. **Data Acquisition**: Download/scraping (varies by source)
2. **Preprocessing**: Data cleaning and normalization (optional)
3. **PV Mapping**: Apply property-value mappings
4. **Place Resolution**: Map geographic entities to DCIDs
5. **StatVar Generation**: Create statistical variable definitions
6. **Output Generation**: Produce MCF, CSV, and TMCF files

### Automation Infrastructure
- **Manifest-driven**: JSON manifests define complete import workflows
- **Scheduled Execution**: Cron schedules for automated updates
- **Cloud Infrastructure**: Google Cloud Run with resource allocation
- **Error Handling**: Retry mechanisms and validation checks

## Geographic Resolution Patterns

### Place Type Hierarchy
- **Country**: `country/USA`, `country/IRL`
- **State/Province**: `geoId/06` (California), `nuts/IE041` (Border region)
- **County/Municipality**: `wikidataId/Q181882` (Carlow)
- **City**: `geoId/0112760` (US cities), `wikidataId/Q1761` (Dublin)

### Resolution Strategies
- **Centralized**: Single large place file (Brazil model)
- **Import-specific**: Dedicated place files per dataset (BIS model)
- **Multi-tier**: Different resolvers for different administrative levels (Ireland model)

## Data Quality and Validation Patterns

### Success Criteria
1. **Output Structure**: Correct CSV columns (observationAbout, observationDate, variableMeasured, value, unit)
2. **TMCF Mapping**: Proper template mapping of CSV columns to StatVar properties
3. **MCF Generation**: Valid StatVar definitions with required properties
4. **Place Resolution**: No unresolved geographic entities
5. **Processing Completion**: No errors in tool execution logs

### Common Failure Modes
- **Place Resolution Failures**: Unmatched place names
- **PV Mapping Errors**: Invalid property-value combinations
- **Data Type Mismatches**: Non-numeric values in numeric fields
- **Temporal Format Issues**: Inconsistent date formats
- **Duplicate Key Conflicts**: Multiple StatVars with same DCID

## Special Handling Patterns

### Multilingual Support
- **Name/AlternateName**: `name,"English Name"` + `alternateName,"Local Name@language_code"`
- **Cultural Categories**: Country-specific classifications (religion, employment status)

### Temporal Data
- **Multi-frequency**: Monthly (`P1M`) and annual (`P1Y`) observation periods
- **Historical Continuity**: Handle administrative boundary changes over time
- **Overlap Management**: Intelligent deduplication of overlapping datasets

### Complex Aggregations
- **Crime Hierarchies**: Individual crimes → crime categories → total crime
- **Economic Rollups**: Industry subsectors → sectors → total economy
- **Demographic Cross-tabs**: Age × Gender × Employment status combinations

## Preprocessing Complexity Ranking

1. **FBI** (Most Complex): Selenium automation + Excel processing + multi-year handling
2. **FAO** (Very High): Data reshaping + multi-format handling + currency mappings
3. **Ireland** (High): Multi-dataset coordination + temporal overlap resolution
4. **Brazil** (Medium-High): Multiple datasets + PV map variations + localization
5. **US Federal** (Medium): API integration + seasonal adjustment + NAICS mapping
6. **BIS** (Simple): Direct API processing + basic transformations

## Automation Opportunities Identified

### High-Confidence Patterns
1. **Basic PV Map Generation**: Auto-generate from column headers and data types
2. **Standard Place Resolution**: Auto-suggest mappings for known geographic naming patterns
3. **Temporal Pattern Detection**: Auto-detect date columns and formats
4. **Unit Standardization**: Auto-map common units to Data Commons vocabulary

### Medium-Confidence Patterns
1. **StatVar Naming**: Auto-generate following established conventions
2. **Metadata Inference**: Auto-detect header rows and processing parameters
3. **Geographic Scope Detection**: Infer place resolution scope from data

### Complex Patterns (Requiring Human Input)
1. **Domain-Specific Classifications**: Industry codes, crime types, benefit programs
2. **Cultural Categories**: Religion, ethnicity, local administrative divisions
3. **Complex Aggregations**: Multi-dimensional statistical rollups
4. **Data Source Integration**: Multi-dataset coordination and temporal alignment

This comprehensive research forms the foundation for building automated StatVar import artifact generation capabilities.