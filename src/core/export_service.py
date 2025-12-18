"""Export service for mailbox data to various formats."""

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from src.core.filter_service import FilterCriteria
from src.data.audit_logger import OperationType
from src.data.models import InactiveMailbox
from src.utils.logging import get_logger

if TYPE_CHECKING:
    from src.data.audit_logger import AuditLogger
    from src.data.database import DatabaseManager

logger = get_logger(__name__)


class ExportError(Exception):
    """Raised when export operations fail."""

    pass


class ExportService:
    """Service for exporting mailbox data to various formats.

    Supports CSV and JSON exports with proper formatting and audit logging.
    """

    # Column mapping for exports
    EXPORT_COLUMNS = [
        ("identity", "Exchange GUID"),
        ("display_name", "Display Name"),
        ("primary_smtp", "Email Address"),
        ("user_principal_name", "UPN"),
        ("when_soft_deleted", "Deleted Date"),
        ("age_days", "Age (Days)"),
        ("size_mb", "Size (MB)"),
        ("item_count", "Item Count"),
        ("license_type", "License"),
        ("monthly_cost", "Monthly Cost"),
        ("hold_types", "Holds"),
        ("litigation_hold", "Litigation Hold"),
        ("recovery_eligible", "Recovery Eligible"),
        ("recovery_blockers", "Blockers"),
        ("operating_company", "Operating Company"),
        ("department", "Department"),
        ("archive_status", "Archive Status"),
    ]

    def __init__(self, db: "DatabaseManager", audit: "AuditLogger") -> None:
        """Initialize export service.

        Args:
            db: Database manager instance
            audit: Audit logger instance
        """
        self._db = db
        self._audit = audit
        logger.debug("ExportService initialized")

    def export_to_csv(
        self,
        mailboxes: list[InactiveMailbox],
        path: Path,
        columns: list[tuple[str, str]] | None = None,
    ) -> int:
        """Export mailboxes to CSV file.

        Args:
            mailboxes: List of mailboxes to export
            path: Output file path
            columns: Optional column mapping (field_name, header_name)

        Returns:
            Number of records exported
        """
        if not mailboxes:
            logger.warning("No mailboxes to export")
            return 0

        columns = columns or self.EXPORT_COLUMNS
        field_names = [col[0] for col in columns]
        header_names = [col[1] for col in columns]

        try:
            # Ensure parent directory exists
            path.parent.mkdir(parents=True, exist_ok=True)

            # Write CSV with UTF-8 BOM for Excel compatibility
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)

                # Write header
                writer.writerow(header_names)

                # Write data rows
                for mailbox in mailboxes:
                    row = self._format_row(mailbox, field_names)
                    writer.writerow(row)

            logger.info(f"Exported {len(mailboxes)} mailboxes to CSV: {path}")

            # Audit log
            self._audit.log_operation(
                OperationType.EXPORT_DATA,
                details={
                    "format": "csv",
                    "path": str(path),
                    "record_count": len(mailboxes),
                    "columns": len(columns),
                },
            )

            return len(mailboxes)

        except Exception as e:
            logger.error(f"Failed to export to CSV: {e}")
            self._audit.log_operation(
                OperationType.EXPORT_DATA,
                result="failure",
                error=str(e),
                details={"format": "csv", "path": str(path)},
            )
            raise ExportError(f"CSV export failed: {e}") from e

    def export_to_json(
        self,
        mailboxes: list[InactiveMailbox],
        path: Path,
        include_metadata: bool = True,
        filter_criteria: FilterCriteria | None = None,
    ) -> int:
        """Export mailboxes to JSON file.

        Args:
            mailboxes: List of mailboxes to export
            path: Output file path
            include_metadata: Include export metadata (date, count, criteria)
            filter_criteria: Filter criteria used (for metadata)

        Returns:
            Number of records exported
        """
        if not mailboxes:
            logger.warning("No mailboxes to export")
            return 0

        try:
            # Ensure parent directory exists
            path.parent.mkdir(parents=True, exist_ok=True)

            # Build export data
            export_data: dict[str, Any] = {}

            if include_metadata:
                export_data["metadata"] = {
                    "export_date": datetime.now().isoformat(),
                    "record_count": len(mailboxes),
                    "export_format": "json",
                }
                if filter_criteria:
                    export_data["metadata"]["filter_criteria"] = filter_criteria.to_dict()

            # Convert mailboxes to dictionaries
            export_data["mailboxes"] = [
                self._mailbox_to_export_dict(mailbox) for mailbox in mailboxes
            ]

            # Write JSON with pretty formatting
            with open(path, "w", encoding="utf-8") as f:
                json.dump(export_data, f, indent=2, default=str)

            logger.info(f"Exported {len(mailboxes)} mailboxes to JSON: {path}")

            # Audit log
            self._audit.log_operation(
                OperationType.EXPORT_DATA,
                details={
                    "format": "json",
                    "path": str(path),
                    "record_count": len(mailboxes),
                    "include_metadata": include_metadata,
                },
            )

            return len(mailboxes)

        except Exception as e:
            logger.error(f"Failed to export to JSON: {e}")
            self._audit.log_operation(
                OperationType.EXPORT_DATA,
                result="failure",
                error=str(e),
                details={"format": "json", "path": str(path)},
            )
            raise ExportError(f"JSON export failed: {e}") from e

    def export_filtered(
        self,
        criteria: FilterCriteria,
        path: Path,
        format: str = "csv",
    ) -> int:
        """Export filtered mailboxes to file.

        Args:
            criteria: Filter criteria to apply
            path: Output file path
            format: Export format ("csv" or "json")

        Returns:
            Number of records exported
        """
        from src.core.filter_service import FilterService

        # Get filtered mailboxes
        filter_service = FilterService(self._db)
        mailboxes = filter_service.filter_mailboxes(criteria)

        if format.lower() == "csv":
            return self.export_to_csv(mailboxes, path)
        elif format.lower() == "json":
            return self.export_to_json(mailboxes, path, filter_criteria=criteria)
        else:
            raise ExportError(f"Unsupported format: {format}")

    def _format_row(self, mailbox: InactiveMailbox, field_names: list[str]) -> list[Any]:
        """Format a mailbox as a CSV row.

        Args:
            mailbox: Mailbox to format
            field_names: List of field names to include

        Returns:
            List of formatted values
        """
        row = []
        for field in field_names:
            value = getattr(mailbox, field, "")

            # Format specific types
            if isinstance(value, datetime):
                value = value.strftime("%Y-%m-%d %H:%M:%S")
            elif isinstance(value, list):
                value = ", ".join(str(v) for v in value)
            elif isinstance(value, bool):
                value = "Yes" if value else "No"
            elif value is None:
                value = ""
            elif isinstance(value, float):
                value = f"{value:.2f}"

            row.append(value)

        return row

    def _mailbox_to_export_dict(self, mailbox: InactiveMailbox) -> dict[str, Any]:
        """Convert mailbox to export dictionary.

        Args:
            mailbox: Mailbox to convert

        Returns:
            Dictionary with formatted values
        """
        data = mailbox.to_dict()

        # Ensure datetime objects are serializable
        for key, value in data.items():
            if isinstance(value, datetime):
                data[key] = value.isoformat()

        return data

    def get_available_formats(self) -> list[str]:
        """Get list of available export formats.

        Returns:
            List of format names
        """
        return ["csv", "json"]

    def suggest_filename(self, format: str, prefix: str = "inactive_mailboxes") -> str:
        """Suggest a filename for export.

        Args:
            format: Export format
            prefix: Filename prefix

        Returns:
            Suggested filename with timestamp
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        extension = format.lower()
        return f"{prefix}_{timestamp}.{extension}"
