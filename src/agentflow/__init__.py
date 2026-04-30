"""
AgentFlow: Hybrid Agent-Workflow Execution Framework for Industrial AI.

A framework that combines LLM agent reasoning with deterministic workflow
execution for reliable, auditable, and compliant AI systems.
"""

__version__ = "0.1.0"
__author__ = "Sun Wei"

from .agent import AgentLayer
from .workflow import WorkflowEngine
from .orchestrator import HybridOrchestrator
from .audit import AuditLogger
from .rules import RuleEngine
from .models import Task, WorkflowPlan, AuditEntry, WorkflowResult

__all__ = [
    "AgentLayer",
    "WorkflowEngine",
    "HybridOrchestrator",
    "AuditLogger",
    "RuleEngine",
    "Task",
    "WorkflowPlan",
    "AuditEntry",
    "WorkflowResult",
]
