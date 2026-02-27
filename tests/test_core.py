"""Comprehensive tests for aumai-planforge core module."""

from __future__ import annotations

from pathlib import Path

import pytest

from aumai_planforge.core import (
    CircularDependencyError,
    DependencyResolver,
    PlanBuilder,
    PlanExecutor,
    PlanGenerator,
    PlanOptimizer,
)
from aumai_planforge.models import Goal, Plan, PlanStep, PlanValidation


# ---------------------------------------------------------------------------
# PlanBuilder tests
# ---------------------------------------------------------------------------


class TestPlanBuilder:
    """Tests for PlanBuilder."""

    def test_create_returns_plan(self, builder: PlanBuilder) -> None:
        """create() returns a Plan with the given name and goal."""
        plan = builder.create(name="my-plan", goal="Achieve something great")
        assert plan.name == "my-plan"
        assert plan.goal == "Achieve something great"
        assert plan.plan_id != ""

    def test_create_status_is_draft(self, builder: PlanBuilder) -> None:
        """create() returns a plan in 'draft' status."""
        plan = builder.create(name="draft-plan", goal="Draft goal")
        assert plan.status == "draft"

    def test_create_empty_steps(self, builder: PlanBuilder) -> None:
        """create() returns a plan with no steps."""
        plan = builder.create(name="empty-plan", goal="Goal")
        assert plan.steps == []

    def test_add_step_appends_to_plan(self, builder: PlanBuilder) -> None:
        """add_step() appends a step to plan.steps."""
        plan = builder.create(name="test-plan", goal="Goal")
        step = builder.add_step(plan, action="Do something", dependencies=[], duration=30.0)
        assert len(plan.steps) == 1
        assert plan.steps[0].step_id == step.step_id

    def test_add_step_returns_plan_step(self, builder: PlanBuilder) -> None:
        """add_step() returns the newly created PlanStep."""
        plan = builder.create(name="test-plan", goal="Goal")
        step = builder.add_step(plan, action="Act", dependencies=[], duration=10.0)
        assert isinstance(step, PlanStep)
        assert step.action == "Act"

    def test_add_step_with_dependencies(self, simple_plan: Plan) -> None:
        """Steps in simple_plan correctly reference each other."""
        assert len(simple_plan.steps) == 2
        step_a = simple_plan.steps[0]
        step_b = simple_plan.steps[1]
        assert step_a.step_id in step_b.dependencies

    def test_validate_valid_plan(self, simple_plan: Plan, builder: PlanBuilder) -> None:
        """validate() returns valid=True for a correctly constructed plan."""
        result = builder.validate(simple_plan)
        assert isinstance(result, PlanValidation)
        assert result.valid is True
        assert result.issues == []

    def test_validate_estimates_duration(
        self, simple_plan: Plan, builder: PlanBuilder
    ) -> None:
        """validate() includes a non-zero duration estimate."""
        result = builder.validate(simple_plan)
        assert result.estimated_total_duration > 0.0

    def test_validate_detects_missing_dependency(self, builder: PlanBuilder) -> None:
        """validate() reports an issue when a step references a missing dependency."""
        plan = builder.create(name="broken", goal="Goal")
        step = PlanStep(
            step_id="orphan",
            action="Act",
            dependencies=["non-existent-step-id"],
            estimated_duration_seconds=10.0,
        )
        plan.steps.append(step)
        result = builder.validate(plan)
        assert result.valid is False
        assert any("non-existent-step-id" in issue for issue in result.issues)

    def test_validate_detects_circular_dependency(
        self, builder: PlanBuilder
    ) -> None:
        """validate() reports a circular dependency."""
        plan = builder.create(name="circular", goal="Goal")
        step_a = PlanStep(step_id="a", action="A", dependencies=["b"])
        step_b = PlanStep(step_id="b", action="B", dependencies=["a"])
        plan.steps.extend([step_a, step_b])
        result = builder.validate(plan)
        assert result.valid is False
        assert any("circular" in issue.lower() or "cycle" in issue.lower()
                   for issue in result.issues)

    def test_topological_sort_correct_order(
        self, simple_plan: Plan, builder: PlanBuilder
    ) -> None:
        """topological_sort() orders steps so dependencies come first."""
        sorted_steps = builder.topological_sort(simple_plan)
        assert sorted_steps[0].action == "Step A"
        assert sorted_steps[1].action == "Step B"

    def test_topological_sort_raises_on_cycle(self, builder: PlanBuilder) -> None:
        """topological_sort() raises CircularDependencyError for cyclic plans."""
        plan = builder.create(name="cyclic", goal="Goal")
        plan.steps.append(PlanStep(step_id="x", action="X", dependencies=["y"]))
        plan.steps.append(PlanStep(step_id="y", action="Y", dependencies=["x"]))
        with pytest.raises(CircularDependencyError):
            builder.topological_sort(plan)

    def test_save_and_load_plan(
        self, builder: PlanBuilder, simple_plan: Plan, tmp_path: Path
    ) -> None:
        """save() persists the plan and load() restores it faithfully."""
        file_path = str(tmp_path / "test_plan.yaml")
        builder.save(simple_plan, file_path)
        loaded = builder.load(file_path)
        assert loaded.name == simple_plan.name
        assert loaded.goal == simple_plan.goal
        assert len(loaded.steps) == len(simple_plan.steps)

    def test_load_restores_step_ids(
        self, builder: PlanBuilder, simple_plan: Plan, tmp_path: Path
    ) -> None:
        """load() restores step_ids correctly."""
        file_path = str(tmp_path / "restore_test.yaml")
        original_ids = [s.step_id for s in simple_plan.steps]
        builder.save(simple_plan, file_path)
        loaded = builder.load(file_path)
        loaded_ids = [s.step_id for s in loaded.steps]
        assert original_ids == loaded_ids


# ---------------------------------------------------------------------------
# PlanExecutor tests
# ---------------------------------------------------------------------------


class TestPlanExecutor:
    """Tests for PlanExecutor."""

    def test_execute_simple_plan_completes(
        self, executor: PlanExecutor, simple_plan: Plan
    ) -> None:
        """execute() runs all steps and returns status='completed'."""
        result = executor.execute(simple_plan)
        assert result["status"] == "completed"

    def test_execute_returns_correct_step_count(
        self, executor: PlanExecutor, simple_plan: Plan
    ) -> None:
        """execute() reports the correct number of completed steps."""
        result = executor.execute(simple_plan)
        assert result["steps_completed"] == 2

    def test_execute_returns_duration(
        self, executor: PlanExecutor, simple_plan: Plan
    ) -> None:
        """execute() returns a non-negative total_duration_seconds."""
        result = executor.execute(simple_plan)
        assert result["total_duration_seconds"] >= 0.0

    def test_execute_returns_step_log(
        self, executor: PlanExecutor, simple_plan: Plan
    ) -> None:
        """execute() includes a step log in the result."""
        result = executor.execute(simple_plan)
        steps = result["steps"]
        assert len(steps) == 2
        assert all(s["status"] == "completed" for s in steps)

    def test_execute_circular_returns_failed(
        self, executor: PlanExecutor, builder: PlanBuilder
    ) -> None:
        """execute() returns status='failed' for cyclic plans."""
        plan = builder.create(name="cyclic", goal="Goal")
        plan.steps.append(PlanStep(step_id="x", action="X", dependencies=["y"]))
        plan.steps.append(PlanStep(step_id="y", action="Y", dependencies=["x"]))
        result = executor.execute(plan)
        assert result["status"] == "failed"
        assert "error" in result

    def test_execute_empty_plan(
        self, executor: PlanExecutor, builder: PlanBuilder
    ) -> None:
        """execute() handles empty plan gracefully."""
        plan = builder.create(name="empty", goal="Nothing")
        result = executor.execute(plan)
        assert result["steps_completed"] == 0

    def test_get_ready_steps_no_deps(
        self, executor: PlanExecutor, builder: PlanBuilder
    ) -> None:
        """get_ready_steps() returns pending steps with no dependencies."""
        plan = builder.create(name="ready-test", goal="Goal")
        builder.add_step(plan, action="A", dependencies=[], duration=5.0)
        ready = executor.get_ready_steps(plan)
        assert len(ready) == 1

    def test_get_ready_steps_respects_completed(
        self, executor: PlanExecutor, simple_plan: Plan
    ) -> None:
        """get_ready_steps() returns dependent steps when dependencies are completed."""
        step_a = simple_plan.steps[0]
        step_b = simple_plan.steps[1]
        step_a.status = "completed"
        ready = executor.get_ready_steps(simple_plan)
        assert any(s.step_id == step_b.step_id for s in ready)


# ---------------------------------------------------------------------------
# PlanOptimizer tests
# ---------------------------------------------------------------------------


class TestPlanOptimizer:
    """Tests for PlanOptimizer."""

    def test_parallelize_single_step_plan(
        self, optimizer: PlanOptimizer, builder: PlanBuilder
    ) -> None:
        """parallelize() returns a single wave for a plan with one step."""
        plan = builder.create(name="solo", goal="Goal")
        builder.add_step(plan, action="Only", dependencies=[], duration=5.0)
        waves = optimizer.parallelize(plan)
        assert len(waves) == 1
        assert len(waves[0]) == 1

    def test_parallelize_sequential_creates_waves(
        self, optimizer: PlanOptimizer, simple_plan: Plan
    ) -> None:
        """parallelize() creates one wave per sequential step."""
        waves = optimizer.parallelize(simple_plan)
        assert len(waves) == 2

    def test_parallelize_parallel_steps_in_same_wave(
        self, optimizer: PlanOptimizer, parallel_plan: Plan
    ) -> None:
        """parallelize() puts independent steps in the same wave."""
        waves = optimizer.parallelize(parallel_plan)
        # Wave 0: A; Wave 1: B and C
        assert len(waves) >= 2
        wave_1_step_count = len(waves[1])
        assert wave_1_step_count == 2

    def test_parallelize_empty_plan(
        self, optimizer: PlanOptimizer, builder: PlanBuilder
    ) -> None:
        """parallelize() returns empty list for an empty plan."""
        plan = builder.create(name="empty", goal="Goal")
        waves = optimizer.parallelize(plan)
        assert waves == []

    def test_parallelize_wave_sorted_by_priority(
        self, optimizer: PlanOptimizer, parallel_plan: Plan
    ) -> None:
        """parallelize() sorts steps within a wave by priority ascending."""
        waves = optimizer.parallelize(parallel_plan)
        if len(waves) > 1:
            wave = waves[1]
            priorities = [s.priority for s in wave]
            assert priorities == sorted(priorities)

    def test_parallelize_raises_on_circular(
        self, optimizer: PlanOptimizer, builder: PlanBuilder
    ) -> None:
        """parallelize() raises CircularDependencyError for cyclic plans."""
        plan = builder.create(name="cyclic", goal="Goal")
        plan.steps.append(PlanStep(step_id="p", action="P", dependencies=["q"]))
        plan.steps.append(PlanStep(step_id="q", action="Q", dependencies=["p"]))
        with pytest.raises(CircularDependencyError):
            optimizer.parallelize(plan)


# ---------------------------------------------------------------------------
# DependencyResolver tests
# ---------------------------------------------------------------------------


class TestDependencyResolver:
    """Tests for DependencyResolver."""

    def test_topological_sort_two_steps(self) -> None:
        """topological_sort() returns steps in dependency order."""
        step_a = PlanStep(step_id="a", action="A", dependencies=[], estimated_duration_seconds=5.0)
        step_b = PlanStep(step_id="b", action="B", dependencies=["a"], estimated_duration_seconds=10.0)
        resolver = DependencyResolver([step_a, step_b])
        sorted_steps = resolver.topological_sort()
        assert sorted_steps[0].step_id == "a"
        assert sorted_steps[1].step_id == "b"

    def test_topological_sort_raises_on_cycle(self) -> None:
        """topological_sort() raises CircularDependencyError for cyclic steps."""
        step_a = PlanStep(step_id="a", action="A", dependencies=["b"])
        step_b = PlanStep(step_id="b", action="B", dependencies=["a"])
        resolver = DependencyResolver([step_a, step_b])
        with pytest.raises(CircularDependencyError):
            resolver.topological_sort()

    def test_detect_cycles_no_cycles(self) -> None:
        """detect_cycles() returns empty list when no cycles exist."""
        step_a = PlanStep(step_id="a", action="A", dependencies=[])
        step_b = PlanStep(step_id="b", action="B", dependencies=["a"])
        resolver = DependencyResolver([step_a, step_b])
        cycles = resolver.detect_cycles()
        assert cycles == []

    def test_detect_cycles_finds_cycle(self) -> None:
        """detect_cycles() returns a non-empty list when a cycle exists."""
        step_a = PlanStep(step_id="a", action="A", dependencies=["b"])
        step_b = PlanStep(step_id="b", action="B", dependencies=["a"])
        resolver = DependencyResolver([step_a, step_b])
        cycles = resolver.detect_cycles()
        assert len(cycles) > 0

    def test_critical_path_simple(self) -> None:
        """critical_path() returns the path through the longest-duration steps."""
        step_a = PlanStep(step_id="a", action="A", dependencies=[], estimated_duration_seconds=5.0)
        step_b = PlanStep(step_id="b", action="B", dependencies=["a"], estimated_duration_seconds=10.0)
        resolver = DependencyResolver([step_a, step_b])
        path = resolver.critical_path()
        assert "a" in path
        assert "b" in path

    def test_critical_path_selects_longest_branch(self) -> None:
        """critical_path() selects the branch with the longest total duration."""
        start = PlanStep(step_id="s", action="S", dependencies=[], estimated_duration_seconds=1.0)
        short = PlanStep(step_id="short", action="Short", dependencies=["s"], estimated_duration_seconds=2.0)
        long_ = PlanStep(step_id="long", action="Long", dependencies=["s"], estimated_duration_seconds=20.0)
        resolver = DependencyResolver([start, short, long_])
        path = resolver.critical_path()
        assert "long" in path
        assert "short" not in path

    def test_total_duration_seconds(self) -> None:
        """total_duration_seconds() returns sum of critical path durations."""
        step_a = PlanStep(step_id="a", action="A", dependencies=[], estimated_duration_seconds=5.0)
        step_b = PlanStep(step_id="b", action="B", dependencies=["a"], estimated_duration_seconds=10.0)
        resolver = DependencyResolver([step_a, step_b])
        total = resolver.total_duration_seconds()
        assert total == 15.0

    def test_total_duration_circular_returns_zero(self) -> None:
        """total_duration_seconds() returns 0.0 when cycle prevents computation."""
        step_a = PlanStep(step_id="a", action="A", dependencies=["b"])
        step_b = PlanStep(step_id="b", action="B", dependencies=["a"])
        resolver = DependencyResolver([step_a, step_b])
        assert resolver.total_duration_seconds() == 0.0


# ---------------------------------------------------------------------------
# PlanGenerator tests
# ---------------------------------------------------------------------------


class TestPlanGenerator:
    """Tests for PlanGenerator."""

    def test_generate_single_goal(self, goal_a: Goal) -> None:
        """generate() creates a plan for a single goal."""
        gen = PlanGenerator()
        plan = gen.generate([goal_a])
        assert isinstance(plan, Plan)
        assert plan.plan_id != ""
        assert len(plan.steps) == 3  # gather / act / verify

    def test_generate_two_goals(self, goal_a: Goal, goal_b: Goal) -> None:
        """generate() creates steps for each goal."""
        gen = PlanGenerator()
        plan = gen.generate([goal_a, goal_b])
        assert len(plan.steps) == 6  # 3 steps per goal

    def test_generate_custom_plan_name(self, goal_a: Goal) -> None:
        """generate() uses the provided plan_name."""
        gen = PlanGenerator()
        plan = gen.generate([goal_a], plan_name="Custom Plan Name")
        assert plan.name == "Custom Plan Name"

    def test_generate_default_plan_name_uses_first_goal(
        self, goal_a: Goal
    ) -> None:
        """generate() uses the first goal description as plan name when none provided."""
        gen = PlanGenerator()
        plan = gen.generate([goal_a])
        assert "Set up infrastructure" in plan.name

    def test_generate_raises_for_empty_goals(self) -> None:
        """generate() raises ValueError for empty goals list."""
        gen = PlanGenerator()
        with pytest.raises(ValueError, match="At least one goal"):
            gen.generate([])

    def test_generate_goals_sorted_by_priority(
        self, goal_a: Goal, goal_b: Goal
    ) -> None:
        """generate() sorts goals by priority (highest first)."""
        gen = PlanGenerator()
        plan = gen.generate([goal_b, goal_a])  # goal_a has higher priority
        assert plan.goals[0].goal_id == "goal-a"

    def test_generate_includes_goals_in_plan(
        self, goal_a: Goal, goal_b: Goal
    ) -> None:
        """generate() stores the sorted goals on the plan."""
        gen = PlanGenerator()
        plan = gen.generate([goal_a, goal_b])
        goal_ids = [g.goal_id for g in plan.goals]
        assert "goal-a" in goal_ids
        assert "goal-b" in goal_ids

    def test_generate_step_descriptions_reference_goal(
        self, goal_a: Goal
    ) -> None:
        """generate() step actions reference the goal description."""
        gen = PlanGenerator()
        plan = gen.generate([goal_a])
        actions = [s.action for s in plan.steps]
        assert any("Set up infrastructure" in a for a in actions)

    def test_generate_has_cost_estimate(self, goal_a: Goal) -> None:
        """generate() sets a non-negative cost estimate."""
        gen = PlanGenerator()
        plan = gen.generate([goal_a])
        assert plan.estimated_cost >= 0.0

    def test_generate_has_duration_estimate(self, goal_a: Goal) -> None:
        """generate() sets a positive duration estimate."""
        gen = PlanGenerator()
        plan = gen.generate([goal_a])
        assert plan.estimated_duration_seconds > 0.0
