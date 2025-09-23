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

**Why SSSOM is the optimal choice:**

SSSOM is a mature, community-driven standard specifically designed for mapping between different ontologies and coding systems. It directly addresses all our core objectives:

**Technical Advantages:**
- **Primary TSV format with multi-format support** - TSV is the canonical format (human-readable, Git diff-friendly), but SSSOM also supports JSON-LD, RDF/TTL, and OWL through converters
- **Rich metadata support** - 40+ optional fields for tracking provenance, confidence scores (0.0-1.0), versioning, and contributor attribution
- **Mature Python tooling** - `sssom-py` library provides parsing, validation, conversion, and batch processing out-of-the-box
- **Scalable architecture** - Handles millions of mappings, supports modular file organization and cross-references

**Alignment with Requirements:**
- **Bidirectional mappings** - Native support via predicate types (skos:exactMatch, skos:broadMatch)
- **Community contributions** - TSV format makes PR reviews straightforward; metadata tracks contributors
- **Error handling** - Built-in confidence scoring and validation schemas
- **No custom tooling needed** - SSSOM CLI (`sssom parse`, `sssom convert`, `sssom validate`), Python API, and built-in converters between TSV↔JSON-LD↔RDF/TTL↔OWL formats

**Example Structure:**
```tsv
subject_id	object_id	predicate_id	confidence	comment
UN:840	dcid:country/USA	skos:exactMatch	1.0	United Nations to DCID
SDMX:POP_TOTAL	dcid:Count_Person	skos:exactMatch	1.0	Population variable
ISO3166-1:US	dcid:country/USA	skos:exactMatch	1.0	ISO country code
```

**Alternative Options Considered:**
- **Custom JSON** - Would require building tooling from scratch
- **Plain CSV** - Lacks metadata and validation capabilities
- **Protocol Buffers** - Not human-readable, poor Git integration
- **RDF/OWL** - Too complex for contributors, steep learning curve

SSSOM provides the ideal balance of simplicity, functionality, and existing ecosystem support.

**References:**
- SSSOM Specification: https://mapping-commons.github.io/sssom/
- SSSOM Python Library & CLI Tools: https://github.com/mapping-commons/sssom-py
- SSSOM CLI Documentation: https://mapping-commons.github.io/sssom-py/cli.html
- SSSOM Tutorial: https://mapping-commons.github.io/sssom/tutorial/
- LinkML (Schema Language): https://linkml.io/

## Recommendation

[TO BE ADDED: Final recommendation based on the analysis above, with specific implementation details including file structure, naming conventions, validation schemas, and example mappings.]