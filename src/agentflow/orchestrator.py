"""HybridOrchestrator: Agent + Workflow orchestration layer."""

from __future__ import annotations

import logging
import time
from typing import Any, Callable, Dict, List, Optional

from .agent import AgentLayer
from .audit import AuditLogger
from .models import Task, TaskStatus, WorkflowPlan, WorkflowResult, Severity
from .workflow import WorkflowEngine

logger = logging.getLogger(__name__)


class HybridOrchestrator:
    """
    Orchestrates the hybrid agent-workflow execution model.

    The orchestrator implements the hybrid function:
        f(t) = f_W(f_A(t), C)

    where:
        f_A: Agent cognitive function (intent resolution + planning)
        f_W: Workflow execution function (deterministic execution)
        C: Audit context and compliance logs

    This is the main entry point for the AgentFlow framework.
    """

    def __init__(
        self,
        agent: AgentLayer,
        workflow_engine: WorkflowEngine,
        audit_logger: Optional[AuditLogger] = None,
        max_exception_retries: int = 2,
    ):
        self.agent = agent
        self.workflow_engine = workflow_engine
        self.audit_logger = audit_logger or AuditLogger()
        self.max_exception_retries = max_exception_retries
        self._execution_count = 0
        self._success_count = 0

    def execute(self, task: Task) -> WorkflowResult:
        """
        Execute a task through the hybrid pipeline:
        1. Agent resolves intent
        2. Agent generates workflow plan
        3. Workflow executes deterministically
        4. Agent interprets results

        Returns WorkflowResult with full audit trail.
        """
        start = time.time()
        self._execution_count += 1

        self.audit_logger.log(
            task_id=task.task_id,
            component="orchestrator",
            action="task_received",
            input_data={"task_type": task.task_type, "description": task.description},
        )

        try:
            # Phase 1: Agent resolves intent
            task.status = TaskStatus.AGENT_PLANNING
            intent = self.agent.resolve_intent(task)

            # Phase 2: Agent generates plan
            plan = self.agent.generate_plan(task, intent)

            # Phase 3: Execute workflow with exception handling
            result = self._execute_with_recovery(task, plan)

            # Phase 4: Interpret results
            interpretation = self.agent.interpret_result(task, result.output)

            duration_ms = (time.time() - start) * 1000
            self.audit_logger.log(
                task_id=task.task_id,
                component="orchestrator",
                action="task_completed",
                output_data={
                    "status": result.status.value,
                    "duration_ms": duration_ms,
                    "interpretation_length": len(interpretation),
                },
                duration_ms=duration_ms,
            )

            if result.status == TaskStatus.COMPLETED:
                self._success_count += 1

            return result

        except Exception as e:
            duration_ms = (time.time() - start) * 1000
            task.status = TaskStatus.FAILED
            self.audit_logger.log(
                task_id=task.task_id,
                component="orchestrator",
                action="task_failed",
                input_data={"error": str(e)},
                severity=Severity.CRITICAL,
                duration_ms=duration_ms,
            )
            return WorkflowResult(
                task_id=task.task_id,
                status=TaskStatus.FAILED,
                error=str(e),
                duration_ms=duration_ms,
            )

    def _execute_with_recovery(
        self, task: Task, plan: WorkflowPlan, retries: int = 0
    ) -> WorkflowResult:
        """Execute workflow with agent-driven exception recovery."""
        task.status = TaskStatus.WORKFLOW_RUNNING

        self.audit_logger.log(
            task_id=task.task_id,
            component="orchestrator",
            action="workflow_start",
            input_data={"workflow_id": plan.workflow_id, "confidence": plan.confidence},
        )

        result = self.workflow_engine.execute(
            workflow_id=plan.workflow_id,
            parameters=plan.parameters,
            task_id=task.task_id,
            audit_context={
                "plan_id": plan.plan_id,
                "agent_reasoning": plan.reasoning,
            },
        )

        # Handle failures with agent recovery
        if result.status == TaskStatus.FAILED and retries < self.max_exception_retries:
            self.audit_logger.log(
                task_id=task.task_id,
                component="orchestrator",
                action="exception_recovery",
                input_data={
                    "error": result.error,
                    "retry": retries + 1,
                    "max_retries": self.max_exception_retries,
                },
                severity=Severity.WARNING,
            )

            # Ask agent to handle the exception
            recovery_plan = self.agent.handle_exception(
                task=task,
                plan=plan,
                error=Exception(result.error or "Unknown error"),
                workflow_state=self.workflow_engine.get_state(task.task_id),
            )

            return self._execute_with_recovery(task, recovery_plan, retries + 1)

        return result

    def get_stats(self) -> Dict[str, Any]:
        """Get execution statistics."""
        return {
            "total_executions": self._execution_count,
            "successful_executions": self._success_count,
            "success_rate": (
                self._success_count / self._execution_count
                if self._execution_count > 0
                else 0.0
            ),
        }
