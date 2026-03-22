"""Smoke tests for CLI commands."""
import pytest
from typer.testing import CliRunner


@pytest.mark.smoke
class TestCLISmoke:
    def test_cli_help(self):
        from apps.cli.main import app
        runner = CliRunner()
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "quant-cli" in result.output.lower() or "usage" in result.output.lower() or "commands" in result.output.lower()

    def test_run_dq_help(self):
        from apps.cli.main import app
        runner = CliRunner()
        result = runner.invoke(app, ["run-dq", "--help"])
        assert result.exit_code == 0
