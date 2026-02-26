"""CLI entry point for aumai-planforge."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from aumai_planforge.core import PlanBuilder, PlanExecutor, PlanOptimizer

_builder = PlanBuilder()
_executor = PlanExecutor(builder=_builder)
_optimizer = PlanOptimizer(builder=_builder)


@click.group()
@click.version_option()
def main() -> None:
    """AumAI PlanForge — Agent planning and strategy generation CLI."""


@main.command("create")
@click.option("--name", required=True, help="Plan name.")
@click.option("--goal", required=True, help="Goal or objective of the plan.")
@click.option(
    "--output",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Save the plan to this YAML file.",
)
def create(name: str, goal: str, output: Path | None) -> None:
    """Create a new empty plan."""
    plan = _builder.create(name=name, goal=goal)
    click.echo(f"Created plan '{name}' (ID: {plan.plan_id})")
    click.echo(f"Goal: {goal}")

    if output is not None:
        _builder.save(plan, str(output))
        click.echo(f"Plan saved to {output}")


@main.command("validate")
@click.option(
    "--plan",
    "plan_file",
    required=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Path to plan YAML file.",
)
def validate(plan_file: Path) -> None:
    """Validate a plan for structural correctness."""
    try:
        plan = _builder.load(str(plan_file))
    except Exception as exc:
        click.echo(f"Failed to load plan: {exc}", err=True)
        sys.exit(1)

    result = _builder.validate(plan)

    if result.valid:
        click.echo(f"Plan '{plan.name}' is valid.")
        click.echo(f"  Steps:               {len(plan.steps)}")
        click.echo(f"  Estimated duration:  {result.estimated_total_duration:.1f}s")
    else:
        click.echo(f"Plan '{plan.name}' has validation issues:")
        for issue in result.issues:
            click.echo(f"  - {issue}")
        sys.exit(1)


@main.command("optimize")
@click.option(
    "--plan",
    "plan_file",
    required=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Path to plan YAML file.",
)
def optimize(plan_file: Path) -> None:
    """Show parallel execution waves for a plan."""
    try:
        plan = _builder.load(str(plan_file))
    except Exception as exc:
        click.echo(f"Failed to load plan: {exc}", err=True)
        sys.exit(1)

    try:
        waves = _optimizer.parallelize(plan)
    except ValueError as exc:
        click.echo(f"Optimization failed: {exc}", err=True)
        sys.exit(1)

    click.echo(f"Plan '{plan.name}' — {len(waves)} parallel wave(s):")
    for wave_idx, wave_steps in enumerate(waves):
        wave_duration = max(
            (s.estimated_duration_seconds for s in wave_steps), default=0.0
        )
        step_names = ", ".join(f"'{s.action[:30]}'" for s in wave_steps)
        click.echo(
            f"  Wave {wave_idx + 1} ({len(wave_steps)} steps, "
            f"~{wave_duration:.1f}s): {step_names}"
        )


@main.command("run")
@click.option(
    "--plan",
    "plan_file",
    required=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Path to plan YAML file.",
)
def run(plan_file: Path) -> None:
    """Execute a plan and print the result."""
    try:
        plan = _builder.load(str(plan_file))
    except Exception as exc:
        click.echo(f"Failed to load plan: {exc}", err=True)
        sys.exit(1)

    click.echo(f"Executing plan '{plan.name}' ({len(plan.steps)} steps)...")
    result = _executor.execute(plan)

    click.echo(f"\nStatus: {result['status']}")
    click.echo(f"Steps completed: {result['steps_completed']}")
    click.echo(f"Duration: {result['total_duration_seconds']:.3f}s")

    if result.get("error"):
        click.echo(f"Error: {result['error']}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
