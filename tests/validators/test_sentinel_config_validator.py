#!/usr/bin/env python3
"""
Tests for Sentinel Configuration Validator

Validates that S10 uses correct MCP field names and prevents regressions.
"""

import pytest
import tempfile
import os
from pathlib import Path
from src.validators.sentinel_config_validator import SentinelConfigValidator


class TestSentinelConfigValidator:
    """Test suite for Sentinel configuration validation."""

    def test_s10_content_type_field_validation_passes(self):
        """Test that S10 correctly uses 'content_type' field (not 'context_type')."""
        # Use actual S10 file
        validator = SentinelConfigValidator()
        is_valid, errors = validator.validate_s10_mcp_field_names()

        assert is_valid, f"S10 validation failed: {errors}"
        assert len(errors) == 0, "S10 should use correct 'content_type' field name"

    def test_s10_uses_content_type_not_context_type(self):
        """Test that S10 does NOT use the incorrect 'context_type' field (PR #273 bug prevention)."""
        validator = SentinelConfigValidator()

        # Read actual S10 file
        s10_file = validator.checks_dir / "s10_content_pipeline.py"
        with open(s10_file, 'r') as f:
            content = f.read()

        # Verify no usage of incorrect field name in payload construction
        # (Allow in comments for documentation purposes)
        lines = content.split('\n')
        for i, line in enumerate(lines, 1):
            if '"context_type":' in line or "'context_type':" in line:
                # Split on '#' to separate code from comment
                code_part = line.split('#')[0] if '#' in line else line
                # Should NOT appear in actual code (OK in comments)
                assert '"context_type"' not in code_part and "'context_type'" not in code_part, \
                    f"Line {i} uses incorrect 'context_type' field in code - should be 'content_type': {line}"

    def test_s10_has_content_type_field_in_payloads(self):
        """Test that S10 actually uses 'content_type' field in MCP payloads."""
        validator = SentinelConfigValidator()

        s10_file = validator.checks_dir / "s10_content_pipeline.py"
        with open(s10_file, 'r') as f:
            content = f.read()

        # Verify correct field name is used
        assert '"content_type"' in content or "'content_type'" in content, \
            "S10 must use 'content_type' field for MCP payloads"

    def test_s9_s10_use_valid_mcp_types(self):
        """Test that S9 and S10 use valid MCP types (design, decision, trace, sprint, log)."""
        validator = SentinelConfigValidator()
        is_valid, errors = validator.validate_s9_s10_mcp_types()

        assert is_valid, f"S9/S10 MCP type validation failed: {errors}"
        assert len(errors) == 0, "S9/S10 should only use valid MCP types"

    def test_s9_does_not_use_invalid_graph_intent_test_type(self):
        """Test that S9 does NOT use 'graph_intent_test' as MCP type (PR #270 bug prevention)."""
        validator = SentinelConfigValidator()

        s9_file = validator.checks_dir / "s9_graph_intent.py"
        with open(s9_file, 'r') as f:
            content = f.read()

        # Check that invalid test type is not used as MCP type
        lines = content.split('\n')
        for i, line in enumerate(lines, 1):
            if '"graph_intent_test"' in line and '"content_type":' in line:
                # Split on '#' to separate code from comment
                code_part = line.split('#')[0] if '#' in line else line
                # Check if both appear in actual code (not just comment)
                if '"graph_intent_test"' in code_part and '"content_type":' in code_part:
                    pytest.fail(
                        f"S9 line {i} uses invalid MCP type 'graph_intent_test' in code - "
                        f"should use valid MCP type (design, decision, trace, sprint, log)"
                    )

    def test_s10_does_not_use_invalid_pipeline_test_type(self):
        """Test that S10 does NOT use 'pipeline_test' as MCP type (PR #270 bug prevention)."""
        validator = SentinelConfigValidator()

        s10_file = validator.checks_dir / "s10_content_pipeline.py"
        with open(s10_file, 'r') as f:
            content = f.read()

        # Check that invalid test type is not used as MCP type
        lines = content.split('\n')
        for i, line in enumerate(lines, 1):
            if '"pipeline_test"' in line and '"content_type":' in line:
                # Split on '#' to separate code from comment
                code_part = line.split('#')[0] if '#' in line else line
                # Check if both appear in actual code (not just comment)
                if '"pipeline_test"' in code_part and '"content_type":' in code_part:
                    pytest.fail(
                        f"S10 line {i} uses invalid MCP type 'pipeline_test' in code - "
                        f"should use valid MCP type (design, decision, trace, sprint, log)"
                    )

    def test_validate_all_checks_passes_on_current_codebase(self):
        """Test that all Sentinel validation checks pass on current codebase."""
        validator = SentinelConfigValidator()
        all_valid, results = validator.validate_all_checks()

        assert all_valid, f"Sentinel validation failed: {results}"
        assert len(results) == 0, "All Sentinel checks should pass validation"

    def test_validator_rejects_context_type_in_mock_file(self):
        """Test that validator correctly rejects 'context_type' usage."""
        # Create temporary directory with mock S10 file
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_s10 = Path(tmpdir) / "s10_content_pipeline.py"

            # Write mock S10 with incorrect field name
            mock_s10.write_text('''
def create_payload():
    return {
        "context_type": "log",  # WRONG - should be content_type
        "content": "test"
    }
''')

            validator = SentinelConfigValidator(sentinel_checks_dir=tmpdir)
            is_valid, errors = validator.validate_s10_mcp_field_names()

            assert not is_valid, "Validator should reject 'context_type' usage"
            assert len(errors) > 0
            assert any("context_type" in err for err in errors)

    def test_validator_accepts_content_type_in_mock_file(self):
        """Test that validator correctly accepts 'content_type' usage."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_s10 = Path(tmpdir) / "s10_content_pipeline.py"

            # Write mock S10 with correct field name
            mock_s10.write_text('''
def create_payload():
    return {
        "content_type": "log",  # CORRECT
        "content": "test"
    }
''')

            validator = SentinelConfigValidator(sentinel_checks_dir=tmpdir)
            is_valid, errors = validator.validate_s10_mcp_field_names()

            assert is_valid, f"Validator should accept 'content_type' usage, got errors: {errors}"
            assert len(errors) == 0

    def test_validator_allows_context_type_in_comments(self):
        """Test that validator allows 'context_type' in comments (for documentation)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_s10 = Path(tmpdir) / "s10_content_pipeline.py"

            # Write mock S10 with field name in comment
            mock_s10.write_text('''
def create_payload():
    # Fixed: Was using "context_type" (wrong), now using "content_type" (correct)
    return {
        "content_type": "log",
        "content": "test"
    }
''')

            validator = SentinelConfigValidator(sentinel_checks_dir=tmpdir)
            is_valid, errors = validator.validate_s10_mcp_field_names()

            assert is_valid, f"Validator should allow 'context_type' in comments, got errors: {errors}"
            assert len(errors) == 0


class TestSentinelValidatorCLI:
    """Test command-line interface for sentinel validator."""

    def test_cli_returns_0_on_valid_config(self):
        """Test that CLI returns exit code 0 when validation passes."""
        import subprocess
        import sys
        result = subprocess.run(
            [sys.executable, "-m", "src.validators.sentinel_config_validator"],
            cwd=Path(__file__).parent.parent.parent,
            capture_output=True,
            text=True
        )

        assert result.returncode == 0, f"Validator CLI should return 0 on success, got stderr: {result.stderr}"
        assert "All Sentinel configuration validations passed" in result.stdout


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
