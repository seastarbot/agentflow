"""RuleEngine: Business rule execution for compliance enforcement."""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional

from .models import Rule, Severity

logger = logging.getLogger(__name__)


class RuleEngine:
    """
    Business rule engine for deterministic compliance enforcement.

    Rules are evaluated before each workflow step. Violations are reported
    as audit entries, and critical violations trigger automatic rollback.
    """

    def __init__(self) -> None:
        self._rules: List[Rule] = []
        self._rule_handlers: Dict[str, Callable[[Dict[str, Any]], bool]] = {}

    def add_rule(
        self,
        rule: Rule,
        handler: Optional[Callable[[Dict[str, Any]], bool]] = None,
    ) -> None:
        """
        Add a business rule with an optional evaluation handler.

        The handler receives the current workflow state and returns True
        if the rule is violated.
        """
        self._rules.append(rule)
        if handler:
            self._rule_handlers[rule.rule_id] = handler
        logger.info(f"Added rule: {rule.rule_id} - {rule.name}")

    def remove_rule(self, rule_id: str) -> bool:
        """Remove a rule by ID."""
        before = len(self._rules)
        self._rules = [r for r in self._rules if r.rule_id != rule_id]
        self._rule_handlers.pop(rule_id, None)
        return len(self._rules) < before

    def evaluate(
        self,
        step_name: str,
        state: Dict[str, Any],
    ) -> List[Rule]:
        """
        Evaluate all enabled rules against the current state.

        Returns list of violated rules (empty if all pass).
        """
        violations = []

        for rule in self._rules:
            if not rule.enabled:
                continue

            handler = self._rule_handlers.get(rule.rule_id)
            if handler is None:
                continue

            try:
                is_violated = handler(state)
                if is_violated:
                    violations.append(rule)
                    logger.warning(
                        f"Rule violation: {rule.rule_id} ({rule.name}) "
                        f"at step {step_name}"
                    )
            except Exception as e:
                logger.error(f"Rule evaluation error for {rule.rule_id}: {e}")

        return violations

    def get_rules(self, enabled_only: bool = True) -> List[Rule]:
        """Get all rules, optionally filtered to enabled only."""
        if enabled_only:
            return [r for r in self._rules if r.enabled]
        return list(self._rules)

    @staticmethod
    def amount_threshold(max_amount: float) -> Callable[[Dict[str, Any]], bool]:
        """Create a rule handler that checks amount against a threshold."""
        def handler(state: Dict[str, Any]) -> bool:
            amount = state.get("parameters", {}).get("amount", 0)
            return amount > max_amount
        return handler

    @staticmethod
    def required_fields(*fields: str) -> Callable[[Dict[str, Any]], bool]:
        """Create a rule handler that checks for required fields."""
        def handler(state: Dict[str, Any]) -> bool:
            params = state.get("parameters", {})
            return not all(f in params for f in fields)
        return handler

    @staticmethod
    def compliance_check(
        check_fn: Callable[[Dict[str, Any]], bool],
    ) -> Callable[[Dict[str, Any]], bool]:
        """Create a rule handler from a custom compliance function."""
        def handler(state: Dict[str, Any]) -> bool:
            return check_fn(state)
        return handler
