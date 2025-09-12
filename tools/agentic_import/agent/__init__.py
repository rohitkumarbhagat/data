"""
ADK implementation for PVMap Generator.

This package contains the Agent Development Kit (ADK) based implementation
of the PVMap generator, providing a modular alternative to the Gemini CLI approach.

Main Components:
- simple_agent: Basic CSV reading and analysis agent
- tools: Shared utility functions

Usage:
    # Tool functions (no ADK required)
    from agent.simple_agent import read_csv_sample
    result = read_csv_sample('data.csv')

    # Agent usage (requires ADK + API key)
    from agent.simple_agent import data_reader
    result = data_reader.run('Analyze data.csv')
"""

from __future__ import annotations

__version__ = "0.1.0"
__author__ = "Data Commons Team"

# Import tool functions (always available)
try:
    from .simple_agent import read_csv_sample
    from .analyzer import analyze_column_types, suggest_dc_mappings
    __all__ = ["read_csv_sample", "analyze_column_types", "suggest_dc_mappings"]
except ImportError:
    __all__ = []

# Import agents (optional - requires ADK)
try:
    from .simple_agent import data_reader
    from .analyzer import data_analyzer
    __all__.extend(["data_reader", "data_analyzer"])
except ImportError:
    # ADK not installed or configured
    pass

# Future imports (planned for later phases)
# from .tools import *  # Phase 1
# from .analyzer import *  # Phase 2
# from .pvmap_creator import *  # Phase 3
# from .coordinator import *  # Phase 5+