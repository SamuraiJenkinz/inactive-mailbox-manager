"""PowerShell execution wrapper with subprocess management."""

import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.utils.logging import get_logger

logger = get_logger(__name__)


class PowerShellError(Exception):
    """Raised when PowerShell command execution fails."""

    def __init__(self, command: str, error_message: str, return_code: int) -> None:
        self.command = command
        self.error_message = error_message
        self.return_code = return_code
        super().__init__(f"PowerShell error (code {return_code}): {error_message}")


@dataclass
class PowerShellResult:
    """Result of a PowerShell command execution."""

    success: bool
    output: str
    error: str
    return_code: int
    duration_ms: int

    def __bool__(self) -> bool:
        """Allow using result in boolean context."""
        return self.success


class PowerShellExecutor:
    """Execute PowerShell commands via subprocess.

    Handles both pwsh (PowerShell Core 7.x) and powershell.exe (Windows PowerShell 5.1).
    Prefers pwsh when available for better cross-platform compatibility.
    """

    def __init__(self, powershell_path: str | None = None) -> None:
        """Initialize PowerShell executor.

        Args:
            powershell_path: Path to PowerShell executable. Auto-detects if not specified.
        """
        self._powershell_path = powershell_path or self._detect_powershell()
        self._base_args = [
            self._powershell_path,
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
        ]
        logger.debug(f"PowerShell executor initialized: {self._powershell_path}")

    def _detect_powershell(self) -> str:
        """Detect available PowerShell executable.

        Returns:
            Path to PowerShell executable (prefers pwsh over powershell.exe)

        Raises:
            PowerShellError: If no PowerShell executable is found
        """
        # Prefer PowerShell Core (pwsh) over Windows PowerShell
        for exe in ["pwsh", "pwsh.exe", "powershell", "powershell.exe"]:
            path = shutil.which(exe)
            if path:
                logger.debug(f"Detected PowerShell: {path}")
                return path

        raise PowerShellError(
            command="",
            error_message="No PowerShell executable found. Install PowerShell Core 7.x (pwsh).",
            return_code=-1,
        )

    @property
    def powershell_path(self) -> str:
        """Get the path to the PowerShell executable."""
        return self._powershell_path

    def _sanitize_for_logging(self, command: str) -> str:
        """Sanitize command for logging (remove sensitive data).

        Args:
            command: Raw PowerShell command

        Returns:
            Sanitized command safe for logging
        """
        # List of patterns to redact
        sensitive_patterns = [
            ("-AccessToken", "***TOKEN***"),
            ("-Password", "***PASSWORD***"),
            ("-Credential", "***CREDENTIAL***"),
            ("-SecureString", "***SECURE***"),
        ]

        sanitized = command
        for pattern, replacement in sensitive_patterns:
            if pattern in sanitized:
                # Simple redaction - replace value after the parameter
                import re

                sanitized = re.sub(
                    rf"{pattern}\s+\S+",
                    f"{pattern} {replacement}",
                    sanitized,
                    flags=re.IGNORECASE,
                )

        return sanitized

    def _wrap_command(self, command: str) -> str:
        """Wrap command in try/catch for better error handling.

        Args:
            command: PowerShell command to wrap

        Returns:
            Wrapped command with error handling
        """
        return f"""
$ErrorActionPreference = 'Stop'
try {{
    {command}
}} catch {{
    Write-Error $_.Exception.Message
    exit 1
}}
"""

    def execute(
        self,
        command: str,
        timeout: int = 120,
        wrap_errors: bool = True,
    ) -> PowerShellResult:
        """Execute a PowerShell command.

        Args:
            command: PowerShell command to execute
            timeout: Timeout in seconds (default 120)
            wrap_errors: Wrap command in try/catch (default True)

        Returns:
            PowerShellResult with output, errors, and timing

        Raises:
            PowerShellError: If command fails and raise_on_error is True
        """
        # Wrap command for better error handling
        if wrap_errors:
            wrapped_command = self._wrap_command(command)
        else:
            wrapped_command = command

        # Build full command line
        args = self._base_args + ["-Command", wrapped_command]

        # Log sanitized command at DEBUG level
        logger.debug(f"Executing: {self._sanitize_for_logging(command)}")

        start_time = time.perf_counter()

        try:
            result = subprocess.run(
                args,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=timeout,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
            )

            duration_ms = int((time.perf_counter() - start_time) * 1000)

            ps_result = PowerShellResult(
                success=result.returncode == 0,
                output=result.stdout.strip(),
                error=result.stderr.strip(),
                return_code=result.returncode,
                duration_ms=duration_ms,
            )

            if ps_result.success:
                logger.debug(f"Command succeeded in {duration_ms}ms")
            else:
                logger.warning(f"Command failed (code {result.returncode}): {ps_result.error[:200]}")

            return ps_result

        except subprocess.TimeoutExpired:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            logger.error(f"Command timed out after {timeout}s")
            return PowerShellResult(
                success=False,
                output="",
                error=f"Command timed out after {timeout} seconds",
                return_code=-1,
                duration_ms=duration_ms,
            )

        except Exception as e:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            logger.error(f"Command execution error: {e}")
            return PowerShellResult(
                success=False,
                output="",
                error=str(e),
                return_code=-1,
                duration_ms=duration_ms,
            )

    def execute_script(
        self,
        script_path: Path | str,
        params: dict[str, Any] | None = None,
        timeout: int = 300,
    ) -> PowerShellResult:
        """Execute a PowerShell script file.

        Args:
            script_path: Path to the .ps1 script file
            params: Dictionary of parameters to pass to the script
            timeout: Timeout in seconds (default 300)

        Returns:
            PowerShellResult with output, errors, and timing
        """
        script_path = Path(script_path)

        if not script_path.exists():
            return PowerShellResult(
                success=False,
                output="",
                error=f"Script not found: {script_path}",
                return_code=-1,
                duration_ms=0,
            )

        # Build parameter string
        param_str = ""
        if params:
            param_parts = []
            for key, value in params.items():
                if isinstance(value, bool):
                    if value:
                        param_parts.append(f"-{key}")
                elif isinstance(value, str):
                    # Escape quotes in string values
                    escaped = value.replace("'", "''")
                    param_parts.append(f"-{key} '{escaped}'")
                else:
                    param_parts.append(f"-{key} {value}")
            param_str = " ".join(param_parts)

        # Build command to execute script
        command = f"& '{script_path}' {param_str}".strip()

        return self.execute(command, timeout=timeout, wrap_errors=True)

    def test_connection(self) -> bool:
        """Test if PowerShell is working correctly.

        Returns:
            True if PowerShell executes successfully
        """
        result = self.execute("Write-Output 'OK'", timeout=10, wrap_errors=False)
        return result.success and "OK" in result.output

    def get_version(self) -> str | None:
        """Get the PowerShell version.

        Returns:
            Version string or None if unable to determine
        """
        result = self.execute("$PSVersionTable.PSVersion.ToString()", timeout=10)
        if result.success:
            return result.output.strip()
        return None

    def check_module(self, module_name: str) -> bool:
        """Check if a PowerShell module is available.

        Args:
            module_name: Name of the module to check

        Returns:
            True if module is available
        """
        result = self.execute(
            f"Get-Module -ListAvailable -Name '{module_name}' | Select-Object -First 1",
            timeout=30,
        )
        return result.success and bool(result.output.strip())
