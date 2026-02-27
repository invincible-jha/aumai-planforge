"""Comprehensive CLI tests for aumai-planforge."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from aumai_planforge.cli import main


@pytest.fixture()
def runner() -> CliRunner:
    """Return a Click test runner."""
    return CliRunner()


@pytest.fixture()
def simple_plan_file(tmp_path: Path) -> Path:
    """Create a minimal valid plan YAML file."""
    plan_data = {
        "plan_id": "plan-cli-001",
        "name": "CLI Test Plan",
        "goal": "Test the CLI",
        "steps": [
            {
                "step_id": "step-1",
                "action": "Gather information",
                "dependencies": [],
                "estimated_duration_seconds": 10.0,
                "priority": 1,
                "preconditions": [],
                "effects": [],
                "status": "pending",
                "metadata": {},
            },
            {
                "step_id": "step-2",
                "action": "Execute action",
                "dependencies": ["step-1"],
                "estimated_duration_seconds": 20.0,
                "priority": 2,
                "preconditions": [],
                "effects": [],
                "status": "pending",
                "metadata": {},
            },
        ],
        "status": "draft",
        "estimated_cost": 0.3,
        "estimated_duration_seconds": 30.0,
        "goals": [],
        "metadata": {},
    }
    file = tmp_path / "plan.yaml"
    file.write_text(yaml.dump(plan_data), encoding="utf-8")
    return file


@pytest.fixture()
def circular_plan_file(tmp_path: Path) -> Path:
    """Create a plan YAML file with circular dependencies."""
    plan_data = {
        "plan_id": "plan-circular",
        "name": "Circular Plan",
        "goal": "Circular goal",
        "steps": [
            {
                "step_id": "a",
                "action": "Step A",
                "dependencies": ["b"],
                "estimated_duration_seconds": 5.0,
                "priority": 1,
                "preconditions": [],
                "effects": [],
                "status": "pending",
                "metadata": {},
            },
            {
                "step_id": "b",
                "action": "Step B",
                "dependencies": ["a"],
                "estimated_duration_seconds": 5.0,
                "priority": 2,
                "preconditions": [],
                "effects": [],
                "status": "pending",
                "metadata": {},
            },
        ],
        "status": "draft",
        "estimated_cost": 0.0,
        "estimated_duration_seconds": 0.0,
        "goals": [],
        "metadata": {},
    }
    file = tmp_path / "circular.yaml"
    file.write_text(yaml.dump(plan_data), encoding="utf-8")
    return file


class TestCliVersion:
    """Tests for --version flag."""

    def test_version_flag(self, runner: CliRunner) -> None:
        """--version must exit 0 and report version."""
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output

    def test_help_flag(self, runner: CliRunner) -> None:
        """--help must exit 0 and describe the CLI."""
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "PlanForge" in result.output


class TestCreateCommand:
    """Tests for the `create` command."""

    def test_create_exits_zero(self, runner: CliRunner) -> None:
        """create exits 0 for valid name and goal."""
        result = runner.invoke(
            main, ["create", "--name", "My Plan", "--goal", "Achieve something"]
        )
        assert result.exit_code == 0

    def test_create_prints_plan_name(self, runner: CliRunner) -> None:
        """create prints the plan name."""
        result = runner.invoke(
            main, ["create", "--name", "Alpha Plan", "--goal", "Some goal"]
        )
        assert "Alpha Plan" in result.output

    def test_create_prints_goal(self, runner: CliRunner) -> None:
        """create prints the goal."""
        result = runner.invoke(
            main, ["create", "--name", "My Plan", "--goal", "My Specific Goal"]
        )
        assert "My Specific Goal" in result.output

    def test_create_saves_file(self, runner: CliRunner, tmp_path: Path) -> None:
        """create --output saves the plan to a YAML file."""
        output_file = tmp_path / "new_plan.yaml"
        result = runner.invoke(
            main,
            [
                "create",
                "--name", "Saved Plan",
                "--goal", "Save to disk",
                "--output", str(output_file),
            ],
        )
        assert result.exit_code == 0
        assert output_file.exists()
        assert "saved" in result.output.lower()

    def test_create_missing_name(self, runner: CliRunner) -> None:
        """create exits non-zero when --name is missing."""
        result = runner.invoke(main, ["create", "--goal", "No name"])
        assert result.exit_code != 0

    def test_create_missing_goal(self, runner: CliRunner) -> None:
        """create exits non-zero when --goal is missing."""
        result = runner.invoke(main, ["create", "--name", "No goal"])
        assert result.exit_code != 0


class TestValidateCommand:
    """Tests for the `validate` command."""

    def test_validate_valid_plan_exits_zero(
        self, runner: CliRunner, simple_plan_file: Path
    ) -> None:
        """validate exits 0 for a valid plan."""
        result = runner.invoke(main, ["validate", "--plan", str(simple_plan_file)])
        assert result.exit_code == 0

    def test_validate_prints_valid_message(
        self, runner: CliRunner, simple_plan_file: Path
    ) -> None:
        """validate prints that the plan is valid."""
        result = runner.invoke(main, ["validate", "--plan", str(simple_plan_file)])
        assert "valid" in result.output.lower()

    def test_validate_prints_step_count(
        self, runner: CliRunner, simple_plan_file: Path
    ) -> None:
        """validate prints the number of steps."""
        result = runner.invoke(main, ["validate", "--plan", str(simple_plan_file)])
        assert "Steps" in result.output

    def test_validate_prints_duration(
        self, runner: CliRunner, simple_plan_file: Path
    ) -> None:
        """validate prints estimated duration."""
        result = runner.invoke(main, ["validate", "--plan", str(simple_plan_file)])
        assert "duration" in result.output.lower()

    def test_validate_missing_file(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """validate exits non-zero for a missing plan file."""
        result = runner.invoke(
            main, ["validate", "--plan", str(tmp_path / "missing.yaml")]
        )
        assert result.exit_code != 0

    def test_validate_circular_plan_exits_nonzero(
        self, runner: CliRunner, circular_plan_file: Path
    ) -> None:
        """validate exits non-zero for a plan with circular dependencies."""
        result = runner.invoke(
            main, ["validate", "--plan", str(circular_plan_file)]
        )
        assert result.exit_code != 0


class TestOptimizeCommand:
    """Tests for the `optimize` command."""

    def test_optimize_valid_plan_exits_zero(
        self, runner: CliRunner, simple_plan_file: Path
    ) -> None:
        """optimize exits 0 for a valid plan."""
        result = runner.invoke(main, ["optimize", "--plan", str(simple_plan_file)])
        assert result.exit_code == 0

    def test_optimize_shows_wave_count(
        self, runner: CliRunner, simple_plan_file: Path
    ) -> None:
        """optimize prints the number of parallel waves."""
        result = runner.invoke(main, ["optimize", "--plan", str(simple_plan_file)])
        assert "wave" in result.output.lower()

    def test_optimize_missing_file(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """optimize exits non-zero for a missing plan file."""
        result = runner.invoke(
            main, ["optimize", "--plan", str(tmp_path / "missing.yaml")]
        )
        assert result.exit_code != 0


class TestRunCommand:
    """Tests for the `run` command."""

    def test_run_valid_plan_exits_zero(
        self, runner: CliRunner, simple_plan_file: Path
    ) -> None:
        """run exits 0 for a valid plan that completes successfully."""
        result = runner.invoke(main, ["run", "--plan", str(simple_plan_file)])
        assert result.exit_code == 0

    def test_run_prints_status(
        self, runner: CliRunner, simple_plan_file: Path
    ) -> None:
        """run prints execution status."""
        result = runner.invoke(main, ["run", "--plan", str(simple_plan_file)])
        assert "Status" in result.output

    def test_run_prints_steps_completed(
        self, runner: CliRunner, simple_plan_file: Path
    ) -> None:
        """run prints number of steps completed."""
        result = runner.invoke(main, ["run", "--plan", str(simple_plan_file)])
        assert "Steps completed" in result.output

    def test_run_missing_file(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """run exits non-zero for a missing plan file."""
        result = runner.invoke(
            main, ["run", "--plan", str(tmp_path / "missing.yaml")]
        )
        assert result.exit_code != 0
