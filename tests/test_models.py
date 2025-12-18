"""
Unit tests for data models.
"""

from datetime import datetime, timedelta

import pytest

from src.data.models import InactiveMailbox


class TestInactiveMailbox:
    """Tests for InactiveMailbox model."""

    def test_create_mailbox(self, sample_mailbox: InactiveMailbox) -> None:
        """Test creating an inactive mailbox."""
        assert sample_mailbox.display_name == "John Smith"
        assert sample_mailbox.primary_smtp == "john.smith@contoso.com"
        assert sample_mailbox.litigation_hold is True

    def test_mailbox_has_holds(self, sample_mailbox: InactiveMailbox) -> None:
        """Test mailbox with holds."""
        assert sample_mailbox.litigation_hold is True
        assert len(sample_mailbox.hold_types) > 0

    def test_mailbox_no_holds(self, sample_mailbox_no_holds: InactiveMailbox) -> None:
        """Test mailbox without holds."""
        assert sample_mailbox_no_holds.litigation_hold is False
        assert len(sample_mailbox_no_holds.hold_types) == 0

    def test_mailbox_size(self, sample_mailbox: InactiveMailbox) -> None:
        """Test mailbox size."""
        assert sample_mailbox.size_mb == 2500.5

    def test_mailbox_has_archive(self, sample_mailbox: InactiveMailbox) -> None:
        """Test mailbox with archive."""
        assert sample_mailbox.archive_guid != ""

    def test_mailbox_no_archive(self, sample_mailbox_no_holds: InactiveMailbox) -> None:
        """Test mailbox without archive."""
        assert sample_mailbox_no_holds.archive_guid == ""

    def test_mailbox_age_days(self, sample_mailbox: InactiveMailbox) -> None:
        """Test age in days."""
        assert sample_mailbox.age_days == 30

    def test_mailbox_to_dict(self, sample_mailbox: InactiveMailbox) -> None:
        """Test serialization to dictionary."""
        data = sample_mailbox.to_dict()
        assert data["display_name"] == "John Smith"
        assert data["primary_smtp"] == "john.smith@contoso.com"
        assert "identity" in data

    def test_mailbox_from_dict(self) -> None:
        """Test creating mailbox from dictionary."""
        data = {
            "identity": "11111111-1111-1111-1111-111111111111",
            "display_name": "Test User",
            "primary_smtp": "test@contoso.com",
            "user_principal_name": "test@contoso.com",
            "litigation_hold": False,
            "size_mb": 100.0,
            "item_count": 500,
            "hold_types": "[]",
            "recovery_blockers": "[]",
        }
        mailbox = InactiveMailbox.from_dict(data)
        assert mailbox.display_name == "Test User"
        assert mailbox.size_mb == 100.0

    def test_mailbox_from_exchange_data(self) -> None:
        """Test creating mailbox from Exchange PowerShell output."""
        data = {
            "ExchangeGuid": "33333333-3333-3333-3333-333333333333",
            "DisplayName": "Exchange User",
            "PrimarySmtpAddress": "exchange@contoso.com",
            "UserPrincipalName": "exchange@contoso.com",
            "LitigationHoldEnabled": True,
            "InPlaceHolds": ["hold1", "hold2"],
        }
        mailbox = InactiveMailbox.from_exchange_data(data)
        assert mailbox.display_name == "Exchange User"
        assert mailbox.litigation_hold is True
        assert len(mailbox.hold_types) == 2

    def test_mailbox_license_and_cost(self, sample_mailbox: InactiveMailbox) -> None:
        """Test license type and cost."""
        assert sample_mailbox.license_type == "E5"
        assert sample_mailbox.monthly_cost == 38.00

    def test_mailbox_recovery_eligible(self, sample_mailbox: InactiveMailbox) -> None:
        """Test recovery eligibility flag."""
        assert sample_mailbox.recovery_eligible is True

    def test_mailbox_department(self, sample_mailbox: InactiveMailbox) -> None:
        """Test department field."""
        assert sample_mailbox.department == "Engineering"
