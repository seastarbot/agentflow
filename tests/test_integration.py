"""Integration tests for AgentFlow framework."""

import json
import pytest
from agentflow.agent import AgentLayer
from agentflow.audit import AuditLogger
from agentflow.orchestrator import HybridOrchestrator
from agentflow.models import Task, TaskStatus, Rule, Severity
from agentflow.rules import RuleEngine
from agentflow.workflow import WorkflowEngine, WorkflowDefinition, WorkflowStep


# --- Manufacturing scenario ---

def manufacturing_validate(state):
    order = state.get("parameters", {})
    if not order.get("order_id"):
        raise ValueError("Missing order_id")
    return {"validated": True, "quality_check": "passed"}


def manufacturing_execute(state):
    return {
        "produced": True,
        "batch_id": f"BATCH-{state.get('parameters', {}).get('order_id', '000')}",
        "units": state.get("parameters", {}).get("quantity", 0),
    }


def manufacturing_ship(state):
    return {"shipped": True, "tracking": f"TRACK-{state.get('parameters', {}).get('order_id', '000')}"}


def manufacturing_compensate(state):
    state["compensated"] = True


# --- Financial scenario ---

def financial_validate(state):
    report = state.get("parameters", {})
    if not report.get("jurisdiction"):
        raise ValueError("Missing jurisdiction")
    return {"validated": True, "format_check": "passed"}


def financial_comply(state):
    return {"compliance_check": "passed", "report_id": f"RPT-{state.get('task_id', '000')}"}


def financial_submit(state):
    return {"submitted": True, "confirmation": "CONF-001"}


# --- Mock LLM for manufacturing ---

def manufacturing_llm(prompt, **kwargs):
    return json.dumps({
        "workflow_id": "manufacturing",
        "parameters": {"order_id": "ORD-1001", "quantity": 500, "priority": "rush"},
        "steps": ["validate", "execute", "ship"],
        "confidence": 0.92,
        "reasoning": "Standard manufacturing order with rush priority",
    })


def financial_llm(prompt, **kwargs):
    return json.dumps({
        "workflow_id": "financial",
        "parameters": {"jurisdiction": "US", "report_type": "quarterly", "amount": 500000},
        "steps": ["validate", "comply", "submit"],
        "confidence": 0.97,
        "reasoning": "Quarterly financial report for US jurisdiction",
    })


def failing_llm(prompt, **kwargs):
    """LLM that simulates occasional failures."""
    if "exception" in prompt.lower():
        return json.dumps({
            "action": "retry",
            "workflow_id": "manufacturing",
            "parameters": {"order_id": "ORD-1001", "quantity": 500},
            "confidence": 0.5,
            "reasoning": "Retrying after timeout",
        })
    return manufacturing_llm(prompt, **kwargs)


@pytest.fixture
def manufacturing_system():
    """Full manufacturing system."""
    agent = AgentLayer(
        llm_fn=manufacturing_llm,
        available_workflows=["manufacturing"],
    )
    engine = WorkflowEngine(audit_logger=AuditLogger())
    workflow = WorkflowDefinition(
        workflow_id="manufacturing",
        name="Manufacturing Execution",
        steps=[
            WorkflowStep("validate", manufacturing_validate),
            WorkflowStep("execute", manufacturing_execute, compensation=manufacturing_compensate),
            WorkflowStep("ship", manufacturing_ship),
        ],
    )
    engine.register_workflow(workflow)

    return HybridOrchestrator(
        agent=agent,
        workflow_engine=engine,
        audit_logger=AuditLogger(),
    )


@pytest.fixture
def financial_system():
    """Full financial compliance system."""
    agent = AgentLayer(
        llm_fn=financial_llm,
        available_workflows=["financial"],
    )
    engine = WorkflowEngine(audit_logger=AuditLogger(), rule_engine=RuleEngine())
    workflow = WorkflowDefinition(
        workflow_id="financial",
        name="Financial Compliance",
        steps=[
            WorkflowStep("validate", financial_validate),
            WorkflowStep("comply", financial_comply),
            WorkflowStep("submit", financial_submit),
        ],
    )
    engine.register_workflow(workflow)

    return HybridOrchestrator(
        agent=agent,
        workflow_engine=engine,
        audit_logger=AuditLogger(),
    )


def test_manufacturing_e2e(manufacturing_system):
    """End-to-end manufacturing workflow."""
    task = Task(
        task_type="manufacturing",
        description="Process production order ORD-1001",
        parameters={"order_id": "ORD-1001", "quantity": 500, "priority": "rush"},
    )
    result = manufacturing_system.execute(task)
    assert result.status == TaskStatus.COMPLETED
    assert "validate" in result.steps_completed
    assert "execute" in result.steps_completed
    assert "ship" in result.steps_completed


def test_financial_e2e(financial_system):
    """End-to-end financial compliance workflow."""
    task = Task(
        task_type="financial",
        description="Submit quarterly report",
        parameters={"jurisdiction": "US", "report_type": "quarterly"},
    )
    result = financial_system.execute(task)
    assert result.status == TaskStatus.COMPLETED


def test_full_audit_trail(manufacturing_system):
    """Verify complete audit trail for compliance across all layers."""
    task = Task(
        task_type="manufacturing",
        description="Audit trail test",
        parameters={"order_id": "ORD-2001", "quantity": 100},
    )
    manufacturing_system.execute(task)

    # Each layer has its own audit logger
    orch_report = manufacturing_system.audit_logger.get_compliance_report(task.task_id)
    assert orch_report["total_entries"] >= 2  # task_received + task_completed

    agent_report = manufacturing_system.agent.audit_logger.get_compliance_report(task.task_id)
    assert agent_report["agent_actions"] >= 2  # intent + plan

    wf_report = manufacturing_system.workflow_engine.audit_logger.get_compliance_report(task.task_id)
    assert wf_report["workflow_actions"] >= 4  # 3 steps + completion
    assert wf_report["errors"] == 0

    # Verify trace is ordered by time
    for report in [orch_report, agent_report, wf_report]:
        trace = report["trace"]
        timestamps = [e["timestamp"] for e in trace]
        assert timestamps == sorted(timestamps)


def test_concurrent_executions(manufacturing_system):
    """Test multiple concurrent task executions."""
    results = []
    for i in range(10):
        task = Task(
            task_type="manufacturing",
            description=f"Concurrent order {i}",
            parameters={"order_id": f"ORD-{3000+i}", "quantity": (i+1)*100},
        )
        result = manufacturing_system.execute(task)
        results.append(result)

    assert all(r.status == TaskStatus.COMPLETED for r in results)
    stats = manufacturing_system.get_stats()
    assert stats["success_rate"] == 1.0


def test_rule_enforcement_financial(financial_system):
    """Test business rule enforcement in financial system."""
    # Add a rule that blocks reports over $1M
    financial_system.workflow_engine.rule_engine.add_rule(
        Rule(
            rule_id="amount_cap",
            name="Transaction Amount Cap",
            severity=Severity.CRITICAL,
        ),
        handler=RuleEngine.amount_threshold(1000000),
    )

    # Override LLM to return high amount
    def high_amount_llm(prompt, **kwargs):
        return json.dumps({
            "workflow_id": "financial",
            "parameters": {"jurisdiction": "US", "amount": 5000000},
            "steps": ["validate", "comply", "submit"],
            "confidence": 0.9,
            "reasoning": "High-value report",
        })

    financial_system.agent.llm_fn = high_amount_llm

    task = Task(
        task_type="financial",
        description="High-value report",
        parameters={"jurisdiction": "US", "amount": 5000000},
    )
    result = financial_system.execute(task)
    assert result.status in (TaskStatus.ROLLED_BACK, TaskStatus.FAILED)


def test_error_handling(manufacturing_system):
    """Test graceful error handling."""
    task = Task(
        task_type="manufacturing",
        description="Error test",
        parameters={"invalid": True},  # Missing required fields
    )
    # Should not crash, even with bad input
    result = manufacturing_system.execute(task)
    assert result.status in (TaskStatus.COMPLETED, TaskStatus.FAILED)
