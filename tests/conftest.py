"""
Pytest fixtures and configuration for Inactive Mailbox Manager tests.
"""

from datetime import datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.data.models import InactiveMailbox


@pytest.fixture
def sample_mailbox() -> InactiveMailbox:
    """Create a sample inactive mailbox for testing."""
    return InactiveMailbox(
        identity="12345678-1234-1234-1234-123456789012",
        display_name="John Smith",
        primary_smtp="john.smith@contoso.com",
        user_principal_name="john.smith@contoso.com",
        when_soft_deleted=datetime.now() - timedelta(days=30),
        age_days=30,
        litigation_hold=True,
        hold_types=["LitigationHold"],
        size_mb=2500.5,
        item_count=15000,
        archive_guid="87654321-4321-4321-4321-210987654321",
        license_type="E5",
        monthly_cost=38.00,
        department="Engineering",
        operating_company="Contoso",
    )


@pytest.fixture
def sample_mailbox_no_holds() -> InactiveMailbox:
    """Create a sample mailbox without holds."""
    return InactiveMailbox(
        identity="22222222-2222-2222-2222-222222222222",
        display_name="Jane Doe",
        primary_smtp="jane.doe@contoso.com",
        user_principal_name="jane.doe@contoso.com",
        when_soft_deleted=datetime.now() - timedelta(days=90),
        age_days=90,
        litigation_hold=False,
        hold_types=[],
        size_mb=1200.0,
        item_count=8000,
        license_type="E3",
        monthly_cost=20.00,
    )


@pytest.fixture
def sample_mailbox_list(
    sample_mailbox: InactiveMailbox, sample_mailbox_no_holds: InactiveMailbox
) -> list[InactiveMailbox]:
    """Create a list of sample mailboxes."""
    return [sample_mailbox, sample_mailbox_no_holds]


@pytest.fixture
def mock_session() -> MagicMock:
    """Create a mock session manager."""
    session = MagicMock()
    session.is_connected = True
    session.organization = "contoso.onmicrosoft.com"
    session.mailboxes = []
    session.get_mailbox = MagicMock(return_value=None)
    session.refresh_mailboxes = AsyncMock(return_value=[])
    return session


@pytest.fixture
def mock_powershell_executor() -> MagicMock:
    """Create a mock PowerShell executor."""
    executor = MagicMock()
    executor.execute = AsyncMock(return_value={"success": True, "output": []})
    executor.is_connected = True
    return executor


@pytest.fixture
def mock_exchange_connection() -> MagicMock:
    """Create a mock Exchange connection."""
    connection = MagicMock()
    connection.connect = AsyncMock(return_value=True)
    connection.disconnect = AsyncMock()
    connection.is_connected = True
    connection.execute_command = AsyncMock(return_value=[])
    return connection


@pytest.fixture
def sample_config() -> dict[str, Any]:
    """Create sample configuration dictionary."""
    return {
        "azure": {
            "tenant_id": "12345678-1234-1234-1234-123456789012",
            "client_id": "87654321-4321-4321-4321-210987654321",
            "certificate_path": "certs/app.pfx",
        },
        "exchange": {
            "organization": "contoso.onmicrosoft.com",
            "page_size": 1000,
            "timeout": 300,
        },
        "costs": {
            "e5_monthly": 38.00,
            "e3_monthly": 20.00,
            "f3_monthly": 10.00,
            "default_license": "E3",
        },
        "cache": {
            "enabled": True,
            "ttl_minutes": 60,
        },
    }


@pytest.fixture
def sample_csv_content() -> str:
    """Create sample CSV content for bulk operations."""
    return """SourceMailbox,TargetUPN,TargetName,IncludeArchive
john.smith@contoso.com,john.smith.new@contoso.com,John Smith,true
jane.doe@contoso.com,jane.doe.new@contoso.com,Jane Doe,false
"""


@pytest.fixture
def temp_config_file(tmp_path, sample_config) -> str:
    """Create a temporary config file."""
    import yaml

    config_path = tmp_path / "config.yaml"
    with open(config_path, "w") as f:
        yaml.dump(sample_config, f)
    return str(config_path)
