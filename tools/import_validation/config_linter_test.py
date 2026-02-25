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
"""Tests for validation config linter."""

import contextlib
import io
import json
import os
import tempfile
import unittest

from tools.import_validation import config_linter


class ConfigLinterTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.config_path = os.path.join(self.tmp.name, "validation_config.json")
        self.manifest_path = os.path.join(self.tmp.name, "manifest.json")

    def tearDown(self):
        self.tmp.cleanup()

    def _write_json(self, path: str, obj):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(obj, f)

    def _write_valid_config(self):
        self._write_json(
            self.config_path, {
                "schema_version": "1.0",
                "rules": [{
                    "rule_id": "check_deleted_records_percent",
                    "validator": "DELETED_RECORDS_PERCENT",
                    "params": {
                        "threshold": 10
                    }
                }]
            })

    def _write_wired_manifest(self):
        self._write_json(
            self.manifest_path, {
                "import_specifications": [{
                    "import_name": "TestImport",
                    "validation_config_file": "validation_config.json"
                }]
            })

    def _run_main(self, args: list[str]):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = config_linter.main(args)
        return code, stdout.getvalue()

    def test_valid_config_and_wired_manifest(self):
        self._write_valid_config()
        self._write_wired_manifest()

        code, output = self._run_main(["--config", self.config_path])

        self.assertEqual(code, 0)
        self.assertIn("VALID:", output)

    def test_invalid_json_returns_runtime_error(self):
        with open(self.config_path, "w", encoding="utf-8") as f:
            f.write("{ invalid json")

        code, output = self._run_main(["--config", self.config_path])

        self.assertEqual(code, 2)
        self.assertIn("RUNTIME_ERROR:", output)

    def test_invalid_root_type_returns_runtime_error(self):
        with open(self.config_path, "w", encoding="utf-8") as f:
            f.write("[]")

        code, output = self._run_main(["--config", self.config_path])

        self.assertEqual(code, 2)
        self.assertIn("Invalid JSON root type", output)

    def test_missing_rule_id_shows_name_fix_hint(self):
        self._write_json(
            self.config_path, {
                "schema_version": "1.0",
                "rules": [{
                    "name": "check_deleted_records_percent",
                    "validator": "DELETED_RECORDS_PERCENT",
                    "params": {
                        "threshold": 10
                    }
                }]
            })
        self._write_wired_manifest()

        code, output = self._run_main(["--config", self.config_path])

        self.assertEqual(code, 1)
        self.assertIn("INVALID:", output)
        self.assertIn("missing 'rule_id'", output)
        self.assertIn("FIX: replace 'name' with 'rule_id'.", output)

    def test_duplicate_rule_id_fails(self):
        self._write_json(
            self.config_path, {
                "schema_version": "1.0",
                "rules": [{
                    "rule_id": "dup_rule",
                    "validator": "DELETED_RECORDS_PERCENT",
                    "params": {
                        "threshold": 10
                    }
                }, {
                    "rule_id": "dup_rule",
                    "validator": "DELETED_RECORDS_COUNT",
                    "params": {
                        "threshold": 5
                    }
                }]
            })
        self._write_wired_manifest()

        code, output = self._run_main(["--config", self.config_path])

        self.assertEqual(code, 1)
        self.assertIn("Duplicate rule_id 'dup_rule'", output)

    def test_unknown_validator_fails(self):
        self._write_json(
            self.config_path, {
                "schema_version": "1.0",
                "rules": [{
                    "rule_id": "check_unknown",
                    "validator": "NOT_A_VALIDATOR",
                    "params": {}
                }]
            })
        self._write_wired_manifest()

        code, output = self._run_main(["--config", self.config_path])

        self.assertEqual(code, 1)
        self.assertIn("is not supported", output)
        self.assertIn("Supported validators:", output)

    def test_sql_validator_missing_condition_fails(self):
        self._write_json(
            self.config_path, {
                "schema_version": "1.0",
                "rules": [{
                    "rule_id": "check_sql",
                    "validator": "SQL_VALIDATOR",
                    "params": {
                        "query": "SELECT * FROM stats"
                    }
                }]
            })
        self._write_wired_manifest()

        code, output = self._run_main(["--config", self.config_path])

        self.assertEqual(code, 1)
        self.assertIn("requires non-empty 'condition'", output)

    def test_missing_manifest_fails_with_fix_hint(self):
        self._write_valid_config()

        code, output = self._run_main(["--config", self.config_path])

        self.assertEqual(code, 1)
        self.assertIn("Manifest file not found", output)
        self.assertIn("FIX: Add/create manifest.json", output)

    def test_manifest_missing_wiring_fails(self):
        self._write_valid_config()
        self._write_json(
            self.manifest_path, {
                "import_specifications": [{
                    "import_name": "TestImport"
                }]
            })

        code, output = self._run_main(["--config", self.config_path])

        self.assertEqual(code, 1)
        self.assertIn("missing validation_config_file wiring", output)
        self.assertIn(
            "FIX: Add \"validation_config_file\": \"validation_config.json\"",
            output)

    def test_skip_manifest_check_bypasses_manifest_errors_only(self):
        self._write_valid_config()

        code, output = self._run_main(
            ["--config", self.config_path, "--skip_manifest_check"])

        self.assertEqual(code, 0)
        self.assertIn("VALID:", output)

        self._write_json(
            self.config_path, {
                "schema_version": "1.0",
                "rules": [{
                    "name": "bad_shape",
                    "validator": "DELETED_RECORDS_PERCENT",
                    "params": {}
                }]
            })
        code, output = self._run_main(
            ["--config", self.config_path, "--skip_manifest_check"])
        self.assertEqual(code, 1)
        self.assertIn("missing 'rule_id'", output)

    def test_threshold_must_be_non_negative_numeric(self):
        self._write_json(
            self.config_path, {
                "schema_version": "1.0",
                "rules": [{
                    "rule_id": "check_bad_threshold",
                    "validator": "DELETED_RECORDS_PERCENT",
                    "params": {
                        "threshold": -1
                    }
                }]
            })
        self._write_wired_manifest()

        code, output = self._run_main(["--config", self.config_path])

        self.assertEqual(code, 1)
        self.assertIn("params.threshold must be >= 0", output)


if __name__ == "__main__":
    unittest.main()
