# Plan 07-02 Summary: Error Handling and Onboarding

## Status: COMPLETE

## Completed Tasks

### Task 1: Create centralized error handling (exceptions.py)
- Created `src/utils/exceptions.py`
- Custom exception hierarchy:
  - `AppException` - Base class with error codes, messages, suggestions
  - `ConnectionError` - Exchange Online connection failures
  - `AuthenticationError` - Auth failures (certificate, secret, MFA)
  - `ConfigurationError` - Config file issues
  - `ValidationError` - Input/data validation failures
  - `RecoveryError` - Mailbox recovery failures
  - `RestoreError` - Mailbox restore failures
  - `BulkOperationError` - Bulk operation failures
  - `PowerShellError` - PowerShell execution failures

- `ErrorCode` enum with 40+ error codes organized by category:
  - 1xxx: Connection errors
  - 2xxx: Authentication errors
  - 3xxx: Configuration errors
  - 4xxx: Validation errors
  - 5xxx: Recovery errors
  - 6xxx: Restore errors
  - 7xxx: Bulk operation errors
  - 8xxx: PowerShell errors
  - 9xxx: General errors

- User-friendly message templates for all error codes
- Recovery suggestions for common errors

### Task 2: Create error handler service (error_handler.py)
- Created `src/utils/error_handler.py`
- `ErrorResult` dataclass with:
  - Success flag, message, error code
  - Severity level (info, warning, error, critical)
  - Recovery suggestions
  - Retry capability flag
  - Timestamp

- `ErrorHandler` class with:
  - Exception categorization and mapping
  - Appropriate logging by severity
  - Callback registration for UI notifications
  - `wrap()` method for function decoration
  - `safe_execute()` for try-catch handling

- Utility functions:
  - `get_error_handler()` - Global handler instance
  - `handle_error()` - Convenience wrapper
  - `format_error_for_display()` - UI formatting
  - `format_error_for_log()` - Log formatting

### Task 3: Create onboarding wizard (onboarding.py)
- Created `src/core/onboarding.py`
- `OnboardingStep` enum with 8 steps:
  1. Welcome - Introduction and prerequisites
  2. Organization - Tenant and app details
  3. Auth Method - Certificate vs secret choice
  4. Certificate - .pfx path and password
  5. Client Secret - Secret value
  6. Test Connection - Verify credentials
  7. Cost Config - License pricing
  8. Complete - Summary and finish

- `OnboardingState` dataclass tracking all wizard data
- `StepInfo` with title, description, fields, skip conditions
- `OnboardingWizard` class with:
  - First-run detection via config file
  - Step navigation (next/previous with skip logic)
  - Field validation per step
  - Connection testing (async and sync)
  - Config file generation (YAML)
  - Progress tracking
  - Summary generation

- `create_example_config()` utility function

## Files Created

- `src/utils/exceptions.py` (280 lines) - Exception hierarchy
- `src/utils/error_handler.py` (250 lines) - Error handler service
- `src/core/onboarding.py` (450 lines) - Onboarding wizard

## Key Features

### Exception System
- Structured error codes for programmatic handling
- User-friendly messages for display
- Recovery suggestions for common errors
- Full exception chaining support
- Serialization to dict for logging/API

### Error Handler
- Automatic severity determination
- Retry capability detection
- Callback system for UI notifications
- Both decorator and direct-call patterns
- Formatted output for UI and logs

### Onboarding Wizard
- Smart step skipping based on auth method
- Input validation per field
- Async connection testing
- YAML config generation
- Loads existing config values
- Progress indicator support

## Verification

```bash
python -c "from src.utils.exceptions import *; from src.utils.error_handler import *; from src.core.onboarding import *; print('All imports successful')"
```

## Usage Examples

### Exception Handling
```python
from src.utils.exceptions import AuthenticationError, ErrorCode

raise AuthenticationError(
    code=ErrorCode.AUTH_CERTIFICATE_ERROR,
    details={"path": "/path/to/cert.pfx"}
)
```

### Error Handler
```python
from src.utils.error_handler import get_error_handler

handler = get_error_handler()
result, error = handler.safe_execute(risky_function, arg1, arg2)
if error:
    print(error.message)
    for suggestion in error.suggestions:
        print(f"  - {suggestion}")
```

### Onboarding
```python
from src.core.onboarding import OnboardingWizard

wizard = OnboardingWizard()
if wizard.needs_onboarding():
    # Walk through steps
    wizard.set_value("organization", "contoso.onmicrosoft.com")
    errors = wizard.validate_current_step()
    if not errors:
        wizard.next_step()
```

## Notes

- Exception codes are stable and can be used for localization
- Error handler supports global singleton pattern
- Onboarding wizard is UI-agnostic (can be used in Terminal or Desktop)
- Config file uses YAML for human readability
