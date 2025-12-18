# Plan 01-02 Summary: PowerShell Executor and Exchange Connection

**Phase**: 01-foundation
**Plan**: 02 of 3
**Status**: ✅ Complete
**Duration**: ~15 minutes

## Completed Tasks

### Task 1: PowerShell Executor ✅
- Created `src/core/powershell_executor.py`:
  - `PowerShellExecutor` class with subprocess management
  - Auto-detects pwsh (PowerShell Core 7.x) vs powershell.exe
  - `execute(command, timeout)` → `PowerShellResult`
  - `execute_script(script_path, params)` for .ps1 files
  - `PowerShellResult` dataclass: success, output, error, return_code, duration_ms
  - `PowerShellError` exception with command context
  - Command sanitization for logging (redacts tokens, passwords)
  - Error wrapping with try/catch for better messages
  - Helper methods: `test_connection()`, `get_version()`, `check_module()`

### Task 2: Exchange Online Connection ✅
- Created `src/core/exchange_connection.py`:
  - `ExchangeConnection` class with state management
  - `ConnectionState` enum: DISCONNECTED, CONNECTING, CONNECTED, ERROR, RECONNECTING
  - `connect(access_token, tenant_id)` with retry logic
  - `disconnect()` with graceful cleanup
  - `is_connected` property and `check_connection()` health check
  - `ensure_connected()` for auto-reconnect
  - `execute_command()` with session expiration handling
  - Exponential backoff: `delay = min(base * 2^attempt, max_delay)`
  - Session timeout detection via error pattern matching
  - `exchange_session()` context manager for scoped connections

### Task 3: Command Builder and JSON Parser ✅
- Created `src/utils/command_builder.py`:
  - `CommandBuilder` class for safe PowerShell command generation
  - `build_get_inactive_mailboxes(result_size, properties)`
  - `build_get_mailbox_details(identity)`
  - `build_get_mailbox_statistics(identity)`
  - `build_get_mailbox_holds(identity)`
  - `build_recovery_preflight(identity)` - AuxPrimary/archive detection
  - Parameter escaping to prevent injection attacks
  - JSON output formatting with ConvertTo-Json

- Created `src/utils/ps_parser.py`:
  - `parse_json_output(output)` - handles arrays, single objects, empty
  - `normalize_property_names(data)` - PascalCase → snake_case
  - `extract_error_details(error)` - structured error parsing
  - `parse_size_value(size_str)` - Exchange size strings to bytes
  - `parse_hold_guids(holds)` - InPlaceHolds GUID interpretation
  - `ParseError` exception for parse failures

## Verification Results

| Check | Result |
|-------|--------|
| PowerShell executor runs commands | ✅ Pass |
| Command builder generates valid syntax | ✅ Pass |
| JSON parser handles arrays and objects | ✅ Pass |
| Property normalization works | ✅ Pass |
| All imports resolve | ✅ Pass |

## Files Created

```
src/core/
├── __init__.py (updated with exports)
├── powershell_executor.py
└── exchange_connection.py

src/utils/
├── __init__.py (updated with exports)
├── command_builder.py
└── ps_parser.py
```

## Key Design Decisions

1. **Synchronous subprocess**: Used `subprocess.run()` instead of asyncio for simplicity - Exchange Online commands are inherently blocking and sequential
2. **Exponential backoff**: Prevents throttling with increasing delays (1s, 2s, 4s, 8s... up to 30s max)
3. **Session expiration patterns**: Detects common Exchange Online timeout messages for auto-reconnect
4. **Parameter escaping**: All user input is escaped with single quotes and doubled internal quotes
5. **JSON depth 10**: Ensures nested hold structures and mailbox properties are fully serialized

## Error Handling

- PowerShell errors are wrapped in try/catch with meaningful messages
- Session expiration triggers automatic reconnection
- JSON parse errors include context (line, column, surrounding text)
- Exchange errors are categorized: throttling, auth, not_found, hold_error, etc.

## Notes

- Exchange Online module must be installed: `Install-Module -Name ExchangeOnlineManagement`
- Access tokens come from MSAL (implemented in 01-03)
- Connection uses `-AccessToken` parameter (no interactive prompts)
- Commands use `-ShowBanner:$false` for clean automation output

## Next Plan

→ **01-03-PLAN.md**: SQLite caching layer and MSAL authentication
