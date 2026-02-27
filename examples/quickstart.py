"""Quickstart examples for aumai-planforge.

Demonstrates the core capabilities of the agent planning framework:
  1. Build a plan manually with PlanBuilder and add steps with dependencies
  2. Validate a plan and inspect the results
  3. Compute parallel execution waves with PlanOptimizer
  4. Find the critical path with DependencyResolver
  5. Generate a plan automatically from Goal objects with PlanGenerator

Run this file directly to verify your installation:

    python examples/quickstart.py

All demos run without network access or a real LLM.
PyYAML is required for the save/load demo (pip install pyyaml).
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from aumai_planforge.core import (
    DependencyResolver,
    PlanBuilder,
    PlanExecutor,
    PlanGenerator,
    PlanOptimizer,
)
from aumai_planforge.models import Goal, Plan, PlanStep, PlanValidation


# ---------------------------------------------------------------------------
# Demo 1: Build a plan manually with PlanBuilder
# ---------------------------------------------------------------------------


def demo_plan_builder() -> Plan:
    """Create a release plan with realistic step dependencies."""
    print("=" * 60)
    print("Demo 1: PlanBuilder — create a plan with dependencies")
    print("=" * 60)

    builder = PlanBuilder()
    plan = builder.create(
        name="Release v2.0",
        goal="Ship version 2.0 to production with zero downtime",
    )

    # Wave 1: no dependencies
    freeze = builder.add_step(
        plan,
        action="Freeze feature branch and run full test suite",
        dependencies=[],
        duration=300.0,
        priority=1,
    )

    # Wave 2: both depend on freeze, but not on each other (parallel)
    build = builder.add_step(
        plan,
        action="Build and sign release artifact",
        dependencies=[freeze.step_id],
        duration=180.0,
        priority=1,
    )
    notify = builder.add_step(
        plan,
        action="Notify stakeholders of upcoming release window",
        dependencies=[freeze.step_id],
        duration=30.0,
        priority=3,
    )

    # Wave 3: depends on both wave-2 steps
    deploy = builder.add_step(
        plan,
        action="Deploy to production via blue-green switch",
        dependencies=[build.step_id, notify.step_id],
        duration=120.0,
        priority=1,
    )

    # Wave 4: final verification
    verify = builder.add_step(
        plan,
        action="Run smoke tests and verify SLO metrics",
        dependencies=[deploy.step_id],
        duration=60.0,
        priority=1,
    )

    print(f"\n  Plan created: '{plan.name}'")
    print(f"  Plan ID: {plan.plan_id}")
    print(f"  Steps: {len(plan.steps)}")
    print(f"  Status: {plan.status}")
    print()
    return plan


# ---------------------------------------------------------------------------
# Demo 2: Validate the plan
# ---------------------------------------------------------------------------


def demo_validation(plan: Plan) -> None:
    """Validate the plan and display the result."""
    print("=" * 60)
    print("Demo 2: PlanBuilder.validate — structural correctness check")
    print("=" * 60)

    builder = PlanBuilder()
    result: PlanValidation = builder.validate(plan)

    if result.valid:
        print(f"\n  Plan '{plan.name}' is VALID.")
        print(f"  Steps:               {len(plan.steps)}")
        print(f"  Estimated duration:  {result.estimated_total_duration:.0f}s "
              f"({result.estimated_total_duration / 60:.1f} min)")
    else:
        print(f"\n  Plan has {len(result.issues)} issue(s):")
        for issue in result.issues:
            print(f"    - {issue}")

    # Topological sort
    ordered = builder.topological_sort(plan)
    print("\n  Topological execution order:")
    for i, step in enumerate(ordered, 1):
        deps = f"deps={step.dependencies}" if step.dependencies else "no deps"
        print(f"    {i}. [{step.priority}] {step.action[:45]}  ({deps})")
    print()


# ---------------------------------------------------------------------------
# Demo 3: Parallel execution waves
# ---------------------------------------------------------------------------


def demo_parallelism(plan: Plan) -> None:
    """Show which steps can run concurrently."""
    print("=" * 60)
    print("Demo 3: PlanOptimizer — parallel execution waves")
    print("=" * 60)

    optimizer = PlanOptimizer()
    waves = optimizer.parallelize(plan)

    print(f"\n  Parallel waves: {len(waves)}")
    for i, wave in enumerate(waves):
        wave_duration = max(s.estimated_duration_seconds for s in wave)
        print(f"\n  Wave {i + 1} (max duration: {wave_duration:.0f}s, "
              f"{len(wave)} step{'s' if len(wave) != 1 else ''}):")
        for step in wave:
            print(f"    [{step.priority}] {step.action}")

    print()


# ---------------------------------------------------------------------------
# Demo 4: Critical path analysis
# ---------------------------------------------------------------------------


def demo_critical_path(plan: Plan) -> None:
    """Identify the critical path and compute minimum possible duration."""
    print("=" * 60)
    print("Demo 4: DependencyResolver — critical path analysis")
    print("=" * 60)

    resolver = DependencyResolver(plan.steps)

    # Critical path
    path = resolver.critical_path()
    critical_duration = resolver.total_duration_seconds()
    step_map = {s.step_id: s for s in plan.steps}

    print(f"\n  Critical path ({len(path)} steps, {critical_duration:.0f}s total):")
    for step_id in path:
        step = step_map[step_id]
        print(f"    -> {step.action} ({step.estimated_duration_seconds:.0f}s)")

    # Cycle check
    cycles = resolver.detect_cycles()
    print(f"\n  Cycles detected: {len(cycles)} (should be 0)")

    # Minimum duration
    print(f"\n  Minimum possible duration: {critical_duration:.0f}s "
          f"({critical_duration / 60:.1f} min)")
    print()


# ---------------------------------------------------------------------------
# Demo 5: Generate a plan from Goal objects
# ---------------------------------------------------------------------------


def demo_plan_generator() -> None:
    """Automatically decompose goals into a structured plan."""
    print("=" * 60)
    print("Demo 5: PlanGenerator — HTN-style goal decomposition")
    print("=" * 60)

    generator = PlanGenerator()

    goals = [
        Goal(
            goal_id="g1",
            description="Provision Kubernetes cluster on cloud provider",
            priority=9,
        ),
        Goal(
            goal_id="g2",
            description="Deploy application workloads and services",
            priority=8,
        ),
        Goal(
            goal_id="g3",
            description="Configure monitoring, alerting, and dashboards",
            priority=7,
        ),
    ]

    plan = generator.generate(goals, plan_name="Infrastructure Bootstrap")

    print(f"\n  Generated plan: '{plan.name}'")
    print(f"  Goals processed: {len(goals)}")
    print(f"  Steps generated: {len(plan.steps)} "
          f"(3 per goal: gather / act / verify)")
    print(f"  Estimated cost:  ${plan.estimated_cost:.4f}")
    print(f"  Estimated duration: {plan.estimated_duration_seconds:.0f}s "
          f"({plan.estimated_duration_seconds / 60:.1f} min)")

    print("\n  Step breakdown:")
    for step in plan.steps:
        dep_count = len(step.dependencies)
        print(f"    [{step.step_id:15s}] {step.action[:45]} "
              f"({step.estimated_duration_seconds:.0f}s, {dep_count} dep)")

    # Validate and optimize the generated plan
    builder = PlanBuilder()
    validation = builder.validate(plan)
    optimizer = PlanOptimizer()
    waves = optimizer.parallelize(plan)

    print(f"\n  Validation: {'VALID' if validation.valid else 'INVALID'}")
    print(f"  Parallel waves: {len(waves)}")
    print()


# ---------------------------------------------------------------------------
# Bonus: Save and load round-trip (requires PyYAML)
# ---------------------------------------------------------------------------


def demo_save_load(plan: Plan) -> None:
    """Save a plan to YAML and reload it."""
    print("=" * 60)
    print("Bonus: PlanBuilder save/load — YAML round-trip")
    print("=" * 60)

    builder = PlanBuilder()

    try:
        import yaml  # noqa: F401
    except ImportError:
        print("\n  PyYAML not installed. Skipping save/load demo.")
        print("  Install with: pip install pyyaml")
        print()
        return

    with tempfile.TemporaryDirectory() as tmpdir:
        path = str(Path(tmpdir) / "release_plan.yaml")
        builder.save(plan, path)
        print(f"\n  Saved plan to: {path}")

        loaded = builder.load(path)
        print(f"  Loaded plan: '{loaded.name}'")
        print(f"  Steps: {len(loaded.steps)} (original: {len(plan.steps)})")
        print(f"  Goal: {loaded.goal}")

        # Verify round-trip fidelity
        assert loaded.plan_id == plan.plan_id
        assert len(loaded.steps) == len(plan.steps)
        print("  Round-trip fidelity: OK")
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    """Run all quickstart demos in sequence."""
    print("\naumai-planforge — Quickstart Demo\n")

    # Demo 1 returns the plan for use in subsequent demos
    plan = demo_plan_builder()
    demo_validation(plan)
    demo_parallelism(plan)
    demo_critical_path(plan)
    demo_plan_generator()
    demo_save_load(plan)

    print("All demos complete.")


if __name__ == "__main__":
    main()
