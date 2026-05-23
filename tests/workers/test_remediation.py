from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, patch

from agent.settings import AppSettings
from workers.remediation import AutonomousRemediation


def test_autonomous_actions_disabled_by_default() -> None:
    remediation = AutonomousRemediation()
    assert remediation.rules["restart_crashing_container"].enabled is False


def test_remediation_blocked_in_stage_1_and_2() -> None:
    remediation = AutonomousRemediation()
    remediation.settings = AppSettings(write_stage=2)
    remediation.rules["restart_crashing_container"].enabled = True

    mock_action = AsyncMock()
    result = asyncio.run(
        remediation.execute_action("restart_crashing_container", "test", mock_action)
    )

    assert result is False
    mock_action.assert_not_called()


@patch("workers.remediation.store_event", new_callable=AsyncMock)
@patch("workers.remediation.dispatch_alert")
def test_remediation_execution_and_receipt(mock_dispatch: Any, mock_store: Any) -> None:
    remediation = AutonomousRemediation()
    remediation.settings = AppSettings(write_stage=3)
    remediation.rules["restart_crashing_container"].enabled = True

    mock_action = AsyncMock()
    result = asyncio.run(
        remediation.execute_action("restart_crashing_container", "test", mock_action)
    )

    assert result is True
    mock_store.assert_called_once()
    mock_dispatch.assert_called_once()
