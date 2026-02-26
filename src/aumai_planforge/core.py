"""Core logic for aumai-planforge.

Provides:
- PlanBuilder: create, validate, topologically sort, and save/load plans
- PlanExecutor: execute plans in dependency order with step tracking
- PlanOptimizer: parallelize steps into execution waves
- DependencyResolver: critical-path analysis on a step list
- PlanGenerator: generate plans from Goal objects (HTN decomposition)
"""

from __future__ import annotations

import time
import uuid
from collections import Counter, defaultdict, deque
from datetime import datetime
from typing import Any

from aumai_planforge.models import (
    ExecutionState,
    Goal,
    Plan,
    PlanStatus,
    PlanStep,
    PlanValidation,
)

__all__ = [
    "PlanBuilder",
    "PlanExecutor",
    "PlanOptimizer",
    "DependencyResolver",
    "PlanGenerator",
]


class CircularDependencyError(ValueError):
    """Raised when a circular dependency is detected in a plan."""


class PlanBuilder:
    """Build, validate, and sort execution plans."""

    def create(self, name: str, goal: str) -> Plan:
        """Create a new empty plan.

        Args:
            name: Human-readable plan name.
            goal: The objective this plan achieves.

        Returns:
            A new Plan in 'draft' status.
        """
        return Plan(
            plan_id=str(uuid.uuid4()),
            name=name,
            goal=goal,
            created_at=datetime.utcnow(),
        )

    def add_step(
        self,
        plan: Plan,
        action: str,
        dependencies: list[str],
        duration: float,
        priority: int = 5,
    ) -> PlanStep:
        """Add a step to a plan.

        Args:
            plan: The plan to extend.
            action: Description of the action.
            dependencies: step_ids this step depends on.
            duration: Estimated duration in seconds.
            priority: Priority 1-10 (1=highest).

        Returns:
            The newly created PlanStep.
        """
        step = PlanStep(
            step_id=str(uuid.uuid4()),
            action=action,
            dependencies=dependencies,
            estimated_duration_seconds=duration,
            priority=priority,
        )
        plan.steps.append(step)
        return step

    def validate(self, plan: Plan) -> PlanValidation:
        """Validate a plan for structural correctness.

        Checks:
        - No duplicate step_ids
        - All dependency references exist
        - No circular dependencies (via topological sort)

        Args:
            plan: The plan to validate.

        Returns:
            PlanValidation with issues list and duration estimate.
        """
        issues: list[str] = []
        step_ids = {step.step_id for step in plan.steps}

        # Duplicate IDs
        if len(step_ids) != len(plan.steps):
            issues.append("Duplicate step_ids detected.")

        # Missing dependencies
        for step in plan.steps:
            for dep_id in step.dependencies:
                if dep_id not in step_ids:
                    issues.append(
                        f"Step '{step.step_id}' depends on '{dep_id}' which does not exist."
                    )

        # Circular dependency check
        if not issues:
            try:
                sorted_steps = self.topological_sort(plan)
                # Estimate total sequential duration
                total_duration = sum(s.estimated_duration_seconds for s in sorted_steps)
            except CircularDependencyError as exc:
                issues.append(str(exc))
                total_duration = sum(s.estimated_duration_seconds for s in plan.steps)
        else:
            total_duration = sum(s.estimated_duration_seconds for s in plan.steps)

        return PlanValidation(
            plan=plan,
            valid=len(issues) == 0,
            issues=issues,
            estimated_total_duration=total_duration,
        )

    def topological_sort(self, plan: Plan) -> list[PlanStep]:
        """Sort plan steps in dependency order using Kahn's algorithm.

        Args:
            plan: The plan to sort.

        Returns:
            Steps ordered so each step appears after its dependencies.

        Raises:
            CircularDependencyError: If the dependency graph contains a cycle.
        """
        step_map = {step.step_id: step for step in plan.steps}
        in_degree: dict[str, int] = {step.step_id: 0 for step in plan.steps}
        adjacency: dict[str, list[str]] = defaultdict(list)

        for step in plan.steps:
            for dep_id in step.dependencies:
                if dep_id in step_map:
                    adjacency[dep_id].append(step.step_id)
                    in_degree[step.step_id] += 1

        queue: deque[str] = deque(
            step_id for step_id, degree in in_degree.items() if degree == 0
        )
        sorted_ids: list[str] = []

        while queue:
            current_id = queue.popleft()
            sorted_ids.append(current_id)
            for neighbor_id in adjacency[current_id]:
                in_degree[neighbor_id] -= 1
                if in_degree[neighbor_id] == 0:
                    queue.append(neighbor_id)

        if len(sorted_ids) != len(plan.steps):
            raise CircularDependencyError(
                "Circular dependency detected in plan. "
                f"Could not sort {len(plan.steps) - len(sorted_ids)} steps."
            )

        return [step_map[step_id] for step_id in sorted_ids]

    def save(self, plan: Plan, path: str) -> None:
        """Persist a plan to a YAML file.

        Args:
            plan: The plan to save.
            path: Output file path.
        """
        from pathlib import Path

        import yaml  # type: ignore[import-untyped]

        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            yaml.dump(plan.model_dump(mode="json"), allow_unicode=True),
            encoding="utf-8",
        )

    def load(self, path: str) -> Plan:
        """Load a plan from a YAML file.

        Args:
            path: Input file path.

        Returns:
            Deserialized Plan.
        """
        from pathlib import Path

        import yaml  # type: ignore[import-untyped]

        raw = Path(path).read_text(encoding="utf-8")
        data: dict[str, object] = yaml.safe_load(raw)
        return Plan.model_validate(data)


class PlanExecutor:
    """Execute a plan by running steps in dependency order."""

    def __init__(self, builder: PlanBuilder | None = None) -> None:
        self._builder = builder or PlanBuilder()

    def execute(self, plan: Plan) -> dict[str, object]:
        """Execute all plan steps in dependency order.

        Steps are executed sequentially. A step is skipped if any of its
        dependencies failed.

        Args:
            plan: The plan to execute.

        Returns:
            Execution summary with step statuses and total duration.
        """
        start_time = time.monotonic()
        completed_ids: set[str] = set()
        failed_ids: set[str] = set()
        step_log: list[dict[str, object]] = []

        try:
            ordered_steps = self._builder.topological_sort(plan)
        except CircularDependencyError as exc:
            return {
                "status": "failed",
                "error": str(exc),
                "steps": [],
                "duration_seconds": 0.0,
            }

        for step in ordered_steps:
            # Check if any dependency failed
            if any(dep_id in failed_ids for dep_id in step.dependencies):
                step.status = "skipped"
                step_log.append({
                    "step_id": step.step_id,
                    "action": step.action,
                    "status": "skipped",
                    "reason": "dependency failed",
                })
                continue

            step.status = "running"
            step_start = time.monotonic()

            # Simulate execution (in production this would dispatch to real handlers)
            step.status = "completed"
            completed_ids.add(step.step_id)
            step_duration = time.monotonic() - step_start

            step_log.append({
                "step_id": step.step_id,
                "action": step.action,
                "status": "completed",
                "duration_seconds": round(step_duration, 4),
            })

        total_duration = time.monotonic() - start_time
        all_completed = len(completed_ids) == len(plan.steps)
        plan.status = "completed" if all_completed else "failed"

        return {
            "plan_id": plan.plan_id,
            "status": plan.status,
            "steps_completed": len(completed_ids),
            "steps_failed": len(failed_ids),
            "total_duration_seconds": round(total_duration, 4),
            "steps": step_log,
        }

    def get_ready_steps(self, plan: Plan) -> list[PlanStep]:
        """Return steps whose dependencies are all completed.

        Args:
            plan: The plan to inspect.

        Returns:
            List of PlanStep objects in 'pending' status whose dependencies
            have all 'completed' status.
        """
        completed_ids = {
            step.step_id for step in plan.steps if step.status == "completed"
        }
        return [
            step
            for step in plan.steps
            if step.status == "pending"
            and all(dep_id in completed_ids for dep_id in step.dependencies)
        ]


class PlanOptimizer:
    """Analyse and optimize plan execution strategies."""

    def __init__(self, builder: PlanBuilder | None = None) -> None:
        self._builder = builder or PlanBuilder()

    def parallelize(self, plan: Plan) -> list[list[PlanStep]]:
        """Group steps into parallel execution waves.

        Each wave contains steps whose dependencies are all satisfied by
        previous waves. Steps within a wave can execute concurrently.

        Args:
            plan: The plan to parallelize.

        Returns:
            List of waves, where each wave is a list of steps that can
            execute simultaneously.

        Raises:
            CircularDependencyError: If the plan has circular dependencies.
        """
        sorted_steps = self._builder.topological_sort(plan)
        step_to_wave: dict[str, int] = {}

        for step in sorted_steps:
            if not step.dependencies:
                step_to_wave[step.step_id] = 0
            else:
                max_dep_wave = max(
                    step_to_wave.get(dep_id, 0)
                    for dep_id in step.dependencies
                )
                step_to_wave[step.step_id] = max_dep_wave + 1

        if not step_to_wave:
            return []

        max_wave = max(step_to_wave.values())
        waves: list[list[PlanStep]] = [[] for _ in range(max_wave + 1)]
        step_map = {step.step_id: step for step in plan.steps}

        for step_id, wave_idx in step_to_wave.items():
            waves[wave_idx].append(step_map[step_id])

        # Within each wave, sort by priority (ascending = higher priority first)
        for wave in waves:
            wave.sort(key=lambda s: s.priority)

        return waves


# ---------------------------------------------------------------------------
# DependencyResolver
# ---------------------------------------------------------------------------


class DependencyResolver:
    """Resolve step dependencies, detect cycles, and find the critical path.

    Example::

        resolver = DependencyResolver(plan.steps)
        order = resolver.topological_sort()
        path = resolver.critical_path()
    """

    def __init__(self, steps: list[PlanStep]) -> None:
        self._steps: dict[str, PlanStep] = {step.step_id: step for step in steps}

    def topological_sort(self) -> list[PlanStep]:
        """Return steps in dependency order (Kahn's algorithm).

        Raises:
            CircularDependencyError: If cycles exist.
        """
        in_degree: dict[str, int] = {sid: 0 for sid in self._steps}
        adjacency: dict[str, list[str]] = {sid: [] for sid in self._steps}

        for step in self._steps.values():
            for dep_id in step.dependencies:
                if dep_id in self._steps:
                    adjacency[dep_id].append(step.step_id)
                    in_degree[step.step_id] += 1

        queue: deque[str] = deque(
            sid for sid, deg in in_degree.items() if deg == 0
        )
        sorted_ids: list[str] = []

        while queue:
            current = queue.popleft()
            sorted_ids.append(current)
            for neighbor in adjacency[current]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(sorted_ids) != len(self._steps):
            raise CircularDependencyError(
                f"Circular dependency detected. Could not order: "
                f"{set(self._steps) - set(sorted_ids)}"
            )

        return [self._steps[sid] for sid in sorted_ids]

    def detect_cycles(self) -> list[list[str]]:
        """Return list of cycles (each as list of step_ids), empty if none."""
        visited: set[str] = set()
        rec_stack: set[str] = set()
        cycles: list[list[str]] = []

        def dfs(node: str, path: list[str]) -> None:
            visited.add(node)
            rec_stack.add(node)
            path.append(node)
            step = self._steps.get(node)
            if step:
                for dep in step.dependencies:
                    if dep not in self._steps:
                        continue
                    if dep not in visited:
                        dfs(dep, path)
                    elif dep in rec_stack:
                        start = path.index(dep)
                        cycles.append(path[start:] + [dep])
            rec_stack.discard(node)
            path.pop()

        for sid in self._steps:
            if sid not in visited:
                dfs(sid, [])

        return cycles

    def critical_path(self) -> list[str]:
        """Compute the critical path (longest duration path) through the DAG.

        Raises:
            CircularDependencyError: If cycles exist.
        """
        sorted_steps = self.topological_sort()
        earliest_start: dict[str, float] = {s.step_id: 0.0 for s in sorted_steps}
        predecessor: dict[str, str | None] = {s.step_id: None for s in sorted_steps}

        for step in sorted_steps:
            deps_in_plan = [d for d in step.dependencies if d in self._steps]
            if deps_in_plan:
                max_finish = max(
                    earliest_start[d] + self._steps[d].estimated_duration_seconds
                    for d in deps_in_plan
                )
                if max_finish > earliest_start[step.step_id]:
                    earliest_start[step.step_id] = max_finish
                    predecessor[step.step_id] = max(
                        deps_in_plan,
                        key=lambda d: earliest_start[d] + self._steps[d].estimated_duration_seconds,
                    )

        if not sorted_steps:
            return []

        end = max(
            sorted_steps,
            key=lambda s: earliest_start[s.step_id] + s.estimated_duration_seconds,
        )
        path: list[str] = []
        current: str | None = end.step_id
        while current is not None:
            path.append(current)
            current = predecessor[current]
        path.reverse()
        return path

    def total_duration_seconds(self) -> float:
        """Return critical-path duration in seconds."""
        try:
            path = self.critical_path()
        except CircularDependencyError:
            return 0.0
        return sum(
            self._steps[sid].estimated_duration_seconds
            for sid in path
            if sid in self._steps
        )


# ---------------------------------------------------------------------------
# PlanGenerator
# ---------------------------------------------------------------------------


class PlanGenerator:
    """Generate plans from goals using HTN-style hierarchical decomposition.

    Example::

        generator = PlanGenerator()
        plan = generator.generate([goal1, goal2])
    """

    def generate(
        self,
        goals: list[Goal],
        plan_name: str | None = None,
    ) -> Plan:
        """Generate a plan that addresses all provided goals.

        Args:
            goals: List of Goal objects to achieve.
            plan_name: Optional name for the generated plan.

        Returns:
            A Plan with steps derived from the goals.
        """
        if not goals:
            raise ValueError("At least one goal is required.")

        plan_id = str(uuid.uuid4())
        name = plan_name or f"Plan for {goals[0].description[:40]}"
        primary_goal = "; ".join(g.description for g in goals)
        sorted_goals = sorted(goals, key=lambda g: g.priority, reverse=True)

        all_steps: list[PlanStep] = []
        previous_ids: list[str] = []

        for idx, goal in enumerate(sorted_goals):
            steps = self._decompose_goal(goal, idx, previous_ids)
            all_steps.extend(steps)
            previous_ids = [s.step_id for s in steps]

        resolver = DependencyResolver(all_steps)
        duration = resolver.total_duration_seconds()
        cost = sum(s.estimated_duration_seconds * 0.01 for s in all_steps)

        return Plan(
            plan_id=plan_id,
            name=name,
            goal=primary_goal,
            goals=sorted_goals,
            steps=all_steps,
            status="draft",
            estimated_cost=round(cost, 4),
            estimated_duration_seconds=round(duration, 2),
        )

    def _decompose_goal(
        self,
        goal: Goal,
        goal_index: int,
        previous_step_ids: list[str],
    ) -> list[PlanStep]:
        """Decompose a single goal into gather / act / verify steps."""
        prefix = f"g{goal_index}"
        gather_id = f"{prefix}_gather"
        act_id = f"{prefix}_act"
        verify_id = f"{prefix}_verify"

        return [
            PlanStep(
                step_id=gather_id,
                action=f"Gather information for: {goal.description}",
                preconditions=[],
                effects=[f"info_ready_{goal_index}"],
                dependencies=list(previous_step_ids),
                estimated_duration_seconds=30.0,
                priority=goal.priority,
            ),
            PlanStep(
                step_id=act_id,
                action=f"Execute action to achieve: {goal.description}",
                preconditions=[f"info_ready_{goal_index}"],
                effects=[f"action_done_{goal_index}"],
                dependencies=[gather_id],
                estimated_duration_seconds=60.0,
                priority=goal.priority,
            ),
            PlanStep(
                step_id=verify_id,
                action=f"Verify outcome of: {goal.description}",
                preconditions=[f"action_done_{goal_index}"],
                effects=[f"goal_{goal_index}_verified"],
                dependencies=[act_id],
                estimated_duration_seconds=15.0,
                priority=goal.priority,
            ),
        ]
