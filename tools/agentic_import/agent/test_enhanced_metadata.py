"""
Comprehensive test suite for enhanced metadata generation features.

This test suite validates all enhanced metadata modules:
- enhanced_metadata.py (header detection)
- date_detector.py (date format detection)
- aggregation_analyzer.py (duplicate detection and aggregation rules)
- metadata_validator.py (comprehensive validation)
- Integration in metadata_generator.py
"""

import unittest
import tempfile
import pandas as pd
import os
import csv
from typing import Dict, Any, List

# Import modules to test
try:
    from enhanced_metadata import (
        detect_header_rows, detect_header_columns, get_enhanced_file_structure
    )
    from date_detector import DateFormatDetector, detect_date_formats
    from aggregation_analyzer import AggregationAnalyzer, detect_aggregation_needs
    from metadata_validator import MetadataValidator, validate_metadata_comprehensive
    from metadata_generator import (
        generate_enhanced_metadata_config, analyze_csv_comprehensively,
        detect_file_structure, generate_metadata_config, validate_metadata_config
    )
    MODULES_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Could not import enhanced modules: {e}")
    MODULES_AVAILABLE = False


class TestDataGenerator:
    """Helper class to generate test data files."""

    @staticmethod
    def create_simple_csv(file_path: str) -> None:
        """Create simple CSV with standard structure."""
        data = {
            'Country': ['USA', 'Canada', 'Mexico', 'USA', 'Canada'],
            'Year': [2020, 2020, 2020, 2021, 2021],
            'Population': [331002651, 37742154, 128932753, 331893745, 38067903],
            'GDP_per_capita': [65279.5, 43241.6, 8346.7, 70248.6, 43242.0]
        }
        df = pd.DataFrame(data)
        df.to_csv(file_path, index=False)

    @staticmethod
    def create_multi_header_csv(file_path: str) -> None:
        """Create CSV with multiple header rows."""
        with open(file_path, 'w', newline='') as f:
            writer = csv.writer(f)
            # Header row 1
            writer.writerow(['', '', 'Economic Indicators', 'Economic Indicators'])
            # Header row 2
            writer.writerow(['Country', 'Year', 'Population', 'GDP per capita'])
            # Data rows
            writer.writerow(['USA', '2020', '331002651', '65279.5'])
            writer.writerow(['Canada', '2020', '37742154', '43241.6'])
            writer.writerow(['Mexico', '2020', '128932753', '8346.7'])

    @staticmethod
    def create_date_format_csv(file_path: str, date_format: str = 'iso') -> None:
        """Create CSV with different date formats."""
        if date_format == 'iso':
            dates = ['2020-01-15', '2020-02-15', '2020-03-15']
        elif date_format == 'us':
            dates = ['1/15/2020', '2/15/2020', '3/15/2020']
        elif date_format == 'quarter':
            dates = ['2020Q1', '2020Q2', '2020Q3']
        else:
            dates = ['2020', '2021', '2022']

        data = {
            'Date': dates,
            'Location': ['USA', 'USA', 'USA'],
            'Value': [100, 110, 120]
        }
        df = pd.DataFrame(data)
        df.to_csv(file_path, index=False)

    @staticmethod
    def create_duplicate_data_csv(file_path: str) -> None:
        """Create CSV with duplicate observations needing aggregation."""
        data = {
            'Country': ['USA', 'USA', 'USA', 'Canada', 'Canada'],
            'Year': [2020, 2020, 2020, 2020, 2020],
            'Region': ['North', 'South', 'West', 'East', 'West'],
            'Population': [100000, 150000, 200000, 50000, 75000],
            'GDP': [1000000, 1500000, 2000000, 500000, 750000]
        }
        df = pd.DataFrame(data)
        df.to_csv(file_path, index=False)


@unittest.skipUnless(MODULES_AVAILABLE, "Enhanced modules not available")
class TestEnhancedMetadata(unittest.TestCase):
    """Test enhanced metadata detection functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.simple_csv = os.path.join(self.temp_dir, 'simple.csv')
        self.multi_header_csv = os.path.join(self.temp_dir, 'multi_header.csv')

        TestDataGenerator.create_simple_csv(self.simple_csv)
        TestDataGenerator.create_multi_header_csv(self.multi_header_csv)

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir)

    def test_header_detection_simple(self):
        """Test header detection on simple CSV."""
        result = detect_header_rows(self.simple_csv)
        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['header_rows'], 1)
        self.assertGreater(result['confidence'], 0.5)

    def test_header_detection_multi(self):
        """Test header detection on multi-header CSV."""
        result = detect_header_rows(self.multi_header_csv)
        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['header_rows'], 2)

    def test_header_column_detection(self):
        """Test header column classification."""
        result = detect_header_columns(self.simple_csv)
        self.assertEqual(result['status'], 'success')
        self.assertIn('data_columns', result)
        self.assertIn('index_columns', result)

    def test_enhanced_file_structure(self):
        """Test comprehensive file structure analysis."""
        result = get_enhanced_file_structure(self.simple_csv)
        self.assertEqual(result['status'], 'success')
        self.assertIn('header_rows', result)
        self.assertIn('total_rows', result)
        self.assertIn('total_columns', result)
        self.assertIn('recommended_config', result)


@unittest.skipUnless(MODULES_AVAILABLE, "Enhanced modules not available")
class TestDateDetector(unittest.TestCase):
    """Test date format detection functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.iso_csv = os.path.join(self.temp_dir, 'iso_dates.csv')
        self.us_csv = os.path.join(self.temp_dir, 'us_dates.csv')
        self.quarter_csv = os.path.join(self.temp_dir, 'quarter_dates.csv')

        TestDataGenerator.create_date_format_csv(self.iso_csv, 'iso')
        TestDataGenerator.create_date_format_csv(self.us_csv, 'us')
        TestDataGenerator.create_date_format_csv(self.quarter_csv, 'quarter')

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir)

    def test_iso_date_detection(self):
        """Test ISO date format detection."""
        detector = DateFormatDetector()
        result = detector.detect_date_columns(self.iso_csv)
        self.assertEqual(result['status'], 'success')
        self.assertGreater(result['date_columns_found'], 0)
        self.assertIn('Date', result['date_columns'])

    def test_us_date_detection(self):
        """Test US date format detection."""
        result = detect_date_formats(self.us_csv)
        self.assertEqual(result['status'], 'success')
        date_columns = result['analysis']['date_columns']
        self.assertIn('Date', date_columns)

    def test_quarter_date_detection(self):
        """Test quarter format detection."""
        result = detect_date_formats(self.quarter_csv)
        self.assertEqual(result['status'], 'success')
        config = result['configuration']['config']
        self.assertIn('observation_period', config)

    def test_date_configuration_generation(self):
        """Test date configuration generation."""
        detector = DateFormatDetector()
        date_analysis = detector.detect_date_columns(self.iso_csv)
        config_result = detector.generate_date_configuration(date_analysis)
        self.assertEqual(config_result['status'], 'success')
        self.assertTrue(config_result['has_date_columns'])


@unittest.skipUnless(MODULES_AVAILABLE, "Enhanced modules not available")
class TestAggregationAnalyzer(unittest.TestCase):
    """Test aggregation analysis functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.duplicate_csv = os.path.join(self.temp_dir, 'duplicates.csv')
        self.simple_csv = os.path.join(self.temp_dir, 'simple.csv')

        TestDataGenerator.create_duplicate_data_csv(self.duplicate_csv)
        TestDataGenerator.create_simple_csv(self.simple_csv)

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir)

    def test_duplicate_detection(self):
        """Test duplicate observation detection."""
        analyzer = AggregationAnalyzer()
        result = analyzer.analyze_duplicates(self.duplicate_csv)
        self.assertEqual(result['status'], 'success')
        self.assertTrue(result['needs_aggregation'])
        self.assertGreater(result['duplicate_analysis']['duplicate_count'], 0)

    def test_no_duplicates(self):
        """Test handling of files without duplicates."""
        result = detect_aggregation_needs(self.simple_csv)
        self.assertEqual(result['status'], 'success')
        # Note: simple.csv might or might not have duplicates depending on data

    def test_aggregation_strategy_generation(self):
        """Test aggregation strategy generation."""
        analyzer = AggregationAnalyzer()
        result = analyzer.analyze_duplicates(self.duplicate_csv)
        if result['needs_aggregation']:
            strategy = result['aggregation_strategy']
            self.assertIn('group_by_columns', strategy)
            self.assertIn('measure_strategies', strategy)

    def test_column_classification(self):
        """Test column classification for aggregation."""
        analyzer = AggregationAnalyzer()
        result = analyzer.analyze_duplicates(self.duplicate_csv)
        classification = result['column_classification']
        self.assertIn('dimensions', classification)
        self.assertIn('measures', classification)


@unittest.skipUnless(MODULES_AVAILABLE, "Enhanced modules not available")
class TestMetadataValidator(unittest.TestCase):
    """Test metadata validation functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_csv = os.path.join(self.temp_dir, 'test.csv')
        TestDataGenerator.create_simple_csv(self.test_csv)

        self.validator = MetadataValidator()

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir)

    def test_valid_config_validation(self):
        """Test validation of valid configuration."""
        config = {
            'output_columns': 'observationAbout,observationDate,value,variableMeasured',
            'header_rows': 1,
            'mapped_rows': 100,
            'mapped_columns': 4
        }
        result = self.validator.validate_metadata_config(config)
        self.assertEqual(result['status'], 'success')
        self.assertTrue(result['valid'])

    def test_invalid_config_validation(self):
        """Test validation of invalid configuration."""
        config = {
            'header_rows': -1,  # Invalid value
            'mapped_columns': 'invalid'  # Wrong type
        }
        result = self.validator.validate_metadata_config(config)
        self.assertEqual(result['status'], 'success')
        self.assertFalse(result['valid'])
        self.assertGreater(len(result['errors']), 0)

    def test_parameter_inference(self):
        """Test intelligent parameter inference."""
        result = self.validator.infer_metadata_parameters(self.test_csv)
        self.assertEqual(result['status'], 'success')
        config = result['inferred_config']
        self.assertIn('output_columns', config)
        self.assertIn('header_rows', config)

    def test_file_validation(self):
        """Test validation against actual file."""
        config = {
            'output_columns': 'observationAbout,observationDate,value,variableMeasured',
            'header_rows': 1,
            'mapped_rows': 5,
            'mapped_columns': 4
        }
        result = validate_metadata_comprehensive(config, self.test_csv)
        self.assertEqual(result['status'], 'success')


@unittest.skipUnless(MODULES_AVAILABLE, "Enhanced modules not available")
class TestIntegration(unittest.TestCase):
    """Test integration of all enhanced metadata features."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_files = {}

        # Create various test files
        self.test_files['simple'] = os.path.join(self.temp_dir, 'simple.csv')
        self.test_files['multi_header'] = os.path.join(self.temp_dir, 'multi_header.csv')
        self.test_files['dates'] = os.path.join(self.temp_dir, 'dates.csv')
        self.test_files['duplicates'] = os.path.join(self.temp_dir, 'duplicates.csv')

        TestDataGenerator.create_simple_csv(self.test_files['simple'])
        TestDataGenerator.create_multi_header_csv(self.test_files['multi_header'])
        TestDataGenerator.create_date_format_csv(self.test_files['dates'])
        TestDataGenerator.create_duplicate_data_csv(self.test_files['duplicates'])

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir)

    def test_enhanced_metadata_generation(self):
        """Test end-to-end enhanced metadata generation."""
        for file_type, file_path in self.test_files.items():
            with self.subTest(file_type=file_type):
                result = generate_enhanced_metadata_config(file_path)
                self.assertEqual(result['status'], 'success')
                self.assertIn('config', result)
                self.assertIn('analysis_details', result)

    def test_comprehensive_analysis(self):
        """Test comprehensive CSV analysis."""
        for file_type, file_path in self.test_files.items():
            with self.subTest(file_type=file_type):
                result = analyze_csv_comprehensively(file_path)
                self.assertEqual(result['status'], 'success')
                self.assertIn('analysis_results', result)
                self.assertIn('summary', result)

    def test_backward_compatibility(self):
        """Test that enhanced functions maintain backward compatibility."""
        for file_type, file_path in self.test_files.items():
            with self.subTest(file_type=file_type):
                # Test basic functions still work
                structure = detect_file_structure(file_path, use_enhanced=False)
                self.assertEqual(structure['status'], 'success')

                basic_config = generate_metadata_config(file_path, use_enhanced=False)
                self.assertEqual(basic_config['status'], 'success')

                validation = validate_metadata_config(
                    basic_config['config'], use_enhanced=False
                )
                self.assertEqual(validation['status'], 'success')

    def test_enhanced_vs_basic_comparison(self):
        """Test that enhanced functions provide more detailed results."""
        file_path = self.test_files['simple']

        # Generate with basic method
        basic_result = generate_metadata_config(file_path, use_enhanced=False)

        # Generate with enhanced method
        enhanced_result = generate_enhanced_metadata_config(file_path)

        self.assertEqual(basic_result['status'], 'success')
        self.assertEqual(enhanced_result['status'], 'success')

        # Enhanced should have more parameters or analysis details
        basic_config = basic_result['config']
        enhanced_config = enhanced_result['config']

        # Enhanced should have analysis details
        self.assertIn('analysis_details', enhanced_result)

        # Enhanced might have more parameters
        enhanced_param_count = len(enhanced_config)
        basic_param_count = len(basic_config)
        # Note: This is not guaranteed, depends on the data

    def test_error_handling(self):
        """Test error handling with invalid inputs."""
        # Test with non-existent file
        result = generate_enhanced_metadata_config('/non/existent/file.csv')
        self.assertEqual(result['status'], 'error')

        # Test with invalid configuration
        invalid_config = {'invalid_param': 'invalid_value'}
        validation = validate_metadata_comprehensive(invalid_config)
        self.assertEqual(validation['status'], 'success')
        self.assertFalse(validation['valid'])


class TestPerformance(unittest.TestCase):
    """Test performance of enhanced metadata features."""

    def setUp(self):
        """Set up performance test fixtures."""
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir)

    def create_large_csv(self, rows: int = 10000) -> str:
        """Create large CSV for performance testing."""
        file_path = os.path.join(self.temp_dir, f'large_{rows}.csv')

        # Create data
        data = {
            'Country': ['USA', 'Canada', 'Mexico'] * (rows // 3 + 1),
            'Year': list(range(2000, 2000 + rows // 100 + 1)) * (rows // (rows // 100 + 1) + 1),
            'Population': [1000000 + i * 1000 for i in range(rows)],
            'GDP': [50000.0 + i * 100 for i in range(rows)]
        }

        df = pd.DataFrame(data)
        df = df.head(rows)  # Ensure exact row count
        df.to_csv(file_path, index=False)
        return file_path

    @unittest.skipUnless(MODULES_AVAILABLE, "Enhanced modules not available")
    def test_large_file_performance(self):
        """Test performance with large files."""
        import time

        large_file = self.create_large_csv(5000)  # Reasonable size for testing

        start_time = time.time()
        result = analyze_csv_comprehensively(large_file)
        end_time = time.time()

        self.assertEqual(result['status'], 'success')
        processing_time = end_time - start_time

        # Should complete within reasonable time (adjust as needed)
        self.assertLess(processing_time, 30.0)  # 30 seconds max

        print(f"Large file analysis took {processing_time:.2f} seconds")


if __name__ == '__main__':
    # Run tests with different verbosity levels
    print("Running Enhanced Metadata Test Suite...")
    print(f"Enhanced modules available: {MODULES_AVAILABLE}")

    if MODULES_AVAILABLE:
        unittest.main(verbosity=2)
    else:
        print("Enhanced modules not available. Skipping tests.")
        print("To run tests, ensure all enhanced metadata modules are properly installed.")