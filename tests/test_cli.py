"""Tests for the CLI entry point."""

from click.testing import CliRunner

from trafficpipeline.cli import main


def test_cli_help():
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "traffic-congestion" in result.output.lower() or "pipeline" in result.output.lower()


def test_cli_version():
    runner = CliRunner()
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.output
