"""Tests for AgentLayer."""

import json
import pytest
from agentflow.agent import AgentLayer
from agentflow.audit import AuditLogger
from agentflow.models import Task, TaskStatus


@pytest.fixture
def agent():
    """Create an AgentLayer with a mock LLM function."""
    def mock_llm(prompt, **kwargs):
        return json.dumps({
            "workflow_id": "order_processing",
            "parameters": {"order_type": "standard", "priority": "rush"},
            "steps": ["validate", "execute", "audit"],
            "exception_handlers": {"timeout": "retry"},
            "confidence": 0.95,
            "reasoning": "Standard order with rush priority",
        })

    return AgentLayer(
        llm_fn=mock_llm,
        audit_logger=AuditLogger(),
        available_workflows=["order_processing", "shipping"],
    )


def test_resolve_intent(agent):
    task = Task(
        task_type="order",
        description="Rush the usual order to Beijing",
        parameters={"amount": 5000},
    )
    intent = agent.resolve_intent(task)
    assert "workflow_id" in intent or "task_type" in intent


def test_generate_plan(agent):
    task = Task(
        task_type="order",
        description="Process order",
        parameters={"amount": 5000},
    )
    intent = agent.resolve_intent(task)
    plan = agent.generate_plan(task, intent)
    assert plan.workflow_id == "order_processing"
    assert plan.confidence > 0.8
    assert len(plan.steps) > 0


def test_handle_exception(agent):
    task = Task(task_type="order", description="Process order")
    plan = agent.generate_plan(task, {"workflow_id": "order_processing"})
    workflow_state = {"current_step": "execute", "retry_count": 0}

    recovery = agent.handle_exception(
        task, plan, Exception("Timeout"), workflow_state
    )
    assert recovery is not None
    assert recovery.task_id == task.task_id


def test_interpret_result(agent):
    task = Task(task_type="order", description="Process order")
    result = {"status": "completed", "order_id": "12345"}
    response = agent.interpret_result(task, result)
    assert isinstance(response, str)
    assert len(response) > 0


def test_audit_trail(agent):
    task = Task(task_type="order", description="Test audit")
    agent.resolve_intent(task)
    agent.generate_plan(task, {"workflow_id": "order_processing"})

    entries = agent.audit_logger.get_entries(task_id=task.task_id)
    assert len(entries) >= 2  # intent + plan
    assert all(e.task_id == task.task_id for e in entries)


def test_plan_history(agent):
    task = Task(task_type="order", description="Test history")
    for _ in range(3):
        agent.generate_plan(task, {"workflow_id": "order_processing"})
    assert len(agent._plan_history) == 3
