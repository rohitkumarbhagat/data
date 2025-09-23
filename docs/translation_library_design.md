# Standards Translation Library Mapping Format

## Introduction

Data Commons aims to establish a universal bridge between diverse data standards used across organizations globally. Currently, organizations maintain isolated mappings between standards, leading to duplication of effort and inconsistent translations. This document recommends the optimal format for a community-driven translation library that will serve as the canonical repository for mapping between various public standard codes and Data Commons identifiers (DCIDs).

The library will be hosted on GitHub to enable community contributions and will position DCIDs as the central anchor point for cross-standard translations. This enables any organization to translate between arbitrary standards A and B by using DCID as an intermediary, eliminating the need for maintaining N×N direct mappings.

## Objective

Recommend a machine-readable, version-controlled mapping format that:

- **Enables bidirectional mapping** between any standard code and DCID
- **Supports batch translations** via CSV input/output and programmatic APIs
- **Facilitates community contributions** through clear, reviewable pull requests
- **Scales efficiently** for geo-codes, statistical variables
- **Provides robust error handling** for unmapped entities and invalid formats
- **Allows incremental adoption** starting with SDMX-to-DCID mappings
- **Leverages standard formats with mature open source tooling** to ensure easy adoption, avoid building custom tooling from scratch, and benefit from **evolving** community standards


## Mapping Options

### SSSOM (Simple Standard for Sharing Ontological Mappings)

### Why SSSOM is the optimal choice:

SSSOM is a mature, community-driven standard specifically designed for mapping between different ontologies and coding systems. It directly addresses all our core objectives:

### Technical Advantages:
- **Primary TSV format with multi-format support** - TSV is the canonical format (human-readable, Git diff-friendly), but SSSOM also supports JSON-LD, RDF/TTL, and Web Ontology Language(OWL) through converters
- **Rich and extensible metadata** - 40+ optional fields for tracking provenance, confidence scores (0.0-1.0), versioning, and contributor attribution. Additionally supports custom fields through LinkML schema extension mechanism for organization-specific needs
  ```yaml
  mapping_set_id: "SDMX_to_DataCommons_v2"
  mapping_set_description: "SDMX/CL_REF_AREA/1.0 to DataCommons DCIDs"
  mapping_set_version: "2.0.1"
  mapping_date: "2024-03-15"
  creator_id: "github:rohitkumarbhagat"
  subject_source: "SDMX:CL_REF_AREA:1.0"
  object_source: "DataCommons:2024.01"
  mapping_justification: "Map Standard SDMX places codes to Data Commons"
  # Custom DataCommons-specific extensions via LinkML
  extension_definitions:
    - slot_name: "ext_dc_review_status"
    - slot_name: "ext_dc_mapping_priority"
    - slot_name: "ext_dc_last_validated"
  ext_dc_review_status: "approved"
  ext_dc_mapping_priority: "high"
  ext_dc_last_validated: "2024-03-10"
  ```
- **Mature Python tooling** - `sssom-py` library provides parsing, validation, conversion, and batch processing out-of-the-box
- **Formal schema validation** - LinkML-based schema ensures data integrity, field constraints, and consistent structure across all mapping files (https://github.com/mapping-commons/sssom/blob/master/src/sssom_schema/schema/sssom_schema.yaml)
- **Scalable architecture** - Handles millions of mappings, supports modular file organization and cross-references
  ```
  mappings/
  ├── world_bank/
  │   ├── indicators.sssom.tsv (3K mappings)
  │   └── country_codes.sssom.tsv (217 mappings)
  ├── un/
  │   ├── sdg_indicators.sssom.tsv (232 mappings)
  │   └── m49_geo_codes.sssom.tsv (249 mappings)
  ├── oecd/
  │   └── economic_indicators.sssom.tsv (1.5K mappings)
  ```

### Alignment with Requirements:
- **Bidirectional mappings** - Native support via predicate types (skos:exactMatch, skos:broadMatch)
  ```tsv
  # Exact match (bidirectional by nature)
  UN:840  dcid:country/USA  skos:exactMatch  1.0
  # Hierarchical with confidence
  UN:019  dcid:northamerica  skos:broadMatch  0.85
  # Close but not exact match
  WHO:TB  dcid:Tuberculosis  skos:closeMatch  0.9
  ```
- **Community contributions** - TSV format makes PR reviews straightforward; metadata tracks contributors
- **Error handling** - Built-in confidence scoring and validation schemas
- **No custom tooling needed** - SSSOM CLI (`sssom parse`, `sssom convert`, `sssom validate`), Python API, and built-in converters between TSV↔JSON-LD↔RDF/TTL↔OWL formats
- **Many-to-many cardinality support** - Native n:n relationships through multiple rows with same subject or object
  ```tsv
  # One-to-many: Single SDMX Europe code maps to both geographic and political entities
  SDMX:150  dcid:Europe         skos:broadMatch   0.8
  SDMX:150  dcid:EuropeanUnion  skos:narrowMatch  0.7
  ```
- **Conditional mappings via extension slots** - Temporal validity using custom metadata fields
  ```yaml
  # Extension slots defined in header
  extension_definitions:
    - slot_name: "ext_valid_from"
    - slot_name: "ext_valid_to"
  ```
  ```tsv
  # Same SDMX code maps to different countries based on time period
  subject_id  object_id        predicate_id      ext_valid_from  ext_valid_to
  SDMX:810    dcid:country/SU  skos:exactMatch   1922           1991
  SDMX:810    dcid:country/RU  skos:exactMatch   1992           null
  ```

### Example Structure:

The `curie_map` defines namespace prefixes for Compact URIs (CURIEs). Each prefix maps to a full URI base, allowing short identifiers like `SDMX:840` instead of full URIs like `https://sdmx.org/wp-content/uploads/CL_REF_AREA_1_0.xlsx#840`.

```tsv
# curie_map:
#   SDMX: "https://sdmx.org/wp-content/uploads/CL_REF_AREA_1_0.xlsx"
#   dcid: "https://datacommons.org/browser/"
#   github: "https://github.com/"
# mapping_set_id: "SDMX_REF_AREA_to_DataCommons_v1"
# mapping_set_description: "SDMX REF_AREA codes to DataCommons DCIDs"
# mapping_set_version: "1.0.0"
# mapping_date: "2024-03-15"
# creator_id: "github:rohitkumarbhagat"
# subject_source: "SDMX:CL_REF_AREA:1.0"
# object_source: "DataCommons:2024.01"
# extension_definitions:
#   - slot_name: "ext_dc_review_status"
#   - slot_name: "ext_dc_mapping_priority"
#   - slot_name: "ext_dc_last_validated"
# ext_dc_review_status: "approved"
# ext_dc_mapping_priority: "high"
# ext_dc_last_validated: "2024-03-10"
subject_id	object_id	predicate_id	confidence	comment
SDMX:840	dcid:country/USA	skos:exactMatch	1.0	United States
SDMX:124	dcid:country/CAN	skos:exactMatch	1.0	Canada
SDMX:826	dcid:country/GBR	skos:exactMatch	1.0	United Kingdom
SDMX:150	dcid:Europe	skos:broadMatch	0.8	Europe region (broader than country)
```

### Real-world adoption:
SSSOM is actively used by major biomedical and semantic web organizations including the **Open Biological and Biomedical Ontology (OBO) Foundry**, **Monarch Initiative** for disease-gene mappings, **EMBL-EBI** for ontology alignment, and various **NIH-funded projects** for clinical terminology mappings. The standard has proven scalability with deployments handling millions of mappings between medical coding systems like SNOMED CT, ICD, and MeSH.

SSSOM provides the ideal balance of simplicity, functionality, and existing ecosystem support.

### Alternative Options Considered:
- **Custom JSON** - Would require building tooling from scratch
- **Plain CSV** - Lacks metadata and validation capabilities
- **Protocol Buffers** - Not human-readable, poor Git integration
- **RDF/OWL** - Too complex for contributors, steep learning curve
- **SDMX Structure Maps** - XML-based transformation blueprints for complex statistical data mappings with the following characteristics:
  - Designed for cases where single SDMX concepts split into multiple target concepts
  - Example: One SDMX concept like "TRANSACTION:B1GQ" (GDP) → multiple Data Commons properties (measuredProperty: grossDomesticProduct, populationType: EconomicActivity)
  - Powerful for advanced use cases but overkill for initial simple 1:1 mappings

### References:
- SSSOM Specification: https://mapping-commons.github.io/sssom/
- SSSOM Python Library & CLI Tools: https://github.com/mapping-commons/sssom-py
- SSSOM CLI Documentation: https://mapping-commons.github.io/sssom-py/cli.html
- SSSOM Tutorial: https://mapping-commons.github.io/sssom/tutorial/
- SSSOM Project Template Generator: https://github.com/mapping-commons/mapping-commons-cookiecutter
- LinkML (Schema Language): https://linkml.io/
- SDMX Structure Maps Documentation: https://fmrwiki.sdmxcloud.org/Structure_Map

## Recommendation

**Adopt SSSOM as the primary mapping format** for the Data Commons translation library. Begin with straightforward SDMX-to-DCID mappings covering geographical codes and statistical variables where direct 1:1 relationships exist.

### Implementation Roadmap:
- **Phase 1**: Deploy SSSOM for simple mappings (geo codes, basic statistical variables) leveraging its TSV format, Python tooling, and community ecosystem
- **Phase 2**: For complex transformations where single SDMX concepts must split into multiple Data Commons concepts, evaluate SDMX Structure Maps with Representation Maps

This approach balances immediate implementation needs with future scalability, starting simple with proven tooling while preserving options for advanced use cases.