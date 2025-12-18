"""
Unit tests for core services.
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from src.data.models import InactiveMailbox
from src.core.onboarding import OnboardingWizard, OnboardingStep, OnboardingState


class TestOnboardingWizard:
    """Tests for OnboardingWizard."""

    @pytest.fixture
    def wizard(self, tmp_path) -> OnboardingWizard:
        """Create wizard with temporary config path."""
        config_path = str(tmp_path / "config.yaml")
        return OnboardingWizard(config_path=config_path)

    def test_initial_state(self, wizard: OnboardingWizard) -> None:
        """Test initial wizard state."""
        assert wizard.current_step == OnboardingStep.WELCOME
        assert wizard.is_complete is False

    def test_first_run_detection(self, wizard: OnboardingWizard) -> None:
        """Test first run detection."""
        assert wizard.is_first_run() is True

    def test_needs_onboarding(self, wizard: OnboardingWizard) -> None:
        """Test needs_onboarding check."""
        assert wizard.needs_onboarding() is True

    def test_set_and_get_value(self, wizard: OnboardingWizard) -> None:
        """Test setting and getting values."""
        wizard.set_value("organization", "contoso.onmicrosoft.com")
        assert wizard.get_value("organization") == "contoso.onmicrosoft.com"

    def test_next_step(self, wizard: OnboardingWizard) -> None:
        """Test navigating to next step."""
        initial = wizard.current_step
        next_step = wizard.next_step()
        assert next_step != initial
        assert wizard.current_step == next_step

    def test_previous_step(self, wizard: OnboardingWizard) -> None:
        """Test navigating to previous step."""
        wizard.next_step()  # Move to second step
        current = wizard.current_step
        prev_step = wizard.previous_step()
        assert prev_step != current
        assert wizard.current_step == prev_step

    def test_can_go_back(self, wizard: OnboardingWizard) -> None:
        """Test can_go_back check."""
        assert wizard.can_go_back() is False  # At first step
        wizard.next_step()
        assert wizard.can_go_back() is True

    def test_can_go_forward(self, wizard: OnboardingWizard) -> None:
        """Test can_go_forward check."""
        assert wizard.can_go_forward() is True

    def test_progress_tracking(self, wizard: OnboardingWizard) -> None:
        """Test progress tracking."""
        current, total = wizard.progress
        assert current == 1
        assert total > 1

    def test_validate_organization(self, wizard: OnboardingWizard) -> None:
        """Test organization validation."""
        wizard._state.current_step = OnboardingStep.ORGANIZATION

        # Empty value
        wizard.set_value("organization", "")
        errors = wizard.validate_current_step()
        assert len(errors) > 0

        # Valid value
        wizard.set_value("organization", "contoso.onmicrosoft.com")
        wizard.set_value("tenant_id", "12345678-1234-1234-1234-123456789012")
        wizard.set_value("client_id", "87654321-4321-4321-4321-210987654321")
        errors = wizard.validate_current_step()
        assert len(errors) == 0

    def test_validate_guid(self, wizard: OnboardingWizard) -> None:
        """Test GUID validation."""
        wizard._state.current_step = OnboardingStep.ORGANIZATION

        # Invalid GUID
        wizard.set_value("tenant_id", "invalid")
        wizard.set_value("organization", "test.onmicrosoft.com")
        wizard.set_value("client_id", "12345678-1234-1234-1234-123456789012")
        errors = wizard.validate_current_step()
        assert any("GUID" in e for e in errors)

    def test_skip_certificate_step(self, wizard: OnboardingWizard) -> None:
        """Test skipping certificate step when using secret."""
        wizard.set_value("auth_method", "secret")

        # Navigate to auth method step and beyond
        while wizard.current_step != OnboardingStep.AUTH_METHOD:
            wizard.next_step()
        wizard.next_step()

        # Should skip certificate step
        assert wizard.current_step != OnboardingStep.CERTIFICATE

    def test_save_config(self, wizard: OnboardingWizard) -> None:
        """Test saving configuration."""
        wizard.set_value("organization", "contoso.onmicrosoft.com")
        wizard.set_value("tenant_id", "12345678-1234-1234-1234-123456789012")
        wizard.set_value("client_id", "87654321-4321-4321-4321-210987654321")
        wizard.set_value("auth_method", "secret")
        wizard.set_value("client_secret", "test-secret")

        result = wizard.save_config()
        assert result is True

    def test_get_summary(self, wizard: OnboardingWizard) -> None:
        """Test getting configuration summary."""
        wizard.set_value("organization", "contoso.onmicrosoft.com")
        wizard.set_value("tenant_id", "12345678-1234-1234-1234-123456789012")

        summary = wizard.get_summary()
        assert "Organization" in summary
        assert summary["Organization"] == "contoso.onmicrosoft.com"


class TestFilterCriteria:
    """Tests for FilterCriteria dataclass."""

    def test_empty_criteria(self) -> None:
        """Test empty filter criteria."""
        from src.core.filter_service import FilterCriteria

        criteria = FilterCriteria()
        assert criteria.is_empty() is True

    def test_criteria_with_values(self) -> None:
        """Test filter criteria with values."""
        from src.core.filter_service import FilterCriteria

        criteria = FilterCriteria(
            has_any_hold=True,
            age_min_days=30,
            search_query="test",
        )
        assert criteria.is_empty() is False

    def test_criteria_to_dict(self) -> None:
        """Test criteria serialization."""
        from src.core.filter_service import FilterCriteria

        criteria = FilterCriteria(
            has_any_hold=True,
            size_min_mb=100.0,
        )
        data = criteria.to_dict()
        assert "has_any_hold" in data
        assert "size_min_mb" in data
        assert data["has_any_hold"] is True


class TestSummaryStats:
    """Tests for SummaryStats dataclass."""

    def test_hold_percentage(self) -> None:
        """Test hold percentage calculation."""
        from src.core.statistics_service import SummaryStats

        stats = SummaryStats(
            total_mailboxes=100,
            with_holds=25,
            without_holds=75,
        )
        assert stats.hold_percentage == 25.0

    def test_recovery_percentage(self) -> None:
        """Test recovery percentage calculation."""
        from src.core.statistics_service import SummaryStats

        stats = SummaryStats(
            total_mailboxes=100,
            recovery_eligible=80,
            recovery_blocked=20,
        )
        assert stats.recovery_percentage == 80.0

    def test_zero_mailboxes(self) -> None:
        """Test percentages with zero mailboxes."""
        from src.core.statistics_service import SummaryStats

        stats = SummaryStats(total_mailboxes=0)
        assert stats.hold_percentage == 0.0
        assert stats.recovery_percentage == 0.0
