# SSSOM Research for Data Commons Translation Library

## Executive Summary

SSSOM (Simple Standard for Sharing Ontological Mappings) is a community-driven standard that provides a TSV-based format for representing mappings between entities from different standards. It offers robust metadata support, Python tooling, and scalability features that align well with Data Commons translation library objectives.

## Core Capabilities Analysis

### 1. Bidirectional Mapping Support
- **Format**: TSV-based with subject_id → object_id mappings
- **Directionality**: Supports explicit predicate_id (e.g., skos:exactMatch, skos:broadMatch) to indicate mapping relationships
- **DCID Integration**: Can use DCIDs as either subject_id or object_id for central anchor pattern

### 2. Batch Translation Support
- **Native CSV/TSV**: Primary format is TSV, directly supporting batch operations
- **Programmatic API**: Python library `sssom-py` provides batch processing capabilities
- **Conversion Tools**: Built-in converters for JSON, RDF/OWL, and other formats

### 3. Community Contribution & Git-Friendliness
- **Human-Readable**: TSV format is diff-friendly and reviewable in pull requests
- **Metadata Headers**: Clear separation of metadata and mappings aids review process
- **Version Control**: Text-based format works seamlessly with Git

### 4. Scalability for Geo-codes and Statistical Variables
- **Large Dataset Support**: Can handle millions of mappings efficiently
- **Modular Files**: Supports splitting mappings across multiple files with cross-references
- **Lazy Loading**: Python library supports streaming for memory-efficient processing

### 5. Error Handling
- **Confidence Scores**: Each mapping can have confidence levels (0.0-1.0)
- **Mapping Cardinality**: Explicit support for 1:1, 1:n, n:1, n:n relationships
- **Validation**: Schema-based validation ensures data integrity

## Python Library Support

### sssom-py Library
```python
# Installation
pip install sssom

# Basic Usage Example
from sssom import MappingSetDataFrame
from sssom.parsers import parse_sssom_table
from sssom.writers import write_table

# Parse SSSOM file
msdf = parse_sssom_table("mappings.sssom.tsv")

# Filter mappings
geo_mappings = msdf.filter_by_prefix("geo:")

# Add new mapping with metadata
msdf.add_mapping(
    subject_id="UN_CODE:840",
    object_id="dcid:country/USA",
    predicate_id="skos:exactMatch",
    confidence=1.0,
    mapping_justification="MANUAL",
    author_id="orcid:0000-0000-0000-0000"
)

# Export to different formats
write_table(msdf, "output.sssom.tsv")
msdf.to_json("output.json")
msdf.to_rdf("output.ttl")
```

### Library Maturity
- **Active Development**: Regular releases and updates
- **Documentation**: Comprehensive API documentation
- **Community**: Active GitHub repository with 50+ contributors
- **Testing**: Extensive test suite with CI/CD

## Metadata Framework

### Core Metadata Fields (Relevant to Data Commons)
```yaml
# Mapping Set Level Metadata
mapping_set_id: "UN_to_DC_geocodes_v1.0"
mapping_set_version: "1.0.0"
mapping_set_description: "United Nations geographical codes to Data Commons DCIDs"
creator_id: "orcid:0000-0000-0000-0000"
license: "CC0 1.0"
mapping_date: "2024-01-15"

# Individual Mapping Metadata
subject_id: "UN:840"
subject_label: "United States of America"
object_id: "dcid:country/USA"
object_label: "United States"
predicate_id: "skos:exactMatch"
confidence: 1.0
mapping_justification: "LEXICAL_MATCH"
author_id: "https://github.com/username"
comment: "Official UN code to DCID mapping"
see_also: "https://unstats.un.org/unsd/methodology/m49/"
```

### Evolution Tracking
- **Version History**: mapping_set_version field for tracking versions
- **Change Tracking**: author_id and mapping_date for attribution
- **Provenance**: mapping_justification explains how mapping was derived
- **Comments**: Free-text field for additional context

## Relevant Examples for Data Commons

### Example 1: Statistical Variable Mapping
```tsv
subject_id	object_id	predicate_id	confidence	comment
SDMX:POP_TOTAL	dcid:Count_Person	skos:exactMatch	1.0	Total population
SDMX:GDP_CURRENT_USD	dcid:Amount_EconomicActivity_GrossDomesticProduction_Nominal	skos:exactMatch	0.95	GDP in current USD
WHO:LIFE_EXP_BIRTH	dcid:LifeExpectancy_Person	skos:exactMatch	1.0	Life expectancy at birth
```

### Example 2: Geo-code Hierarchical Mapping
```tsv
subject_id	object_id	predicate_id	confidence	subject_label
ISO3166-1:US	dcid:country/USA	skos:exactMatch	1.0	United States
ISO3166-2:US-CA	dcid:geoId/06	skos:exactMatch	1.0	California
FIPS:06037	dcid:geoId/06037	skos:exactMatch	1.0	Los Angeles County
UN_M49:840	dcid:country/USA	skos:exactMatch	1.0	United States
```

### Example 3: Time Format Mapping
```tsv
subject_id	object_id	predicate_id	confidence	comment
ISO8601:2024	dcid:2024	skos:exactMatch	1.0	Year 2024
ISO8601:2024-Q1	dcid:2024Q1	skos:exactMatch	1.0	First quarter 2024
ISO8601:2024-01	dcid:2024-01	skos:exactMatch	1.0	January 2024
```

## File Organization Strategies

### 1. Directory Structure for Large-Scale Mappings
```
translation-library/
├── metadata/
│   └── mapping_sets.yaml          # Registry of all mapping sets
├── geo/
│   ├── un_codes.sssom.tsv        # UN geographical codes
│   ├── iso_3166.sssom.tsv        # ISO country codes
│   └── fips_codes.sssom.tsv      # FIPS codes
├── statistical/
│   ├── sdmx_variables.sssom.tsv  # SDMX statistical variables
│   └── who_indicators.sssom.tsv   # WHO health indicators
├── temporal/
│   └── time_formats.sssom.tsv    # Time format mappings
└── scripts/
    └── validate_mappings.py       # Validation utilities
```

### 2. Grouping Strategies
```yaml
# External metadata mode for grouping
# File: geo/un_codes.metadata.yml
mapping_set_id: "UN_geographical_codes"
subsets:
  - id: "un_countries"
    description: "UN member states"
    file: "un_countries.sssom.tsv"
  - id: "un_regions"
    description: "UN regional groupings"
    file: "un_regions.sssom.tsv"
  - id: "un_subregions"
    description: "UN sub-regional divisions"
    file: "un_subregions.sssom.tsv"
```

### 3. Cross-Reference Support
```tsv
# File can reference mappings from other files
subject_id	object_id	predicate_id	imported_from
UN:840	dcid:country/USA	owl:sameAs	iso_3166.sssom.tsv
```

## Standards Compliance & Tooling

### Built-in Standards Support
- **Semantic Web**: OWL/RDF export for integration with knowledge graphs
- **LinkML**: Schema definition using LinkML for validation
- **SKOS**: Native support for SKOS predicates (exactMatch, broadMatch, etc.)
- **OBO**: Compatible with Open Biological Ontologies

### Ecosystem Tools
```bash
# CLI Tools
sssom parse mappings.tsv              # Parse and validate
sssom convert mappings.tsv -o rdf     # Convert to RDF
sssom merge file1.tsv file2.tsv       # Merge mapping sets
sssom filter --prefix "UN:" mappings.tsv  # Filter mappings

# Integration with Other Tools
robot convert --input mappings.sssom.tsv --output mappings.owl
linkml-validate -s sssom_schema.yaml mappings.tsv
```

## Implementation Recommendations

### 1. Adopt SSSOM as Primary Format
- Use TSV format for human readability and Git-friendliness
- Leverage metadata headers for comprehensive documentation
- Implement confidence scores for mapping quality indication

### 2. Repository Structure
```
datacommons-translation-library/
├── README.md
├── CONTRIBUTING.md
├── schemas/
│   └── dcid_extensions.yaml      # Custom extensions for DC-specific needs
├── mappings/
│   ├── core/                     # Core DC mappings
│   ├── community/                # Community contributions
│   └── staging/                  # Pending review
└── tools/
    ├── validator.py              # SSSOM validation with DC rules
    ├── translator.py             # A→B translation via DCID
    └── api/                      # REST API for translations
```

### 3. API Implementation
```python
class DataCommonsTranslator:
    def __init__(self, mappings_dir="mappings/"):
        self.mappings = self.load_all_mappings(mappings_dir)

    def translate(self, source_format, source_id, target_format):
        # Step 1: source_format:source_id → DCID
        dcid = self.to_dcid(source_format, source_id)

        # Step 2: DCID → target_format:target_id
        target_id = self.from_dcid(dcid, target_format)

        return target_id

    def batch_translate(self, csv_file, source_col,
                       source_format, target_format):
        # Process CSV with translations
        pass
```

### 4. Quality Assurance
- Require confidence scores for all mappings
- Implement automated validation on pull requests
- Use mapping_justification field to document methodology
- Track contributor information via author_id

## Advanced Features

### 1. Complex Mappings
```tsv
# Many-to-one mapping with different confidence levels
subject_id	object_id	predicate_id	confidence	comment
UN:156	dcid:country/CHN	skos:exactMatch	1.0	China mainland
UN:344	dcid:country/CHN	skos:narrowMatch	0.8	Hong Kong SAR
UN:446	dcid:country/CHN	skos:narrowMatch	0.8	Macao SAR
```

### 2. Conditional Mappings
```tsv
# Time-dependent mappings
subject_id	object_id	predicate_id	other_properties
USSR:1922-1991	dcid:country/SU	skos:exactMatch	{"valid_from": "1922", "valid_to": "1991"}
```

### 3. Unit Conversions (via semantic_similarity field)
```tsv
subject_id	object_id	predicate_id	semantic_similarity	comment
unit:fahrenheit	unit:celsius	rdfs:seeAlso	"(F-32)*5/9"	Temperature conversion
unit:feet	unit:meters	rdfs:seeAlso	"ft*0.3048"	Length conversion
```

## Conclusion

SSSOM provides a robust, standards-based foundation for the Data Commons translation library that:
- Meets all core objectives with mature tooling
- Offers extensive metadata support for tracking evolution
- Scales efficiently for large mapping sets
- Facilitates community contributions through Git-friendly format
- Provides Python library for programmatic access
- Supports complex real-world mapping scenarios

The standard's active community, comprehensive documentation, and existing tooling ecosystem make it an ideal choice for avoiding custom tooling development while ensuring long-term maintainability and community adoption.