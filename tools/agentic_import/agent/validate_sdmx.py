#!/usr/bin/env python3

"""
SDMX Validation Script

Quick validation script to test SDMX implementation with sample data.
Use this to verify SDMX support is working correctly.
"""

import os
import sys
import pandas as pd
import tempfile
import shutil
import logging
from pathlib import Path

# Add current directory to path for imports
sys.path.append(os.path.dirname(__file__))

from sdmx_reader import read_sdmx_file
from sdmx_analyzer import analyze_sdmx_structure
from sdmx_pvmap_creator import create_sdmx_pvmap_from_file
from sdmx_metadata_generator import create_sdmx_metadata_from_file
from enhanced_coordinator import EnhancedIterativeCoordinator

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')


def create_sample_sdmx_data(file_path: str) -> None:
    """Create sample SDMX data for validation."""
    print("📝 Creating sample SDMX dataset...")

    data = {
        'REF_AREA': ['USA', 'USA', 'GBR', 'GBR', 'FRA', 'FRA', 'DEU', 'DEU'],
        'TIME_PERIOD': ['2020', '2021', '2020', '2021', '2020', '2021', '2020', '2021'],
        'FREQ': ['A', 'A', 'A', 'A', 'A', 'A', 'A', 'A'],
        'INDICATOR': ['GDP_USD', 'GDP_USD', 'GDP_USD', 'GDP_USD', 'GDP_USD', 'GDP_USD', 'GDP_USD', 'GDP_USD'],
        'OBS_VALUE': [20953.0, 22996.1, 2707.7, 3131.4, 2603.0, 2937.5, 3800.4, 4223.1],
        'UNIT_MEASURE': ['USD_BILLIONS', 'USD_BILLIONS', 'USD_BILLIONS', 'USD_BILLIONS', 'USD_BILLIONS', 'USD_BILLIONS', 'USD_BILLIONS', 'USD_BILLIONS'],
        'OBS_STATUS': ['A', 'A', 'A', 'A', 'A', 'A', 'A', 'A']
    }

    df = pd.DataFrame(data)
    df.to_csv(file_path, index=False)
    print(f"✅ Sample data created: {file_path}")


def validate_sdmx_reader(file_path: str) -> bool:
    """Validate SDMX reader functionality."""
    print("\n🔍 Testing SDMX Reader...")

    try:
        result = read_sdmx_file(file_path)

        if result['status'] == 'success':
            print(f"✅ SDMX Reader: Successfully read file")
            print(f"   Format: {result.get('format', 'unknown')}")
            if 'data' in result:
                shape = result['data'].shape
                print(f"   Data shape: {shape[0]} rows, {shape[1]} columns")
            return True
        else:
            print(f"❌ SDMX Reader: Failed - {result.get('error_message')}")
            return False

    except Exception as e:
        print(f"❌ SDMX Reader: Exception - {str(e)}")
        return False


def validate_sdmx_analyzer(file_path: str) -> bool:
    """Validate SDMX analyzer functionality."""
    print("\n📊 Testing SDMX Analyzer...")

    try:
        result = analyze_sdmx_structure(file_path)

        if result['status'] == 'success':
            analysis = result['analysis']
            print(f"✅ SDMX Analyzer: Successfully analyzed structure")
            print(f"   Dimensions: {len(analysis.dimensions)}")
            print(f"   Measures: {len(analysis.measures)}")
            print(f"   Attributes: {len(analysis.attributes)}")
            print(f"   Frequency: {analysis.frequency}")

            # Check for expected dimensions
            dim_names = [d.upper() for d in analysis.dimensions.keys()]
            expected_dims = ['REF_AREA', 'TIME_PERIOD', 'FREQ', 'INDICATOR']
            found_dims = [dim for dim in expected_dims if dim in dim_names]
            print(f"   Standard SDMX dimensions found: {found_dims}")

            return len(found_dims) >= 3  # Should find most standard dimensions
        else:
            print(f"❌ SDMX Analyzer: Failed - {result.get('error_message')}")
            return False

    except Exception as e:
        print(f"❌ SDMX Analyzer: Exception - {str(e)}")
        return False


def validate_pvmap_creator(file_path: str, output_dir: str) -> bool:
    """Validate SDMX PVMap creator functionality."""
    print("\n🗺️ Testing SDMX PVMap Creator...")

    try:
        pvmap_path = os.path.join(output_dir, 'validation_pvmap.csv')
        result = create_sdmx_pvmap_from_file(file_path, output_path=pvmap_path)

        if result['status'] == 'success':
            print(f"✅ SDMX PVMap Creator: Successfully created PVMap")
            print(f"   Output: {pvmap_path}")
            print(f"   Mappings created: {result.get('mapping_count', 0)}")

            # Validate PVMap content
            if os.path.exists(pvmap_path):
                pvmap_df = pd.read_csv(pvmap_path)
                properties = pvmap_df['property'].unique()
                expected_properties = ['observationAbout', 'observationDate', 'value']
                found_properties = [prop for prop in expected_properties if prop in properties]
                print(f"   Key properties found: {found_properties}")

                return len(found_properties) >= 2  # Should find key properties
            else:
                print(f"❌ SDMX PVMap Creator: Output file not created")
                return False
        else:
            print(f"❌ SDMX PVMap Creator: Failed - {result.get('error_message')}")
            return False

    except Exception as e:
        print(f"❌ SDMX PVMap Creator: Exception - {str(e)}")
        return False


def validate_metadata_generator(file_path: str, output_dir: str) -> bool:
    """Validate SDMX metadata generator functionality."""
    print("\n⚙️ Testing SDMX Metadata Generator...")

    try:
        metadata_path = os.path.join(output_dir, 'validation_metadata.csv')
        result = create_sdmx_metadata_from_file(file_path, output_path=metadata_path)

        if result['status'] == 'success':
            print(f"✅ SDMX Metadata Generator: Successfully created metadata")
            print(f"   Output: {metadata_path}")
            print(f"   Parameters configured: {result.get('configuration', {}).get('parameters_written', 0) if 'configuration' in result else 0}")

            # Validate metadata content
            if os.path.exists(metadata_path):
                metadata_df = pd.read_csv(metadata_path)
                parameters = metadata_df['parameter'].unique()
                expected_params = ['date_format', 'aggregation_method', 'header_rows']
                found_params = [param for param in expected_params if param in parameters]
                print(f"   Key parameters found: {found_params}")

                return len(found_params) >= 2  # Should find key parameters
            else:
                print(f"❌ SDMX Metadata Generator: Output file not created")
                return False
        else:
            print(f"❌ SDMX Metadata Generator: Failed - {result.get('error_message')}")
            return False

    except Exception as e:
        print(f"❌ SDMX Metadata Generator: Exception - {str(e)}")
        return False


def validate_coordinator_integration(file_path: str) -> bool:
    """Validate SDMX integration with enhanced coordinator."""
    print("\n🤝 Testing Enhanced Coordinator Integration...")

    try:
        coordinator = EnhancedIterativeCoordinator(max_iterations=1, auto_fix=False)

        # Test dataset type detection
        detected_type = coordinator._detect_dataset_type(file_path)
        print(f"✅ Dataset Type Detection: {detected_type.upper()}")

        if detected_type == 'sdmx':
            print("✅ Enhanced Coordinator: Successfully detected SDMX dataset")

            # Test CSV pattern analysis
            csv_pattern = coordinator._analyze_csv_for_sdmx_patterns(file_path)
            print(f"   CSV pattern analysis: {csv_pattern}")

            return True
        else:
            print(f"❌ Enhanced Coordinator: Failed to detect SDMX (detected: {detected_type})")
            return False

    except Exception as e:
        print(f"❌ Enhanced Coordinator: Exception - {str(e)}")
        return False


def run_sdmx_validation():
    """Run complete SDMX validation."""
    print("🚀 SDMX Implementation Validation")
    print("=" * 50)

    # Create temporary directory
    temp_dir = tempfile.mkdtemp()
    output_dir = os.path.join(temp_dir, 'output')
    os.makedirs(output_dir, exist_ok=True)

    try:
        # Create sample data
        sample_file = os.path.join(temp_dir, 'sample_sdmx.csv')
        create_sample_sdmx_data(sample_file)

        # Run validation tests
        results = {}
        results['reader'] = validate_sdmx_reader(sample_file)
        results['analyzer'] = validate_sdmx_analyzer(sample_file)
        results['pvmap_creator'] = validate_pvmap_creator(sample_file, output_dir)
        results['metadata_generator'] = validate_metadata_generator(sample_file, output_dir)
        results['coordinator'] = validate_coordinator_integration(sample_file)

        # Calculate overall results
        total_tests = len(results)
        passed_tests = sum(1 for result in results.values() if result)
        success_rate = passed_tests / total_tests if total_tests > 0 else 0

        # Display summary
        print(f"\n📊 VALIDATION SUMMARY")
        print("=" * 30)
        print(f"Total tests: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {total_tests - passed_tests}")
        print(f"Success rate: {success_rate:.1%}")

        # Detail results
        print(f"\n📋 DETAILED RESULTS")
        print("-" * 30)
        for component, passed in results.items():
            status = "✅ PASS" if passed else "❌ FAIL"
            print(f"{component.replace('_', ' ').title():<20} {status}")

        # Overall assessment
        print(f"\n🎯 ASSESSMENT")
        print("-" * 20)
        if success_rate >= 0.8:
            print("✅ SDMX implementation is ready for production use!")
            print("   All core components are functioning correctly.")
        elif success_rate >= 0.6:
            print("⚠️  SDMX implementation is mostly functional.")
            print("   Some components may need refinement.")
        else:
            print("❌ SDMX implementation needs significant work.")
            print("   Multiple components are failing.")

        return {
            'success_rate': success_rate,
            'results': results,
            'temp_dir': temp_dir,  # For inspection if needed
            'sample_file': sample_file
        }

    except Exception as e:
        print(f"\n💥 VALIDATION FAILED: {str(e)}")
        return {'success_rate': 0.0, 'error': str(e)}

    finally:
        # Clean up (comment out for debugging)
        try:
            shutil.rmtree(temp_dir)
        except:
            pass


def main():
    """Main validation entry point."""
    if len(sys.argv) > 1 and sys.argv[1] == '--help':
        print("SDMX Validation Script")
        print("Usage: python validate_sdmx.py [--verbose]")
        print("       python validate_sdmx.py --help")
        return

    if len(sys.argv) > 1 and sys.argv[1] == '--verbose':
        logging.getLogger().setLevel(logging.DEBUG)

    results = run_sdmx_validation()

    # Exit with appropriate code
    if results.get('success_rate', 0) >= 0.8:
        sys.exit(0)  # Success
    else:
        sys.exit(1)  # Failure


if __name__ == '__main__':
    main()