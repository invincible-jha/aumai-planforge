"""Pydantic v2 models for aumai-planforge.

Provides typed structures for goal-oriented planning, plan steps,
dependencies, dependency analysis, and execution state tracking.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "PlanStatus",
    "Goal",
    "PlanStep",
    "Plan",
    "ExecutionState",
    "PlanValidation",
]


class PlanStatus(str, Enum):
    """Lifecycle status of a plan."""

    DRAFT = "draft"
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"


class Goal(BaseModel):
    """A high-level objective to be achieved by a plan."""

    model_config = ConfigDict(str_strip_whitespace=True)

    goal_id: str = Field(description="Unique goal identifier.")
    description: str = Field(description="Natural language description of the goal.")
    priority: int = Field(
        default=5, ge=1, le=10,
        description="Priority from 1 (lowest) to 10 (highest).",
    )
    deadline: str | None = Field(default=None, description="Optional ISO-8601 deadline.")
    metadata: dict[str, object] = Field(default_factory=dict)


class PlanStep(BaseModel):
    """A single actionable step within a plan."""

    model_config = ConfigDict(str_strip_whitespace=True)

    step_id: str = Field(description="Unique step identifier.")
    action: str = Field(description="What this step does.")
    preconditions: list[str] = Field(
        default_factory=list,
        description="Conditions that must hold before executing this step.",
    )
    effects: list[str] = Field(
        default_factory=list,
        description="State changes produced by completing this step.",
    )
    dependencies: list[str] = Field(
        default_factory=list,
        description="step_ids that must complete before this step.",
    )
    estimated_duration_seconds: float = Field(
        default=60.0, ge=0.0,
        description="Estimated execution time in seconds.",
    )
    priority: int = Field(default=5, ge=1, le=10, description="1=highest, 10=lowest.")
    status: Literal["pending", "running", "completed", "failed", "skipped"] = "pending"
    metadata: dict[str, object] = Field(default_factory=dict)


class Plan(BaseModel):
    """A structured plan composed of steps with dependency links."""

    model_config = ConfigDict(str_strip_whitespace=True)

    plan_id: str = Field(description="Unique plan identifier.")
    name: str = Field(description="Human-readable plan name.")
    goal: str = Field(description="Primary goal description.")
    goals: list[Goal] = Field(default_factory=list, description="Structured goal objects.")
    steps: list[PlanStep] = Field(default_factory=list)
    status: Literal["draft", "validated", "active", "running", "completed", "failed"] = "draft"
    estimated_cost: float = Field(default=0.0, ge=0.0)
    estimated_duration_seconds: float = Field(default=0.0, ge=0.0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))
    metadata: dict[str, object] = Field(default_factory=dict)


class ExecutionState(BaseModel):
    """Tracks the runtime state of plan execution."""

    plan_id: str
    current_step_id: str | None = None
    completed_steps: list[str] = Field(default_factory=list)
    blocked_steps: list[str] = Field(default_factory=list)
    failed_steps: list[str] = Field(default_factory=list)
    status: PlanStatus = Field(default=PlanStatus.ACTIVE)
    execution_log: list[dict[str, object]] = Field(default_factory=list)


class PlanValidation(BaseModel):
    """Result of validating a plan's structure."""

    plan: Plan
    valid: bool
    issues: list[str] = Field(default_factory=list)
    estimated_total_duration: float = Field(
        ge=0.0, default=0.0,
        description="Estimated critical-path duration in seconds.",
    )
