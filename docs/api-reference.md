# API Reference — aumai-planforge

Complete reference for all public classes, functions, and Pydantic models in `aumai-planforge`.

---

## Module: `aumai_planforge.models`

Pydantic v2 models for goals, plan steps, plans, execution state, and validation results.

---

### `PlanStatus`

```python
class PlanStatus(str, Enum)
```

Lifecycle status of a plan.

| Value | Description |
|-------|-------------|
| `DRAFT` | Plan is being assembled |
| `ACTIVE` | Plan has been accepted and is ready to execute |
| `COMPLETED` | All steps have completed successfully |
| `FAILED` | One or more steps failed |

---

### `Goal`

```python
class Goal(BaseModel)
```

A high-level objective to be achieved by a plan.

**Fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `goal_id` | `str` | Required | Unique goal identifier. Whitespace is stripped. |
| `description` | `str` | Required | Natural language description of the goal. Whitespace is stripped. |
| `priority` | `int` | `5` | Priority from `1` (lowest) to `10` (highest). Range: `1`–`10`. |
| `deadline` | `str \| None` | `None` | Optional ISO-8601 deadline string. |
| `metadata` | `dict[str, object]` | `{}` | Arbitrary extra data. |

**Example:**

```python
from aumai_planforge.models import Goal

goal = Goal(
    goal_id="g1",
    description="Deploy service to production",
    priority=9,
    deadline="2026-03-01T00:00:00Z",
)
```

---

### `PlanStep`

```python
class PlanStep(BaseModel)
```

A single actionable step within a plan.

**Fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `step_id` | `str` | Required | Unique step identifier within the plan. |
| `action` | `str` | Required | Human-readable description of what this step does. |
| `preconditions` | `list[str]` | `[]` | World-state conditions that must hold before this step can execute. |
| `effects` | `list[str]` | `[]` | World-state changes produced by completing this step. |
| `dependencies` | `list[str]` | `[]` | `step_id` values of steps that must complete before this step. |
| `estimated_duration_seconds` | `float` | `60.0` | Expected execution time. Minimum: `0.0`. |
| `priority` | `int` | `5` | Priority where `1` = highest. Range: `1`–`10`. Used for ordering within parallel waves. |
| `status` | `Literal[...]` | `"pending"` | Current execution status. One of: `pending`, `running`, `completed`, `failed`, `skipped`. |
| `metadata` | `dict[str, object]` | `{}` | Arbitrary extra data. |

**Example:**

```python
from aumai_planforge.models import PlanStep

step = PlanStep(
    step_id="build-001",
    action="Build Docker image",
    dependencies=["test-001"],
    estimated_duration_seconds=180.0,
    priority=2,
)
```

---

### `Plan`

```python
class Plan(BaseModel)
```

A structured plan composed of steps with dependency links.

**Fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `plan_id` | `str` | Required | Unique plan identifier. |
| `name` | `str` | Required | Human-readable plan name. |
| `goal` | `str` | Required | Primary goal description. |
| `goals` | `list[Goal]` | `[]` | Structured goal objects (populated by `PlanGenerator`). |
| `steps` | `list[PlanStep]` | `[]` | All plan steps. |
| `status` | `Literal[...]` | `"draft"` | One of: `draft`, `validated`, `active`, `running`, `completed`, `failed`. |
| `estimated_cost` | `float` | `0.0` | Heuristic cost estimate. Minimum: `0.0`. |
| `estimated_duration_seconds` | `float` | `0.0` | Critical-path duration estimate. Minimum: `0.0`. |
| `created_at` | `datetime` | `datetime.now(UTC)` | UTC creation timestamp. |
| `metadata` | `dict[str, object]` | `{}` | Arbitrary extra data. |

---

### `ExecutionState`

```python
class ExecutionState(BaseModel)
```

Tracks the runtime state of plan execution.

**Fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `plan_id` | `str` | Required | ID of the plan being tracked. |
| `current_step_id` | `str \| None` | `None` | ID of the step currently executing. |
| `completed_steps` | `list[str]` | `[]` | IDs of successfully completed steps. |
| `blocked_steps` | `list[str]` | `[]` | IDs of steps blocked on unmet dependencies. |
| `failed_steps` | `list[str]` | `[]` | IDs of failed steps. |
| `status` | `PlanStatus` | `PlanStatus.ACTIVE` | Overall execution status. |
| `execution_log` | `list[dict[str, object]]` | `[]` | Ordered log of execution events. |

---

### `PlanValidation`

```python
class PlanValidation(BaseModel)
```

Result of validating a plan's structure.

**Fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `plan` | `Plan` | Required | The plan that was validated. |
| `valid` | `bool` | Required | `True` if no issues were found. |
| `issues` | `list[str]` | `[]` | Human-readable descriptions of structural problems. |
| `estimated_total_duration` | `float` | `0.0` | Sum of all step durations if valid (sequential estimate). Minimum: `0.0`. |

---

## Module: `aumai_planforge.core`

---

### `CircularDependencyError`

```python
class CircularDependencyError(ValueError)
```

Raised when a circular dependency is detected during topological sort. Message identifies how many steps could not be ordered, or the specific step IDs involved.

---

### `PlanBuilder`

```python
class PlanBuilder
```

Build, validate, topologically sort, and persist execution plans.

#### `create`

```python
def create(self, name: str, goal: str) -> Plan
```

Create a new empty plan in `draft` status with a UUID `plan_id`.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `name` | `str` | Human-readable plan name. |
| `goal` | `str` | The objective this plan achieves. |

**Returns:** `Plan` — New plan with no steps and `status="draft"`.

#### `add_step`

```python
def add_step(
    self,
    plan: Plan,
    action: str,
    dependencies: list[str],
    duration: float,
    priority: int = 5,
) -> PlanStep
```

Create a `PlanStep` with a UUID `step_id`, append it to `plan.steps`, and return it.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `plan` | `Plan` | Required | The plan to extend. Mutated in place. |
| `action` | `str` | Required | Description of the action. |
| `dependencies` | `list[str]` | Required | `step_id` values this step depends on. |
| `duration` | `float` | Required | Estimated duration in seconds. |
| `priority` | `int` | `5` | Priority `1`–`10` (1 = highest). |

**Returns:** `PlanStep` — The newly created and appended step.

#### `validate`

```python
def validate(self, plan: Plan) -> PlanValidation
```

Validate a plan for structural correctness.

**Checks performed:**
1. Duplicate `step_id` values
2. Dependency references to non-existent step IDs
3. Circular dependencies (via `topological_sort`)

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `plan` | `Plan` | The plan to validate. |

**Returns:** `PlanValidation` — `valid=True` with duration estimate if all checks pass; `valid=False` with `issues` list otherwise.

**Note:** If circular dependency or missing dependency issues are found, `estimated_total_duration` falls back to the sum of all step durations (sequential).

#### `topological_sort`

```python
def topological_sort(self, plan: Plan) -> list[PlanStep]
```

Sort plan steps in dependency order using Kahn's algorithm.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `plan` | `Plan` | The plan to sort. |

**Returns:** `list[PlanStep]` — Steps ordered so each step appears after all its dependencies.

**Raises:**

| Exception | Condition |
|-----------|-----------|
| `CircularDependencyError` | The dependency graph contains a cycle. |

#### `save`

```python
def save(self, plan: Plan, path: str) -> None
```

Persist a plan to a YAML file. Creates parent directories if needed.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `plan` | `Plan` | The plan to serialize. |
| `path` | `str` | Output file path (`.yaml` recommended). |

**Raises:** `ImportError` if PyYAML is not installed.

#### `load`

```python
def load(self, path: str) -> Plan
```

Load and deserialize a plan from a YAML file.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `path` | `str` | Input file path. |

**Returns:** `Plan` — Validated Pydantic model instance.

**Raises:** `FileNotFoundError`, `pydantic.ValidationError`, `ImportError` (if PyYAML missing).

---

### `PlanExecutor`

```python
class PlanExecutor
```

Execute a plan by running steps in dependency order.

#### `__init__`

```python
def __init__(self, builder: PlanBuilder | None = None) -> None
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `builder` | `PlanBuilder \| None` | New `PlanBuilder()` | Used for topological sort. |

#### `execute`

```python
def execute(self, plan: Plan) -> dict[str, object]
```

Execute all plan steps in dependency order.

Steps are executed sequentially. A step is set to `"skipped"` (not executed) if any of its direct dependencies have `"failed"` status. In the current implementation, all eligible steps are simulated as immediately completing; this method is the integration point for real handler dispatch.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `plan` | `Plan` | The plan to execute. Mutates `step.status` and `plan.status` in place. |

**Returns:** `dict` with keys:

| Key | Type | Description |
|-----|------|-------------|
| `plan_id` | `str` | ID of the executed plan. |
| `status` | `str` | `"completed"` if all steps completed, `"failed"` if any were skipped or failed, `"failed"` if circular dependency detected. |
| `steps_completed` | `int` | Number of steps with `completed` status. |
| `steps_failed` | `int` | Number of steps with `failed` status. |
| `total_duration_seconds` | `float` | Wall-clock execution time. |
| `steps` | `list[dict]` | Per-step log with `step_id`, `action`, `status`, `duration_seconds`. |
| `error` | `str` | Present only if `CircularDependencyError` was caught. |

#### `get_ready_steps`

```python
def get_ready_steps(self, plan: Plan) -> list[PlanStep]
```

Return steps whose dependencies are all completed and whose own status is `"pending"`.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `plan` | `Plan` | The plan to inspect. |

**Returns:** `list[PlanStep]` — Steps that are currently eligible to execute.

**Use case:** Incremental execution — poll this method after marking each step complete to determine what to dispatch next.

---

### `PlanOptimizer`

```python
class PlanOptimizer
```

Analyze and optimize plan execution strategies.

#### `__init__`

```python
def __init__(self, builder: PlanBuilder | None = None) -> None
```

#### `parallelize`

```python
def parallelize(self, plan: Plan) -> list[list[PlanStep]]
```

Group steps into parallel execution waves.

Each wave contains steps whose dependencies are all satisfied by previous waves. Steps within a wave can execute concurrently. Within each wave, steps are sorted by `priority` ascending (priority 1 runs before priority 10).

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `plan` | `Plan` | The plan to parallelize. |

**Returns:** `list[list[PlanStep]]` — List of waves. Empty list if plan has no steps.

**Raises:** `CircularDependencyError` if the plan's dependency graph has cycles.

**Algorithm:** After topological sort, each step is assigned wave `max(wave_of_each_dependency) + 1`. Steps with no dependencies go to wave 0.

**Example:**

```python
from aumai_planforge.core import PlanOptimizer

optimizer = PlanOptimizer()
waves = optimizer.parallelize(plan)

for i, wave in enumerate(waves):
    print(f"Wave {i+1}: {[s.action for s in wave]}")
```

---

### `DependencyResolver`

```python
class DependencyResolver
```

Resolve step dependencies, detect cycles, and find the critical path. Operates on a list of `PlanStep` objects directly rather than a `Plan`.

#### `__init__`

```python
def __init__(self, steps: list[PlanStep]) -> None
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `steps` | `list[PlanStep]` | The steps to analyze. Keyed internally by `step_id`. |

#### `topological_sort`

```python
def topological_sort(self) -> list[PlanStep]
```

Return steps in dependency order using Kahn's algorithm.

**Returns:** `list[PlanStep]` — Ordered steps.

**Raises:** `CircularDependencyError` if cycles exist.

#### `detect_cycles`

```python
def detect_cycles(self) -> list[list[str]]
```

Return all cycles in the dependency graph, each as a list of `step_id` strings. Returns an empty list if the graph is acyclic.

**Returns:** `list[list[str]]` — Each inner list is a cycle path (includes the repeated start node at the end).

**Note:** Uses DFS with a recursion stack to detect back edges. Does not raise on cycles — use this when you want to inspect cycle membership rather than raise.

#### `critical_path`

```python
def critical_path(self) -> list[str]
```

Compute the critical path (longest-duration path) through the dependency DAG.

**Returns:** `list[str]` — Ordered list of `step_id` values on the critical path, from start to end. Empty list if no steps.

**Raises:** `CircularDependencyError` if cycles exist.

**Algorithm:** Forward pass computes earliest start time for each step as `max(earliest_start[dep] + dep.estimated_duration_seconds)` over all dependencies. The step with the largest `earliest_start + duration` is the end of the critical path. The path is reconstructed backwards via a predecessor map.

#### `total_duration_seconds`

```python
def total_duration_seconds(self) -> float
```

Return the sum of `estimated_duration_seconds` for all steps on the critical path.

**Returns:** `float` — Critical-path duration. Returns `0.0` if a `CircularDependencyError` is caught internally.

---

### `PlanGenerator`

```python
class PlanGenerator
```

Generate plans from `Goal` objects using HTN-style hierarchical decomposition.

#### `generate`

```python
def generate(
    self,
    goals: list[Goal],
    plan_name: str | None = None,
) -> Plan
```

Generate a plan that addresses all provided goals.

Goals are processed in descending `priority` order. Each goal is decomposed into three steps (gather / act / verify). Each goal's gather step depends on the previous goal's verify step.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `goals` | `list[Goal]` | Required | List of `Goal` objects to achieve. Must be non-empty. |
| `plan_name` | `str \| None` | `None` | Optional plan name. Defaults to `"Plan for {first_goal_description[:40]}"`. |

**Returns:** `Plan` — With `status="draft"`, populated `steps`, `goals`, `estimated_cost`, and `estimated_duration_seconds`.

**Raises:** `ValueError` if `goals` is empty.

**Step naming pattern per goal:**

| Step ID | Action | Duration | Dependencies |
|---------|--------|----------|--------------|
| `g{i}_gather` | `"Gather information for: {goal.description}"` | 30 s | Previous goal's verify step (or none for first goal) |
| `g{i}_act` | `"Execute action to achieve: {goal.description}"` | 60 s | `g{i}_gather` |
| `g{i}_verify` | `"Verify outcome of: {goal.description}"` | 15 s | `g{i}_act` |

**Cost estimate:** `sum(step.estimated_duration_seconds * 0.01)` across all steps.

**Example:**

```python
from aumai_planforge.core import PlanGenerator
from aumai_planforge.models import Goal

gen = PlanGenerator()
plan = gen.generate(
    goals=[
        Goal(goal_id="g1", description="Set up CI pipeline", priority=8),
        Goal(goal_id="g2", description="Configure deployment", priority=6),
    ],
    plan_name="DevOps Setup",
)
print(f"Steps: {len(plan.steps)}")              # 6
print(f"Duration: {plan.estimated_duration_seconds:.0f}s")   # 210
```

---

## Package-Level Exports

`aumai_planforge.__init__` exports only `__version__`. Import from submodules directly:

```python
from aumai_planforge.core import (
    PlanBuilder,
    PlanExecutor,
    PlanOptimizer,
    DependencyResolver,
    PlanGenerator,
    CircularDependencyError,
)

from aumai_planforge.models import (
    PlanStatus,
    Goal,
    PlanStep,
    Plan,
    ExecutionState,
    PlanValidation,
)
```

**Version:**

```python
import aumai_planforge
print(aumai_planforge.__version__)  # "0.1.0"
```
