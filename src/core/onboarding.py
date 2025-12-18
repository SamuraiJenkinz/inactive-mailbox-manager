"""
Onboarding wizard for first-time setup of Inactive Mailbox Manager.

Guides users through Azure AD configuration, connection testing,
and initial configuration file generation.
"""

import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable

import yaml


class OnboardingStep(Enum):
    """Steps in the onboarding wizard."""

    WELCOME = "welcome"
    ORGANIZATION = "organization"
    AUTH_METHOD = "auth_method"
    CERTIFICATE = "certificate"
    CLIENT_SECRET = "client_secret"
    TEST_CONNECTION = "test_connection"
    COST_CONFIG = "cost_config"
    COMPLETE = "complete"


@dataclass
class OnboardingState:
    """Current state of the onboarding wizard."""

    current_step: OnboardingStep = OnboardingStep.WELCOME
    organization: str = ""
    tenant_id: str = ""
    client_id: str = ""
    auth_method: str = "certificate"  # certificate or secret
    certificate_path: str = ""
    certificate_password: str = ""
    client_secret: str = ""
    e5_cost: float = 38.00
    e3_cost: float = 20.00
    f3_cost: float = 10.00
    connection_tested: bool = False
    connection_success: bool = False
    errors: list[str] = field(default_factory=list)


@dataclass
class StepInfo:
    """Information about an onboarding step."""

    title: str
    description: str
    fields: list[str]
    optional: bool = False
    skip_condition: Callable[[OnboardingState], bool] | None = None


# Step definitions
STEPS: dict[OnboardingStep, StepInfo] = {
    OnboardingStep.WELCOME: StepInfo(
        title="Welcome to Inactive Mailbox Manager",
        description=(
            "This wizard will help you configure the application to connect "
            "to your Microsoft 365 tenant.\n\n"
            "Before continuing, ensure you have:\n"
            "- Azure AD App Registration with Exchange.ManageAsApp permission\n"
            "- Certificate (.pfx) or client secret for authentication\n"
            "- Your tenant ID and organization domain"
        ),
        fields=[],
    ),
    OnboardingStep.ORGANIZATION: StepInfo(
        title="Organization Details",
        description=(
            "Enter your Microsoft 365 organization details.\n\n"
            "The organization is typically your tenant domain "
            "(e.g., contoso.onmicrosoft.com)."
        ),
        fields=["organization", "tenant_id", "client_id"],
    ),
    OnboardingStep.AUTH_METHOD: StepInfo(
        title="Authentication Method",
        description=(
            "Choose how to authenticate with Azure AD.\n\n"
            "Certificate authentication is recommended for production use "
            "as it's more secure and doesn't expire as frequently."
        ),
        fields=["auth_method"],
    ),
    OnboardingStep.CERTIFICATE: StepInfo(
        title="Certificate Configuration",
        description=(
            "Provide the path to your certificate file (.pfx) and password.\n\n"
            "Make sure the public key (.cer) has been uploaded to your "
            "Azure AD App Registration."
        ),
        fields=["certificate_path", "certificate_password"],
        skip_condition=lambda s: s.auth_method != "certificate",
    ),
    OnboardingStep.CLIENT_SECRET: StepInfo(
        title="Client Secret Configuration",
        description=(
            "Enter your client secret from Azure AD.\n\n"
            "Note: Client secrets expire and must be renewed periodically. "
            "Consider using certificate authentication for production."
        ),
        fields=["client_secret"],
        skip_condition=lambda s: s.auth_method != "secret",
    ),
    OnboardingStep.TEST_CONNECTION: StepInfo(
        title="Test Connection",
        description=(
            "Test your connection to Exchange Online.\n\n"
            "This will verify your credentials and permissions."
        ),
        fields=[],
    ),
    OnboardingStep.COST_CONFIG: StepInfo(
        title="Cost Configuration",
        description=(
            "Configure license costs for cost analysis.\n\n"
            "Enter the monthly cost per license type in your currency."
        ),
        fields=["e5_cost", "e3_cost", "f3_cost"],
        optional=True,
    ),
    OnboardingStep.COMPLETE: StepInfo(
        title="Setup Complete",
        description=(
            "Congratulations! Your configuration is complete.\n\n"
            "The configuration has been saved. You can modify these settings "
            "at any time from the Settings screen."
        ),
        fields=[],
    ),
}


class OnboardingWizard:
    """
    Wizard to guide users through initial setup.

    Manages state, validates input, and generates configuration.
    """

    def __init__(self, config_path: str = "config.yaml") -> None:
        self._config_path = Path(config_path)
        self._state = OnboardingState()
        self._step_order = list(OnboardingStep)

    @property
    def state(self) -> OnboardingState:
        """Get current wizard state."""
        return self._state

    @property
    def current_step(self) -> OnboardingStep:
        """Get current step."""
        return self._state.current_step

    @property
    def current_step_info(self) -> StepInfo:
        """Get info for current step."""
        return STEPS[self._state.current_step]

    @property
    def is_complete(self) -> bool:
        """Check if wizard is complete."""
        return self._state.current_step == OnboardingStep.COMPLETE

    @property
    def progress(self) -> tuple[int, int]:
        """Get progress as (current, total)."""
        current_idx = self._step_order.index(self._state.current_step)
        return current_idx + 1, len(self._step_order)

    def is_first_run(self) -> bool:
        """Check if this is the first run (no config exists)."""
        return not self._config_path.exists()

    def needs_onboarding(self) -> bool:
        """Check if onboarding is needed."""
        if self.is_first_run():
            return True

        # Check if config is valid
        try:
            config = self._load_existing_config()
            required_fields = [
                config.get("azure", {}).get("tenant_id"),
                config.get("azure", {}).get("client_id"),
                config.get("exchange", {}).get("organization"),
            ]
            return not all(required_fields)
        except Exception:
            return True

    def _load_existing_config(self) -> dict[str, Any]:
        """Load existing configuration if present."""
        if self._config_path.exists():
            with open(self._config_path) as f:
                return yaml.safe_load(f) or {}
        return {}

    def load_existing_values(self) -> None:
        """Load existing config values into state."""
        config = self._load_existing_config()

        azure = config.get("azure", {})
        exchange = config.get("exchange", {})
        costs = config.get("costs", {})

        self._state.tenant_id = azure.get("tenant_id", "")
        self._state.client_id = azure.get("client_id", "")
        self._state.certificate_path = azure.get("certificate_path", "")
        self._state.client_secret = azure.get("client_secret", "")
        self._state.organization = exchange.get("organization", "")

        if azure.get("certificate_path"):
            self._state.auth_method = "certificate"
        elif azure.get("client_secret"):
            self._state.auth_method = "secret"

        self._state.e5_cost = costs.get("e5_monthly", 38.00)
        self._state.e3_cost = costs.get("e3_monthly", 20.00)
        self._state.f3_cost = costs.get("f3_monthly", 10.00)

    def set_value(self, field: str, value: Any) -> None:
        """Set a field value in the state."""
        if hasattr(self._state, field):
            setattr(self._state, field, value)

    def get_value(self, field: str) -> Any:
        """Get a field value from the state."""
        return getattr(self._state, field, None)

    def validate_current_step(self) -> list[str]:
        """
        Validate the current step.

        Returns list of validation errors (empty if valid).
        """
        errors: list[str] = []
        step = self._state.current_step
        info = STEPS[step]

        for field in info.fields:
            error = self._validate_field(field)
            if error:
                errors.append(error)

        self._state.errors = errors
        return errors

    def _validate_field(self, field: str) -> str | None:
        """Validate a single field."""
        value = getattr(self._state, field, None)

        validators: dict[str, Callable[[], str | None]] = {
            "organization": lambda: self._validate_organization(value),
            "tenant_id": lambda: self._validate_guid(value, "Tenant ID"),
            "client_id": lambda: self._validate_guid(value, "Application ID"),
            "certificate_path": lambda: self._validate_certificate_path(value),
            "client_secret": lambda: self._validate_required(value, "Client Secret"),
            "e5_cost": lambda: self._validate_cost(value, "E5"),
            "e3_cost": lambda: self._validate_cost(value, "E3"),
            "f3_cost": lambda: self._validate_cost(value, "F3"),
        }

        validator = validators.get(field)
        if validator:
            return validator()
        return None

    def _validate_organization(self, value: str) -> str | None:
        """Validate organization domain."""
        if not value:
            return "Organization is required"
        if not value.endswith(".onmicrosoft.com") and "." not in value:
            return "Organization should be a domain (e.g., contoso.onmicrosoft.com)"
        return None

    def _validate_guid(self, value: str, name: str) -> str | None:
        """Validate a GUID/UUID format."""
        if not value:
            return f"{name} is required"
        # Basic GUID format check
        value = value.strip().lower()
        if len(value) != 36 or value.count("-") != 4:
            return f"{name} should be a valid GUID"
        return None

    def _validate_certificate_path(self, value: str) -> str | None:
        """Validate certificate file path."""
        if not value:
            return "Certificate path is required"
        if not Path(value).exists():
            return f"Certificate file not found: {value}"
        if not value.lower().endswith((".pfx", ".p12")):
            return "Certificate should be a .pfx or .p12 file"
        return None

    def _validate_required(self, value: str, name: str) -> str | None:
        """Validate a required string field."""
        if not value or not value.strip():
            return f"{name} is required"
        return None

    def _validate_cost(self, value: float, name: str) -> str | None:
        """Validate a cost value."""
        try:
            cost = float(value)
            if cost < 0:
                return f"{name} cost cannot be negative"
        except (TypeError, ValueError):
            return f"{name} cost must be a number"
        return None

    def next_step(self) -> OnboardingStep:
        """
        Move to the next step.

        Skips steps that don't apply based on current state.
        """
        current_idx = self._step_order.index(self._state.current_step)

        while current_idx < len(self._step_order) - 1:
            current_idx += 1
            next_step = self._step_order[current_idx]
            info = STEPS[next_step]

            # Check if this step should be skipped
            if info.skip_condition and info.skip_condition(self._state):
                continue

            self._state.current_step = next_step
            return next_step

        # Already at last step
        return self._state.current_step

    def previous_step(self) -> OnboardingStep:
        """
        Move to the previous step.

        Skips steps that don't apply based on current state.
        """
        current_idx = self._step_order.index(self._state.current_step)

        while current_idx > 0:
            current_idx -= 1
            prev_step = self._step_order[current_idx]
            info = STEPS[prev_step]

            # Check if this step should be skipped
            if info.skip_condition and info.skip_condition(self._state):
                continue

            self._state.current_step = prev_step
            return prev_step

        # Already at first step
        return self._state.current_step

    def can_go_back(self) -> bool:
        """Check if we can go to a previous step."""
        return self._state.current_step != OnboardingStep.WELCOME

    def can_go_forward(self) -> bool:
        """Check if we can go to the next step."""
        return self._state.current_step != OnboardingStep.COMPLETE

    async def test_connection(self) -> tuple[bool, str]:
        """
        Test the connection with current settings.

        Returns (success, message).
        """
        # Import here to avoid circular imports
        try:
            from src.core.exchange_connection import ExchangeConnection

            config = self._build_config()
            connection = ExchangeConnection(
                organization=config["exchange"]["organization"],
                app_id=config["azure"]["client_id"],
                tenant_id=config["azure"]["tenant_id"],
                certificate_path=config["azure"].get("certificate_path"),
                client_secret=config["azure"].get("client_secret"),
            )

            success = await connection.connect()
            if success:
                self._state.connection_tested = True
                self._state.connection_success = True
                return True, "Connection successful! Your credentials are working."
            else:
                self._state.connection_tested = True
                self._state.connection_success = False
                return False, "Connection failed. Please check your credentials."

        except Exception as e:
            self._state.connection_tested = True
            self._state.connection_success = False
            return False, f"Connection error: {str(e)}"

    def test_connection_sync(self) -> tuple[bool, str]:
        """
        Synchronous version of connection test (for non-async contexts).

        Returns (success, message).
        """
        import asyncio

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(self.test_connection())

    def _build_config(self) -> dict[str, Any]:
        """Build configuration dictionary from current state."""
        config: dict[str, Any] = {
            "azure": {
                "tenant_id": self._state.tenant_id,
                "client_id": self._state.client_id,
            },
            "exchange": {
                "organization": self._state.organization,
                "page_size": 1000,
                "timeout": 300,
            },
            "costs": {
                "e5_monthly": self._state.e5_cost,
                "e3_monthly": self._state.e3_cost,
                "f3_monthly": self._state.f3_cost,
                "default_license": "E3",
            },
            "cache": {
                "enabled": True,
                "ttl_minutes": 60,
                "database_path": "data/cache.db",
            },
            "logging": {
                "level": "INFO",
                "file": "logs/app.log",
                "audit_file": "logs/audit.log",
            },
            "ui": {
                "theme": "dark",
                "page_size": 50,
            },
        }

        # Add authentication method
        if self._state.auth_method == "certificate":
            config["azure"]["certificate_path"] = self._state.certificate_path
            if self._state.certificate_password:
                config["azure"]["certificate_password"] = self._state.certificate_password
        else:
            config["azure"]["client_secret"] = self._state.client_secret

        return config

    def save_config(self) -> bool:
        """
        Save the configuration to file.

        Returns True on success.
        """
        try:
            config = self._build_config()

            # Create parent directories if needed
            self._config_path.parent.mkdir(parents=True, exist_ok=True)

            # Create logs and data directories
            Path("logs").mkdir(exist_ok=True)
            Path("data").mkdir(exist_ok=True)

            with open(self._config_path, "w") as f:
                yaml.dump(config, f, default_flow_style=False, sort_keys=False)

            return True
        except Exception as e:
            self._state.errors.append(f"Failed to save config: {e}")
            return False

    def get_summary(self) -> dict[str, Any]:
        """Get a summary of the configuration for review."""
        return {
            "Organization": self._state.organization,
            "Tenant ID": self._state.tenant_id[:8] + "..." if self._state.tenant_id else "",
            "Application ID": self._state.client_id[:8] + "..." if self._state.client_id else "",
            "Auth Method": "Certificate" if self._state.auth_method == "certificate" else "Client Secret",
            "Certificate": self._state.certificate_path if self._state.auth_method == "certificate" else "N/A",
            "E5 Cost": f"${self._state.e5_cost:.2f}/month",
            "E3 Cost": f"${self._state.e3_cost:.2f}/month",
            "F3 Cost": f"${self._state.f3_cost:.2f}/month",
            "Connection Tested": "Yes" if self._state.connection_tested else "No",
            "Connection Status": "Success" if self._state.connection_success else "Not tested",
        }


def create_example_config(path: str = "config.example.yaml") -> None:
    """Create an example configuration file."""
    example = {
        "azure": {
            "tenant_id": "your-tenant-id-here",
            "client_id": "your-client-id-here",
            "certificate_path": "path/to/certificate.pfx",
            "# OR use client_secret instead of certificate": None,
            "# client_secret": "your-client-secret-here",
        },
        "exchange": {
            "organization": "your-org.onmicrosoft.com",
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
            "database_path": "data/cache.db",
        },
        "logging": {
            "level": "INFO",
            "file": "logs/app.log",
            "audit_file": "logs/audit.log",
        },
        "ui": {
            "theme": "dark",
            "page_size": 50,
        },
    }

    with open(path, "w") as f:
        yaml.dump(example, f, default_flow_style=False, sort_keys=False)
