"""AgentLayer: LLM agent cognitive interface for intent resolution, planning, and exception handling."""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Callable, Dict, List, Optional

from .audit import AuditLogger
from .models import Task, TaskStatus, WorkflowPlan, Severity

logger = logging.getLogger(__name__)


class AgentLayer:
    """
    Cognitive layer that handles intent resolution, plan generation,
    and exception handling using LLM capabilities.

    The AgentLayer is designed to be deterministic in its interface
    (always produces a WorkflowPlan) while allowing stochastic reasoning
    internally. This bounded non-determinism is key to the hybrid architecture.
    """

    def __init__(
        self,
        llm_fn: Optional[Callable] = None,
        audit_logger: Optional[AuditLogger] = None,
        available_workflows: Optional[List[str]] = None,
        max_retries: int = 3,
    ):
        self.llm_fn = llm_fn or self._default_llm
        self.audit_logger = audit_logger or AuditLogger()
        self.available_workflows = available_workflows or []
        self.max_retries = max_retries
        self._plan_history: List[WorkflowPlan] = []

    def _default_llm(self, prompt: str, **kwargs) -> str:
        """Default LLM function (stub). Replace with actual LLM call."""
        return json.dumps({
            "workflow_id": self.available_workflows[0] if self.available_workflows else "default",
            "parameters": kwargs.get("parameters", {}),
            "steps": ["validate", "execute", "audit"],
            "reasoning": "Default plan generation",
            "confidence": 0.9,
        })

    def resolve_intent(self, task: Task) -> Dict[str, Any]:
        """
        Parse and resolve the intent from a task description.
        Extracts structured parameters from unstructured input.
        """
        start = time.time()
        prompt = self._build_intent_prompt(task)

        try:
            raw_response = self.llm_fn(prompt, task=task)
            intent = json.loads(raw_response) if isinstance(raw_response, str) else raw_response
        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"Intent resolution failed: {e}")
            intent = {
                "task_type": task.task_type,
                "parameters": task.parameters,
                "confidence": 0.0,
                "error": str(e),
            }

        duration_ms = (time.time() - start) * 1000
        self.audit_logger.log(
            task_id=task.task_id,
            component="agent",
            action="resolve_intent",
            input_data={"description": task.description},
            output_data=intent,
            duration_ms=duration_ms,
        )
        return intent

    def generate_plan(self, task: Task, intent: Dict[str, Any]) -> WorkflowPlan:
        """
        Generate a workflow execution plan from resolved intent.
        Selects the appropriate workflow and defines execution parameters.
        """
        start = time.time()
        prompt = self._build_plan_prompt(task, intent)

        try:
            raw_response = self.llm_fn(prompt, intent=intent)
            plan_data = json.loads(raw_response) if isinstance(raw_response, str) else raw_response
        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"Plan generation failed: {e}")
            plan_data = {
                "workflow_id": "default",
                "parameters": task.parameters,
                "steps": ["execute"],
                "reasoning": f"Fallback plan: {e}",
                "confidence": 0.5,
            }

        plan = WorkflowPlan(
            task_id=task.task_id,
            workflow_id=plan_data.get("workflow_id", "default"),
            parameters=plan_data.get("parameters", task.parameters),
            steps=plan_data.get("steps", ["execute"]),
            exception_handlers=plan_data.get("exception_handlers", {}),
            confidence=plan_data.get("confidence", 0.5),
            reasoning=plan_data.get("reasoning", ""),
        )

        self._plan_history.append(plan)
        duration_ms = (time.time() - start) * 1000

        self.audit_logger.log(
            task_id=task.task_id,
            component="agent",
            action="generate_plan",
            input_data={"intent": intent},
            output_data={"workflow_id": plan.workflow_id, "confidence": plan.confidence},
            duration_ms=duration_ms,
        )

        return plan

    def handle_exception(
        self,
        task: Task,
        plan: WorkflowPlan,
        error: Exception,
        workflow_state: Dict[str, Any],
    ) -> WorkflowPlan:
        """
        Handle workflow exceptions by generating a recovery plan.
        Can retry, escalate, modify parameters, or switch workflows.
        """
        start = time.time()
        prompt = self._build_exception_prompt(task, plan, error, workflow_state)

        try:
            raw_response = self.llm_fn(prompt, error=str(error))
            recovery = json.loads(raw_response) if isinstance(raw_response, str) else raw_response
        except Exception as e:
            logger.error(f"Exception handling failed: {e}")
            recovery = {
                "action": "escalate",
                "reasoning": f"Unable to handle exception: {e}",
            }

        # Build recovery plan
        recovery_plan = WorkflowPlan(
            task_id=task.task_id,
            workflow_id=recovery.get("workflow_id", plan.workflow_id),
            parameters=recovery.get("parameters", plan.parameters),
            steps=recovery.get("steps", plan.steps),
            exception_handlers=recovery.get("exception_handlers", {}),
            confidence=recovery.get("confidence", 0.3),
            reasoning=recovery.get("reasoning", ""),
        )

        duration_ms = (time.time() - start) * 1000
        self.audit_logger.log(
            task_id=task.task_id,
            component="agent",
            action="handle_exception",
            input_data={"error": str(error), "workflow_state": workflow_state},
            output_data={"action": recovery.get("action", "retry")},
            severity=Severity.WARNING,
            duration_ms=duration_ms,
        )

        return recovery_plan

    def interpret_result(
        self,
        task: Task,
        result: Dict[str, Any],
        user_context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Interpret workflow results and generate a human-readable response.
        """
        start = time.time()
        prompt = self._build_interpret_prompt(task, result, user_context)

        try:
            response = self.llm_fn(prompt, result=result)
        except Exception as e:
            response = f"Workflow completed with result: {result}"

        duration_ms = (time.time() - start) * 1000
        self.audit_logger.log(
            task_id=task.task_id,
            component="agent",
            action="interpret_result",
            input_data={"result": result},
            output_data={"response_length": len(str(response))},
            duration_ms=duration_ms,
        )

        return response

    def _build_intent_prompt(self, task: Task) -> str:
        return (
            f"Resolve intent for task:\n"
            f"Type: {task.task_type}\n"
            f"Description: {task.description}\n"
            f"Parameters: {json.dumps(task.parameters)}\n"
            f"Context: {json.dumps(task.context)}\n"
            f"\nReturn JSON with: task_type, parameters, confidence"
        )

    def _build_plan_prompt(self, task: Task, intent: Dict[str, Any]) -> str:
        return (
            f"Generate execution plan:\n"
            f"Intent: {json.dumps(intent)}\n"
            f"Available workflows: {self.available_workflows}\n"
            f"\nReturn JSON with: workflow_id, parameters, steps, exception_handlers, confidence, reasoning"
        )

    def _build_exception_prompt(
        self, task: Task, plan: WorkflowPlan, error: Exception, state: Dict[str, Any]
    ) -> str:
        return (
            f"Handle exception:\n"
            f"Task: {task.description}\n"
            f"Original plan: {plan.workflow_id}\n"
            f"Error: {error}\n"
            f"Workflow state: {json.dumps(state)}\n"
            f"\nReturn JSON with: action (retry/escalate/modify/switch), workflow_id, parameters, reasoning"
        )

    def _build_interpret_prompt(
        self, task: Task, result: Dict[str, Any], user_context: Optional[Dict[str, Any]]
    ) -> str:
        return (
            f"Interpret workflow result:\n"
            f"Task: {task.description}\n"
            f"Result: {json.dumps(result)}\n"
            f"User context: {json.dumps(user_context or {})}\n"
            f"\nProvide a clear, concise summary of the result."
        )
