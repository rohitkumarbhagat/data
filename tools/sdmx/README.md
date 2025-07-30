# SDMX Tools

Tools for downloading SDMX (Statistical Data and Metadata eXchange) dataflows and data.

## Quick Start

### Installation
```bash
pip install sdmx1 absl-py pandas
```

### Basic Usage

**Recommended: Use the sdmx1 version for better performance and cleaner code**

```bash
# Download from predefined sources (ECB, IMF, WB, etc.)
python download_dataflows_sdmx1.py --source=ECB --agency_id=ECB

# Download from custom SDMX endpoint
python download_dataflows_sdmx1.py --base_url=https://api.example.com/sdmx/rest --agency_id=MYORG

# Specify custom download directory
python download_dataflows_sdmx1.py --source=ECB --agency_id=ECB --download_dir=./my_data
```

## Available Scripts

- **`download_dataflows_sdmx1.py`** - Uses sdmx1 library's built-in methods (recommended)
- **`download_dataflows.py`** - Legacy script with manual URL construction
- **`test_sdmx1_builtin.py`** - Test script demonstrating built-in methods

## Common Options

| Flag | Description | Example |
|------|-------------|---------|
| `--source` | Predefined source (ECB, IMF, WB) | `--source=ECB` |
| `--base_url` | Custom SDMX endpoint URL | `--base_url=https://api.example.com/sdmx/rest` |
| `--agency_id` | Agency identifier | `--agency_id=ECB` |
| `--download_dir` | Download directory | `--download_dir=./data` |
| `--timeout` | Request timeout in seconds | `--timeout=300` |

## Documentation

See `sdmx1_reference.md` for detailed API documentation and examples.