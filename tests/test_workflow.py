"""Tests for WorkflowEngine."""

import pytest
from agentflow.audit import AuditLogger
from agentflow.models import TaskStatus, Severity
from agentflow.rules import RuleEngine, Rule
from agentflow.workflow import WorkflowEngine, WorkflowDefinition, WorkflowStep


def step_validate(state):
    return {"validated": True}


def step_execute(state):
    return {"executed": True, "order_id": "ORD-001"}


def step_audit(state):
    return {"audited": True}


def compensation_execute(state):
    state["compensated"] = True


@pytest.fixture
def engine():
    """Create a WorkflowEngine with a test workflow."""
    engine = WorkflowEngine(audit_logger=AuditLogger())

    workflow = WorkflowDefinition(
        workflow_id="order_processing",
        name="Order Processing",
        steps=[
            WorkflowStep("validate", step_validate),
            WorkflowStep("execute", step_execute, compensation=compensation_execute),
            WorkflowStep("audit", step_audit),
        ],
    )
    engine.register_workflow(workflow)
    return engine


def test_execute_workflow(engine):
    result = engine.execute(
        workflow_id="order_processing",
        parameters={"order_type": "standard"},
        task_id="test-001",
    )
    assert result.status == TaskStatus.COMPLETED
    assert "validate" in result.steps_completed
    assert "execute" in result.steps_completed
    assert "audit" in result.steps_completed
    assert result.output.get("execute", {}).get("order_id") == "ORD-001"


def test_workflow_not_found(engine):
    result = engine.execute(
        workflow_id="nonexistent",
        parameters={},
        task_id="test-002",
    )
    assert result.status == TaskStatus.FAILED
    assert "not found" in result.error


def test_step_failure_triggers_rollback():
    engine = WorkflowEngine(audit_logger=AuditLogger())
    compensations_called = []

    def step_fail(state):
        raise ValueError("Step failed")

    def compensate_step1(state):
        compensations_called.append("step1_compensated")

    workflow = WorkflowDefinition(
        workflow_id="rollback_test",
        name="Rollback Test",
        steps=[
            WorkflowStep("step1", lambda s: {"done": True}, compensation=compensate_step1),
            WorkflowStep("step2", step_fail),
        ],
    )
    engine.register_workflow(workflow)

    result = engine.execute(
        workflow_id="rollback_test",
        parameters={},
        task_id="test-rollback",
    )
    assert result.status == TaskStatus.FAILED
    assert "step1" in result.steps_completed
    assert "step2" in result.steps_failed
    assert "step1_compensated" in compensations_called


def test_optional_step_failure():
    engine = WorkflowEngine(audit_logger=AuditLogger())

    def step_fail(state):
        raise ValueError("Optional step failed")

    workflow = WorkflowDefinition(
        workflow_id="optional_test",
        name="Optional Step Test",
        steps=[
            WorkflowStep("step1", lambda s: {"done": True}),
            WorkflowStep("step2", step_fail, required=False),
            WorkflowStep("step3", lambda s: {"done": True}),
        ],
    )
    engine.register_workflow(workflow)

    result = engine.execute(
        workflow_id="optional_test",
        parameters={},
        task_id="test-optional",
    )
    assert result.status == TaskStatus.COMPLETED
    assert "step1" in result.steps_completed
    assert "step3" in result.steps_completed


def test_rule_enforcement():
    engine = WorkflowEngine(audit_logger=AuditLogger(), rule_engine=RuleEngine())

    # Add rule: amount > 10000 is critical violation
    engine.rule_engine.add_rule(
        Rule(rule_id="amount_limit", name="Amount Limit", severity=Severity.CRITICAL),
        handler=RuleEngine.amount_threshold(10000),
    )

    workflow = WorkflowDefinition(
        workflow_id="rule_test",
        name="Rule Test",
        steps=[WorkflowStep("execute", lambda s: {"done": True})],
    )
    engine.register_workflow(workflow)

    # This should trigger rule violation and rollback
    result = engine.execute(
        workflow_id="rule_test",
        parameters={"amount": 15000},
        task_id="test-rule",
    )
    assert result.status == TaskStatus.ROLLED_BACK


def test_audit_trail(engine):
    result = engine.execute(
        workflow_id="order_processing",
        parameters={},
        task_id="test-audit",
    )
    entries = engine.audit_logger.get_entries(task_id="test-audit")
    assert len(entries) >= 4  # 3 steps + completion


def test_state_management(engine):
    engine.execute(
        workflow_id="order_processing",
        parameters={"key": "value"},
        task_id="test-state",
    )
    state = engine.get_state("test-state")
    assert state.get("parameters", {}).get("key") == "value"
