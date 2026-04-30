"""Financial Compliance Example - AgentFlow Demo."""

import json
from agentflow import AgentLayer, WorkflowEngine, HybridOrchestrator, AuditLogger, RuleEngine
from agentflow.models import Task, Rule, Severity
from agentflow.workflow import WorkflowDefinition, WorkflowStep


def parse_regulation(state):
    """Parse regulatory requirements for jurisdiction."""
    params = state.get("parameters", {})
    jurisdiction = params.get("jurisdiction", "US")
    return {
        "regulation": f"{jurisdiction}-SEC-2026",
        "deadline": "2026-06-30",
        "requirements": ["financial_statements", "risk_disclosure", "audit_report"],
    }


def validate_data(state):
    """Validate financial data completeness and accuracy."""
    return {"data_valid": True, "completeness": 0.99, "accuracy": 0.998}


def compliance_check(state):
    """Run automated compliance checks."""
    return {"compliance_passed": True, "violations": 0}


def generate_report(state):
    """Generate regulatory report."""
    return {
        "report_generated": True,
        "report_id": f"RPT-{state.get('task_id', '000')}",
        "format": "XBRL",
        "pages": 47,
    }


def submit_report(state):
    """Submit report to regulatory authority."""
    return {
        "submitted": True,
        "confirmation": "CONF-2026-001",
        "submission_time": "2026-05-15T14:30:00",
    }


def compensate_submission(state):
    """Compensate: withdraw submitted report if needed."""
    state["report_withdrawn"] = True


def financial_llm(prompt, **kwargs):
    """Mock LLM for financial compliance."""
    return json.dumps({
        "workflow_id": "financial_compliance",
        "parameters": {
            "jurisdiction": "US",
            "report_type": "quarterly",
            "entity": "TechCorp Inc.",
            "amount": 2500000,
        },
        "steps": ["parse_regulation", "validate_data", "compliance_check", "generate_report", "submit"],
        "confidence": 0.98,
        "reasoning": "Quarterly report for US entity, all compliance checks passed",
    })


def main():
    print("=" * 60)
    print("AgentFlow: Financial Compliance Example")
    print("=" * 60)

    # Setup
    agent = AgentLayer(
        llm_fn=financial_llm,
        available_workflows=["financial_compliance"],
    )

    engine = WorkflowEngine(audit_logger=AuditLogger(), rule_engine=RuleEngine())

    workflow = WorkflowDefinition(
        workflow_id="financial_compliance",
        name="Financial Regulatory Compliance",
        steps=[
            WorkflowStep("parse_regulation", parse_regulation),
            WorkflowStep("validate_data", validate_data),
            WorkflowStep("compliance_check", compliance_check),
            WorkflowStep("generate_report", generate_report),
            WorkflowStep("submit", submit_report, compensation=compensate_submission),
        ],
    )
    engine.register_workflow(workflow)

    # Compliance rules
    engine.rule_engine.add_rule(
        Rule(
            rule_id="max_report_amount",
            name="Maximum Reportable Amount",
            severity=Severity.CRITICAL,
        ),
        handler=RuleEngine.amount_threshold(10000000),
    )

    orchestrator = HybridOrchestrator(
        agent=agent,
        workflow_engine=engine,
        audit_logger=AuditLogger(),
    )

    task = Task(
        task_type="financial",
        description="Submit Q2 2026 quarterly report for TechCorp Inc.",
        parameters={"jurisdiction": "US", "report_type": "quarterly", "entity": "TechCorp Inc."},
    )

    print(f"\n📋 Task: {task.description}")
    result = orchestrator.execute(task)

    print(f"\n✅ Result: {result.status.value}")
    print(f"   Steps completed: {result.steps_completed}")
    print(f"   Duration: {result.duration_ms:.1f}ms")

    # Compliance report
    report = orchestrator.audit_logger.get_compliance_report(task.task_id)
    print(f"\n📊 Compliance Report:")
    print(f"   Total audit entries: {report['total_entries']}")
    print(f"   Agent actions: {report['agent_actions']}")
    print(f"   Workflow actions: {report['workflow_actions']}")
    print(f"   Errors: {report['errors']}")
    print(f"   Total duration: {report['total_duration_ms']:.1f}ms")


if __name__ == "__main__":
    main()
