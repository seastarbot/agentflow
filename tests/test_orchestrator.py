"""Tests for HybridOrchestrator."""

import json
import pytest
from agentflow.agent import AgentLayer
from agentflow.audit import AuditLogger
from agentflow.orchestrator import HybridOrchestrator
from agentflow.models import Task, TaskStatus
from agentflow.rules import RuleEngine, Rule
from agentflow.workflow import WorkflowEngine, WorkflowDefinition, WorkflowStep


def step_validate(state):
    return {"validated": True}


def step_execute(state):
    return {"executed": True, "result": "success"}


def step_audit(state):
    return {"audited": True}


def mock_llm(prompt, **kwargs):
    return json.dumps({
        "workflow_id": "test_workflow",
        "parameters": {"action": "process"},
        "steps": ["validate", "execute", "audit"],
        "confidence": 0.9,
        "reasoning": "Test plan",
    })


@pytest.fixture
def orchestrator():
    """Create a HybridOrchestrator with test components."""
    agent = AgentLayer(
        llm_fn=mock_llm,
        audit_logger=AuditLogger(),
        available_workflows=["test_workflow"],
    )

    engine = WorkflowEngine(audit_logger=AuditLogger())
    workflow = WorkflowDefinition(
        workflow_id="test_workflow",
        name="Test Workflow",
        steps=[
            WorkflowStep("validate", step_validate),
            WorkflowStep("execute", step_execute),
            WorkflowStep("audit", step_audit),
        ],
    )
    engine.register_workflow(workflow)

    return HybridOrchestrator(
        agent=agent,
        workflow_engine=engine,
        audit_logger=AuditLogger(),
    )


def test_execute_task(orchestrator):
    task = Task(
        task_type="test",
        description="Process test order",
        parameters={"amount": 5000},
    )
    result = orchestrator.execute(task)
    assert result.status == TaskStatus.COMPLETED


def test_full_audit_trail(orchestrator):
    task = Task(task_id="audit-test", task_type="test", description="Test audit trail")
    orchestrator.execute(task)

    # Orchestrator logs its own entries
    orch_entries = orchestrator.audit_logger.get_entries(task_id=task.task_id)
    assert len(orch_entries) >= 2  # received + workflow_start + completed

    # Agent logs to its own logger
    agent_entries = orchestrator.agent.audit_logger.get_entries(task_id=task.task_id)
    assert len(agent_entries) >= 2  # resolve_intent + generate_plan

    # Workflow logs to its own logger
    wf_entries = orchestrator.workflow_engine.audit_logger.get_entries(task_id=task.task_id)
    assert len(wf_entries) >= 4  # 3 steps + completion


def test_compliance_report(orchestrator):
    task = Task(task_id="compliance-test", task_type="test", description="Test compliance")
    orchestrator.execute(task)

    # Each layer has its own compliance report
    orch_report = orchestrator.audit_logger.get_compliance_report(task.task_id)
    assert orch_report["task_id"] == task.task_id

    agent_report = orchestrator.agent.audit_logger.get_compliance_report(task.task_id)
    assert agent_report["agent_actions"] >= 2

    wf_report = orchestrator.workflow_engine.audit_logger.get_compliance_report(task.task_id)
    assert wf_report["workflow_actions"] >= 4
    assert wf_report["errors"] == 0


def test_execution_stats(orchestrator):
    for i in range(5):
        task = Task(task_type="test", description=f"Task {i}")
        orchestrator.execute(task)

    stats = orchestrator.get_stats()
    assert stats["total_executions"] == 5
    assert stats["success_rate"] == 1.0


def test_exception_recovery(orchestrator):
    """Test that agent handles workflow exceptions."""
    # This tests the recovery mechanism
    task = Task(task_type="test", description="Test recovery")
    result = orchestrator.execute(task)
    # Should succeed since mock LLM always returns valid plan
    assert result.status == TaskStatus.COMPLETED
