# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Lints a validation_config.json file for schema and wiring correctness."""

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Iterable, Optional


class LintRuntimeError(Exception):
    """Raised for runtime/usage failures that should return exit code 2."""


SUPPORTED_VALIDATORS = {
    "SQL_VALIDATOR",
    "MAX_DATE_LATEST",
    "MAX_DATE_CONSISTENT",
    "DELETED_RECORDS_COUNT",
    "DELETED_RECORDS_PERCENT",
    "MISSING_REFS_COUNT",
    "LINT_ERROR_COUNT",
    "MODIFIED_RECORDS_COUNT",
    "ADDED_RECORDS_COUNT",
    "NUM_PLACES_CONSISTENT",
    "NUM_PLACES_COUNT",
    "NUM_OBSERVATIONS_CHECK",
    "UNIT_CONSISTENCY_CHECK",
    "MIN_VALUE_CHECK",
    "MAX_VALUE_CHECK",
}

THRESHOLD_VALIDATORS = {
    "DELETED_RECORDS_PERCENT",
    "DELETED_RECORDS_COUNT",
    "MISSING_REFS_COUNT",
    "LINT_ERROR_COUNT",
}

ALLOWED_RULE_KEYS = {
    "rule_id",
    "validator",
    "params",
    "scope",
    "enabled",
    "description",
}


def _append_error(errors: list[str], message: str, fix: Optional[str] = None):
    errors.append(f"ERROR: {message}")
    if fix:
        errors.append(f"FIX: {fix}")


def _is_non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _format_validator_list(validators: Iterable[str]) -> str:
    return ", ".join(sorted(validators))


def validate_top_level(config_obj: Any) -> list[str]:
    """Validates top-level fields for a config object."""
    errors = []
    if not isinstance(config_obj, dict):
        _append_error(errors, "Top-level JSON must be an object.",
                      "Use a JSON object with schema_version and rules.")
        return errors

    if "schema_version" not in config_obj:
        _append_error(errors, "Missing required top-level field 'schema_version'.",
                      "Add \"schema_version\": \"1.0\".")
    elif config_obj.get("schema_version") != "1.0":
        _append_error(
            errors,
            f"Unsupported schema_version '{config_obj.get('schema_version')}'.",
            "Set \"schema_version\" to \"1.0\".")

    if "rules" not in config_obj:
        _append_error(errors, "Missing required top-level field 'rules'.",
                      "Add a non-empty \"rules\" list.")
    elif not isinstance(config_obj.get("rules"), list):
        _append_error(errors, "Top-level field 'rules' must be a list.",
                      "Set \"rules\" to a JSON array of rule objects.")
    elif not config_obj.get("rules"):
        _append_error(errors, "Top-level field 'rules' must be non-empty.",
                      "Add at least one rule object.")

    return errors


def validate_rule(rule: Any, index: int) -> list[str]:
    """Validates a single rule object."""
    errors = []
    rule_path = f"rules[{index}]"
    if not isinstance(rule, dict):
        _append_error(errors, f"{rule_path} must be an object.",
                      f"Replace {rule_path} with a JSON object.")
        return errors

    unknown_keys = sorted(set(rule.keys()) - ALLOWED_RULE_KEYS)
    if unknown_keys:
        _append_error(errors, f"{rule_path} has unknown keys: {unknown_keys}.",
                      "Remove unknown keys or move custom data into params.")

    if "rule_id" not in rule:
        if "name" in rule:
            _append_error(errors, f"{rule_path} is missing 'rule_id'.",
                          "replace 'name' with 'rule_id'.")
        else:
            _append_error(errors, f"{rule_path} is missing 'rule_id'.",
                          "Add a unique string field 'rule_id'.")
    elif not _is_non_empty_string(rule.get("rule_id")):
        _append_error(errors, f"{rule_path}.rule_id must be a non-empty string.",
                      "Set rule_id to a non-empty string.")

    if "validator" not in rule:
        _append_error(errors, f"{rule_path} is missing 'validator'.",
                      "Add a supported validator name.")
        validator = None
    elif not _is_non_empty_string(rule.get("validator")):
        _append_error(
            errors, f"{rule_path}.validator must be a non-empty string.",
            "Set validator to one of the supported validator names.")
        validator = None
    else:
        validator = rule.get("validator")
        if validator not in SUPPORTED_VALIDATORS:
            _append_error(
                errors,
                f"{rule_path}.validator '{validator}' is not supported.",
                "Supported validators: "
                f"{_format_validator_list(SUPPORTED_VALIDATORS)}.")

    if "params" not in rule:
        _append_error(errors, f"{rule_path} is missing 'params'.",
                      "Add a params object, e.g. \"params\": {}.")
        params = None
    elif not isinstance(rule.get("params"), dict):
        _append_error(errors, f"{rule_path}.params must be an object.",
                      "Set params to a JSON object.")
        params = None
    else:
        params = rule.get("params")

    if isinstance(params, dict):
        if validator == "SQL_VALIDATOR":
            if not _is_non_empty_string(params.get("query")):
                _append_error(
                    errors,
                    f"{rule_path} SQL_VALIDATOR requires non-empty 'query'.",
                    "Add params.query with a SQL SELECT statement.")
            if not _is_non_empty_string(params.get("condition")):
                _append_error(
                    errors,
                    f"{rule_path} SQL_VALIDATOR requires non-empty 'condition'.",
                    "Add params.condition with a SQL boolean expression.")

        if validator in THRESHOLD_VALIDATORS and "threshold" in params:
            threshold = params.get("threshold")
            if isinstance(threshold, bool) or not isinstance(
                    threshold, (int, float)):
                _append_error(
                    errors,
                    f"{rule_path}.params.threshold must be numeric.",
                    "Set threshold to a number >= 0.")
            elif threshold < 0:
                _append_error(
                    errors,
                    f"{rule_path}.params.threshold must be >= 0.",
                    "Set threshold to a non-negative number.")

    return errors


def validate_rules(rules: Any) -> list[str]:
    """Validates the rules list and rule_id uniqueness."""
    errors = []
    if not isinstance(rules, list):
        return errors

    seen_rule_ids = set()
    duplicate_rule_ids = set()
    for index, rule in enumerate(rules):
        errors.extend(validate_rule(rule, index))
        if isinstance(rule, dict) and _is_non_empty_string(rule.get("rule_id")):
            rule_id = rule.get("rule_id")
            if rule_id in seen_rule_ids:
                duplicate_rule_ids.add(rule_id)
            else:
                seen_rule_ids.add(rule_id)

    for rule_id in sorted(duplicate_rule_ids):
        _append_error(
            errors, f"Duplicate rule_id '{rule_id}' found.",
            "Ensure every rule_id is unique within the file.")
    return errors


def validate_manifest_wiring(manifest_path: Any) -> list[str]:
    """Validates manifest presence and validation_config_file wiring."""
    errors = []
    manifest = Path(manifest_path)
    if not manifest.exists():
        _append_error(
            errors, f"Manifest file not found at '{manifest}'.",
            "Add/create manifest.json and include "
            "\"validation_config_file\": \"validation_config.json\" inside an "
            "import_specifications entry.")
        return errors

    try:
        with open(manifest, encoding="utf-8") as f:
            manifest_obj = json.load(f)
    except json.JSONDecodeError as err:
        _append_error(
            errors,
            f"Manifest JSON parse error in '{manifest}': {err.msg} "
            f"(line {err.lineno}, column {err.colno}).",
            "Fix manifest.json to valid JSON and wire "
            "\"validation_config_file\": \"validation_config.json\".")
        return errors
    except OSError as err:
        _append_error(errors, f"Unable to read manifest '{manifest}': {err}.",
                      "Ensure manifest.json is readable.")
        return errors

    if not isinstance(manifest_obj, dict):
        _append_error(
            errors, f"Manifest '{manifest}' top-level JSON must be an object.",
            "Use a JSON object with import_specifications.")
        return errors

    specs = manifest_obj.get("import_specifications")
    if not isinstance(specs, list) or not specs:
        _append_error(
            errors, f"Manifest '{manifest}' has no import_specifications list.",
            "Add import_specifications and set "
            "\"validation_config_file\": \"validation_config.json\".")
        return errors

    has_wiring = False
    wrong_values = []
    for index, spec in enumerate(specs):
        if not isinstance(spec, dict):
            continue
        value = spec.get("validation_config_file")
        if value == "validation_config.json":
            has_wiring = True
            break
        if "validation_config_file" in spec:
            wrong_values.append((index, value))

    if not has_wiring:
        if wrong_values:
            _append_error(
                errors,
                f"Manifest '{manifest}' has incorrect validation_config_file "
                f"values: {wrong_values}.",
                "Set \"validation_config_file\": \"validation_config.json\" in "
                "the relevant import_specifications entry.")
        else:
            _append_error(
                errors,
                f"Manifest '{manifest}' is missing validation_config_file "
                "wiring.",
                "Add \"validation_config_file\": \"validation_config.json\" to "
                "the relevant import_specifications entry.")

    return errors


def lint_config(config_path: Any,
                manifest_path: Optional[Any] = None,
                skip_manifest_check: bool = False) -> list[str]:
    """Lints a single validation config and optional manifest wiring."""
    config = Path(config_path)
    if not config.exists():
        raise LintRuntimeError(
            f"Config file not found: '{config}'. Provide a valid --config path.")
    if not config.is_file():
        raise LintRuntimeError(
            f"Config path is not a file: '{config}'. Provide a file path.")

    try:
        with open(config, encoding="utf-8") as f:
            config_obj = json.load(f)
    except json.JSONDecodeError as err:
        raise LintRuntimeError(
            f"Config JSON parse error: {err.msg} (line {err.lineno}, "
            f"column {err.colno}).") from err
    except OSError as err:
        raise LintRuntimeError(f"Unable to read config file '{config}': {err}."
                               ) from err

    if not isinstance(config_obj, dict):
        raise LintRuntimeError(
            "Invalid JSON root type: top-level JSON must be an object.")

    errors = []
    errors.extend(validate_top_level(config_obj))
    rules = config_obj.get("rules")
    if isinstance(rules, list):
        errors.extend(validate_rules(rules))

    if not skip_manifest_check:
        manifest = Path(manifest_path) if manifest_path else config.parent / (
            "manifest.json")
        errors.extend(validate_manifest_wiring(manifest))

    return errors


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Lint a single validation_config.json file.")
    parser.add_argument("--config",
                        required=True,
                        help="Path to validation_config.json")
    parser.add_argument(
        "--manifest",
        help="Optional path to manifest.json (defaults to sibling manifest).")
    parser.add_argument(
        "--skip_manifest_check",
        action="store_true",
        help="Skip manifest wiring checks and lint only the config file.")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)
    config_path = str(Path(args.config))

    try:
        errors = lint_config(config_path=config_path,
                             manifest_path=args.manifest,
                             skip_manifest_check=args.skip_manifest_check)
    except LintRuntimeError as err:
        print(f"RUNTIME_ERROR: {err}")
        return 2

    if errors:
        print(f"INVALID: {config_path}")
        for err in errors:
            print(err)
        return 1

    print(f"VALID: {config_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
