"""AuditLogger: Structured audit logging for compliance and traceability."""

from __future__ import annotations

import json
import logging
import threading
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from .models import AuditEntry, Severity, TaskStatus

logger = logging.getLogger(__name__)


class AuditLogger:
    """
    Structured audit logger for industrial AI systems.

    Provides machine-readable, timestamped audit trails suitable for
    regulatory review. Thread-safe for concurrent workflow execution.
    """

    def __init__(
        self,
        log_file: Optional[str] = None,
        custom_handler: Optional[Callable[[AuditEntry], None]] = None,
    ):
        self.log_file = log_file
        self.custom_handler = custom_handler
        self._entries: List[AuditEntry] = []
        self._lock = threading.Lock()

    def log(
        self,
        task_id: str,
        component: str,
        action: str,
        input_data: Optional[Dict[str, Any]] = None,
        output_data: Optional[Dict[str, Any]] = None,
        severity: Severity = Severity.INFO,
        duration_ms: float = 0.0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AuditEntry:
        """Log a structured audit entry."""
        entry = AuditEntry(
            task_id=task_id,
            component=component,
            action=action,
            severity=severity,
            input_data=input_data or {},
            output_data=output_data or {},
            duration_ms=duration_ms,
            metadata=metadata or {},
        )

        with self._lock:
            self._entries.append(entry)

        # Write to file if configured
        if self.log_file:
            self._write_to_file(entry)

        # Call custom handler if configured
        if self.custom_handler:
            try:
                self.custom_handler(entry)
            except Exception as e:
                logger.error(f"Custom audit handler failed: {e}")

        # Log to standard logger
        log_fn = {
            Severity.INFO: logger.info,
            Severity.WARNING: logger.warning,
            Severity.ERROR: logger.error,
            Severity.CRITICAL: logger.critical,
        }.get(severity, logger.info)

        log_fn(
            f"[{component}] {action} | task={task_id} | "
            f"duration={duration_ms:.1f}ms | severity={severity.value}"
        )

        return entry

    def get_entries(
        self,
        task_id: Optional[str] = None,
        component: Optional[str] = None,
        severity: Optional[Severity] = None,
        since: Optional[datetime] = None,
    ) -> List[AuditEntry]:
        """Query audit entries with optional filters."""
        with self._lock:
            entries = list(self._entries)

        if task_id:
            entries = [e for e in entries if e.task_id == task_id]
        if component:
            entries = [e for e in entries if e.component == component]
        if severity:
            entries = [e for e in entries if e.severity == severity]
        if since:
            entries = [e for e in entries if e.timestamp >= since]

        return entries

    def get_task_trace(self, task_id: str) -> List[AuditEntry]:
        """Get complete audit trace for a task, ordered by time."""
        entries = self.get_entries(task_id=task_id)
        entries.sort(key=lambda e: e.timestamp)
        return entries

    def get_compliance_report(self, task_id: str) -> Dict[str, Any]:
        """Generate a compliance report for a task."""
        entries = self.get_task_trace(task_id)

        agent_entries = [e for e in entries if e.component == "agent"]
        workflow_entries = [e for e in entries if e.component == "workflow"]

        errors = [e for e in entries if e.severity in (Severity.ERROR, Severity.CRITICAL)]
        total_duration = sum(e.duration_ms for e in entries)

        return {
            "task_id": task_id,
            "total_entries": len(entries),
            "agent_actions": len(agent_entries),
            "workflow_actions": len(workflow_entries),
            "errors": len(errors),
            "total_duration_ms": total_duration,
            "trace": [
                {
                    "timestamp": e.timestamp.isoformat(),
                    "component": e.component,
                    "action": e.action,
                    "severity": e.severity.value,
                    "duration_ms": e.duration_ms,
                }
                for e in entries
            ],
        }

    def _write_to_file(self, entry: AuditEntry) -> None:
        """Write audit entry to file in JSONL format."""
        try:
            record = {
                "entry_id": entry.entry_id,
                "timestamp": entry.timestamp.isoformat(),
                "task_id": entry.task_id,
                "component": entry.component,
                "action": entry.action,
                "severity": entry.severity.value,
                "input_data": entry.input_data,
                "output_data": entry.output_data,
                "duration_ms": entry.duration_ms,
                "metadata": entry.metadata,
            }
            with open(self.log_file, "a") as f:
                f.write(json.dumps(record) + "\n")
        except Exception as e:
            logger.error(f"Failed to write audit log: {e}")

    def export_json(self, task_id: Optional[str] = None) -> str:
        """Export audit entries as JSON."""
        entries = self.get_entries(task_id=task_id) if task_id else self._entries
        return json.dumps(
            [
                {
                    "entry_id": e.entry_id,
                    "timestamp": e.timestamp.isoformat(),
                    "task_id": e.task_id,
                    "component": e.component,
                    "action": e.action,
                    "severity": e.severity.value,
                    "duration_ms": e.duration_ms,
                }
                for e in entries
            ],
            indent=2,
        )
