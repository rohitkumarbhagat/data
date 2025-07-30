# SDMX1 Python Library Reference Guide

## Overview

The `sdmx1` library (imported as `sdmx`) is a Python implementation of the SDMX 2.1 (ISO 17369:2013) and 3.0 standards for Statistical Data and Metadata eXchange. It provides a pythonic interface for working with statistical data from various sources.

### Installation
```bash
pip install sdmx1
```

### Key Features
- Support for any SDMX 2.1/3.0 compliant data source
- Native Python objects for SDMX information model
- Built-in pandas integration
- Automatic format negotiation (XML, JSON, CSV)
- No manual parsing required

## Client Creation

### Generic Client (for arbitrary endpoints)
```python
import sdmx

# Create a generic client that works with any SDMX endpoint
client = sdmx.Client()

# Use with custom URLs
response = client.get(url="https://your-sdmx-endpoint.com/rest/...")
```

### Named Client (for predefined sources)
```python
# Create client for known data sources
ecb_client = sdmx.Client('ECB')
wb_client = sdmx.Client('WB')
```

### Client Configuration
```python
# Pass any requests.request() arguments
client = sdmx.Client(
    timeout=300,
    proxies={'http': 'http://proxy.example.com:8080'},
    headers={'User-Agent': 'My App'}
)
```

## Core Operations

### 1. Retrieving All Dataflows
```python
# Get all dataflows from an agency
response = client.get(
    url=f"{base_url}/dataflow/{agency_id}",
    resource_type='dataflow'
)

# Access dataflows as native objects
for flow_id, flow in response.dataflow.items():
    print(f"ID: {flow_id}")
    print(f"Name: {flow.name}")
    print(f"Description: {flow.description}")
```

### 2. Retrieving Specific Dataflow with References
```python
# Get dataflow with all related structures
response = client.get(
    url=f"{base_url}/dataflow/{agency_id}/{dataflow_id}/{version}",
    params={'references': 'all'}  # Includes DSD, codelists, concepts
)

# Access the DSD directly (no manual lookup needed)
dataflow = response.dataflow[dataflow_id]
dsd = dataflow.structure  # Direct reference to DSD
```

### 3. Retrieving Data Structure Definitions (DSDs)
```python
# Method 1: Direct DSD request
dsd_response = client.get(
    url=f"{base_url}/datastructure/{agency_id}/{dsd_id}/{version}",
    params={'references': 'children'}  # Include codelists, concepts
)

# Method 2: From dataflow with references
df_response = client.get(
    url=f"{base_url}/dataflow/{agency_id}/{df_id}/{version}",
    params={'references': 'all'}
)
dsd = df_response.structure[dsd_id]  # Access from structure collection
```

### 4. Downloading Data
```python
# Get data with various options
data_response = client.get(
    url=f"{base_url}/data/{agency_id},{dataflow_id},{version}",
    params={
        'detail': 'full',
        'dimensionAtObservation': 'TIME_PERIOD'
    }
)

# Or use key-based filtering
data_response = client.get(
    url=f"{base_url}/data/{dataflow_id}",
    key={'FREQ': 'A', 'GEO': 'EU27_2020'},
    params={'startPeriod': '2020', 'endPeriod': '2023'}
)
```

## File Operations

### Saving Responses Directly
```python
# Save response to file during retrieval
client.get(
    url=f"{base_url}/dataflow/{agency_id}",
    tofile='dataflows.xml'  # Saves in original format
)
```

### Converting and Saving Data
```python
# Convert to pandas and save as CSV
data_response = client.get(url=data_url)
df = sdmx.to_pandas(data_response)
df.to_csv('output.csv', index=False)

# Save as SDMX-CSV
sdmx.to_csv(data_response, path='output_sdmx.csv')

# Save structure as XML
structure_response = client.get(url=structure_url)
with open('structure.xml', 'wb') as f:
    f.write(sdmx.to_xml(structure_response))
```

## Working with SDMX Objects

### Message Structure
```python
# Every response is a Message object
response = client.get(...)

# Access different components
response.dataflow      # Dict of dataflows
response.structure     # Dict of DSDs
response.codelist      # Dict of codelists
response.data          # Dataset(s)
```

### Navigating Objects
```python
# Dataflows
for flow_id, flow in response.dataflow.items():
    flow.id              # Identifier
    flow.name            # Human-readable name
    flow.description     # Description
    flow.structure       # Reference to DSD
    flow.maintainer      # Maintaining agency

# Data Structure Definitions
dsd = response.structure[dsd_id]
for dim in dsd.dimensions:
    dim.id               # Dimension ID
    dim.concept          # Concept reference
    dim.local_representation  # Codelist or format

# Codelists
codelist = response.codelist[codelist_id]
for code in codelist:
    code.id              # Code value
    code.name            # Code description
```

## Error Handling

```python
from sdmx.exceptions import HTTPError, XMLParseError

try:
    response = client.get(url=...)
except HTTPError as e:
    print(f"HTTP Error {e.response.status_code}: {e.response.text}")
except XMLParseError as e:
    print(f"Invalid SDMX response: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")
```

## Best Practices

### 1. Use References Efficiently
```python
# Get everything in one request
response = client.get(
    url=f"{base_url}/dataflow/{agency_id}/{df_id}",
    params={'references': 'all'}  # Includes DSD, codelists, concepts
)
# Access related objects directly
dsd = response.dataflow[df_id].structure
codelists = response.codelist
```

### 2. Handle Large Datasets
```python
# Use streaming for large data
response = client.get(url=data_url, stream=True)

# Or process in chunks with pandas
for chunk in sdmx.to_pandas(response, chunksize=10000):
    process_chunk(chunk)
```

### 3. Logging and Debugging
```python
import logging

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)
sdmx.log.setLevel(logging.DEBUG)
```

### 4. Parallel Processing
```python
from concurrent.futures import ThreadPoolExecutor

def download_dataflow(df_id):
    return client.get(url=f"{base_url}/data/{df_id}")

# Download multiple dataflows in parallel
with ThreadPoolExecutor(max_workers=5) as executor:
    futures = [executor.submit(download_dataflow, df_id) for df_id in dataflow_ids]
    results = [f.result() for f in futures]
```

## Common Patterns

### Pattern 1: Download All Dataflows for an Agency
```python
# Get list of dataflows
df_response = client.get(url=f"{base_url}/dataflow/{agency_id}")

# Download each dataflow's data
for df_id, dataflow in df_response.dataflow.items():
    try:
        # Get data
        data = client.get(
            url=f"{base_url}/data/{agency_id},{df_id},{dataflow.version}"
        )
        # Save to CSV
        sdmx.to_pandas(data).to_csv(f"{df_id}.csv")
    except Exception as e:
        print(f"Failed to download {df_id}: {e}")
```

### Pattern 2: Explore Data Structure
```python
# Get dataflow with all references
response = client.get(
    url=f"{base_url}/dataflow/{agency_id}/{df_id}",
    params={'references': 'all'}
)

# Access DSD
dsd = response.dataflow[df_id].structure

# List dimensions
print("Dimensions:")
for dim in dsd.dimensions:
    print(f"  {dim.id}: {dim.concept.name}")
    if hasattr(dim.local_representation, 'enumerated'):
        codelist = response.codelist[dim.local_representation.enumerated.id]
        print(f"    Values: {[code.id for code in codelist][:5]}...")

# List measures
print("Measures:")
for measure in dsd.measures:
    print(f"  {measure.id}: {measure.concept.name}")
```

### Pattern 3: Filter and Download Specific Data
```python
# Build key dictionary for filtering
key = {
    'FREQ': 'A',      # Annual frequency
    'GEO': ['DE', 'FR', 'IT'],  # Multiple countries
    'INDICATOR': 'GDP'
}

# Download filtered data
data = client.get(
    url=f"{base_url}/data/{dataflow_id}",
    key=key,
    params={
        'startPeriod': '2020',
        'endPeriod': '2023',
        'detail': 'dataonly'  # Skip attributes
    }
)
```

## Differences from Manual Approach

### Old Way (Manual Parsing)
```python
# Manual URL construction
url = base_url + f"/dataflow/{agency_id}/{dataflow_id}/{version}"
response = requests.get(url)
json_data = response.json()

# Manual path navigation
dataflows = json_data["data"]["dataflows"]
dsd_urn = dataflows[0]["links"][0]["urn"]

# Manual URN parsing
match = re.match(r"([^:]+):([^(\)]+)\(([^)]+)\)", urn)
```

### New Way (sdmx1 Native)
```python
# Automatic URL handling
response = client.get(url=f"{base_url}/dataflow/{agency_id}/{df_id}")

# Direct object access
dataflow = response.dataflow[df_id]
dsd = dataflow.structure

# No URN parsing needed - objects linked automatically
```

## Tips for Migration

1. **Replace requests.get() with client.get()**
   - Pass base URL to `url` parameter
   - Use `params` for query parameters
   - Use `tofile` for direct file saving

2. **Remove all JSON path navigation**
   - Use response.dataflow, response.structure, etc.
   - Access objects by ID from collections

3. **Remove URN parsing**
   - Objects have direct references (e.g., dataflow.structure)
   - No need to extract IDs from URNs

4. **Use native conversions**
   - sdmx.to_pandas() instead of manual CSV creation
   - sdmx.to_xml() for structure files
   - Let the library handle format negotiation

5. **Leverage 'references' parameter**
   - Use 'all' to get everything in one request
   - Reduces number of API calls significantly