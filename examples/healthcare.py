"""Healthcare Operations Example - AgentFlow Demo."""

import json
from agentflow import AgentLayer, WorkflowEngine, HybridOrchestrator, AuditLogger
from agentflow.models import Task
from agentflow.workflow import WorkflowDefinition, WorkflowStep


def parse_medical_records(state):
    """Parse unstructured medical records and insurance info."""
    params = state.get("parameters", {})
    return {
        "patient_id": params.get("patient_id", "PAT-001"),
        "records_parsed": True,
        "insurance_verified": True,
        "primary_diagnosis": params.get("diagnosis", "general_checkup"),
    }


def verify_insurance(state):
    """Verify insurance eligibility and pre-authorization."""
    return {
        "insurance_verified": True,
        "pre_auth_approved": True,
        "coverage_amount": 50000,
        "copay": 200,
    }


def schedule_intake(state):
    """Schedule patient intake appointment."""
    return {
        "scheduled": True,
        "facility": "Hospital-A",
        "department": "Internal Medicine",
        "time_slot": "2026-05-02T09:00:00",
    }


def process_admission(state):
    """Process patient admission."""
    return {
        "admitted": True,
        "bed_assignment": "Ward-3B-12",
        "attending_physician": "Dr. Wang",
    }


def healthcare_llm(prompt, **kwargs):
    """Mock LLM for healthcare operations."""
    return json.dumps({
        "workflow_id": "healthcare_intake",
        "parameters": {
            "patient_id": "PAT-7890",
            "diagnosis": "cardiology_screening",
            "insurance_id": "INS-456",
            "facility": "Hospital-A",
        },
        "steps": ["parse_medical_records", "verify_insurance", "schedule_intake", "process_admission"],
        "confidence": 0.96,
        "reasoning": "Patient intake for cardiology screening, insurance verified",
    })


def main():
    print("=" * 60)
    print("AgentFlow: Healthcare Operations Example")
    print("=" * 60)

    agent = AgentLayer(
        llm_fn=healthcare_llm,
        available_workflows=["healthcare_intake"],
    )

    engine = WorkflowEngine(audit_logger=AuditLogger())

    workflow = WorkflowDefinition(
        workflow_id="healthcare_intake",
        name="Patient Intake Process",
        steps=[
            WorkflowStep("parse_medical_records", parse_medical_records),
            WorkflowStep("verify_insurance", verify_insurance),
            WorkflowStep("schedule_intake", schedule_intake),
            WorkflowStep("process_admission", process_admission),
        ],
    )
    engine.register_workflow(workflow)

    orchestrator = HybridOrchestrator(
        agent=agent,
        workflow_engine=engine,
        audit_logger=AuditLogger(),
    )

    task = Task(
        task_type="healthcare",
        description="Patient intake for cardiology screening",
        parameters={
            "patient_id": "PAT-7890",
            "diagnosis": "cardiology_screening",
            "insurance_id": "INS-456",
        },
    )

    print(f"\n📋 Task: {task.description}")
    result = orchestrator.execute(task)

    print(f"\n✅ Result: {result.status.value}")
    print(f"   Steps completed: {result.steps_completed}")
    print(f"   Duration: {result.duration_ms:.1f}ms")

    report = orchestrator.audit_logger.get_compliance_report(task.task_id)
    print(f"\n📊 Audit Report:")
    print(f"   Total entries: {report['total_entries']}")
    print(f"   Agent actions: {report['agent_actions']}")
    print(f"   Workflow actions: {report['workflow_actions']}")
    print(f"   Errors: {report['errors']}")


if __name__ == "__main__":
    main()
