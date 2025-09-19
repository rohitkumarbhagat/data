"""
SDMX Reader Agent

Handles reading and parsing SDMX data files and metadata.
Supports both SDMX-ML (XML) and SDMX-CSV formats.
"""

from __future__ import annotations

import pandas as pd
import xml.etree.ElementTree as ET
import logging
import json
import os
import sdmx
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

# SDMX namespace mappings
SDMX_NAMESPACES = {
    'structure': 'http://www.sdmx.org/resources/sdmxml/schemas/v2_1/structure',
    'common': 'http://www.sdmx.org/resources/sdmxml/schemas/v2_1/common',
    'message': 'http://www.sdmx.org/resources/sdmxml/schemas/v2_1/message',
    'generic': 'http://www.sdmx.org/resources/sdmxml/schemas/v2_1/data/generic'
}

@dataclass
class SdmxDimension:
    """Represents an SDMX dimension"""
    id: str
    name: str
    description: str
    codelist: Optional[str] = None
    codes: Dict[str, str] = None

    def __post_init__(self):
        if self.codes is None:
            self.codes = {}

@dataclass
class SdmxMeasure:
    """Represents an SDMX measure"""
    id: str
    name: str
    description: str
    unit: Optional[str] = None

@dataclass
class SdmxAttribute:
    """Represents an SDMX attribute"""
    id: str
    name: str
    description: str
    attachment_level: str  # 'dataset', 'series', 'observation'
    codelist: Optional[str] = None
    codes: Dict[str, str] = None

    def __post_init__(self):
        if self.codes is None:
            self.codes = {}

@dataclass
class SdmxStructure:
    """Complete SDMX data structure"""
    dataflow_id: str
    dataflow_name: str
    dataflow_description: str
    dimensions: List[SdmxDimension]
    measures: List[SdmxMeasure]
    attributes: List[SdmxAttribute]
    codelists: Dict[str, Dict[str, str]]
    constraints: Optional[Dict[str, List[str]]] = None

    def __post_init__(self):
        if self.constraints is None:
            self.constraints = {}


def read_sdmx_csv(file_path: str) -> Dict[str, Any]:
    """Read SDMX-CSV format data file.

    Args:
        file_path: Path to SDMX-CSV file

    Returns:
        Dictionary with parsed data and structure info
    """
    try:
        df = pd.read_csv(file_path)

        # Identify standard SDMX columns
        dimensions = []
        measures = []
        attributes = []

        for col in df.columns:
            col_upper = col.upper()
            if col_upper in ['REF_AREA', 'TIME_PERIOD', 'FREQ', 'INDICATOR', 'SERIES']:
                dimensions.append(col)
            elif col_upper in ['OBS_VALUE', 'VALUE']:
                measures.append(col)
            elif col_upper in ['UNIT_MEASURE', 'OBS_STATUS', 'CONF_STATUS']:
                attributes.append(col)
            else:
                # Heuristic: if mostly numeric, it's a measure
                numeric_ratio = pd.to_numeric(df[col], errors='coerce').notna().sum() / len(df)
                if numeric_ratio > 0.8:
                    measures.append(col)
                elif len(df[col].unique()) < 50:
                    dimensions.append(col)
                else:
                    attributes.append(col)

        return {
            "status": "success",
            "format": "sdmx-csv",
            "data": df,
            "structure": {
                "dimensions": dimensions,
                "measures": measures,
                "attributes": attributes
            },
            "shape": {"rows": len(df), "cols": len(df.columns)}
        }

    except Exception as e:
        logging.error(f"Failed to read SDMX-CSV file {file_path}: {str(e)}")
        return {"status": "error", "error_message": str(e)}


def read_sdmx_ml(file_path: str) -> Dict[str, Any]:
    """Read SDMX-ML format metadata file.

    Args:
        file_path: Path to SDMX-ML file

    Returns:
        Dictionary with parsed metadata structure
    """
    try:
        tree = ET.parse(file_path)
        root = tree.getroot()

        # Register namespaces
        for prefix, uri in SDMX_NAMESPACES.items():
            ET.register_namespace(prefix, uri)

        structure = _parse_sdmx_structure(root)

        return {
            "status": "success",
            "format": "sdmx-ml",
            "structure": structure,
            "raw_xml": ET.tostring(root, encoding='unicode')
        }

    except Exception as e:
        logging.error(f"Failed to parse SDMX-ML file {file_path}: {str(e)}")
        return {"status": "error", "error_message": str(e)}


def _parse_sdmx_structure(root: ET.Element) -> SdmxStructure:
    """Parse SDMX structure from XML root element."""

    # Find dataflow information
    dataflow_elem = root.find('.//structure:Dataflow', SDMX_NAMESPACES)
    dataflow_id = ""
    dataflow_name = ""
    dataflow_description = ""

    if dataflow_elem is not None:
        dataflow_id = dataflow_elem.get('id', '')
        name_elem = dataflow_elem.find('common:Name', SDMX_NAMESPACES)
        if name_elem is not None:
            dataflow_name = name_elem.text or ""
        desc_elem = dataflow_elem.find('common:Description', SDMX_NAMESPACES)
        if desc_elem is not None:
            dataflow_description = desc_elem.text or ""

    # Parse dimensions
    dimensions = []
    dimension_elems = root.findall('.//structure:Dimension', SDMX_NAMESPACES)
    for dim_elem in dimension_elems:
        dim_id = dim_elem.get('id', '')
        concept_ref = dim_elem.find('structure:ConceptIdentity/Ref', SDMX_NAMESPACES)
        codelist_ref = dim_elem.find('structure:LocalRepresentation/structure:Enumeration/Ref', SDMX_NAMESPACES)

        dimensions.append(SdmxDimension(
            id=dim_id,
            name=dim_id,  # Will be enriched from concepts
            description="",
            codelist=codelist_ref.get('id') if codelist_ref is not None else None
        ))

    # Parse measures
    measures = []
    measure_elems = root.findall('.//structure:PrimaryMeasure', SDMX_NAMESPACES)
    for measure_elem in measure_elems:
        measure_id = measure_elem.get('id', 'OBS_VALUE')
        measures.append(SdmxMeasure(
            id=measure_id,
            name=measure_id,
            description="Primary observation value"
        ))

    # Parse attributes
    attributes = []
    attr_elems = root.findall('.//structure:Attribute', SDMX_NAMESPACES)
    for attr_elem in attr_elems:
        attr_id = attr_elem.get('id', '')
        attachment_level = 'observation'  # Default

        # Determine attachment level
        if attr_elem.find('structure:AttributeRelationship/structure:Group', SDMX_NAMESPACES) is not None:
            attachment_level = 'series'
        elif attr_elem.find('structure:AttributeRelationship/structure:None', SDMX_NAMESPACES) is not None:
            attachment_level = 'dataset'

        attributes.append(SdmxAttribute(
            id=attr_id,
            name=attr_id,
            description="",
            attachment_level=attachment_level
        ))

    # Parse codelists
    codelists = {}
    codelist_elems = root.findall('.//structure:Codelist', SDMX_NAMESPACES)
    for codelist_elem in codelist_elems:
        codelist_id = codelist_elem.get('id', '')
        codes = {}

        code_elems = codelist_elem.findall('structure:Code', SDMX_NAMESPACES)
        for code_elem in code_elems:
            code_id = code_elem.get('id', '')
            name_elem = code_elem.find('common:Name', SDMX_NAMESPACES)
            code_name = name_elem.text if name_elem is not None else code_id
            codes[code_id] = code_name

        codelists[codelist_id] = codes

    # Parse constraints if present
    constraints = {}
    constraint_elems = root.findall('.//structure:ContentConstraint', SDMX_NAMESPACES)
    for constraint_elem in constraint_elems:
        # Parse constraint definitions for focused processing
        pass  # TODO: Implement constraint parsing

    return SdmxStructure(
        dataflow_id=dataflow_id,
        dataflow_name=dataflow_name,
        dataflow_description=dataflow_description,
        dimensions=dimensions,
        measures=measures,
        attributes=attributes,
        codelists=codelists,
        constraints=constraints
    )


def read_sdmx_with_library(file_path: str) -> Dict[str, Any]:
    """Read SDMX using the sdmx library.

    Args:
        file_path: Path to SDMX file

    Returns:
        Dictionary with parsed data and metadata
    """
    try:
        # Read with sdmx library
        msg = sdmx.read_sdmx(file_path)

        result = {
            "status": "success",
            "format": "sdmx-library",
            "message": msg,
        }

        # Extract data if available
        if hasattr(msg, 'data') and msg.data is not None:
            df = sdmx.to_pandas(msg.data).reset_index()
            result.update({
                "data": df,
                "shape": {"rows": len(df), "cols": len(df.columns)}
            })

        # Extract structure information
        if hasattr(msg, 'structure') and msg.structure is not None:
            structure_info = _extract_structure_info(msg.structure)
            result["structure_info"] = structure_info

        return result

    except Exception as e:
        logging.error(f"Failed to read SDMX with library {file_path}: {str(e)}")
        return {"status": "error", "error_message": str(e)}


def _extract_structure_info(structure) -> Dict[str, Any]:
    """Extract structure information from SDMX message structure.

    Args:
        structure: SDMX structure object

    Returns:
        Dictionary with extracted structure info
    """
    info = {
        "dataflows": {},
        "dimensions": {},
        "attributes": {},
        "codelists": {},
        "concepts": {}
    }

    try:
        # Extract dataflows
        if hasattr(structure, 'dataflow') and structure.dataflow:
            for df_key, df in structure.dataflow.items():
                info["dataflows"][df_key] = {
                    "name": str(df.name) if df.name else df_key,
                    "description": str(df.description) if df.description else ""
                }

        # Extract dimensions from data structure definitions
        if hasattr(structure, 'datastructure') and structure.datastructure:
            for dsd_key, dsd in structure.datastructure.items():
                if hasattr(dsd, 'dimensions'):
                    for dim in dsd.dimensions:
                        dim_id = dim.id if hasattr(dim, 'id') else str(dim)
                        info["dimensions"][dim_id] = {
                            "name": str(dim.concept_identity.name) if hasattr(dim, 'concept_identity') and dim.concept_identity.name else dim_id,
                            "codelist": str(dim.local_representation.enumerated) if hasattr(dim, 'local_representation') and dim.local_representation else None
                        }

                # Extract attributes
                if hasattr(dsd, 'attributes'):
                    for attr in dsd.attributes:
                        attr_id = attr.id if hasattr(attr, 'id') else str(attr)
                        info["attributes"][attr_id] = {
                            "name": str(attr.concept_identity.name) if hasattr(attr, 'concept_identity') and attr.concept_identity.name else attr_id,
                            "attachment_level": "observation"  # Default, could be refined
                        }

        # Extract codelists
        if hasattr(structure, 'codelist') and structure.codelist:
            for cl_key, codelist in structure.codelist.items():
                codes = {}
                if hasattr(codelist, '__iter__'):
                    for code in codelist:
                        code_id = code.id if hasattr(code, 'id') else str(code)
                        code_name = str(code.name) if hasattr(code, 'name') and code.name else code_id
                        codes[code_id] = code_name
                info["codelists"][cl_key] = codes

    except Exception as e:
        logging.warning(f"Failed to extract complete structure info: {str(e)}")

    return info


def read_sdmx_file(file_path: str, metadata_path: Optional[str] = None) -> Dict[str, Any]:
    """Main function to read SDMX file, auto-detecting format.

    Args:
        file_path: Path to SDMX data file
        metadata_path: Optional path to SDMX metadata file

    Returns:
        Dictionary with parsed data and metadata
    """
    if not os.path.exists(file_path):
        return {"status": "error", "error_message": f"File not found: {file_path}"}

    # Always try sdmx library first as it handles most formats
    result = read_sdmx_with_library(file_path)

    # If sdmx library fails, try format-specific parsers
    if result.get("status") == "error":
        file_ext = os.path.splitext(file_path)[1].lower()

        if file_ext == '.csv':
            result = read_sdmx_csv(file_path)
        elif file_ext in ['.xml', '.sdmx']:
            result = read_sdmx_ml(file_path)

    # Add metadata if provided and main parsing succeeded
    if metadata_path and os.path.exists(metadata_path) and result.get("status") == "success":
        metadata_result = read_sdmx_with_library(metadata_path)
        if metadata_result.get("status") == "success":
            result["metadata_structure"] = metadata_result.get("structure_info")
        else:
            # Fallback to XML parsing for metadata
            xml_metadata = read_sdmx_ml(metadata_path)
            if xml_metadata.get("status") == "success":
                result["metadata_structure"] = xml_metadata.get("structure")

    return result


# Tool function for ADK integration
def read_sdmx_sample(file_path: str, metadata_path: str = None, rows: int = 50) -> Dict[str, Any]:
    """Read sample of SDMX file for analysis.

    Args:
        file_path: Path to SDMX file
        metadata_path: Optional metadata file path
        rows: Number of rows to sample

    Returns:
        Dictionary with sample data and structure info
    """
    try:
        result = read_sdmx_file(file_path, metadata_path)

        if result["status"] != "success":
            return result

        # Limit data sample if available
        if "data" in result and isinstance(result["data"], pd.DataFrame):
            df = result["data"]
            if len(df) > rows:
                result["data"] = df.head(rows)
                result["sample_note"] = f"Showing first {rows} rows of {len(df)} total"

            # Add sample records for analysis
            result["sample_records"] = df.head(5).to_dict("records")

        return result

    except Exception as e:
        logging.error(f"SDMX sample reading failed: {str(e)}")
        return {"status": "error", "error_message": str(e)}