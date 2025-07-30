#!/usr/bin/env python3
"""Test script to demonstrate built-in SDMX1 methods vs manual URL construction."""

import sdmx
import pandas as pd

def test_builtin_methods():
    """Demonstrate using built-in methods with predefined sources."""
    print("=== Testing Built-in Methods with ECB ===\n")
    
    # Create client for ECB
    ecb = sdmx.Client('ECB')
    
    # Get all dataflows using built-in method
    print("1. Getting all dataflows:")
    flow_msg = ecb.dataflow()
    
    # Convert to pandas for easy viewing
    dataflows = sdmx.to_pandas(flow_msg.dataflow)
    print(f"Found {len(dataflows)} dataflows")
    print(dataflows.head())
    print()
    
    # Search for exchange rate dataflows
    print("2. Searching for exchange rate dataflows:")
    exchange_flows = dataflows[dataflows.str.contains('exchange', case=False)]
    print(exchange_flows)
    print()
    
    # Get specific dataflow with references
    print("3. Getting EXR dataflow with all references:")
    exr_msg = ecb.dataflow('EXR')
    
    # Access dataflow and structure directly
    dataflow = exr_msg.dataflow.EXR
    print(f"Dataflow name: {dataflow.name}")
    print(f"Dataflow ID: {dataflow.id}")
    print(f"DSD reference: {dataflow.structure}")
    
    # Show the actual URL that was used
    print(f"\nActual URL used: {exr_msg.response.url}")


def test_manual_method():
    """Demonstrate manual URL construction for comparison."""
    print("\n=== Testing Manual Method ===\n")
    
    # Create generic client
    client = sdmx.Client()
    
    # Manual URL construction
    base_url = "https://data-api.ecb.europa.eu/service"
    agency_id = "ECB"
    
    # Get all dataflows manually
    print("1. Getting all dataflows manually:")
    url = f"{base_url}/dataflow/{agency_id}"
    response = client.get(url=url)
    
    dataflows = sdmx.to_pandas(response.dataflow)
    print(f"Found {len(dataflows)} dataflows")
    print()
    
    # Get specific dataflow manually
    print("2. Getting EXR dataflow manually:")
    dataflow_id = "EXR"
    version = "1.0"
    url = f"{base_url}/dataflow/{agency_id}/{dataflow_id}/{version}"
    response = client.get(url=url, params={'references': 'all'})
    
    print(f"URL used: {url}")
    print(f"Response contains: {list(response.__dict__.keys())}")


def test_custom_source():
    """Demonstrate configuring a custom source."""
    print("\n=== Testing Custom Source Configuration ===\n")
    
    import json
    
    # Configure a hypothetical custom source
    custom_source = {
        "id": "MYAPI",
        "name": "My Custom SDMX API",
        "url": "https://api.example.com/sdmx/rest",
        "api_version": "2.1"
    }
    
    client = sdmx.Client()
    
    print(f"Configuring custom source: {custom_source['id']}")
    print(f"URL: {custom_source['url']}")
    
    # Note: This would actually add the source if the URL was valid
    # client.add_source(json.dumps(custom_source))
    # myapi_client = sdmx.Client('MYAPI')
    # flow_msg = myapi_client.dataflow()


if __name__ == "__main__":
    try:
        test_builtin_methods()
        test_manual_method()
        test_custom_source()
    except Exception as e:
        print(f"Error: {e}")
        print("\nNote: This test requires internet connection to ECB's SDMX API")