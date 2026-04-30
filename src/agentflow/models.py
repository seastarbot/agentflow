"""Data models for AgentFlow."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class TaskStatus(Enum):
    """Status of a task in the system."""
    PENDING = "pending"
    AGENT_PLANNING = "agent_planning"
    WORKFLOW_RUNNING = "workflow_running"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class Severity(Enum):
    """Severity levels for audit entries."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class Task:
    """An industrial task to be processed by the hybrid system."""
    task_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    task_type: str = ""
    description: str = ""
    parameters: Dict[str, Any] = field(default_factory=dict)
    context: Dict[str, Any] = field(default_factory=dict)
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkflowPlan:
    """Agent-generated plan for workflow execution."""
    plan_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    task_id: str = ""
    workflow_id: str = ""
    parameters: Dict[str, Any] = field(default_factory=dict)
    steps: List[str] = field(default_factory=list)
    exception_handlers: Dict[str, str] = field(default_factory=dict)
    confidence: float = 0.0
    reasoning: str = ""


@dataclass
class WorkflowResult:
    """Result of workflow execution."""
    result_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    task_id: str = ""
    plan_id: str = ""
    status: TaskStatus = TaskStatus.COMPLETED
    output: Dict[str, Any] = field(default_factory=dict)
    steps_completed: List[str] = field(default_factory=list)
    steps_failed: List[str] = field(default_factory=list)
    duration_ms: float = 0.0
    error: Optional[str] = None


@dataclass
class AuditEntry:
    """Structured audit log entry."""
    entry_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    timestamp: datetime = field(default_factory=datetime.utcnow)
    task_id: str = ""
    component: str = ""  # "agent" or "workflow"
    action: str = ""
    severity: Severity = Severity.INFO
    input_data: Dict[str, Any] = field(default_factory=dict)
    output_data: Dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Rule:
    """A business rule for the rule engine."""
    rule_id: str = ""
    name: str = ""
    condition: str = ""  # Human-readable condition
    action: str = ""  # Action to take when condition is met
    severity: Severity = Severity.WARNING
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
