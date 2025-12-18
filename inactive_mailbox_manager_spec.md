# Project: Inactive Mailbox Manager for Microsoft 365

## Overview

Build a Python-based Windows application that provides enterprise-grade management of Microsoft 365 inactive mailboxes through PowerShell automation. The tool addresses critical gaps in Microsoft Purview's 5,000-mailbox portal limit and lack of GUI for recovery, restore, bulk operations, and cost analysis. Designed for large-scale deployments (80,000+ users across multiple operating companies) with brutalist terminal aesthetics.

## Business Problem

**Current State Pain Points:**
- Microsoft Purview portal limited to 5,000 inactive mailboxes
- All critical operations (recover, restore, delete) require PowerShell expertise
- No visual hold type identification (Retention Policy, Litigation Hold, eDiscovery, etc.)
- No cost analysis or license tracking for inactive mailboxes
- Manual CSV workflows for bulk operations
- Complex hold identification requires multiple cmdlets
- No pre-flight validation before destructive operations
- Risk of UPN/SMTP mismatches causing permanent deletion locks

**Target Users:**
- Senior Exchange Engineers
- M365 Administrators
- Compliance Officers
- IT Operations Teams
- Finance (cost analysis stakeholders)

## Tech Stack

- **Core:** Python 3.10+
- **PowerShell Integration:** subprocess + PowerShell Core 7.x (Exchange Online Module)
- **UI Options:**
  - **Primary:** Textual (terminal UI with mouse support)
  - **Secondary:** PyQt6 or CustomTkinter (desktop GUI)
  - **Tertiary:** FastAPI + React (web-based, optional)
- **Data Storage:** SQLite (local cache, audit logs)
- **Authentication:** MSAL (Microsoft Authentication Library) for Azure AD
- **Data Processing:** pandas, openpyxl (Excel export)
- **Visualization:** Rich (terminal formatting), matplotlib (charts)
- **Configuration:** YAML/TOML for settings

## Project Structure

```
InactiveMailboxManager/
├── main.py                          # Entry point with CLI argument parser
├── config/
│   ├── settings.yaml                # User configuration (tenant, defaults)
│   └── branding.yaml                # Terminal colors, ASCII art, theme
├── core/
│   ├── powershell_executor.py       # PowerShell command runner with connection management
│   ├── mailbox_operations.py        # High-level mailbox operations (get, recover, restore)
│   ├── hold_analyzer.py             # Hold type identification and management
│   ├── cost_calculator.py           # License cost analysis and projections
│   └── validator.py                 # Pre-flight checks for operations
├── ui/
│   ├── terminal_ui.py               # Textual-based TUI (primary interface)
│   ├── gui_main.py                  # PyQt6/CustomTkinter GUI (secondary)
│   ├── components/                  # Reusable UI components
│   │   ├── mailbox_table.py
│   │   ├── hold_panel.py
│   │   ├── cost_dashboard.py
│   │   └── recovery_wizard.py
│   └── styles/
│       ├── brutalist_theme.tcss     # Textual CSS for terminal UI
│       └── qt_stylesheet.qss        # Qt stylesheet for GUI
├── data/
│   ├── cache.py                     # SQLite caching layer
│   ├── audit_logger.py              # Comprehensive operation logging
│   └── export_manager.py            # Excel/CSV/JSON export handler
├── utils/
│   ├── authentication.py            # MSAL Azure AD authentication
│   ├── command_builder.py           # PowerShell script generator
│   ├── error_handler.py             # Centralized error handling
│   └── formatting.py                # Output formatters (tables, charts)
├── tests/
│   ├── test_powershell_executor.py
│   ├── test_hold_analyzer.py
│   └── test_cost_calculator.py
├── docs/
│   ├── USER_GUIDE.md
│   ├── POWERSHELL_REFERENCE.md
│   └── TROUBLESHOOTING.md
├── requirements.txt
├── requirements-dev.txt             # Dev dependencies (pytest, black, etc.)
├── pyproject.toml                   # Package configuration
└── README.md
```

## Functional Requirements

### 1. PowerShell Integration (`core/powershell_executor.py`)

**Connection Management:**
- Establish Exchange Online PowerShell session using modern authentication
- Support MFA and conditional access policies
- Maintain persistent connection across operations
- Auto-reconnect on timeout
- Support for multiple tenant configurations

**Command Execution:**
- Execute PowerShell cmdlets with proper error handling
- Parse JSON output from PowerShell commands
- Stream long-running operations with progress updates
- Support for batch operations with retry logic
- Command validation before execution

**Key Methods:**
```python
connect_exchange_online(tenant_id: str) -> bool
disconnect()
get_inactive_mailboxes(result_size: int, filter: str) -> List[Dict]
get_mailbox_statistics(identity: str) -> Dict
identify_holds(identity: str) -> Dict
recover_mailbox(inactive_guid: str, new_user_params: Dict) -> bool
restore_mailbox(source_guid: str, target_identity: str) -> bool
remove_from_retention_policy(identity: str, policy_guid: str) -> bool
bulk_operation(command_template: str, identities: List[str]) -> BatchResult
```

### 2. Mailbox Discovery & Inventory (`core/mailbox_operations.py`)

**Data Retrieval:**
- Fetch all inactive mailboxes (bypassing 5,000 portal limit)
- Retrieve mailbox properties: DisplayName, PrimarySmtpAddress, WhenSoftDeleted, ExchangeGuid, Size, ItemCount
- Calculate mailbox age (days since deletion)
- Determine recovery eligibility (check for AuxPrimary shards, auto-expanding archives)
- Cache results locally with configurable refresh intervals

**Filtering & Search:**
- Filter by: age, hold type, size, cost, operating company, department
- Full-text search across DisplayName, PrimarySmtpAddress
- Saved filter presets ("Aged >3 years", "High cost E5 licenses", etc.)
- Export filtered results to CSV/Excel

**Schema:**
```python
InactiveMailbox:
    - identity: str (ExchangeGuid)
    - display_name: str
    - primary_smtp: str
    - when_soft_deleted: datetime
    - age_days: int
    - size_mb: float
    - item_count: int
    - license_type: str (E5, E3, F3)
    - monthly_cost: float
    - hold_types: List[str]
    - recovery_eligible: bool
    - recovery_blockers: List[str]
    - operating_company: str
    - department: str
```

### 3. Hold Analysis & Management (`core/hold_analyzer.py`)

**Hold Type Identification:**
- Detect all hold types: M365 Retention Policy, Retention Labels, Litigation Hold, eDiscovery Hold, Legacy In-Place Hold
- Parse InPlaceHolds GUIDs and map to readable policy names
- Identify ComplianceTagHoldApplied (retention labels on items)
- Detect DelayHoldApplied and DelayReleaseHoldApplied
- Flag conflicting holds (multiple holds with different durations)

**Hold Operations:**
- Remove mailbox from retention policy (Set-Mailbox -ExcludeFromOrgHolds)
- Change Litigation Hold duration
- Enable/disable Litigation Hold
- List all policies affecting a mailbox
- Visualize hold hierarchy (which hold is controlling retention)

**Risk Detection:**
- Identify UPN/SMTP mismatches (can't be removed from policy)
- Detect auto-expanding archives (can't be recovered)
- Flag AuxPrimary shards (recovery will fail)
- Warn about eDiscovery holds (legal case dependency)

**Output Format:**
```python
HoldAnalysis:
    - mailbox_identity: str
    - holds: List[Hold]
    - primary_hold: Hold (the one controlling retention)
    - hold_conflicts: List[str]
    - removal_blockers: List[str]
    - estimated_deletion_date: datetime | None
    - can_be_deleted: bool
    
Hold:
    - hold_type: str
    - policy_name: str
    - policy_guid: str
    - duration_days: int | None (None = indefinite)
    - applied_date: datetime
    - expires_date: datetime | None
```

### 4. Cost Analysis & Reporting (`core/cost_calculator.py`)

**License Cost Tracking:**
- Maintain license price database (E5=$38, E3=$20, F3=$10 per month)
- Calculate per-mailbox monthly and annual cost
- Aggregate costs by: operating company, department, hold type, age bracket
- Project future costs based on growth trends

**Cost Reports:**
- Total inactive mailbox cost (monthly/annual)
- Cost breakdown by license type
- Top 100 most expensive mailboxes
- Potential savings from cleanup (mailboxes >3 years old)
- Trend analysis (monthly growth in costs)

**Visualizations:**
- Cost distribution pie chart (by license type)
- Age distribution histogram
- Monthly cost trend line chart
- Operating company comparison bar chart

**Export Options:**
- PDF executive summary
- Excel workbook with multiple sheets (detail, summary, charts)
- CSV for finance systems
- PowerBI-compatible JSON

### 5. Recovery Operations (`core/mailbox_operations.py`)

**Pre-Flight Validation:**
- Verify no auto-expanding archive (recovery blocker)
- Check for AuxPrimary shards (recovery blocker)
- Validate target user account doesn't exist
- Confirm UPN/SMTP availability
- Estimate recovery time based on mailbox size

**Guided Recovery Wizard:**
- Step 1: Select inactive mailbox (with search/filter)
- Step 2: Enter new user details (Name, UPN, generate password)
- Step 3: License selection
- Step 4: Preview PowerShell command
- Step 5: Execute with progress tracking
- Step 6: Verify recovery success

**Restore to Existing Mailbox:**
- Select source (inactive) and target (active) mailboxes
- Choose folders to restore (all, or selective)
- Set target folder name (prevent overwriting)
- Handle conflicts (keep both, keep target, keep source)
- Track restore job progress (New-MailboxRestoreRequest)

### 6. Bulk Operations Manager (`core/mailbox_operations.py`)

**CSV-Based Bulk Actions:**
- Import CSV with mailbox identities
- Validate all identities exist
- Preview operations before execution
- Execute with progress tracking
- Generate detailed success/failure report

**Supported Bulk Operations:**
- Remove from retention policy (ExcludeFromOrgHolds)
- Change Litigation Hold status
- Export all mailbox details
- Delete (after hold removal)

**Scheduling:**
- Define recurring cleanup rules
- Schedule operations for off-hours
- Email notifications on completion
- Approval workflows (send email before execution)

### 7. Compliance & Audit Trail (`data/audit_logger.py`)

**Operation Logging:**
- Log every operation: who, what, when, result
- Include PowerShell command executed
- Capture before/after state
- Store in SQLite with full-text search

**Audit Reports:**
- All operations in date range
- All operations by user
- All operations on specific mailbox
- Failed operations summary
- Export to CSV/JSON for SIEM integration

**Compliance Dashboard:**
- Count of mailboxes under each retention policy
- Compliance status (% with proper holds)
- Audit policy adherence
- Regulatory compliance summary (SOX, GDPR, HIPAA)

### 8. Textual Terminal UI (`ui/terminal_ui.py`)

**Main Screen Layout:**
```
┌─────────────────────────────────────────────────────────────────────┐
│ INACTIVE MAILBOX MANAGER - MMC                          [Connected] │
├─────────────────────────────────────────────────────────────────────┤
│ Mailboxes: 5,247  │  Monthly: $104,940  │  Annual: $1,259,280     │
├─────────────────────────────────────────────────────────────────────┤
│ DisplayName      │ Email                │ Deleted    │ Age │ Hold  │
│──────────────────┼──────────────────────┼────────────┼─────┼───────│
│ John Doe         │ john.doe@mmc.com     │ 2022-03-15 │ 1007│ M365  │
│ Jane Smith       │ jane.smith@mmc.com   │ 2021-11-22 │ 1121│ Litig │
│ ...              │                      │            │     │       │
├─────────────────────────────────────────────────────────────────────┤
│ [F1] Help  [F2] Filter  [F3] Recover  [F4] Cost  [F5] Bulk  [Q] Quit│
└─────────────────────────────────────────────────────────────────────┘
```

**Brutalist Design Elements:**
- Dark background (#0d0d0d)
- Terminal green accents (#00ff00)
- Monospace fonts (Consolas, Cascadia Mono)
- ASCII box drawing characters
- Minimal chrome, maximum density
- Keyboard-driven navigation
- Mouse support for clicks

**Key Bindings:**
- `F1`: Help screen
- `F2`: Open filter dialog
- `F3`: Recover selected mailbox
- `F4`: Open cost dashboard
- `F5`: Bulk operations menu
- `F6`: Export to CSV
- `/`: Quick search
- `Enter`: View mailbox details
- `Space`: Multi-select
- `Esc`: Cancel/back
- `Q`: Quit

**Screens:**
1. Main List View (paginated table)
2. Mailbox Detail View (full properties, hold analysis)
3. Hold Management View (visual hold hierarchy)
4. Cost Dashboard (charts and breakdowns)
5. Recovery Wizard (step-by-step)
6. Bulk Operations Queue (progress tracking)
7. Audit Log Viewer (searchable history)
8. Settings Panel (connection, preferences)

### 9. Desktop GUI (Optional - `ui/gui_main.py`)

**PyQt6/CustomTkinter Implementation:**
- Tabbed interface (Discovery, Holds, Recovery, Cost, Bulk, Audit)
- Dark brutalist theme matching terminal UI
- Excel-style data grid with sorting
- Interactive charts (click to drill down)
- Drag-and-drop CSV import
- System tray integration with notifications

**Advantages over Terminal UI:**
- Multiple windows (compare mailboxes side-by-side)
- Richer charts and visualizations
- Easier for non-technical users
- Print preview for reports

## Configuration (`config/settings.yaml`)

```yaml
connection:
  tenant_id: "your-tenant-id"
  default_result_size: 10000
  connection_timeout_minutes: 30
  auto_reconnect: true

cost_analysis:
  license_costs:
    E5: 38.00
    E3: 20.00
    F3: 10.00
  currency: USD

ui:
  theme: brutalist_dark
  default_view: terminal
  rows_per_page: 50
  refresh_interval_minutes: 60

cache:
  enabled: true
  refresh_on_startup: false
  cache_duration_hours: 24

audit:
  enabled: true
  log_level: INFO
  retention_days: 365

bulk_operations:
  max_batch_size: 100
  delay_between_operations_seconds: 2
  send_email_on_completion: true
  approval_required: true

export:
  default_format: xlsx
  include_charts: true
  include_audit_log: true
```

## Non-Functional Requirements

### Performance
- Cold start under 10 seconds (excluding Exchange Online connection)
- List 10,000 mailboxes in under 5 seconds (from cache)
- Refresh 10,000 mailboxes from Exchange in under 2 minutes
- Recover mailbox operation completes in under 60 seconds
- Bulk operations process 100 mailboxes in under 5 minutes

### Reliability
- Auto-reconnect on PowerShell session timeout
- Graceful handling of network interruptions
- Retry logic for transient errors (3 attempts with exponential backoff)
- All destructive operations require confirmation
- Pre-flight validation prevents invalid operations

### Security
- All authentication via MSAL (Azure AD modern auth)
- Support for MFA and conditional access
- Audit log for all operations
- No plaintext password storage
- Configuration file excludes sensitive data (use environment variables)

### Usability
- Clear error messages with remediation steps
- Progress indicators for long operations
- Keyboard shortcuts for power users
- Context-sensitive help (F1)
- Onboarding wizard for first-time setup

### Maintainability
- Comprehensive docstrings (Google style)
- Unit test coverage >80%
- Logging at appropriate levels (DEBUG, INFO, WARNING, ERROR)
- Type hints throughout codebase
- Modular architecture (easy to add new features)

## Acceptance Criteria

### Phase 1: Core Functionality
1. ✅ Connect to Exchange Online and list all inactive mailboxes (>5,000)
2. ✅ Display mailbox details in terminal table with sorting/filtering
3. ✅ Identify all hold types for selected mailbox
4. ✅ Calculate total monthly cost across all inactive mailboxes
5. ✅ Export filtered results to Excel with formatting

### Phase 2: Recovery Operations
6. ✅ Pre-flight validation detects recovery blockers (AuxPrimary, auto-expanding)
7. ✅ Guided recovery wizard creates new active mailbox from inactive
8. ✅ Restore operation merges inactive mailbox into existing mailbox
9. ✅ PowerShell command preview shown before execution
10. ✅ Operation success/failure logged to audit trail

### Phase 3: Bulk Operations
11. ✅ Import CSV with 100+ mailboxes and validate all exist
12. ✅ Remove 100+ mailboxes from retention policy in single batch
13. ✅ Progress bar updates in real-time during bulk operation
14. ✅ Generate success/failure report with details
15. ✅ Schedule recurring cleanup with email approval

### Phase 4: Cost & Reporting
16. ✅ Cost dashboard shows breakdown by license type and operating company
17. ✅ Age distribution histogram displays mailbox age brackets
18. ✅ Export multi-sheet Excel workbook with charts
19. ✅ PDF executive summary includes key metrics and recommendations
20. ✅ Trend analysis projects costs for next 12 months

### Phase 5: Polish & Documentation
21. ✅ Brutalist terminal theme matches provided branding.yaml
22. ✅ Keyboard shortcuts work across all screens
23. ✅ User guide includes screenshots and PowerShell reference
24. ✅ Error messages include KB article links where applicable
25. ✅ First-time setup wizard configures tenant connection

## Out of Scope (v1.0)

- Multi-user / role-based access control
- SharePoint/OneDrive inactive data management
- Real-time alerts via Microsoft Teams/Slack
- Machine learning-based cleanup recommendations
- Mobile app or web portal
- Integration with ITSM systems (ServiceNow, Jira)
- Automated compliance report generation for auditors

## Future Enhancements (Roadmap)

### v1.1
- PyQt6 desktop GUI (in addition to terminal UI)
- Email notifications for expiring holds
- Advanced filtering with query builder
- Mailbox content preview (last 10 emails)

### v1.2
- FastAPI web backend + React frontend
- Multi-tenant support (manage multiple M365 organizations)
- Role-based access control
- Real-time collaboration (multiple users)

### v1.3
- Machine learning-based cost optimization recommendations
- Predictive analytics (forecast future inactive mailbox growth)
- Integration with ServiceNow for ticket creation
- SharePoint/OneDrive inactive site management

### v2.0
- Full GUI rewrite in Tauri (Rust + web frontend)
- Mobile companion app (view-only)
- Microsoft Teams bot integration
- Advanced compliance reporting

## Implementation Notes

### Development Phases

**Phase 1: Foundation (Week 1)**
- Set up project structure
- Implement `powershell_executor.py` with connection management
- Create basic terminal UI with mailbox list view
- Implement local caching with SQLite
- Write unit tests for PowerShell integration

**Phase 2: Core Features (Week 2)**
- Implement hold analyzer with full detection logic
- Add cost calculator with aggregation
- Build filtering and search functionality
- Create export manager (CSV, Excel)
- Add audit logging

**Phase 3: Operations (Week 3)**
- Implement recovery wizard with validation
- Add restore functionality
- Build bulk operations manager
- Create scheduling system
- Implement approval workflows

**Phase 4: Polish (Week 4)**
- Complete brutalist terminal theme
- Add all keyboard shortcuts
- Write comprehensive documentation
- Create tutorial videos
- Perform end-to-end testing in production-like environment

### Testing Strategy

**Unit Tests:**
- Mock PowerShell commands with sample JSON responses
- Test hold identification logic with various configurations
- Verify cost calculations
- Validate CSV parsing and export

**Integration Tests:**
- Test against non-production M365 tenant
- Verify recovery and restore operations
- Test bulk operations with 100+ mailboxes
- Validate audit logging

**Performance Tests:**
- Benchmark list refresh with 10,000 mailboxes
- Measure cache performance
- Test bulk operation throughput
- Profile memory usage

### Deployment

**Standalone Executable (Recommended for v1.0):**
```bash
# Using PyInstaller
pip install pyinstaller
pyinstaller --onefile --add-data "config:config" --add-data "docs:docs" main.py
```

**Python Distribution (For IT teams):**
```bash
# Install from GitHub
pip install git+https://github.com/your-org/inactive-mailbox-manager.git

# Or local development
pip install -e .
```

**Docker Container (For web deployment):**
```dockerfile
FROM python:3.10-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "main.py", "--mode", "web"]
```

## Success Metrics

**Operational Efficiency:**
- Reduce time to identify all inactive mailboxes from 30 min → 2 min
- Reduce mailbox recovery time from 15 min → 2 min
- Enable bulk operations (100+ mailboxes) without manual CSV editing

**Cost Savings:**
- Identify $50K+ annual savings from cleaning aged mailboxes
- Track and report on license reclamation
- Prevent accidental license waste from forgotten inactive mailboxes

**Risk Reduction:**
- Eliminate UPN/SMTP mismatch incidents (can't delete mailboxes)
- Prevent failed recoveries due to auto-expanding archives
- Ensure all operations logged for compliance audits

**User Satisfaction:**
- Net Promoter Score (NPS) >8/10 from Exchange Admins
- 80% of users prefer tool over manual PowerShell
- Zero critical bugs in production after 30 days

---

## Getting Started

### Prerequisites
- Windows 10/11 or Windows Server 2019+
- PowerShell Core 7.x installed
- Exchange Online PowerShell Module v3.x
- Python 3.10+
- Azure AD App Registration (for MSAL authentication)

### Quick Start
```bash
# Clone repository
git clone https://github.com/your-org/inactive-mailbox-manager.git
cd inactive-mailbox-manager

# Install dependencies
pip install -r requirements.txt

# Configure tenant connection
cp config/settings.yaml.example config/settings.yaml
# Edit settings.yaml with your tenant ID

# Set environment variables
export AZURE_CLIENT_ID="your-app-id"
export AZURE_CLIENT_SECRET="your-app-secret"

# Run terminal UI
python main.py --mode terminal

# Or run GUI
python main.py --mode gui
```

### Initial Setup
1. Register Azure AD application with Exchange.ManageAsApp permission
2. Grant admin consent in Azure portal
3. Configure settings.yaml with tenant and application details
4. Test connection: `python main.py --test-connection`
5. Perform initial mailbox discovery: `python main.py --refresh-cache`
6. Launch UI: `python main.py`

---

## Support & Troubleshooting

**Common Issues:**

1. **"Unable to connect to Exchange Online"**
   - Verify Exchange Online PowerShell module installed
   - Check Azure AD app permissions
   - Ensure admin consent granted
   - See: `docs/TROUBLESHOOTING.md#connection-errors`

2. **"5000+ mailboxes not displaying"**
   - Increase `default_result_size` in settings.yaml
   - Use `--result-size unlimited` flag
   - Enable caching for large datasets

3. **"Recovery failed: AuxPrimary shards detected"**
   - Use restore operation instead of recovery
   - See: `docs/POWERSHELL_REFERENCE.md#recovery-vs-restore`

**Contact:**
- Internal Slack: #m365-tools-support
- Email: your-team@company.com
- GitHub Issues: https://github.com/your-org/inactive-mailbox-manager/issues

---

**Document Version:** 1.0  
**Last Updated:** 2024-12-17  
**Author:** OverLord Of AI  
**Reviewed By:** [TBD]  
**Status:** DRAFT - Ready for Development
