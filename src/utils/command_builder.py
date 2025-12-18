"""PowerShell command builder for Exchange Online operations."""

import re
from typing import Any


class CommandBuilder:
    """Build PowerShell commands for Exchange Online operations.

    Generates properly formatted and parameterized PowerShell commands
    with JSON output for parsing. All commands are designed to be safe
    from injection attacks through proper escaping.
    """

    # Default properties for inactive mailbox queries
    DEFAULT_MAILBOX_PROPERTIES = [
        "ExchangeGuid",
        "Guid",
        "DisplayName",
        "PrimarySmtpAddress",
        "UserPrincipalName",
        "WhenSoftDeleted",
        "WhenCreated",
        "InPlaceHolds",
        "LitigationHoldEnabled",
        "LitigationHoldDate",
        "RetentionPolicy",
        "RetainDeletedItemsFor",
        "SingleItemRecoveryEnabled",
        "ArchiveStatus",
        "ArchiveGuid",
        "RecipientTypeDetails",
        "ExternalDirectoryObjectId",
    ]

    # Properties for mailbox statistics
    STATISTICS_PROPERTIES = [
        "DisplayName",
        "TotalItemSize",
        "ItemCount",
        "TotalDeletedItemSize",
        "DeletedItemCount",
        "LastLogonTime",
        "LastLogoffTime",
    ]

    def __init__(self) -> None:
        """Initialize command builder."""
        pass

    def _escape_parameter(self, value: str) -> str:
        """Escape a string value for safe use in PowerShell.

        Args:
            value: String value to escape

        Returns:
            Escaped string safe for PowerShell parameter
        """
        if not value:
            return "''"

        # Escape single quotes by doubling them
        escaped = value.replace("'", "''")

        # Wrap in single quotes
        return f"'{escaped}'"

    def _escape_identity(self, identity: str) -> str:
        """Escape identity parameter (GUID or email).

        Args:
            identity: Mailbox identity (GUID or email)

        Returns:
            Escaped identity string
        """
        # Check if it's a GUID format
        guid_pattern = r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'
        if re.match(guid_pattern, identity):
            return f"'{identity}'"

        # Otherwise escape as regular string
        return self._escape_parameter(identity)

    def _format_properties(self, properties: list[str]) -> str:
        """Format property list for Select-Object.

        Args:
            properties: List of property names

        Returns:
            Formatted property string for PowerShell
        """
        if not properties:
            return "*"

        # Validate property names (alphanumeric and underscores only)
        valid_properties = []
        for prop in properties:
            if re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', prop):
                valid_properties.append(prop)

        if not valid_properties:
            return "*"

        return ", ".join(valid_properties)

    def build_get_inactive_mailboxes(
        self,
        result_size: int | str = "Unlimited",
        properties: list[str] | None = None,
        include_soft_deleted: bool = True,
    ) -> str:
        """Build command to get inactive mailboxes.

        Args:
            result_size: Number of results to return (int or "Unlimited")
            properties: Specific properties to retrieve (uses defaults if None)
            include_soft_deleted: Include soft-deleted mailboxes

        Returns:
            PowerShell command string
        """
        props = properties or self.DEFAULT_MAILBOX_PROPERTIES
        prop_str = self._format_properties(props)

        # Format result size
        if isinstance(result_size, int):
            size_str = str(result_size)
        else:
            size_str = "Unlimited"

        cmd = f"""Get-EXOMailbox -InactiveMailboxOnly -ResultSize {size_str} -PropertySets All |
    Select-Object {prop_str} |
    ConvertTo-Json -Depth 10 -Compress"""

        return cmd.strip()

    def build_get_mailbox_details(self, identity: str) -> str:
        """Build command to get detailed mailbox information.

        Args:
            identity: Mailbox identity (GUID or email)

        Returns:
            PowerShell command string
        """
        escaped_id = self._escape_identity(identity)
        props = self._format_properties(self.DEFAULT_MAILBOX_PROPERTIES)

        cmd = f"""Get-EXOMailbox -Identity {escaped_id} -PropertySets All |
    Select-Object {props} |
    ConvertTo-Json -Depth 10"""

        return cmd.strip()

    def build_get_mailbox_statistics(self, identity: str) -> str:
        """Build command to get mailbox statistics.

        Args:
            identity: Mailbox identity (GUID or email)

        Returns:
            PowerShell command string
        """
        escaped_id = self._escape_identity(identity)
        props = self._format_properties(self.STATISTICS_PROPERTIES)

        cmd = f"""Get-EXOMailboxStatistics -Identity {escaped_id} |
    Select-Object {props} |
    ConvertTo-Json -Depth 10"""

        return cmd.strip()

    def build_get_mailbox_holds(self, identity: str) -> str:
        """Build command to get mailbox hold information.

        Args:
            identity: Mailbox identity (GUID or email)

        Returns:
            PowerShell command string
        """
        escaped_id = self._escape_identity(identity)

        # Get comprehensive hold information
        cmd = f"""$mbx = Get-EXOMailbox -Identity {escaped_id} -PropertySets Hold
$result = [PSCustomObject]@{{
    Identity = $mbx.ExchangeGuid
    DisplayName = $mbx.DisplayName
    InPlaceHolds = $mbx.InPlaceHolds
    LitigationHoldEnabled = $mbx.LitigationHoldEnabled
    LitigationHoldDate = $mbx.LitigationHoldDate
    LitigationHoldOwner = $mbx.LitigationHoldOwner
    LitigationHoldDuration = $mbx.LitigationHoldDuration
    RetentionPolicy = $mbx.RetentionPolicy
    RetentionHoldEnabled = $mbx.RetentionHoldEnabled
    DelayHoldApplied = $mbx.DelayHoldApplied
    DelayReleaseHoldApplied = $mbx.DelayReleaseHoldApplied
    ComplianceTagHoldApplied = $mbx.ComplianceTagHoldApplied
}}
$result | ConvertTo-Json -Depth 10"""

        return cmd.strip()

    def build_get_retention_policies(self) -> str:
        """Build command to get all retention policies.

        Returns:
            PowerShell command string
        """
        cmd = """Get-RetentionPolicy |
    Select-Object Name, Guid, RetentionPolicyTagLinks, IsDefault |
    ConvertTo-Json -Depth 10 -Compress"""

        return cmd.strip()

    def build_test_connection(self) -> str:
        """Build command to test Exchange Online connection.

        Returns:
            PowerShell command string
        """
        return "Get-EXOMailbox -ResultSize 1 | Select-Object -First 1 | ConvertTo-Json"

    def build_recovery_preflight(self, identity: str) -> str:
        """Build command for recovery pre-flight validation.

        Checks for AuxPrimary shard, auto-expanding archives, and other blockers.

        Args:
            identity: Mailbox identity (GUID or email)

        Returns:
            PowerShell command string
        """
        escaped_id = self._escape_identity(identity)

        cmd = f"""$mbx = Get-EXOMailbox -Identity {escaped_id} -PropertySets Archive, Hold
$mailboxLocation = Get-MailboxLocation -Identity {escaped_id} -ErrorAction SilentlyContinue

$result = [PSCustomObject]@{{
    Identity = $mbx.ExchangeGuid
    DisplayName = $mbx.DisplayName
    ArchiveStatus = $mbx.ArchiveStatus
    ArchiveGuid = $mbx.ArchiveGuid
    AutoExpandingArchiveEnabled = $mbx.AutoExpandingArchiveEnabled
    MailboxLocationType = if ($mailboxLocation) {{ $mailboxLocation.MailboxLocationType }} else {{ 'Unknown' }}
    IsAuxPrimary = if ($mailboxLocation) {{ $mailboxLocation.MailboxLocationType -eq 'AuxPrimary' }} else {{ $false }}
    HasHolds = ($mbx.InPlaceHolds.Count -gt 0) -or $mbx.LitigationHoldEnabled
    HoldCount = $mbx.InPlaceHolds.Count
    LitigationHold = $mbx.LitigationHoldEnabled
    RecoveryEligible = $true
    RecoveryBlockers = @()
}}

# Check for recovery blockers
$blockers = @()
if ($result.IsAuxPrimary) {{
    $blockers += 'AuxPrimary shard mailbox - cannot recover directly'
}}
if ($result.AutoExpandingArchiveEnabled) {{
    $blockers += 'Auto-expanding archive enabled - special handling required'
}}
$result.RecoveryBlockers = $blockers
$result.RecoveryEligible = ($blockers.Count -eq 0)

$result | ConvertTo-Json -Depth 10"""

        return cmd.strip()

    def build_count_inactive_mailboxes(self) -> str:
        """Build command to count total inactive mailboxes.

        Returns:
            PowerShell command string
        """
        cmd = """(Get-EXOMailbox -InactiveMailboxOnly -ResultSize Unlimited).Count"""
        return cmd.strip()

    def build_check_mailbox_exists(self, identity: str) -> str:
        """Build command to check if a mailbox exists.

        Args:
            identity: UPN or mailbox identity to check

        Returns:
            PowerShell command string
        """
        escaped_id = self._escape_identity(identity)
        cmd = f"""Get-EXOMailbox -Identity {escaped_id} -ErrorAction SilentlyContinue |
    Select-Object ExchangeGuid, UserPrincipalName |
    ConvertTo-Json"""
        return cmd.strip()

    def build_check_smtp_exists(self, smtp_address: str) -> str:
        """Build command to check if SMTP address is in use.

        Args:
            smtp_address: SMTP address to check

        Returns:
            PowerShell command string
        """
        escaped_smtp = self._escape_parameter(smtp_address)
        cmd = f"""Get-EXORecipient -Filter "EmailAddresses -eq 'smtp:{smtp_address}'" -ErrorAction SilentlyContinue |
    Select-Object RecipientType, PrimarySmtpAddress |
    ConvertTo-Json"""
        return cmd.strip()

    def build_new_mailbox_from_inactive(
        self,
        inactive_mailbox_guid: str,
        display_name: str,
        upn: str,
        password: str,
        first_name: str | None = None,
        last_name: str | None = None,
        reset_password: bool = True,
    ) -> str:
        """Build command to create new mailbox from inactive mailbox.

        Args:
            inactive_mailbox_guid: GUID of the inactive mailbox
            display_name: Display name for new mailbox
            upn: User principal name (email)
            password: Initial password
            first_name: First name
            last_name: Last name
            reset_password: Force password reset on first login

        Returns:
            PowerShell command string
        """
        escaped_guid = self._escape_identity(inactive_mailbox_guid)
        escaped_name = self._escape_parameter(display_name)
        escaped_upn = self._escape_parameter(upn)
        escaped_pwd = self._escape_parameter(password)

        cmd_parts = [
            f"New-Mailbox -InactiveMailbox {escaped_guid}",
            f"-Name {escaped_name}",
            f"-DisplayName {escaped_name}",
            f"-MicrosoftOnlineServicesID {escaped_upn}",
            f"-Password (ConvertTo-SecureString -String {escaped_pwd} -AsPlainText -Force)",
        ]

        if first_name:
            escaped_first = self._escape_parameter(first_name)
            cmd_parts.append(f"-FirstName {escaped_first}")

        if last_name:
            escaped_last = self._escape_parameter(last_name)
            cmd_parts.append(f"-LastName {escaped_last}")

        if reset_password:
            cmd_parts.append("-ResetPasswordOnNextLogon $true")

        cmd = " ".join(cmd_parts) + " | ConvertTo-Json -Depth 10"
        return cmd

    def build_new_restore_request(
        self,
        source_mailbox: str,
        target_mailbox: str,
        target_root_folder: str | None = None,
        allow_legacy_dn_mismatch: bool = True,
        conflict_resolution: str = "KeepAll",
    ) -> str:
        """Build command to create mailbox restore request.

        Args:
            source_mailbox: Source inactive mailbox GUID
            target_mailbox: Target active mailbox
            target_root_folder: Folder to restore content into
            allow_legacy_dn_mismatch: Allow DN mismatch
            conflict_resolution: How to handle conflicts

        Returns:
            PowerShell command string
        """
        escaped_source = self._escape_identity(source_mailbox)
        escaped_target = self._escape_identity(target_mailbox)

        cmd_parts = [
            f"New-MailboxRestoreRequest -SourceMailbox {escaped_source}",
            f"-TargetMailbox {escaped_target}",
        ]

        if target_root_folder:
            escaped_folder = self._escape_parameter(target_root_folder)
            cmd_parts.append(f"-TargetRootFolder {escaped_folder}")

        if allow_legacy_dn_mismatch:
            cmd_parts.append("-AllowLegacyDNMismatch")

        if conflict_resolution:
            cmd_parts.append(f"-ConflictResolutionOption {conflict_resolution}")

        cmd = " ".join(cmd_parts) + " | ConvertTo-Json -Depth 10"
        return cmd

    def build_get_restore_request_status(self, request_identity: str) -> str:
        """Build command to get restore request status.

        Args:
            request_identity: Restore request identity

        Returns:
            PowerShell command string
        """
        escaped_id = self._escape_parameter(request_identity)
        cmd = f"""Get-MailboxRestoreRequest -Identity {escaped_id} |
    Get-MailboxRestoreRequestStatistics |
    Select-Object Name, Status, PercentComplete, ItemsTransferred, BytesTransferred, BadItemsEncountered |
    ConvertTo-Json -Depth 10"""
        return cmd.strip()

    def build_custom_command(
        self,
        cmdlet: str,
        parameters: dict[str, Any] | None = None,
        select_properties: list[str] | None = None,
        json_output: bool = True,
    ) -> str:
        """Build a custom PowerShell command.

        Args:
            cmdlet: PowerShell cmdlet name
            parameters: Dictionary of parameter names and values
            select_properties: Properties to select
            json_output: Convert output to JSON

        Returns:
            PowerShell command string
        """
        # Validate cmdlet name (basic safety check)
        if not re.match(r'^[A-Za-z]+-[A-Za-z]+$', cmdlet):
            raise ValueError(f"Invalid cmdlet name: {cmdlet}")

        parts = [cmdlet]

        # Add parameters
        if parameters:
            for key, value in parameters.items():
                # Validate parameter name
                if not re.match(r'^[A-Za-z][A-Za-z0-9]*$', key):
                    continue

                if isinstance(value, bool):
                    if value:
                        parts.append(f"-{key}")
                    else:
                        parts.append(f"-{key}:$false")
                elif isinstance(value, (int, float)):
                    parts.append(f"-{key} {value}")
                elif isinstance(value, str):
                    parts.append(f"-{key} {self._escape_parameter(value)}")

        cmd = " ".join(parts)

        # Add Select-Object
        if select_properties:
            props = self._format_properties(select_properties)
            cmd += f" | Select-Object {props}"

        # Add JSON conversion
        if json_output:
            cmd += " | ConvertTo-Json -Depth 10"

        return cmd
