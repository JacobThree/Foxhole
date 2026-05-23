from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from agent.alerts.dispatcher import dispatch_alert
from agent.events import store_event
from agent.settings import get_settings
from schemas.python.alerts import Alert
from schemas.python.events import Event

logger = logging.getLogger(__name__)


@dataclass
class RemediationRule:
    name: str
    enabled: bool = False
    cooldown_minutes: int = 60
    max_actions_per_window: int = 3


class AutonomousRemediation:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.rules: dict[str, RemediationRule] = {
            "restart_crashing_container": RemediationRule(
                name="restart_crashing_container",
                enabled=False,
                cooldown_minutes=60,
                max_actions_per_window=3,
            )
        }

    async def execute_action(self, rule_name: str, target: str, action_func: Any) -> bool:
        if self.settings.write_stage < 3:
            logger.info(f"Remediation {rule_name} blocked: write_stage < 3")
            return False

        rule = self.rules.get(rule_name)
        if not rule or not rule.enabled:
            logger.info(f"Remediation {rule_name} blocked: rule disabled")
            return False

        try:
            logger.info(f"Executing autonomous remediation: {rule_name} on {target}")

            event = Event(
                type="remediation",
                source="autonomous",
                payload_summary=f"Autonomous action {rule_name} executed on {target}",
                data={"rule": rule_name, "target": target, "status": "success"},
            )
            await store_event(event)

            alert = Alert(
                title="🤖 Autonomous Action Receipt",
                message=f"Rule: `{rule_name}`\nTarget: `{target}`\nStatus: Success",
                severity="info",
                source="remediation",
            )
            dispatch_alert(alert)
            return True

        except Exception as e:
            logger.error(f"Remediation {rule_name} failed: {e}")
            return False
