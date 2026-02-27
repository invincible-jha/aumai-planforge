"""Shared test fixtures for aumai-planforge."""

from __future__ import annotations

from pathlib import Path

import pytest

from aumai_planforge.core import PlanBuilder, PlanExecutor, PlanOptimizer
from aumai_planforge.models import Goal, Plan, PlanStep


@pytest.fixture()
def builder() -> PlanBuilder:
    """Return a PlanBuilder instance."""
    return PlanBuilder()


@pytest.fixture()
def executor(builder: PlanBuilder) -> PlanExecutor:
    """Return a PlanExecutor backed by the builder fixture."""
    return PlanExecutor(builder=builder)


@pytest.fixture()
def optimizer(builder: PlanBuilder) -> PlanOptimizer:
    """Return a PlanOptimizer backed by the builder fixture."""
    return PlanOptimizer(builder=builder)


@pytest.fixture()
def simple_plan(builder: PlanBuilder) -> Plan:
    """Return a plan with two sequential steps (A -> B)."""
    plan = builder.create(name="simple-plan", goal="Achieve simple goal")
    step_a = builder.add_step(plan, action="Step A", dependencies=[], duration=10.0, priority=1)
    builder.add_step(plan, action="Step B", dependencies=[step_a.step_id], duration=20.0, priority=2)
    return plan


@pytest.fixture()
def parallel_plan(builder: PlanBuilder) -> Plan:
    """Return a plan where steps B and C can run in parallel after A."""
    plan = builder.create(name="parallel-plan", goal="Run things in parallel")
    step_a = builder.add_step(plan, action="Step A", dependencies=[], duration=5.0, priority=1)
    builder.add_step(plan, action="Step B", dependencies=[step_a.step_id], duration=10.0, priority=2)
    builder.add_step(plan, action="Step C", dependencies=[step_a.step_id], duration=8.0, priority=3)
    return plan


@pytest.fixture()
def goal_a() -> Goal:
    """Return a high-priority goal."""
    return Goal(
        goal_id="goal-a",
        description="Set up infrastructure",
        priority=8,
    )


@pytest.fixture()
def goal_b() -> Goal:
    """Return a lower-priority goal."""
    return Goal(
        goal_id="goal-b",
        description="Deploy application",
        priority=5,
    )


@pytest.fixture()
def saved_plan_file(builder: PlanBuilder, simple_plan: Plan, tmp_path: Path) -> Path:
    """Save a plan to a YAML file and return the path."""
    file = tmp_path / "plan.yaml"
    builder.save(simple_plan, str(file))
    return file
