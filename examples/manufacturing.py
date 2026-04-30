"""Manufacturing Execution Example - AgentFlow Demo."""

import json
from agentflow import AgentLayer, WorkflowEngine, HybridOrchestrator, AuditLogger, RuleEngine
from agentflow.models import Task, Rule, Severity
from agentflow.workflow import WorkflowDefinition, WorkflowStep


def parse_order(state):
    """Parse customer order from email/text."""
    params = state.get("parameters", {})
    return {
        "order_id": params.get("order_id", "ORD-NEW"),
        "parsed": True,
        "customer": params.get("customer", "unknown"),
    }


def check_inventory(state):
    """Check inventory availability."""
    quantity = state.get("parameters", {}).get("quantity", 0)
    # Simulate inventory check
    return {"inventory_available": quantity <= 1000, "warehouse": "WH-BJ-01"}


def schedule_production(state):
    """Schedule production on production line."""
    return {
        "scheduled": True,
        "line_id": "LINE-03",
        "start_time": "2026-05-01T08:00:00",
        "estimated_duration": "4h",
    }


def quality_check(state):
    """Run quality checks on produced items."""
    return {"quality_passed": True, "defect_rate": 0.002}


def ship_order(state):
    """Ship completed order."""
    return {
        "shipped": True,
        "tracking": f"SF-{state.get('parameters', {}).get('order_id', '000')}",
        "carrier": "SF Express",
    }


def compensate_production(state):
    """Compensate production (cancel if needed)."""
    state["production_cancelled"] = True


def manufacturing_llm(prompt, **kwargs):
    """Mock LLM for manufacturing intent parsing."""
    return json.dumps({
        "workflow_id": "manufacturing",
        "parameters": {
            "order_id": "ORD-5001",
            "quantity": 200,
            "priority": "standard",
            "customer": "Acme Corp",
        },
        "steps": ["parse_order", "check_inventory", "schedule_production", "quality_check", "ship"],
        "confidence": 0.94,
        "reasoning": "Standard manufacturing order, all checks passed",
    })


def main():
    print("=" * 60)
    print("AgentFlow: Manufacturing Execution Example")
    print("=" * 60)

    # Setup components
    agent = AgentLayer(
        llm_fn=manufacturing_llm,
        available_workflows=["manufacturing"],
    )

    engine = WorkflowEngine(audit_logger=AuditLogger())

    # Register manufacturing workflow
    workflow = WorkflowDefinition(
        workflow_id="manufacturing",
        name="Electronics Manufacturing",
        steps=[
            WorkflowStep("parse_order", parse_order),
            WorkflowStep("check_inventory", check_inventory),
            WorkflowStep("schedule_production", schedule_production, compensation=compensate_production),
            WorkflowStep("quality_check", quality_check),
            WorkflowStep("ship", ship_order),
        ],
    )
    engine.register_workflow(workflow)

    # Add business rules
    engine.rule_engine.add_rule(
        Rule(
            rule_id="max_batch_size",
            name="Maximum Batch Size",
            severity=Severity.WARNING,
        ),
        handler=RuleEngine.amount_threshold(500),
    )

    # Create orchestrator
    orchestrator = HybridOrchestrator(
        agent=agent,
        workflow_engine=engine,
        audit_logger=AuditLogger(),
    )

    # Execute a manufacturing order
    task = Task(
        task_type="manufacturing",
        description="Process rush order for Acme Corp - 200 units",
        parameters={"order_id": "ORD-5001", "quantity": 200, "customer": "Acme Corp"},
    )

    print(f"\n📋 Task: {task.description}")
    print(f"   Task ID: {task.task_id}")

    result = orchestrator.execute(task)

    print(f"\n✅ Result: {result.status.value}")
    print(f"   Steps completed: {result.steps_completed}")
    print(f"   Duration: {result.duration_ms:.1f}ms")

    # Show audit trail
    report = orchestrator.audit_logger.get_compliance_report(task.task_id)
    print(f"\n📊 Audit Report:")
    print(f"   Total entries: {report['total_entries']}")
    print(f"   Agent actions: {report['agent_actions']}")
    print(f"   Workflow actions: {report['workflow_actions']}")
    print(f"   Errors: {report['errors']}")

    # Show stats
    stats = orchestrator.get_stats()
    print(f"\n📈 Stats:")
    print(f"   Total executions: {stats['total_executions']}")
    print(f"   Success rate: {stats['success_rate']:.1%}")


if __name__ == "__main__":
    main()
