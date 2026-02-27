# Getting Started with aumai-planforge

This guide walks you from installation to creating, validating, optimizing, and executing your first agent plan — in under fifteen minutes.

---

## Prerequisites

- **Python 3.11 or higher**
- **pip** 22+ recommended
- **PyYAML** for plan persistence (save/load to YAML files)

---

## Installation

### From PyPI

```bash
pip install aumai-planforge
```

### With YAML support (recommended)

```bash
pip install "aumai-planforge[yaml]"
```

### Development install

```bash
git clone https://github.com/aumai/aumai-planforge
cd aumai-planforge
pip install -e ".[dev]"
```

### Verify installation

```bash
aumai-planforge --version
python -c "from aumai_planforge.core import PlanBuilder; print('OK')"
```

---

## Step-by-Step Tutorial

### Step 1: Create a plan

The simplest entry point is `PlanBuilder.create`, which produces an empty `Plan` in `draft` status.

```python
from aumai_planforge.core import PlanBuilder

builder = PlanBuilder()
plan = builder.create(
    name="Release v3.0",
    goal="Ship version 3.0 of the product to production with zero downtime",
)

print(f"Plan ID: {plan.plan_id}")
print(f"Status: {plan.status}")
print(f"Steps: {len(plan.steps)}")  # 0 — empty plan
```

### Step 2: Add steps with dependencies

`add_step` creates a `PlanStep` and appends it to the plan. Pass `dependencies` as a list of `step_id` strings from previously created steps.

```python
# No dependencies — can start immediately
prep = builder.add_step(
    plan,
    action="Freeze feature branch and run full test suite",
    dependencies=[],
    duration=300.0,   # seconds
    priority=1,
)

# Depends on prep
build = builder.add_step(
    plan,
    action="Build and sign release artifact",
    dependencies=[prep.step_id],
    duration=180.0,
    priority=1,
)

# Also depends on prep — can run in parallel with build
notify = builder.add_step(
    plan,
    action="Notify stakeholders of upcoming release window",
    dependencies=[prep.step_id],
    duration=30.0,
    priority=3,
)

# Depends on both build and notify
deploy = builder.add_step(
    plan,
    action="Deploy to production via blue-green switch",
    dependencies=[build.step_id, notify.step_id],
    duration=120.0,
    priority=1,
)

# Final verification
verify = builder.add_step(
    plan,
    action="Run smoke tests and verify SLO metrics",
    dependencies=[deploy.step_id],
    duration=60.0,
    priority=1,
)
```

### Step 3: Validate the plan

Always validate before executing. Validation catches missing dependencies, duplicate IDs, and circular dependencies.

```python
result = builder.validate(plan)

if result.valid:
    print(f"Plan is valid.")
    print(f"  Steps:              {len(plan.steps)}")
    print(f"  Estimated duration: {result.estimated_total_duration:.0f}s")
else:
    print("Validation failed:")
    for issue in result.issues:
        print(f"  - {issue}")
```

### Step 4: Analyze parallel execution waves

```python
from aumai_planforge.core import PlanOptimizer

optimizer = PlanOptimizer()
waves = optimizer.parallelize(plan)

print(f"Parallel waves: {len(waves)}")
for i, wave in enumerate(waves):
    step_names = [s.action[:40] for s in wave]
    print(f"  Wave {i + 1}: {step_names}")
```

Expected output:

```
Parallel waves: 4
  Wave 1: ['Freeze feature branch and run full test suite']
  Wave 2: ['Build and sign release artifact', 'Notify stakeholders...']
  Wave 3: ['Deploy to production via blue-green switch']
  Wave 4: ['Run smoke tests and verify SLO metrics']
```

### Step 5: Find the critical path

```python
from aumai_planforge.core import DependencyResolver

resolver = DependencyResolver(plan.steps)
path = resolver.critical_path()
duration = resolver.total_duration_seconds()

print(f"Critical path: {len(path)} steps")
step_map = {s.step_id: s for s in plan.steps}
for step_id in path:
    s = step_map[step_id]
    print(f"  {s.action[:50]} ({s.estimated_duration_seconds:.0f}s)")
print(f"Minimum possible duration: {duration:.0f}s")
```

### Step 6: Save and reload the plan

```python
builder.save(plan, "release_v3.yaml")
print("Plan saved.")

# Later — or in a different process
loaded = builder.load("release_v3.yaml")
print(f"Reloaded plan: {loaded.name} ({len(loaded.steps)} steps)")
```

### Step 7: Execute the plan

```python
from aumai_planforge.core import PlanExecutor

executor = PlanExecutor(builder=builder)
summary = executor.execute(loaded)

print(f"Status:          {summary['status']}")
print(f"Steps completed: {summary['steps_completed']}")
print(f"Duration:        {summary['total_duration_seconds']:.3f}s")
```

---

## Common Patterns

### Pattern 1: Generate a plan from goals automatically

Use `PlanGenerator` when you have structured `Goal` objects and want the framework to decompose them into steps automatically using the gather / act / verify pattern.

```python
from aumai_planforge.core import PlanGenerator
from aumai_planforge.models import Goal

generator = PlanGenerator()

goals = [
    Goal(goal_id="g1", description="Provision Kubernetes cluster", priority=9),
    Goal(goal_id="g2", description="Deploy application workloads", priority=8),
    Goal(goal_id="g3", description="Configure monitoring and alerting", priority=7),
]

plan = generator.generate(goals, plan_name="Infrastructure Bootstrap")
print(f"Generated {len(plan.steps)} steps")  # 9 — 3 per goal
print(f"Estimated duration: {plan.estimated_duration_seconds:.0f}s")
```

Each goal produces three steps in sequence: `Gather information for: ...` (30 s), `Execute action to achieve: ...` (60 s), `Verify outcome of: ...` (15 s). Goals are chained in descending priority order.

### Pattern 2: Incremental execution with ready-step polling

Instead of running the full plan at once, poll `get_ready_steps` to implement a real dispatcher that marks steps complete as work finishes:

```python
from aumai_planforge.core import PlanExecutor, PlanBuilder

builder = PlanBuilder()
executor = PlanExecutor(builder=builder)
plan = builder.load("release_v3.yaml")

while True:
    ready = executor.get_ready_steps(plan)
    if not ready:
        break  # all done or blocked

    for step in ready:
        print(f"Dispatching: {step.action}")
        # ... dispatch to real handler ...
        step.status = "completed"   # mark complete after handler returns
```

### Pattern 3: Validate then save in one flow

```python
from aumai_planforge.core import PlanBuilder

builder = PlanBuilder()
plan = builder.create("Data Sync", "Sync 50M records to data warehouse")

a = builder.add_step(plan, "Export source tables", [], 600.0, 1)
b = builder.add_step(plan, "Validate export checksum", [a.step_id], 30.0, 1)
c = builder.add_step(plan, "Load into warehouse", [b.step_id], 900.0, 2)
d = builder.add_step(plan, "Run reconciliation report", [c.step_id], 120.0, 2)

validation = builder.validate(plan)
if validation.valid:
    builder.save(plan, "data_sync.yaml")
    print(f"Saved. Estimated duration: {validation.estimated_total_duration:.0f}s")
else:
    for issue in validation.issues:
        print(f"ERROR: {issue}")
```

### Pattern 4: Detect and report circular dependencies

```python
from aumai_planforge.core import DependencyResolver
from aumai_planforge.models import PlanStep

steps = [
    PlanStep(step_id="a", action="Step A", dependencies=["b"]),
    PlanStep(step_id="b", action="Step B", dependencies=["c"]),
    PlanStep(step_id="c", action="Step C", dependencies=["a"]),  # cycle!
]

resolver = DependencyResolver(steps)
cycles = resolver.detect_cycles()

if cycles:
    print(f"Found {len(cycles)} cycle(s):")
    for cycle in cycles:
        print(f"  {' -> '.join(cycle)}")
```

### Pattern 5: Use the CLI in a CI/CD pipeline

```bash
#!/bin/bash
set -e

# Create plan from YAML template (pre-authored)
aumai-planforge validate --plan release.yaml || exit 1

# Show optimization before running
aumai-planforge optimize --plan release.yaml

# Execute
aumai-planforge run --plan release.yaml
```

---

## Troubleshooting FAQ

**Q: `PlanBuilder.save` fails with `ModuleNotFoundError: No module named 'yaml'`.**

Install PyYAML:

```bash
pip install pyyaml
# or
pip install "aumai-planforge[yaml]"
```

**Q: `validate` reports "Duplicate step_ids detected" but I used `add_step` to create all steps.**

`add_step` uses `uuid.uuid4()` to generate step IDs, so duplicates cannot occur through `add_step`. This error appears when you manually construct `PlanStep` objects with hardcoded `step_id` values that collide, or when you loaded a plan file that was manually edited with duplicate IDs.

**Q: `topological_sort` raises `CircularDependencyError`. How do I find the cycle?**

Use `DependencyResolver.detect_cycles()` instead — it returns the actual cycle paths without raising:

```python
resolver = DependencyResolver(plan.steps)
cycles = resolver.detect_cycles()
print(cycles)
```

**Q: `PlanExecutor.execute` returns `status: "completed"` but some steps were skipped.**

A step is skipped (not failed) when a dependency of that step failed. In the simulation mode, all steps succeed by default, so skipping only happens when `step.status = "failed"` is set externally before calling `execute`. In production, if your real handler marks a step as failed, all downstream steps will be skipped.

**Q: `PlanOptimizer.parallelize` puts every step in its own wave even though some could run together.**

This happens when every step depends on the previous one (a pure sequential chain). Check your dependency graph — steps that have no dependency on each other should have independent (or shared upstream) dependencies, not chained ones.

**Q: `PlanGenerator` always generates exactly 3 steps per goal. Can I customize it?**

The current `PlanGenerator._decompose_goal` uses a fixed gather/act/verify pattern. To customize decomposition, subclass `PlanGenerator` and override `_decompose_goal`, or build your steps manually with `PlanBuilder.add_step`.

**Q: `critical_path` returns a single-step path even for a complex plan.**

This is correct when one step dominates all others by duration. The critical path is the longest-duration path through the DAG, not the longest by step count. If you have one 3600-second step and ten 10-second steps, the single long step is the critical path.

---

## Next Steps

- Read the [API Reference](api-reference.md) for complete class and method documentation
- Explore the [quickstart example](../examples/quickstart.py)
- See the [README](../README.md) for architecture diagrams and integration guidance
- Join the [AumAI Discord](https://discord.gg/aumai)
