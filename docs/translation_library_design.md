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
- **Leverages standard formats with mature open source tooling** to ensure easy adoption, avoid building custom tooling from scratch, and benefit from evolving community standards


## Format Options

[TO BE ADDED: Analysis of different format options including JSON, CSV, Protocol Buffers, YAML, and hybrid approaches. Each option will be evaluated on criteria such as human readability, machine parsing efficiency, git-friendliness, validation capabilities, and community familiarity.]

## Recommendation

[TO BE ADDED: Final recommendation based on the analysis above, with specific implementation details including file structure, naming conventions, validation schemas, and example mappings.]