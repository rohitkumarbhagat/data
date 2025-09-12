from __future__ import annotations

import os
from typing import Optional, Dict, Any

import pandas as pd
from google.adk.agents import LlmAgent


def read_csv_sample(
    file_path: str,
    rows: int = 20,
    encoding: Optional[str] = None,
    delimiter: Optional[str] = None,
) -> Dict[str, Any]:
    """Read first N rows of a CSV and return structured metadata.

    Returns a dict with keys:
      - status: "success" | "error"
      - columns: list[str]
      - sample: list[dict]
      - shape: {rows: int, cols: int}
      - message | error_message: str
    """
    try:
        if not file_path or not os.path.isfile(file_path):
            return {"status": "error", "error_message": f"File not found: {file_path}"}

        # Cap rows to avoid large reads
        try:
            nrows = int(rows) if rows is not None else 20
        except Exception:
            nrows = 20
        nrows = max(1, min(nrows, 200))

        read_kwargs: Dict[str, Any] = {"nrows": nrows}
        if encoding:
            read_kwargs["encoding"] = encoding
        if delimiter:
            read_kwargs["sep"] = delimiter

        df = pd.read_csv(file_path, **read_kwargs)

        # Handle empty result explicitly
        columns = df.columns.tolist()
        sample = df.head(5).to_dict("records")
        shape = {"rows": len(df), "cols": len(columns)}

        return {
            "status": "success",
            "columns": columns,
            "sample": sample,
            "shape": shape,
            "message": f"Read {min(5, len(df))} sample rows from {file_path}",
        }
    except Exception as e:  # Broad by design for tool boundary
        return {"status": "error", "error_message": str(e)}


# Agent for CSV reading and analysis
data_reader = LlmAgent(
    name="data_reader",
    model="gemini-2.0-flash",
    description="Reads and analyzes CSV files",
    instruction=(
        "Read the CSV file and describe its structure. "
        "Use the read_csv_sample tool for file access and return structured results."
    ),
    tools=[read_csv_sample],
)
