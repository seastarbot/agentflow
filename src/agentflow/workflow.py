"""WorkflowEngine: Deterministic workflow execution with state management and compliance."""

from __future__ import annotations

import logging
import time
from typing import Any, Callable, Dict, List, Optional

from .audit import AuditLogger
from .models import Task, TaskStatus, WorkflowPlan, WorkflowResult, Severity
from .rules import RuleEngine

logger = logging.getLogger(__name__)


class WorkflowStep:
    """A single step in a workflow definition."""

    def __init__(
        self,
        name: str,
        handler: Callable[[Dict[str, Any]], Dict[str, Any]],
        compensation: Optional[Callable[[Dict[str, Any]], None]] = None,
        required: bool = True,
    ):
        self.name = name
        self.handler = handler
        self.compensation = compensation
        self.required = required


class WorkflowDefinition:
    """A deterministic workflow definition with ordered steps."""

    def __init__(
        self,
        workflow_id: str,
        name: str,
        steps: Optional[List[WorkflowStep]] = None,
    ):
        self.workflow_id = workflow_id
        self.name = name
        self.steps: List[WorkflowStep] = steps or []

    def add_step(self, step: WorkflowStep) -> None:
        self.steps.append(step)

    def get_step(self, name: str) -> Optional[WorkflowStep]:
        for step in self.steps:
            if step.name == name:
                return step
        return None


class WorkflowEngine:
    """
    Deterministic workflow execution engine.

    Handles state management, business rule enforcement, compensation/rollback,
    and compliance logging. The engine is fully deterministic — given the same
    inputs and workflow definition, it produces identical execution traces.
    """

    def __init__(
        self,
        audit_logger: Optional[AuditLogger] = None,
        rule_engine: Optional[RuleEngine] = None,
    ):
        self.audit_logger = audit_logger or AuditLogger()
        self.rule_engine = rule_engine or RuleEngine()
        self._workflows: Dict[str, WorkflowDefinition] = {}
        self._state_store: Dict[str, Dict[str, Any]] = {}

    def register_workflow(self, workflow: WorkflowDefinition) -> None:
        """Register a workflow definition."""
        self._workflows[workflow.workflow_id] = workflow
        logger.info(f"Registered workflow: {workflow.workflow_id}")

    def execute(
        self,
        workflow_id: str,
        parameters: Dict[str, Any],
        task_id: str = "",
        audit_context: Optional[Dict[str, Any]] = None,
    ) -> WorkflowResult:
        """
        Execute a workflow deterministically.

        Returns a WorkflowResult with status, outputs, and execution trace.
        All steps are logged for audit purposes.
        """
        start = time.time()
        workflow = self._workflows.get(workflow_id)
        if not workflow:
            return WorkflowResult(
                task_id=task_id,
                status=TaskStatus.FAILED,
                error=f"Workflow not found: {workflow_id}",
            )

        state = {
            "task_id": task_id,
            "parameters": parameters,
            "audit_context": audit_context or {},
        }
        self._state_store[task_id] = state

        completed_steps: List[str] = []
        failed_steps: List[str] = []
        outputs: Dict[str, Any] = {}

        for step in workflow.steps:
            step_start = time.time()
            try:
                # Check business rules before execution
                rule_violations = self.rule_engine.evaluate(step.name, state)
                if rule_violations:
                    for violation in rule_violations:
                        self.audit_logger.log(
                            task_id=task_id,
                            component="workflow",
                            action=f"rule_violation:{step.name}",
                            input_data={"rule": violation.rule_id},
                            output_data={"severity": violation.severity.value},
                            severity=Severity.ERROR,
                        )
                        if violation.severity == Severity.CRITICAL:
                            # Rollback completed steps
                            self._rollback(workflow, completed_steps, state, task_id)
                            return WorkflowResult(
                                task_id=task_id,
                                status=TaskStatus.ROLLED_BACK,
                                output=outputs,
                                steps_completed=completed_steps,
                                steps_failed=[step.name],
                                duration_ms=(time.time() - start) * 1000,
                                error=f"Rule violation: {violation.name}",
                            )

                # Execute step
                result = step.handler(state)
                state.update(result)
                outputs[step.name] = result
                completed_steps.append(step.name)

                step_duration = (time.time() - step_start) * 1000
                self.audit_logger.log(
                    task_id=task_id,
                    component="workflow",
                    action=f"execute_step:{step.name}",
                    input_data=state,
                    output_data=result,
                    duration_ms=step_duration,
                )

            except Exception as e:
                failed_steps.append(step.name)
                step_duration = (time.time() - step_start) * 1000
                self.audit_logger.log(
                    task_id=task_id,
                    component="workflow",
                    action=f"step_failed:{step.name}",
                    input_data={"error": str(e)},
                    output_data={},
                    severity=Severity.ERROR,
                    duration_ms=step_duration,
                )

                if step.required:
                    # Rollback on required step failure
                    self._rollback(workflow, completed_steps, state, task_id)
                    return WorkflowResult(
                        task_id=task_id,
                        status=TaskStatus.FAILED,
                        output=outputs,
                        steps_completed=completed_steps,
                        steps_failed=failed_steps,
                        duration_ms=(time.time() - start) * 1000,
                        error=str(e),
                    )

        duration_ms = (time.time() - start) * 1000
        self.audit_logger.log(
            task_id=task_id,
            component="workflow",
            action="workflow_complete",
            input_data={"workflow_id": workflow_id},
            output_data={"steps_completed": len(completed_steps)},
            duration_ms=duration_ms,
        )

        return WorkflowResult(
            task_id=task_id,
            plan_id="",
            status=TaskStatus.COMPLETED,
            output=outputs,
            steps_completed=completed_steps,
            steps_failed=failed_steps,
            duration_ms=duration_ms,
        )

    def _rollback(
        self,
        workflow: WorkflowDefinition,
        completed_steps: List[str],
        state: Dict[str, Any],
        task_id: str,
    ) -> None:
        """Execute compensation actions in reverse order."""
        for step_name in reversed(completed_steps):
            step = workflow.get_step(step_name)
            if step and step.compensation:
                try:
                    step.compensation(state)
                    self.audit_logger.log(
                        task_id=task_id,
                        component="workflow",
                        action=f"compensate:{step_name}",
                        input_data=state,
                        output_data={"status": "compensated"},
                    )
                except Exception as e:
                    logger.error(f"Compensation failed for {step_name}: {e}")
                    self.audit_logger.log(
                        task_id=task_id,
                        component="workflow",
                        action=f"compensation_failed:{step_name}",
                        input_data={"error": str(e)},
                        output_data={},
                        severity=Severity.CRITICAL,
                    )

    def get_state(self, task_id: str) -> Dict[str, Any]:
        """Get current state for a task."""
        return self._state_store.get(task_id, {})
