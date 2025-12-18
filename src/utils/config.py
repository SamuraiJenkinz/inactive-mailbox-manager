"""Configuration management system with YAML loading and environment variable overrides."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


class ConfigurationError(Exception):
    """Raised when configuration is invalid or cannot be loaded."""

    pass


@dataclass
class ConnectionConfig:
    """Exchange Online connection settings."""

    tenant_id: str = ""
    client_id: str = ""
    default_result_size: int = 10000
    connection_timeout_minutes: int = 30
    auto_reconnect: bool = True
    max_retries: int = 3


@dataclass
class CostAnalysisConfig:
    """License cost analysis settings."""

    license_costs: dict[str, float] = field(
        default_factory=lambda: {
            "E5": 38.00,
            "E3": 20.00,
            "E1": 10.00,
            "F3": 10.00,
            "Exchange_Online_Plan_1": 4.00,
            "Exchange_Online_Plan_2": 8.00,
        }
    )
    currency: str = "USD"
    currency_symbol: str = "$"


@dataclass
class UIConfig:
    """User interface settings."""

    theme: str = "brutalist_dark"
    default_view: str = "terminal"
    rows_per_page: int = 50
    refresh_interval_minutes: int = 60
    confirm_destructive: bool = True


@dataclass
class CacheConfig:
    """Local cache settings."""

    enabled: bool = True
    refresh_on_startup: bool = False
    cache_duration_hours: int = 24
    db_path: str = "data/imm_cache.db"


@dataclass
class AuditConfig:
    """Audit logging settings."""

    enabled: bool = True
    log_level: str = "INFO"
    retention_days: int = 365
    log_path: str = "logs/audit.log"
    json_format: bool = True


@dataclass
class BulkOperationsConfig:
    """Bulk operations settings."""

    max_batch_size: int = 100
    delay_between_operations_seconds: int = 2
    require_confirmation: bool = True
    stop_on_error: bool = False


@dataclass
class ExportConfig:
    """Export settings."""

    default_format: str = "xlsx"
    include_charts: bool = True
    export_path: str = "exports"
    date_format: str = "%Y-%m-%d"
    timestamp_filenames: bool = True


@dataclass
class Config:
    """Main configuration container."""

    connection: ConnectionConfig = field(default_factory=ConnectionConfig)
    cost_analysis: CostAnalysisConfig = field(default_factory=CostAnalysisConfig)
    ui: UIConfig = field(default_factory=UIConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)
    audit: AuditConfig = field(default_factory=AuditConfig)
    bulk_operations: BulkOperationsConfig = field(default_factory=BulkOperationsConfig)
    export: ExportConfig = field(default_factory=ExportConfig)


def _get_env_override(section: str, key: str) -> str | None:
    """Get environment variable override for a config key.

    Format: IMM_<SECTION>_<KEY> (e.g., IMM_CONNECTION_TENANT_ID)
    """
    env_key = f"IMM_{section.upper()}_{key.upper()}"
    return os.environ.get(env_key)


def _apply_env_overrides(config_dict: dict[str, Any]) -> dict[str, Any]:
    """Apply environment variable overrides to configuration dictionary."""
    for section, values in config_dict.items():
        if isinstance(values, dict):
            for key, value in values.items():
                env_value = _get_env_override(section, key)
                if env_value is not None:
                    # Convert to appropriate type based on original value
                    if isinstance(value, bool):
                        values[key] = env_value.lower() in ("true", "1", "yes")
                    elif isinstance(value, int):
                        try:
                            values[key] = int(env_value)
                        except ValueError:
                            pass
                    elif isinstance(value, float):
                        try:
                            values[key] = float(env_value)
                        except ValueError:
                            pass
                    else:
                        values[key] = env_value
    return config_dict


def _dict_to_dataclass(data: dict[str, Any], section: str) -> Any:
    """Convert dictionary to appropriate dataclass based on section name."""
    dataclass_map = {
        "connection": ConnectionConfig,
        "cost_analysis": CostAnalysisConfig,
        "ui": UIConfig,
        "cache": CacheConfig,
        "audit": AuditConfig,
        "bulk_operations": BulkOperationsConfig,
        "export": ExportConfig,
    }

    if section not in dataclass_map:
        return data

    dc_class = dataclass_map[section]
    # Filter out any keys not in the dataclass
    valid_keys = {f.name for f in dc_class.__dataclass_fields__.values()}
    filtered_data = {k: v for k, v in data.items() if k in valid_keys}
    return dc_class(**filtered_data)


def load_config(path: Path | str | None = None) -> Config:
    """Load configuration from YAML file with environment variable overrides.

    Args:
        path: Path to configuration file. Defaults to config/settings.yaml

    Returns:
        Config object with all settings loaded

    Raises:
        ConfigurationError: If configuration file cannot be loaded or is invalid
    """
    if path is None:
        path = Path("config/settings.yaml")
    elif isinstance(path, str):
        path = Path(path)

    # Start with default configuration
    config_dict: dict[str, Any] = {
        "connection": {},
        "cost_analysis": {},
        "ui": {},
        "cache": {},
        "audit": {},
        "bulk_operations": {},
        "export": {},
    }

    # Load from file if it exists
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                file_config = yaml.safe_load(f) or {}
                # Merge file config with defaults
                for section in config_dict:
                    if section in file_config and isinstance(file_config[section], dict):
                        config_dict[section].update(file_config[section])
        except yaml.YAMLError as e:
            raise ConfigurationError(f"Invalid YAML in configuration file: {e}") from e
        except OSError as e:
            raise ConfigurationError(f"Cannot read configuration file: {e}") from e

    # Apply environment variable overrides
    config_dict = _apply_env_overrides(config_dict)

    # Convert to dataclasses
    try:
        config = Config(
            connection=_dict_to_dataclass(config_dict.get("connection", {}), "connection"),
            cost_analysis=_dict_to_dataclass(
                config_dict.get("cost_analysis", {}), "cost_analysis"
            ),
            ui=_dict_to_dataclass(config_dict.get("ui", {}), "ui"),
            cache=_dict_to_dataclass(config_dict.get("cache", {}), "cache"),
            audit=_dict_to_dataclass(config_dict.get("audit", {}), "audit"),
            bulk_operations=_dict_to_dataclass(
                config_dict.get("bulk_operations", {}), "bulk_operations"
            ),
            export=_dict_to_dataclass(config_dict.get("export", {}), "export"),
        )
    except TypeError as e:
        raise ConfigurationError(f"Invalid configuration structure: {e}") from e

    return config


def validate_config(config: Config) -> list[str]:
    """Validate configuration and return list of issues.

    Args:
        config: Configuration object to validate

    Returns:
        List of validation error messages (empty if valid)
    """
    issues: list[str] = []

    # Validate connection settings
    if config.connection.default_result_size < 1:
        issues.append("connection.default_result_size must be positive")
    if config.connection.connection_timeout_minutes < 1:
        issues.append("connection.connection_timeout_minutes must be positive")
    if config.connection.max_retries < 0:
        issues.append("connection.max_retries cannot be negative")

    # Validate UI settings
    if config.ui.rows_per_page < 1:
        issues.append("ui.rows_per_page must be positive")
    if config.ui.refresh_interval_minutes < 0:
        issues.append("ui.refresh_interval_minutes cannot be negative")

    # Validate cache settings
    if config.cache.cache_duration_hours < 1:
        issues.append("cache.cache_duration_hours must be positive")

    # Validate audit settings
    valid_log_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
    if config.audit.log_level.upper() not in valid_log_levels:
        issues.append(f"audit.log_level must be one of {valid_log_levels}")
    if config.audit.retention_days < 1:
        issues.append("audit.retention_days must be positive")

    # Validate bulk operations settings
    if config.bulk_operations.max_batch_size < 1:
        issues.append("bulk_operations.max_batch_size must be positive")
    if config.bulk_operations.delay_between_operations_seconds < 0:
        issues.append("bulk_operations.delay_between_operations_seconds cannot be negative")

    # Validate export settings
    valid_formats = {"xlsx", "csv", "json", "pdf"}
    if config.export.default_format.lower() not in valid_formats:
        issues.append(f"export.default_format must be one of {valid_formats}")

    return issues
