# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
SDMX Message Dataclasses

This module provides dataclasses for representing SDMX structural metadata
in a simplified JSON format. These classes serve as data transfer objects
for SDMX dataflows and their components.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Literal


@dataclass
class Code:
    """Represents a single Code within a Codelist."""
    id: str
    name: str = ""
    description: str = ""


@dataclass
class CodelistDetails:
    """Represents the details of a Codelist, including its Codes."""
    id: str
    name: str = ""
    description: str = ""
    codes: List[Code] = field(default_factory=list)


@dataclass
class FacetDetails:
    """Represents a single Facet for non-enumerated representations."""
    type: str  # Corresponds to sdmx.model.common.FacetType, e.g., 'string', 'integer'
    value: Optional[str] = None
    value_type: Optional[
        str] = None  # Corresponds to sdmx.model.common.FacetValueType


@dataclass
class RepresentationDetails:
    """
    Describes the permissible values for a Dimension, Attribute, or Measure.
    It can be either enumerated (using a Codelist) or non-enumerated (using Facets).
    """
    type: Literal["enumerated", "non-enumerated"]
    codelist: Optional[
        CodelistDetails] = None  # Present if type is "enumerated"
    facets: List[FacetDetails] = field(
        default_factory=list)  # Present if type is "non-enumerated"


@dataclass
class ConceptDetails:
    """Represents the Concept associated with a Component (Dimension, Attribute, Measure)."""
    id: str
    name: str = ""
    description: str = ""
    concept_scheme_id: Optional[
        str] = None  # The ID of the ConceptScheme it belongs to


@dataclass
class ComponentDetails:
    """
    A base structure for Dimensions, Attributes, and Measures, as they share common properties.
    Each is a Component of a data structure.
    """
    id: str
    name: str = ""
    description: str = ""
    concept: Optional[ConceptDetails] = None
    representation: Optional[RepresentationDetails] = None


@dataclass
class DataStructureDefinitionDetails:
    """
    Represents the Data Structure Definition (DSD) associated with a Dataflow.
    It describes the dimensions, attributes, and measures of the data.
    """
    id: str
    name: str = ""
    description: str = ""
    dimensions: List[ComponentDetails] = field(
        default_factory=list)  # Each is a DimensionComponent
    attributes: List[ComponentDetails] = field(
        default_factory=list)  # Each is a DataAttribute
    measures: List[ComponentDetails] = field(
        default_factory=list
    )  # Each is a PrimaryMeasure (v2.1) or Measure (v3.0)


@dataclass
class ReferencedConceptSchemeDetails:
    """Represents a ConceptScheme and its Concepts referenced within the Dataflow."""
    id: str
    name: str = ""
    description: str = ""
    concepts: List[ConceptDetails] = field(default_factory=list)


@dataclass
class DataflowArtefactAttributes:
    """
    A collection of additional attributes for the Dataflow, corresponding to
    properties of a MaintainableArtefact and VersionableArtefact.
    """
    version: Optional[str] = None  # A version string
    valid_from: Optional[str] = None  # Date from which the dataflow is valid
    valid_to: Optional[str] = None  # Date from which the dataflow is superseded
    is_final: Optional[
        bool] = None  # True if the object is final; otherwise it is in a draft state
    is_external_reference: Optional[
        bool] = None  # True if the content of the object is held externally
    service_url: Optional[str] = None  # URL of an SDMX-compliant web service
    structure_url: Optional[str] = None  # URL of an SDMX-ML document


@dataclass
class DataflowStructure:
    """
    Represents a single Dataflow object, corresponding to
    sdmx.model.common.BaseDataflow (e.g., v21.DataflowDefinition or v30.Dataflow).
    """
    id: str
    name: str = ""
    description: str = ""
    artefact_attributes: Optional[DataflowArtefactAttributes] = None
    data_structure_definition: Optional[DataStructureDefinitionDetails] = None
    referenced_concept_schemes: List[ReferencedConceptSchemeDetails] = field(
        default_factory=list)


@dataclass
class MultiDataflowOutput:
    """The root object for multiple dataflows, containing the 'dataflows' key."""
    dataflows: List[DataflowStructure] = field(default_factory=list)
