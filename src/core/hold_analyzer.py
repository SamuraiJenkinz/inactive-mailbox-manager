"""Hold analyzer for comprehensive hold type detection and analysis."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

from src.data.models import RetentionPolicy
from src.utils.logging import get_logger

if TYPE_CHECKING:
    from src.data.session import SessionManager

logger = get_logger(__name__)


class HoldType(Enum):
    """Types of holds that can be applied to mailboxes."""

    LITIGATION_HOLD = "litigation_hold"
    EDISCOVERY_CASE_HOLD = "ediscovery_case_hold"
    RETENTION_POLICY = "retention_policy"
    RETENTION_LABEL = "retention_label"
    IN_PLACE_HOLD = "in_place_hold"
    DELAY_HOLD = "delay_hold"
    SKYPE_HOLD = "skype_hold"
    GROUP_HOLD = "group_hold"
    UNKNOWN = "unknown"

    @property
    def display_name(self) -> str:
        """Get user-friendly display name for hold type."""
        names = {
            HoldType.LITIGATION_HOLD: "Litigation Hold",
            HoldType.EDISCOVERY_CASE_HOLD: "eDiscovery Case Hold",
            HoldType.RETENTION_POLICY: "Retention Policy",
            HoldType.RETENTION_LABEL: "Retention Label",
            HoldType.IN_PLACE_HOLD: "In-Place Hold (Legacy)",
            HoldType.DELAY_HOLD: "Delay Hold",
            HoldType.SKYPE_HOLD: "Skype for Business Hold",
            HoldType.GROUP_HOLD: "Group-based Hold",
            HoldType.UNKNOWN: "Unknown Hold",
        }
        return names.get(self, "Unknown")

    @property
    def priority(self) -> int:
        """Get hold priority for hierarchy (lower = stronger)."""
        priorities = {
            HoldType.LITIGATION_HOLD: 1,
            HoldType.EDISCOVERY_CASE_HOLD: 2,
            HoldType.IN_PLACE_HOLD: 3,
            HoldType.RETENTION_POLICY: 4,
            HoldType.RETENTION_LABEL: 5,
            HoldType.DELAY_HOLD: 6,
            HoldType.SKYPE_HOLD: 7,
            HoldType.GROUP_HOLD: 8,
            HoldType.UNKNOWN: 99,
        }
        return priorities.get(self, 99)


@dataclass
class Hold:
    """Represents a single hold applied to a mailbox."""

    hold_id: str
    hold_type: HoldType
    display_name: str = ""
    description: str | None = None
    source: str | None = None
    applied_date: datetime | None = None
    applied_by: str | None = None
    is_inherited: bool = False
    raw_data: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Set default display name if not provided."""
        if not self.display_name:
            self.display_name = self.hold_type.display_name


@dataclass
class MailboxHoldInfo:
    """Complete hold information for a mailbox."""

    identity: str
    display_name: str = ""
    total_hold_count: int = 0
    holds: list[Hold] = field(default_factory=list)
    has_litigation_hold: bool = False
    has_ediscovery_hold: bool = False
    has_retention_policy: bool = False
    has_retention_label: bool = False
    has_delay_hold: bool = False
    can_be_removed: bool = True
    removal_blockers: list[str] = field(default_factory=list)

    def get_hold_summary(self) -> dict[str, int]:
        """Get count of holds by type."""
        summary: dict[str, int] = {}
        for hold in self.holds:
            type_name = hold.hold_type.display_name
            summary[type_name] = summary.get(type_name, 0) + 1
        return summary


class HoldAnalyzerError(Exception):
    """Raised when hold analysis operations fail."""

    pass


class HoldAnalyzer:
    """Analyzes holds on inactive mailboxes.

    Provides comprehensive hold detection, retention policy resolution,
    and removal eligibility assessment.
    """

    # GUID prefixes for hold type detection
    HOLD_PREFIXES = {
        "UniH": HoldType.EDISCOVERY_CASE_HOLD,
        "mbx": HoldType.IN_PLACE_HOLD,
        "skp": HoldType.SKYPE_HOLD,
        "cld": HoldType.EDISCOVERY_CASE_HOLD,
        "grp": HoldType.GROUP_HOLD,
    }

    def __init__(self, session: "SessionManager") -> None:
        """Initialize hold analyzer.

        Args:
            session: Session manager with active connection
        """
        self._session = session
        self._retention_policy_cache: dict[str, RetentionPolicy] = {}
        self._policy_cache_loaded = False

        logger.debug("HoldAnalyzer initialized")

    def analyze_mailbox_holds(self, mailbox_data: dict[str, Any]) -> MailboxHoldInfo:
        """Analyze all holds on a mailbox.

        Args:
            mailbox_data: Raw mailbox data from Exchange

        Returns:
            Complete hold information for the mailbox
        """
        identity = mailbox_data.get("ExchangeGuid") or mailbox_data.get("Guid") or ""
        display_name = mailbox_data.get("DisplayName") or ""

        hold_info = MailboxHoldInfo(
            identity=identity,
            display_name=display_name,
        )

        holds: list[Hold] = []

        # Check Litigation Hold
        if mailbox_data.get("LitigationHoldEnabled"):
            hold_info.has_litigation_hold = True
            litigation_hold = Hold(
                hold_id="litigation",
                hold_type=HoldType.LITIGATION_HOLD,
                display_name="Litigation Hold",
                source="Exchange Admin Center",
            )

            # Add litigation hold details if available
            if mailbox_data.get("LitigationHoldDate"):
                try:
                    date_str = mailbox_data["LitigationHoldDate"]
                    if isinstance(date_str, str):
                        litigation_hold.applied_date = datetime.fromisoformat(
                            date_str.replace("Z", "+00:00")
                        )
                except (ValueError, TypeError):
                    pass

            if mailbox_data.get("LitigationHoldOwner"):
                litigation_hold.applied_by = mailbox_data["LitigationHoldOwner"]

            holds.append(litigation_hold)

        # Check InPlaceHolds
        in_place_holds = mailbox_data.get("InPlaceHolds") or []
        if isinstance(in_place_holds, str):
            in_place_holds = [in_place_holds]

        for hold_guid in in_place_holds:
            hold = self.decode_hold_guid(hold_guid)
            holds.append(hold)

            # Update flags based on hold type
            if hold.hold_type == HoldType.EDISCOVERY_CASE_HOLD:
                hold_info.has_ediscovery_hold = True
            elif hold.hold_type == HoldType.RETENTION_POLICY:
                hold_info.has_retention_policy = True

        # Check Delay Hold
        if mailbox_data.get("DelayHoldApplied") or mailbox_data.get("DelayReleaseHoldApplied"):
            hold_info.has_delay_hold = True
            holds.append(
                Hold(
                    hold_id="delay",
                    hold_type=HoldType.DELAY_HOLD,
                    display_name="Delay Hold (30 days)",
                    description="Temporary hold after hold removal",
                    source="System",
                )
            )

        # Check Retention Label Hold
        if mailbox_data.get("ComplianceTagHoldApplied"):
            hold_info.has_retention_label = True
            holds.append(
                Hold(
                    hold_id="compliance_tag",
                    hold_type=HoldType.RETENTION_LABEL,
                    display_name="Retention Label Hold",
                    description="Content marked with retention label",
                    source="Microsoft Purview",
                )
            )

        # Check Retention Policy (by name)
        retention_policy_name = mailbox_data.get("RetentionPolicy")
        if retention_policy_name:
            hold_info.has_retention_policy = True
            policy = self.get_policy_by_name(retention_policy_name)
            holds.append(
                Hold(
                    hold_id=policy.policy_id if policy else retention_policy_name,
                    hold_type=HoldType.RETENTION_POLICY,
                    display_name=f"Retention Policy: {retention_policy_name}",
                    description=policy.description if policy else None,
                    is_inherited=policy.is_default if policy else False,
                    source="Microsoft Purview",
                )
            )

        # Update hold info
        hold_info.holds = holds
        hold_info.total_hold_count = len(holds)

        # Determine removal eligibility
        can_remove, blockers = self._assess_removal_eligibility(hold_info)
        hold_info.can_be_removed = can_remove
        hold_info.removal_blockers = blockers

        return hold_info

    def decode_hold_guid(self, guid: str) -> Hold:
        """Decode a hold GUID to determine its type and details.

        Args:
            guid: Hold GUID from InPlaceHolds property

        Returns:
            Hold object with decoded information
        """
        if not guid:
            return Hold(
                hold_id="unknown",
                hold_type=HoldType.UNKNOWN,
                display_name="Unknown Hold",
            )

        # Check for known prefixes
        for prefix, hold_type in self.HOLD_PREFIXES.items():
            if guid.startswith(prefix):
                return Hold(
                    hold_id=guid,
                    hold_type=hold_type,
                    display_name=hold_type.display_name,
                    description=f"Hold ID: {guid}",
                    source=self._get_source_for_type(hold_type),
                )

        # Check if it's a GUID format (likely retention policy)
        if self._is_guid_format(guid):
            # Try to resolve as retention policy
            policy = self.resolve_retention_policy(guid)
            if policy:
                return Hold(
                    hold_id=guid,
                    hold_type=HoldType.RETENTION_POLICY,
                    display_name=f"Retention Policy: {policy.name}",
                    description=policy.description,
                    is_inherited=policy.is_default,
                    source="Microsoft Purview",
                )
            else:
                # Unknown GUID - could be retention policy we couldn't resolve
                return Hold(
                    hold_id=guid,
                    hold_type=HoldType.RETENTION_POLICY,
                    display_name="Retention Policy (Unresolved)",
                    description=f"Policy ID: {guid}",
                    source="Microsoft Purview",
                )

        # Unknown format
        return Hold(
            hold_id=guid,
            hold_type=HoldType.UNKNOWN,
            display_name="Unknown Hold",
            description=f"Hold ID: {guid}",
        )

    def _is_guid_format(self, value: str) -> bool:
        """Check if a string appears to be a GUID format."""
        # Simple GUID format check (8-4-4-4-12 or without hyphens)
        clean = value.replace("-", "").replace("{", "").replace("}", "")
        return len(clean) == 32 and all(c in "0123456789abcdefABCDEF" for c in clean)

    def _get_source_for_type(self, hold_type: HoldType) -> str:
        """Get the typical source for a hold type."""
        sources = {
            HoldType.LITIGATION_HOLD: "Exchange Admin Center",
            HoldType.EDISCOVERY_CASE_HOLD: "Microsoft Purview eDiscovery",
            HoldType.RETENTION_POLICY: "Microsoft Purview",
            HoldType.RETENTION_LABEL: "Microsoft Purview",
            HoldType.IN_PLACE_HOLD: "Exchange Admin Center (Legacy)",
            HoldType.DELAY_HOLD: "System",
            HoldType.SKYPE_HOLD: "Skype for Business",
            HoldType.GROUP_HOLD: "Microsoft 365 Groups",
        }
        return sources.get(hold_type, "Unknown")

    def resolve_retention_policy(self, policy_id: str) -> RetentionPolicy | None:
        """Resolve a retention policy GUID to its details.

        Args:
            policy_id: Retention policy GUID

        Returns:
            RetentionPolicy if found, None otherwise
        """
        # Check cache first
        if policy_id in self._retention_policy_cache:
            return self._retention_policy_cache[policy_id]

        # Load policies if not yet loaded
        if not self._policy_cache_loaded:
            self._fetch_retention_policies()

        return self._retention_policy_cache.get(policy_id)

    def get_policy_by_name(self, name: str) -> RetentionPolicy | None:
        """Get retention policy by name.

        Args:
            name: Retention policy name

        Returns:
            RetentionPolicy if found, None otherwise
        """
        # Load policies if not yet loaded
        if not self._policy_cache_loaded:
            self._fetch_retention_policies()

        # Search by name
        for policy in self._retention_policy_cache.values():
            if policy.name == name:
                return policy

        return None

    def _fetch_retention_policies(self) -> None:
        """Fetch retention policies from Exchange Online."""
        try:
            if not self._session.connection or not self._session.connection.is_connected:
                logger.debug("Not connected - skipping retention policy fetch")
                self._policy_cache_loaded = True
                return

            from src.utils.command_builder import CommandBuilder
            from src.utils.ps_parser import parse_json_output

            builder = CommandBuilder()
            cmd = builder.build_get_retention_policies()

            result = self._session.connection.execute_command(cmd, timeout=60)

            if result.success and result.output:
                data = parse_json_output(result.output)
                if isinstance(data, dict):
                    data = [data]

                for item in data:
                    policy = RetentionPolicy.from_exchange_data(item)
                    self._retention_policy_cache[policy.policy_id] = policy
                    # Also cache by name for quick lookup
                    logger.debug(f"Cached retention policy: {policy.name}")

                logger.info(f"Cached {len(self._retention_policy_cache)} retention policies")
            else:
                logger.warning("Failed to fetch retention policies")

        except Exception as e:
            logger.warning(f"Error fetching retention policies: {e}")

        self._policy_cache_loaded = True

    def get_retention_policies(self) -> list[RetentionPolicy]:
        """Get all cached retention policies.

        Returns:
            List of retention policies
        """
        if not self._policy_cache_loaded:
            self._fetch_retention_policies()
        return list(self._retention_policy_cache.values())

    def _assess_removal_eligibility(
        self, hold_info: MailboxHoldInfo
    ) -> tuple[bool, list[str]]:
        """Assess whether a mailbox can be permanently removed.

        Args:
            hold_info: Hold information for the mailbox

        Returns:
            Tuple of (can_remove, list of blockers)
        """
        blockers: list[str] = []

        if hold_info.has_litigation_hold:
            blockers.append(
                "Litigation Hold must be removed by legal/compliance team in Exchange Admin"
            )

        if hold_info.has_ediscovery_hold:
            blockers.append(
                "eDiscovery case hold must be released in Microsoft Purview Compliance Center"
            )

        if hold_info.has_delay_hold:
            blockers.append(
                "Delay hold is active - wait 30 days after hold removal or contact Microsoft Support"
            )

        # Retention policies are generally less blocking
        if hold_info.has_retention_policy and not any(
            [hold_info.has_litigation_hold, hold_info.has_ediscovery_hold]
        ):
            # Retention policies alone don't fully block recovery
            pass

        if hold_info.has_retention_label:
            blockers.append(
                "Content has retention labels - labels must be removed or expired"
            )

        can_remove = len(blockers) == 0
        return can_remove, blockers

    def get_hold_hierarchy(self, holds: list[Hold]) -> list[Hold]:
        """Sort holds by hierarchy (strongest first).

        Args:
            holds: List of holds to sort

        Returns:
            Sorted list with strongest holds first
        """
        return sorted(holds, key=lambda h: h.hold_type.priority)

    def get_strongest_hold(self, holds: list[Hold]) -> Hold | None:
        """Get the strongest hold from a list.

        Args:
            holds: List of holds

        Returns:
            Strongest hold or None if empty
        """
        if not holds:
            return None
        return self.get_hold_hierarchy(holds)[0]

    def can_remove_mailbox(self, mailbox_data: dict[str, Any]) -> tuple[bool, list[str]]:
        """Check if a mailbox can be permanently removed.

        Args:
            mailbox_data: Raw mailbox data from Exchange

        Returns:
            Tuple of (can_remove, list of blockers)
        """
        hold_info = self.analyze_mailbox_holds(mailbox_data)
        return hold_info.can_be_removed, hold_info.removal_blockers

    def get_removal_steps(self, mailbox_data: dict[str, Any]) -> list[str]:
        """Get ordered steps to remove all holds from a mailbox.

        Args:
            mailbox_data: Raw mailbox data from Exchange

        Returns:
            Ordered list of steps to remove holds
        """
        hold_info = self.analyze_mailbox_holds(mailbox_data)
        steps: list[str] = []

        # Order by hold hierarchy
        sorted_holds = self.get_hold_hierarchy(hold_info.holds)

        for hold in sorted_holds:
            if hold.hold_type == HoldType.LITIGATION_HOLD:
                steps.append(
                    f"1. Remove Litigation Hold via Exchange Admin Center or PowerShell:\n"
                    f"   Set-Mailbox -Identity '{hold_info.identity}' -LitigationHoldEnabled $false"
                )

            elif hold.hold_type == HoldType.EDISCOVERY_CASE_HOLD:
                steps.append(
                    f"2. Release eDiscovery hold '{hold.hold_id}' in Microsoft Purview:\n"
                    f"   - Navigate to Compliance Center > eDiscovery\n"
                    f"   - Find the case and release the hold"
                )

            elif hold.hold_type == HoldType.IN_PLACE_HOLD:
                steps.append(
                    f"3. Remove legacy In-Place Hold '{hold.hold_id}':\n"
                    f"   Remove-MailboxSearch -Identity '{hold.hold_id}'"
                )

            elif hold.hold_type == HoldType.RETENTION_POLICY:
                steps.append(
                    f"4. Remove or exclude from retention policy:\n"
                    f"   - Policy: {hold.display_name}\n"
                    f"   - Exclude mailbox from policy in Compliance Center"
                )

            elif hold.hold_type == HoldType.RETENTION_LABEL:
                steps.append(
                    f"5. Remove retention labels from content:\n"
                    f"   - Review content in mailbox\n"
                    f"   - Remove or wait for label expiration"
                )

            elif hold.hold_type == HoldType.DELAY_HOLD:
                steps.append(
                    f"6. Wait for Delay Hold to expire (30 days):\n"
                    f"   - Or contact Microsoft Support to expedite"
                )

        if not steps:
            steps.append("No holds detected - mailbox can be permanently removed")

        return steps

    def get_hold_details(self, hold_id: str) -> Hold | None:
        """Get details for a specific hold.

        Args:
            hold_id: Hold identifier

        Returns:
            Hold if found, None otherwise
        """
        # Try to decode the hold ID
        return self.decode_hold_guid(hold_id)
