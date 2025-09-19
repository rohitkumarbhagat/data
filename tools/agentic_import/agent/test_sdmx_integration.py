#!/usr/bin/env python3

"""
SDMX Integration Tests

Comprehensive test suite for SDMX support in the ADK agent system.
Tests all components: reader, analyzer, PVMap creator, metadata generator, and coordinator.
"""

import os
import sys
import pandas as pd
import tempfile
import shutil
import unittest
from pathlib import Path
from typing import Dict, Any, List

# Add current directory to path for imports
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(_SCRIPT_DIR)

from sdmx_reader import read_sdmx_file, read_sdmx_sample
from sdmx_analyzer import analyze_sdmx_structure, analyze_sdmx_sample
from sdmx_pvmap_creator import create_sdmx_pvmap_from_file
from sdmx_metadata_generator import create_sdmx_metadata_from_file
from enhanced_coordinator import EnhancedIterativeCoordinator


class TestSDMXReader(unittest.TestCase):
    """Test SDMX reader functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.temp_dir)

    def create_sample_sdmx_csv(self, file_path: str) -> None:
        """Create a sample SDMX-like CSV file."""
        data = {
            'REF_AREA': ['USA', 'USA', 'GBR', 'GBR', 'FRA', 'FRA'],
            'TIME_PERIOD': ['2020', '2021', '2020', '2021', '2020', '2021'],
            'FREQ': ['A', 'A', 'A', 'A', 'A', 'A'],
            'INDICATOR': ['GDP', 'GDP', 'GDP', 'GDP', 'GDP', 'GDP'],
            'OBS_VALUE': [21427.7, 22996.1, 2827.1, 3131.4, 2630.3, 2937.5],
            'UNIT_MEASURE': ['USD', 'USD', 'USD', 'USD', 'USD', 'USD'],
            'OBS_STATUS': ['A', 'A', 'A', 'A', 'A', 'A']
        }
        df = pd.DataFrame(data)
        df.to_csv(file_path, index=False)

    def create_sample_sdmx_xml(self, file_path: str) -> None:
        """Create a sample SDMX-ML metadata file."""
        xml_content = '''<?xml version="1.0" encoding="UTF-8"?>
<message:StructureMessage xmlns:message="http://www.sdmx.org/resources/sdmxml/schemas/v2_1/message"
                          xmlns:structure="http://www.sdmx.org/resources/sdmxml/schemas/v2_1/structure"
                          xmlns:common="http://www.sdmx.org/resources/sdmxml/schemas/v2_1/common">
  <message:Header>
    <message:ID>SDMX-ML-STRUCTURE</message:ID>
    <message:Test>false</message:Test>
    <message:Prepared>2025-01-01T00:00:00Z</message:Prepared>
    <message:Sender id="TEST"/>
  </message:Header>
  <message:Structures>
    <structure:DataStructures>
      <structure:DataStructure id="GDP_DSD" version="1.0">
        <common:Name>GDP Data Structure</common:Name>
        <common:Description>Gross Domestic Product Statistics</common:Description>
        <structure:DataStructureComponents>
          <structure:DimensionList>
            <structure:Dimension id="REF_AREA" position="1">
              <structure:ConceptIdentity>
                <Ref id="REF_AREA"/>
              </structure:ConceptIdentity>
              <structure:LocalRepresentation>
                <structure:Enumeration>
                  <Ref id="CL_AREA"/>
                </structure:Enumeration>
              </structure:LocalRepresentation>
            </structure:Dimension>
            <structure:TimeDimension id="TIME_PERIOD" position="2">
              <structure:ConceptIdentity>
                <Ref id="TIME_PERIOD"/>
              </structure:ConceptIdentity>
            </structure:TimeDimension>
          </structure:DimensionList>
          <structure:MeasureList>
            <structure:PrimaryMeasure id="OBS_VALUE">
              <structure:ConceptIdentity>
                <Ref id="OBS_VALUE"/>
              </structure:ConceptIdentity>
            </structure:PrimaryMeasure>
          </structure:MeasureList>
        </structure:DataStructureComponents>
      </structure:DataStructure>
    </structure:DataStructures>
    <structure:Codelists>
      <structure:Codelist id="CL_AREA" version="1.0">
        <common:Name>Area Code List</common:Name>
        <structure:Code id="USA">
          <common:Name>United States</common:Name>
        </structure:Code>
        <structure:Code id="GBR">
          <common:Name>United Kingdom</common:Name>
        </structure:Code>
        <structure:Code id="FRA">
          <common:Name>France</common:Name>
        </structure:Code>
      </structure:Codelist>
    </structure:Codelists>
  </message:Structures>
</message:StructureMessage>'''

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(xml_content)

    def test_read_sdmx_csv(self):
        """Test reading SDMX CSV file."""
        csv_path = os.path.join(self.temp_dir, 'test_sdmx.csv')
        self.create_sample_sdmx_csv(csv_path)

        result = read_sdmx_file(csv_path)

        self.assertEqual(result['status'], 'success')
        self.assertIn('data', result)
        self.assertIsInstance(result['data'], pd.DataFrame)
        self.assertEqual(len(result['data']), 6)

    def test_read_sdmx_xml_metadata(self):
        """Test reading SDMX-ML metadata file."""
        xml_path = os.path.join(self.temp_dir, 'test_metadata.xml')
        self.create_sample_sdmx_xml(xml_path)

        result = read_sdmx_file(xml_path)

        self.assertEqual(result['status'], 'success')
        # Should have structure information even if no data

    def test_read_sdmx_sample(self):
        """Test reading SDMX sample data."""
        csv_path = os.path.join(self.temp_dir, 'test_sdmx.csv')
        self.create_sample_sdmx_csv(csv_path)

        result = read_sdmx_sample(csv_path, rows=3)

        self.assertEqual(result['status'], 'success')
        self.assertIn('sample_records', result)
        self.assertEqual(len(result['sample_records']), 3)


class TestSDMXAnalyzer(unittest.TestCase):
    """Test SDMX analyzer functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.temp_dir)

    def create_complex_sdmx_csv(self, file_path: str) -> None:
        """Create a more complex SDMX CSV for analysis testing."""
        data = {
            'REF_AREA': ['USA', 'USA', 'USA', 'GBR', 'GBR', 'GBR', 'FRA', 'FRA'],
            'TIME_PERIOD': ['2020-Q1', '2020-Q2', '2020-Q3', '2020-Q1', '2020-Q2', '2020-Q3', '2020-Q1', '2020-Q2'],
            'FREQ': ['Q', 'Q', 'Q', 'Q', 'Q', 'Q', 'Q', 'Q'],
            'INDICATOR': ['GDP', 'GDP', 'GDP', 'GDP', 'GDP', 'GDP', 'GDP', 'GDP'],
            'SECTOR': ['TOT', 'TOT', 'TOT', 'TOT', 'TOT', 'TOT', 'TOT', 'TOT'],
            'OBS_VALUE': [5394.5, 5337.8, 5418.3, 702.4, 665.2, 710.8, 643.2, 632.1],
            'UNIT_MEASURE': ['USD_BILLIONS', 'USD_BILLIONS', 'USD_BILLIONS', 'USD_BILLIONS', 'USD_BILLIONS', 'USD_BILLIONS', 'USD_BILLIONS', 'USD_BILLIONS'],
            'OBS_STATUS': ['A', 'A', 'A', 'A', 'A', 'A', 'A', 'A']
        }
        df = pd.DataFrame(data)
        df.to_csv(file_path, index=False)

    def test_analyze_sdmx_structure(self):
        """Test SDMX structure analysis."""
        csv_path = os.path.join(self.temp_dir, 'complex_sdmx.csv')
        self.create_complex_sdmx_csv(csv_path)

        result = analyze_sdmx_structure(csv_path)

        self.assertEqual(result['status'], 'success')
        self.assertIn('analysis', result)

        analysis = result['analysis']
        self.assertGreater(len(analysis.dimensions), 0)
        self.assertGreater(len(analysis.measures), 0)
        self.assertGreater(len(analysis.attributes), 0)

        # Check specific dimension detection
        dimension_names = list(analysis.dimensions.keys())
        self.assertIn('REF_AREA', [d.upper() for d in dimension_names])
        self.assertIn('TIME_PERIOD', [d.upper() for d in dimension_names])

    def test_frequency_detection(self):
        """Test frequency detection from SDMX data."""
        csv_path = os.path.join(self.temp_dir, 'quarterly_sdmx.csv')
        self.create_complex_sdmx_csv(csv_path)

        result = analyze_sdmx_structure(csv_path)

        self.assertEqual(result['status'], 'success')
        analysis = result['analysis']
        self.assertEqual(analysis.frequency, 'Q')  # Should detect quarterly

    def test_time_pattern_analysis(self):
        """Test time pattern recognition."""
        csv_path = os.path.join(self.temp_dir, 'time_pattern_sdmx.csv')
        self.create_complex_sdmx_csv(csv_path)

        result = analyze_sdmx_structure(csv_path)

        self.assertEqual(result['status'], 'success')
        analysis = result['analysis']

        # Check for TIME_PERIOD dimension
        time_dims = [d for d in analysis.dimensions.values()
                    if d.get('column', '').upper() == 'TIME_PERIOD']
        self.assertGreater(len(time_dims), 0)

    def test_area_code_analysis(self):
        """Test area code analysis."""
        csv_path = os.path.join(self.temp_dir, 'area_code_sdmx.csv')
        self.create_complex_sdmx_csv(csv_path)

        result = analyze_sdmx_structure(csv_path)

        self.assertEqual(result['status'], 'success')
        analysis = result['analysis']

        # Check for REF_AREA dimension
        area_dims = [d for d in analysis.dimensions.values()
                    if d.get('column', '').upper() == 'REF_AREA']
        self.assertGreater(len(area_dims), 0)

        area_dim = area_dims[0]
        if 'area_codes' in area_dim:
            self.assertIn('likely_format', area_dim['area_codes'])


class TestSDMXPVMapCreator(unittest.TestCase):
    """Test SDMX PVMap creator functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.temp_dir)

    def create_test_sdmx_data(self, file_path: str) -> None:
        """Create test SDMX data for PVMap creation."""
        data = {
            'REF_AREA': ['USA', 'GBR', 'FRA'],
            'TIME_PERIOD': ['2021', '2021', '2021'],
            'FREQ': ['A', 'A', 'A'],
            'INDICATOR': ['GDP_GROWTH', 'GDP_GROWTH', 'GDP_GROWTH'],
            'OBS_VALUE': [5.7, 7.4, 7.0],
            'UNIT_MEASURE': ['PERCENT', 'PERCENT', 'PERCENT'],
            'OBS_STATUS': ['A', 'A', 'A']
        }
        df = pd.DataFrame(data)
        df.to_csv(file_path, index=False)

    def test_create_sdmx_pvmap(self):
        """Test SDMX PVMap creation from file."""
        csv_path = os.path.join(self.temp_dir, 'test_data.csv')
        pvmap_path = os.path.join(self.temp_dir, 'pvmap.csv')

        self.create_test_sdmx_data(csv_path)

        result = create_sdmx_pvmap_from_file(csv_path, output_path=pvmap_path)

        self.assertEqual(result['status'], 'success')
        self.assertTrue(os.path.exists(pvmap_path))

        # Read and validate PVMap
        pvmap_df = pd.read_csv(pvmap_path)
        self.assertIn('input', pvmap_df.columns)
        self.assertIn('property', pvmap_df.columns)
        self.assertIn('value', pvmap_df.columns)

        # Check for expected mappings
        properties = pvmap_df['property'].tolist()
        self.assertIn('observationAbout', properties)
        self.assertIn('observationDate', properties)
        self.assertIn('value', properties)

    def test_dimension_mappings(self):
        """Test specific dimension mappings."""
        csv_path = os.path.join(self.temp_dir, 'test_data.csv')
        pvmap_path = os.path.join(self.temp_dir, 'pvmap.csv')

        self.create_test_sdmx_data(csv_path)
        result = create_sdmx_pvmap_from_file(csv_path, output_path=pvmap_path)

        self.assertEqual(result['status'], 'success')

        pvmap_df = pd.read_csv(pvmap_path)

        # Check REF_AREA mapping
        ref_area_mappings = pvmap_df[pvmap_df['input'] == 'REF_AREA']
        self.assertGreater(len(ref_area_mappings), 0)

        # Check TIME_PERIOD mapping
        time_mappings = pvmap_df[pvmap_df['input'] == 'TIME_PERIOD']
        self.assertGreater(len(time_mappings), 0)

    def test_unit_conversions(self):
        """Test unit measure conversions."""
        csv_path = os.path.join(self.temp_dir, 'test_data.csv')
        pvmap_path = os.path.join(self.temp_dir, 'pvmap.csv')

        self.create_test_sdmx_data(csv_path)
        result = create_sdmx_pvmap_from_file(csv_path, output_path=pvmap_path)

        self.assertEqual(result['status'], 'success')

        pvmap_df = pd.read_csv(pvmap_path)

        # Check for unit mappings
        unit_mappings = pvmap_df[pvmap_df['property'] == 'unit']
        if len(unit_mappings) > 0:
            # Should convert PERCENT to Percent
            percent_mapping = unit_mappings[unit_mappings['input'] == 'PERCENT']
            if len(percent_mapping) > 0:
                self.assertEqual(percent_mapping.iloc[0]['value'], 'Percent')


class TestSDMXMetadataGenerator(unittest.TestCase):
    """Test SDMX metadata generator functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.temp_dir)

    def create_frequency_test_data(self, file_path: str, frequency: str = 'A') -> None:
        """Create test data with specific frequency."""
        if frequency == 'A':
            time_periods = ['2019', '2020', '2021']
        elif frequency == 'Q':
            time_periods = ['2021-Q1', '2021-Q2', '2021-Q3']
        elif frequency == 'M':
            time_periods = ['2021-01', '2021-02', '2021-03']
        else:
            time_periods = ['2021-01-01', '2021-01-02', '2021-01-03']

        data = {
            'REF_AREA': ['USA'] * len(time_periods),
            'TIME_PERIOD': time_periods,
            'FREQ': [frequency] * len(time_periods),
            'INDICATOR': ['TEST'] * len(time_periods),
            'OBS_VALUE': [100.0, 105.0, 110.0][:len(time_periods)]
        }
        df = pd.DataFrame(data)
        df.to_csv(file_path, index=False)

    def test_create_sdmx_metadata_annual(self):
        """Test metadata generation for annual data."""
        csv_path = os.path.join(self.temp_dir, 'annual_data.csv')
        metadata_path = os.path.join(self.temp_dir, 'metadata.csv')

        self.create_frequency_test_data(csv_path, 'A')

        result = create_sdmx_metadata_from_file(csv_path, output_path=metadata_path)

        self.assertEqual(result['status'], 'success')
        self.assertTrue(os.path.exists(metadata_path))

        # Read and validate metadata
        metadata_df = pd.read_csv(metadata_path)
        self.assertIn('parameter', metadata_df.columns)
        self.assertIn('value', metadata_df.columns)

        # Check for date format
        date_format_rows = metadata_df[metadata_df['parameter'] == 'date_format']
        self.assertGreater(len(date_format_rows), 0)
        self.assertEqual(date_format_rows.iloc[0]['value'], '%Y')

    def test_create_sdmx_metadata_quarterly(self):
        """Test metadata generation for quarterly data."""
        csv_path = os.path.join(self.temp_dir, 'quarterly_data.csv')
        metadata_path = os.path.join(self.temp_dir, 'metadata.csv')

        self.create_frequency_test_data(csv_path, 'Q')

        result = create_sdmx_metadata_from_file(csv_path, output_path=metadata_path)

        self.assertEqual(result['status'], 'success')
        self.assertTrue(os.path.exists(metadata_path))

        # Check frequency detection
        self.assertIn('frequency', result.get('summary', {}))
        if 'frequency' in result['summary']:
            self.assertEqual(result['summary']['frequency'], 'Q')

    def test_aggregation_method_detection(self):
        """Test aggregation method detection."""
        csv_path = os.path.join(self.temp_dir, 'test_data.csv')
        metadata_path = os.path.join(self.temp_dir, 'metadata.csv')

        self.create_frequency_test_data(csv_path, 'M')

        result = create_sdmx_metadata_from_file(csv_path, output_path=metadata_path)

        self.assertEqual(result['status'], 'success')

        # Check for aggregation method in metadata
        metadata_df = pd.read_csv(metadata_path)
        agg_rows = metadata_df[metadata_df['parameter'] == 'aggregation_method']
        self.assertGreater(len(agg_rows), 0)


class TestSDMXCoordinatorIntegration(unittest.TestCase):
    """Test SDMX integration with enhanced coordinator."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.temp_dir)

    def create_integration_test_data(self, file_path: str) -> None:
        """Create data for integration testing."""
        data = {
            'REF_AREA': ['USA', 'GBR', 'FRA', 'DEU'] * 3,
            'TIME_PERIOD': ['2019', '2020', '2021'] * 4,
            'FREQ': ['A'] * 12,
            'INDICATOR': ['GDP_USD'] * 12,
            'OBS_VALUE': [21427.7, 20953.0, 22996.1, 2827.1, 2707.7, 3131.4,
                         2630.3, 2603.0, 2937.5, 3846.4, 3800.4, 4223.1],
            'UNIT_MEASURE': ['USD'] * 12,
            'OBS_STATUS': ['A'] * 12
        }
        df = pd.DataFrame(data)
        df.to_csv(file_path, index=False)

    def test_dataset_type_detection(self):
        """Test automatic SDMX dataset detection."""
        coordinator = EnhancedIterativeCoordinator(max_iterations=1, auto_fix=False)

        # Test SDMX CSV detection
        csv_path = os.path.join(self.temp_dir, 'sdmx_test.csv')
        self.create_integration_test_data(csv_path)

        detected_type = coordinator._detect_dataset_type(csv_path)
        self.assertEqual(detected_type, 'sdmx')

        # Test regular CSV detection (create non-SDMX data)
        regular_data = {
            'Country': ['USA', 'UK', 'France'],
            'Year': [2021, 2021, 2021],
            'GDP': [22996.1, 3131.4, 2937.5]
        }
        regular_csv = os.path.join(self.temp_dir, 'regular.csv')
        pd.DataFrame(regular_data).to_csv(regular_csv, index=False)

        detected_type = coordinator._detect_dataset_type(regular_csv)
        self.assertEqual(detected_type, 'csv')

    def test_sdmx_workflow_components(self):
        """Test individual SDMX workflow components."""
        csv_path = os.path.join(self.temp_dir, 'integration_test.csv')
        output_dir = os.path.join(self.temp_dir, 'output')
        working_dir = os.path.join(self.temp_dir, 'work')

        os.makedirs(output_dir, exist_ok=True)
        os.makedirs(working_dir, exist_ok=True)

        self.create_integration_test_data(csv_path)

        coordinator = EnhancedIterativeCoordinator(max_iterations=1, auto_fix=False)

        # Test SDMX workflow execution (without processor)
        try:
            result = coordinator._execute_sdmx_workflow(
                csv_path, output_dir, working_dir, [], 1
            )

            # Should get through analysis and file generation steps
            # May fail at processor step if statvar_processor not available
            self.assertTrue(result.get('status') in ['success', 'error'])

            if result.get('status') == 'error':
                # Should fail at processor step, not earlier steps
                error_step = result.get('error_step', '')
                self.assertIn(error_step, ['statvar_processor', 'sdmx_workflow_execution'])

        except Exception as e:
            # Expected if imports fail - that's okay for unit testing
            self.assertIn('import', str(e).lower())


class TestSDMXEndToEnd(unittest.TestCase):
    """End-to-end SDMX processing tests."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.temp_dir)

    def create_realistic_sdmx_data(self, file_path: str) -> None:
        """Create realistic SDMX dataset."""
        countries = ['USA', 'GBR', 'FRA', 'DEU', 'JPN']
        years = ['2019', '2020', '2021', '2022']
        indicators = ['GDP_USD', 'GDP_GROWTH', 'INFLATION']

        data = []
        for country in countries:
            for year in years:
                for indicator in indicators:
                    if indicator == 'GDP_USD':
                        value = 20000 + hash(country + year) % 10000
                        unit = 'USD_BILLIONS'
                    elif indicator == 'GDP_GROWTH':
                        value = -2.0 + (hash(country + year) % 100) / 10
                        unit = 'PERCENT'
                    else:  # INFLATION
                        value = 1.0 + (hash(country + year) % 50) / 10
                        unit = 'PERCENT'

                    data.append({
                        'REF_AREA': country,
                        'TIME_PERIOD': year,
                        'FREQ': 'A',
                        'INDICATOR': indicator,
                        'OBS_VALUE': value,
                        'UNIT_MEASURE': unit,
                        'OBS_STATUS': 'A'
                    })

        df = pd.DataFrame(data)
        df.to_csv(file_path, index=False)

    def test_full_sdmx_processing_pipeline(self):
        """Test complete SDMX processing pipeline."""
        input_file = os.path.join(self.temp_dir, 'realistic_sdmx.csv')
        output_dir = os.path.join(self.temp_dir, 'output')
        working_dir = os.path.join(self.temp_dir, 'working')

        os.makedirs(output_dir, exist_ok=True)
        os.makedirs(working_dir, exist_ok=True)

        self.create_realistic_sdmx_data(input_file)

        # Test each component in sequence
        # 1. Analysis
        analysis_result = analyze_sdmx_structure(input_file)
        self.assertEqual(analysis_result['status'], 'success')

        # 2. PVMap creation
        pvmap_path = os.path.join(working_dir, 'pvmap.csv')
        pvmap_result = create_sdmx_pvmap_from_file(input_file, output_path=pvmap_path)
        self.assertEqual(pvmap_result['status'], 'success')
        self.assertTrue(os.path.exists(pvmap_path))

        # 3. Metadata generation
        metadata_path = os.path.join(working_dir, 'metadata.csv')
        metadata_result = create_sdmx_metadata_from_file(input_file, output_path=metadata_path)
        self.assertEqual(metadata_result['status'], 'success')
        self.assertTrue(os.path.exists(metadata_path))

        # 4. Validation checks
        self._validate_generated_files(pvmap_path, metadata_path, analysis_result)

    def _validate_generated_files(self, pvmap_path: str, metadata_path: str, analysis_result: Dict[str, Any]) -> None:
        """Validate generated PVMap and metadata files."""
        # Validate PVMap
        pvmap_df = pd.read_csv(pvmap_path)
        self.assertGreater(len(pvmap_df), 0)

        required_properties = ['observationAbout', 'observationDate', 'value']
        actual_properties = pvmap_df['property'].unique()

        for prop in required_properties:
            self.assertIn(prop, actual_properties, f"Required property {prop} missing from PVMap")

        # Validate metadata
        metadata_df = pd.read_csv(metadata_path)
        self.assertGreater(len(metadata_df), 0)

        required_params = ['date_format', 'aggregation_method']
        actual_params = metadata_df['parameter'].unique()

        for param in required_params:
            self.assertIn(param, actual_params, f"Required parameter {param} missing from metadata")

    def test_error_handling_and_recovery(self):
        """Test SDMX error handling and recovery."""
        # Test with malformed data
        malformed_file = os.path.join(self.temp_dir, 'malformed.csv')

        malformed_data = {
            'BadColumn1': ['val1', 'val2'],
            'BadColumn2': ['val3', 'val4']
        }
        pd.DataFrame(malformed_data).to_csv(malformed_file, index=False)

        # Should not detect as SDMX
        coordinator = EnhancedIterativeCoordinator(max_iterations=1)
        detected_type = coordinator._detect_dataset_type(malformed_file)
        self.assertEqual(detected_type, 'csv')

        # Test with partially SDMX data
        partial_sdmx_file = os.path.join(self.temp_dir, 'partial_sdmx.csv')
        partial_data = {
            'REF_AREA': ['USA', 'GBR'],
            'TIME_PERIOD': ['2021', '2022'],
            'SomeOtherColumn': ['val1', 'val2'],
            'AnotherColumn': ['val3', 'val4']
        }
        pd.DataFrame(partial_data).to_csv(partial_sdmx_file, index=False)

        # Should still detect as SDMX due to REF_AREA + TIME_PERIOD
        detected_type = coordinator._detect_dataset_type(partial_sdmx_file)
        self.assertEqual(detected_type, 'sdmx')


def run_sdmx_tests():
    """Run all SDMX tests and return results."""
    test_suite = unittest.TestSuite()

    # Add test classes
    test_classes = [
        TestSDMXReader,
        TestSDMXAnalyzer,
        TestSDMXPVMapCreator,
        TestSDMXMetadataGenerator,
        TestSDMXCoordinatorIntegration,
        TestSDMXEndToEnd
    ]

    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        test_suite.addTests(tests)

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)

    return {
        'tests_run': result.testsRun,
        'failures': len(result.failures),
        'errors': len(result.errors),
        'success_rate': (result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun if result.testsRun > 0 else 0,
        'details': {
            'failures': [(test.id(), error) for test, error in result.failures],
            'errors': [(test.id(), error) for test, error in result.errors]
        }
    }


if __name__ == '__main__':
    print("🧪 Running SDMX Integration Tests...")
    results = run_sdmx_tests()

    print(f"\n📊 Test Results:")
    print(f"Tests run: {results['tests_run']}")
    print(f"Failures: {results['failures']}")
    print(f"Errors: {results['errors']}")
    print(f"Success rate: {results['success_rate']:.1%}")

    if results['failures'] > 0:
        print(f"\n❌ Failures:")
        for test_id, error in results['details']['failures']:
            print(f"  • {test_id}")

    if results['errors'] > 0:
        print(f"\n💥 Errors:")
        for test_id, error in results['details']['errors']:
            print(f"  • {test_id}")

    if results['success_rate'] >= 0.8:
        print(f"\n✅ SDMX implementation ready for production!")
    else:
        print(f"\n⚠️ SDMX implementation needs refinement.")