"""PowerShell JSON output parser with error handling."""

import json
import re
from typing import Any

from src.utils.logging import get_logger

logger = get_logger(__name__)


class ParseError(Exception):
    """Raised when PowerShell output cannot be parsed."""

    def __init__(self, message: str, raw_output: str | None = None) -> None:
        self.message = message
        self.raw_output = raw_output
        super().__init__(message)


def parse_json_output(output: str) -> list[dict[str, Any]] | dict[str, Any]:
    """Parse JSON output from PowerShell commands.

    Handles:
    - Single objects (returns dict)
    - Arrays of objects (returns list)
    - Empty output (returns empty list)
    - Malformed JSON with helpful error messages

    Args:
        output: Raw PowerShell output string

    Returns:
        Parsed JSON as dict or list of dicts

    Raises:
        ParseError: If output cannot be parsed as valid JSON
    """
    if not output or not output.strip():
        logger.debug("Empty output, returning empty list")
        return []

    # Clean the output
    cleaned = _clean_output(output)

    if not cleaned:
        return []

    try:
        parsed = json.loads(cleaned)

        # Ensure we return list or dict
        if isinstance(parsed, list):
            return parsed
        elif isinstance(parsed, dict):
            return parsed
        else:
            # Wrap primitive values in a dict
            return {"value": parsed}

    except json.JSONDecodeError as e:
        # Try to provide helpful error message
        error_msg = _format_json_error(cleaned, e)
        logger.error(f"JSON parse error: {error_msg}")
        raise ParseError(error_msg, cleaned) from e


def _clean_output(output: str) -> str:
    """Clean PowerShell output for JSON parsing.

    Removes common non-JSON artifacts from PowerShell output.

    Args:
        output: Raw output string

    Returns:
        Cleaned string ready for JSON parsing
    """
    lines = output.strip().split("\n")
    cleaned_lines = []

    for line in lines:
        # Skip empty lines
        if not line.strip():
            continue

        # Skip PowerShell progress/warning messages
        if line.startswith("WARNING:") or line.startswith("VERBOSE:"):
            continue

        # Skip Exchange Online banner lines
        if "Exchange Online PowerShell" in line:
            continue

        cleaned_lines.append(line)

    cleaned = "\n".join(cleaned_lines).strip()

    # Handle case where output is just whitespace or comments
    if not cleaned:
        return ""

    return cleaned


def _format_json_error(json_str: str, error: json.JSONDecodeError) -> str:
    """Format a helpful JSON error message.

    Args:
        json_str: The JSON string that failed to parse
        error: The JSON decode error

    Returns:
        Formatted error message with context
    """
    lines = json_str.split("\n")
    line_num = error.lineno
    col_num = error.colno

    msg_parts = [f"JSON parse error at line {line_num}, column {col_num}: {error.msg}"]

    # Add context lines if available
    if 0 < line_num <= len(lines):
        context_start = max(0, line_num - 2)
        context_end = min(len(lines), line_num + 1)

        msg_parts.append("\nContext:")
        for i in range(context_start, context_end):
            prefix = ">>> " if i == line_num - 1 else "    "
            msg_parts.append(f"{prefix}{i + 1}: {lines[i][:100]}")

    return "\n".join(msg_parts)


def normalize_property_names(
    data: dict[str, Any] | list[dict[str, Any]],
    to_snake_case: bool = True,
) -> dict[str, Any] | list[dict[str, Any]]:
    """Normalize property names from PowerShell PascalCase.

    Args:
        data: Parsed JSON data
        to_snake_case: Convert to snake_case (default True)

    Returns:
        Data with normalized property names
    """
    if isinstance(data, list):
        return [normalize_property_names(item, to_snake_case) for item in data]

    if not isinstance(data, dict):
        return data

    result = {}
    for key, value in data.items():
        # Convert key
        if to_snake_case:
            new_key = _pascal_to_snake(key)
        else:
            new_key = key

        # Recursively normalize nested structures
        if isinstance(value, dict):
            result[new_key] = normalize_property_names(value, to_snake_case)
        elif isinstance(value, list):
            result[new_key] = [
                normalize_property_names(item, to_snake_case)
                if isinstance(item, dict)
                else item
                for item in value
            ]
        else:
            result[new_key] = value

    return result


def _pascal_to_snake(name: str) -> str:
    """Convert PascalCase to snake_case.

    Args:
        name: PascalCase string

    Returns:
        snake_case string
    """
    # Insert underscore before uppercase letters (except at start)
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    # Insert underscore before uppercase letters followed by lowercase
    s2 = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1)
    return s2.lower()


def extract_error_details(error_output: str) -> dict[str, Any]:
    """Extract structured error information from PowerShell error output.

    Args:
        error_output: PowerShell stderr or error message

    Returns:
        Dictionary with error details
    """
    result: dict[str, Any] = {
        "raw_error": error_output,
        "error_type": "unknown",
        "message": error_output,
        "details": None,
    }

    if not error_output:
        return result

    # Common Exchange Online error patterns
    error_patterns = [
        # Throttling errors
        (
            r"throttl",
            "throttling",
            "Request throttled. Please wait before retrying.",
        ),
        # Session errors
        (
            r"session.*(expired|closed|invalid)",
            "session_expired",
            "Exchange Online session has expired. Reconnection required.",
        ),
        # Authentication errors
        (
            r"(unauthorized|authentication|access.denied)",
            "authentication",
            "Authentication failed or access denied.",
        ),
        # Not found errors
        (
            r"(couldn't be found|does not exist|not found)",
            "not_found",
            "The requested mailbox or resource was not found.",
        ),
        # Invalid operation
        (
            r"(invalid.operation|cannot.perform|not.allowed)",
            "invalid_operation",
            "The requested operation is not valid for this mailbox.",
        ),
        # Hold-related errors
        (
            r"(hold|retention|litigation)",
            "hold_error",
            "Operation blocked due to hold or retention policy.",
        ),
        # Connection errors
        (
            r"(connection|network|timeout)",
            "connection",
            "Connection or network error occurred.",
        ),
    ]

    error_lower = error_output.lower()
    for pattern, error_type, friendly_message in error_patterns:
        if re.search(pattern, error_lower, re.IGNORECASE):
            result["error_type"] = error_type
            result["message"] = friendly_message
            break

    # Try to extract XML error details (Exchange returns XML errors sometimes)
    xml_match = re.search(r"<Message>(.*?)</Message>", error_output, re.DOTALL)
    if xml_match:
        result["details"] = xml_match.group(1).strip()

    return result


def parse_size_value(size_str: str) -> int | None:
    """Parse Exchange size values like "1.5 GB (1,610,612,736 bytes)".

    Args:
        size_str: Size string from Exchange

    Returns:
        Size in bytes, or None if unable to parse
    """
    if not size_str:
        return None

    # Try to extract bytes value in parentheses
    bytes_match = re.search(r"\(([0-9,]+)\s*bytes?\)", size_str, re.IGNORECASE)
    if bytes_match:
        bytes_str = bytes_match.group(1).replace(",", "")
        try:
            return int(bytes_str)
        except ValueError:
            pass

    # Try to parse human-readable format
    size_match = re.match(r"([0-9.]+)\s*(B|KB|MB|GB|TB)", size_str, re.IGNORECASE)
    if size_match:
        value = float(size_match.group(1))
        unit = size_match.group(2).upper()

        multipliers = {
            "B": 1,
            "KB": 1024,
            "MB": 1024**2,
            "GB": 1024**3,
            "TB": 1024**4,
        }

        if unit in multipliers:
            return int(value * multipliers[unit])

    return None


def parse_hold_guids(in_place_holds: list[str] | None) -> list[dict[str, str]]:
    """Parse InPlaceHolds GUID list into structured format.

    Exchange Online holds are identified by GUIDs with prefixes:
    - UniH: Unified Hold (eDiscovery)
    - mbx: Mailbox-level hold
    - skp: Skype for Business hold
    - cld: Cloud-based hold
    - grp: Group hold

    Args:
        in_place_holds: List of hold GUIDs from mailbox

    Returns:
        List of dicts with hold_id and hold_type
    """
    if not in_place_holds:
        return []

    result = []
    for hold in in_place_holds:
        if not hold:
            continue

        hold_info: dict[str, str] = {
            "hold_id": hold,
            "hold_type": "unknown",
            "hold_name": None,
        }

        # Identify hold type by prefix
        if hold.startswith("UniH"):
            hold_info["hold_type"] = "unified_hold"
            hold_info["hold_name"] = "Unified eDiscovery Hold"
        elif hold.startswith("mbx"):
            hold_info["hold_type"] = "mailbox_hold"
            hold_info["hold_name"] = "Mailbox Hold"
        elif hold.startswith("skp"):
            hold_info["hold_type"] = "skype_hold"
            hold_info["hold_name"] = "Skype for Business Hold"
        elif hold.startswith("cld"):
            hold_info["hold_type"] = "cloud_hold"
            hold_info["hold_name"] = "Cloud Hold"
        elif hold.startswith("grp"):
            hold_info["hold_type"] = "group_hold"
            hold_info["hold_name"] = "Group Hold"
        elif "-" in hold and len(hold) == 36:
            # Looks like a plain GUID - likely a retention policy
            hold_info["hold_type"] = "retention_policy"
            hold_info["hold_name"] = "Retention Policy"

        result.append(hold_info)

    return result
